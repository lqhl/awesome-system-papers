# The Benefits and Limitations of User Interrupts for Preemptive Userspace Scheduling

**作者**：Linsong Guo, Danial Zuberi, Tal Garfinkel, Amy Ousterhout (UC San Diego)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/guo
**源文件**：[[nsdi2025-guo.pdf]]

---

## 一、背景

数据中心应用普遍受到高尾延迟的困扰。Google 的一项研究表明，90% 的 RPC 方法可以在数百微秒内完成，但中位延迟却在毫秒级别。造成这一问题的关键因素之一是请求在服务器端的排队——当请求具有异构的服务时间时，短请求可能被长请求阻塞（head-of-line blocking）。

抢占式调度（preemptive scheduling）是减少 head-of-line blocking 的经典方案：调度器周期性中断正在运行的任务，让更紧急的短任务有机会尽快执行。然而，当前的用户态调度器很少实现抢占。大多数高性能数据中心系统和语言运行时采用协作式并发（cooperative concurrency），或者仅在极粗粒度（如 Go 的 10ms）进行抢占。根本原因在于：现有抢占机制（信号和编译器插桩）的开销高且不可预测。

Intel 最新的 Sapphire Rapids CPU 引入了 user interrupts（用户中断）——一种全新的硬件特性，允许在用户态直接发送和接收处理器间中断（IPI），无需内核参与，为低开销的细粒度抢占提供了新的可能。

---

## 二、要解决的问题

现有用户态抢占机制存在明显不足：

1. **信号（Signals）开销高**：每次抢占需要在发送端和接收端各经历多次用户态-内核态切换，单次信号处理开销约 2.4µs，限制了抢占频率。以 10µs 的抢占量子（quantum）为例，程序减速约 25% 以上。
2. **编译器插桩（Compiler Instrumentation）开销不可预测**：编译器在函数入口和循环回边插入检查代码，开销严重依赖程序控制流。紧循环（tight loop）场景下开销可能极高（如 matrix_multiply 高达 25%），且参数调优（subloops、loop unrolling 深度等）需要大量手工工作，轻微变动即可导致开销剧变。
3. **两者都难以支持亚毫秒级尾延迟保证**：信号在 30µs 以下量子时开销不可接受；编译器插桩虽然某些场景下低开销，但 fragile、不可移植、难以泛化。

核心问题：**能否利用 user interrupts 实现低开销、可预测的细粒度用户态抢占调度？**

---

## 三、洞察与设计

**关键洞察**：User interrupts 通过硬件快速路径在用户态直接发送和接收 IPI，彻底绕过了信号机制中多次内核态切换的开销（从 2.4µs 降至 0.4µs），同时不像编译器插桩那样对程序控制流敏感——中断仅在实际抢占时产生开销，而非持续轮询。这意味着 user interrupts 能在大多数场景下同时兼顾低开销和可预测性。

基于这一洞察，作者构建了两个抢占式用户态调度器：

### Aspen-KB：Kernel-Bypass 抢占调度器

- 扩展 Caladan 运行时，采用 kernel-bypass 网络栈
- 专用 timer core 周期性发送 user interrupts 到 runtime core
- **避免不必要抢占**：timer core 通过共享内存查看各 core 的 RX 队列和调度器状态，仅在有待处理任务且当前线程已运行超过 quantum 时才发送中断
- **两队列调度（two-queue）**：新任务进 new queue（高优先级），被抢占的任务进 preempted queue（低优先级，更长 quantum），无需先验任务类型信息即可减少 head-of-line blocking
- **频繁轮询网络**：每次抢占后轮询 RX 队列，减少网络栈中的排队延迟

### Aspen-Go：Go 运行时抢占调度器

- 扩展 Go 1.21 运行时，将 sysmon 线程改为使用 user interrupts
- sysmon 改为 busy-spin 以支持精确的细粒度抢占
- 将 sysmon 的网络轮询频率从 10ms 提升至 100µs
- 在 Lock()/Unlock() 处禁用/启用抢占以保护临界区
- 修改量 733 LOC

---

## 四、实现细节

**User Interrupts 机制**：发送端和接收端先向内核注册，之后 IPI 的发送和接收完全在用户态完成。处理器直接查询内核管理的路由表将中断送达特定接收线程。单次 user interrupt 开销仅 0.4µs（vs. 信号 2.4µs）。

**非抢占代码处理**：调度器代码持锁、malloc/free、TLS 访问等区域不可安全抢占。硬件提供 `clui`/`stui` 指令延迟中断交付，但每对指令约 18ns，频繁调用开销不可忽略（如 RocksDB GET 中 malloc 调用频率 4 calls/µs）。因此 Aspen-KB 采用软件方式（preempt_disable/enable），仅增加 1-2ns 每次。

**扩展寄存器保存**：User interrupts 硬件仅保存 flags、IP、SP；调度器需保存所有 SIMD/AVX-512 寄存器（每线程额外 2KB）。实测大多数情况下开销可忽略（<40ns/次），仅当线程集体访问的内存恰好刚好填满某层 cache 时，worst case 可达 700ns。

**Aspen-KB 实现**：基于 Caladan 扩展，1849 LOC。同时实现了信号和 Concord 编译器插桩变体，支持 apples-to-apples 对比。

**Aspen-Go 实现**：修改 Go 运行时 733 LOC。受限于 Go 运行时设计（依赖 OS 网络栈、全局队列优先级低于本地队列），无法完全消除 head-of-line blocking。

---

## 五、实验结果

**实验平台**：双路 Intel Xeon Gold 5420+（Sapphire Rapids, 28 cores, 2.0GHz），256GB RAM，100Gbps Mellanox ConnectX-6 Dx NIC，Ubuntu 22.04，自定义 Intel 内核（6.0.0 + user interrupts 支持）。

### Aspen-KB 结果

| 应用 | 工作负载 | User Interrupts 收益 | 最佳 quantum |
|------|---------|---------------------|-------------|
| RocksDB | 95% GET + 5% SCAN | GET 吞吐量比非抢占提升 **58.2%**（tail latency ≤ 50µs 约束下） | 5µs |
| DataFrame | 5 种异构任务 | 短任务吞吐量比非抢占提升 **30%**，比 fine-tuned Concord 高 **9%** | 20µs |

### Aspen-Go 结果

| 应用 | User Interrupts 收益 |
|------|---------------------|
| BadgerDB (99% GET + 1% RangeSCAN) | GET 吞吐量比 unmodified Go 提升 **17.5%**（tail latency ≤ 1000µs） |

### 单次抢占开销对比

| 机制 | 单次开销 |
|------|---------|
| Signals | ~2.4µs |
| User Interrupts | ~0.4µs |
| Compiler Instrumentation | 低但不可预测（0~25%+ 取决于程序） |

### Timer Core 可扩展性（5µs quantum）

| 机制 | 单个 timer core 支持的 application cores |
|------|----------------------------------------|
| Signals | 2 |
| User Interrupts | 22 |
| Compiler Instrumentation | 24 |

### 基准程序减速（24 个程序，5µs quantum）

- User Interrupts：6.1%–9.3%，**一致且可预测**
- Signals：43%–66%
- Compiler Instrumentation：-1.7%–25.8%，**高度不可预测**

---

## 六、批判性分析

1. **User interrupts 并非万能药——论文标题已暗示但实际 Aspen-Go 的收益相当有限**。Go 场景下 user interrupts 仅带来 17.5% 的 GET 吞吐提升，且 compiler instrumentation 反而比 user interrupts 高 6%。论文在标题中用"Benefits and Limitations"来对冲，但摘要和引言仍给人"user interrupts 是更好选择"的印象，容易误导读者忽视 Go 这类场景的局限性。

2. **实验硬件的可获得性是重大问题**。User interrupts 仅在 Intel Sapphire Rapids 及后续 CPU 上可用，且需要 Intel 提供的定制 Linux 内核（基于 6.0.0）。论文未讨论该特性何时会进入主线内核、AMD 是否有对应方案、以及云环境中的可用性。这严重限制了结果的实际可复现性和可部署性。

3. **Aspen-KB 与现有系统的对比不够公平**。论文坦承无法直接对比 Shinjuku 和 Concord（内核版本不兼容、负载均衡策略不同），而是在 Aspen-KB 上重新实现了各种抢占机制。但 Aspen-KB 的设计决策（two-queue policy、skip unnecessary preemptions）针对 user interrupts 优化，这些策略叠加在一起使得"抢占机制本身的差异"难以干净地分离。

4. **Two-queue 调度的收益与抢占机制混淆**。Figure 10 显示 two-queue policy 对性能有巨大影响，但这是一个调度策略层面的贡献，与 user interrupts 硬件特性无关。论文将两者打包在一起展示，使得 user interrupts 的独立贡献被高估。

5. **编译器插桩的"难以调优"被夸大**。论文反复强调 Concord 的 subloops 参数难调，但 Concord fine-tuned 在多个场景下表现与 user interrupts 相当甚至更好。如果配合 autotuning 工具，编译器插桩的可用性可能并不像论文描述的那么差。

6. **BadgerDB 实验中未充分讨论 Go 运行时的结构性限制**。Aspen-Go 受限于 Go 的全局队列设计、OS 网络栈依赖等，但论文仅将其作为"Go 不适合细粒度抢占"的证据，未深入探讨是否可以通过更激进的运行时修改（如 Junction 已展示的 kernel-bypass Go）来释放 user interrupts 的潜力。

---

## 七、AI Infra / MLSys 视角

1. **推理服务的请求调度**：LLM 推理服务（如 vLLM）面临类似的异构请求问题——prefill 请求计算密集，decode 请求延迟敏感。User interrupts 提供的低开销抢占机制可以用于在 CPU 端实现更精细的请求调度和上下文切换，特别是在 CPU-bound 的 tokenization、KV cache 管理等环节。

2. **分布式训练中的通信调度**：AllReduce 等集合通信操作中，计算与通信的重叠（overlap）需要精确的抢占时机。User interrupts 的 0.4µs 级开销可能使得在用户态实现更激进的 compute-communication interleaving 成为可能，替代目前基于 CUDA stream/event 的粗粒度方案。

3. **Two-queue 策略对 serving 系统的启发**：Aspen-KB 的 new queue / preempted queue 分离思路可以直接应用于推理 serving——新到达的请求（特别是首 token 请求）优先于被抢占的续生成请求，无需预知请求长度即可降低首 token 延迟（TTFT）。

4. **值得跟进的方向**：
   - 将 user interrupts 引入 GPU 驱动的用户态调度（如 GPU kernel preemption 的 CPU 侧决策路径）
   - 在 RDMA/kernel-bypass 推理服务中集成 Aspen-KB 风格的抢占调度
   - 探索 xUI（Extended User Interrupts）对 AI workload 的进一步加速潜力

---

## 八、总结

本文系统性地研究了 Intel user interrupts 在用户态抢占调度中的收益与局限。在 kernel-bypass 场景（Aspen-KB）中，user interrupts 以 0.4µs 的单次开销显著优于信号（2.4µs），在大多数 quantum ≥ 10µs 的场景下也优于或持平编译器插桩，同时提供更一致、可预测的性能和更简单的使用体验。然而，在 Go 运行时这类非针对细粒度抢占设计的系统中，user interrupts 的收益有限。论文的核心贡献在于提供了三种抢占机制的深入量化对比，并展示了 two-queue 调度等实用的系统设计技巧。主要局限是对 Intel 特定硬件的依赖以及定制内核的部署门槛。
