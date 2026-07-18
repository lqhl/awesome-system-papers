---
type: paper
name: CLONE
full_title: "CLONE: Customizing LLMs for Efficient Latency-Aware Inference at the Edge"
authors: [Chunlin Tian, Xinpeng Qin, Kahou Tam, Li Li, Zijian Wang, Yuanzhe Zhao, Minglei Zhang, Chengzhong Xu]
venue: ATC
year: 2025
tags: [edge-llm, llm-inference, dvfs, lora, pruning, hardware-accelerator]
source_pdf: "[[atc2025-tian.pdf]]"
source_md: "[[atc2025-tian]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# CLONE: Customizing LLMs for Efficient Latency-Aware Inference at the Edge (ATC 2025)

> **一句话总结**：CLONE 观察到边缘 LLM 的瓶颈不仅是参数量，更是层间贡献不均、stochastic I/O 与前台干扰导致的运行时方差；它用 device-specific generative pruning + request-wise LoRA-MoE + layer-boundary learning-based DVFS，并在 28nm LPU/SFU 加速器上落地，在 Jetson Orin 上相对 baseline 推理加速最高 11.92×、能耗节省最高 7.36×，同时保持下游任务精度。

## 问题与动机

在 COTS 边缘设备上部署 LLM 面临 SWaP（Space/Weight/Power）三重约束：Llama-7B FP16 约需 14 GB 内存，而典型边缘设备 RAM 仅 4–12 GB；单 token 推理约 14 TFLOPs，约为 VGG-19 单图推理的 360×；GPT-3 单条响应约 300 J，约为 ResNet-50 的 400×。作者 claim 的边界是：不是重新发明 [[Pruning]]/[[Quantization]]，而是把 **model-level customization** 与 **system-level latency/energy control** 放进同一套 offline/online 协调框架。

现有方案各自为政。[[Pruning]]、NAS、[[Quantization]] 主要压缩模型本身，很少同时优化存储重量与系统层 trade-off；LLM compiler / co-processor 方案（如 [[FlexGen]]、near-sensor processing）引入额外计算与通信开销，缩短设备续航并干扰并发应用；[[DVFS]] 多面向 CNN/RNN，把整网当 black-box workload，未针对 auto-regressive prefill/decode 异构、stochastic prompt/output 和 per-layer 不均匀负载做细粒度调节。边缘场景还需要在 latency SLO、能耗与生成质量之间做联合优化，而不是一次性静态压缩。

## 关键观察 / 隐含假设

- **观察 1：同构 decoder layer 对生成质量、能耗、延迟的贡献高度不均。** 逐层移除实验显示，Llama-7B / Llama2-7B / Vicuna-7B 的前后层对 zero-shot PPL 影响远大于中间层；CodeCarbon 测得的 E2E 能耗与延迟也随被剪层位置呈非均匀变化（§3.1, Figure 3）。
  - **依赖假设**：目标模型是 uniform transformer stack，且 layer-wise structural pruning 后 inter-layer interaction 仍可用静态 ratio 近似。
  - **可能失效场景**：MoE/transformer 变体、强 coupling 的 cross-layer 结构，或 pruning 后 accuracy cliff 出现在中间层时，连续 ratio 搜索可能错过离散最优。

- **观察 2：LLM 推理 I/O 强 stochastic，prefill 与 decode 的资源画像不同。** Azure trace 显示 prompt/output 长度长尾分布；Gemma-2B on Orin NX 上，prompt 从 128→1024 tokens 时 prefill 从 255 ms 增至 1935 ms，而 TPOT 稳定在 180–200 ms；prefill 能耗高、decode 单步功耗低但 E2E 随输出 token 线性拉长（§3.2, Figure 5）。
  - **依赖假设**：用户请求混合多任务，且 embedding 相似度足以区分应激活的 [[LoRA]] expert；输出长度可被 token predictor 在 prefill 后足够准确地估计。
  - **可能失效场景**：单 prompt 内混合多任务、极低相似度区分的 niche domain，或 output length 高度不确定时，request-wise routing 与 DVFS 预算会失配。

- **观察 3：硬件平台与前台并发显著放大运行时方差。** 同 workload（128 prompt + 242 output tokens）下，Orin NX idle TTFT/TPOT 为 255/198 ms，Nano 为 268/231 ms；前台 web-search 使 NX E2E 从 42.6 s 增至 61.4 s；不同 GPU frequency 对 E2E/TPOT/能效的影响随 output length 变化（§3.3, Figure 6–7）。
  - **依赖假设**：DVFS 在 layer 边界调节 $V_{DD}$/$F_{req}$ 能追上 per-token 负载变化；MLP policy + power LUT 足以覆盖 co-running app 强度与 SLO 组合。
  - **可能失效场景**：更激进的 OS 调度干扰、热 throttling、或真实 Jetson 离散频点无法达到 SFU 仿真的连续 DVFS 粒度时，layer-wise policy 收益会缩水。

- **假设 1：把 pruning 建模为连续表征空间上的 generative task，比手工 heuristic 更能兼顾 PPL、延迟与能耗。**
  - **证据强度**：中。Equation (1) 的 ratio-score 与 gradient search 在 WikiText2/PTB 上优于 Random/LLM-Pruner/ShortGPT/SliceGPT，但 score 函数和 α=β=2 惩罚系数是手工设定，未见 sensitivity study。

- **假设 2：专用 28nm 加速器（LPU hot-swap LoRA、eNVM 缓冲、SFU 连续 DVFS）是软件栈无法替代的瓶颈消解手段。**
  - **证据强度**：弱–中。加速器仅 post-layout/SPICE 仿真验证，未 tape-out；Table 3 显示关掉硬件后 CLONE-HW 仍优于所有 software baseline，说明算法层本身已有效，硬件增益是增量而非前提。

## 核心方法

CLONE 采用 hierarchical offline/online 两阶段（Figure 8），把静态模型权重、设备 profile、stochastic request 与运行时方差放进统一协调器。

**离线 device-specific tailoring** 回应观察 1。CLONE 不把 pruning ratio 当离散启发式搜索，而是：先用 LLM-Pruner、ShortGPT、SliceGPT 等 heuristic + 随机 ratio 收集 $(r_i, s_i)$，其中 $s_i = f(r_i) = \frac{1}{ppl_i}(\frac{E}{e_i})^{1(E<e_i)\cdot\alpha}(\frac{T}{t_i})^{1(T<t_i)\cdot\beta}$，同时惩罚超延迟/能耗预算的配置；LSTM encoder-evaluator-decoder 把 ratio-score 嵌入连续空间 Θ，沿 evaluator 梯度 ascent 得 $\mathcal{E}_r^*$，beam search 解码 layer-wise $r^*$，再做 structural pruning。随后为 Flanv2 的 46 tasks / 10 domains 训练多组 plug-and-play [[LoRA]] adapter（rank r=8, α=16），保留 frozen base weights。

**在线 latency-aware inference** 回应观察 2 与 3。Model level：parameter-free soft [[MoE]] router 用 BGE embedding 计算 prompt 与每个 LoRA expert 的 cosine similarity，再 softmax 加权融合，避免可训练 gate 的额外存储与计算；这比 Top-1 选择更适合单请求跨任务场景（Figure 19）。System level：token predictor 估计输出长度，两层 MLP（<1K 参数）作为 learning-based [[DVFS]] controller，在 **每个 token、每个 layer 边界** 选择 $(V_{DD}, F_{req})$；state 包含前台 app 强度 $S_{pro}$、TTFT target $T_{PRE}$、TPOT target $T_{DEC}$，reward 用 prefill/decode power LUT 估算能耗。控制器与 prefill（>100 ms）并发执行（<10 ms），decode 时在生成 token $t$ 的同时为 $t+1$ 决策，尽量避开 critical path。

**28nm hardware accelerator** 把上述算法映射到专用 datapath（Figure 10–12）：LPU 通过 eNVM 常驻 LoRA 权重，避免 SRAM leakage 或 DRAM 重载；SFU 用 fast-switching LDO + ADPLL 实现细粒度连续 DVFS；core 面积 1.588 mm²，经 PCIe 接入 Jetson 与 GPU 协同。深度实现细节回 [[atc2025-tian]]。

## 设计取舍

- **用离线 generative search 换 tailoring 质量与工程可重复性**：LSTM + gradient search + beam search 比一次性 heuristic pruning 更重，但能把 PPL/延迟/能耗同时写进目标；代价是 tailoring 绑定特定 device profile，换硬件需重跑离线流程。
- **用多 LoRA + soft MoE 换单模型通用性**：避免为每个 edge app 单独蒸馏/微调整模，但增加存储（多个 adapter）和 routing 延迟；rank 增大后 MMLU 收益饱和（Figure 18），存在 capacity–overhead 拐点。
- **用 layer-boundary DVFS 换能效**：比 workload-level black-box DVFS 更贴合 pruned LLM 的不均匀层负载，但 policy 依赖手工 SLO 与 power LUT，且真实 Orin 频点是离散的，与 SFU 连续调节存在实现鸿沟。
- **用专用 ASIC 换峰值能效，牺牲通用性与验证完整性**：LPU/SFU 针对 LoRA swap 与 DVFS 定制，未 tape-out，系统实验主要在 Jetson GPU + 仿真加速器上完成；纯软件路径（CLONE-HW）已能打败 pruning baseline，说明 ASIC 是锦上添花。
- **边界条件**：最优雅场景是 memory-bound 7B 级 LLM、少量已知 downstream task、可接受百秒级 WikiText2 benchmark E2E 的机器人/嵌入式 GPU；脆弱场景是手机 NPU、需要 sub-second 交互 SLO、或应优先 [[Quantization]]+[[PagedAttention]] 而非 structural pruning 的部署。

## 实验与结果

- **系统效率（Table 3, WikiText2）**：CLONE 在 Orin NX 上 3.46 Wh / 322.76 s，Nano 上 3.54 Wh / 392.15 s；相对 Random（7.27–8.26 Wh, 842–1145 s）、SliceGPT、LLM-Pruner、ShortGPT、OpenLLaMA-3B、FlexGen（21–26 Wh, 3166–4674 s）分别实现最高 **11.92× 加速、7.36× 节能**。
- **硬件贡献**：CLONE-HW（无加速器）为 4.81–5.56 Wh、462–552 s，仍优于所有 baseline，但比完整 CLONE 慢约 1.3–1.4×、多耗约 1.4× 能量。
- **生成能力**：WikiText2/PTB zero-shot PPL 归一化后，CLONE 最高达 Random 的 **5.1× / 3.4×** 生成质量保留；Llama2-13B 上保持 vanilla **91.13%** 性能。
- **下游任务（BBH / MMLU / Commonsense, 87 tasks）**：比 Random 平均 accuracy 高 **6.0%–15.1%**，比其他 pruning baseline 高 **2.37%–6.1%**；跨 Llama2-7B 与 Vicuna-7B 平均优于 baseline **23.85%**。
- **Ablation**：request-wise soft MoE 显著优于 w/o MoE（直接平均 LoRA）和 Top-1；layer-wise generative pruning ratio 比 ShortGPT 二值/LLM-Pruner 均匀策略更自适应（Figure 17）；DVFS 为 SPICE 级仿真验证（Figure 16）。
- **开销**：offline tailoring 用轻量 LSTM/FFN；online MoE routing 无额外可训练参数；DVFS MLP 能耗增量在 mWh 级，相对 Wh 级 inference 可忽略。

## Critical Analysis

### 论证链条

论文主链条较完整：§3 的 layer/I/O/platform 三类 heterogeneity measurement → offline generative pruning 利用层间不均匀 + 多 LoRA 覆盖 mixed-task → online MoE/DVFS 处理 stochastic request 与 runtime variance → Jetson 实测 + 28nm 布局/仿真支撑 co-design claim。最有价值的抽象是 **把 edge LLM 看成「静态定制模型 + 动态系统控制器」的联合优化问题**，而不是孤立 compression。

需要警惕的外推：11.92×/7.36× 是相对较弱 baseline（含 Random、未协同 DVFS 的 pruning）在 WikiText2 全长推理上的峰值；Table 3 绝对延迟仍达 **322–392 s**，距离 Table 2 中 chatbot/smart-reply 的 low TTFT/TPOT SLO 很远。论文证明了「比传统 pruning 更省能更快」，尚未证明「满足真实交互式 edge SLO」。

### 假设压力测试

**workload assumption**：评测以 WikiText2 全长生成、Flanv2 下游任务、固定 128+242 token case study 为主；缺少真实手机聊天、流式输出、多轮对话 trace。Azure trace 只用于动机，未驱动 end-to-end scheduler 评测。若迁移到 production chat workload，token predictor 与 DVFS 预算可能频繁失配。

**resource bottleneck assumption**：默认瓶颈是 memory footprint + edge GPU 能耗，通过 pruning 与 DVFS 解决；未与 INT4/INT8 [[Quantization]]（论文 Related Work 承认常见但未作 baseline）、[[KV-Cache]] 压缩、[[PagedAttention]] 类 serving 优化对比。对 7B@FP16 仍 OOM 的设备，CLONE 的 pruning 能否压到可部署阈值论文未给明确 memory breakdown。

**hardware/deployment assumption**：系统实验集中在 Jetson Orin NX/Nano；28nm ASIC 为 post-layout simulation + PCIe 原型描述，无硅片功耗/面积/带宽实测。SFU 连续 DVFS 与 Jetson 离散频点、热设计功耗之间的 gap 未量化。智能手机、MCU-class IoT 不在评测矩阵内。

**scaling assumption**：在 Llama2-13B 上保持 91% vanilla 性能，说明方法有一定 scale-out 性；但 offline ratio-score 收集、LSTM training、per-device tailoring 成本随模型层数/宽度增长，论文未报告 tailoring 搜索的 wall-clock 与人力成本。

**correctness/SLO assumption**：优化聚焦 throughput/E2E energy，对 tail latency、多租户隔离、故障恢复、policy 可观测性几乎未讨论。DVFS 降频是否影响数值稳定性或生成分布，论文未测量。

### 实验可信度

**强项**：动机 measurement 扎实（layer sensitivity、Azure trace、foreground app interference）；baseline 覆盖代表性 pruning 方法 + FlexGen + 小模型 OpenLLaMA-3B；多 backbone（Llama/Vicuna, 7B/13B）与 87 downstream tasks 支撑 generality claim；CLONE-HW ablation 清晰分离算法 vs 硬件收益。

**弱项**：缺少与 contemporary edge LLM stack（llama.cpp、MLC、Qualcomm/QNN 量化 Llama）的对比；系统 metric 用 WikiText2 全长 E2E，对 TTFT/TPOT SLO 的满足情况仅停留在动机图（Figure 2/6），未在完整 CLONE 系统上按 Table 2 各类 app SLO 报告达标率；加速器结论来自仿真，PCIe 原型是否达到 Table 3 的 CLONE 数字论文未明确拆分。

### 系统性缺陷

- **交互式延迟**：论文未讨论如何把 322 s 量级 E2E 压到 50 ms 级 TPOT；DVFS 节能与 latency target 的 trade-off 只在 controlled benchmark 中体现，缺少 SLO violation rate。
- **多应用并发与隔离**：仅模拟前台 web-search 干扰，未给出 DVFS/scheduler 在多重 GPU consumer 下的公平性与优先级策略。
- **可观测性与运维**：learning-based DVFS policy、MoE routing 决策、pruning ratio 缺少线上 debug 接口；policy 漂移、embedding model 更新后的再训练流程论文未讨论。
- **edge–cloud 协同**：§6 Related Work 提出超本地容量时 offload 到 cloud LLM，但无实验验证切换策略、隐私边界与网络断开行为。
- **正确性**：pruning + 多 LoRA 融合对 hallucination、安全对齐的影响未评估；论文未讨论。

## 局限与 Future Work

- **局限 1：28nm 加速器未流片。** 后续应 tape-out 或 FPGA 原型，实测 LPU swap latency、eNVM 带宽与 SFU DVFS 切换能耗，并与 Table 3 仿真增益交叉验证。
- **局限 2：系统评测 metric 与真实 edge SLO 脱节。** 应在 chatbot/smart-reply 等场景报告 TTFT/TPOT 达标率、P99 latency 和能耗，而非仅 WikiText2 全长 E2E。
- **局限 3：缺少与量化 + 现代 inference runtime 的联合 baseline。** 可测量 CLONE pruning 叠加 INT4/AWQ 后的 memory floor，并与 [[PagedAttention]]/continuous batching 类栈对比相同 SLO 下的能耗。
- **局限 4：offline tailoring 成本与可迁移性未量化。** 应报告 per-device search 时间、ratio-score 样本数敏感性，以及从 Orin NX profile 迁移到 Nano 时的性能损失。
- **Future work 1：在线 policy adaptation。** 用真实部署 trace 微调 MoE router 与 DVFS MLP，测量 foreground app 分布漂移时的 SLO violation 与重训练频率。
- **Future work 2：layer-aware + KV-aware 协同调度。** 将 [[KV-Cache]] 增长纳入 Equation (1) 约束与 DVFS state，针对 long-context edge request 量化和验证 memory–energy–latency 三维权衡。

## 相关

- **相关概念**：[[LoRA]]、[[MoE]]、[[Pruning]]、[[KV-Cache]]、[[Quantization]]、[[PagedAttention]]、[[DVFS]]、[[Chunked-Prefill]]
- **同类系统**：[[FlexGen]]、[[vLLM]]、LLM-Pruner、ShortGPT、SliceGPT、OpenLLaMA
- **同会议**：[[ATC-2025]]
- **对比**（如有）：CLONE 代表 **edge-specific co-design（pruning + LoRA-MoE + DVFS + ASIC）** 路线，与 cloud serving 栈和纯量化压缩路线互补而非替代
