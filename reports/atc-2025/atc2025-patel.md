# XRT: An Accelerator-Aware Runtime for Accelerated Chip Multiprocessors

**作者**：Neel Patel, Mohammad Alian (Cornell University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/patel
**源文件**：[[atc2025-patel.pdf]]

---

## 一、背景

数据中心应用在执行通用函数（如压缩/解压、加解密、数据搬移、数据库查询等）上消耗了大量 CPU 周期。为提升性能和能效，现代服务器处理器（如 Intel Xeon 4/5 代）开始在片上集成多种专用加速器——Intel DSA（数据搬移）、IAA（分析/压缩）、QAT（加密/压缩）、DLB（核间通信）。这类集成了加速器的片上多处理器被称为 Accelerated Chip Multi-Processors（XMPs）。

XMPs 通过共享虚拟内存（SVM）、设备侧 TLB 和共享工作队列等硬件机制，实现了核与加速器之间的低开销通信和多租户共享。然而，现有的 CMP 运行时系统（如 Concord、Shinjuku、TinyQuanta 等）在设计时假设所有请求处理都在通用核上完成，完全未考虑加速器的存在，导致在 XMP 上无法有效利用加速器资源。

---

## 二、要解决的问题

现有 CMP 运行时在 XMP 上面临三个核心问题：

1. **Dispatcher-Centric 架构的扩展性瓶颈**：集中式 dispatcher 同时负责负载均衡和处理加速器完成通知，在多核多加速器场景下迅速成为瓶颈。实验显示，Dispatcher-Centric 在 DDH 工作负载上仅能维持约 1.0 MRPS 的吞吐量，而 Worker-Centric 可达约 2.5 MRPS。

2. **不必要的上下文切换开销（Unnecessary Resumption）**：Worker-Centric 运行时（如 TinyQuanta）的调度器在 yield 后以 round-robin 方式恢复线程，但无法感知 offload 是否已完成。线程被恢复后发现 offload 仍在进行中，只能再次 yield，造成大量无效上下文切换。DDH 工作负载中每个请求平均经历 21 次不必要的恢复，占请求端到端执行时间的 13%。

3. **加速器争用导致核心阻塞（Stalls on Contended Accelerators）**：在 Yield 模式下，大量线程并发提交 offload，加速器工作队列满后，核心在 offload 提交处阻塞等待。高负载下，Yield 模式的请求执行时间甚至超过不使用加速器的 NoAcceleration 模式——即"用了加速器反而更慢"。

---

## 三、洞察与设计

**关键洞察**：加速器按 FIFO 顺序处理 offload 请求，因此调度器只需轮询下一个预期完成的 offload 的 completion record（而非遍历所有线程），即可用极低开销（2-3 个周期的 L1 cache 访问）判断 offload 是否完成，从而消除不必要的上下文切换。

基于此洞察，XRT 采用 Worker-Centric 两级调度架构，包含两个核心机制：

### Notification-Aware Scheduler

每个 worker 核心维护两个 ring buffer：
- **Monitoring Set**：缓存大小的 completion record 数组，加速器完成 offload 后写入对应的 completion record
- **Thread Contexts**：指向 worker 线程上下文的指针数组，与 completion record 保持逻辑映射

调度器利用加速器的 FIFO 处理特性，只需检查下一个预期完成的 completion record 即可判断是否有线程可恢复。这将判断开销从 ~30 周期（无效上下文切换）降至 2-3 周期（L1 cache 读取）。

### Software Fallback

当加速器工作队列已满时（ENQCMD 指令返回 "retry"），XRT 不再重试或阻塞，而是直接回退到 CPU 上执行该函数的软件实现。这避免了核心在满载加速器上的阻塞等待，确保系统吞吐量不低于不使用加速器的基线。

---

## 四、实现细节

- **调度策略**：Dispatcher 使用 Join-the-Shortest-Queue（JSQ）负载均衡，基于优先队列和计数器追踪每个 worker 的排队请求数。每个 worker 维护浅队列（4 个线程 + 1 个调度线程），使用 Boost coroutine 实现用户态线程。
- **Offload 接口**：使用 Intel ENQCMD 指令将 offload descriptor 写入加速器的 memory-mapped register，指令原子地返回成功/失败状态。offload descriptor 中指定 completion record 的地址，加速器完成后写入该地址。
- **加速器配置**：使用 idxd-config 库配置共享工作队列（shared work queues），启用 PASID 和 SVM，支持多核并发提交 offload。
- **请求生命周期**：Dispatcher 接收请求 → JSQ 分配到最短队列的 worker → 调度器分配线程执行 Pre-Processing → 尝试 offload Accelerable Function（失败则 software fallback）→ 成功则 yield 核心 → 调度器周期性轮询 monitoring set → 检测完成后恢复线程执行 Post-Processing。
- **硬件平台**：Intel Xeon 8571N（5th Gen），双 NUMA 节点，26 个 worker 核 + 1 个 dispatcher 核，配置 4× IAA + 4× DSA 加速器（实验使用单 NUMA 节点上的 2× IAA + 2× DSA）。

---

## 五、实验结果

实验在 6 个代表性工作负载上比较 4 种运行时配置：NoAcceleration、Block&Wait、RR-Worker（naive Worker-Centric）、XRT。指标为 99.9th percentile slowdown（请求延迟 / Block&Wait 无负载执行时间）。

| 工作负载 | 特征 | XRT vs RR-Worker | XRT vs NoAcceleration | 关键发现 |
|----------|------|-------------------|----------------------|----------|
| DDH | 反序列化+解压+哈希 | 显著提升 | 大幅提升（解压为瓶颈） | XRT 消除了不必要恢复开销 |
| DC | 解压+指针追踪 | 显著提升 | 大幅提升 | 计算密集型解压受益最大 |
| DMD | 解密+memcpy+点积 | 3.2× 吞吐量提升 | 大幅提升 | 加速器争用严重，RR-Worker 比 NoAcceleration 慢 188% |
| MC | memcpy+指针追踪 | 显著提升 | 提升 | RR-Worker 比 NoAcceleration 慢 14%，XRT 通过 fallback 避免 |
| MMP | 矩阵乘+memfill+PCA | 基本持平 | 持平 | Pre-Processing 占 99.6% 时间，加速器优化影响微小 |
| UFH | 更新+过滤+直方图 | 基本持平 | 持平 | 核心计算为主，加速器部分占比小 |

核心结论：
- XRT 在所有工作负载上**从不比 NoAcceleration 差**（software fallback 保底）
- 在加速器受益显著的工作负载上，XRT 实现**最高 3.2× 的 SLO 吞吐量提升**
- RR-Worker 和 Block&Wait 在加速器争用场景下可能**比不用加速器更差**

---

## 六、批判性分析

1. **工作负载的代表性存疑**：6 个工作负载均为合成 benchmark，使用指数分布的服务时间和固定的三阶段执行模型。真实数据中心工作负载的请求处理通常更复杂（多次 offload、动态分支、可变阶段数），论文未评估 XRT 在更复杂请求处理流程下的表现。

2. **加速器数量和类型受限**：实验仅使用单 NUMA 节点上的 2 个同类型加速器。论文标题和摘要强调"many-accelerator"，但未展示 4 个以上加速器同时使用、多种加速器混合调度的场景。XRT 的 software fallback 策略在多种加速器竞争资源时是否仍然有效未经验证。

3. **Software fallback 的决策过于简单**：当前策略是 ENQCMD 失败就立即回退到 CPU 执行。但这忽略了一种常见场景：加速器队列即将空出一个位置，短暂等待（几十纳秒）可能比在 CPU 上执行一个长函数更优。论文没有探讨 adaptive 的 fallback 策略。

4. **与 NoAcceleration 持平的场景比例偏高**：6 个工作负载中有 2 个（MMP、UFH）XRT 几乎没有收益，说明 XRT 的价值高度依赖于 Accelerable Function 在请求中的时间占比。论文未给出指导性阈值——什么条件下值得引入 XRT 的复杂性。

5. **单地址空间的部署限制**：XRT 是单地址空间用户态运行时，不支持多租户隔离，这在公有云场景下是硬伤。论文仅一句话提到可用用户态进程抽象解决，但未评估隔离带来的性能开销。

6. **仅评估 Intel 平台**：尽管讨论了 ARM（ST64BV）和 RISC-V（Atomic IO Enqueue）的类似原语，实际实验仅在 Intel Xeon 上进行。跨平台的可移植性缺乏实证支持。

---

## 七、AI Infra / MLSys 视角

1. **异构调度的借鉴价值**：XRT 的核心问题——如何在通用核和专用加速器之间高效调度——与 AI 推理系统中的 CPU-GPU 协同调度高度类似。Notification-aware scheduler 的思路可迁移到 GPU 推理场景中，例如在 prefill 和 decode 阶段之间智能切换，或在多 GPU 卡之间感知 kernel 完成状态进行调度。

2. **Software fallback 思路对 AI serving 的启发**：在 LLM serving 中，当 GPU 显存不足或 batch 队列已满时，类似的 fallback 机制（如将部分计算回退到 CPU、或降级到更小模型）可以保证系统在高负载下不发生 throughput collapse。当前 vLLM/SGLang 等系统在 GPU 资源满载时主要采用排队等待策略，引入 adaptive fallback 可能是一个有价值的方向。

3. **Completion notification 机制**：XRT 利用硬件 completion record 实现的低开销 offload 状态追踪，在 AI 系统中对应的是 CUDA event/stream synchronization。当前 AI 框架中 kernel 完成检测的开销和粒度仍有优化空间，XRT 的 ring buffer + FIFO polling 模式值得参考。

4. **可跟进的研究方向**：
   - 将 XRT 的调度思路扩展到 AI 加速器（如 NPU、TPU）的片上异构调度
   - 在 AI 推理 serving 系统中实现 accelerator-aware 的请求调度，感知 GPU kernel 完成状态来减少空闲等待
   - 探索 CPU 上的 AI 相关加速器（如 Intel AMX）与 XRT 的集成

---

## 八、总结

XRT 是首个面向 Accelerated Chip Multi-Processors（XMPs）的运行时系统，通过 notification-aware scheduler 消除不必要的上下文切换、通过 software fallback 避免加速器争用导致的核心阻塞，在代表性工作负载上实现最高 3.2× 的 SLO 吞吐量提升，且保证在任何场景下不比不使用加速器差。其适用于私有云中单租户的微秒级延迟服务场景，主要局限在于工作负载模型较简单、仅验证了 Intel 平台、以及缺乏多租户隔离支持。
