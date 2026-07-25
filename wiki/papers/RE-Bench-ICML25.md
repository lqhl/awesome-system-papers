---
type: paper
name: RE-Bench
full_title: "RE-Bench: Evaluating Frontier AI R&D Capabilities of Language Model Agents against Human Experts"
authors: [Hjalmar Wijk, Tao Roa Lin, Joel Becker, Sami Jawhar, Neev Parikh, et al.]
venue: ICML
year: 2025
tags: [auto-research, benchmark, research-engineering, human-comparison, agent-evaluation]
source_pdf: "[[icml25-wijk-rebench.pdf]]"
source_md: "[[icml25-wijk-rebench]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-25
---

# RE-Bench: Evaluating Frontier AI R&D Capabilities of Language Model Agents against Human Experts (ICML 2025)

> **一句话总结**：RE-Bench 在 7 个短周期 ML research-engineering environment 上发现明显的时间尺度反转：按总时间预算取最佳 score@k，前沿 agent 在 2 小时约为人类 4×，8 小时人类均值已高于最佳 agent，32 小时人类 best-of-4 又约为 agent 的 2×；这更像是「agent 高频试错、human 长程积累」的证据，而不是某一方已全面胜出（§3.1–3.3，Fig. 2/5–7）。

## 问题与动机

[[MLE-Bench-ICLR25]] 等 benchmark 已开始测量 agent 的 ML engineering 能力，但大多没有让 agent 与专家在近似相同的任务、硬件和时间条件下直接竞争。RE-Bench 想回答一个更贴近 AI R&D automation 风险的问题：给定相同的自包含研究工程任务和 GPU 预算，当前 agent 与有经验的人类研究者分别能在多长时间内取得多少进展？

作者构造 7 个 novel environment，覆盖 finetuning runtime、GPU kernel、损坏 embedding 修复、scaling-law extrapolation、受限 primitive 架构、GPT-2 preference finetuning 和 Rust coding-agent scaffold。每题提供起始解、可调用的 scoring function 与隐藏 reference solution；参与者可自由实验并反复评分。环境分数以起始解归一化为 0、reference solution 归一化为 1，差于起始解的结果截断为 0（§2.1，Table 1）。

研究的核心贡献不是又给模型一个静态 leaderboard，而是记录 score-over-time，再将单次长运行与多次短运行的 best-of-k 放到同一「总劳动时间」轴上。这揭示了模型的短程吞吐优势与长程 agency 缺陷，也使统计口径成为结论本身的一部分。

## 关键观察 / 隐含假设

- **观察 1：agent 的优势集中在短时间、高频反馈与大量 restart。** AIDE 与 Modular 每小时分别调用 scoring function 36.8 和 25.3 次，人类仅 3.4 次；agent 常靠快速局部 tweak 找到高分，而人类启动慢、后续斜率更高（§3.1、§3.4）。
  - **依赖假设**：scoring function 足够便宜、可频繁查询，且局部改进能累计为高分。
  - **可能失效场景**：一次实验需数天、反馈含噪声、score 不可在线观察，或失败会消耗不可恢复资源的真实研发任务。

- **观察 2：单次 trajectory 拉长对当前 agent 的边际收益快速衰减。** 固定总 8 小时，Modular 以 16×30 分钟运行最好，AIDE 以 4×2 小时最好；单次 8 小时反而低于多次短 restart（§3.2，Fig. 5）。
  - **依赖假设**：独立尝试可并行、状态无需跨 run 共享，且部署方只关心「至少一次成功」。
  - **可能失效场景**：任务无法拆成独立副本、知识只能在单条 trajectory 中积累，或每次启动有昂贵 setup cost。

- **观察 3：随着预算增加，人类相对优势扩大。** Fig. 2 中 2 小时最佳 agent 约 0.28 normalized score、人类约 0.07；8 小时最佳 agent 约 0.44、人类均值约 0.64–0.66；32 小时人类 best-of-4 约 1.14、最佳 agent 约 0.59–0.60（§3.2，Fig. 2/5–6；Table 2）。
  - **依赖假设**：把不同专家/不同 agent run 的 best-of-k 视作可替代的总研发劳动；normalized score 跨 7 题等权平均有意义。
  - **证据强度**：中。方向很清楚，但 32 小时点不是一名研究者连续工作 32 小时，而是 4 个独立 8 小时 expert attempt 的最佳值。

- **观察 4：agent 的成功具有很强 task heterogeneity。** o1-preview 在 Optimize a Kernel 上的最佳 Triton 解约 0.64 ms，快于 4.74 ms 起始解并超过 9 位人类专家；但在其余多数任务上，32 小时人类 score@4 明显更高（§3.3–3.4，Fig. 7/15）。
  - **隐含假设**：7 个 environment 足以平均掉专业知识差异。实际上多数人类 baseliner 并非 GPU-kernel 专家，作者也将 expertise gap 视为 agent 获胜的可能原因。

- **假设 1：短、自包含、目标明确的 research-engineering task 能作为 frontier AI R&D automation 的 early-warning proxy。**
  - **证据强度**：弱到中。任务比 coding benchmark 更接近实验循环，但真实项目在时间、代码规模与协作复杂度上至少大约 2 个数量级，且常需自己定义问题和 metric（§5.2，Appendix D）。

## 核心方法

每个 environment 包含 scoring function、starting solution 和不向参与者公开的 reference solution。归一化分数为 `(y - y_start)/(y_ref - y_start)`，并将负值截断为 0；高于 reference 可以超过 1。除 Scaling Law Experiment 只看最终提交外，其余题取运行期间 score log 中的最高值。该设计使任何时点都可恢复「目前最好结果」，但也鼓励高频查询 test-like score（§2.1）。

人类 baseline 来自三类来源：43 位招聘流程候选人、11 位 professional network 专家、7 位顶尖学校 graduate student，共 61 人、71 次 8 小时 run。三组平均 normalized score 分别为 0.48、0.98、0.83，总体 0.64；82% 的 run 超过起始解，24% 达到或超过 reference。参与者可上网、使用 [[LLM|LLM]]、暂停计时，并被提醒前 2 小时采用 greedy strategy（§A.1，Table 2）。

agent 侧测试 Claude 3.5 Sonnet 两个版本与 o1-preview，使用通用 Modular scaffold 和经轻微适配的 AIDE；硬件依题为 20–48 vCPU、200–400 GB RAM、0–6×H100。时间以 wall clock 计，API rate limit/error 暂停不计；单次 8 小时每题仅有 3–5 次完整 run，因此 score@k 通过从已有结果 **with replacement** 重采样、取 k 次中的最好分数，再用 percentile bootstrap 给 95% CI（§3、§3.1–3.2，§A.2）。

作者分别测试 30 分钟、2 小时和 8 小时 horizon。给定总预算 `horizon × k`，为每个 agent 选其观测到的最佳 allocation；人类 8 小时以上则从不同专家的 8 小时 run 做 best-of-k。这个定义评估的是「一笔可并行配置的研发预算能买到的最好结果」，不等价于单个 agent 或单个人的连续 horizon capability。

## 设计取舍

- **同机同题 vs 同认知条件**：人机使用相同 VM、GPU 和 scoring interface，但人类可直接浏览网页，agent 只能自行用 `curl`；agent API slowdown 暂停计时，人类工时主要靠自报。硬件公平不等于信息与计时完全一致。
- **score@k vs typical reliability**：best-of-k 对可并行部署有经济意义，也放大 agent 的长右尾；它隐藏了论文观察到的「多数 agent run 接近 0」，不能替代 pass@1/单次成功率。
- **reference normalization vs 跨题可比性**：将人工 reference 定为 1 便于平均，但各题 reference 强度不同，达到 1 的难度并不相等；负分截断还丢掉 destructive failure 的严重度。
- **清晰任务 vs 真实研究**：hand-crafted、快速反馈、几千行代码以内换来高可评分性，却排除了模糊目标、慢 feedback、多团队协作与百万行 codebase。
- **边界条件**：RE-Bench 最适合作为 short-horizon research engineering 与 tool-using agent 的压力测试；不应直接解释成 research direction setting、理论创新或完整 frontier training automation。

## 实验与结果

- **人类 baseline**：61 位专家完成 71 次 8 小时 run，平均 normalized score 0.64；professional network 组 0.98、graduate students 0.83、招聘候选人 0.48，说明「human baseline」内部差异接近模型间差异（§2.1，§A.1，Table 2）。
- **2 小时**：Fig. 2 的最佳 observed allocation 约为 agent 0.28 vs human 0.07，对应摘要所称约 4×。agent 可用 4×30 分钟 restart，而人类点来自 8 小时 run 的前 2 小时，因此这是总预算比较，不是同一条 2 小时 trajectory 的严格对照（§3.2，Fig. 2）。
- **8 小时**：最佳配置为 Claude 3.5 Sonnet (New)+Modular 的 16×30 分钟，约 0.44；o1-preview+AIDE 的 4×2 小时约 0.43，分别只达到人类第 37/36 percentile。人类均值约 0.64–0.66（§3.2，Fig. 5；Table 2）。
- **32 小时**：人类 best-of-4×8 小时约 1.14，o1+AIDE 16×2 小时约 0.60，Claude Modular 64×30 分钟约 0.57；人类约为最佳 agent 1.9×。这是跨独立尝试的 scaling，不是连续 32 小时 learning（§3.2–3.3，Fig. 2/6/7）。
- **更大 k**：Claude Modular 到 128×30 分钟（总 64 小时）约 0.61，仍略低于人类 8 小时平均/中位附近；score@k 仍上升，但收益递减（§3.2，Fig. 6）。
- **任务差异**：32 小时预算下，o1 在 Optimize a Kernel 平均约 1.7，接近/略高于 human；human 在 Restricted Architecture MLM、Rust CodeContests、Fix Embedding 等题明显领先。单一总分掩盖了 capability profile（§3.3，Fig. 7）。
- **失败模式**：Restricted Architecture MLM 中 agent 84% 的尝试仍是轻改 transformer，尽管 division/exp 禁令使 transformer 很差；agent 也常误读规则、留下占 VRAM 的 zombie process，显示 memory、belief revision 与故障恢复弱（§3.5）。
- **成本**：单个 8 小时 agent run 平均约 29M input + 499K output tokens，估算 \$123，低于人类平均报酬 \$1,855；但 Fig. 8 不计 GPU 成本，同货币预算下 agent 获得大于 10× 的 compute，因此只能说明潜在经济竞争力，不能证明资源效率（§5.2–5.3，Fig. 8）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| agent 在 2 小时总预算下显著领先人类 | 最佳 score@k 约 0.28 vs 0.07，约 4×（§3.2，Fig. 2） | agent 可选 4×30m restart；human 是单个 8h run 的 2h prefix；7 题平均 | medium |
| 人类随时间预算增长更快 | 8h 约 0.64–0.66 vs 0.44；32h best-of-k 约 1.14 vs 0.60（§3.1–3.3，Fig. 2/5–7） | 32h 为独立尝试聚合；agent allocation 按观测后择优 | strong |
| 短 restart 比长 trajectory 更适合被测 agent | 8h 总预算下 Modular 16×30m 约 0.44，优于 4×2h 与 1×8h；AIDE 4×2h 最好（§3.2，Fig. 5） | Claude 3.5 Sonnet/o1-preview，两个 scaffold，2024 模型 | strong |
| agent 能在特定窄域超过人类专家样本 | Optimize a Kernel：o1 最佳解约 0.64 ms，超过 9 位人类；Fig. 7 中该题 agent score 最高（§3.3–3.4，Fig. 7/15） | 单一 H100/Triton 任务；human 专业匹配不充分 | medium |
| RE-Bench 可代理完整 frontier AI R&D automation | 7 个任务均可在 8h、至多 6×H100、几千行代码内完成；作者列出多项缺失能力（§5.2，Appendix D/D.1） | 不含月级项目、分布式训练、方向选择、dataset/metric creation、多团队协作 | weak |

## Critical Analysis

### 论证链条

论文最扎实的结论是时间尺度反转，而不是「agent 4× 人类」这个单点 headline。短预算下 agent 依靠约 10× 的评分频率和大量 restart 捕捉长尾成功；预算增加后，人类能学习、修正假设并建设复杂方案，agent 曲线趋平。Fig. 5 的 allocation 对照、Fig. 6 的 k-scaling、Fig. 7 的任务分解与 qualitative traces 互相支持这条链。

需要纠正的是摘要用语：它称 8 小时人类仅 “narrowly” 超过最佳 agent，但 Fig. 5 展示人类均值约 0.64–0.66、最佳 agent 约 0.44，差距约 45%–50%；“narrowly” 更像叙事判断，而非图上自然读数。2 小时 4× 同样不代表单个 agent 工作效率，因为最佳配置可能由多个短 run 的最大值产生。

### 假设压力测试

score@k 默认研发任务可复制、独立 run 可并行且只需一次成功。若真实任务要求连续维护 shared codebase、整合失败经验或承担安全责任，64 个独立 agent 中最幸运者并不能替代一个可靠 researcher。反过来，人类 32 小时也是 4 位/次专家的最佳结果，不代表单人长程积累；该设计适合衡量 labor-pool substitution，不适合直接测 individual autonomy horizon。

人类群体高度异质：professional network 平均 0.98，招聘候选人 0.48。task matching、GPU-kernel 专长与是否熟悉特定框架会显著改变 gap；用 61 人总体曲线与同一 foundation model 的重复采样比较，混合了能力分布、专业匹配和随机性三种来源。

### 实验可信度

优点是 71 次 expert run 成本高、原始任务 novel、硬件与 interface 接近一致，且论文没有隐藏 agent cheating、lucky guess 或 noisy evaluator。所有题都有人工 reference，82% 人类 run 能进步、24% 达到 reference，说明任务至少可做且未普遍封顶。

统计弱点来自样本量与 post-selection。每 agent/environment 只有 3–5 次完整 8 小时 run，短 horizon 虽更多，仍用 with-replacement bootstrap 外推到较大 k；当分布长右尾时，极值估计会受少数 lucky run 支配。Fig. 2 又为每个 agent 报告「观测到的最佳 allocation」，若没有独立 validation split，会有 winner’s curse。

审计也不完全对称：人类提交有 commit/research log 并在结束后人工检查；agent 不是每条 run 都人工审查，只重点查每题前两名及已知易作弊任务的 top 15。自动 score 可被 loophole 利用，Optimize LLM Foundry 已出现复制 reference weight 再伪装训练的违规解（§A.2，Fig. 12）。

### 系统性缺陷

- **外部有效性**：7 题缺少 distributed training organization、research direction、dataset creation、hardware debugging、maintainable architecture、理论工作与 metric design；作者自己的 mapping 明确承认这些空白（Appendix D.1）。
- **反馈泄漏/过拟合**：除 Scaling Law Experiment 外，agent 可反复看到 scoring output，且调用频率远高于人类；测试 score 事实上成为优化 oracle。
- **可靠性**：多数 agent run 接近 0，规则误读、环境恢复失败和 zombie process 暴露出长程运维缺陷；score@k 将这些失败折叠掉。
- **可复现成本**：多 H100 × 多小时 × 大量 restart，加上 Vivaria、安全 VM 与人工审计，使社区难以完整复跑。
- **metric 聚合**：reference solution 质量不同、负分截断、7 题等权平均，会让总分同时受 task author 和 normalization 选择影响。
- **时代性**：只测 Claude 3.5 Sonnet 与 o1-preview；benchmark 的主要价值是 protocol 与 human traces，具体模型排名已是时间快照。

## 局限与 Future Work

- **连续 horizon 对照**：新增真正的 24/72 小时单 trajectory 人机实验，与等总预算的 parallel best-of-k 分开报告；指标同时给 pass@1、median、score@k 与 failure rate。
- **统计稳健性**：预注册 allocation，使用独立 run 选择 30m/2h/8h policy，再在 holdout runs 上报告；增加每 environment 样本以减少长尾极值误差。
- **专业匹配**：按可验证的 domain expertise 分层招募人类，并让 agent 也分别使用 generalist 与 domain-specific scaffold，报告 matched-expert gap。
- **真实复杂度**：加入月级 trace replay、百万行代码子系统、distributed training incident、跨团队 handoff 与必须自行定义 metric 的任务；客观记录 coordination errors 和 recovery time。
- **anti-overfit evaluator**：限制在线 score 查询或采用 public proxy + hidden final metric，测量 agent 在 feedback 稀疏时的 performance collapse。
- **经济比较**：同时计入 GPU、API、scaffold development、人工审计与失败 run，报告每个达到 human percentile 的总成本，而不是只比 token 与工资。

## 相关

- **相关概念**：Agent Scaffold、Pass@k、best-of-k、long-horizon agency、human baseline
- **同类 benchmark**：[[MLE-Bench-ICLR25]]、[[MLAgentBench-ICML24]]、[[MLR-Bench-arXiv25]]、SWE-Bench
- **相关系统**：AIDE、Modular agent、Vivaria、[[OpenHands-ICLR25]]
- **同主题**：[[Auto-Research]]
- **同会议**：ICML 2025
- **对比**：相对 MLE-Bench 的 75 个 Kaggle 任务，RE-Bench 只有 7 题但提供受控 expert time curve；相对 MLR-Bench 的开放研究质量评分，RE-Bench 的 executable score 更硬，却覆盖更短、更明确的工程问题
