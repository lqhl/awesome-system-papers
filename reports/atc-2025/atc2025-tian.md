# CLONE: Customizing LLMs for Efficient Latency-Aware Inference at the Edge

**作者**：Chunlin Tian, Xinpeng Qin, Kahou Tam, Li Li†, Zijian Wang, Yuanzhe Zhao, Minglei Zhang, Chengzhong Xu（University of Macau）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/tian
**源文件**：[[atc2025-tian.pdf]]

---

## 一、背景

LLM 正从云端走向边缘设备（手机、机器人、IoT），以实现低延迟响应和数据隐私保护。然而，边缘设备面临严格的 SWaP（Space, Weight, and Power）约束：Llama-7B 仅推理就需要 ~14GB 内存（FP16），而典型边缘设备 RAM 仅 4-12GB；单次推理的算力需求是 VGG-19 的 360 倍，能耗是 ResNet-50 的 400 倍。现有的模型压缩（量化、剪枝、架构搜索）和系统优化（DVFS、co-processor offload）各自独立工作，无法协同平衡精度、延迟和能效三个目标。

---

## 二、要解决的问题

1. **模型层面**：如何根据特定边缘硬件的资源 profile，自动确定最优剪枝配置，在满足内存约束的同时最大化生成能力？传统方法依赖手工设计的启发式离散搜索空间，难以找到全局最优。

2. **运行时任务适配**：边缘场景下用户请求是随机的、混合任务的，输入/输出长度服从长尾分布。单一 LoRA adapter 无法同时适配多种任务类型。

3. **系统层面能效优化**：现有 DVFS 策略针对 CNN/RNN 设计，将整个网络视为黑盒做 workload 级调频。LLM 的自回归推理特性（prefill vs decode 异构、逐 token 生成）和层间异构性未被利用。

4. **软硬件协同**：模型压缩和系统调频各自优化容易导致能效浪费或精度下降，缺乏端到端的协同设计。

---

## 三、洞察与设计

**关键洞察**：LLM 的 decoder 层虽然结构同质，但对生成能力、推理延迟和能耗的贡献是高度异构的——前端层负责特征提取、后端层负责输出生成，它们对模型性能的影响远大于中间层。这种层间异构性意味着可以在层粒度上分别做剪枝配置和 DVFS 调频，而非将模型视为黑盒统一处理。

基于这一洞察，CLONE 采用离线 + 在线两阶段层级架构：

### 离线：设备自适应模型裁剪

将 LLM 剪枝重新定义为**生成式任务**：
- **数据收集**：通过 exploration-exploitation 策略收集 (pruning ratio, score) 数据对，其中 score 综合考虑 PPL、延迟和能耗
- **连续空间建模**：用 encoder-evaluator-decoder（单层 LSTM）将离散剪枝空间映射为连续表示空间
- **梯度优化**：在连续空间中用梯度下降搜索最优剪枝配置，再由 decoder 解码为具体的逐层剪枝比例
- **LoRA 适配**：对裁剪后模型用多个 plug-and-play LoRA adapter 分别微调，支持不同下游任务

### 在线：延迟感知推理

- **Request-wise MoE Router**：用 sentence embedding（BGE）计算用户 prompt 与各 LoRA 的余弦相似度，通过 softmax 加权融合多个 LoRA adapter，无需额外可训练参数
- **Learning-based DVFS Controller**：基于 DQN 的两层 MLP（<1K 参数），在每个 token 的 layer boundary 动态调节 V_DD 和 F_req，状态包含 co-running app 负载、TTFT/TPOT 约束，奖励函数编码能效目标

### 硬件加速器

28nm ASIC（核心面积 1.588mm²），包含：
- **LoRA Processing Unit (LPU)**：支持 LoRA adapter 热切换，使用 eNVM 缓存避免 DRAM 重加载
- **Special Function Unit (SFU)**：集成快速 LDO 稳压器和 ADPLL，实现连续细粒度 DVFS 调节

---

## 四、实现细节

- **裁剪框架**：Encoder/Decoder 各用单层 LSTM（hidden=64），Evaluator 用双层前馈网络（hidden=200），embedding size=32。训练 batch size=1024，lr=0.001，选 top-25 剪枝记录作为梯度优化起点，用 beam search 迭代生成最优配置
- **LoRA 配置**：rank r=8，scaling α=16，3 轮训练。每个下游任务一个 LoRA adapter
- **MoE Router**：使用 BGE sentence embedding 模型计算 prompt 与 LoRA 的相似度。无额外可训练参数，仅一次 softmax 计算
- **DVFS Controller**：两层 MLP（<1K 参数）。MoE 路由和 DVFS 决策与 prefill 阶段并行执行（<10ms vs prefill >100ms），token t+1 的 DVFS 决策在 token t 解码时生成，不在关键路径上
- **硬件集成**：CLONE 加速器通过 PCIe 接口连接 Jetson 平台，由 host CPU 做顶层数据流控制

---

## 五、实验结果

**实验平台**：NVIDIA Jetson Orin NX（16GB, 100 TOPS）和 Jetson Orin Nano（8GB, 40 TOPS）

**模型**：Llama-7B, Llama2-7B, Llama2-13B, Vicuna-7B

**数据集**：WikiText2, PTB（PPL 评估），Flan v2（46 tasks, 10 domains），BBH, MMLU, Commonsense

### 生成能力（PPL）

CLONE 在 WikiText2 上生成能力是 Random pruning 的 5.1 倍，在 PTB 上是 3.4 倍，显著优于 LLMPruner、ShortGPT、SliceGPT 等基线。

### 下游任务准确率（Llama-7B, Orin NX）

| Benchmark | vs Random | vs 次优基线 |
|---|---|---|
| BBH (zero-shot) | +15.1% | +2.37% |
| MMLU (3-shot) | +6.0% | +2.96% |
| Commonsense (zero-shot) | +10.1% | +6.1% |

### 系统效率

| 方法 | 能耗 NX (Wh) | 能耗 Nano (Wh) | 延迟 NX (s) | 延迟 Nano (s) |
|---|---|---|---|---|
| Random | 7.27 | 8.26 | 842.40 | 1145.07 |
| LLMPruner | 6.01 | 6.91 | 622.92 | 1023.51 |
| ShortGPT | 5.67 | 8.56 | 555.14 | 698.02 |
| SliceGPT | 5.47 | 7.54 | 661.65 | 929.39 |
| FlexGen | 21.12 | 26.04 | 3166.27 | 4674.42 |
| CLONE (无硬件) | 4.81 | 5.56 | 462.72 | 552.18 |
| **CLONE** | **3.46** | **3.54** | **322.76** | **392.15** |

CLONE 最高实现 **11.92x 推理加速**和 **7.36x 能效提升**。

### 鲁棒性

- 跨模型：在 Llama2-7B 和 Vicuna-7B 上平均优于基线 23.85%
- 跨规模：Llama2-13B 上保留原模型 91.13% 性能

---

## 六、批判性分析

1. **硬件加速器仅为仿真验证**：28nm 加速器经过完整 P&R 流程但并未真正流片（tape-out），仅通过 post-layout simulation 验证。论文将其作为核心贡献之一，但实际上无法确认真实芯片上的功耗、良率和热效应。"Due to the high cost and time requirements of a full tape-out" 的表述过于轻描淡写。

2. **评估规模偏小**：所有实验仅在 7B 和 13B 模型上进行。当前主流边缘模型已扩展到 Llama-3-8B、Phi-3、Gemma-2-9B 等更新架构，论文使用的 Llama-7B/Llama2-7B 已显过时。对于宣称的通用性（"not a one-off software-ASIC"），支撑证据不足。

3. **基线不公平**：FlexGen 的核心价值是通过 CPU-GPU offloading 支持超大模型推理，将其与剪枝方法在延迟/能耗上直接对比并不合理——它们解决的是不同问题。此外，缺少与量化方法（GPTQ, AWQ）和小模型（Phi-2, Gemma-2B）的关键对比。

4. **端到端 throughput 未评估**：所有延迟实验仅在 WikiText2 上进行，缺少真实对话场景的 TTFT/TPOT 数据。论文在 motivation 中大量讨论 TTFT 和 TPOT SLO，但实验中仅报告 E2E 延迟和能耗。

5. **MoE Router 的 embedding 模型开销被忽略**：每次请求需要运行 BGE sentence embedding 模型来计算相似度。在边缘设备上这个额外的推理开销不可忽略，但论文未报告其延迟和内存占用。

6. **DVFS 适用性假设过强**：实验中 co-running app 仅为 web search。实际边缘场景下的干扰源更复杂（camera、GPS、多 app 切换），DQN 的泛化能力未被验证。

---

## 七、AI Infra / MLSys 视角

1. **层间异构性的通用意义**：论文对 transformer decoder 层在精度/延迟/能耗三个维度的异构性分析（§3.1）具有普遍参考价值。这种异构性在云端推理优化中同样可以利用——例如对不同层采用不同精度的混合量化、不同层分配到不同硬件（GPU vs CPU vs NPU）。

2. **生成式剪枝搜索范式**：将离散剪枝配置搜索转化为连续空间上的梯度优化是一个有趣的思路。这个方法可以迁移到更广泛的 NAS 和模型压缩场景，特别是在需要同时优化多个目标（精度、延迟、内存、能耗）的 Pareto 搜索问题中。

3. **Token 级 DVFS 的启发**：虽然 DVFS 是硬件特定的，但"在每个 token 的 layer boundary 做细粒度资源调度"的思想可以扩展到云端的 GPU 功率管理、heterogeneous computing 中的任务分配，以及 speculative decoding 中的 draft/verify 阶段资源分配。

4. **值得跟进的方向**：
   - 将 CLONE 的离线裁剪方法与 4-bit 量化（AWQ/GPTQ）结合，探索剪枝+量化联合搜索空间在边缘设备上的极限
   - 将 MoE LoRA router 的思路应用到云端多租户 LoRA serving 场景（如 S-LoRA），实现 request-level 的动态 adapter 融合
   - 借鉴层间异构性分析，在 KV cache 管理中对不同层采用不同的 eviction/compression 策略

---

## 八、总结

CLONE 提出了一套面向边缘 LLM 推理的算法-硬件协同设计方案：离线阶段通过生成式框架自动搜索设备特定的最优剪枝配置并训练多 LoRA adapter，在线阶段通过 MoE router 动态融合 adapter 适配混合任务，同时用 learning-based DVFS 在 token 级 layer boundary 做细粒度能效优化，配合专用 28nm 加速器实现最高 11.92x 加速和 7.36x 能效提升。该系统在模型精度保持方面优于现有剪枝基线，但硬件加速器仅为仿真验证、评估模型规模偏小、关键基线缺失（量化方法）是主要局限。
