---
type: paper
name: AutoScientists
full_title: "AutoScientists: Self-Organizing Agent Teams for Long-Running Scientific Experimentation"
authors: [Shanghua Gao, Ada Fang, Marinka Zitnik]
venue: arXiv
year: 2026
tags: [auto-research, multi-agent, scientific-discovery, long-horizon-agent, llm-agent, ai4science]
source_pdf: "[[arxiv26-gao-autoscientists.pdf]]"
source_md: "[[arxiv26-gao-autoscientists]]"
---

# AutoScientists: Self-Organizing Agent Teams for Long-Running Scientific Experimentation (arXiv 2026)

> **一句话总结**：AutoScientists 把 long-running scientific experimentation 从单 agent 轨迹改成无中心协调的自组织 agent team，在 BioML-Bench 24 任务上平均 leaderboard percentile 达 74.40%（比 Autoresearch 高 +8.33），GPT nanochat 达到同一 val_bpb 只需 34 vs 65 次实验，并在 ProteinGym 217 assays 上把 Kermut 平均 Spearman ρ 从 0.657 提到 0.700。

## 问题

已有科研 agent 已能提出假设、写代码、跑实验和根据反馈迭代，但多数系统仍沿着一条单一研究轨迹推进，或依赖中心 planner / 固定 decomposition 来分配任务。这在 short-horizon ML engineering 里还能工作，但 long-running science 的关键难点是：方向会随实验结果改变，失败方向需要被记住以避免重复探索，新的 productive hypothesis 往往要在已有失败和 near-miss 之后才浮现。

这篇论文把问题定义成长期程序搜索：给定任务、数据集、评估指标和可选初始程序，一组持久 agent 不断提出代码变体、训练、评估，并维护当前 champion。目标不是一次性生成答案，而是在多轮实验中持续扩大搜索面，同时避免错误提升 champion、重复探索死路、或所有 agent 收敛到同一个局部方向。

## 核心方法

AutoScientists 的核心是**去中心化自组织 team + shared experimental state**。系统没有固定 manager agent；所有 agent 周期性 heartbeat，读取共享状态后自己决定讨论、提案、实验或重组。共享状态包括当前 champion、完整 experiment log、shared forum、每个 team 的 queue / dead-end registry / hypothesis documents。

![[Pasted image 20260601232231.png]]

系统在 discussion phase 和 execution phase 间循环。Discussion phase 中，agent 读取任务、当前 champion 和 forum，提出候选研究方向，互相 critique，并形成 roster：若多数 agent 认为讨论收敛，最后一个 analyst 负责把 team assignment 写入共享状态。Execution phase 中，每个 team 持续 propose-execute：analyst 负责 coverage audit、根据历史 effect size 排序候选方向、提出实验；experiment agent 领取 queue 里的实验，修改代码、训练、评估并写回结果。

这套机制相对 [[AI-Scientist-v2-arXiv25]] 的 agentic tree search、[[ASI-ARCH-arXiv25]] 的 Researcher/Engineer/Analyst pipeline，以及 [[AlphaEvolve-arXiv25]] 的 evaluator-driven evolution，强调的是**长期协作结构本身**：team 可在 stagnation 后创建、合并、拆分、退休；失败实验进入 dead-end registry；proposal 在消耗 GPU 前先经过 peer critique；near-miss 和成功机制会被跨 team 传播。

论文还有两个重要工程细节。第一是 noise-aware champion validation：小于噪声带的提升必须用第二个 seed 确认，避免把随机波动提升为新 champion 后污染后续比较。第二是 analyst proposal protocol：analyst 要做未测试参数 audit、维护 empirical axis priors，并保证每批 proposal 至少包含一个 bold move 或公开说明为什么没有。

## 开源实现解读

开源仓库的形态比论文叙述更清楚：它不是一个大型 Python agent framework，而是**Claude Code subagents + 本地 ClawInstitute server + 一组 markdown runbook / role template**。核心入口是 `launch.py`：每次运行会创建一个新的 run directory，复制 `system/`、`task/`、`runbook.md`，把对应 task 的 `LAUNCH.md` 复制成 `task-profile.md`，然后注册 10 个 agent（1 个 monitor、6 个 GPU/experiment agents、3 个 analysts），并创建共享 workspace / workshop / team roster / champion / knowledge 文件。

整个系统的控制流是 hook-based：

- `runbook.md` 是通用 orchestrator 程序，只负责循环、发起 agent、收集结果、promote champion；它明确规定 orchestrator **不训练模型、不写实验代码**。
- `task-profile.md` 由具体任务的 `LAUNCH.md` 填充，用 hook 决定 deadline、discussion policy、GPU dispatch、champion promotion、stagnation response。
- 每个 agent 每次被唤醒都读自己的 `HEARTBEAT.md`。`HEARTBEAT.md` 先做 mode selector：若有 active discussion trigger 就进入讨论；若无 team 就退出；若有未发布的 `result_latest.json` 就先恢复发布结果；否则进入 normal cycle。
- Analyst 的职责是读 shared state / forum / team queue，发 `[PROPOSAL]` 并写入 queue；GPU agent 的职责是 claim queue item、在自己的 workspace 写/改 `train.py`、跑实验、保存 `submission_<expid>.csv` 和 `result_latest.json`，再发 `[RESULT]`。
- 共享状态不是数据库里的复杂对象，而主要是 ClawInstitute workspace 中的一组 markdown / JSON 文件：`teams/roster.md`、`champion.md`、team `queue.md`、结果文件、workshop posts、agent local memory。

这个设计很“系统”：关键机制都落在**共享文件协议 + agent heartbeat contract** 上，而不是隐藏在模型 prompt 里。它也暴露出工程脆弱点：许多 safety rule 是在 markdown role template 中约束 agent 行为，比如不要直接写 `task/submission.csv`、必须写 `result_latest.json`、必须用 API trail 记录 proposal→claim→result；系统正确性很依赖 agent 遵守这些 protocol。

### ClawInstitute 具体是什么

ClawInstitute 是 AutoScientists 的本地协作后端，不是 LLM runtime，也不是 agent framework。开源仓库引用的 `mims-harvard/ClawInstitute` 目前不可访问；可核查实现来自 npm 包 `clawinstitute@0.1.3`，metadata 指向该 GitHub repo，author 是 Shanghua Gao。它的定位是一个 self-hosted coordination service：Express API + bundled Next frontend + PGlite/Postgres database。

默认启动方式是 `clawinstitute start`：

- API 监听 `http://localhost:3000/api/v1`，frontend 默认 `http://localhost:3001`。
- 默认存储是 PGlite，路径 `~/.clawinstitute/db`；也可通过 `DATABASE_URL` 使用真实 Postgres。
- token 存在 `~/.clawinstitute/token`；默认 auth 关闭，设置 `CLAWINSTITUTE_AUTH_REQUIRED=1` 才要求 `Authorization: Bearer ...`。
- 本地模式下 agent 注册返回的 token 实际上接近共享 token；请求身份主要靠 `X-Agent-Name` header，因此它不是强安全边界。

数据模型很接近一个“本地 Reddit + Notion + Git-lite”：

- `agents`：agent 名称、profile、状态、karma 等。
- `workshops`：任务/实验 run 对应的讨论区。
- `posts` / `comments` / `notifications`：proposal、discussion、result、mention、reply。
- `ws_workspaces`：共享 workspace。
- `ws_workspace_files`：workspace 内的文本文件，如 `champion.md`、`teams/roster.md`、team `queue.md`。
- `ws_workspace_file_revisions`：文件版本历史。

最关键的是 workspace file API：`GET/PUT/PATCH /workspaces/:id/files/<path>` 支持版本号和 `If-Match`，写冲突返回 409。这就是 queue claim、champion update 和 result recovery 的并发控制基础。它不是分布式锁，也没有强事务化 workflow；AutoScientists 通过“读文件版本 → 修改 YAML frontmatter → 用 `If-Match` PUT 回去”的 optimistic concurrency protocol 避免多数竞态。

### 单个 GPU agent 的生命周期

实验型 agent 也不是常驻进程。它更像一个**一次性 Claude Code subagent invocation**：orchestrator 每个 cycle 用 `Task` / `Agent` 调起它，prompt 只给最小上下文：

```text
You are {agent_name}.
FOCUS_ROOT={run_dir}
CUDA_VISIBLE_DEVICES={cuda}
MODE=execute
Read {FOCUS_ROOT}/agents/{agent_name}/HEARTBEAT.md and follow it.
Start at Part 0 (Mode Selector).
When done: <promise>{agent_name} cycle complete</promise>
```

Agent 的身份在 `launch.py` 生成时已经落盘：`agents/<name>/credentials.json` 保存 API token 和 `agent_name`，`agents/<name>/AGENT.md` 保存 `role: gpu`、`gpu`、`server`、`status` 等。它的 team 不是 prompt 传入的，而是每次启动后从 ClawInstitute 的 `teams/roster.md` 里发现：若自己的名字出现在某个 team 的 `members`，就得到 `MY_TEAM` 和 `TEAM_WS_ID`。

每次 invocation 的状态机由 `HEARTBEAT.md` 驱动：

1. **Part 0 Mode Selector**：先看 prompt 的 `MODE`；再查 workshop 是否有 active `[DISCUSSION-TRIGGER]`；再读 `teams/roster.md`；GPU agent 还会检查本地 `agents/<name>/workspace/result_latest.json` 是否有未发布的上轮结果。
2. **Part 1 Boot**：读 credentials、`AGENT.md`、memory index、`task/TASK.md`、`WORKSPACE_ID`、`WORKSHOP_NAME`。
3. **Part 4 Normal Cycle**：读 team workspace / workshop posts / champion，声明 approach 和 compute mode，从 team `queue.md` claim 实验，修改 agent-local `train.py`，同步训练，保存 result sentinel，写结果文件并发 `[RESULT]`。
4. **Part 6 Always-Last**：更新本地 `AGENT.md`，mirror 到 ClawInstitute 的 `agents/<name>.md`，保存 memory，打印 `<promise>...cycle complete</promise>` 后退出。

因此 “heartbeat” 不是传统意义上的后台定时心跳 daemon，而是每次 agent 启动时必须执行的 boot protocol / state machine。系统的长时间性来自持久化共享状态，而不是来自单个 agent 进程一直活着。

实际的 health / recovery 机制分散在几个文件和轮询里：

- `AGENT.md.last_seen` 和 `session_count`：每次退出前更新，作为 agent 活跃记录。
- `<promise>` tag：orchestrator 用它判断一次 invocation 是否完成，并把记录写入 `logs/sessions.jsonl`。
- `logs/<agent>.gpu_claim`：BioML-Bench mixed dispatch 中，GPU agent 启动后应在约 60 秒内声明 `gpu` 或 `cpu`；orchestrator 每 5 秒轮询，最多等 120 秒，超时默认当作 GPU 任务。
- `result_latest.json`：训练前写 `status: running`，训练完成改 `complete`，发完 `[RESULT]` 改 `posted`。如果 agent 死在训练后发帖前，下次 relaunch 会进入 Part 5，把旧结果补发出去。
- Stale claim sweep：orchestrator health check 会释放超过 30 分钟且没有 result file 的 queue claim。

这解释了 AutoScientists 的一个核心设计取舍：它没有强 runtime scheduler，也没有真正的 agent-level heartbeat service；它靠 markdown/JSON sentinel、ClawInstitute 文件版本号、Claude Code subagent 的完成信号和 orchestrator loop 拼出一个可恢复的 long-running research workflow。

## Autoresearch baseline 到底是什么

这里最容易误读。论文表格里 BioML-Bench 也列了 “Autoresearch”，但开源实现显示：**BioML-Bench 上跑的不是 Karpathy 原版 `autoresearch` repo**。

仓库里有两个完全不同的 task profile：

- `task-autoresearch/`：这才是真正包 [[Auto-Research|Karpathy Autoresearch]] 的 nanoGPT / nanochat `val_bpb` 优化任务。`launch.py` 会 clone `https://github.com/karpathy/autoresearch.git`，seed `champion/train.py`，agent 修改现成 GPT training loop。
- `task-biomlbench/`：这是 BioML-Bench 的 fixed-deadline Kaggle-style profile。这里没有 pre-populated `repo/`，也没有初始 `train.py`；每个任务只有 `TASK.md`、数据、submission 格式、CV 评估说明。Agent 必须从零写 `train.py`，用 local CV 迭代，最后生成 `submission.csv`。

所以 BioML-Bench 里的 “Autoresearch” 更准确应理解为：**Autoresearch-style single-agent iterative coding loop baseline**，而不是 “Karpathy 的 GPT 训练优化项目直接迁移到 biomedical ML”。作者复用了的是“单 agent 持续写代码、跑实验、根据结果迭代”的 orchestration pattern；任务接口已经换成 BioML-Bench 的 train/submission/evaluator。

这点对解读结果很重要。AutoScientists 在 BioML-Bench 上优于 Autoresearch，主要说明的是：在相同 biomedical benchmark interface 下，**多 agent 自组织 + method diversity + shared state** 比单 agent iterative coding loop 更有效；它不说明 Karpathy 原始 nanoGPT autoresearch 系统天然适合或不适合 BioML-Bench。

BioML-Bench profile 还加入了不少 domain-specific 脚手架：

- 任务级 `TASK.md` 会告诉 agent 数据列、CV fold、metric、submission 格式，并反复警告不要读取 `data/private/answers.csv`。
- `task-biomlbench/LAUNCH.md` 会按 domain 生成 approach menu：小分子任务给 Chemprop / GNN / ChemBERTa / RDKit+LightGBM / Tanimoto-GP 等；protein 任务给 ESM / MSA / zero-shot features / GP 等；single-cell 和 image 任务也有各自菜单。
- Discussion 阶段强制 method diversity：每个 agent 要选择不同 paradigm；monitor / team seed 规则要求 exactly one team 走 classical baseline，其余 team 尽量覆盖 GPU-native 或不同 featurization。
- BioML profile 的 champion 是最佳 `submission.csv`，不是 `train.py` provenance；orchestrator 根据 agent-local `result_latest.json` 统一 promote。

因此，BioML-Bench 实验更像是在比较两类 agent orchestration：单 agent loop vs 多 agent self-organizing research team，而不是比较一个具体 Karpathy repo 和一个具体 AutoScientists repo。

## 关键结果

- BioML-Bench 24 个 biomedical ML 任务：AutoScientists 平均 leaderboard percentile 74.40%，Autoresearch 为 66.07%，提升 +8.33；drug discovery 领域从 46.16/47.91% 附近提升到 64.52%。
- GPT nanochat training optimization：从 Autoresearch baseline 出发，达到约 0.978 val_bpb 需要 34 次实验，Autoresearch 需要 65 次，实验数约 1.9× 更少。
- 从 AutoScientists champion 继续优化：AutoScientists 在 93 次实验中接受 7 个改进，val_bpb 从 0.9777 到 0.9730；Autoresearch 100 次实验接受 0 个改进。
- ProteinGym ACE2-Spike：基于 Kermut 发现三 GP ensemble + expanded zero-shot features + diversity feature selection + quantile-warping，Spearman ρ 从 0.747 提到 0.840，相对提升 12.5%。
- ProteinGym 全 217 supervised substitution assays：冻结同一 recipe 后，官方平均 Spearman ρ 从 Kermut 的 0.657 提到 0.700，绝对 +0.043，相对 +6.5%。
- Ablation 显示四个组件解决不同瓶颈：移除 analyst 在 TDC-hERG 最伤，移除 cross-agent feedback 在 Human Plasma-Protein Binding 最伤，移除 self-organization 在 GPT optimization 最伤，independent agents 在 Cell-Cell Communication 最伤。

## 批判与局限

这篇最强的贡献是把 long-running scientific agent 明确建模成 coordination architecture problem，而不只是 prompt engineering。但结果解读需要保守：

- **Autoresearch baseline 命名不严谨**：BioML-Bench 上的 Autoresearch 不是 Karpathy 原版 repo，而是 single-agent coding loop 的适配版。表格里直接写 Autoresearch 容易让读者误以为 Karpathy 原项目本身可以直接跑 biomedical benchmarks。
- **domain-specific scaffold 很强**：BioML-Bench task profile 给了详细 task spec、CV protocol、domain approach menu、method diversity 指令和丰富依赖环境。若对比 baseline 没拿到完全同等的菜单、工具、时间和 pretrained model access，结果会偏向 AutoScientists。
- **validation overfitting 风险**：BioML-Bench 运行中用 local CV 反复选择方法，最终用 held-out/private answers 评分；虽然代码排除了 `private/answers.csv` 和 reference submissions，但多轮 CV-driven search 仍可能过拟合开发反馈。ProteinGym 更特殊，prescribed folds 本身也是官方评分的一部分，泛化证据比真正 held-out test 弱。
- **系统正确性依赖 agent 遵守协议**：开源实现大量 safety rule 写在 markdown heartbeat / role templates 中，而不是强类型 runtime enforcement。比如必须写 `result_latest.json`、不能直接覆盖 `task/submission.csv`、proposal 必须有 API trail。这是可运行原型，但还不是一个强隔离、强一致性的 research OS。
- **复现实验成本高**：依赖 Claude Code / Sonnet 4.6、ClawInstitute、本地 task 环境、大量 Python/ML 包、H100 GPU 和多小时运行。论文自己也承认 BioML-Bench 全量多随机种子重复不可行，只在代表任务做了有限重复。
- **多 agent token 成本更高**：论文明确说 AutoScientists 不是 LLM-call efficient；它优化的是 fixed experimental-compute budget 下的 experiment selection，而不是总成本。

对系统研究的启发是：真正值得抽象化的不是“多个 agent 一起聊天”，而是 **state schema、queue/claim protocol、dead-end registry、promotion gate、trace replay、team reformation trigger** 这些机制。若要把它发展成更强的系统论文，下一步应该把 markdown protocol 收敛成可验证的 runtime contract，并把 single-agent baseline 明确命名为 “Autoresearch-style” 而非 “Autoresearch”。

## 相关

- **相关概念**：long-horizon agent、multi-agent collaboration、shared state、dead-end registry、noise-aware validation、scientific discovery
- **同类系统**：[[AI-Scientist-v2-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[AlphaEvolve-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[MLR-Bench-arXiv25]]、[[OpenHands-ICLR25]]
- **同主题**：[[Auto-Research]]
