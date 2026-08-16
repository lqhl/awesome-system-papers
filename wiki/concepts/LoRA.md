---
type: concept
aliases: [LoRA, lora, Low-Rank Adaptation, low-rank adaptation, LoRA adapter]
parent: "[[LLM-Inference]]"
introduced_by: LoRA-ICLR22
last_updated: 2026-08-14
tags: [fine-tuning, peft, llm-training, adapter-serving]
---

# 低秩适配（LoRA）

> LoRA 冻结原模型权重，只训练一个低秩增量。它显著减少可训练参数、优化器状态和 checkpoint 大小，但不会自动消除前向/反向激活，也不会自动让多 adapter 服务没有开销。

## 基本做法

对一个线性层 (W_0\in\mathbb{R}^{d_{out}\times d_{in}})，LoRA 不直接更新 (W_0)，而是学习两个小矩阵：

\[
y = W_0x + sBAx,
\]

其中 (A\in\mathbb{R}^{r\times d_{in}})、(B\in\mathbb{R}^{d_{out}\times r})，(r) 是 rank，(s) 常由缩放系数和 rank 决定。只要 (r) 远小于输入、输出维度，可训练参数就从 (d_{out}d_{in}) 降到 (r(d_{in}+d_{out}))。实际系统可以只给注意力投影加 LoRA，也可以覆盖 MLP 或所有 linear 层；rank、初始化和作用位置都是配置，不存在对所有任务通用的固定值。

“冻结 base model”带来三种不同收益：

- **训练**：不用为原权重保存梯度和完整 optimizer state，adapter checkpoint 也较小。
- **分发**：多个任务或用户可以共享同一 base，只传输各自的 adapter。
- **服务**：单一 adapter 可以在部署前合并进 base；多租户则保留独立 adapter，按请求选择或混合。

最后一点最容易被说得过头。只有在**单一、静态 adapter** 且权重格式允许时，合并后才可接近普通 dense layer 的执行路径。多租户服务不能把许多 adapter 同时永久合进同一份 base；量化 base 的 merge/unmerge 还可能需要重打包或重新量化。因此“LoRA 推理零开销”不是一般结论。

## LoRA 省了什么，没有省什么

### 省可训练状态，不一定省激活

LoRA 大幅减少 trainable parameter、gradient 和 optimizer state，但前向仍要经过完整 base model，反向也必须沿计算图把梯度传到插入的低秩矩阵。序列很长时，保存中间 activation 仍可能是主导成本。

[[Jenga-ATC25]] 给出很直接的反例：Llama2-7B、4K 序列下，LoRA activation footprint 约 39.2 GB，LongLoRA 约 41.3 GB；LoRA 解决的是参数状态，不是 token 维度激活。Jenga 用上下文 token 稀疏把该设置降到 31.3 GB，但这项收益来自 token 剔除，不来自 LoRA。

[[AssyLLM-ATC25]] 在内存受限联邦环境中也发现，LoRA/QLoRA/FedAdapter 仍需要 15 GB 以上，许多 4–16 GB 客户端无法参加，原因同样主要是 forward activation。其 block 组装路线比全量微调降低 92% 峰值内存、比 PEFT 基线再低 63.6%；这些数字证明 LoRA 的边界，不应解释成 LoRA 自身的收益。

### 省 checkpoint，不等于训练免费

[[mTuner-ATC25]] 利用“base 权重冻结”这一特性，把权重、activation 和 checkpoint 做成弹性 tensor，运行时用空闲显存减少 PCIe/NVLink 搬运。在 Llama 2 7B–70B 的 LoRA 工作负载上，它相对所列系统最高提高 PCIe 51.2%、NVLink 24.8% 的吞吐，平均为 28.3%/14.5%。结果依赖 frozen base；换成全参数微调或大比例可训练参数后，缓存机会和收益都会下降。

[[LLMStation-ATC25]] 则把 LoRA PEFT 与同一 base 的在线服务放到同组 GPU。它利用 decode 常偏内存带宽受限、PEFT forward/backward 更偏计算受限的互补性，把 backward 改成可暂停的细粒度 tasklet，并共享一份 base。满足论文设置的 P99 SLO 时，PEFT 吞吐相对三类基线提高 1.38–14.77 倍；若 serving 本身已经违反 SLO，其 uniform-adapter 实验中所有方案可用于 PEFT 的吞吐都降为 0。LoRA 创造了共享条件，却没有创造无限的空闲资源。

## 多 adapter 服务真正难在哪里

多租户服务通常把 base 常驻 GPU，把大量 adapter 放在 host memory 或存储中；每个请求可选择不同 rank、不同 adapter，甚至加权混合多个 adapter。系统要同时处理加载、批处理、kernel、缓存和公平性。

[[Toppings-ATC25]] 对这些成本给出了最完整的测量：

- 在 512 个 adapter、rank 64、RPS 9 的配置中，一个请求的 decode 中位数被新请求打断 25 次，累计 interruption 占服务时间 29%。
- rank 64 的单 adapter 约 100 MiB；把 200 多个 adapter 常驻 GPU 才能达到约 50% cache hit，会挤占 20 GiB 以上 KV 空间。
- BGMV 会按 batch 内最大 rank padding，MBGMV 的成本随 rank 之和变化；同 batch size 的不同 rank 组合可让 decode latency 相差 28%。

Toppings 在 CPU 上提前计算 LoRA prefill，同时流水加载 adapter，并按 rank-aware 模型调度。在其实验中，相对 S-LoRA/dLoRA 的平均服务延迟最高降低 1.7 倍，SLO 达标率为 99%，相对“所有 adapter 已缓存”的不可扩展理想基线只多 7% 开销。代价是 CPU 利用率从 4% 升到 46%、每请求平均增加 27 ms CPU LoRA 计算，而且结果主要覆盖 attention 投影 LoRA；adapter 扩到 MLP 或 CPU 已繁忙时，成本模型要重做。

[[CLONE-ATC25]] 展示另一种服务形态：边缘设备预先训练多组 rank 8 的 LoRA，再用 prompt embedding 做 soft [[MoE]] 路由和融合。多个 adapter 提供任务覆盖，但会增加存储、路由和融合成本；论文的整体 11.92 倍最高加速还包含结构化剪枝、DVFS 与模拟硬件，不能归因给 LoRA。

[[Katz-ATC25]] 研究 text-to-image 服务。其生产 trace 中超过 95% 请求至少使用一个 LoRA，系统允许 base model 先执行有限的无 LoRA denoising steps，同时异步加载 adapter，并用 in-place merge 降低 patch 成本。这里允许延迟加载的前提是扩散早期步骤主要决定语义布局；不能把同一技巧直接搬到 token-by-token LLM，因为漏用 adapter 的 token 已经改变输出历史。

## 联邦学习把低秩矩阵变成通信对象

不同客户端可选择不同 rank，于是问题从“少传参数”变成“怎样数学正确地聚合不同低秩更新”。直接平均 (A) 和 (B) 会产生不属于各客户端更新之和的交叉项；先恢复完整 ΔW 再做 SVD 又会在服务器物化大矩阵。

[[FLoRIST-MLSys26]] 把各客户端 adapter 先堆叠，再在较小的中间空间做等价 SVD，并按奇异值能量阈值选择统一 global rank。其 8-client 实验中，一些 q_proj 层在第 8–10 个奇异分量后快速衰减，尽管最大 client rank 是 64；LLaMA-7B 的服务器分解估算为 6.18B FLOPs，相比 FlexLoRA 的 2209.39B 约低 350 倍。通信效率数字基于“下载 rank 总量”，没有计入序列化、协议和很多客户端时仍线性增长的 upload。

[[PLayer-FL-MLSys26]] 和 [[ProToken-MLSys26]] 只把 LoRA 作为未来边界：前者的层选择主要在 CNN/MLP 上验证，尚未说明 LoRA-only 联邦应按层还是 rank 定义敏感度；后者的 provenance 方法依赖 FedAvg 线性分解，异构 adapter、非线性聚合和 client dropout 下尚未验证。它们不是 LoRA 聚合算法的实验证据。

## LoRA 作为训练载体

- [[CDLM-MLSys26]] 用 LoRA 把 diffusion language model 微调成 block-causal student，4×A100 上训练 8–16 小时；其 3.6–14.5 倍延迟下降来自架构和并行 finalize，多数不能归因于低秩更新。
- [[RLVR-LowData-MLSys26]] 用 Qwen3-4B、全 linear 层 rank 64 LoRA 和 GRPO 研究低数据 RLVR；“mixed difficulty 比纯 easy 最多省 5 倍样本”只在这套单模型、单 seed、程序生成任务中成立，LoRA 是固定实验载体。
- [[CacheSlide-FAST26]] 用 LoRA adapter 让模型支持其位置编码方案。论文 3.11–4.3 倍延迟下降和 3.5–5.8 倍吞吐提升来自 KV 重用、校正注意力和 I/O pipeline；baseline 没用同一位置编码，LoRA 适配本身还引入公平性边界。
- [[ZK-APEX-MLSys26]] 用 LoRA 表示小幅个性化更新，借此论证 provider 在 base 权重上计算的 mask 可近似用于 client 模型。OPT-125M 实验只恢复约 70% 被 mask 损失的精度，明显低于 ViT 的约 99%；“低秩更新小”是协议假设，不是对任意大 adapter 的保证。

## 与其他适配方式的关系

### LoRA 与 KV prefix

[[Cartridges-ICLR26]] 把每个语料库蒸馏成可加载的 trainable KV prefix。在约 0.6 GB 的 memory-matched 对比中，KV-prefix 在 MTOB 高 4.5 chrF；adapter 从 0.15 增到 1.06 GB 时，LoRA 的 MMLU 从 54.7 降到 45.3，KV-prefix 只从 54.7 降到 54.3。这个结果支持“语料表示放进 KV 可能比改权重更稳”，但只覆盖该模型、数据和蒸馏流程；它不是所有任务上 KV prefix 胜过 LoRA 的定理。

[[PASTA-ICLR24]] 选择在推理时重加权少数 attention heads，不改模型权重，因此省去 LoRA 训练，却要求用户准确标出重点 span，并要求 runtime 暴露 attention score。它说明“无需微调”会把成本转移到推理接口和输入标注，而不是自动更简单。

### LoRA 与量化、稀疏和编译

QLoRA 的基本思想是把 frozen base 以低 bit 保存/计算，同时训练较高精度的 LoRA；它主要降低训练时 base footprint。动态 adapter 合并到量化权重可能需要反量化或重新打包，不能假设普通 FP16 merge 路径仍成立。

[[MixLLM-MLSys26]] 和 [[OptiKit-MLSys26]] 都把 LoRA 后的再量化或 calibration 作为未覆盖边界；二者的量化 headline 没有在动态 adapter 服务上验证。[[AttributionSparseActivation-MLSys26]] 说运行时稀疏激活与 LoRA 正交，但没有报告联合配置，不能直接相乘两项加速。[[AccelOpt-MLSys26]] 的 kernel 集含 LoRA 算子，用来评测自动 kernel 优化，并不研究 adapter 训练或服务策略。

[[MPK-OSDI26]] 的 persistent mega-kernel 主实验是固定离线 batch，没有动态 LoRA。不同请求使用不同 adapter 时，权重地址、task graph、batch shape、缓存和抢占都变化，是其静态 specialization 的未验证边界。[[MSA-arXiv26]] 仅在相关概念中列出 LoRA，没有 LoRA 消融；其 100M-token 结果来自可训练稀疏注意力和 KV 压缩。

[[TimesFM-Fin-arXiv24]] 采用全参数 continual pre-training 适配金融数据，只把 LoRA/frozen backbone 列为待比较方向。其交易指标不能证明全量更新优于 LoRA，因为论文没有在相同数据、算力与遗忘评测下运行 LoRA 对照。

## 设计选择

| 选择 | 适合的场景 | 主要代价 | 代表论文 |
|---|---|---|---|
| 静态 merge | 单任务、adapter 已确定 | 更新 adapter 需重新 merge；量化格式可能重打包 | 基础 LoRA 部署 |
| 动态按请求执行 | 多租户、adapter 多且常变 | adapter load、异构 rank batching、KV 竞争 | [[Toppings-ATC25]] |
| 多 adapter 混合 | 一个请求跨任务或风格 | 路由和多个低秩乘法，语义可能相互干扰 | [[CLONE-ATC25]] |
| LoRA 与在线服务共置训练 | 同 base、服务负载有空隙 | 必须保护 TTFT/TPOT，训练可被频繁暂停 | [[LLMStation-ATC25]] |
| 冻结权重的弹性内存 | 单机多 GPU PEFT | full fine-tuning 时优势减弱 | [[mTuner-ATC25]] |
| 异构 rank 联邦聚合 | 客户端能力不同 | SVD、通信与全局 rank 选择 | [[FLoRIST-MLSys26]] |
| KV-prefix 代替权重 adapter | 同一长语料反复查询 | 需要专门蒸馏与 KV 生命周期 | [[Cartridges-ICLR26]] |

## 评价 LoRA 系统时应看什么

1. 分开报告 trainable parameters、optimizer state、activation、base weight、KV 和 adapter cache；只报参数比例会掩盖内存峰值。
2. 说明 LoRA 插在哪些层、rank 分布、精度、量化格式，以及是静态 merge 还是 per-request 动态执行。
3. 多租户服务要报告 adapter 数、流行度、cache hit、加载链路、rank 混合、TTFT/TPOT P99 和 KV 容量损失。
4. 训练系统要报告真实收敛/任务质量、暂停恢复和 checkpoint correctness，而不只是 samples/s。
5. 联邦方案要分别核算 upload、download、聚合 FLOPs、服务器峰值内存和异构 rank 的数学误差。
6. 与量化、稀疏、编译或 KV 优化组合时，应给联合实验；“正交”只表示机制可能不冲突，不等于收益可相乘。

## 仍未解决的问题

- 在数万 adapter、连续到达和异构 rank 下联合优化 GPU/CPU/存储缓存、batch 和公平性。
- 给量化 base 上的 adapter merge、热更新与版本回滚建立稳定格式，避免每次重新量化整层。
- 长上下文 PEFT 中同时控制 activation、optimizer、通信和 recomputation，而不只压缩 trainable parameters。
- 在多 adapter 组合中检测能力冲突、安全对齐退化和跨租户信息泄漏。
- 对 LoRA、KV prefix、prompt steering 和全量微调建立按任务、更新频率和服务成本划分的可复现实用边界。
