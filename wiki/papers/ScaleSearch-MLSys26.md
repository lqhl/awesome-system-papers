---
type: paper
name: ScaleSearch
full_title: "Search Your Block Floating Point Scales!"
authors: [Tanmaey Gupta, Hayden Prairie, Shirley Wu, Reyna Abhyankar, Qingyang Wu, "et al."]
venue: MLSys
year: 2026
tags: [quantization, nvfp4, attention, kv-cache, block-floating-point]
source_pdf: "[[3ef815416f775098fe977004015c6193.pdf]]"
source_md: "[[3ef815416f775098fe977004015c6193]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Search Your Block Floating Point Scales! (MLSys 2026)

> **一句话总结**：标准 BFP max-scaling 未必最小化 block MSE；NVFP4 的 E4M3 scale 有 mantissa 分辨率，ScaleSearch 在邻域 **[-2,+6]** 穷举搜索使合成误差 **-27%**、Qwen3-8B MATH500 PTQ **+15** 分；ScaleSearchAttention 让 QKᵀ/PV 在 NVFP4 Tensor Core 上无 dequant 执行，Llama 3.1 70B Wikitext-2 PPL **3.4→2.63**、量化开销仅 **1.74×**、attention 吞吐达 SageAttention3 **98.3%**。

## 问题与动机

[[Quantization]] 是生成式模型推理加速的主路径，NVIDIA Blackwell 的 NVFP4/MXFP4 microscaling BFP 格式已在 Tensor Core 上支持 4-bit matmul，相对 FP8 可达 **2–3×** 吞吐。工业栈（[[vLLM]]、TensorRT、ModelOpt）与学术工作普遍采用 **max-abs scaling**：每个 micro-block 的 scale 由 block 内最大绝对值决定，保证所有元素可表示，但 **不保证最小化量化误差**。

论文 claim 有两层：（1）在 PTQ 与低精度 attention 中，更优 block scale 可显著降低 MSE 并改善下游 benchmark；（2）FP4-native attention 与 [[KV-Cache]] 压缩仍欠探索——现有工作多聚焦权重/激活 PTQ 或 QAT，而 attention 的二次复杂度与 outlier 动态使 FP4 路径尤其脆弱。ScaleSearch 针对第一层；ScaleSearchAttention 将前者扩展到端到端 causal LM 推理，目标是在 Blackwell 硬件约束下 **近零精度损失** 地跑通 FP4 attention。

## 关键观察 / 隐含假设

- 观察 1：max-scaling 对 block-wise MSE 可显著次优，且误差可通过搜索邻近可表示 scale 大幅削减。 合成高斯 tensor 上，穷举 scale 搜索使 MSE 从 0.0990→0.0066（约 25% 相对降幅）；NVFP4 配置仿真显示 27% 改进。真实 Llama 3.1 8B Key state 的 offset 分布与合成高斯 双峰结构一致（主峰在 offset 0 与 4–5），支撑「小范围搜索即可」的归纳。
  - **依赖假设**：每个 16 元 micro-block 内元素幅度相关；最大元素用 FP4 幅值 **6** 或 **4** 表示时，最优 scale 相差约 **1.5×**，对应 E4M3 bit pattern 上 offset **4–5**。
  - **可能失效场景**：block 内出现极端 outlier 且其余元素极小时，max-scaling 与 MSE-optimal scale 可能重合，搜索收益趋零；per-tensor / per-column 等大 block 时收益随 block size 增大而衰减（Fig. 7）。

- 观察 2：NVFP4 的 E4M3 浮点 scale（相对 MXFP4 的 UE7M0 纯指数 scale）在 max-scale 附近有更多可表示邻点，使邻域搜索性价比高。 MXFP4 offset 分布仅使用 0 与 1 两个值，MSE 改进约 8–11%；NVFP4 在 [-2,+6] 共 9 个 offset 即可饱和收益。
  - **依赖假设**：目标部署格式为 **NVFP4**（16 元 block + E4M3 scale），且量化路径可改写 scale 选择逻辑（论文基于 vLLM `nvfp4_utils.cuh` 集成）。
  - **可能失效场景**：仅支持 MXFP4 或 power-of-two scale 的硬件/框架；scale 不可按 int8 邻域微调时算法需重新设计。

- 观察 3：Attention 中 Q/K outlier 与 attention sink 使纯 FP4 KV cache 误差放大，但可用 incoherence processing + 混合精度 sink block 补偿。 Ablation 显示去掉 mixed-precision KV cache 使 PPL 从 5.4977→5.5768（最大单项退化）；去掉 ScaleSearch 仅 5.5024，说明 sink-aware 全精度首尾 block 对精度贡献大于 scale 搜索本身。
  - **依赖假设**：attention score 集中在 **初始 token** 与 **最近 local token**（StreamingLLM / attention sink 现象）；固定 **O(B)** 大小全精度 KV 不随 context 增长。
  - **可能失效场景**：sink 行为弱的模型或任务；极大 context 下首尾 block 策略无法覆盖中间关键 pivot token；B 与 NVFP4 MMA 约束（m≥16）不匹配时的实现碎片。

- 观察 4：ScaleSearch 的额外算力集中在离线/逐 block 量化阶段，对 attention kernel 吞吐影响极小。 2048×2048 矩阵 FP32→NVFP4：baseline 0.0258 ms，搜索 [-2,+6] 为 0.0449 ms（1.74×）；32K 序列 non-causal attention 达 SageAttention3 98.3% TOPs。
  - **依赖假设**：量化发生在 **prefill / cache 写入** 频率远低于 matmul；搜索范围固定为小常数。
  - **可能失效场景**：在线动态 requantization、极高 churn 的 KV 驱逐策略；搜索范围扩大到全 E4M3 邻域时开销线性爆炸。

- **假设 1：ScaleSearchAttention 的精度结论可通过 PyTorch 仿真框架代表真实 Blackwell NVFP4 Tensor Core 行为。**
  - **证据强度**：中。PPL/benchmark 与 full-precision 对齐较好，但论文自述 SageAttention3 官方代码在 causal 设定下数值不稳定，改用自研 simulator；**未展示** 与生产级 FP4 attention kernel 的 bit-exact 对齐或端到端 serving 指标。

## 核心方法

### ScaleSearch：邻域 scale 穷举

对每个 NVFP4 micro-block **x ∈ ℝ¹⁶**：

1. 计算标准 scale **s = round_E4M3(max|x| / 6)**（与 vLLM 默认路径一致）；
2. 将 **s** 重解释为 int8，对 offset **f ∈ [f_min, f_max]**（论文默认 **[-2, +6]**）生成候选 **s(f)**；
3. 对每个候选量化 **q_i = round_E2M1(x_i / s(f))**，计算 MSE **ℓ = Σ(x_i - q_i·s(f))²**；
4. 取 **ℓ** 最小的 **(s*, q*)**。

算法与 microscaling 格式解耦，可迁移到其他 block FP 格式，但论文聚焦 **唯一具备浮点 scale 且硬件加速** 的 NVFP4。集成点包括 TensorRT-ModelOpt PTQ 路径与 SageAttention3 的 scale 选择。

### ScaleSearchAttention：端到端 FP4 attention + KV cache

在 ScaleSearch 基础上构建 **hardware-aware** attention pipeline，回应 [[Flash-Attention]] 式分块计算与 Blackwell NVFP4 MMA 约束：

- **全链路 NVFP4 化**：Q、K、V 及 partial attention 矩阵 P 均量化为 NVFP4（平均 **4.5 bit/数**）；**QKᵀ** 与 **PV** 直接在 NVFP4 Tensor Core 上 matmul，FP32 accumulator，**无显式 dequant**。
- **Scale 方向**：Q/K/V/P 的 block scale 经 ScaleSearch 计算；量化沿 matmul **归约维** 分组（满足 NVFP4 warp-level block scaling 指令要求）。
- **Incoherence Processing (IP)**：沿用 QuIP#/QuaRot 思路，对 Q/K 施加 Hadamard 变换 **H** 打散 outlier，保持 attention score 不变。
- **Magnitude reduction**：引入可逆变换 **R ∈ ℝ^{d×d}**，通过 Q/K 二阶矩矩阵的 SVD 构造 **R**，在保持 **QKᵀ** 的前提下联合降低投影后 Q/K 的平均平方幅度，直接压低量化误差（附录给出最优性证明）。
- **Attention-sink mixed-precision cache**：将 attention 矩阵按 block 大小 **B** 切分；**首个 block** 与 **最近 incomplete block** 的 K/V 保持全精度，其余 KV cache 存 NVFP4。全精度部分 **O(B)** 常量，不随 context 增长；Fig. 8 展示 prefill 末尾 token 凑满 block 后批量量化写入压缩 cache 的流程。

## 设计取舍

- **穷举邻域搜索 vs 解析最优 scale**：赢得实现简单、与现有 rounding 路径正交、可证明在小范围内接近全局最优 MSE；代价是每 block 多 **9×** 次 round+dequant 试探（仍仅 **1.74×** 总量化时间），且收益依赖 E4M3 邻域密度。
- **NVFP4 vs MXFP4**：NVFP4 更小 block（16）+ 更细 scale → 更低 MSE；牺牲略差动态范围与略高 bits/数。
- **Mixed-precision sink cache vs 纯 FP4 KV**：赢得接近 full-precision 的 PPL/benchmark；牺牲实现复杂度（QKᵀ/PV 需拼接高低精度 matmul 结果）、固定 **O(B)** HBM 用于 sink block，且 **B** 需与性能/内存 trade-off 手工调参。
- **仿真验证 vs 生产 kernel**：PyTorch simulator 便于快速 ablation 与跨模型对比；**未验证** 真实 FP4 attention kernel 的数值边界、warp scheduling 与与 [[PagedAttention]] 等 serving 栈的集成成本。
- **边界条件**：在 **Blackwell + NVFP4 Tensor Core + causal LM 长上下文** 下最优雅；扩散模型 attention（Mochi/CogVideoX）上 ScaleSearch 叠加 SageAttention3 也有效，但 ScaleSearchAttention 的 KV 混合精度策略主要针对 **自回归 sink** 结构。

## 实验与结果

**环境**：ScaleSearch PTQ/attention 吞吐基于 vLLM 量化实现与 SageAttention3 风格 benchmark；bfloat16 输入；ScaleSearchAttention PPL 为 PyTorch 仿真。

### ScaleSearch（PTQ + 扩散 attention）

- **PTQ**（DeepSeek-R1-Distill-Qwen-1.5B、Qwen3-8B vs ModelOpt NVFP4）：全 benchmark 平均优于 NVFP4，MATH500 最高 **+15** percentage points（Qwen3-8B）；在 baseline 与 NVFP4 差距大的 GPQA/MATH500/MMLU 上显著 **收窄 gap**。
- **扩散 attention**（Mochi、CogVideoX-2B + SageAttention3）：VQA-a/VQA-t/FScore 提升，VQA-t 最高 **+14**；CLIPSIM/CLIP-T 已与 full-precision 接近处保持持平。

### ScaleSearchAttention（causal LM）

- **Wikitext-2 PPL**（Llama 3.1 8B/70B、Qwen3 4B/8B）：全面优于 Naive-FP4 与 SageAttention3；Llama 3.1 70B **3.4→2.6348**（**~22%** 相对降幅，**0.77** 绝对改善）；大模型上收益仍明显（反驳「大模型量化不敏感」直觉）。
- **叠加 ScaleSearch**：在 Naive-FP4 与 SA3 之上均降低 PPL，验证 ScaleSearch 可 **插件式** 嵌入多种 FP4 attention 流程。
- **GPQA Diamond**（Llama 3.1 8B Instruct）：SSA **32.32** vs SA3 **26.26**，逼近 full-precision。
- **Ablation**（Llama 3.1 8B）：完整 SSA **5.4977**；去 ScaleSearch **5.5024**；去 IP+magnitude reduction **5.5283**；去 mixed-precision KV **5.5768**。

### 开销与效率

- 量化：**1.27×**（搜索 **[-1,1]**）、**1.74×**（**[-2,6]**）。
- Attention 吞吐：32K 序列 non-causal **98.3%**、causal **97.5%** SageAttention3 TOPs。
- 端到端 text-to-video 延迟：Mochi **353.40 s**（SA3）vs **364.68 s**（+ScaleSearch）；CogVideoX **61.72 s** vs **63.09 s**——边际开销。

## Critical Analysis

### 论证链条

链条为：**测量** max-scaling MSE 次优（合成 + 真实 Key tensor offset 分布）→ **机制** E4M3 mantissa 使邻域搜索可行且小范围饱和（Fig. 3–4）→ **设计** ScaleSearch 嵌入 PTQ/attention scale 路径 → **结果** MSE -27%、MATH500 +15、PPL 大幅改善且吞吐损失 <3%。

ScaleSearchAttention 链条额外依赖：**观察** attention outlier + sink（ablation 量化 mixed-precision 贡献）→ **设计** IP + magnitude reduction + FP4 Tensor Core matmul → **结果** 70B PPL 近 full-precision。

最强证据是 **offset 分布跨合成/真实数据一致** 与 **受限搜索范围下 MSE 饱和曲线**（Fig. 3），直接支撑工程默认 **[-2,+6]**。最弱环节是 ScaleSearchAttention **全程仿真**——论证从 simulator 到 Blackwell production kernel 的跳步未被实验覆盖。

### 假设压力测试

**Workload**：以 Wikitext-2 PPL 与数学/科学 benchmark 为主；未覆盖代码生成、多轮 tool-use、极长 context（>32K）生产 trace。扩散实验用 SageAttention3 评测集，与 LM serving 负载差异大。Attention sink 假设对非标准位置编码或弱 sink 模型可能失效。

**硬件**：结论绑定 **NVFP4 + Blackwell Tensor Core**；MXFP4、非 NVIDIA 4-bit 格式仅仿真 MSE 改进，无端到端 LM 结果。Mixed-precision matmul 依赖高低精度 kernel 共存与拼接，在异构或旧代 GPU 上可能无加速甚至变慢——论文未测。

**规模**：70B 上 PPL 改善显著，但 GPQA 仅在 8B Instruct 上报告；缺少 70B 下游 task accuracy 与多租户 serving 数据。

**部署**：与 [[vLLM]] rounding 路径集成已演示，但 ScaleSearchAttention 的 KV 混合精度、跨 block 量化时机与 [[PagedAttention]] block 生命周期对齐的工程细节论文未展开；在线 decode 每 token 触发 block 量化完成的延迟未单独报告。

### 实验可信度

优点：PTQ 覆盖多 benchmark 与两种模型规模；ablation 清晰分解 ScaleSearch / IP / mixed-precision KV；开销测量分离量化阶段与 attention kernel；与强 baseline（ModelOpt NVFP4、SageAttention3）对比。

限制：ScaleSearchAttention **无** 真实 NVFP4 attention kernel 或端到端 serving QPS/TPOT；SageAttention3 causal 结果来自 **重实现 simulator** 而非官方代码；PTQ 仅两模型；Table 1 具体分数在 markdown 中以图片形式存在，数字精度依赖正文叙述；缺少与 QuIP#/QuaRot 等 **仅 IP 无 ScaleSearch** 的 head-to-head。

### 系统性缺陷

- **尾延迟与流水线**：mixed-precision QKᵀ/PV 需分块拼接高低精度结果，可能引入额外同步点；论文未报告 decode TPOT 分布。
- **内存**：sink block 全精度 KV 为 **O(B)** 常量，但 B 选择与峰值 HBM 的 trade-off 未系统扫描。
- **可观测性 / 调试**：多 offset 搜索使 block scale 分布更难与 max-scaling 基线对比排障；论文未讨论 production monitoring。
- **兼容性**：算法假设 E4M3 scale 可按 int8 偏移遍历；框架升级或 scale encoding 变更时集成脆弱性未讨论。
- **故障与数值安全**：仿真中未讨论 FP4 累加溢出、极端 temperature 下 softmax 与 FP4 P 量化的交互。

## 局限与 Future Work

- **局限 1**（论文自述）：ScaleSearch 主要验证于 **NVFP4**；MXFP4 等稀疏 scale 格式收益有限。
- **局限 2**：ScaleSearchAttention 基于 **模拟框架**，非完整 production attention kernel；SageAttention3 官方 causal 代码数值不稳定。
- **局限 3**：搜索范围 **[-2,+6]** 来自经验分布，非理论最优；更大范围线性增加量化开销。
- **局限 4**：mixed-precision KV 策略依赖 attention sink 启发式，对非 causal 或弱 sink workload 泛化未充分验证。
- **局限 5**：端到端延迟仅在 text-to-video 扩散模型上测量，**未报告** LM serving 场景。

- **Future work 1**：在真实 Blackwell FP4 attention kernel 上复现 ScaleSearchAttention PPL/benchmark，量化 simulator-to-hardware gap。
- **Future work 2**：将 offset 搜索范围与 block 统计量（方差、outlier 比例）关联，学习 **per-layer 自适应 [f_min, f_max]**，在精度与 1.74× 开销间做 Pareto 曲线。
- **Future work 3**：与 [[PagedAttention]] / [[RadixAttention]] 集成，测量长 context decode 下 mixed-precision sink cache 的 TPOT 尾延迟与 HBM 占用。
- **Future work 4**：在 MXFP8/其他 microscaling 格式上系统测量「scale 邻域密度 vs ScaleSearch 收益」，验证观察 2 的外推边界。

## 相关

- **相关概念**：[[Quantization]]、[[KV-Cache]]、[[Flash-Attention]]、[[Attention]]、[[PagedAttention]]
- **同类系统**：[[vLLM]]、SageAttention3、QuIP#、QuaRot、TensorRT-ModelOpt
- **同会议**：[[MLSys-2026]]、[[IntAttention-MLSys26]]（低精度 attention）、[[FlexiCache-MLSys26]]（KV cache 管理）
- **对比**：与 QuIP#/QuaRot 同属 **attention 量化前变换降 outlier**，ScaleSearch 额外优化 **BFP block scale** 本身；与 SageAttention3 正交可叠加，论文显示 **+ScaleSearch** 在 VQA-t 等指标上进一步增益
