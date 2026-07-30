---
type: paper
name: Tempo
full_title: "Tempo: Compiled Dynamic Deep Learning with Symbolic Dependence Graphs"
authors: [Pedro F. Silvestre, Peter Pietzuch]
venue: SOSP
year: 2025
tags: [dl-compiler, dynamic-tensors, reinforcement-learning, llm-decoding, polyhedral]
source_pdf: "[[3731569.3764840.pdf]]"
source_md: "[[3731569.3764840]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Tempo：使用符号依赖图编译动态深度学习（SOSP 2025）

> **原题**：Tempo: Compiled Dynamic Deep Learning with Symbolic Dependence Graphs

> **一句话总结**：Tempo 用 recurrent tensors 与 symbolic dependence graph 编译 temporal dependencies。Llama-3.2-3B windowed attention 在 T=16,384、batch 16 时最多比 JAX **7×** 快；PPO 对 RLlib 的最高 iteration-time 改善为 **54×**。两者不泛化为所有 decode 或 RL algorithms。

## 问题与动机

许多 DL 算法（[[Attention]]、RL、diffusion）用 recurrence 表达跨 timestep 依赖，但 eager 系统（PyTorch）无法 whole-program 优化；graph 系统（JAX/TensorFlow）要求静态 shape，迫使用 padding/mask、loop unroll 或拆成多个 static subgraph。

后果：LLM decode 的 [[KV-Cache]] 策略需为每种 attention 类型手工工程；RL 的 actor-learner 拆分导致 **重复前向**、**串行 acting/learning**、**高峰显存**（Fig. 4 三大缺陷）。

## 关键观察 / 隐含假设

- **观察 1**：动态依赖的结构可用 timestep 符号表达式紧凑编码，从而支持代数化简、vectorization、tiling 等 whole-program 优化。
  - **依赖假设**：依赖表达式在编译期可符号操作（invert、slice range 等）；T 上界已知或可参数化。
  - **可能失效场景**：数据依赖的控制流（依赖运行时 tensor 值的分支）超出 RT 表达能力。
  - **证据强度**：强——RL 与 LLM decode 两类 workload 均显著加速。
- **观察 2**：RL actor-learner 拆分的根本原因是现有系统无法在同一程序里表达 acting 与 learning 的细粒度未来依赖。
  - **依赖假设**：experience 数据可通过 RT 自动 memory management 保留/释放，无需 replay buffer 语义。
  - **可能失效场景**：极大 T 导致 schedule/search 爆炸；需显式 checkpoint 的极长 horizon。
  - **证据强度**：中——三种经典 RL 算法验证，但未覆盖 distributed RL。
- **假设 1**：polyhedral schedule + 自动 memory management 可在单 GPU 上优于手工调度的 JAX/Torch 实现。
  - **证据强度**：强——7×/54× 量级差距，ablation 支持 tiling 与 memory 贡献。

## 核心方法

1. **Recurrent tensors (RT)**：显式 temporal dimension，用符号表达式索引过去/未来 timestep；支持 domain unioning、符号自动微分（dependence invert）。
2. **Symbolic dependence graph (SDG)**：顶点带 temporal domain，边用符号表达跨 timestep 依赖；在此上做代数化简、vectorization、tiling（动态依赖 tile 成 static block 复用现有 codegen）。
3. **Polyhedral scheduling**：SDG 转 ILP 约束求全局执行顺序。
4. **Automated memory management**：在 SDG 上插入 dealloc/donate/swap 操作，与 schedule 联合求解。

后端可接 Torch/JAX codegen，按 schedule AST 运行时解析符号依赖。

## 设计取舍

- **取舍 1**：声明式 RT 编程模型学习曲线高于 imperative PyTorch，换 compile-time 优化空间。
- **取舍 2**：单 GPU 原型，分布式 dynamic DL 未涉及。
- **边界条件**：依赖结构在编译期可符号化的算法收益最大；完全动态 shape 且无 recurrence 结构的模型收益有限。

## 实验与结果

**指标、基线与边界**：mean time between tokens、PPO iteration time、maximum observation resolution；Tempo vs JAX/Torch/RLlib/CleanRL；RTX A6000、Llama-3.2-3B 或 PPO specified simulation workload（§7）。

- windowed attention、batch 16、T=16,384：MTBT 最多比 JAX **7×**、Torch **3.9×**（§7.1–7.2，Fig.17c）。
- causal attention、batch 4：T=32,768/65,536 时比 JAX **2×/2.5×**（§7.2，Fig.17b）。
- PPO iteration time 最多比 RLlib **54×** 快、平均比次快 baseline CleanRL **2.6×**；默认 workload 为 250 simulation steps/512 envs（§7.3，Fig.20）。
- PPO 可处理 **3×256×256** observation，为 3×64×64 的 **16×** input area；其他 baselines 更早 OOM（§7.3，Fig.21）。

## 论断—证据表

| 论断 | 证据 | 指标 / 基线 / 评测边界 | 定位 | 置信度 |
|---|---|---|---|---|
| 7× 是 windowed decode 的峰值 | JAX 7×、Torch3.9× | Llama3.2-3B、batch16、T16384、RTX A6000 | §7.1–7.2，Fig.17c | high |
| causal 长上下文有不同配置/收益 | 2×/2.5× | batch4、T32768/65536；vs JAX | §7.2，Fig.17b | high |
| RL 最大结果只对应 PPO/RLlib | up to54×、vs CleanRL avg2.6× | PPO、250 steps/512 envs、指定 frameworks | §7.3，Fig.20 | high |
| 16× 描述可扩展 input area | 3×256² vs3×64² | PPO、256 envs/1000 steps；非“peak memory 16× lower” | §7.3，Fig.21 | high |
| compile-time 有测得成本 | ~18s，codegen7s、alloc1s、ILP~2s | repeated transformer layers；非无上限 scale | §7.5，Fig.24 | high |

## 批判性分析

### 论证链条

「动态依赖有结构 → 符号图可优化」是核心 insight，从 observation 到 SDG/polyhedral 设计链条闭合。RL 结果尤其能证明 actor-learner 拆分非必然，具有 counterintuitive 价值。

### 假设压力测试

- 编译时间随 T、模型深度增长如何 scale？论文对 compilation time 讨论有限。
- 多 GPU / pipeline parallel decode 未覆盖，7× 结论限于 single-GPU。
- 与 [[Flash-Attention|FlashAttention]]、[[PagedAttention]] 等手工 KV 优化系统的正面对比深度不足。

### 实验可信度

Baseline 包含多种 RL 框架，覆盖面好。LLM 实验用 3B 模型，对 70B+ production serving 的外推需谨慎。

### 系统性缺陷

论文未讨论：编译失败/debug 体验；与 torch.compile/XLA 动态 shape 进展的横向对比；生产部署的 warmup 与 AOT 缓存策略。

## 局限与后续工作

- **局限 1**：单 GPU，无分布式 dynamic compilation。
- **局限 2**：用户需适应 RT 编程模型。
- **Future work 1**：与 [[KV-Cache]] 专用 runtime（vLLM 类）的 hybrid——编译期 schedule + runtime paging。

## 相关

- **相关概念**：[[KV-Cache]]、[[Attention]]、[[Flash-Attention|FlashAttention]]
- **同类系统**：JAX、PyTorch、TorchInductor
- **同会议**：[[SOSP-2025]]
