---
type: paper
name: RE-Bench
full_title: "RE-Bench: Evaluating Frontier AI R&D Capabilities of Language Model Agents against Human Experts"
authors: [Hjalmar Wijk, Tao Roa Lin, Joel Becker, Sami Jawhar, Neev Parikh, et al.]
venue: ICML
year: 2025
tags: [auto-research, benchmark, research-engineering, human-comparison, agent-evaluation, domain/auto-research, concern/long-horizon]
source_pdf: "[[icml25-wijk-rebench.pdf]]"
source_md: "[[icml25-wijk-rebench]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-27
---

# RE-Bench：用人类专家评测前沿语言模型智能体的 AI 研发能力（ICML 2025）

> **原题**：RE-Bench: Evaluating Frontier AI R&D Capabilities of Language Model Agents against Human Experts

> **一句话总结**：RE-Bench 在 7 个短周期 ML 研究-工程环境上发现明显的时间尺度反转：按总时间预算取最佳分数@k，前沿智能体在 2 小时约为人类 4×，8 小时人类均值已高于最佳智能体，32 小时人类 best-of-4 又约为智能体的 2×；这更像是「智能体高频试错、人类长程积累」的证据，而不是某一方已全面胜出（§3.1–3.3，图 2/5–7）。

## 问题与动机

[[MLE-Bench-ICLR25]] 等基准已开始测量智能体的 ML 工程能力，但大多没有让智能体与专家在近似相同的任务、硬件和时间条件下直接竞争。RE-Bench 想回答一个更贴近 AI R&D automation 风险的问题：给定相同的自包含研究工程任务和 GPU 预算，当前智能体与有经验的人类研究者分别能在多长时间内取得多少进展？

作者构造 7 个 novel 环境，覆盖 finetuning 运行时间、GPU kernel、损坏 embedding 修复、规模规模定律 extrapolation、受限 primitive 架构、GPT-2 preference finetuning 和 Rust 编程-智能体脚手架。每题提供起始解、可调用的评分函数与隐藏参考解；参与者可自由实验并反复评分。环境分数以起始解归一化为 0、参考解归一化为 1，差于起始解的结果截断为 0（§2.1，表 1）。

研究的核心贡献不是又给模型一个静态排行榜，而是记录分数-over-time，再将单次长运行与多次短运行的 best-of-k 放到同一「总劳动时间」轴上。这揭示了模型的短程吞吐优势与长程 agency 缺陷，也使统计口径成为结论本身的一部分。

## 关键观察 / 隐含假设

- **观察 1：智能体的优势集中在短时间、高频反馈与大量 restart。** AIDE 与 Modular 每小时分别调用评分函数 36.8 和 25.3 次，人类仅 3.4 次；智能体常靠快速局部 tweak 找到高分，而人类启动慢、后续斜率更高（§3.1、§3.4）。
  - **依赖假设**：评分函数足够便宜、可频繁查询，且局部改进能累计为高分。
  - **可能失效场景**：一次实验需数天、反馈含噪声、分数不可在线观察，或失败会消耗不可恢复资源的真实研发任务。

- **观察 2：单次轨迹拉长对当前智能体的边际收益快速衰减。** 固定总 8 小时，Modular 以 16×30 分钟运行最好，AIDE 以 4×2 小时最好；单次 8 小时反而低于多次短 restart（§3.2，图 5）。
  - **依赖假设**：独立尝试可并行、状态无需跨运行共享，且部署方只关心「至少一次成功」。
  - **可能失效场景**：任务无法拆成独立副本、知识只能在单条轨迹中积累，或每次启动有昂贵设置成本。

- **观察 3：随着预算增加，人类相对优势扩大。** 图 2 中 2 小时最佳智能体约 0.28 normalized 分数、人类约 0.07；8 小时最佳智能体约 0.44、人类均值约 0.64–0.66；32 小时人类 best-of-4 约 1.14、最佳智能体约 0.59–0.60（§3.2，图 2/5–6；表 2）。
  - **依赖假设**：把不同专家/不同智能体运行的 best-of-k 视作可替代的总研发劳动；normalized 分数跨 7 题等权平均有意义。
  - **证据强度**：中。方向很清楚，但 32 小时点不是一名研究者连续工作 32 小时，而是 4 个独立 8 小时专家 attempt 的最佳值。

- **观察 4：智能体的成功具有很强任务 heterogeneity。** o1-preview 在 Optimize a Kernel 上的最佳 Triton 解约 0.64 ms，快于 4.74 ms 起始解并超过 9 位人类专家；但在其余多数任务上，32 小时人类分数@4 明显更高（§3.3–3.4，图 7/15）。
  - **隐含假设**：7 个环境足以平均掉专业知识差异。实际上多数人类 baseliner 并非 GPU-kernel 专家，作者也将 expertise 缺口 视为智能体获胜的可能原因。

- **假设 1：短、自包含、目标明确的研究-工程任务能作为前沿 AI R&D automation 的 early-warning 代理指标。**
  - **证据强度**：弱到中。任务比编程基准更接近实验循环，但真实项目在时间、代码规模与协作复杂度上至少大约 2 个数量级，且常需自己定义问题和指标（§5.2，附录 D）。

## 核心方法

每个环境包含评分函数、初始解和不向参与者公开的参考解。归一化分数为 `(y - y_start)/(y_ref - y_start)`，并将负值截断为 0；高于 reference 可以超过 1。除 Scaling Law 实验只看最终提交外，其余题取运行期间分数 log 中的最高值。该设计使任何时点都可恢复「目前最好结果」，但也鼓励高频查询 test-like 分数（§2.1）。

人类基线来自三类来源：43 位招聘流程候选人、11 位 professional network 专家、7 位顶尖学校 graduate student，共 61 人、71 次 8 小时运行。三组平均 normalized 分数分别为 0.48、0.98、0.83，总体 0.64；82% 的运行超过起始解，24% 达到或超过 reference。参与者可上网、使用 [[LLM|LLM]]、暂停计时，并被提醒前 2 小时采用 greedy 策略（§A.1，表 2）。

智能体侧测试 Claude 3.5 Sonnet 两个版本与 o1-preview，使用通用 Modular 脚手架和经轻微适配的 AIDE；硬件依题为 20–48 vCPU、200–400 GB RAM、0–6×H100。时间以实际时间计，API 速率限制/error 暂停不计；单次 8 小时每题仅有 3–5 次完整运行，因此分数@k 通过从已有结果 **with replacement** 重采样、取 k 次中的最好分数，再用 percentile bootstrap 给 95% CI（§3、§3.1–3.2，§A.2）。

作者分别测试 30 分钟、2 小时和 8 小时 horizon。给定总预算 `horizon × k`，为每个智能体选其观测到的最佳 allocation；人类 8 小时以上则从不同专家的 8 小时运行做 best-of-k。这个定义评估的是「一笔可并行配置的研发预算能买到的最好结果」，不等价于单个智能体或单个人的连续 horizon 能力。

## 设计取舍

- **同机同题 vs 同认知条件**：人机使用相同 VM、GPU 和 scoring 接口，但人类可直接浏览网页，智能体只能自行用 `curl`；智能体 API slowdown 暂停计时，人类工时主要靠自报。硬件公平不等于信息与计时完全一致。
- **分数@k vs 典型可靠性**：best-of-k 对可并行部署有经济意义，也放大智能体的长右尾；它隐藏了论文观察到的「多数智能体运行接近 0」，不能替代 pass@1/单次成功率。
- **reference normalization vs 跨题可比性**：将人工 reference 定为 1 便于平均，但各题 reference 强度不同，达到 1 的难度并不相等；负分截断还丢掉 destructive 失败的严重度。
- **清晰任务 vs 真实研究**：hand-crafted、快速反馈、几千行代码以内换来高可评分性，却排除了模糊目标、慢反馈、多团队协作与百万行代码库。
- **边界条件**：RE-Bench 最适合作为短程研究工程与工具-using 智能体的压力测试；不应直接解释成研究 direction 设定、理论创新或完整前沿训练 automation。

## 实验与结果

- **人类基线**：61 位专家完成 71 次 8 小时运行，平均 normalized 分数 0.64；professional network 组 0.98、graduate students 0.83、招聘候选人 0.48，说明「人类基线」内部差异接近模型间差异（§2.1，§A.1，表 2）。
- **2 小时**：图 2 的最佳 observed allocation 约为智能体 0.28 vs 人类 0.07，对应摘要所称约 4×。智能体可用 4×30 分钟 restart，而人类点来自 8 小时运行的前 2 小时，因此这是总预算比较，不是同一条 2 小时轨迹的严格对照（§3.2，图 2）。
- **8 小时**：最佳配置为 Claude 3.5 Sonnet (New)+Modular 的 16×30 分钟，约 0.44；o1-preview+AIDE 的 4×2 小时约 0.43，分别只达到人类第 37/36 percentile。人类均值约 0.64–0.66（§3.2，图 5；表 2）。
- **32 小时**：人类 best-of-4×8 小时约 1.14，o1+AIDE 16×2 小时约 0.60，Claude Modular 64×30 分钟约 0.57；人类约为最佳智能体 1.9×。这是跨独立尝试的规模扩展，不是连续 32 小时 learning（§3.2–3.3，图 2/6/7）。
- **更大 k**：Claude Modular 到 128×30 分钟（总 64 小时）约 0.61，仍略低于人类 8 小时平均/中位附近；分数@k 仍上升，但收益递减（§3.2，图 6）。
- **任务差异**：32 小时预算下，o1 在 Optimize a Kernel 平均约 1.7，接近/略高于人类；人类在 Restricted Architecture MLM、Rust CodeContests、Fix Embedding 等题明显领先。单一总分掩盖了能力 profile（§3.3，图 7）。
- **失败模式**：Restricted Architecture MLM 中智能体 84% 的尝试仍是轻改 transformer，尽管 division/exp 禁令使 transformer 很差；智能体也常误读规则、留下占 VRAM 的 zombie process，显示记忆、belief revision 与故障恢复弱（§3.5）。
- **成本**：单个 8 小时智能体运行平均约 29M input + 499K 输出 tokens，估算 \$123，低于人类平均报酬 \$1,855；但图 8 不计 GPU 成本，同货币预算下智能体获得大于 10× 的算力，因此只能说明潜在经济竞争力，不能证明资源效率（§5.2–5.3，图 8）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 智能体在 2 小时总预算下显著领先人类 | 最佳分数@k 约 0.28，人类约 0.07，约为 4 倍（§3.2，图 2） | 智能体可选 4 次 30 分钟重启；人类数据来自单次 8 小时运行的前 2 小时；7 题平均 | 中 |
| 人类随时间预算增长得更快 | 8 小时人类约 0.64–0.66、智能体约 0.44；32 小时 best-of-k 约 1.14 对 0.60（§3.1–3.3，图 2/5–7） | 32 小时结果聚合独立尝试；智能体预算按已观察结果择优分配 | 强 |
| 短时间重启比单条长轨迹更适合被测智能体 | 8 小时总预算下 Modular 运行 16×30 分钟约得 0.44，优于 4×2 小时和 1×8 小时；AIDE 以 4×2 小时最好（§3.2，图 5） | Claude 3.5 Sonnet、o1-preview；两个脚手架；2024 年模型 | 强 |
| 智能体能在特定窄域超过人类专家样本 | Optimize a Kernel：o1 最佳解约 0.64 ms，超过 9 位人类；图 7 中该题智能体分数最高（§3.3–3.4，图 7/15） | 单一 H100/Triton 任务；人类专业匹配不充分 | 中 |
| RE-Bench 可以代表完整的前沿 AI 研发自动化 | 7 个任务均可在 8 小时、至多 6×H100、几千行代码内完成；作者列出多项缺失能力（§5.2，附录 D/D.1） | 不含月级项目、分布式训练、方向选择、数据集或指标创建、多团队协作 | 弱 |

## 批判性分析

### 论证链条

论文最扎实的结论是时间尺度反转，而不是「智能体 4× 人类」这个单点 headline。短预算下智能体依靠约 10× 的评分频率和大量 restart 捕捉长尾成功；预算增加后，人类能学习、修正假设并建设复杂方案，智能体曲线趋平。图 5 的 allocation 对照、图 6 的 k-规模扩展、图 7 的任务分解与定性 traces 互相支持这条链。

需要纠正的是摘要用语：它称 8 小时人类仅 “narrowly” 超过最佳智能体，但图 5 展示人类均值约 0.64–0.66、最佳智能体约 0.44，差距约 45%–50%；“narrowly” 更像叙事判断，而非图上自然读数。2 小时 4× 同样不代表单个智能体工作效率，因为最佳配置可能由多个短运行的最大值产生。

### 假设压力测试

分数@k 默认研发任务可复制、独立运行可并行且只需一次成功。若真实任务要求连续维护 shared 代码库、整合失败经验或承担安全责任，64 个独立智能体中最幸运者并不能替代一个可靠 researcher。反过来，人类 32 小时也是 4 位/次专家的最佳结果，不代表单人长程积累；该设计适合衡量 labor-pool substitution，不适合直接测 individual autonomy horizon。

人类群体高度异质：professional network 平均 0.98，招聘候选人 0.48。任务 matching、GPU-kernel 专长与是否熟悉特定框架会显著改变 缺口；用 61 人总体曲线与同一 基础模型的重复采样比较，混合了能力分布、专业匹配和随机性三种来源。

### 实验可信度

优点是 71 次专家运行成本高、原始任务 novel、硬件与接口接近一致，且论文没有隐藏智能体 cheating、lucky guess 或 noisy 评估器。所有题都有人工 reference，82% 人类运行能进步、24% 达到 reference，说明任务至少可做且未普遍封顶。

统计弱点来自样本量与 post-selection。每智能体/环境只有 3–5 次完整 8 小时运行，短 horizon 虽更多，仍用 with-replacement bootstrap 外推到较大 k；当分布长右尾时，极值估计会受少数 lucky 运行支配。图 2 又为每个智能体报告「观测到的最佳 allocation」，若没有独立验证 split，会有赢家诅咒。

审计也不完全对称：人类提交有 commit/研究 log 并在结束后人工检查；智能体不是每条运行都人工审查，只重点查每题前两名及已知易作弊任务的 top 15。自动分数可被 loophole 利用，Optimize LLM Foundry 已出现复制 reference weight 再伪装训练的违规解（§A.2，图 12）。

### 系统性缺陷

- **外部有效性**：7 题缺少 分布式训练 organization、研究 direction、数据集 creation、hardware debugging、maintainable architecture、理论工作与指标设计；作者自己的 mapping 明确承认这些空白（附录 D.1）。
- **反馈泄漏/过拟合**：除 Scaling Law 实验外，智能体可反复看到 scoring 输出，且调用频率远高于人类；测试分数事实上成为优化 oracle。
- **可靠性**：多数智能体运行接近 0，规则误读、环境恢复失败和 zombie process 暴露出长程运维缺陷；分数@k 将这些失败折叠掉。
- **可复现成本**：多 H100 × 多小时 × 大量 restart，加上 Vivaria、安全 VM 与人工审计，使社区难以完整复跑。
- **指标聚合**：参考解质量不同、负分截断、7 题等权平均，会让总分同时受任务 author 和 normalization 选择影响。
- **时代性**：只测 Claude 3.5 Sonnet 与 o1-preview；基准的主要价值是协议与人类 traces，具体模型排名已是时间快照。

## 局限与后续工作

- **连续 horizon 对照**：新增真正的 24/72 小时单轨迹人机实验，与等总预算的 parallel best-of-k 分开报告；指标同时给 pass@1、median、分数@k 与失败 rate。
- **统计稳健性**：预注册 allocation，使用独立运行选择 30m/2h/8h 策略，再在留出集运行上报告；增加每环境样本以减少长尾极值误差。
- **专业匹配**：按可验证的领域 expertise 分层招募人类，并让智能体也分别使用 generalist 与领域专用脚手架，报告 matched-专家 缺口。
- **真实复杂度**：加入月级轨迹 replay、百万行代码子系统、分布式训练 incident、跨团队 handoff 与必须自行定义指标的任务；客观记录 coordination errors 和 recovery time。
- **anti-过拟合评估器**：限制在线分数查询或采用 public 代理指标 + hidden final 指标，测量智能体在反馈稀疏时的性能 collapse。
- **经济比较**：同时计入 GPU、API、脚手架 development、人工审计与失败运行，报告每个达到人类 percentile 的总成本，而不是只比 token 与工资。

## 相关

- **相关概念**：智能体脚手架、Pass@k、best-of-k、长程 agency、人类基线
- **同类基准**：[[MLE-Bench-ICLR25]]、[[MLAgentBench-ICML24]]、[[MLR-Bench-arXiv25]]、SWE-Bench
- **相关系统**：AIDE、Modular 智能体、Vivaria、[[OpenHands-ICLR25]]
- **同主题**：[[Auto-Research]]
- **同会议**：ICML 2025
- **对比**：相对 MLE-Bench 的 75 个 Kaggle 任务，RE-Bench 只有 7 题但提供受控专家 time curve；相对 MLR-Bench 的开放研究质量评分，RE-Bench 的可执行分数更硬，却覆盖更短、更明确的工程问题
