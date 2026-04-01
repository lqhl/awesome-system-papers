# MettEagle: Costs and Benefits of Implementing Containers on Microkernels

**作者**：Till Miemietz, Viktor Reusch, Matthias Hille (Barkhausen Institut); Lars Wrenger (Leibniz-Universität Hannover); Jana Eisoldt (Barkhausen Institut); Jan Klötzke (Kernkonzept GmbH); Max Kurze (TU Dresden); Adam Lackorzynski (TU Dresden & Kernkonzept GmbH); Michael Roitzsch (Barkhausen Institut); Hermann Härtig (Barkhausen Institut & TU Dresden)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/miemietz
**源文件**：[osdi25-miemietz.pdf](../../papers/osdi-2025/osdi25-miemietz.pdf)

---

## 一、背景

云计算环境中，容器（containers）和轻量级虚拟机（lightweight VMs）是隔离不可信工作负载的两大主流机制。容器因为与宿主机共享内核、启动快、性能接近裸机，成为 serverless computing 等场景的首选隔离方案。然而，容器的安全隔离依赖于 Linux 内核中大量复杂机制——seccomp-bpf（系统调用过滤）、namespaces（可见性限制）、cgroups（资源限制），这些机制显著增加了内核的复杂度和攻击面。

从操作系统工程视角看，容器本质上只是经过"加固"的进程（组），需要额外机制来限制进程本来就拥有的 ambient authority。这个问题的根源在于单体内核（monolithic kernel）的设计：进程默认拥有对大量内核接口的访问权限，容器需要"事后补救"地限制这些权限。

微内核（microkernel）架构在设计上遵循最小权限原则（Principle of Least Authority, PoLA）——进程默认没有任何权限，必须显式获取 capability 才能访问系统服务。这一根本性差异使得微内核上的容器隔离可能天然更简洁、更安全。

---

## 二、要解决的问题

1. **单体内核容器的复杂性与安全风险**：Linux 容器依赖 seccomp-bpf、namespaces、cgroups 等内核机制来"补偿"进程默认拥有的过多权限。这些机制增加了共享内核的代码量和攻击面，历史上已出现大量 CVE（如权限逃逸、内存破坏）。

2. **微内核能否胜任容器场景尚未被验证**：微内核在概念上天然适合容器隔离，但现有微内核系统主要用于嵌入式/静态配置场景。是否能在服务器级硬件上支持高度动态的工作负载（如 FaaS），其性能是否能与 Linux 容器竞争，此前没有系统性研究。

3. **微内核在并行/大规模场景下的可扩展性问题**：L4Re 等微内核系统的核心组件（内核数据结构锁、内存管理器）采用粗粒度锁，在高并发容器启动场景下可能成为瓶颈。

---

## 三、洞察与设计

**关键洞察**：在 capability-based 微内核上，进程默认没有 ambient authority，隔离是系统的固有属性而非后加的限制层。因此，Linux 容器中用于限制进程权限的三大机制（seccomp-bpf、namespaces、cgroups）在微内核上要么不需要，要么可以用更简洁的方式实现，从而在不牺牲安全性的前提下降低系统复杂度。

基于这一洞察，作者设计了 MettEagle——一个运行在 L4Re 微内核上的容器引擎（称为 compartment engine）。核心设计包括：

- **Compartment 架构**：每个 compartment（对应 Linux 容器）是一组 L4Re 进程，共享一组 capabilities。Compartment engine 分为两层：compartment service（类似 runC 的低层运行时）和 Phlox（高层运行时，提供 FaaS API）。

- **可见性限制**：通过 capability delegation 控制 compartment 能访问哪些系统服务，而非像 Linux namespaces 那样在内核中虚拟化资源标识符。L4Re 没有全局 PID、共享内存 key 等概念，资源全部通过 capabilities 引用，天然实现了资源隔离。

- **系统调用限制**：通过 IPC gate 的分层设计，系统服务为不同客户端暴露不同的 IPC gate（control plane vs. data plane），compartment 只能通过 session-specific gate 访问数据面操作，无需 seccomp-bpf 这类运行时过滤机制。

- **资源限制**：通过系统服务的 session 机制实现资源配额，类似 cgroups 但分布在各个独立的用户态服务中，无需统一的内核级框架。

---

## 四、实现细节

MettEagle 在 L4Re 公开开发仓库基础上构建，主要新增/修改组件：

| 组件 | SLOC | 功能 |
|------|------|------|
| L4Re kernel | 41,406 | 微内核 |
| SPAFS | 501 | 可写内存文件系统 |
| LUNA | 8,735 | NIC 驱动 + UDP/IP 网络栈 |
| LSMM | 4,289 | 并行化内存管理器（替代 moe 的内存管理） |
| PROMFS | 780 | 并行化 boot 文件系统 |
| Compartment Service | 1,793 | 容器生命周期管理 |
| Phlox | 826 | FaaS 高层运行时 |

**总 TCB**：89,271 SLOC（vs. Linux 容器栈 2,699,812 SLOC）。

关键实现优化：

- **回调机制**：L4Re 线程只有一个隐式 reply capability，服务线程一次只能服务一个客户端。通过 callback IPC gate 模式避免为每个请求创建新线程。
- **资源池与延迟回收**：避免在关键路径上执行 capability revocation（因 RCU 实现会阻塞一个调度 tick ~10ms），改用线程池和后台删除线程。
- **Capability 数据结构锁优化**：移除 map 操作中源 task 的锁（因 capability 本身已在内核中被锁定），提升并行 delegation 性能。
- **跨核 IPC 优化**：让 moe 在多核上运行，避免跨核同步 IPC（通过 IPI 实现）的开销。

Python 3 被移植到 L4Re，使用自研交叉编译器从标准 Linux 源码包生成 L4Re 可执行文件。

---

## 五、实验结果

**实验平台**：双路 Intel Xeon Platinum 8358（32 核/CPU），500 GiB 内存，10 Gbit Intel 82599/X540 NIC。关闭 SMT 和 Turbo Boost。

**对比基线**：Linux 进程（性能上界）、runC（Linux 容器标准实现）、Kata Containers + Firecracker（轻量级 VM）。

### 容器启动延迟

| 场景 | Linux 进程 | runC | Kata+FC | L4Re |
|------|-----------|------|---------|------|
| N=1（空系统冷启动） | ~200 µs | ~70 ms | ~1 s | ~1 ms |
| N=64（并行启动） | ~200 µs | ~200 ms | ~1 s | ~100 ms |

L4Re 单容器启动比 runC 快 70×，但并行启动时因内核粗粒度锁和 moe 单锁瓶颈导致延迟上升。空闲容器数量对启动延迟无显著影响。

### 网络 I/O

- UDP ping-pong 延迟：所有平台约 40 µs。
- 带宽（10 Gbit NIC）：低并行度时 Linux 900 MiB/s vs. L4Re 350 MiB/s（L4Re 未实现 RSS，驱动单核处理）；高并行度时 L4Re 达到线速，Linux 反而下降。

### 应用基准测试（SeBS FaaS）

| 基准 | L4Re vs. runC（端到端） |
|------|----------------------|
| Empty function | 相近 |
| HTML manipulation | L4Re 快 10% |
| ZIP 压缩 | L4Re 较慢（文件系统开销） |
| 图算法 (Rank/Tree/Search) | L4Re 慢 ≤15% |

L4Re 的文件系统操作（stat ~4 µs vs. Linux ~460 ns，约 10× 差距）是主要性能瓶颈，导致 Python 启动和模块加载较慢，但快速的容器启动部分弥补了这一不足。

### CVE 安全分析（33 个 Linux 容器相关高危 CVE）

| 类别 | 完全缓解 (FM) | 部分缓解 (PM) | 未缓解 (N) |
|------|-------------|-------------|-----------|
| seccomp-bpf (8) | 8 | 0 | 0 |
| namespaces (22) | 4 | 13 | 5 |
| cgroups (3) | 0 | 3 | 0 |

---

## 六、批判性分析

1. **TCB 对比不公平**：Linux 侧的 containerd（922K SLOC）和 runC（290K SLOC）是功能完整的生产系统，而 MettEagle 是研究原型，缺少 OCI 镜像支持、overlay FS、warm start 等核心功能。作者承认了这一点但仍将数字放在一起对比，容易产生误导。

2. **CVE 分析方法论的局限**：论文对 33 个 CVE 的"完全/部分/未缓解"分类高度依赖主观判断。对于"部分缓解"类别（如 namespace 相关的 13 个），攻击虽不能直接入侵内核，但仍可能妥协用户态服务组件——而这些组件在微内核架构中承担了原本内核的功能，其安全影响可能被低估。

3. **文件系统性能差距被轻描淡写**：stat 操作 10× 的差距、大量 Python 场景下的性能瓶颈被归因为"实现问题而非架构问题"，但论文未给出具体的优化方案和预期改进幅度。提到的 persistent memory 式共享内存方案仅为设想。

4. **并行启动可扩展性问题**：N=64 时 L4Re 启动延迟从 1ms 涨到 100ms（100×），暴露了内核和 moe 的锁竞争问题。论文指出了原因但解决方案（更细粒度的锁）并未实现和验证。

5. **fork 不支持是重大功能缺失**：L4Re 不支持 fork 系统调用，这不仅导致 FFMPEG 基准被跳过，更意味着大量依赖 fork 的真实应用（如 web 服务器、数据库）无法直接在 MettEagle 上运行。论文对此一笔带过。

6. **timing side-channel 讨论空泛**：Section 5.3 讨论了时序侧信道，但只给出定性论证（"L4Re 内核实时、共享数据结构少"），没有任何量化评估或实验验证。

---

## 七、总结

MettEagle 展示了在 L4Re 微内核上实现容器级隔离的可行性和潜在优势。其核心贡献在于证明了 capability-based 微内核的固有隔离属性可以替代 Linux 容器的三大安全机制（seccomp-bpf、namespaces、cgroups），从而大幅缩小 TCB（89K vs. 2.7M SLOC）并缓解大量历史 CVE。性能方面，单容器启动延迟比 runC 快 70×，端到端 FaaS 性能在多数场景下与 Linux 容器竞争力相当。主要局限在于文件系统性能差距（10×）、并行可扩展性瓶颈、缺少 fork 支持和 OCI 兼容性，这些使其离生产部署仍有显著距离。论文为微内核在云基础设施中的应用提供了有价值的探索，但从研究原型到实际替代 Linux 容器栈，还需要大量工程和性能优化工作。
