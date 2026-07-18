---
type: paper
name: AXLearn
full_title: "AXLearn: Modular, Hardware-Agnostic Large Model Training"
authors: [Mark Lee, Chang Lan, Tom Gunter, John Peebles, Hanzhi Zhou, "et al."]
venue: MLSys
year: 2026
tags: [training-framework, modularity, jax, xla, hardware-agnostic, apple]
source_pdf: "[[28dd2c7955ce926456240b2ff0100bde.pdf]]"
source_md: "[[28dd2c7955ce926456240b2ff0100bde]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# AXLearn: Modular, Hardware-Agnostic Large Model Training (MLSys 2026)

> **一句话总结**：Apple 开源 JAX/XLA 训练框架，用严格封装 + 层次化 config modifier 将 RoPE/[[MoE]] 等特性扩展成本压到 O(1) LoC-Complexity（约 10 行配置覆盖 1000+ 实验），在 H100/TPU v5p/Trainium2 上与 Megatron/MaxText 性能持平，弱扩展 256→4096 chip MFU 仍 52–63%，但 H100 上 Megatron 仍更快、推理 vs [[vLLM]] 对比受 TPU 生态成熟度影响。

## 问题与动机

Apple 训练 LLM 的约束不止吞吐与 MFU。第一，**modularity**：数百名工程师需用最少代码试验 FFN→[[MoE]]、attention→RoPE、换 checkpointer/trainer loop 等，而不在 subtype 层级上连锁改代码。第二，**hardware-agnostic**：不能绑定单一硬件供应商，需同时覆盖 GPU、TPU、AWS Trainium，跑在 AWS/GCP/Azure 与自有机房。

既有大模型训练栈（Megatron-LM、DeepSpeed、TorchTitan、MaxText、Flax/Pax）普遍用 **subtyping + config flattening**：子类化父 layer、在 init 签名里传播新参数。论文用 DeepSpeed QwenV2→QwenV2-MoE 说明：表面 4 行替换 FFN，实际需 >200 LoC 改 subtype 链；生产环境数十 model variants 可放大到数千行。Megatron 深度优化 Nvidia GPU，Haiku/Flax/Pax/MaxText 偏 Google TPU，均难同时满足 Apple 的双约束。

AXLearn 的 claim：唯一严格坚持 **encapsulation** 的训练框架——任何模块（input pipeline、checkpointer、trainer loop）可替换而不抬升系统整体复杂度；基于 XLA/GSPMD 实现硬件无关并行；性能与 SOTA 可比。系统已开源（Apache 2.0），支撑数千模型、数百工程师、>10,000 并发实验。

## 关键观察 / 隐含假设

- 观察 1：ML 框架的 subtyping 使「局部换层」在类型层级上递归放大，扩展成本随模块数 N 线性甚至二次增长。 DeepSpeed MoE 需 subtype 每个 attention variant 及其祖先；Megatron RoPE 参数在 GPTModel→TransformerBlock→Attention 链上扁平传播。论文提出 LoC-Complexity：按 API 重参数化所需 asymptotic LoC 变化量化扩展性；AXLearn 对 RoPE/[[MoE]] 为 O(1)，DeepSpeed/TorchTitan/MaxText 等多为 O(NM)（N=模块数，M=特性变体数）。
  - **依赖假设**：LoC 变化能代理真实工程成本；config modifier 的 10 行 snippet 可泛化到任意 experiment config，无需改已有 module 接口。
  - **可能失效场景**：需改 module **内部实现**（非配置层）的新特性；第三方库不兼容 AXLearn `Module.Config` 接口时，封装边界被打破；复杂 conditional logic 难以用 `replace_config` 表达。

- **观察 2：编译器注入通信（GSPMD/XLA）可把并行策略从 layer 实现中剥离，使 layer 保持 sharding/remat 无关的纯逻辑。** 2021 年后 JAX/XLA 跨 GPU/TPU/Trainium 成熟，硬件商有动力优化 compiler，性能可「零 LoC」随生态提升。
  - **依赖假设**：XLA 在目标 backend 上能达到 hand-tuned kernel 可接受差距；mesh shape + sharding annotation + remat tag 足以表达生产级优化。
  - **可能失效场景**：新硬件（Trainium2）compiler 不成熟时需大量 custom kernel（FlashAttention 每 backend 一套）；PyTorch 在 H100 上 finer-grained scheduling 仍优于 XLA（Table 3 Megatron > AXLearn on H100）。

- 观察 3：JAX 函数式约束与 imperative 式 NN 编程冲突，若不抽象 state 管理，modularity 会在「手动传参/收集 summary」处崩塌。 AXLearn 用 InvocationContext 在 module 调用栈上透明管理 PRNG、参数、summary，使 layer 实现可保持 PyTorch 风格 imperative，同时满足 `jit`/`grad`。
  - **依赖假设**：Context 单向引用 module（module 不持有 context），足以集成 optax 等第三方库与 custom vjp。
  - **可能失效场景**：极深嵌套或跨 graph 边界的 state 共享（tied weights 以外）可能仍需显式穿透；debug 时隐式 context stack 增加认知负担。

- **观察 4：层次化 config tree + Python 原生 config modifier，比 TorchTitan/DeepSpeed 的 monolithic flat config 更易做跨实验批量重参数化。** 同一 10 行 `replace_config` 用于 1000+ RoPE/[[MoE]] 实验；TorchTitan 每个 model 需改 ModelArgs + Attention 实现，估计 240–400 LoC（Appendix B）。
  - **依赖假设**：研究员主要改 config 而非写新 layer；golden configuration test 能捕获 config 漂移。
  - **可能失效场景**：需要 fork-and-modify 整个 model 定义的新架构（MaxText 式路径）时，组合优势减弱；config tree 过深时 discoverability 变差。

- **观察 5：模块化训练栈可低成本复用为推理引擎——attention/KV cache 封装使 continuous batching、disaggregated prefill-decode、paged KV 以 drop-in 配置接入。** TPU 上 Llama2-7B/70B 推理吞吐达 [[vLLM]] 的 2.8×/1.6×。
  - **依赖假设**：训练侧 sharding/remat 配置与 decode 优化正交；TPU 上 vLLM 仍实验性。
  - **可能失效场景**：GPU 推理、生产级 serving 特性（多租户、KV 传输、spec decode 生态）未作为主实验；推理优势可能无法迁移到 [[vLLM]]/[[SGLang]] 成熟栈。

- **隐含假设：Apple 内部「20 model variants × 10 attention variants」生产设定可代表业界扩展成本量级。**
  - **证据强度**：中。LoC 估计有 Appendix B 逐项 rationale，但具体内部 codebase 规模不可披露；对比的是开源 sample + 保守外推，非第三方独立审计。

## 核心方法

**双组件架构**（Figure 2）：
1. **AXLearn Composer**：用户用 layer library 写 hierarchical training config → 物化完整 JAX program（选 mesh shape、sharding annotation、XLA autotune、backend-specific [[Flash-Attention]] kernel、remat 策略）→ 交 XLA 编译。
2. **AXLearn Runtime**：在 Kubernetes 等上编排 accelerator program；监控、异步 checkpoint（S3/GCS）、fault tolerance。

**Modular configuration**：
- 每层 `Module.Config` 封装子层 config，父层不扁平子层超参；父→子 propagate `input_dim` 等接口约定。
- **Config modifier**：递归遍历 config tree（`cfg.visit`），如 `replace_config(trainer_cfg, target=FeedForwardLayer, new_cfg=MoELayer...)` 全局替换 FFN→[[MoE]]。
- **Config-based parallelism**：FSDP、[[Pipeline-Parallelism]]、[[Expert-Parallelism]]、sequence parallelism、[[Tensor-Parallelism]] 原生嵌入 layer library，用户只配策略不改代码。
- **Memory**：remat 在 attention QKV/output 等 **tagged points** 选择性 save/offload/recompute；optimizer state offload 到 CPU（TPU v5e 大模型必需）。
- **Mesh rules**：`(accelerator_regex → [config modifiers])`，如 TPU v5e 用 slice 内 FSDP + 跨 slice DP + dot offload + INT8；H100 用 8-way TP + FSDP + save QKVO + FP8 delayed scaling（Appendix A）。
- **Custom kernels**：[[Flash-Attention]] 按 backend dispatch——GPU cuDNN/Pallas、Trainium AWS NKI、TPU SplashAttention Pallas；通过 mesh rule 作 drop-in attention 替换。
- **AOT compilation**：本地 CPU 即可分析 memory/FLOPS、捕获 OOM，减少大规模分布式试跑浪费。

**InvocationContext**：parent invoke child 时 push context（split PRNG、子 output collection）；return 时 pop 并汇总到 parent。Module 不持有 context 引用，支持 optax、custom vjp 等外部集成。

**Runtime 韧性**：异步 checkpoint + GC；watchdog 监测 step time/utilization；failure 时从健康 DP replica restore + broadcast；persistent compilation cache；**slice-level hot-swap**（over-provision spare replicas，4 min 完成 swap，9 min checkpoint restore，总计约 21 min downtime，Figure 5）。

**训练-推理统一**：KV cache 封装在 attention layer 内，可接 [[Continuous-Batching]]、[[Disaggregation|disaggregated prefill-decode]]、[[PagedAttention]] 式 paged KV，无需重写 model。

## 设计取舍

- **严格封装 + 组合 vs 峰值性能**：XLA 编译路径牺牲 H100 上相对 Megatron/PyTorch 的调度细粒度（Table 3 Megatron H100 最快），换取 GPU/TPU/Trainium 单 codebase——Apple 明确接受该 trade-off。
- **Config 驱动优化 vs 手写并行 plan**：TorchTitan 需 per-model parallel plan traverse 架构；AXLearn 把 sharding/remat/量化表达为 config + mesh rule，降低工程师负担，但 expert 需理解 XLA sharding 语义才能调优。
- **LoC-Complexity 度量 vs 运行时复杂度**：O(1) 指 **改已有接口** 的 LoC，不包括新 layer（MoE/RoPE）本身实现与 per-backend kernel 维护；Trainium2 等需持续投入 kernel 专家。
- **Compiler-first vs 资源受限开发**：AOT + golden config test 缓解 TPU 容量紧张与 config 回归，但增加 CI 与 config diff review 流程成本。
- **边界条件**：在 **多硬件、多架构、频繁试验新 layer/训练技巧** 的研发环境最优雅；单一 GPU 栈、固定模型、追求最后一档 MFU 的团队可能更愿用 Megatron 手写优化。

## 实验与结果

**LoC 分析**（Table 2）：AXLearn RoPE/[[MoE]] 对已有接口 **0 LoC**（10 行 modifier 在 config 层）；Megatron MoE O(N)、Praxis MoE O(M)；DeepSpeed/TorchTitan/MaxText RoPE 估计 120–600+ LoC（20 variants 设定）。

**训练性能**（Table 3，global batch 1024）：
- 模型：Llama2 7B/70B dense、Qwen-3 30B-A3B [[MoE]]。
- 硬件：256/512 H100、512 B200、TPU v5p-512/1024、1024 Trainium2。
- TPU：AXLearn SOTA，MaxText 略慢（remat 选择）；PyTorch XLA FSDP OOM 无法运行。
- H100：AXLearn > PyTorch FSDP（细粒度 remat、RMSNorm/RoPE 等 memory-bound op）；Megatron > AXLearn（PyTorch scheduling）。
- Trainium2：仅 AXLearn（首批大规模支持之一）。

**弱扩展**（Figure 4）：70B、4096 ctx，256→4096 chip MFU **63.0%→52.4%**；150B、8192 ctx，8192→32768 chip **40.6%→37.6%**（150B 受 global batch 收敛限制）。

**推理**（Table 4，ShareGPT，TPU）：Llama2-7B TTFT **500×**、TPOT **6×** 快于 [[vLLM]]，吞吐 **2.8×**；70B 吞吐 **1.6×**。论文注明 vLLM TPU 支持仍实验性。

**故障恢复**：32,768 TPU 生产 job，hot-swap 4 min + restore 9 min，总约 21 min 训练损失（含 checkpoint 间隔内进度）。

**生产规模**：>10,000 并发实验、数百工程师、十亿级用户产品功能；GitHub `apple/axlearn`。

## Critical Analysis

### 论证链条

主链条：**痛点**——subtype 导致特性集成 LoC 随 N/M 爆炸 + 单硬件绑定 → **设计**——严格封装 Module.Config + config modifier + XLA/GSPMD 硬件抽象 + InvocationContext 保 imperative UX → **度量**——LoC-Complexity O(1) vs 竞品 O(N)~O(NM) → **验证**——多硬件训练性能可比 SOTA + 弱扩展近线性 + 生产采纳规模。

链条在 **「研发敏捷性」** 上最闭合：10 行 MoE snippet × 1000 实验是 concrete evidence。在 **「绝对训练性能冠军」** 上故意不闭合：H100 上承认 Megatron 更快，定位是 hardware-agnostic 的可接受 trade-off。

推理 vs [[vLLM]] 链条较弱：训练框架非 inference-first，对比对象 TPU 生态不成熟，数字（500× TTFT）易误导为通用 serving 优势。

### 假设压力测试

**Workload**：LoC 分析假设「换 FFN/加 RoPE」类 re-parameterization 是高频操作；若团队主攻单一 Llama 克隆、极少改架构，modularity 收益难抵消 JAX/XLA 学习曲线。

**硬件**：Mesh rule + custom kernel 需 per-backend 专家；新加速器上线时 compiler gap 由 Apple 团队填，外部用户能否复现 Trainium2 级支持存疑。XLA 在 B200/H100 上相对 PyTorch 的调度差距可能随代际变化。

**规模**：弱扩展 MFU 下降尚可接受，但 150B 需缩小 global batch，暗示 **收敛约束** 与 **系统扩展** 耦合；论文未展开 multi-trillion 或异构集群。

**组织**：生产数据（实验数、用户规模）来自 Apple 内部，外部无法独立验证 adoption 与 goodput；开源代码≠开源 production config 与 mesh rule 全集。

### 实验可信度

**可信处**：同硬件同集群对比（Table 3 分组说明）；覆盖 dense + [[MoE]]、四种 backend；弱扩展用真实 70B/150B 生产模型；failure recovery 用 32K TPU 真实 trace；LoC 附录逐项拆解竞品。

**不足**：
- LoC 估计基于假设性 20×10 variants，非 measured diff on public repo。
- Trainium2/B200 无开源 baseline 对比。
- 推理仅 TPU、两模型、vLLM 弱基线；无 GPU 推理、无 tail latency、无 multi-tenant。
- Megatron 胜 H100 的 gap 未 ablate「若 AXLearn 放弃 XLA 用手写 CUDA 能否追上」。
- PyTorch XLA FSDP OOM 作为 TPU baseline 失败，衬托 AXLearn 但略 asymmetric。

### 系统性缺陷

- **运维复杂度**：mesh rules、remat tags、multi-cloud checkpoint 使 **config 空间** 本身变大；golden config test 缓解但需 discipline，论文未量化 misconfig 率。
- **尾延迟与多租户**：训练 job 级优化，未讨论共享集群 queueing、优先级抢占、资源隔离。
- **第三方生态**：JAX 库、checkpoint 格式、K8s operator 与 PyTorch 栈相比社区更小；迁移成本论文轻描淡写。
- **Kernel 债务**：每 backend FlashAttention/FP8/INT8 需持续维护；hardware-agnostic 不等于 **maintenance-agnostic**。
- **推理生产化**：论文未讨论 serving 的 KV 传输、[[Disaggregation]] 部署、与 [[SGLang]]/[[vLLM]] feature parity。

## 局限与 Future Work

- **局限 1**：H100 上训练 MFU 仍低于 Megatron；hardware-agnostic 有明确性能 ceiling。
- **局限 2**：LoC-Complexity 不计新 layer 实现与 kernel 工程；O(1) 是接口变更意义，非总交付成本。
- **局限 3**：推理对比依赖 immature vLLM TPU；不宜外推为通用 serving SOTA。
- **局限 4**：生产规模与故障数据不可复现；外部用户缺少 Apple 级 multi-cloud 运维配套。
- **局限 5**：论文承认 public cloud 不透明故障（ICI、silent corruption、FS throttling）需与云厂商协作，通用用户难复制 resilience 栈。

- **Future work 1**：量化「config modifier 覆盖率」——哪些新特性无法用 10 行 snippet 集成，需破坏封装？
- **Future work 2**：在 H100/B200 上 ablate XLA vs partial hand-schedule，测定 hardware-agnostic tax 的精确 MFU 百分点。
- **Future work 3**：GPU 推理上与 [[vLLM]]/[[SGLang]] 公平对比（含 prefix cache、spec decode、[[Disaggregation]]）。
- **Future work 4**：开源 community 独立复现 mesh rules + Trainium2 scaling，验证「首批支持」是否可持续 without Apple 内核团队。
- **Future work 5**：论文隐含方向——golden config + AOT 能否形式化为 ML 系统的「类型检查」，降低大规模 config 回归风险。

## 相关

- **相关概念**：[[MoE]]、[[Flash-Attention]]、[[Expert-Parallelism]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Quantization]]、[[Disaggregation]]
- **同类系统**：Megatron-LM、DeepSpeed、TorchTitan、MaxText、Flax、Pax/Praxis、[[vLLM]]、[[SGLang]]
- **同会议**：[[MLSys-2026]]
