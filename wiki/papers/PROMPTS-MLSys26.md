---
type: paper
name: PROMPTS
full_title: "PROMPTS: Performance Optimization via Multi-Agent Planning for LLM Training and Serving"
authors: [Yuran Ding, Ruobing Han, Xiaofan Zhang, Xinwei Chen]
venue: MLSys
year: 2026
tags: [llm-training, auto-tuning, sharding, multi-agent, tpu]
source_pdf: "[[03afdbd66e7929b125f8597834fa83a4.pdf]]"
source_md: "[[03afdbd66e7929b125f8597834fa83a4]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# PROMPTS: Performance Optimization via Multi-Agent Planning for LLM Training and Serving (MLSys 2026)

> **一句话总结**：在 TPU 大规模训练/serving 中，ICI-mesh 分片决定 memory fit 与通信上限；PROMPTS 用 Analyzer（读 [[XPROF-MLSys26|XProf]] 瓶颈）+ Proposal（[[RAG]] 检索历史案例与专家文档）一次调用给出 top-3 方案，8 个生产 workload 上 100% 覆盖专家配置、87.5% top-1 一致、搜索 effort 平均少 50.25 次、吞吐最高 +434%，且 7/8 案例无需历史库精确匹配。

## 问题与动机

大规模 LLM **训练与 serving** 的第一步往往是：在固定硬件预算下，为 hybrid parallelism（data / model / sequence / pipeline 及其组合）选出可编译、可运行、且接近性能上限的 **sharding 配置**。这个搜索空间组合爆炸——同一模型在 2D vs 3D Torus、不同 TPU 代际、不同 batch/seq 长度下，最优 data/model/seq 轴映射完全不同；性能 trade-off 也非线性（加 model parallel 降 per-chip 内存但增 collective 流量）。

工程师常规路径是 **profiling → 读 trace → 手工调 ici_mesh → 再跑实验**，慢且依赖资深 performance engineer。另一类方案是 **黑盒搜索**（Vizier、FlexFlow/Alpa/Metis/Sailor 一类 structured search）：sample efficiency 差，换模型/硬件/框架往往要重建 search space；学到的 surrogate 也 brittle。第三类是 **纯诊断工具**（dPRO、Lumos）：能回答「哪里慢」，但不自动生成可执行的 sharding proposal，诊断到方案之间仍有「专家脑内推理」缺口。

论文 claim：需要把 **专家诊断–提案推理** 自动化，作为与黑盒搜索 **正交的一层**——先剪枝到高潜力子空间，再让搜索或人工验证少量候选。PROMPTS 聚焦 **ICI-mesh sharding**（Inter-Chip Interconnect 逻辑 mesh 上 data/model/seq 轴映射），因为这是 TPU slice 内决定 **能否放下模型（memory fit）** 与 **通信拓扑** 的关键旋钮；batch size、compiler flag 等维度暂固定，避免 confounding。

## 关键观察 / 隐含假设

- **观察 1：ICI-mesh 是 TPU 上性能的天花板旋钮，且与硬件拓扑强耦合。** 论文把 ici_mesh 视为决定 feasibility（OOM、collective layout）和 performance ceiling 的首要配置；2D Torus 与 3D Torus 上最优通信模式不同，同一 sharding 换拓扑可能完全失效（Case 4 拓扑变更）。
  - **依赖假设**：workload 已能在某 baseline 配置下编译运行，优化目标是 **在同框架（JAX/GSPMD 类）内调 logical mesh 轴**；batch、rematerialization、compiler flag 已固定或接近最优。
  - **可能失效场景**：瓶颈其实在 batch size、offload、算子 fusion 或 prefill/decode 分离时，只调 ici_mesh 收益有限；GPU/NVIDIA 栈上 mesh 语义与 TPU 不同，结论不能直接迁移。
- 观察 2：黑盒搜索在 sharding 子空间里极度 sample-inefficient，而专家式「先诊断瓶颈类型再改轴」可 one-shot 命中。 论文对比 Vizier 定义的 exhaustive valid search space（最多 165 个配置，Case 3），agent 在 7/8 case 上 第一次试验 即找到工程师采纳配置；平均少评 50.25 个配置，双方最终平均吞吐提升同为 115.61%。
  - **依赖假设**：profiler（XProf KPI + HLO + roofline）能可靠区分 compute / HBM / communication 主导瓶颈；知识库中的原则（如「通信瓶颈时降 model parallel、增 data parallel」）在目标 regime 仍成立。
  - **可能失效场景**：profiler 噪声大、trace 不完整或多瓶颈叠加时，Analyzer 误判会级联到 Proposal；search space 若包含大量无效配置，compiler reject 率上升（论文平均 compilability **69%**），需要多轮 invocation。
- 观察 3：泛化主要来自原则推理而非历史案例精确匹配。 8 case 中仅 Case 1 有历史库精确匹配，7/8 需 first-principles 推理；Case 2 HBM 优化甚至不在工程师历史数据库中，agent 仍提出有效 model parallel 方案。
  - **依赖假设**：不同 LLM 共享相似 execution primitive（collective、matmul、attention），sharding 约束可跨模型迁移；扩展新模型/硬件只需 **增补 RAG 文档**，不必重做 search algorithm。
  - **可能失效场景**：zero-knowledge stress test（Qwen 32B on tpu7x，故意 withheld 文档）显示 agent 只能做「初级症状识别」——tensor relayout root cause、平台特有 sparse core offloading、all-gather+slice 反模式等需专家级上下文；知识缺口会直接表现为错误建议。
- **假设 1：TPU compiler 交叉编译是足够强的可行性 oracle。** 无效 mesh / OOM 在 compile 阶段 reject，无需额外 instrumentation；Proposal 可大胆探索，靠 compiler fail-fast 过滤。
  - **证据强度**：中。Case 4 证明 compiler 能抓 OOM，但 agent top-1 仍可能选 **步时更优却 OOM** 的配置，说明 compiler 校验晚于 agent 排序逻辑，不能替代 memory-feasibility reasoning。
- **假设 2：单次 invocation、固定 top-3 batch 足以覆盖生产级最优解。**
  - **证据强度**：中–强。8/8 覆盖专家解、87.5% top-1 命中，但是 **8 个精心选取的 regime coverage case**，非随机采样；统计泛化性有限。

## 核心方法

**PROMPTS**（PeRformance Optimization via Multi-Agent Planning for LLM Training and Serving）是基于 Google ADK 的 multi-agent 框架，把 performance engineering 流程拆成 **诊断 → 提案 → 审计**：

### Multi-agent 工作流

- **Coordinator Agent**：接收 experiment ID，顺序调用 Analyzer 与 Proposal，路由结构化中间结果。
- **Analyzer Agent**：通过工具调用 [[XPROF-MLSys26|XProf]] API， ingest KPI（device duty cycle、communication overhead、step time）、HLO operation profile、on-device roofline，并结合实验配置 metadata，输出结构化瓶颈报告——分类为 **compute / memory (HBM) / communication**，并列出 top HLO ops。
- **Proposal Agent**：以瓶颈报告为 query，对两类知识源做 semantic retrieval（cosine similarity embedding）：(1) 结构化 **历史优化案例库**；(2) **专家撰写技术文档**（如 scaling 原则、特定 TPU 架构策略）。综合检索结果生成 **3 个** ici_mesh 配置，每个附文字 justification 与引用证据。
- **Sharding Memory**：文件化持久化 tool calls、中间 LLM 输出与用户输入，提供可审计 trail。

### 设计不变量与扩展性

对给定 workload，characterization、agent instruction、knowledge base 固定；输入为 profiling 数据 + baseline 配置。随机性主要来自 LLM query formulation 与 proposal generation，论文称对最终 ici_mesh 建议 **material impact 不大**。扩展新硬件/模型时 **不改 agent 架构**，只增补 RAG 文档——与黑盒方法需重建 search space 形成对比。

### 与现有系统的关系

PROMPTS 定位为 GSPMD / Partir 等 **hybrid partitioning** 系统中「人工 annotation 阶段」的自动化替代品，与 Alpa、FlexFlow、Vizier、Metis、Sailor 等 search-based tuner **正交**：先 reasoning-prune，再 fine-grained search。当前 scope 明确排除 joint optimization（batch size、offloading、rematerialization、compiler flags），但框架声称可通过扩展知识库 heuristics 增量接入。

### 三类瓶颈的推理模板（定性验证）

- **Compute-bound**（Case 1，duty cycle 99.7%，comm overhead 2.6%）：trade seq parallel for data parallel（seq 8→4，data 8→16）以更好饱和算力。
- **HBM-bound**（Case 2）：增加 model parallelism（引入 4-way）shard 大模型，缓解 per-chip 复制压力。
- **Communication-bound**（Case 3，top ops 全是 collective）：减半 model parallel、加倍 data parallel（model 4→2，data 4→8）降低 all-reduce 流量。

## 设计取舍

- **收窄优化维度换可解释性与 sample efficiency**：只动 ici_mesh，固定 batch/compiler，使 claim「reasoning 剪枝 sharding 子空间」可验证；代价是 **无法声称端到端系统最优**，真实部署还需第二轮 tuning。
- **LLM + RAG 换黑盒 surrogate**：获得 natural-language justification 与快速适配新文档，但引入 **69% 平均 compilability**、LLM 幻觉与平台例外知识缺失风险；依赖 compiler 作 safety net。
- **Top-3 小 batch 换 engineer 认知负担**：一次给 3 个候选便于对比，而非输出全排序 search result；若 3 个都偏了需重新 invocation（论文每 workload 仅 1 次 invocation）。
- **Profiler-driven 换 upfront cost**：无需额外 instrumentation（JAX 自动采 XProf），但 **完全依赖 post-run trace 质量**；冷启动、无 baseline 的 generative case（Case 4/6）信息更少，更考验知识库泛化。
- **Production case study 换学术 benchmark 可复现性**：8 个匿名生产 workload 代表性强，但外部读者无法复现实验；结论可信度依赖作者内部验证流程。

## 实验与结果

评估强调 **regime coverage** 而非统计抽样：8 case 跨越 TPU v5p/v5e/v6e/tpu7x、2–2048 chips、2D/3D Torus、dense + [[MoE]]、pretrain / SFT / serving / audio，batch 2–256。

- **Solution coverage**：**8/8** workload 的 top-3 建议中包含工程师已采纳的生产配置。
- **Ranking**：**87.5%**（7/8）case agent **top-1** 即生产配置；**7/8** 第一次试验即命中最优。
- **搜索 effort**：相对 exhaustive blackbox valid space，agent 平均只评 **1** 个配置即找到专家解；Fig.1 显示平均节省 **50.25** 次试验；最大 blackbox space **165** configs（Case 3）。
- **吞吐提升**：相对 suboptimal baseline，步时缩短对应吞吐提升 **40–434%**；峰值 **+434.75%**（Case 5 专有 [[MoE]]）；Case 6 serving +182.86%；Case 7 pretrain +104.16%。
- **效率**：单次 invocation **<1 min**；工业黑盒搜索因资源分配与编译常需 **5 min–数小时**（论文用配置数而非 wall-clock 作 cleaner metric）。
- **Compilability**：建议配置平均 **69%** 可编译，但仍足以完成任务；Case 4 用 cross-compilation reject OOM 提案。
- **泛化**：**7/8** 无历史库精确匹配；Case 6 无初始 ici_mesh 仍 one-shot 生成有效配置；zero-knowledge test 下 agent 能做症状级诊断但距专家有明确知识 gap。

## Critical Analysis

### 论证链条

论文主链条是：**sharding 空间巨大且黑盒搜索 knowledge-blind（§3.2）→ 专家先诊断瓶颈再改 parallel 轴（§3.4）→ Analyzer/Proposal 两阶段 agent 复现该流程（§4）→ 8 个生产 case 上 one-shot 覆盖专家解且搜索 effort 降 1–2 个数量级（§5）**。链条在「**剪枝 sharding 子空间**」这一 scoped claim 内较闭合：qualitative case（Cases 1–3）展示瓶颈分类与轴调整方向一致，与 quantitative coverage/ranking 指标互相支撑。

较弱环节在于把 **8 个 curated case** 外推为「可扩展的 AI-driven performance engineering 方法论」。论文自己也承认是 regime coverage 而非 random sampling；87.5% top-1、100% top-3 是在 **已知专家答案存在** 的 retrospective 评估里量的——更像「agent 能否复现已有专家结论」，而非「agent 能否在未知 workload 上持续发现新最优」。另外，blackbox baseline 定义为 **Vizier search space 的 exhaustive 配置数**，不是实际跑 Vizier BO 的 sample complexity；agent 与 blackbox「平均提升同为 115.61%」只说明最终命中点质量相当，不能证明 agent 在 **同等 wall-clock 预算** 下总优于调参后的 Vizier。

Case 4 是重要边界反例：agent 诊断方向对，但 top-1 在 **8×16 拓扑** 下把步时优化置于 HBM 硬约束之上导致 OOM；成功配置需更高 seq parallel 换 memory headroom。说明 **论证链条在 feasibility vs performance 二阶段决策上仍有断点**——compiler 能事后 reject，但不能保证 agent 排序优先可行解。

### 假设压力测试

- **硬件/软件栈绑定**：实验全部在 **Google TPU + JAX + XProf + GSPMD 式** 环境；ICI-mesh 轴语义、compiler 行为是 core assumption。迁到 [[Tensor-Parallelism]]/[[Pipeline-Parallelism]] 主导的 GPU Megatron/DeepSpeed 栈，agent 工具链与知识库需重写，论文未提供迁移证据。
- **Profiler 质量**：多瓶颈叠加、async collectives 隐藏、或 input pipeline 主导时，单一 KPI 分类可能过度简化；论文承认 noisy/incomplete trace 会降低诊断准确度，但未量化敏感度。
- **知识库维护成本**：扩展性 claim 依赖 **持续策展的专家文档与案例库**；zero-knowledge test 表明缺 tpu7x 特性文档时 agent 会给出通用但错误的 fusion/overlap 建议。这与「换硬件只需加文档」在工程上成立，但 **文档编写本身仍是专家劳动**，可能抵消部分自动化收益。
- **LLM 稳定性**：框架称 stochasticity 影响不大，但仅 8 case × 1 invocation；无多次采样方差报告。生产环境若 top-1 错误而 top-2/3 正确（12.5% case），工程师是否总能识别 **论文未讨论**。
- **固定 batch/compiler**：许多生产优化恰恰是 batch size 与 rematerialization 联动调整；论文 scope 内无法验证 joint space 上 reasoning 是否仍 one-shot 有效。

### 实验可信度

- **Workload 代表性**：8 case 覆盖模型类型、规模、生命周期维度广，但是 **内部生产匿名 case**，外部无法复现；作为 case study 可信，作为 benchmark 不可比。
- **Baseline 公平性**：对比对象是 **专家已找到的最优解** 与 **exhaustive valid config count**，不是同期运行的 Alpa/Metis/Sailor；未证明对「正在运行的自动 tuner」的 online 优势。与人工 expert 对比公平（同一生产 ground truth），但与其它 ML 系统论文常用的 open benchmark 不对齐。
- **Ablation**：缺少对 RAG 两源（历史库 vs 文档）、Analyzer 各 tool、embedding model、knowledge 规模的系统 ablation；7/8 无精确匹配说明 RAG 检索不是简单 memorization，但不能分解 **LLM 预训练知识 vs 私有知识库** 各自贡献。
- **Metric 覆盖**：主 metric 是 **throughput / step time** 与 search effort；无 dollar cost、无 tail latency、无 multi-tenant 干扰、无训练收敛正确性检验（假设 sharding 只影响性能不影响 numerics）。Compilability 69% 说明 proposal 质量不均匀，但论文未报告「非 top-1 候选」的质量分布。

### 系统性缺陷

- **尾延迟与 SLO**：serving case（Case 6）只报平均吞吐提升，未拆 prefill/decode TTFT/TPOT 尾部分布；论文未讨论。
- **故障恢复与可观测性**：Sharding Memory 提供 audit trail，但是 file-based log；无与 CI/CD、experiment tracker 集成，也无 agent 错误时的自动 rollback 策略。
- **资源隔离**：2048-chip job 的试验成本极高；agent 错误建议若直接上生产集群，失败试验的 **机会成本** 论文未量化（依赖 compiler fail-fast 降低但非零）。
- **安全与治理**：RAG 知识库含内部优化案例与 proprietary model 信息；多租户下 knowledge 泄漏、prompt injection 对 Proposal Agent 的影响 **论文未讨论**。
- **与 search 的衔接**：声称与黑盒 search 正交，但实验未展示「PROMPTS 剪枝后 + Vizier」联合曲线的 additive gain；工程上是否真比单独 tuner 更省总时间，证据不完整。

## 局限与 Future Work

- **局限 1**：优化 scope 限于预定义 ici_mesh 维度，未联合 batch size、offloading、rematerialization、compiler flags；论文承认是 staged design，非架构硬限制。
- **局限 2**：依赖 post-run XProf trace 质量；profiler-driven 方法的共同边界，噪声 trace 会降低 Analyzer 可信度。
- **局限 3**：Proposal Agent 倾向 **孤立 HLO op 分析**，难识别 sequential anti-pattern（如 all-gather 后立即 slice 可改 reduce-scatter）；Case 4 显示 **memory feasibility 排序** 仍不完善。
- **局限 4**：评估样本少（8 case）、单次 invocation，缺乏 multi-seed 稳定性与开源可复现 benchmark。
- **Future work 1**：引入 **Evaluator–Verifier loop**——Verifier 用 profiler 证据与硬约束（topology legality、divisibility、memory）确定性检查推理；Evaluator 用 cross-compilation + 轻量 test run 验证；多样本 proposal + 确定性 scoring（feasibility 优先）提升跨 run 稳定性。
- **Future work 2**：输入 **完整 computational graph**，支持 per-layer sharding、算子 fusion/layout 决策，识别跨 op 反模式。
- **Future work 3**：扩展知识模块到 joint optimization 轴，并在真实 trace 上测量「PROMPTS + search」的 end-to-end wall-clock 与 dollar cost，而非仅 valid config count。

## 相关

- **相关概念**：[[RAG]]、[[MoE]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Expert-Parallelism]]
- **依赖工具**：[[XPROF-MLSys26]]
- **同类系统**：Alpa、FlexFlow、GSPMD、Partir、Vizier、Metis、Sailor、dPRO、Lumos
- **相近方向**：[[LLaMEA-KernelTuner-MLSys26]]（LLM 驱动 auto-tuning）、[[OpenHands-SDK-MLSys26]]（agentic ML 系统）
- **同会议**：[[MLSys-2026]]
