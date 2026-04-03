# Accelerating Nested Virtualization with HyperTurtle

**作者**：Ori Ben Zur, Jakob Krebs (Technion), Shai Aviram Bergman (Huawei Zurich Research Center), Mark Silberstein (Technion)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/zur
**源文件**：[[atc2025-zur.pdf]]

---

## 一、背景

基于虚拟机的容器（如 Kata containers）通过 CPU 虚拟化能力提供比进程级容器更强的隔离性，被多家云厂商采用。在实际部署中，Kata containers 通常作为嵌套虚拟机（nested VMs）运行——L1 虚拟机中运行虚拟化管理程序来管理 L2 容器 VM。这种嵌套虚拟化架构为工作负载整合和灵活部署提供了便利。

然而，嵌套虚拟化带来了严重的性能开销，主要源于虚拟化层之间过多的 world switch（上下文切换）。在非嵌套场景中，一次 EPT fault 只需 2 次 world switch，而嵌套场景需要 6 次。每次 world switch 约 1µs，占 vm-exit 总处理时间的约 33%。此外，从 L2 触发的 world switch 比从 L1 触发的更昂贵（如 cpuid hypercall：0.78µs vs 2.77µs，NMI：5.7µs vs 16.7µs）。

---

## 二、要解决的问题

1. **EPT fault 处理开销过大**：嵌套场景下 EPT fault 延迟是非嵌套的 5.1×（28.39µs vs 5.58µs），直接拖慢 Kata 容器启动时间——嵌套 Kata 容器启动耗时 1.5s（其中 EPT fault 占 46%），非嵌套仅 0.7s
2. **网络 I/O 性能下降**：两层 VirtIO 虚拟化（Nested-VirtIO）导致延迟增加 1.6×。Direct-Assignment（DVH）虽然性能好，但让 L1 失去了对 L2 网络策略的控制权（路由、监控、流量整形）
3. **性能 profiling 开销大**：从 L1 profiling L2 应用的采样延迟是 profiling L0→L1 的 10.7×（60.68µs vs 5.66µs），因为需要 26 次 world switch

已有方案各有局限：DVH 牺牲 L1 对 L2 的控制权；SVT 依赖 SMT（正在被淘汰）；PVM/X-Containers/CKI 需要侵入式代码修改或硬件变更；Peer-Pods/Free-The-Turtles 完全回避嵌套但失去灵活性。

---

## 三、洞察与设计

**关键洞察**：嵌套虚拟化的性能瓶颈在于 L2 vm-exit 必须经 L0 转发给 L1 处理再返回，产生大量冗余 world switch。如果能将 L1 hypervisor 中处理 vm-exit 的关键逻辑封装为 eBPF 程序，直接在 L0 上下文中执行，就可以跳过 L1 的介入，从根本上消除这些冗余 world switch，同时通过 eBPF 的验证机制保证安全性。

基于此洞察，HyperTurtle 的核心设计：

- **Hyperupcall 机制**：L1 将自身 hypervisor 的关键功能编译为 eBPF 字节码，通过 hypercall 注册到 L0。L0 在处理 L2 vm-exit 时直接执行该 eBPF，而非转发给 L1
- **通用设计方法（Recipe）**：三步走——(1) 共享信息：通过 eBPF maps 和 helper functions 暴露 L1 状态给 eBPF；(2) Hook into L0：在 L0 hypervisor 中添加事件拦截钩子；(3) 开发 eBPF 程序：实现具体功能
- **安全模型**：eBPF 程序经过 L0 内核标准验证器检查；支持两种模式——L1 提供的 eBPF 由 L0 验证器保障安全，或云厂商预审签名的 eBPF

该设计应用于三个子系统：

1. **EPT fault 处理**：hyperupcall 在 L0 发现 EPT₁→₂ 缺失时直接调用，使用预分配内存池映射页面，避免进入 L1。通过 fault log（共享 eBPF map）和锁机制保持与 L1 的一致性
2. **网络控制**：在 Direct-Assignment 的基础上，L1 在 L0 的网络接口上安装 eBPF 程序（防火墙、限速器、TCP-Top 等），恢复对 L2 网络策略的控制
3. **性能 profiling**：将 profiling 采样事件处理 offload 到 L0，通过 ring buffer 共享采样结果给 L1

---

## 四、实现细节

**EPT fault hyperupcall**：
- 使用预分配内存池（4096 frames），避免在 eBPF 上下文中分配内存
- 引入 `bpf_probe_read_hyperupcall` helper function，允许 eBPF 安全访问 L1 物理内存（验证地址合法性和 VM 归属）
- 通过 cyclic fault log（共享 map）通知 L1 hyperupcall 所做的 EPT₁→₂ 映射变更
- 使用锁（通过共享 map 暴露给 L1）防止竞态条件；获取锁失败则 fallback 到传统 EPT fault 机制
- 对 shmem page fault handler 包装额外逻辑，确保与 virtiofsd 等外部进程的一致性

**网络 hyperupcall**：
- 实现了 4 个 PoC eBPF 程序：Pass（空处理）、Stateless Firewall、Rate Limiter、TCP-Top
- 开发自定义 CNI 插件，集成动态 Direct-Assignment 接口管理，兼容 Kubernetes
- 每个 L2 可以安装不同的 eBPF 网络程序，确保隔离

**Profiling hyperupcall**：
- 利用 Linux 已有的 perf syscall 接口注册 eBPF 采样事件
- 引入 `vcpu_probe` helper function 读取 L2 寄存器状态
- 采样结果通过 ring buffer（共享 map）传递给 L1

**代码修改规模**：总计约 2400 LOC，其中 L0 内核/KVM 270 LOC，L0 QEMU 775 LOC，L1 内核 685 LOC，eBPF 程序 888 LOC（EPT fault 566 LOC 为最复杂部分）。

---

## 五、实验结果

实验平台：2× Xeon Silver 4216 (16-core, 2.1GHz)，512GiB RAM，Nvidia MT27710 NIC，SMT off。L1：12 vCPUs, 64GiB RAM, QEMU VMM。L2：1 vCPU, 2GiB RAM, Cloud-Hypervisor VMM (Kata containers)。

### 微基准测试

| 指标 | Vanilla 嵌套 | HyperTurtle | 非嵌套 (上界) | 改善 |
|------|-------------|-------------|--------------|------|
| EPT fault 平均延迟 | 28.39µs | ~5.4µs | 5.58µs | 5.25× |
| EPT fault 99p 延迟 | 49.13µs | ~10.3µs | 9.35µs | 4.76× |
| Profiling 采样延迟 | 60.68µs | ~8.5µs | 5.66µs (L0→L1) | 7.15× |

网络延迟（UDP 1-byte round-trip）：

| 配置 | 平均延迟 | 99p 延迟 | 吞吐量 |
|------|---------|---------|--------|
| Nested-VirtIO | 90.2µs | 106µs | 12.1 Gb/s |
| Direct-Assignment | 54.52µs | 67µs | 17.4 Gb/s |
| HyperTurtle + Pass | 55.0µs | 67µs | 17.3 Gb/s |
| HyperTurtle + Firewall | 60.5µs | 73µs | 17.1 Gb/s |

### 宏基准测试

**Kata 容器启动时间**（4KiB pages）：HyperTurtle 平均降低 27%，2MiB pages 降低 8%。Redis 1GiB snapshot 启动加速 55%，DeathStarBench TextService 加速 35%。

**应用吞吐量**：
- Nginx：HyperTurtle 比 Nested-VirtIO 提升 45%（1.24K → 1.8K QPS），与 Direct-Assignment 持平
- Redis：提升最高 65%
- Memcached（500µs SLA）：29K → 50K QPS（+72%），仅比 Direct-Assignment 低 9%

**Profiling 对 Memcached 影响**：4000Hz 采样率下，HyperTurtle profiler 比 L1 profiling 提升 26% 吞吐量。

---

## 六、批判性分析

1. **EPT fault hyperupcall 的并发限制**：当前实现使用全局 L0 eBPF hook，只允许一个 L1 对一个 L2 使用 EPT fault hyperupcall。这在多租户场景下是严重限制，论文将其轻描淡写为"future work"，但这是实际部署的根本障碍

2. **不支持 huge pages**：EPT fault hyperupcall 不支持大页映射。论文声称"huge page EPT faults are scarce"，但在生产环境中大量使用 2MiB/1GiB huge pages 是常态，2MiB pages 实验中启动时间改善仅 8%（vs 4KiB 的 27%）也间接说明了这一限制的影响

3. **安全模型的实际可行性存疑**：论文提出 L1 可以向 L0 注册任意 eBPF 程序。即使有 eBPF verifier，让租户向底层 hypervisor 注入代码在安全合规严格的云环境中很难被接受。"cloud vendor-vetted eBPFs" 模式更现实，但大大限制了灵活性

4. **锁竞争和 fallback 路径未充分评估**：EPT fault hyperupcall 在获取锁失败或内存池耗尽时 fallback 到传统机制。在高并发 EPT fault 场景下（如多个 L2 同时启动），fallback 频率和性能影响未被量化

5. **实验配置单一**：所有实验使用 L2=1 vCPU, 2GiB RAM，未展示多 vCPU、大内存工作负载、多 L2 并发等更接近生产的配置下的表现

6. **与 Cloud-Hypervisor 绑定**：论文使用 Cloud-Hypervisor 作为 Kata 的 VMM（因为支持 pass-through），但市场上 Firecracker 更为流行。虽然声称兼容其他 VMM，未提供实验验证

---

## 七、AI Infra / MLSys 视角

1. **GPU 嵌套虚拟化加速**：当前 AI Infra 中 GPU 虚拟化（如 vGPU、MIG）在嵌套场景下性能很差。HyperTurtle 的 hyperupcall 思路可以扩展到 GPU MMIO/DMA 操作的 offloading，减少 GPU 虚拟化中的 world switch 开销

2. **Serverless AI 推理冷启动优化**：Kata containers 的启动时间优化（降低 27%）对 serverless AI 推理场景有直接价值。大模型推理服务需要强隔离（处理敏感数据）+ 快速冷启动，HyperTurtle 让 VM-based sandbox 更接近容器的启动速度

3. **eBPF offloading 的设计模式可迁移**：将上层逻辑封装为 eBPF 下沉到底层执行的模式，可以应用于 AI Infra 中的其他分层系统。例如，在分布式训练框架中，将通信调度逻辑以 eBPF 形式 offload 到网络层（SmartNIC/DPU），减少 CPU 参与

4. **值得跟进的方向**：
   - 将 hyperupcall 扩展到 NVMe/存储设备直通，加速 checkpoint/restore 和模型加载中的 I/O
   - 探索 eBPF + SmartNIC 组合在嵌套虚拟化场景下完全卸载 RDMA 网络虚拟化逻辑的可能性

---

## 八、总结

HyperTurtle 通过将 L1 hypervisor 的关键 vm-exit 处理逻辑封装为 eBPF 程序（hyperupcall）并在 L0 直接执行，有效减少了嵌套虚拟化中冗余的 world switch。系统在 EPT fault 处理（5×加速）、网络（恢复 L1 控制权的同时达到 DVH 级别性能）和 profiling（7×加速）三个子系统中展示了显著收益，且代码改动量适中（~2400 LOC）。主要局限在于 EPT fault hyperupcall 的并发限制（单 L1 单 L2）、不支持 huge pages、以及安全模型在多租户生产环境中的可行性仍需验证。
