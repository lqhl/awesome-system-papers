---
type: paper
name: VTC
full_title: "VTC: DNN Compilation with Virtual Tensors for Data Movement Elimination"
authors: [Muyan Hu, Ahan Gupta, Jiachen Yuan, Janardhan Kulkarni, Ofer Dekel, et al.]
venue: OSDI
year: 2026
tags: [tensor-compiler, gpu, data-movement, virtual-tensor, dnn-inference]
source_pdf: "[[osdi26-hu-muyan.pdf]]"
source_md: "[[osdi26-hu-muyan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 用 Virtual Tensor 消除 DNN Data Movement（OSDI 2026）

> **原题**：VTC: DNN Compilation with Virtual Tensors for Data Movement Elimination

> **一句话总结**：现有 layout optimization/operator fusion 只能消除部分搬运；VTC 将任意纯 data-movement operator 表示成 physical tensor 上的 index mapping，并用 profile-guided opportunity graph 选择有利组合，在 A100/H100 五种 DNN 上比最佳 compiler 最多快 1.93×、平均 1.28×，峰值显存最多省 60%、平均 17.5%。

## 问题与动机

GPU compute 增长快于 memory bandwidth，DNN 中 Transpose、Split、ScatterND、Slice、Expand 等不做算术的 operator 仍反复读写 global memory。layout optimization 主要处理 Reshape/Transpose，fusion 又依赖手写 pattern；在 Llama-3 decode 中，TensorRT 已识别 [[Attention|attention]]，却仍用六个 kernel 处理 QKV projection 与 FlashDecoding 之间的搬运，其 latency 超过相邻 compute。

VTC 的观察是 compute unit 只要求 on-chip tile contiguous，global tensor 无需完整 contiguous。若 producer/consumer 的 load/store stage 能理解 index mapping，中间 tensor 无需物理 materialize；问题转化为决定哪些 tensor virtualize，以及 mapping overhead 是否小于省掉的搬运。

## 关键观察 / 隐含假设

- **观察 1**：所有 data-movement operator 都可写成 output index 到唯一 input element 的 mapping，故能以 pointer + mapping 代替完整 physical tensor（§2、定义 2–3）。
  - **依赖假设**：operator 不改变 value；mapping 可组合并在 block granularity 高效求值。
  - **可能失效场景**：reduction、value-dependent gather、alias/in-place side effect 或动态 shape 使 mapping 复杂。
- **观察 2**：global memory 只需“部分 contiguous”即可 coalescing；例如 head dimension 128 大于 warp 32，非完整连续仍有宽 transaction（§3.1、图 3）。
  - **依赖假设**：contiguous chunk 足够大、mapping branch 不发散，kernel I/O 修改不破坏 tensor-core tile。
  - **可能失效场景**：小/irregular chunk、极端 gather/scatter、TMA/CUTLASS 对 layout 有更强约束。
- **假设 1**：profiled edge latency 在目标 batch/shape/hardware 上稳定，greedy strategy 足够接近最优。
  - **证据强度**：中。五模型表现良好，但无 optimality bound；新 configuration 需重新 profile。
- **假设 2**：只改 kernel stage 1/3 可复用现有 compute kernel，numeric semantics 不变。
  - **证据强度**：强。实现保持 end-to-end numeric equivalence；performance portability 仍受 Triton 限制。

## 核心方法

virtual tensor 是 `(mapping F, physical pointers P)`，访问 `V[x]` 时由 `F(x)` 找到某个 `Pj[y]`。producer 可通过 virtual store 直接把 QKV result 写进 Q 与 [[KV-Cache]]，consumer 的 virtual load 则从非完整连续的 physical region 直接取数；mapping 只进入 global-memory I/O，compute body 保持不变。

compiler 从 fusion 后 graph 构造 virtual-tensor opportunity graph（VTOG），枚举 data-movement chain 的可行 mapping 与 producer/consumer 改写。edge weight 通过 profiling 估计“省掉搬运 - virtual I/O overhead”的 marginal latency saving，并考虑多条 mapping conflict。

全局 greedy algorithm 逐轮选择当前非冲突收益最大的 edge/set；若最大收益为负则停止，因此在 H100/vLLM case 会自动跳过有害改写。最终 points-to graph 指定哪些 tensor materialize，TorchInductor analysis pass 修改 IR，transformation pass 删除搬运 node并把 overloaded load/store 降到 Triton。

## 设计取舍

- **indirection 换 materialization**：省 global write/read 与 allocation，但 compute kernel 的 address calculation、non-contiguous access 变慢。
- **profiling 换 cost-model robustness**：少依赖静态 GPU model，编译每 configuration 仍少于 10 分钟，不适合极短生命周期/dynamic shape 爆炸。
- **greedy 换 polynomial complexity**：避免指数搜索，无全局最优保证。
- **接在 fusion 之后**：与现有 compiler 互补且低侵入，但上游 fusion/layout choice 可能先关闭更好的 virtual strategy。

## 实验与结果

- A100 80 GB [[PCIe|PCIe]] 与 H100 NVL，Llama-3、Gemma-2、EfficientViT、YOLOv11、ShuffleNet，batch 1/16；对比 [[PyTorch|torch]].compile、ONNX Runtime、XLA、TensorRT（§7.1）。
- 相对每项最快 baseline，end-to-end latency 最多改善 1.93×、平均 1.28×；Transformer 平均 1.36×，CNN 平均 1.15×（§7.2、图 9）。
- 10 个 model/batch case 中 7 个完全消除 data-movement operator；H100 上 10 项中 7 项比 A100 获得更大 speedup（§7.2–7.4、图 10）。
- 相对 PyTorch，A100 peak GPU memory 最多减少 60%、平均 17.5%，来源是 large intermediate 不再 materialize（§7.3、表 2）。
- 集成 [[vLLM]] 的 Llama-3 8B case，A100 decoder layer end-to-end 只改善 1.011×；H100 自动选择不优化，若强制 virtualize 反而慢 8%（§7.5、表 3–4）。
- profiling 每 configuration 少于 10 秒，所测完整 model compilation 少于 10 分钟（§6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Virtual tensor 可在通用 compiler 中显著降 latency | §7.2、图 9：最多 1.93×、平均 1.28× | 五模型、batch 1/16、A100/H100 | 强 |
| 虚拟化同时节省显存 | §7.3、表 2：最多 60%、平均 17.5% | A100、相对 PyTorch peak memory | 强 |
| profile guard 能避免负优化 | §7.5：H100 默认跳过，强制方案慢 8% | 单一 vLLM/Llama configuration | 强 |
| 对强手工 [[LLM\|LLM]] baseline 的收益有限 | §7.5：A100 vLLM end-to-end 1.011× | Llama-3 8B、context 4096、BF16 | 强 |

## 批判性分析

### 论证链条

论文从纯搬运的 index semantics 推出 virtual representation，再以 I/O-stage 改写和 profile selection 解决 correctness/performance，逻辑闭合。相对 compiler 的平均收益明显；vLLM case 诚实显示强 domain-specific kernel 已消除多数机会，通用性并不等于每种生产 serving 都有大收益。

### 假设压力测试

收益随搬运占比、chunk contiguity 与 compiler kernel quality 变化。H100 强制优化慢 8%说明更快 compute/memory primitive 不必单调放大收益；若 Triton MatMul 落后 cuBLAS，省下搬运也会被 compute regression 抵消。动态 sequence/batch、alias 和 training backward graph 会扩大 mapping/strategy 空间。

### 实验可信度

baseline 强、模型跨 Transformer/CNN、两代 GPU、memory/latency breakdown 与负结果都有，证据扎实。缺少 training、multi-GPU、dynamic shape、Blackwell/TMA 和 strategy optimality 对比；compile time 只报上限，未给 opportunity 数量与 profile count scaling。

### 系统性缺陷

virtual tensor 改变 kernel address semantics，debugger/profiler 看到的 tensor 不再有独立 storage，错误定位和 interoperability 更难。外部 custom kernel 若不支持 virtual load/store 必须 materialize，graph boundary 会削弱收益。mapping code generation 还增加 compiler correctness attack surface，需要 differential test 各种 shape/index。

## 局限与后续工作

- **局限 1**：当前基于 Triton，H100 已暴露相对 cuBLAS 的 kernel quality gap。
- **局限 2**：只评测 single-GPU inference，training/backward/dynamic shape 未覆盖。
- **局限 3**：greedy 无最优保证，profiling 使编译时间随 configuration 增长。
- **后续工作 1**：集成 CUTLASS/TMA，并在 H100/B200 上比较同一 mapping 的 memory transaction 与 kernel regression。
- **后续工作 2**：扩展 training graph，对 forward/backward alias、activation checkpoint 做 differential numeric test和 peak-memory评测。
- **后续工作 3**：用小 graph exhaustive search 对比 greedy，报告 optimality gap，并训练静态 cost model减少 profile 次数。

## 相关

- **相关概念**：[[Tensor-Compiler]]、[[Data-Movement]]、[[Operator-Fusion]]、[[Virtual-Tensor]]
- **同类系统**：[[TorchInductor]]、[[TensorRT]]、[[vLLM]]、[[Triton]]
- **同会议**：[[OSDI-2026]]
