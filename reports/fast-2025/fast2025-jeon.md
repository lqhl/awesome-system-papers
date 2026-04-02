# AWUPF Rediscovered: Atomic Writes to Unleash Pivotal Fault-Tolerance in SSDs

**作者**：Jiyune Jeon, Jongseok Kim (Sungkyunkwan University); Sam H. Noh (Virginia Tech); Euiseong Seo (Sungkyunkwan University)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/jeon
**源文件**：[fast2025-jeon.pdf](../../papers/fast-2025/fast2025-jeon.pdf)

---

## 一、背景

现代 SSD 从诞生之初就在 flash page 级别保证了写入的原子性——即使发生掉电，写入要么完整完成，要么完全不可见。NVMe 规范将这一特性标准化为 Atomic Write Unit Power Fail (AWUPF)，大多数 SSD 提供 4KB 的 AWUPF 保证，部分设备甚至支持更大的原子写入粒度（如 256KB NAWUPF）。

然而，主机端软件栈（文件系统、DBMS、RAID）长期以来完全忽视了这一硬件能力。为了保证崩溃一致性，它们依赖 journaling 或 write-ahead logging (WAL)，需要对同一数据进行双重写入（先写日志，再写实际位置），导致写放大和性能下降。此前的研究尝试通过修改 SSD 的 FTL 和主机接口来实现事务性写入，但这些方案侵入性强，难以部署。

---

## 二、要解决的问题

1. **Journaling 开销显著**：Log-RAID 系统（如 PoseidonOS）采用日志结构写入，需要维护动态的 stripe 映射元数据。每次写操作后都需要将映射更新提交到 journal，checkpoint 时再写回元数据区域，导致大量额外 I/O，尤其在小块随机写场景下性能严重退化（实测开启 journaling 后随机写性能下降数倍）。

2. **现有原子写方案侵入性强**：X-FTL、CFS 等方案需要修改 SSD 固件中的 FTL 映射结构或定义新的主机接口，实际部署困难。

3. **AWUPF 能力被浪费**：SSD 已经提供了 page 级别的原子写保证，但主机端从未利用这一特性来减轻崩溃一致性的开销。

---

## 三、洞察与设计

**关键洞察**：SSD 的 AWUPF 特性保证了单次写操作在 AWUPF 大小限制内的原子性。如果元数据更新可以被压缩到一个 AWUPF 大小（通常 4KB）的连续空间内，就可以直接写入元数据区域而无需经过 journaling，从而将崩溃一致性保证"卸载"给 SSD 硬件，无需修改 FTL 或主机接口。

基于此洞察，论文提出了一种**双路径更新策略 (Dual Update Path)**：

- **Direct Path**：当元数据更新量不超过 AWUPF 大小（即只需修改单个 mpage）时，直接原子写入元数据区域，跳过 journal。
- **Journal Path**：当更新量超过 AWUPF 限制（跨越多个 mpage）时，走传统 journaling 路径。

在 PoseidonOS 的 Log-RAID 中，VSA map 的每个 mpage (4KB) 包含约 2MB 虚拟设备块的映射信息。对于 4KB 随机写，每次只需更新单个 mpage 中的一个条目，完美适配 AWUPF 直接写入。

---

## 四、实现细节

**排序冲突与解决**：双路径更新引入了复杂的排序问题——同一个 mpage 可能同时被 journal 和 direct 两条路径更新，崩溃后需要正确恢复。论文识别了两类冲突：

1. **部分提交冲突**（Fig. 3a）：journal 提交未完成时 direct write 已持久化，导致 journal 中的部分更新被错误地保留在存储中。
   - **解决**：将 in-memory mpage 的更新推迟到 journal commit 完成之后。

2. **版本冲突**（Fig. 3b）：journal commit 完成后，同一 mpage 被 direct write 覆盖，再次崩溃后恢复时无法判断哪个版本是最新的。
   - **解决**：在每个 mpage 头部引入 64-bit header（63-bit 版本号 + 1-bit in-use 标志）。

**版本管理机制**：
- 每次 commit 或 direct update 开始时，版本号递增 1
- 更新后的 mpage 版本号同时记录在 journal commit 中
- 当 direct write 的目标 mpage 处于 in-use 状态（正在被 commit）时，不递增版本号，确保两条路径的更新都能在恢复时保留
- 恢复时，仅当 commit log 中的版本 ≥ 元数据区域中的版本时才重放日志

**实现平台**：基于 PoseidonOS (POS)，一个开源的全闪存阵列存储操作系统，使用 SPDK 进行磁盘 I/O。系统配置 56 个 user data reactor 和 20 个 metadata reactor。

---

## 五、实验结果

**硬件环境**：

| 组件 | 规格 |
|------|------|
| Target CPU | Intel Xeon Gold 6336Y 24C/48T × 2 |
| Target Memory | DDR4 32GB RDIMM × 16 (512GB) |
| SSD | Samsung PM9A3 3.84TB × 10 (AWUPF = 4KB) |
| 网络 | Mellanox ConnectX-5 100GbE (NVMe-oF) |

**FIO 微基准测试**：

| 场景 | Our Approach vs Journaled | Our Approach vs Direct |
|------|--------------------------|----------------------|
| 4KB 随机写 | **3.6× 提升** | 接近 Direct 性能 |
| 1MB 随机写 | 平均 20% 提升 | 略低于 Direct |
| 4KB 顺序写 | 接近 | 接近 |
| 2MB 写入 | 接近 Direct | 接近 Direct |

**Filebench 综合负载**：

| 工作负载 | Our Approach vs Journaled (32 线程) |
|----------|-------------------------------------|
| varmail | +14% |
| fileserver | 差异不显著（大请求占比高） |
| OLTP | +21%~73%（随线程数变化） |
| tpcso | 小幅提升（写入强度低） |

**可扩展性**：随 metadata reactor 数增加，Journaled 在 4KB 随机写下几乎无法扩展（checkpoint 瓶颈），而 Our Approach 与 Direct 一样持续获得扩展收益，最大差距达 3.3×。

---

## 六、批判性分析

1. **应用场景局限性较大**：论文仅在 Log-RAID 的 VSA map 更新这一特定场景下验证了 AWUPF 的效果。Log-RAID 天然适合此优化——元数据更新小且连续。但论文在结论中暗示这一思路可以推广到文件系统，却未提供任何可行性分析或原型验证。传统文件系统的元数据更新（inode bitmap + inode entry + directory entry）通常涉及多个不连续位置，远超 4KB AWUPF 限制，推广难度可能被严重低估。

2. **实验基线选择问题**："Direct" 配置（无一致性保证的直接写）作为性能上界参照是合理的，但论文未与任何其他 lightweight consistency 方案（如 soft updates、copy-on-write、epoch-based 等）进行对比，无法判断 AWUPF 方案在一致性开销优化领域的相对优势。

3. **4KB AWUPF 的普遍性存疑**：论文提到"大多数 SSD 提供 4KB AWUPF"，但这一结论仅基于作者自有设备的调查，缺乏系统性的市场调研。部分 SSD 仅提供 512B AWUPF，此时方案的适用性大幅下降。

4. **版本管理机制增加了恢复复杂度**：引入的 64-bit header、版本号比较、in-use 标志等机制虽然解决了正确性问题，但增加了恢复路径的复杂度。论文未讨论恢复时间的开销，也未进行故障注入测试来验证恢复逻辑的正确性。

5. **Filebench 结果选择性呈现**：在 fileserver 负载下 Our Approach 几乎无优势，论文将其归因于"大请求占比高"。但这恰恰说明该优化仅在小块随机写主导的场景下有效，而实际存储系统的写入模式通常是混合的。

---

## 七、总结

本文首次提出利用 SSD 已有的 AWUPF 特性来减轻主机端 journaling 开销，无需修改 SSD 固件或接口。通过在 PoseidonOS 的 Log-RAID 系统中实现双路径更新策略（小更新直接原子写、大更新走 journal），在 4KB 随机写场景下实现了最高 3.6× 的性能提升。方案的核心价值在于"零硬件改动"的实用性，但适用范围受限于元数据更新能被压缩到 AWUPF 大小内的系统，向通用文件系统的推广仍需进一步研究。
