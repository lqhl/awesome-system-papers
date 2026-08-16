---
type: paper
name: Murakkab
full_title: "Murakkab: Resource-Efficient Agentic Workflow Orchestration in Cloud Platforms"
authors: [Gohar Irfan Chaudhry, Esha Choukse, Haoran Qiu, Íñigo Goiri, Rodrigo Fonseca, Adam Belay, Ricardo Bianchini]
venue: OSDI
year: 2026
tags: [agentic-workflow, cloud-orchestration, resource-management, slo, llm-serving]
source_pdf: "[[osdi26-chaudhry.pdf]]"
source_md: "[[osdi26-chaudhry]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Murakkab：云平台中的资源高效 Agent Workflow 编排（OSDI 2026）

> **原题**：Murakkab: Resource-Efficient Agentic Workflow Orchestration in Cloud Platforms

> **一句话总结**：Murakkab 让开发者只描述任务和依赖，再根据离线画像、请求 SLO、流量和硬件供给，联合选择 workflow 参数、模型、工具、并行方式、实例数和路由；在论文构造的 24 小时双 workflow trace replay 中，最优策略相对手工 LangGraph 把 GPU 从 2,568 降到 912、能耗从 82.1 MWh 降到 22.1 MWh、成本从 211.7K 美元降到 47.2K 美元。

## 问题与动机

一个 agent workflow 可能同时调用 [[LLM]]、视觉模型、语音识别、目标检测器和代码执行器。开发者通常用 LangGraph、LlamaIndex 等框架把调用顺序、模型名字、agent 数量和迭代次数写进命令式程序；云平台则在另一层独立部署模型，并把每次模型调用当作普通 API 请求。于是三类决定彼此看不见：

- workflow 层决定有哪些步骤、是串行还是并行、要不要 reviewer、要跑几轮；
- agent 层决定每一步用什么模型、处理多少帧、生成多少候选；
- infrastructure 层决定 GPU 类型、tensor parallelism、实例数和扩缩容。

这些决定互相影响。论文的 Video Q/A workflow 会先抽帧、语音转写和目标检测，再把结果交给多模态模型；10 帧加 STT 的 Gemma-3-27B 配置达到最高 66.2% accuracy，却也产生最多 token。Code Generation workflow 中，同一 workflow 配置换成 DeepSeek-Qwen-32B 后，中位生成量约 20K token，而 Gemma-3-27B 约 2.5K；增加 debater 或 round 也不保证单调提高质量（§2、图 1–4）。因此，单独优化某一层很容易选出端到端成本高、延迟超标或质量不足的组合。

Murakkab 的出发点是把整个 workflow 当成一个可优化的计算图。开发者声明“做什么”和数据依赖，平台决定“怎么做”和“放在哪里做”，形式上接近 [[Serverless]]：应用逻辑与执行配置分开，运行时可以随请求 SLO、负载或 GPU 供给变化而重新配置。

## 关键观察 / 隐含假设

- **观察 1：workflow 的配置空间大，而且收益不单调。** Video Q/A 的帧数、STT 开关和模型会共同改变 accuracy、token 数与延迟；dynamic coding 中，reviewer 对一部分配置有帮助，对另一部分反而有害，两个 writer 也没有一个始终占优（图 2、图 10）。
  - **设计含义**：不能用固定规则说“大模型一定更好”或“review 一定值得”，需要保留多个实测 operating point。
  - **可能失效场景**：若新 prompt、tool 或输入域不在画像范围内，旧 operating point 的质量和负载预测可能失真。
- **观察 2：workflow、model 和 hardware 分开画像可以复用。** workflow 画像记录每种逻辑配置的质量、端到端延迟和 executor load；model 画像再把 token/load 映射到某个模型、GPU 和并行配置的 TTFT、TPOT、吞吐、能耗和价格（§3.3）。
  - **隐含假设**：二者可以近似组合，跨 executor 的排队、cache 干扰和 tool tail 不会破坏这一分解。
- **观察 3：按峰值 provision、按平均值 route，可以共享余量。** 不同 workflow–SLO 类别的峰值未必同时发生，相同模型实例可以承接多个类别的平均负载；表 2 中 multiplexing 在独立优化之上又减少 21.6% GPU、20.2% 能耗和 17.4% 成本。
  - **隐含假设**：平台允许跨 workflow、甚至跨 tenant 共享模型实例，并能满足隔离与数据治理要求。
- **观察 4：动态 agent 也存在可选择的 operating point。** LiveCodeBench-v5 上，dynamic coding 的 Pareto frontier 横跨约一个数量级的生成 token 和约 2 倍 pass@1，部分请求通过公开测试后早停，部分请求跑满迭代上限（§4.4、图 10）。
  - **证据边界**：这一节只实测 workflow 配置选择；论文明确说硬件配置与 autoscaling 已在别处测过，并未在 dynamic coding 上重新做端到端联合实验。
- **假设 1：质量可以被 benchmark 和 SLO tier 表示。** VideoMME、HumanEval、Math 等有 ground truth；没有公开数据时，论文建议用开发者数据集或用户反馈补画像。
  - **风险**：开放式 agent 的正确性、安全性和主观质量不一定能压成单一 accuracy。
- **假设 2：provider 控制完整栈。** Murakkab 需要看到 DAG、候选模型、硬件、负载和资源池，还要能跨层改配置。
  - **风险**：第三方模型 API、不同安全域、固定采购合同或 tenant 禁止 multiplex 时，优化空间会明显缩小。

## 核心方法

### 1. 从自然语言任务生成逻辑 workflow

开发者声明 task、subtask、依赖、输入输出和可选约束，不绑定具体模型或硬件。Orchestrator 使用具备 tool-calling 能力的 LLM，把 task 映射到 executor library 中已有的 LLM executor、结构化组合器或传统工具；若没有匹配 executor，就要求开发者先 onboard 一个。它还检查相邻节点的输入输出类型，类型不匹配时重新生成，仍失败才交回开发者处理（§3.2）。

产物是请求无关的 logical DAG。运行时也允许用户只给自然语言 query、输入和 SLO，由 orchestrator 临时拆成 subtask，再复用已有 executor 或 workflow。这里的关键边界是：LLM 生成 DAG 的正确性依赖 executor library、类型检查和开发者反馈，论文没有单独测量生成错误率。

### 2. 两层离线画像

**Workflow profile** 枚举 workflow knob 和 executor knob。例如 Video Q/A 会改变抽帧数、STT 开关和模型，Code Generation 会改变 debater 数与 round 数。每个配置记录 benchmark accuracy、端到端 latency，以及各 executor 的 prompt/completion token 等 load 分布。

**Model profile** 以 `(model, hardware, software/parallelism)` 为单位，记录不同 load 下的 TTFT、TPOT、throughput、energy per token 和 GPU-hour cost。新模型或新 accelerator 接入时单独画像，不必重新跑所有 workflow。外部 GPT-4o、Claude 之类 API 也可作为“无 GPU、固定 token 价格/延迟、有 rate limit”的 profile 进入同一个优化问题（§3.3）。

论文称 profiling 每个配置只需做一次并可摊销，但没有给画像总 GPU-hour、搜索覆盖率或更新成本。画像也不是永久真值：论文建议周期性吸收新 benchmark、request-response 和用户反馈。

### 3. MILP 联合决定配置、资源和路由

每个 optimization epoch，混合整数线性规划（MILP）读取四类输入：workflow profiles、model profiles、下一 epoch 中每个 workflow–SLO 类别的预计到达率，以及不同 GPU/spot resource 和 tenant budget。

它同时决定：

1. 每个 workflow–SLO 类别使用哪组 workflow knob；
2. 每个 executor 选择哪个模型或工具；
3. 选择哪个 GPU 与 parallelism profile，并启动多少实例；
4. 各类请求以什么比例路由到哪些实例，从而实现跨 workflow multiplexing。

约束要求候选配置满足画像中的 quality/latency SLO、实例容量覆盖预计 peak demand、总 GPU 数不超过资源池。目标可以是最小 energy、最小 dollar cost，或在 cost budget 内最大化 aggregate accuracy。实例数按预测峰值加余量配置，路由比例则按平均负载优化共享率。附录默认统一 buffer factor `α=1.15`；Gurobi 求解 time limit 为 300 秒（附录 A.5）。

### 4. Registry、周期重优化与快速 autoscaler

求解结果变成 executable workflow，写进 workflow registry。请求到来时，runtime 按 workflow ID 和 SLO tier 查表并调度 DAG。后台 optimizer 默认每 60 分钟重算一次；它用上一批 epoch 的状态预测下一批流量。短时间内的 token 波动由 per-model autoscaler 处理：根据 profile 中的 throughput–latency 边界设阈值，在秒到分钟级 scale out，保留 spare resource，偏差很大时提前触发重优化（§3.4）。

论文把 SLO 分为 best、good、fair、basic，但这些名字不是用户语义上的绝对等级，而是所有可用配置中 accuracy/latency 的最佳值、95th、80th 和 50th percentile。实验的“满足 SLO”因此表示满足这套内部 tier。

### 5. 感知 DAG 关键路径的放置

Murakkab 不只决定模型实例，还看 DAG critical path。论文构造“从视频提取学生代码，同时生成参考答案”的并行请求：Gemma-3-27B 固定用 4 张 A100；OmDet 与 Whisper 都放 GPU 时总计 6 张，满足 30 秒 SLO；两者都放 CPU 时只用 4 张，却因 OmDet 太慢而超时；只把 Whisper 放 CPU、OmDet 留在 1 张 A100 时共用 5 张并满足 SLO（§4.6、图 12）。这说明“能否 offload”要看并行重叠和 critical path，不能只看单组件速度。

## 设计取舍

- **声明式接口换统一优化。** 平台能替换模型、工具和硬件，但开发者必须接受 executor library 和 logical DAG 的表达范围；有 side effect、transaction 或人工审批的 workflow 语义更难安全重配。
- **画像搜索换在线稳定性。** MILP 不必在线试错，代价是画像成本、离散化和 drift。准确度画像一旦错，系统可能“形式上满足 SLO，实际质量却下降”。
- **集中全局视野换隔离复杂度。** 跨 workflow multiplexing 是主要收益来源之一，也扩大了 trust domain、故障半径和 tenant fairness 问题。
- **两层时间尺度。** 小 autoscaler 处理秒级波动，大 optimizer 处理配置与资源变化；这降低求解频率，却可能在 profile、forecast 和 autoscaler 三者交界处重复预留资源。
- **频繁重配换响应速度。** 论文假设新 VM、软件和模型上 GPU 共需 20 分钟。epoch 太短时 transition buffer 和 [[KV-Cache|KV cache]] 损失变大；太长时 forecast 失准。60 分钟只是该 trace 下的折中，不是通用常数（§4.7）。

## 实验设计

主要实验运行在 Azure A100/H100 VM：每台分别有 8×A100 80GB 或 8×H100 80GB，模型服务使用 [[vLLM|vLLM]] 0.9，语音服务用 speachesai 0.7，目标检测用 OmDet。主 workload 是 Video Q/A 和多 agent Code Generation；附录加入 Math Q/A，dynamic coding 使用 LiveCodeBench-v5 hidden tests。

论文明确说没有公开的 production agent workflow trace，因此使用 Azure [[LLM-Inference|LLM inference]] service 在 2024 年 5 月 15–16 日的 24 小时 chat/coding trace近似到达过程：chat request 映射为 Video Q/A，coding request 映射为 Code Generation。这是 **production-scale arrival trace 的合成映射**，不是 Murakkab 在真实 agent 平台上的线上部署。

四个策略为：手工选择 Gemma-3-27B+A100 的 LangGraph（LG）；给 LG 加上与 Murakkab 相同的自建 autoscaler；每个 workflow–SLO 独立优化的 Mkb Opt；再加入跨类别共享实例的 Mkb Opt+Mult。所有策略按 profile 中 p90 token load provision。LG 是作者手工调到兼顾质量和成本的 baseline，不是 LangGraph 原生 autoscaling 产品。

## 实验与结果

- **单 workflow 的大幅节省往往来自改变 SLO，而非同质量加速。** Video Q/A 从 66.2% best 到 64.4% good 时，energy 从 5.1 降到 3.9 MWh，cost 从 18.5K 降到 14.3K 美元；放宽到 61.4% fair 后 cost 为 6.9K。Code Generation 跨 accuracy tier 的 energy 范围是 312→2 MWh、cost 是 820K→25K 美元；best→good 约少 10.5× energy 和 8.7× cost，主要因为从 DeepSeek-Qwen-32B 换成 Gemma-3-27B（§4.2、图 7–8）。
- **同一组 good-tier mixed SLO 下，联合优化和 multiplexing 显著降低资源。** 24 小时 replay 中，70% request 为 high-accuracy、30% 为 low-latency。LG、LG+Auto、Mkb Opt、Mkb Opt+Mult 分别使用 2,568、2,472、1,164、912 张 GPU；energy 为 82.1、80.6、27.7、22.1 MWh；cost 为 211.7K、112.3K、57.2K、47.2K 美元（表 2）。LG+Auto 已把成本降约 1.8×，但 GPU 数和 energy 变化很小；进一步收益来自换 workflow/model 配置和共享实例。
- **dynamic coding 的配置前沿证明“一套固定配置”不够。** LiveCodeBench-v5 中，Pareto frontier 从约 0.19 到 0.40 pass@1，生成 token 跨约一个数量级；较小 writer 覆盖低成本区，较大 writer 贡献部分最高质量点，reviewer 并非总有帮助（§4.4、图 10）。这部分没有重新测 GPU、autoscaling 或端到端成本。
- **硬件供给变化时可以在同一 SLO 下重映射。** 固定提供 2,000 张 A100、把 H100 availability 从 0 扫到 500 时，energy objective 的方案从 1,292×A100、24.7 MWh 变为最多使用 495×H100、约 11 MWh，并相应减少 A100（§4.5、表 3）。
- **DAG placement 的 4/5/6-GPU case 展示 critical-path 价值。** OmDet+Whisper 全 GPU 用 6 张并达标；全 CPU 用 4 张但违反 30 秒 SLO；OmDet 用 GPU、Whisper 用 CPU 共 5 张并达标。证据只来自一个组合请求和一组模型配置（§4.6、图 12）。
- **重优化频率存在三个区间。** 20–60 分钟主要受 transition/buffer cost 影响，60–180 分钟在该 trace 上较平衡，180 分钟以上 forecast uncertainty 增大；若完全没有 autoscaler，240 分钟 epoch 的 demand under-prediction 接近 15%。这个 15% 是“可能无法服务的预测需求”，不是实验中实际丢弃了 15% 请求（§4.7、图 13）。Math-500→未见过的 MathEval 只验证了同一数学领域内 model accuracy 排序和 token 分布相似（§4.8、图 14）。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| 在设定 SLO 下，联合 workflow/model/resource 优化明显优于固定 LangGraph | 表 2：2,568→912 GPU，82.1→22.1 MWh，211.7K→47.2K 美元 | 两个 workflow；Azure chat/coding arrival 被映射成 agent 请求；trace replay | 强 |
| multiplexing 在独立优化之外仍有收益 | 表 2：Mkb Opt→Opt+Mult 再少 21.6% GPU、20.2% energy、17.4% cost | 允许跨 workflow 共享相同模型实例 | 强 |
| 动态 workflow 需要按请求选择配置 | 图 10：token/pass@1 frontier，writer/reviewer 无统一赢家 | LiveCodeBench-v5；只测 workflow knob，不含硬件联合评测 | 中 |
| profile 可迁移到未见输入 | 图 14：Math-500 与 MathEval 的 accuracy 排序和 token PDF 相似 | 单一数学领域、两个相近 benchmark | 弱到中 |
| runtime 能应对 load 和 resource availability 变化 | 图 11、表 3、图 13 | trace-driven epoch replay；20 分钟 provisioning 与 EWMA `α=0.5` 为假设 | 中 |

## 批判性分析

### 论证链条

论文先用三个 workflow 展示“同一逻辑存在很多质量—资源 operating point”，再让 declarative DAG、两层 profile、MILP 和两级 runtime 分别解决可见性、搜索、全局分配和短期波动，机制与问题对应得比较完整。表 2 也把 fixed、autoscaling、per-workflow optimization 和 multiplexing 分开，说明最大收益不是单靠 autoscaler 得到的。

但不同数字不能混读。表 2 是同一 good-tier workload 下的 baseline 比较，最能支持“系统优化减少资源”；§4.2 的 10.5× energy 和 8.7× cost 则是从 best 放宽到 good、并更换模型后的结果，不能说成“保持相同质量的加速”。摘要报告“最高 2.8× GPU、3.7× energy、4.3× cost”；表 2 的 rounded cost 数 211.7/47.2 约为 4.5，正文没有解释这点小口径差异，宜引用摘要或原始表，不自行混成一个精确倍数。

### 假设压力测试

Murakkab 最适合一个 provider 同时掌握 agent framework、模型服务和 GPU 集群，workflow 大体稳定，质量又有可重复 benchmark。以下情况会压缩收益或破坏正确性：

- prompt/model/tool 更新后，accuracy 或 token profile 快速漂移；
- 动态 DAG 生成了 profile 中没有的 executor 组合；
- tool latency 与失败高度长尾，无法用静态 throughput envelope 表示；
- tenant 因隐私或公平性不能共享实例；
- side-effecting tool 在重试或 reconfiguration 中不能重复执行；
- 第三方 API rate limit、价格或模型行为突然变化。

“至少一个可行 profile 满足 SLO”本身也是前提。若没有候选配置达到用户要求，MILP 只能不可行；论文没有完整讨论 admission control、降级提示或多个 tenant 同时预算不足时的选择。

### 实验可信度

评测覆盖多模态、文本、静态 DAG、动态 coding、CPU/GPU placement、A100/H100 availability 和 epoch sensitivity，范围较广；关键表同时给 GPU、energy、cost 和 SLO，而不是只给一个吞吐数字。LG+Auto 使用与 Murakkab 相同 autoscaler，也能分离“只是扩缩容”与“跨层换配置”的差别。

最主要的外部有效性问题是 trace。作者明确承认没有 production agentic trace，于是把 Azure chat 到达映射到 Video Q/A、coding 到达映射到 Code Generation；到达节奏是真实的，workflow 内容、token/质量和 tenant correlation 则是实验构造。系统也不是 production deployment。dynamic coding 只展示 Pareto frontier，没有把其输入依赖控制流真正接入硬件与 autoscaling 实验。画像 generality 只做 Math-500→MathEval 的同域测试。

论文还没有把 profiling 总成本、profile coverage、MILP 实际 solve-time 分布、orchestrator DAG 正确率、reconfiguration 失败率和 SLO violation rate作为主结果。附录只说 Gurobi time limit 为 300 秒；这不等于每次都在 300 秒内得到接近最优的方案。

### 系统性缺陷

统一 control plane 需要看到 prompt/data dependency、模型选择、tenant demand 和资源库存，却没有深入处理 tenant privacy、fairness、quota conflict 与故障隔离。跨 tenant multiplexing 还可能引入 cache interference、side channel 和 noisy neighbor，profile 中的单实例曲线未必覆盖这些影响。

runtime 假设 model/VM provision 约 20 分钟，并用 spare capacity 与 autoscaler吸收过渡；论文没有对 VM failure、model load failure、tool timeout、registry stale read 或 optimizer crash 做 fault injection。declarative graph 也缺少 transaction 与 exactly-once tool semantics，换配置或重试时可能重复发邮件、写数据库或调用付费 API。

## 局限与后续工作

- **局限 1**：24 小时“production-scale trace”是 Azure chat/coding arrival 到 agent workflow 的映射，不是 agent serving production trace 或线上 A/B。
- **局限 2**：quality 依赖固定 benchmark 和 percentile tier；开放式正确性、安全性及用户主观质量没有被充分覆盖。
- **局限 3**：profiling 成本、drift 检测、MILP 求解质量与 orchestrator 错误率缺少量化。
- **局限 4**：依赖完整 stack ownership 与跨 workflow multiplexing，隔离严格或大量第三方 API 的环境收益未知。
- **局限 5**：没有系统评测 tenant fairness、admission control、failure recovery 和 side-effecting tool 的重试语义。
- **后续工作 1**：公开或收集真实 agent trace，保留 workflow 分支、token、tool latency、失败、tenant 与 SLO，和当前映射 trace 做误差对比。
- **后续工作 2**：注入 prompt/model drift、tool timeout、burst 和 GPU failure，画出 profile error→SLO violation→invalidation/reprofile 的完整链条。
- **后续工作 3**：报告 profile GPU-hour、MILP solve gap/latency、方案切换时间和 transition 期间的 p99 SLO。
- **后续工作 4**：加入 tenant-level fairness、isolation、admission 与 cost budget 冲突处理，并测 multiplexing 的 cache interference 和 side channel。
- **后续工作 5**：为有副作用的 tool 增加 idempotency key、checkpoint 和补偿动作，验证 reconfiguration 不会重复执行外部操作。

## 相关

- **相关概念**：[[LLM]]、[[Serverless]]
- **同类方向**：LangGraph、LlamaIndex、AutoGen、DSPy、Circinus、Aragog
- **同会议**：[[OSDI-2026]]
