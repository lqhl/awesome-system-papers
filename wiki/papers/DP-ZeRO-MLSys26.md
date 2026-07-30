---
type: paper
name: DP-ZeRO
full_title: "ZERO REDUNDANCY DISTRIBUTED LEARNING WITH DIFFERENTIAL PRIVACY"
authors: [Zhiqi Bu, Ruixuan Liu, Justin Chiu, Sheng Zha, George Karypis]
venue: MLSys
year: 2026
tags: [differential-privacy, zero, distributed-training, large-models]
source_pdf: "[[da4fb5c6e93e74d3df8527599fa62642.pdf]]"
source_md: "[[da4fb5c6e93e74d3df8527599fa62642]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# DP-ZeRO：具有差异隐私的零冗余分布式学习（MLSys 2026）

> **原题**：ZERO REDUNDANCY DISTRIBUTED LEARNING WITH DIFFERENTIAL PRIVACY

> **一句话总结**：DP-ZeRO 将 [[Differential-Privacy]] clipping/noise 与 ZeRO1/2/3、FSDP 和 mixed precision 组合；在 A100 实验中，ViT-Gigantic 的 DP/standard throughput ratio 随 ZeRO1→ZeRO3 从 81–83% 提升到 94–95%，并在最多 256 GPUs 上运行 100B trainable-parameter efficiency benchmark（§4.3–4.4，Fig. 7–8）。

## 问题与动机

大模型 + [[Differential-Privacy]]（per-sample clip + noise）在单卡上 BK/GhostClip 已接近非私有开销（ViT-Large **1.08×** 时间），但 **DDP** 无法装下超大模型且缓存 per-sample gradient 贵；**PipeP** + DP 有 pipeline bubble。业界需要与 [[DeepSpeed]]/[[FSDP]] 同级的 DP 分布式方案以训练十亿级可训参数（GPT2-XL、ViT-10B、GPT-100B 等）。

## 关键观察 / 隐含假设

- **观察 1：DP 的数学梯度分组（all-layer vs layer-wise clip）与 ZeRO 的物理分片可分离组合，细粒度 clip 更省内存。**
  - **依赖假设**：各 group clip 的 noise 与 accounting 仍正确。
  - **可能失效场景**：极端 layer-wise 分组与 ZeRO3 通信模式交互未充分边界测试。

- **观察 2：混合精度 DP 的 loss scaling 与 master weight 更新需专门处理，否则 ZeRO 的 fp16 grad + fp32 state 路径破坏 DP 正确性。**
  - **依赖假设**：修复后数值稳定与 non-DP ZeRO 等价。
  - **可能失效场景**：更大模型/更低 precision 数值漂移需额外验证。

- **观察 3：DP-ZeRO3 在最多 256 GPUs 上运行 7B–100B trainable-parameter benchmark；固定 26B 从 16 扩至 128 GPUs 时达到 standard ZeRO 大于 95% 的速度（§4.4，Fig. 8）。**
  - **依赖假设**：per-sample norm 计算用 mixed ghost norm 避免第二遍 backward。
  - **可能失效场景**：极大 micro-batch 时 clip 统计方差与 privacy budget 权衡仍由用户负责。

- **假设 1**：作者称可用一行代码接入 DeepSpeed/FSDP，但实验仅覆盖所测模型、operators 和 precision 路径。
  - **证据强度**：**中**——能力矩阵与实验支持兼容性，但不能证明任意架构。

## 核心方法

**DP-ZeRO**：在 ZeRO 三阶段 partition（optimizer state / grad / params）中组合 DP clip+noise；Book-Keeping 使用 mixed ghost norm 并保存 output gradients。Appendix A 描述两轮各约半复杂度的 backward，总复杂度接近一次标准完整 backward，而非真正单次 backward。

**Mixed-precision DP**：解决 loss scaling，使 fp16/bf16 训练通信减半。

**Scale**：系统效率实验扩展到大于 1B、最高 100B trainable parameters；这证明可运行性与效率，不证明 100B 私有训练的 convergence 或 utility（§4.4，Fig. 8）。

## 设计取舍

- **ZeRO3 vs ZeRO1/2**：更低内存更高通信；DP 噪声与分片顺序需小心。
- **PipeP+DP vs DP-ZeRO**：避开 bubble，但需 ZeRO 生态成熟。
- **Privacy vs accuracy**：更大模型更好 DP accuracy 但算力贵——论文不解决 budget 选择。
- **边界条件**：A100 40/80GB；ViT/GPT/ModelP efficiency workloads；除 Fig. 4 的 CIFAR100 数值实验外，多数系统实验按模型与输入维度运行，不声明真实 dataset 或 utility。

## 实验与结果

- **Throughput ratio**：ViT-Gigantic 的 DP/standard throughput ratio 从 ZeRO1 的 81–83% 提升到 ZeRO3 的 94–95%，FSDP 为 97–98%；GPT2-XL 的 ZeRO1/2 为 82–84%（§4.3，Fig. 7；A100-40GB，micro-batch 4，ViT-G 1.8B / GPT2-XL 1.5B，full/mixed precision）。
- **Mixed-precision memory**：mixed-precision DP 的单卡 model-state memory 为 full-precision standard baseline 的 46–74%；例如 ViT-ZeRO2 从约 31GB 降至约 14.5GB（46%）（§4.3，Fig. 7；结果依模型、stage 与 optimizer 而异）。
- **Scale-out**：固定 26B 从 16 扩至 128 GPUs 时达到 standard ZeRO 大于 95% 的速度；固定 256 GPUs 时运行 7B/13B/26B/100B，DP 与 non-DP TFLOPS 曲线接近（§4.4，Fig. 8；A100-80GB，seq 2048，activation checkpointing，ModelP，MiCS/ZeRO3，bf16，AdamW，layer-wise clipping）。
- **Optimizer + PEFT**：ViT-5B、micro-batch 1 下，从 Adam/full tuning 的约 31 samples/s 提升至 SGD+PEFT 的约 72 samples/s，单卡 CPU/GPU memory 从约 34GB 降至约 11GB（§4.2，Fig. 6；两项变化合并，不能全归因于 PEFT）。
- **Loss scaling failure**：ViT-Large/CIFAR100 的 DP test accuracy 随 loss scale 从 1 提高到 100/1000，由约 84% 降至约 18%/接近 1%，standard accuracy 约 92% 不变；论文因此主张 DP mixed precision 不使用 standard loss scaling，并优先 bf16（§3.4，Fig. 4，Table 3；5 epochs，ε=2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 更高 ZeRO stage 将 DP throughput 拉近 standard ZeRO | §4.3, Fig. 7 | A100-40GB；ViT-G 1.8B / GPT2-XL 1.5B；micro-batch 4 | strong |
| Mixed precision 将单卡 model-state memory 降至 full-precision baseline 的 46–74% | §4.3, Fig. 7 | ViT/GPT；ZeRO1/2/3 与 FSDP；特定 optimizer | strong |
| DP-ZeRO3 扩展到 100B trainable parameters 和 256 GPUs | §4.4, Fig. 8 | A100-80GB；ModelP；seq 2048；bf16；只验证效率/可运行性 | strong |
| Low-memory optimizer 与 PEFT 的组合提高吞吐并降低内存 | §4.2, Fig. 6 | ViT-5B；micro-batch 1；Adam/full vs SGD+PEFT 联合变化 | strong |
| Standard loss scaling 会破坏所测 DP mixed-precision training | §3.4, Fig. 4, Table 3 | ViT-Large；CIFAR100；5 epochs；ε=2；单一任务 | medium |

## 批判性分析

### 论证链条

DP 单卡已高效 → 瓶颈在分布式分片 → 将 BK 嵌入 ZeRO 各 stage → 扩展至 100B trainable parameters，逻辑清晰。论文只报告 100B efficiency benchmark，没有下游 utility 或相对 non-DP accuracy。

### 假设压力测试

LLM generative DP（大词汇 softmax clip）成本仍高；ZeRO+EP+DP 未谈。多租户 GPU 上 side-channel 与 DP 正交。

### 实验可信度

系统论文+规模里程碑；baseline 表格完整。缺：与最新 Opacus/FSDP-DP 公开栈长期维护对比。

### 系统性缺陷

论文未讨论 privacy accounting 自动化运维、checkpoint 泄露、failure recovery 对 DP 保证影响。

## 局限与后续工作

- **局限 1**：极大 generative 模型 DP utility 与 ε 权衡仍难。
- **局限 2**：与 MoE/EP 组合复杂度未展开。
- **Future work 1**：DP+[[FSDP]]2+[[Context-Parallel]] 全栈 profiling。
- **Future work 2**：生产级 privacy dashboard  tied to DP-ZeRO steps。

## 相关

- **相关概念**：[[Differential-Privacy]]、[[ZeRO]]、[[FSDP]]、[[GhostClip]]
- **同类系统**：Opacus、TensorFlow Privacy
- **同会议**：[[MLSys-2026]]
