# AtomicDisk: A Secure Virtual Disk for TEEs against Eviction Attacks

**作者**：Hongliang Tian (Ant Group), Xinyi Yu (NICE Lab, Xiamen University), Shaowei Song, Qingsong Chen (Ant Group), Zhihao Zhang, Shiyu Wang (NICE Lab, Xiamen University), Weijie Liu (Nankai University), Erci Xu (Shanghai Jiao Tong University), Shoumeng Yan (Ant Group), Yiming Zhang (NICE Lab, Xiamen University & SJTU)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/tian-hongliang
**源文件**：[fast2025-tian-hongliang.pdf](../../papers/fast-2025/fast2025-tian-hongliang.pdf)

---

## 一、背景

可信执行环境（TEE）是一种广泛采用的硬件安全技术，允许用户在受保护的内存区域中运行敏感应用程序，使得特权级别的对手（如恶意 hypervisor 或 OS）也无法窥视或篡改数据。主流 CPU 架构均已推出 TEE 实现，包括 Intel SGX、AMD SEV 和 Arm CCA。

虽然 TEE 硬件可以保护内存中的数据，但磁盘上的数据仍需通过 TEE 软件进行保护。Intel SGX Protected File System（SGX-PFS）是当前最先进的 TEE 安全存储方案，使用 Merkle Hash Tree（MHT）提供机密性（Confidentiality）、完整性（Integrity）、新鲜性（Freshness）和一致性（Consistency）四项安全属性（CIFC）。

---

## 二、要解决的问题

本文发现 SGX-PFS 存在一种新型攻击漏洞——**驱逐攻击（Eviction Attacks）**：

1. **缓存驱逐产生脆弱快照**：SGX-PFS 内部维护一个固定大小的 MHT 缓存。当缓存满时，脏节点会被自动驱逐（eviction）到磁盘，产生瞬态的磁盘快照。这些快照对用户不可见且不可预期，但从 MHT 角度来看是合法的。

2. **特权对手可利用这些快照**：特权级别的对手可以捕获这些瞬态快照（vulnerable snapshots），并在之后重放给 TEE，从而绕过安全机制。论文展示了一个具体攻击：对手可以捕获 Redis 配置文件写入过程中的中间快照（此时 `requirepass` 指令尚未写入），然后用该快照重启 enclave，从而在无需认证的情况下完全访问 Redis 服务器。该漏洞已被 Intel 确认并分配了 CVE ID。

3. **根本原因**：POSIX 文件系统接口和 block 接口对写入持久化的顺序和时机没有约束，因此存储栈可以在任意时刻进行驱逐，无需等待用户的 sync 请求。TEE 无法区分驱逐产生的脆弱快照和用户 sync 产生的合法磁盘状态。

---

## 三、洞察与设计

**关键洞察**：驱逐攻击的本质在于 TEE 无法区分用户主动 sync 产生的合法磁盘状态和缓存驱逐产生的瞬态快照。如果能在存储层面区分这两种状态——将驱逐写入标记为"未提交"、sync 写入标记为"已提交"——就能在崩溃恢复时丢弃所有未提交的驱逐写入，从而消除攻击面。

基于此洞察，论文提出 **sync atomicity** 安全属性：所有在 sync 请求之前的写入必须以全有或全无（all-or-nothing）的方式提交，即仅当 sync 完成时这些写入才被视为已提交。

**AtomicDisk 设计**：

- 在 SGX-PFS 基础上增强 MHT，为每个数据块引入 committed/uncommitted 两种状态
- 在 metadata node 中新增 `committed` 标志位
- 当缓存驱逐发生时，被驱逐的脏节点写入磁盘后标记为 uncommitted，同时将旧版本保存到 recovery journal
- 当用户发起 sync 时，触发内部 commit 操作：(i) 将所有磁盘块标记为 committed（设置 metadata node 的 committed 标志为 true），(ii) 清除 journal
- 崩溃恢复时，检查 committed 标志：若为 true 则正常打开；否则从 journal 中恢复，仅还原 committed 的旧版本块，忽略 uncommitted 的块

**Journal 设计优化**：为实现简单，AtomicDisk 在驱逐前保存所有旧版本块（不区分 committed/uncommitted）。每个逻辑块在 journal 中首次出现的必定是 committed 的，后续出现的是 uncommitted 的。恢复时使用 in-memory bitmap 追踪已恢复的块。

---

## 四、实现细节

- **语言**：Rust 实现，约 5,000 行代码
- **集成**：与 Occlum library OS（SGX）集成，作为虚拟块设备
- **MHT 结构**：与 SGX-PFS 相同，使用 AES-GCM 进行认证加密
- **密钥管理**：
  - 数据块密钥随机生成，保存在父节点
  - Journal 块密钥通过确定性密钥派生函数（KDK + 递增序列号）生成，简化管理
- **Journal 块链**：每个 journal 块保存下一个块的 MAC，形成链式结构，防止 journal 块被单独回滚
- **写缓冲**：多个 journal 块聚合写入，缓冲区满或 sync 时刷盘
- **Root key 获取**：通过 early userspace（initramfs）解决鸡生蛋问题——先挂载内存中的临时根文件系统，通过远程认证获取 root key，再挂载 AtomicDisk 保护的真实根文件系统
- **开源**：代码和攻击复现工件均已开源

---

## 五、实验结果

**实验环境**：64 核 Intel Xeon (Icelake) @ 3.10GHz, Intel DCS3500 SATA SSD, 256GB 内存（64GB 为 SGX EPC），Linux 5.17, SGX SDK 2.15。磁盘容量 100GB，默认块大小 4KB。

**安全性结果**：

| Trace | 总写入量 | PFSDisk 快照数 | AtomicDisk 快照数 |
|-------|---------|---------------|-----------------|
| hm | 22GB | 280K | 1 |
| mds | 8GB | 276K | 1 |
| prn | 49GB | 788K | 1 |
| wdev | 8GB | 173K | 1 |
| web | 13GB | 311K | 1 |

SGX-PFS 每个 trace 产生数十万脆弱快照，而 AtomicDisk 仅产生 1 个合法快照（由 sync 触发）。

**性能结果（FIO 微基准测试）**：
- AtomicDisk 与 PFSDisk 读写性能相当（均基于 MHT）
- CRYPTDISK（仅加密，无 MHT）写性能快 1.2×–7.5×，读性能快 2.2×–2.8×

**Trace-driven 基准测试**：AtomicDisk 与 PFSDisk 性能相当，与 CRYPTDISK 的差距在小 I/O 工作负载下收窄。

**YCSB 基准测试**：
- Redis：三种磁盘性能相当（Redis I/O 模式轻量）
- BadgerDB：AtomicDisk 和 PFSDisk 性能相当，达到 CRYPTDISK 的 50%–85%

---

## 六、批判性分析

1. **安全改进的实际影响有限**：论文展示的攻击场景（Redis 配置文件写入中间状态）虽然真实但相当特殊。需要应用程序恰好在初始化阶段写入安全敏感的配置，且此过程中发生缓存驱逐。论文未充分讨论在多文件场景下攻击的可行性（自己也承认留作 future work），而实际生产环境中多文件状态一致性问题更为常见和严重。

2. **性能评估的基线选择**：CRYPTDISK 作为不提供 freshness 和 consistency 的方案，不具备 AtomicDisk 要求的安全属性，与之对比并不公平。更有意义的对比应是与其他提供完整安全属性的方案（如 transactional file systems）比较，但论文仅定性讨论了这些相关工作。

3. **Journal 空间开销未充分评估**：AtomicDisk 的 journal 需要保留所有旧版本块直到下次 sync，而 SGX-PFS 在驱逐完成后即可清除。论文承认 AtomicDisk 消耗更多磁盘空间，但未给出量化数据。对于写密集型工作负载或 sync 间隔较长的应用，journal 空间膨胀可能成为实际问题。

4. **单文件保护的局限性**：AtomicDisk 继承了 SGX-PFS 只能保护单个文件的限制。实际应用通常涉及多个文件的协调更新（如数据库的数据文件 + WAL + 元数据），跨文件的 sync atomicity 是一个更难但更重要的问题，论文未涉及。

5. **Threat model 的排除项较多**：论文不考虑 DoS 攻击、侧信道攻击和全盘回滚攻击。特别是磁盘访问模式侧信道在 TEE 场景中是一个已知且严重的威胁，完全排除使得安全保证有较大缺口。

---

## 七、总结

本文发现了 TEE 安全存储中的一种新型驱逐攻击，揭示了 SGX-PFS 因缓存驱逐产生的瞬态磁盘快照可被特权对手利用的安全漏洞。论文提出 sync atomicity 安全属性和 AtomicDisk 系统来解决此问题，通过区分 committed/uncommitted 状态并增强 recovery journal，在几乎不影响 I/O 性能的前提下完全消除了驱逐产生的脆弱快照。该工作的核心贡献在于问题的发现和形式化定义，系统设计相对简洁但有效，主要局限在于仅支持单文件保护且未覆盖多文件跨文件场景。
