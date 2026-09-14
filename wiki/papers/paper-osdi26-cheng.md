---
type: paper
name: MPK
full_title: "MPK: A Compiler and Runtime for Mega-Kernelizing Tensor Programs"
authors: [Xinhao Cheng, Zhihao Zhang, Yu Zhou, Jianan Ji, Jinchen Jiang, et al.]
venue: OSDI
year: 2026
tags: [llm-inference, mega-kernel, gpu-runtime, compiler, multi-gpu]
source_pdf: "[[osdi26-cheng.pdf]]"
source_md: "[[osdi26-cheng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-09-14
---

# MPK：把张量程序编译成持久化大内核（OSDI 2026）

> **原题**：MPK: A Compiler and Runtime for Mega-Kernelizing Tensor Programs

> **一句话总结**：传统 kernel-per-operator 执行在算子边界引入启动和同步气泡；MPK 用 SM 粒度的 tGraph 和内核内调度器把整个推理过程融合成一次 mega-kernel，在五个模型、A100/H100/B200 上相对 vLLM/SGLang 获得 1.0–1.7× 吞吐提升，并将 Qwen3-8B 的单 token kernel 启动开销从约 0.2–1.1 ms 消除。

## 问题与动机

LLM 推理通常把每个张量算子交给独立 GPU kernel。即使使用 CUDA Graphs，这种模型仍在 kernel 之间形成全局屏障：依赖算子只能在前一个算子完全结束后启动，计算和通信难以细粒度重叠，数百个 kernel 的启动也会增加每 token 延迟。CUDA Graphs 还偏静态，动态 batch、控制流和依赖变化会削弱其收益。

MPK 试图自动化手写 persistent kernel 的工作。输入仍是 PyTorch 张量程序，但编译器将算子拆成 SM 级任务，运行时在一个持久化 kernel 中调度计算与通信。目标是保留 PyTorch 编程接口，同时获得跨算子流水、通信重叠和较低调度开销。

## 关键观察 / 隐含假设

- **观察 1**：MatMul 后的 AllReduce 中，每个通信 tile 只依赖部分 MatMul 输出；算子级屏障因此过早同步。图 3、§3 展示了这种依赖关系。
  - **依赖假设**：任务能够按输出 tile 正确切分，且设备内存中的事件同步成本低于隐藏通信延迟带来的收益。
  - **可能失效场景**：算子依赖高度稠密、任务过小，或跨节点网络延迟和抖动主导执行时，事件和调度开销可能抵消重叠收益。
- **观察 2**：推理包含动态 batch 和数据相关执行时间，尤其是 attention 与 MoE 路由。静态任务分配会造成 SM 负载不均（§5.2、§6.4）。
  - **应对假设**：用 JIT 调度处理不均衡算子，用 AOT 预排队稳定算子，且编译时生成的代表性 batch-size tGraph 足以覆盖实际负载。
- **假设 3**：目标模型具有足够“深”的算子链。论文观察到归一化在评测模型中几乎不增加开销，因为融合后的图很少出现宽的 fork/join（§6.7）。这一结论对分支密集或控制流更动态的 DNN 仍属中等强度证据。

## 核心方法

MPK 的中间表示 tGraph 在 SM 粒度表达任务和事件。任务执行计算或通信，事件等待所有前驱完成后触发后继任务。生产者和消费者按张量区域的重叠关系建立事件，从而保留 tile 级依赖；这比 CUDA Graphs 的 kernel 级依赖暴露更多并行性。

编译器先分解算子，再做 successor-set / predecessor-set event fusion。随后用 tGraph normalization 把每个任务的事件 fan-in/fan-out 限制为至多一个，并用线性化把同一事件触发的任务放入连续索引区间。这样任务只需保存固定大小的事件 ID，事件只需保存首尾索引，减少设备端间接访问。

每个任务的实现由 Mirage superoptimizer 在 thread-block 粒度搜索并生成 CUDA device function，支持软件流水、寄存器复用和 shared-memory layout 优化。运行时把部分 SM 分配给 scheduler，其余分配给 worker；scheduler 传播事件，worker 执行任务，整个模型只启动一次 mega-kernel。

MPK 还引入分页 shared memory，使后续任务能在前一任务计算期间预取数据。JIT 适用于 attention 等执行时间不确定的算子，AOT 适用于稳定算子；二者由编译器按算子分类。MoE 中，路由、all-to-all、expert GEMM 和 combine 都统一成任务，并用运行时 token 元数据做混合负载均衡。

## 设计取舍

- **调度开销与负载均衡**：JIT 能适应长短序列，却需要 worker-scheduler 通信；AOT 更快，却依赖静态负载近似。混合策略用全局 barrier 作为重新平衡边界。
- **通用性与特化**：tGraph 按 batch size、GPU 架构生成，换形状或硬件需要额外编译；作为交换，任务切分和内存流水能针对目标设备优化。
- **资源峰值**：寄存器按所有任务类型的最大需求固定，可能压低 occupancy；shared memory 改为分页动态分配，但其单调释放约束限制了任务实现。
- **工程复杂度**：实现约 44K 行 C++、42K 行 CUDA 和 10K 行 Python，并依赖 NVSHMEM。论文未量化编译时间、调试成本和故障恢复行为。

## 实验与结果

- 在 Qwen3-0.6B、Llama-3.2-1B-Instruct、Qwen3-1.7B、Qwen3-8B 和 Qwen3-30B-A3B 上，A100、H100、B200 单 batch 推理相对 vLLM/SGLang 提升 1.0–1.7×（图 9）。Qwen3-8B/A100 的 per-token latency 从 14.5 ms 降至 12.5 ms，论文估计硬件下界约 10 ms。
- 8 张 H100 tensor parallel 下，MPK 相对 vLLM/SGLang 提升 1.1–1.4×，相对 PyTorch 最多提升 10×（图 11）。
- Qwen3-8B 每 token 的 kernel 数为 293；B200 上 eager 启动开销约 1.1 ms，CUDA Graphs 约 0.2 ms。MPK runtime scheduler 仅占总运行时间 0.28%（§6.6）。
- 跨任务流水使 Qwen3-8B 最后一层线性层加速 1.2–1.3×（图 12）；细粒度计算—通信重叠使四张 H100 上的 Qwen3-1.7B 每轮延迟降低约 1.1×（图 13）。
- event fusion 将 69,000–162,000 个生产者—消费者依赖压缩为 1,142–2,366 个事件；线性化使 Qwen3-8B 编码从 110,932 bytes 降至 18,928 bytes，即 5.9× 缩减（表 2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 单 batch serving 可明显降低延迟 | 图 9；1.0–1.7× 相对提升 | 五个 LLM，A100/H100/B200，batch 1–16 | 强 |
| SM 级依赖能带来计算—通信重叠 | §6.6、图 13；约 1.1× | Qwen3-1.7B，4× H100，tensor parallel | 中 |
| 单次 kernel launch 能消除启动成本 | §6.6；293 次 launch、0.28% scheduler 开销 | Qwen3-8B，B200 | 强 |
| 编译式 mega-kernel 能处理动态 serving | §6.4、图 9 | 离线 batch，固定 64-token prompt 和 1024-token 输出 | 中 |

## 批判性分析

### 论证链条

论文的主要链条是闭合的：算子级屏障限制流水和重叠，tGraph 暴露 tile 依赖，内核内调度执行这些依赖，消融实验分别测到流水、重叠和启动削减收益。较大的端到端提升集中在小模型和新 GPU；这说明 MPK 主要收回固定开销，不代表所有计算密集型模型都能获得同等收益。

### 假设压力测试

评测采用离线 batched inference、固定 prompt 和输出长度，避免了在线到达间隔、取消、抢占和 SLO 约束。论文支持连续 batching，但没有给出真实 request trace 下的 P99 或 admission 控制结果。batch-size powers-of-two 的多 tGraph 方案也可能在形状组合更多时增加编译和缓存管理成本。跨节点通信只在概念上讨论，实验证据集中在 DGX 内部 H100。

### 实验可信度

基线包含经过高度优化的 vLLM 和 SGLang，且使用相同精度、paged attention 和 continuous batching，比较具有参考价值。实验覆盖三代 GPU、dense/MoE 和单/多 GPU；但主要指标是吞吐或平均 per-token 延迟，缺少在线 P99、显存占用、编译时间、能耗、恢复时间以及更多网络拓扑的测量。因此“接近硬件极限”的结论应限于给定模型和离线工作负载。

### 系统性缺陷

一个 mega-kernel 把模型执行、请求管理和通信耦合到同一设备内运行时，可能增加错误定位、升级单个算子和故障恢复的难度。论文未讨论单个通信任务失败、GPU hang、任务超时、租户隔离或动态模型加载。scheduler 固定占用四个 SM，在小模型或极小 batch 上的资源机会成本也需要独立测量。

## 局限与后续工作

- **局限 1**：动态性通过预编译多个代表性 batch-size tGraph 处理，而非任意形状的完全动态编译。
- **局限 2**：评测主要是离线推理，未覆盖在线服务的到达过程、P99、请求取消和多租户隔离。
- **后续工作 1**：在公开在线 trace 上比较 MPK、vLLM 和 SGLang 的 P50/P95/P99、编译缓存命中率及单位 token 能耗。
- **后续工作 2**：在跨节点 RDMA 拓扑上测量事件粒度、网络抖动和错误恢复对 mega-kernel 的影响。
- **后续工作 3**：研究 scheduler SM 数量、寄存器上限和任务粒度的自动调优，验证其对小模型与分支密集模型的适用性。

## 相关

- **相关概念**：[[CUDA Graphs]]、[[PagedAttention]]、[[Continuous Batching]]、[[Persistent Kernel]]
- **同类系统**：[[vLLM]]、[[SGLang]]、[[Mirage]]、[[TileRT]]
- **同会议**：[[OSDI-2026]]
- **相关论文**：[[NanoFlow-OSDI25]]、[[Mirage-OSDI25]]
