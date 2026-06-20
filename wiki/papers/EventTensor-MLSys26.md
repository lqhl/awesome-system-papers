---
type: paper
name: EventTensor
full_title: "Event Tensor: A Unified Abstraction for Compiling Dynamic Megakernel"
authors: [Hongyi Jin, Bohan Hou, Guanjie Wang, Ruihang Lai, Jinqi Chen, et al.]
venue: MLSys
year: 2026
tags: [compiler, megakernel, llm-inference, moe, gpu-scheduling]
source_pdf: "[[07e1cd7dca89a1678042477183b7ac3f.pdf]]"
source_md: "[[07e1cd7dca89a1678042477183b7ac3f]]"
---

# Event Tensor: A Unified Abstraction for Compiling Dynamic Megakernel (MLSys 2026)

> **一句话总结**：观察到 LLM decode 中 kernel launch（5–10 µs）与 kernel 边界粗同步是主导瓶颈，而现有 megakernel 无法表达 shape/data-dependent 动态依赖；Event Tensor 把 SM 级同步事件升为一等多维 tensor（symbolic shape + runtime 索引），ETC 编译器生成动态 persistent megakernel，低 batch decode 比 [[vLLM]] 快 1.48×、warmup 35 s vs 123 s（3.5×），MoE 整层融合 1.23×。

## 问题与动机

现代 GPU ML 工作负载——尤其是 [[LLM-Inference]]——在 host 侧逐 kernel launch 的执行模型下，系统开销已可与算子本身竞争。论文量化了两个瓶颈：（1）每个 kernel launch 约 5–10 µs，而最快 kernel 可能仅 2 µs，decode 一步动辄数百上千细粒度 op，launch 无法摊销；（2）kernel 边界强制全局同步，后续 kernel 往往只依赖前序 kernel 的部分输出，却无法跨边界 pipeline，inter-kernel 并行被白白浪费。

[[CUDA-Graph]] 通过 capture/replay 消除 launch overhead，但保留 kernel 边界，无法暴露细粒度并行。近期 megakernel 工作（Mirage Persistent Kernel、ThunderKittens 等）把多算子 fuse 成单一 persistent kernel，在消除 launch gap 的同时用 tile-level task + 轻量 signaling 实现跨算子 overlap。然而真实 [[LLM-Serving]] 有两类动态性让手写 megakernel 极难落地：

1. **Shape dynamism**：[[Continuous-Batching]] 带来变 batch/变 sequence length；静态 megakernel 需为每种 shape 重编译或重生成，warmup 成本爆炸，shape 空间过大时甚至不可行。
2. **Data-dependent dynamism**：[[MoE]] 路由在 runtime 决定 token→expert 映射，task 依赖图不规则且 compile time 未知，需要 runtime 更新 event counter 和触发可变数量 consumer task。

此外，megakernel 编程要求开发者手工维护百万级 tile 依赖，static vs dynamic scheduling 策略也难以在不重写 kernel 的前提下切换。论文 claim：需要一个 **compiler-first** 抽象，把 fine-grained synchronization 表达为一等对象，并系统化支持两类动态性。

## 关键观察 / 隐含假设

- **观察 1**：LLM decode 的 latency 敏感场景（agentic workflow、交互式 coding assistant）以 **低 batch** 为主，此时 kernel launch + 边界同步开销相对算子执行时间占比最高，inter-kernel parallelism 对 per-request latency 至关重要。
  - **依赖假设**：benchmark 用 synthetic prefill=512、decode 100 tokens、batch 1–128 能代表这类 workload；大 batch prefill 场景 megakernel 收益有限（论文 §4.3 也承认）。
  - **可能失效场景**：高吞吐 datacenter serving 以 large-batch prefill/decode 为主时，收益可能收敛到通信 overlap（§4.1）而非端到端 TPOT。

- **观察 2**：MoE 等 data-dependent workload 的依赖链在 macro 层面仍是 feed-forward（Attention → TopK → Grouping → GroupGEMM），**只有后段**依赖 routing 结果；可用 runtime tensor（`topk`、`exp_indptr`）驱动 event update 和 task trigger，无需在 compile time 物化完整 task graph。
  - **依赖假设**：MoE 路由决策在 megakernel 内 sequential 完成，不存在跨 step 的复杂 control flow；expert 数量与 top-k 固定（Qwen3-30B-A3B：128 experts, top-k=8）。
  - **可能失效场景**：更复杂的 dynamic control flow（speculative decoding 分支、conditional early exit）可能超出当前 Event Tensor 表达力。

- **观察 3**：把 event 组织成多维 tensor 后，可复用现有 compiler 的 **symbolic shape** 基础设施（Relax、torch.compile 等），用单一模板 AOT 编译覆盖多种 runtime shape，彻底避免 CUDA Graph 反复 recapture。
  - **依赖假设**：unseen shape 可通过采样 representative shapes + 向上取整 reuse queue 处理（static scheduling）；或 dynamic scheduling 在 runtime 解析 symbolic dim。
  - **证据强度**：**强**——warmup 实验直接对比 vLLM 67 个 graph capture vs ETC 单次 AOT load（35 s vs 123 s）。

- **假设 1**：fine-grained notify/wait（counter-based semaphore + spin-wait）在百万 event 规模下开销可控，且优于 materialize 完整 task graph 的 generic executor。
  - **证据强度**：**中**——MoE/TP overlap 实验支持；但 dynamic scheduler 用 centralized global queue，论文承认大规模可能有 contention（Appendix E 仅讨论 early push 优化）。

## 核心方法

### Event Tensor 抽象

**Event** 表示一组 tile task 在 SM 级完成；**Event Tensor** 是其多维数组，每个元素维护 wait count，支持 `notify()`（atomic decrement）、`wait()`（spin until zero），dynamic scheduling 下还可 trigger dependent tasks。核心创新不是 semaphore 本身，而是把同步原语 **升为一等 compiler IR tensor**，与 data tensor 并列出现在 graph function 中。

程序结构三层：
- **Device function**：按多维 coordinate 启动 tile task grid，可含 warp specialization / tensor core 调用
- **Event Tensor**：显式 `in_edges`/`out_edges` 标注 producer→event→consumer 映射，或用 lambda 表达坐标变换
- **Graph function**：串联 device function launch，同时携带 data tensor 与 Event Tensor

### 两类动态性

**Shape dynamism**：Event Tensor 维度可为 symbolic（如 batch B），compile time 生成 dependency template，runtime 用具体 shape 实例化 task graph（Figure 4），无需重编译。

**Data-dependent dynamism**（MoE 为例）：
1. **Data-dependent event update**：`topk` 决定每个 grouping tile 更新哪个 expert event；event counter 初始化为 routed token 数
2. **Data-dependent task trigger**：`exp_indptr`（per-expert GroupGEMM tile 前缀和）决定 expert i 触发 `(exp_indptr[i], exp_indptr[i+1])` 范围的 tile

### ETC 编译器与调度

基于 Apache [[TVM]] passes，DSL-agnostic（实现用 TVM-based DSL，可移植到 [[Triton]] 等）：

- **Static scheduling**：host 预计算 per-SM task queue → persistent main loop；Event Tensor 降为 integer tensor + notify/wait。适合可预测 workload（All-Gather + GEMM 按 ring 顺序到达）。
- **Dynamic scheduling**：event counter 归零时 atomic push ready tasks 到 GPU scheduler queue，空闲 SM pop 执行。适合 MoE 不规则路由、GEMM+Reduce-Scatter 通信抖动。
- **Lowering**：Event Tensor → integer tensor，runtime 仅需 counter tensors + scheduler queue，无需 materialize task graph（对比传统 executor Figure 10）。

端到端流程：graph-level opt（memory planning）→ tile-level opt → static/dynamic scheduling pass → persistent kernel emit → optional weight prefetch pass。

## 设计取舍

- **Static vs Dynamic scheduling**：static 同步开销最低、适合 latency-sensitive 低 batch decode；dynamic 提供 load balance 但 push/pop + centralized queue 有 runtime 开销，multi-GPU TP 场景 dynamic 反而更慢（Table 3：distributed push 到 remote queue 代价大）。
- **Worst-case conservative rewrite**：static scheduling 处理 data-dependent dynamism 时，把相关 notify/wait 改写为 worst-case（如 `E[0].notify()`），牺牲精度换取可静态调度。
- **Shape coverage**：unseen shape 复用 next-larger sampled shape 的 queue，可能 over-provision 同步或浪费 SM 分配。
- **Composable with serving engines**：ETC 作为 backend 编译 megakernel，但端到端实验暴露 compiler-generated GEMM tile 调优不如 cuBLAS、CPU-side scheduling overhead 高于 [[SGLang]] 等问题——收益来自 GPU execution model 而非完整 serving stack 最优。
- **边界条件**：大 batch bandwidth-bound（8192 tokens）+ 通信 overlap 场景 dynamic scheduler 表现好；低 batch latency-bound + multi-GPU 场景 static scheduler 更优。

## 实验与结果

硬件：8× NVIDIA B200，NVLink，CUDA 13.0，PyTorch 2.8.0。

- **GEMM + Reduce-Scatter**（8×B200，TP=8，8192 tokens，dynamic scheduler）：相对 cuBLAS+NCCL 最高 **1.40×**；优于 TP-Async、Triton Distributed、cuBLASMp
- **All-Gather + GEMM**（static scheduler）：同样最高 **1.40×** over cuBLAS+NCCL
- **MoE 整层**（Qwen3-30B-A3B，128 experts，top-k=8，单 B200，dynamic scheduler）：相对 Triton/FlashInfer 最高 **1.23×**（1024 tokens）
- **端到端 decode TPOT**（prefill=512，gen=100 tokens，覆盖 Attention/RoPE/[[KV-Cache]]/Norm/MLP/MoE）：
  - Qwen3-30B-A3B batch=1：比 [[vLLM]] v0.11 **1.48×**，比 [[SGLang]] v0.5 **1.20×**
  - Qwen3-32B batch=1：比 vLLM **1.15×**；batch=64 比 SGLang **1.09×**
  - Qwen3-32B TP=4：与 vLLM 持平（0.99–1.06×），低于 SGLang（CPU scheduler 更优）
- **Engine warmup**（Qwen3-32B）：ETC **35 s** vs vLLM **123 s** vs SGLang **583 s**（~3.5× over vLLM）；AOT 编译 107 s offline，runtime 无 JIT/CUDA Graph recapture
- **Scheduling ablation**：MoE 上 dynamic vs static 最高差 4.0%；dense TP=4 上 static vs unfused megakernel 稳定 **6–8%** 增益（纯来自 fine-grained pipelining）
- **Raw kernel time**（排除 CPU overhead）：Qwen3-30B-A3B batch=1 比 vLLM **1.49×**、比 SGLang **1.27×**

## Critical Analysis

### 论证链条

Observation（launch + boundary sync 主导低 batch decode latency）→ Event Tensor 表达 fine-grained deps + 两类 dynamism → ETC 生成 persistent megakernel → 在强 baseline（vLLM/SGLang + CUDA Graph + torch.compile）上仍有 1.1–1.5× TPOT 提升。链条在 **单 GPU 低 batch decode** 和 **MoE/通信融合 microbenchmark** 上闭合较好。

薄弱环节：（1）multi-GPU TP 端到端仅打平 vLLM、输给 SGLang，作者归因 engineering gap 而非抽象限制——合理但未完全排除 static scheduling + CPU orchestration 组合更优的可能；（2）大 batch serving 场景论文明确说收益边际，claim 边界需牢记。

### 假设压力测试

- **Centralized dynamic scheduler queue**：所有 SM 竞争同一 global queue，SM 数/GPU 数增加时 contention 可能放大；论文未给出 scalability 曲线。
- **Worst-case static fallback for data-dependent ops**：在 routing 高度倾斜时可能 over-synchronize，损失 MoE 细粒度 pipeline 优势。
- **B200 + 最新 stack 特异性**：baseline 中 Triton Distributed 对 Blackwell 优化不足，可能放大 ETC 相对优势；跨硬件代际（A100/H100）外推需谨慎。
- **Serving integration 成熟度**：端到端数字包含 framework overhead，ETC 的 CPU 侧调度明显弱于 SGLang；若只替换 kernel backend 而不优化 host runtime，生产收益可能低于 raw kernel 实验。

### 实验可信度

- **Baseline 强度**：vLLM/SGLang 均为 industry-level 且启用 CUDA Graph + compile，对比公平性高。
- **Microbenchmark 与 E2E 分离**：Appendix D raw kernel 实验剥离 CPU overhead，支撑「GPU execution model 是主要增益来源」的判断。
- **Ablation 设计**：unfused megakernel baseline 使用相同 operator code、仅加 global sync barrier，isolates inter-operator parallelism 贡献，设计合理。
- **未覆盖**：tail latency（P99）、multi-tenant 隔离、fault recovery、长序列 prefill、speculative decoding 路径均未讨论。

### 系统性缺陷

- **编程门槛**：虽比手写 megakernel 低，但仍需用 TVM DSL 写 tile-level device function 并显式标注 Event Tensor 依赖；论文承认未来需要 auto-generate task graph 的 higher-level pass。
- **Dynamic scheduler 扩展性**：centralized queue 是 simplicity trade-off，论文未讨论 hierarchical / per-SM queue 等替代。
- **GEMM 质量**：compiler-generated tile 在部分 config 不如 cuBLAS，是 TP 场景落后的直接原因之一。
- **可观测性/调试**：persistent megakernel 内百万 event 的 deadlock/race 调试难度，论文未讨论。
- **与 CUDA Graph 共存策略**：生产环境可能仍需 graph capture 覆盖非 megakernel 路径，集成复杂度未展开。

## 局限与 Future Work

- **局限 1**：现有 megakernel 框架（对比对象）仅支持 single-batch dense inference，论文实验也主要聚焦 decode + 特定 Qwen 家族；泛化到其他模型架构/量化路径需额外工程。
- **局限 2**：Event Tensor 程序仍需手工或半手工构造；论文 Future work 明确提出从标准 computational graph 自动生成 Event Tensor task graph。
- **Future work 1**：auto-scheduling pass——根据 workload 特征在 static/dynamic 间自动选择或 hybrid，避免人工调参（Table 2/3 已显示选择错误可损 4–8%）。
- **Future work 2**：hierarchical GPU scheduler 设计空间——测量 centralized queue contention vs per-SM local queue 在不同 SM count / MoE skew 下的 crossover point。
- **Future work 3**：与 [[FlashInfer]]、cuBLAS 等成熟 kernel 库 composable fusion——只 megakernel 化 dependency-heavy 段（MoE routing + GroupGEMM pipeline），保留调优过的 GEMM/Attention kernel。

## 相关

- **相关概念**：[[Megakernel]]、[[MoE]]、[[KV-Cache]]、[[Continuous-Batching]]、[[CUDA-Graph]]、[[Tensor-Parallelism]]
- **同类系统**：[[vLLM]]、[[SGLang]]、Mirage Persistent Kernel、ThunderKittens、Triton Distributed、[[FlashInfer]]、CuSync
- **同会议**：[[MLSys-2026]]
- **对比**：ETC 相对 CUDA Graph 的核心差异在于打破 kernel 边界 + 支持 dynamic shape/data-dependent deps；相对手写 megakernel 在于 compiler-managed Event Tensor 与 dual scheduling passes