---
type: paper
name: MPK
full_title: "MPK: A Compiler and Runtime for Mega-Kernelizing Tensor Programs"
authors: [Xinhao Cheng, Zhihao Zhang, Yu Zhou, Jianan Ji, Jinchen Jiang, et al.]
venue: OSDI
year: 2026
tags: [gpu, compiler, mega-kernel, llm-inference, tensor-program]
source_pdf: "[[osdi26-cheng.pdf]]"
source_md: "[[osdi26-cheng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Tensor Program 的自动 Mega-Kernel 编译与运行时（OSDI 2026）

> **原题**：MPK: A Compiler and Runtime for Mega-Kernelizing Tensor Programs

> **一句话总结**：MPK 把 multi-GPU tensor program 降为 SM-level task graph，并由单个 persistent mega-kernel 内的去中心化 runtime 调度，使跨 operator pipeline 与细粒度 compute–communication overlap 成为可能；五个模型、A100/H100/B200 上相对 vLLM/SGLang 将单 batch latency 改善 1.0–1.7×，8×H100 上吞吐改善 1.1–1.4×。

## 问题与动机

主流 ML system 对每个 tensor operator 启动独立 GPU kernel。kernel boundary 提供简单的全 GPU dependency barrier，却阻止下游 operator 在上游部分 SM 完成后提前运行，也只能在完整 MatMul 结束后启动 collective。每 token 数百次 launch 还带来 CPU dispatch 开销，而 CUDA Graph 对 shape/control-flow 变化不灵活。

手写 persistent mega-kernel 可消除 launch，并进行跨 operator software pipeline，但需要统一 CUDA/Triton、[[Flash-Attention|FlashAttention]]、[[NCCL|NCCL]]/NVSHMEM 等分散组件，手工安排 SM 与同步，难以扩展到完整 multi-GPU model。MPK 的目标是从 PyTorch tensor program 自动生成一个高性能 mega-kernel，同时仍支持 [[Continuous-Batching|dynamic batching]] 和 MoE routing。

## 关键观察 / 隐含假设

- **观察 1**：operator-level DAG 的 dependency 过粗；一个 output fragment 往往只依赖上游部分 SM task，SM-level edge 能提前释放 parallelism（§2–3、图 2/5）。
  - **依赖假设**：operator 可被稳定 partition 成 SM task，读写 region 可静态推导，跨 task synchronization 成本小于 overlap 收益。
  - **可能失效场景**：极小 operator、强全局 reduction、irregular memory dependency 或 task 太短导致 runtime overhead 主导。
- **观察 2**：persistent kernel 可避免 kernel switching/CPU launch，并让 compute 与 communication 同处一个调度域（§1、§6.5–6.6）。
  - **依赖假设**：模型执行期间可长期占有足够 SM，且不会破坏 GPU multi-tenancy/preemption 与其他 stream 的公平性。
  - **可能失效场景**：多 tenant 共享 GPU、频繁 high-priority kernel、MIG 或外部 collective/runtime 不能被纳入 mega-kernel。
- **假设 1**：对给定 model、batch 上限、parallelism 与 GPU architecture 做 specialized compilation 的成本可被 serving 生命周期摊销。
  - **证据强度**：中。论文展示生成代码性能和少量 PyTorch 改动，但未把 compile/search time 纳入 latency/cost 主结果。
- **假设 2**：shared-memory paging、event metadata 与 scheduler SM 的资源占用不会显著压低 compute kernel occupancy。
  - **证据强度**：强于定性。ablation 与 memory reduction 给出证据，但只覆盖五个 model 和三代 NVIDIA GPU。

## 核心方法

MPK 引入 tGraph：node 是单个 SM 上运行的 task，edge 是 producer/consumer task 的细粒度 dependency，event 汇聚前驱完成并释放后继。compiler 从 tensor DAG 与 inference configuration 生成初始 tGraph，再做 event fusion、graph normalization 和 linearization，减少 event 数、同步 metadata 与 runtime traversal；单 task CUDA implementation 由既有 superoptimization 技术生成。

单个 persistent mega-kernel 内把 SM 分为 worker 和 scheduler。worker 有 FIFO task queue 并执行 compute/communication task；scheduler 更新 event、在 dependency 满足时 dispatch。JIT launch 动态选择 worker、适合 execution time 易变的 task；AOT launch 提前把 task 放入固定 queue，仅等待 event，降低 dispatch latency。compiler 的 hybrid labeling 在 global barrier 后偏向 AOT，在 imbalance 可能积累处保留 JIT。

runtime 还提供 paged shared memory abstraction，使生命周期不重叠的 task 复用有限 SMEM；task description prefetch 隐藏 queue metadata 读取。decode iteration 开始时，kernel 内直接更新 request admission 与 [[KV-Cache]] metadata，支持 batch 变化；[[MoE|MoE]] 则按 routing 动态 dispatch expert task，避免完全静态 mapping 的 imbalance。

multi-GPU 时，通信 task 也进入 tGraph，producer SM 完成相应 fragment 后即可触发 AllReduce/All-to-All 的部分工作，下游 compute 只等自己的输入 fragment，而不是整个 operator barrier。

## 设计取舍

- **细粒度 graph**：暴露更多 parallelism，却将数百 operator 展开为上万 task/event；fusion/linearization 是可扩展性的必要条件。
- **persistent ownership**：消除 CPU launch 并统一调度，代价是与外部 workload 共存、preemption 和 observability 更困难。
- **AOT/JIT hybrid**：AOT 低 overhead 但 mapping 固定，JIT load balance 好但 scheduler 开销高；效果依赖 compiler 对 variability 的预测。
- **architecture specialization**：逼近硬件上限，但 CUDA/NVIDIA-specific implementation 的 portability 与新 GPU adaptation 成本较高。

## 实验与结果

- 五个常用 [[LLM|LLM]]、batch 1–16，覆盖 A100/H100/B200；baseline 包括 PyTorch/CUDA Graph、vLLM 与 SGLang，并复用 FlashInfer/FlashAttention/cuBLAS 等优化 kernel（§6.2）。
- 单 batch serving 中，MPK 相对最佳 vLLM/SGLang 改善 1.0–1.7×；A100 上 Qwen3-8B 每 token decode latency 从 14.5 ms 降至约 8.5 ms（§6.3、图 9）。
- 扩展到 8×H100 tensor parallel 时，相对 PyTorch 吞吐最高提高 10×，相对 vLLM/SGLang 提高 1.1–1.4×（§6.5、图 11）。
- Qwen3-8B 的 cross-task pipelining 使 linear task runtime 改善 1.2–1.3×；细粒度 compute–communication overlap 使 multi-GPU iteration latency 改善约 1.1×（§6.6）。
- Qwen3 模型中 event fusion 把 synchronization event 减少 37–118×；linearization 把 graph metadata footprint 减少 4.4–15.0×，例如 Qwen3-8B 从 110,932 B 降至 18,928 B（§6.7、表 2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 自动 mega-kernel 优于成熟 per-operator serving | §6.3、图 9：latency 改善 1.0–1.7× | 五模型、batch 1–16、A100/H100/B200、offline batched inference | 强 |
| multi-GPU 细粒度 overlap 有额外收益 | §6.5–6.6：8 H100 上 1.1–1.4×，overlap ablation 约 1.1× | tensor parallel，特定 Qwen model/config | 强 |
| tGraph optimization 控制 metadata/sync explosion | §6.7、表 2：event 少 37–118×、footprint 少 4.4–15× | 三个 Qwen3 model | 强 |
| MPK 支持 dynamic MoE 而非仅静态 dense graph | §6.4、图 10 | 所测 MoE routing distribution；未覆盖 serving burst | 中 |

## 批判性分析

### 论证链条

论文把 kernel barrier 的 coarse dependency 映射到 SM-level graph，把 launch/dispatch 映射到 in-kernel runtime，机制与 ablation 闭合。相对 PyTorch 的 10×主要说明 baseline dispatch 差距，最可信的系统增益是相对强 vLLM/SGLang 的 1.0–1.7×和 1.1–1.4×。

### 假设压力测试

MPK 的延迟优势在 batch 小、kernel 短、launch/communication 暴露多时最大；batch 变大后单 operator 已接近饱和，mega-kernel overhead 更难摊薄。若同 GPU 需要 concurrent model、[[LoRA|LoRA adapter]]、prefill/decode disaggregation 或 strict priority，单 persistent kernel 的资源占有可能与 serving scheduler 冲突。MoE 极端 skew 也会考验 JIT scheduler capacity。

### 实验可信度

覆盖三代硬件、dense/MoE、single/multi-GPU、强 baseline 和 compiler ablation，证据扎实；artifact 还给出固定 prompt 64、decode 1024、greedy 的 reproduction boundary。缺口是 workload 主要为 offline batch，未呈现 arrival trace 下 TTFT/TPOT/P99、continuous batching、[[Prefix-Caching|prefix cache]] 和 multi-tenant interference，也未量化 compile/search time。

### 系统性缺陷

mega-kernel 内部调度降低了标准 profiler/kernel trace 的可读性，hang 或 deadlock 的故障定位更难。persistent kernel crash 会覆盖整个 model iteration；论文未讨论 timeout、cancellation、request failure isolation 与 CUDA context recovery。跨 GPU communication 自管后还要承担 topology、collective correctness 和新 interconnect 适配维护。

## 局限与后续工作

- **局限 1**：仅 NVIDIA CUDA GPU，未验证 AMD/TPU 或跨代自动 portability。
- **局限 2**：以 offline fixed prompt/decode 为主，production arrival、P99 与 multi-tenancy 未覆盖。
- **局限 3**：compile/superoptimization 时间、cache 与 binary size 未计入部署成本。
- **后续工作 1**：在 ShareGPT/production trace 下与 vLLM/SGLang 比较 TTFT、TPOT、P99、goodput，并扫 concurrent model/priority interference。
- **后续工作 2**：加入 task timeout、request cancellation 和 scheduler watchdog，fault-inject deadlock/SM failure 并测恢复粒度。
- **后续工作 3**：报告 configuration 变化下的 compile cache hit、首次部署时间和新 GPU bring-up 工时，量化 specialization 的全生命周期成本。

## 相关

- **相关概念**：[[Persistent-Kernel]]、[[Kernel-Fusion]]、[[Tensor-Compilation]]、[[Compute-Communication-Overlap]]
- **同类系统**：[[vLLM]]、[[SGLang]]、[[PyTorch]]、[[Triton]]
- **同会议**：[[OSDI-2026]]
