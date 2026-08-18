---
type: concept
aliases: [LLM, large language model, Large Language Models, foundation model, LLMs]
last_updated: 2026-08-18
tags: [llm-inference, llm-training, foundation-model, agents, serving]
---

# LLM

> 大语言模型（Large Language Model，LLM）在系统论文中有两种不同角色：它既是需要被训练和服务的重型工作负载（workload），也可能是提出代码、计划、判断或解释的非确定性系统组件；这两种角色需要不同的性能指标和正确性边界。

## 核心思想

LLM 通常用 Transformer 在 token 序列上建模。训练反复执行前向、反向和参数更新，常组合数据、张量、流水线和专家并行，并依靠 checkpoint、故障恢复和数值检查维持长任务。[[LLM-Inference|推理服务]]先处理输入，再逐步生成输出，持续维护 [[KV-Cache|KV cache]]。在这类论文里，LLM 是**被系统承载的 workload**：模型图和数值语义相对明确，系统研究的是 GPU/加速器、内存、网络、存储、调度与故障怎样共同影响吞吐、延迟、成本和收敛。

另一类系统把 LLM 放进控制面或应用逻辑：模型可能提出补丁、proof tactic、查询计划、故障解释、研究假设或 shell command。此时 LLM 是**非确定性组件**，自然语言输出不是正确性证明。可靠系统会把“扩大候选召回”和“接受候选”分开，再用编译、测试、静态/动态分析、符号执行、定理证明器、可执行评估器、人类复核或隔离执行建立确定性边界。

两种角色不能混为一谈。训练/服务的数值误差主要问“同一计算是否被硬件和 runtime 正确执行”；LLM 组件的语义错误则问“模型提出的内容是否满足任务规范”。更高 tokens/s 不会提高补丁正确率；较低 benchmark error 也不会证明线上 SLO、故障恢复或多租户隔离已解决。

这里保留历史 alias `foundation model`，但它比 LLM 更宽。[[TimesFM-Fin-arXiv24]] 这样的时间序列 foundation model 并不是语言模型；由该 alias 产生的入链只能当作术语边界提醒，不能作为 LLM 机制的直接证据。

## 为什么重要

把 LLM 当 workload 时，规模会把过去的局部问题变成集群级问题。[[AEGIS-OSDI26]] 在 3,500 万 GPU-hours 的生产数据中发现 18 起静默数据损坏（SDC）；[[SDCHunter-OSDI26]] 进一步表明真实坏卡可能只在特定 kernel、dtype 和输入值上出错。[[Hetu-v2-OSDI26]]、[[RollArt-OSDI26]] 与 [[Seer-OSDI26]] 又说明，异构 GPU、agentic RL 的多阶段 workflow 和 rollout 长尾都会破坏对称、同步的执行假设。

推理侧的瓶颈也会随阶段、context 和硬件改变。[[DirectKV-OSDI26]] 依赖 GH200 的 NVLink-C2C 直接访问主机 KV；[[DCP-OSDI26]] 的流水线结论来自 4×A100 PCIe；[[LMetric-OSDI26]] 与 [[StriaTrace-OSDI26]] 则来自 H20 上的 trace replay 或生产部署。它们共同证明内存、互连、排队和可观测性重要，但没有任何一个数字能脱离 hardware/workload/SLO 原样迁移。

把 LLM 当组件时，系统价值常来自模型之外的闭环。[[ECO-OSDI26]] 用全机群 profiling 找目标，再经检索、测试、review 和 canary 接受补丁；[[NeuroSymbolicProof-OSDI26]] 让模型提出 Isabelle tactic，再由 prover 执行和剪枝；[[gigiprofiler-OSDI26]] 用 LLM 扩大语义召回，再用静态与动态证据过滤。所谓“LLM 系统正确”因此通常只是一个受限契约：在给定规范、评估器、预算和覆盖范围内，没有接受已知不合格候选。

## 关键观察 / 隐含假设

- **LLM workload 的首要矛盾不总是 FLOPs。** 训练会受故障、checkpoint 和异构负载限制，推理会受权重/KV 容量、内存带宽、排队和互连限制。[[AEGIS-OSDI26]]、[[ByteRobust-SOSP25]]、[[DirectKV-OSDI26]] 和 [[BEAM-MLSys26]] 分别从 SDC、恢复、分层内存和能耗展示了不同瓶颈。
- **阶段异质性比“训练”或“推理”标签更具体。** [[RollArt-OSDI26]] 把 rollout、环境、reward 与训练分开，[[Seer-OSDI26]] 处理同一 prompt 组内 response 长短差异，[[EcoServe-OSDI26]]（经 [[LLM-Inference]] 汇总）处理 prefill/decode。设计是否有效，取决于每个阶段的资源需求和状态传递。
- **规模数字不能替代故障模型。** [[AEGIS-OSDI26]] 的 0.86% 是采样检测平均开销，不是每个算子完整检查；[[SDCHunter-OSDI26]] 是异常后的确定性 replay 诊断，不是 always-on detector；[[OpGuard-OSDI26]] 需要可比较 reference run。三者解决的是不同时间点的问题。
- **模型输出适合当候选，不适合当权威。** [[ECO-OSDI26]]、[[NeuroSymbolicProof-OSDI26]]、[[Ote-OSDI26]] 和 [[gigiprofiler-OSDI26]] 都让确定性工具或人类决定是否接受。模型单独运行时，gigiprofiler 观察到 45%–60% false positive，直接说明“语义召回高”不等于“诊断正确”。
- **verifier 只证明它能检查的性质。** Isabelle kernel 能验证给定 theorem 的 proof，不会判断 theorem 是否表达了正确需求；test/canary 覆盖到的行为也不是完整程序语义。[[NeuroSymbolicProof-OSDI26]] 的成功率还存在分母口径不完全一致，[[ECO-OSDI26]] 少于 0.5% rollback 是整条生产流水线的结果，不是原始模型精度。
- **自然语言 judge 会把不确定性重新带回控制面。** [[Ote-OSDI26]] 让 LLM 判断分支相关性并保留人工复核，[[SMARTTalk-OSDI26]] 让模型解释压缩后的 SMART 模式。若 judge、压缩器或 prompt 变化，系统行为会漂移；需要版本化输入、模型、prompt、阈值和复核记录。
- **真实 workload 分布比平均值重要。** [[LMetric-OSDI26]] 的路由分数来自生产排队结构，[[StriaTrace-OSDI26]] 用 token 条件化的 P99 roofline 区分正常长生成与异常，[[AgenticCache-MLSys26]] 利用计划局部性。模型、产品和用户行为改变后，这些局部性都可能失效。
- **自动科研系统的进展主要受可执行反馈约束。** [[AlphaEvolve-arXiv25]]、[[FunSearch-Nature24]] 和 [[SR-Scientist-ICLR26]] 都让程序或数学评估器筛候选；[[PaperBench-ICML25]]、[[AstaBench-ICLR26]]、[[RE-Bench-ICML25]] 与 [[ResearchClawBench-arXiv26]] 则显示，长时程执行、结果复现和证据核验仍明显弱于短时生成。
- **更强模型不会自动消除系统问题。** 模型变大通常增加内存、通信、能耗和故障暴露；模型更能生成合理候选，也可能更有说服力地生成错误内容。可靠性必须来自可观察、可回放、可验证和可撤销的系统边界，而不是只寄希望于下一代模型。

## 设计空间与取舍

- **训练执行**：对称 SPMD 接口简单，但异构 GPU 和变长样本会产生 straggler；非对称 plan、异步 rollout 和动态切换提高利用率，也增加 planner、staleness 与调试复杂度。[[Hetu-v2-OSDI26]]、[[RollArt-OSDI26]]、[[HetRL-MLSys26]] 分别覆盖训练、agentic RL 和跨区异构环境。
- **训练可靠性**：可以在线抽样检测、异常后 replay、跨实现比较、checkpoint 恢复或 spare capacity。覆盖越完整，额外计算和存储越高；恢复越快，预留资源越多。[[AEGIS-OSDI26]]、[[SDCHunter-OSDI26]]、[[OpGuard-OSDI26]]、[[ByteRobust-SOSP25]] 与 [[Quirk-Sparing-MLSys26]] 不能用同一个“可靠性开销”数字比较。
- **推理资源管理**：batch、并行、量化、稀疏、编译、KV 分层和阶段解聚共同决定 SLO。细节集中在 [[LLM-Inference]]；任何速度结论都应带模型、精度、context、到达、硬件、互连和质量边界。
- **模型参与深度**：模型可以只做检索/排序，也可以提出候选、写完整代码，甚至在 agent loop 中调用工具。参与越深，自动化潜力越大，错误传播和成本方差也越大。[[ECO-OSDI26]] 偏受控补丁流水线，[[Murakkab-OSDI26]] 优化多步骤 workflow，[[Try-OSDI26]] 则把不透明命令副作用留给用户决定是否提交。
- **接受边界**：可分为无验证、模型自评、人类复核、test/static analysis、可执行 evaluator、形式化 verifier 和 sandbox。越靠后，接受语义越清楚，但能覆盖的任务更窄、工程成本更高。[[NeuroSymbolicProof-OSDI26]] 的 prover 边界最强，[[Ote-OSDI26]] 的 bounded analysis 与人工审查更灵活但不完备。
- **学习方式**：可以冻结权重、优化 prompt/程序，也可以微调、强化学习或搜索外部记忆。[[GEPA-ICLR26]] 用语言反馈演化 prompt，[[Seer-OSDI26]] 和 [[RollArt-OSDI26]] 优化 RL 执行，[[AgenticCache-MLSys26]] 与 [[HIPPOCAMPUS-MLSys26]] 优化计划和记忆复用。系统成本、可复现性和更新频率不同。
- **证据等级**：微基准回答机制是否可能有效；受控端到端实验回答某一配置是否有效；trace replay回答历史流量是否受益；production canary/deployment 才回答真实系统是否可运维。页面中的倍数必须保留这一证据层级。

## 引用本概念的论文

- [[PithTrain-arXiv26]] — 同时把 LLM 作为被训练的 MoE workload 与修改框架的 coding agent 组件；ATE-Bench 用可执行 artifact 和人工复核约束 agent 输出，但只固定 Claude Code Opus 4.7，不能外推跨模型排序或长程可靠性。

### OSDI 2026：LLM 是训练或服务 workload

- [[ADAngel-OSDI26]] — 为固定模型、GPU、shape 和任意精度格式离线选择 GEMM kernel；收益伴随约 5.7 小时 profile 和多份权重布局。
- [[AEGIS-OSDI26]] — 在线抽样检测训练 SDC，再离线确认；3,500 万 GPU-hours、18 起 SDC 和 0.86% 平均开销属于其生产检测策略。
- [[Cocoon-OSDI26]] — 为相关噪声差分隐私训练管理历史状态，并在 GPU、CPU 和 CXL-NMP 间计算；NMP 部分含按 22 GB/s 缩放的结果。
- [[DCP-OSDI26]] — 在 4×A100 PCIe 上用动态分块 prefill 和 delay scheduling 控制流水线 bubble；结论绑定 Qwen2.5-14B/32B 与论文的 P90 SLO。
- [[DirectKV-OSDI26]] — 在 GH200 上直接读取 CPU KV，避免 HBM staging；47 GB GPU 内存和平均降低 43% 不适用于普通 PCIe 主机。
- [[Hetu-v2-OSDI26]] — 用 HSPMD 处理异构 GPU 和变长数据；16×H800+32×H20 的 32B Llama 每步 6.05 秒依赖场景专用 planner。
- [[KAIROX-OSDI26]] — 在消费级独显主机上预测活跃神经元并在 CPU/GPU 间迁移；证据以单请求、近似稀疏执行和离线激活数据为边界。
- [[LMetric-OSDI26]] — 用“待处理新 prefill token×batch size”兼顾 prefix locality 与负载；有 16×H20 replay 和数百 GPU canary，但效果依赖其真实流量。
- [[MPK-OSDI26]] — 用 persistent mega-kernel 跨算子流水；只报告固定长度 offline decode 吞吐，没有 online P99、多租户和编译成本。
- [[MoonBright-OSDI26]] — 加速 GPU 页表建立；LLM 端到端只测单 A100、7B/8B，8.2 倍 TTFT 是 prefix-cache 场景，无 prefix 收益约 5%。
- [[Nixie-OSDI26]] — 在 RTX 5090 上按整个 ML App 驻留与迁移，改善交互式代码补全 TTFT；高交互频率可牺牲 23.5% 后台吞吐。
- [[OpGuard-OSDI26]] — 在共同模型算子边界比较 tensor fingerprint，定位训练差异；需要可比较 reference run，trusted mode 运行时间约增加到 1.25–1.45 倍。
- [[RollArt-OSDI26]] — 解耦 agentic RL 的 rollout、环境、reward 和训练，在 Qwen3-32B 与 3,000 多 GPU 部署中减少同步长尾；bounded staleness 改变了训练时序。
- [[SANI-OSDI26]] — 为非对称移动 CPU 选择不同 kernel，并处理跨 cluster 迁移；LLM 是移动推理 workload，结论受 SoC 核型和内存系统约束。
- [[SDCHunter-OSDI26]] — 对异常训练做 bit-wise deterministic replay，在 23 张真实坏卡分析后生产识别 40 张缺陷 GPU；它诊断已发生故障，不提供持续预防。
- [[Seer-OSDI26]] — 利用 GRPO 同 prompt 组内长度和 token 模式相关性加速同步 rollout；32–256×H800、32 GB–1 TB reasoning models 是主要证据范围。
- [[Sereno-OSDI26]] — 在共享 DRAM 的手机上用 speculative draft 作为让出点，减少后台 Llama-8B 对前台应用的带宽干扰。
- [[Spain-OSDI26]] — 为容许近似误差的数值计算生成简洁证明；LLM 相关计算是应用之一，核心证据仍是数值程序和证明系统。
- [[SPEX-OSDI26]] — 在 SGLang-based Tree-of-Thought 中推测扩展分支；部分收益来自会改变搜索空间的 early termination，不能全算作语义等价加速。
- [[Syncopate-OSDI26]] — 为多 GPU GEMM/attention 自动生成通信分块内核；只测单机 4/8×H100 operator，尚无完整 LLM 或跨节点证据。
- [[VTC-OSDI26]] — 用虚拟 tensor 消除 DNN 数据搬运；在 A100/H100 的模型组件上验证，未覆盖完整多 GPU LLM 训练。

### OSDI 2026：LLM 是非确定性组件或辅助信号

- [[ECO-OSDI26]] — 模型生成代码优化候选，但 profiling、检索、测试、self-review、人类 review 和 canary 才组成接受链；少于 0.5% rollback 是整条流水线指标。
- [[Murakkab-OSDI26]] — 把模型、工具和工作流当可配置组件联合部署；24 小时双 workflow 是合成映射 trace，不能直接代表真实 agent 到达。
- [[NeuroSymbolicProof-OSDI26]] — 模型提出 Isabelle tactic，prover 和检查器执行、修复与剪枝；成功只表示给定 theorem 找到可检查 proof。
- [[Ote-OSDI26]] — 用 LLM judge 剪掉 SQL policy 分析中的无关分支，再由人工复核；有界 concolic analysis 不保证 view 完整或最紧。
- [[S4-FIFO-OSDI26]] — 学习控制面只为 S3-FIFO 选择少量全局参数，外部 LLM 主要帮助解释语义；它不是逐对象由 LLM 决策的 cache。
- [[SMARTTalk-OSDI26]] — 先把 SMART 数值序列压成短语，再让 LLM 判断故障；最佳 `F0.5` 不能证明建议对运维人员有用。
- [[Try-OSDI26]] — 把 LLM 生成的 shell command 视为不透明命令，用 semisolate 暂存副作用供用户选择提交；它防误操作，不是抵御主动恶意程序的安全沙箱。
- [[UCSan-OSDI26]] — LLM 可辅助生成 wrapper 或分析入口，但执行结果仍受编译、伪指针模型和分析范围约束。
- [[gigiprofiler-OSDI26]] — LLM 找应用自定义资源的候选事件，静态/动态分析负责去误报；模型单独判断的 false positive 高达 45%–60%。

### OSDI 2026：背景、benchmark 或相邻 workload

- [[Drs-NAS-OSDI26]] — LLM 只是模型架构搜索讨论中的相邻大模型类别；核心方法是推荐系统 NAS 的七维零成本代理。
- [[FlowANN-OSDI26]] — 向量搜索可服务 LLM/RAG 应用，但论文证据来自十亿规模静态 proximity graph、H20+CPU+2 TB DRAM，而非语言模型本身。
- [[Incr-OSDI26]] — 重放缓存可加速包含 LLM 开发命令在内的重复 shell workflow；核心正确性和性能对象是 command 的 stream、退出码与文件副作用。
- [[Oxbow-OSDI26]] — LLM 相关数据处理只是多组件文件系统可承载的 workload；论文核心是内核、用户态和计算存储设备间的读写路径。
- [[RT-OSDI26]] — 120 个 LLM 生成 bug 被纳入 shell 类型系统 benchmark；这验证 benchmark 构造，不表示 LLM 是运行时组件。
- [[Umap-OSDI26]] — LLM/ML 数据可通过文件后备矩阵访问 DFS；核心结论针对 mmap、cache protocol 与生产 job termination。

### 训练、验证与通用 ML 基础设施

- [[ByteRobust-SOSP25]] — 用 778K incident 提炼快速隔离、分级诊断、热更新 standby 和 checkpoint，在 9,600 GPU 三个月训练中达到 97% ETTR。
- [[Charon-MLSys26]] — 在原生 PyTorch/HuggingFace/vLLM 图上模拟训练和推理并行，端到端误差低于 5.35%；模型与 profiler 覆盖决定预测范围。
- [[DistCA-MLSys26]] — 将无参数 core attention 分配给独立 server pool，在 512×H200、512K context 训练上处理 quadratic attention straggler。
- [[DreamDDP-MLSys26]] — 在低带宽 geo-DDP 中按层部分同步并重叠通信，结论面向 Local SGD regime。
- [[FPRev-ATC25]] — 黑盒恢复浮点累加树，解释 NumPy/PyTorch/BLAS 与 Tensor Core 的跨平台不可复现来源。
- [[GCR-FAST26]] — 用 control/data 分离和 CPU shadow execution 改善 GPU checkpoint/restore；LLM 是大状态 workload 之一。
- [[GMI-DRL-ATC25]] — 用 sub-GPU 分区调度 DRL 的 simulator/agent/trainer；与 LLM agentic RL 有资源异质性类比，但评测对象是 DRL。
- [[Guard-MLSys26]] — 在线监控与离线 node sweep 管理 fail-slow GPU；生产预训练指标不能与 SDC 检测混为一类。
- [[Hawkeye-MLSys26]] — 在 CPU 上 bit-exact 复现多代 NVIDIA Tensor Core MMA，为可验证执行提供 oracle。
- [[HetRL-MLSys26]] — 在跨区 A100/L40S/L4 和 1–60 ms 延迟环境中联合调度 RL workflow；报告 20K GPU-hour 评测。
- [[HexiScale-MLSys26]] — 让异构 GPU 使用非对称 pipeline、TP 度、层数与 microbatch，交换 planner 复杂度换 MFU。
- [[MTraining-MLSys26]] — 为 512K context 的动态稀疏 attention 训练平衡 worker 和 step；32×A100 结果不能代表 dense attention。
- [[ProTrain-MLSys26]] — 自动搜索 ZeRO/offload/checkpointing 内存策略，降低手工配置成本；主要证据为单卡 A100 多模型。
- [[Quirk-Sparing-MLSys26]] — 用概率模型权衡 spare GPU/tray 与 checkpoint，适合早期集群 order-of-magnitude 决策，不是在线故障定位器。
- [[TrainVerify-SOSP25]] — 验证并行训练 DFG 与逻辑 DFG 等价；0.2–9.0 小时验证成本属于给定形式化假设和 plan。
- [[XPROF-MLSys26]] — 为 OpenXLA/JAX 统一 host/device profiling，千芯片规模开销少于 1%；可观测性覆盖由 instrumentation 决定。

### 推理、压缩和服务系统

- [[AttributionSparseActivation-MLSys26]] — 用归因分数选择稀疏激活，在特定模型、任务和 sparsity 下权衡质量、延迟与内存。
- [[BEAM-MLSys26]] — 联合 batching 与 DVFS 使用同一 SLO slack，在约 95% TTFT/TBT 达成率下节能；功耗最优点随 batch 改变。
- [[BLASST-MLSys26]] — 在 online softmax 中按阈值跳过 attention block；加速与稀疏率、阈值和质量边界绑定。
- [[BOUTE-MLSys26]] — 联合选择异构模型路由和 GPU 部署，在质量、P95 延迟与成本间做多目标优化。
- [[BatchLLM-MLSys26]] — 利用离线大批量请求全局可知的 prefix tree 重排；吞吐优先场景不能代表在线尾延迟服务。
- [[Behdin-SemanticJobSearch-MLSys26]] — 为 LinkedIn 单 token 语义职位打分做模型剪枝、上下文摘要和 prefill-only serving，接受少于 2% NDCG@10 下降换约 10 倍系统吞吐。
- [[CAGE-MLSys26]] — 用 curvature-aware 梯度修正低比特量化感知训练；它优化量化模型本身，不是 serving scheduler。
- [[CORE-MLSys26]] — 在 Pixel 7 上联合 CPU/GPU/MIF DVFS，说明移动 LLM 的 CPU 与内存开销不能忽略。
- [[CacheSlide-FAST26]] — 为位置漂移的 agent prompt 复用 KV，并部分重算 cross-attention；依赖专门位置编码训练和约 26% token 重算。
- [[DynaFlow-MLSys26]] — 用可编程设备内子图调度透明表达 overlap、fusion 与 split，并以 CUDA Graph 摊销动态执行成本。
- [[FlashAgents-MLSys26]] — 流式传递上游 token，让下游 agent incremental prefill 与 decode 重叠；收益依赖多 agent 的顺序依赖结构。
- [[FlashInfer-Bench-MLSys26]] — 用真实 shape/dtype/ragged trace 把 AI 生成 kernel 的评测与框架集成连接起来；kernel 正确率和端到端替换是不同指标。
- [[FlexiCache-MLSys26]] — 利用 attention head 的时序稳定性把部分 KV 放到主机；假设 head 稳定性跨请求和任务保持。
- [[HeteroInfer-SOSP25]] — 在 Snapdragon 8 Gen 3 上协同 GPU、NPU 与统一内存；速度受厂商 runtime、温控和高精度模型范围约束。
- [[IntAttention-MLSys26]] — 用整数 softmax 打通 INT8 attention 路径；Armv8 kernel 加速必须结合完整模型质量看。
- [[Kitty-MLSys26]] — 为 reasoning model 的 Key cache 混合 INT2/INT4，按通道敏感度保留质量；结论绑定所测 Qwen3/LLaMA3 任务。
- [[LAPS-MLSys26]] — 在 P/D 解聚后再按 prefill 长度分池，减少长短请求干扰；效果依赖长度分布和 pool 容量。
- [[LocalityAwareBeamScheduling-MLSys26]] — 在消费级 GPU 的 layer-wise offload beam search 中复用跨 token/beam KV，属于 step-wise beam 特化场景。
- [[MAC-Attention-MLSys26]] — 复用相似 query 的 attention summary，并修正边界与 tail；速度来自命中率和近似质量共同作用。
- [[METIS-SOSP25]] — 用 per-query LLM 估计剪枝 RAG 配置，再联合调 GPU batch；模型 estimator 自身也需要校准。
- [[MixLLM-MLSys26]] — 为少量敏感输出通道保留 8-bit、其余 4-bit；精度、显存和 int8 Tensor Core kernel 共同决定收益。
- [[MorphServe-MLSys26]] — 随 burst 和显存压力动态换入量化 layer、调整 KV，SLO 改善伴随可控质量退化。
- [[OPKV-MLSys26]] — 让稀疏 attention 的 critical token 与 KV page 布局对齐，减少 recall 开销。
- [[OptiKit-MLSys26]] — 把量化、统计评测、SLO benchmark 和 Bayesian tuning 串成企业优化流程，减少专家工时。
- [[PipelinedSharding-MLSys26]] — 在客户端极小 VRAM 下跨磁盘、CPU、PCIe 和 GPU 调度权重 shard；结论面向低并发本地推理。
- [[QFactory-ATC25]] — 延迟 dequantization 并自动搜索量化 kernel，集成 vLLM 的端到端 decode 加速低于单 kernel 倍数。
- [[RaidServe-MLSys26]] — 用 KV 备份、按需权重加载和不规则 TP 支持故障恢复；固定 SLO 下吞吐与恢复时间应一起看。
- [[Shannonic-MLSys26]] — 用极小 codec state 压缩低比特张量，在边云 Llama2-7B 传输中降低延迟；收益依赖链路而非纯计算。
- [[SuperInfer-MLSys26]] — 在 GH200 上围绕 NVLink-C2C 调度权重/KV rotation；不能外推到 PCIe offload。
- [[TokenWeave-MLSys26]] — 在 8×H100 上切分 token 并融合 AllReduce–RMSNorm，以重叠 TP 计算和通信。

### Agent、自动科研与模型评测

- [[SkVM-SOSP26]] — 把 skill 视为自然语言代码、LLM 视为异构 processor，用 capability-aware AOT/JIT、environment binding 和 runtime scheduling 改善跨 model/harness 执行；没有验证多小时任务的持久状态与恢复。
- [[ADR-MLSys26]] — 用 LLM/agent 检测企业 MCP 风险；benchmark 上的 false positive 口径不能代替生产告警队列。
- [[AgenticCache-MLSys26]] — 缓存具身 agent 的局部计划并后台校验，利用的是 plan locality，不是通用语义等价。
- [[AlphaEvolve-arXiv25]] — 用 LLM 生成可执行程序，再由 evaluator 和 population search 筛选；强证据集中在可自动评分问题。
- [[AstaBench-ICLR26]] — 统一工具与预算评测科学 agent；最佳完整任务成功率仍约 5%，暴露长程整合缺口。
- [[Auto-Research-arXiv25]] — 描述自动科研全生命周期愿景；原型量化证据主要来自 6 篇论文的 AutoReview。
- [[CausalEvolve-ICLR26]] — 用 LLM 结果描述与过程标签引导程序进化；部分任务改善不证明找到了真实因果机制。
- [[CausalGame-ICML26]] — 把取得高分与理解隐藏机制分开，显示通用 agent 仍常停留在试错搜索。
- [[Co-Scientist-Nature26]] — 多 agent 生成、反思、排序和进化假设，并由人类参与湿实验验证；不是无人监督实验闭环。
- [[DDR-Bench-ICML26]] — 要求 agent 自己决定查什么和何时停止；主动探索明显弱于直接回答已知问题。
- [[DeepScientist-ICLR26]] — 用 Bayesian optimization、记忆和 UCB 漏斗筛选候选；约 60% 抽样失败来自实现错误，结果由人类监督验真。
- [[EviGraph-arXiv26]] — 用类型化证据图和 rollback 管理科研状态；缺少组件消融时只能把收益归于整套系统。
- [[FunSearch-Nature24]] — 把冻结 LLM 当程序变异器，以可执行 evaluator 过滤；适用前提是问题容易自动评分。
- [[GEPA-ICLR26]] — 用执行轨迹和自然语言反馈演化 prompt，不更新权重；依赖固定模型已有反思能力和可靠反馈函数。
- [[HIPPOCAMPUS-MLSys26]] — 为 agent memory 同时索引 token 精确流与语义签名，减少检索成为端到端瓶颈。
- [[HeurekaBench-ICLR26]] — 从论文、代码和数据构建可核验科学问题；结果主要测到 workflow 和 scaffold 质量。
- [[ICL-EF-ICML26]] — 在离线基因扰动数据上模拟十轮实验反馈；这是已有数据重检索，不是实际 lab-in-the-loop。
- [[InnovatorBench-ICLR26]] — 把研究任务运行到超过 11 小时才达峰值，暴露 impatience、GPU 冲突和模板化推理。
- [[LLaMEA-KernelTuner-MLSys26]] — 让 LLM 进化生成 auto-tuning 搜索算法；最终性能仍由可执行 kernel benchmark 决定。
- [[Li-LongHorizonResearchEvaluation-arXiv26]] — 用确定性 verifier 分解数小时工程搜索；252 个 best-of-three 解中只有 3 个被人工保留为 task-level novel approach。
- [[Matrix-MLSys26]] — 用无状态 actor 和分布式服务扩展合成数据/agent workflow；吞吐证据需和 agreement/reward 正确性并列。
- [[MetaMuse-ICLR26]] — 用多样性反馈和外部刺激减少 LLM 的熟悉启发式偏好；证据是两个离线问题的 best-of-350。
- [[PaperBench-ICML25]] — 用可执行环境和 8,316 个 rubric leaf 评测论文复现，显示代码生成远强于执行和结果匹配。
- [[RD-Agent-Quant-arXiv25]] — 用多 agent 闭环搜索量化因子和模型；结果限于 Qlib 日频回测，不是实盘验证。
- [[RE-Bench-ICML25]] — 显示短预算 agent 可高频试错，但 8–32 小时人类优势扩大；不能从短跑外推长程自主研发。
- [[ResearchClawBench-arXiv26]] — 评测隐藏论文的证据链重建；最佳 21.5/100 不是新发现已被独立验证。
- [[Robin-Nature26]] — 把文献、候选排序、数据分析和湿实验串联；关键步骤仍有人类选题、协议和实验参与。
- [[SR-Scientist-ICLR26]] — 让 LLM 在数据分析、方程执行和反馈改写闭环中搜索；依赖强 BFGS evaluator、合成题和每题 1,000 次调用。

### LLM 作为其他系统中的模型、工具或术语

- [[NetKeeper-ATC25]] — 用 LLM 把自然语言和日志译为网络 DSL，再由 API 与优化器执行；94.8% 生产正确重配置仍需要配置验证边界。
- [[NewsShock-NBER26]] — 用 LLM embedding 表示金融新闻并分离可预测成分；这是语言表征应用，不是训练或 serving 系统证据。
- [[PLayer-FL-MLSys26]] — 以 foundation model/LLM 为潜在联邦 workload 背景，核心方法是按层 federation sensitivity 的跨 silo 个性化训练。
- [[RocketPPA-MLSys26]] — 用 LLaMA-3.1-8B 编码 RTL 并预测 PPA；准确性受 synthesis node/objective regime 约束。
- [[SysSpec-FAST26]] — 用形式化 spec 驱动 LLM 生成文件系统模块；生成准确率只在明确模块接口与测试 oracle 内成立。
- [[TimesFM-Fin-arXiv24]] — 研究时间序列 foundation model，而非语言模型；它暴露了 `foundation model` alias 的语义过宽问题。

## 已知局限 / 开放问题

- 建立同时覆盖模型质量/收敛、P99 SLO、能耗、故障恢复和资源成本的端到端 benchmark，避免只优化容易测的一列数字。
- 为模型、prompt、tool、runtime 和硬件版本定义可回放的 provenance；输出漂移与性能漂移都应能定位到具体版本变化。
- 明确每个 LLM 组件的接受契约：谁验证、验证什么、覆盖不到什么、失败是否可撤销，以及人工复核队列能承受多大误报。
- 把 production trace 的采样、匿名化和概念漂移作为一等问题；历史 trace replay 不能自动证明下一版模型和用户行为仍受益。
- 对 agentic RL 和自动科研系统联合衡量基础设施吞吐、模型学习效果、evaluator 偏差与最终证据质量，防止更快地产生更多无效候选。
- 将过宽的 `foundation model` 术语与 LLM 机制分开；时间序列、视觉和多模态 foundation model 可以共享系统问题，但不能默认共享生成语义或验证方式。
