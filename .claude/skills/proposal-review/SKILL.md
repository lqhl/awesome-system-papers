---
name: proposal-review
description: "Use this skill to deeply review and improve an existing proposal in proposals/. Verifies claims against cited papers (markdowns/PDFs) and code repos, hunts for internal inconsistencies / logical fallacies / overlooked prior work, applies the Taste Rubric again, and surfaces concrete fix-ups without auto-archiving. Triggers on /proposal-review <slug>, '审 proposal', '审一下我的 idea', 'review 这个 proposal', '看看 proposal 哪里有问题', 'proposal 是否合理'. Output edits the proposal in place + appends a Review Log + writes a separate review report when findings are heavy."
---

# Proposal Review Skill

把一个**已存在**的 `proposals/{Slug}.md` 做深度审稿:沿用 `/proposal` skill 的 generator/critic 分离 + Taste Rubric + failure memory 纪律,在此基础上**额外**做三件事:

1. **Evidence verification**:proposal 引用的内部论文打开 wiki 页 → 必要时进 markdowns/ → 必要时 Read PDF;引用的外部 URL 打开 abstract;声称"复用某 system"时打开对应 GitHub repo 验证能力是否真存在。
2. **Internal consistency**:扫 proposal 全文找前后矛盾(TL;DR 数字 vs Plan 数字、Idea 描述的方法 vs 实现规划的步骤、claimed novelty vs 调研覆盖、risks 列了但 Plan 没处理)。
3. **Logical fallacy hunt**:strawman / 循环论证 / 含义漂移 / 假二分 / 把 speculation 写成 fact / cherry-pick baseline / hasty generalization,逐条排查。

执行模式:**默认非破坏性增量编辑**——append 新发现到既有节,改正错误数字,但**不删除原有内容**(即使发现 Steel-man 过头);加一个 `## Review Log` 节做审计 trail;`status` 与 `verdict` 都不动,留给人决策。

## Usage

```
/proposal-review <slug-or-path> [--no-web] [--deep] [--mode <surface|inline|report>] [--category <mlsys|agent|generic>]
```

- `<slug-or-path>`:`KvCacheCompression` 或 `proposals/KvCacheCompression.md` 都行
- `--no-web`:跳过 WebSearch / WebFetch / `gh`
- `--deep`:开启深度模式——所有内部引用的论文都进 markdown 全文;所有 GitHub repo 引用都打开 README + 最相关源文件;token 预算从 ~30k 抬到 ~80k
- `--mode`:
  - `inline`(默认):评审发现直接增量改 proposal 文件;末尾追加 `## Review Log`
  - `surface`:**只**追加 `## Review Log`,不改其它节;适合 quick scan
  - `report`:proposal 文件几乎不动,详细评审写到 `proposals/_reviews/{Slug}-{YYYYMMDD}.md`;适合深度审稿与原作分离
- `--category`:覆盖 frontmatter 里的 category(用来选 Taste Rubric);通常不用传

## Step 0 — Pre-flight

1. `mkdir -p proposals/_reviews/`(`--mode report` 时需要;幂等)
2. 解析 `<slug-or-path>`:
   - 给的是路径 → 直接用
   - 给的是 slug → `Glob proposals/{Slug}.md`;命中多个时取最近修改的并提示用户
   - 找不到 → 报错退出
3. `Read proposals/{Slug}.md` 全文
4. `Read proposals/_log.md` 若存在(看本 proposal 是否被 review 过、之前的 critique 还成立吗)
5. 取今日日期(`currentDate`)

## Step 1 — Parse the proposal

从 frontmatter 抽:`name, title, status, category(可选), novelty, feasibility, verdict(可选), tags, related_papers, related_concepts, related_systems, created, last_updated`。

**判 schema 版本**:
- 有 `category` 与 `verdict` 字段 → 新版 schema(`/proposal` skill 重写后)
- 无这两个字段 → 老版 schema;review 时**顺手补上**(category 用 Step 4 的 auto-detect,verdict 默认 `pending`)

从正文抽各节文本:`Idea`、`相关工作(仓库内)`、`相关工作(外部)`、`Steel-man`(若存在)、`Critic`(若存在)、`Reframings`(若存在)、`可行性评估`、`实现规划`、`Verdict`(若存在)、`开放问题`。

提取所有具体数字声明(如 "≥ 25%"、"~2 weeks"、"K=8"、"1.3 s")到一个声明清单,Step 2 用。

提取所有 wikilink 与外部 URL 到一个引用清单,Step 3 用。

## Step 2 — Internal Consistency Check

逐项过,**不允许跳**。每条命中都进 Critic 节(Step 7)的 `[inconsistency]` 类。

| 检查 | 例 |
|---|---|
| TL;DR 数字 vs 其它节数字 | TL;DR 说 "≥25% 加速",Plan M3 验证标准写 "≥20%" → flag |
| Idea 描述的方法 vs Plan 步骤 | Idea 提了 KL-bounded reconciliation,Plan 没出现 KL 验证步骤 → flag |
| Steel-man 的 novelty thesis vs 相关工作覆盖 | Steel-man 说"无人做过 X",但相关工作引了 [[Y]] 而 Y 实际就在做 X → flag |
| Critic 顾虑 vs Reframings 处理 | Critic 标 dealbreaker 的某点,Reframings 节不存在或没回应 → flag |
| Feasibility risks vs Plan milestones | 列了"硬件门槛 64 卡 RDMA"风险,Plan M1 假设单机 8 卡 → flag |
| Acronym/术语漂移 | 全文同一概念用了 "speculative gradient" / "shadow gradient" / "tentative update" 三种说法 → flag |
| 假设链 | "若 K < 8 则 KL < ε" 在某节当假设引,在另一节当结论用 → flag |

## Step 3 — Evidence Verification

对引用清单逐条核验。

### 3a — 内部论文 wikilink

对每个 `[[X-Conf25]]`:
- `Read wiki/papers/X-Conf25.md`(存在的话)
- 把 proposal 里对该论文的描述与 wiki 页内容比对:**有没有 misrepresent**?(把弱论点说成强结论、把 ablation 当 main result、把"提到"当"解决"、年份写错、作者写错)
- `--deep` 模式:从 wiki 页 frontmatter 拿 `source_md`,`Read markdowns/{dir}/{stem}/{stem}.md` 关键章节(`Grep` 关键词后窄窗口 Read)
- 找不到 wiki 页时 fallback:`Glob wiki/papers/{X}*.md` 或直接 `Glob markdowns/**/X*.md` 或 `Read papers/{...}/{...}.pdf`(只读最相关 2-4 页)

### 3b — 外部 URL

对每个外部 markdown link(arxiv / blog / paper homepage):
- `WebFetch <url>` 拿 abstract / intro
- 比对 proposal 里对该工作的 framing 是否准确
- 重点看:proposal 写"它已经做了 X",abstract 是不是真的说在做 X?(常见错误:proposal 凭关键词印象描述外部论文,abstract 一读发现实际是邻近问题)

### 3c — 系统 / 代码仓库引用

proposal 在「可复用代码」节常说 "可借 [[vLLM]] / [[SGLang]] / [Megatron repo](url)" 之类。逐条验证能力是否真存在:
- `WebFetch https://github.com/<owner>/<repo>` → 拿 README / project description
- `--deep` 模式:`gh search code` 或 `gh api repos/<owner>/<repo>/contents/<path>` 或直接 `WebFetch https://github.com/<owner>/<repo>/blob/main/<path>` 看关键文件是否真有需要的接口
- 重点看:"借 X 的 Y 模块" 时 X 是不是真有 Y 模块,是不是 public API,是不是已经 deprecate
- 命中"声称能借但实际不能借" → 标 `[serious]` critic

### 3d — Verification 结果归档

每条核验产出三种状态之一:
- `verified`:proposal 描述与证据一致 → 不动
- `mischaracterized`:描述失真 → 进 Critic 节 `[misrepresentation]` 类,inline 模式时**改正**proposal 原文
- `unverifiable`:无法核验(论文找不到、repo 私有、web 工具不可用) → 标注于 Review Log,不进 Critic

## Step 4 — Fresh Prior-Work Survey

proposal 创建后到今日,世界又新出了什么?

### 4a — 关键词抽取

从 proposal 的 tags + 标题 + Idea 节抽 3-5 个核心关键词。

### 4b — 时间窗口

从 frontmatter `created` 到 `currentDate` 的窗口里搜 site:arxiv.org:
- `WebSearch query="<关键词组合> site:arxiv.org {created.year}-{currentDate.year}"`
- 关注顶会:`OSDI / SOSP / MLSys / NSDI / ATC / NeurIPS / ICML / ICLR`
- 取前 5-10 个,挑日期晚于 `created` 且标题高度相关的 3-5 篇

### 4c — Scoop check

对挑出的新工作 WebFetch abstract,判定:
- `scooped`:整个 idea 已被这篇论文做了 → `[dealbreaker]` critic
- `partial-overlap`:部分核心 contribution 重叠 → `[serious]` critic
- `parallel`:同方向但不同 framing/方法 → 进相关工作节,不一定是 critic
- `irrelevant`:虽含关键词但实际不相关 → 丢弃

### 4d — 已知 prior-work 升级

proposal 引用的 paper,这一年内可能有该作者的后续工作或社区跟进 → 也补进相关工作节。

## Step 5 — Logical Fallacy Hunt

逐条排查。每条命中进 Critic 节 `[logical-fallacy]` 类,标具体类型与原文位置。

| 谬误 | 排查问题 |
|---|---|
| Strawman | 把 prior work 描述弱化以衬托本 idea 的 delta?(对照 Step 3a 的 wiki/markdown 验证) |
| 循环论证 | "这个 novel 因为没人做过,没人做过因为这是 novel 的方向"——novelty thesis 是否自我引用而非引证外部 evidence? |
| 含义漂移 | 某术语在不同节含义不一致(常见:"async" 在 Idea 是松耦合调度,在 Plan 是 NCCL 异步通信) |
| 假二分 | "要么 sync 要么 async,本 idea 选 async"——是否忽略了第三选项? |
| Speculation as fact | "本 idea 将达到 X%"——有没有 baseline 数据 / preliminary experiment / 类比工作支撑这个数字?还是凭直觉? |
| Cherry-pick baseline | 对比的 baseline 是不是已被 superseded?是不是只挑了对自己有利的 metric? |
| Hasty generalization | 单 workload / 单 hardware 的结论被推广为通用结论? |
| 因果错位 | "X 提升导致 Y 改善"——X 与 Y 的因果链是相关性还是因果性? |
| 复杂度藏在小字 | TL;DR 说"简单加一层 cache",Plan 里却要改 4 个组件 + 新协议 → Occam violation |
| 假设变结论 | "假设 KL 漂移 < ε" 在 Idea 节是开放假设,到 Verdict 节变成"已证明 KL < ε" |

## Step 6 — Re-apply Taste Rubric

按 frontmatter 的 `category`(或 Step 4 用的关键词 auto-detect)选 rubric——三套同 `/proposal` skill:

- **mlsys**:Workload 真实性 / 硬件趋势对齐 / Abstraction 层次 / 10x vs 2x
- **agent**:Model-proof / Workload 特征 / Framework vs System / Multi-agent 必要性
- **generic**(任何 category 必过):Reviewer 视角 / Occam's Razor / Adoption

每个维度产出三种状态:
- `still-strong`:原 Steel-man 在该维度的论点经 Step 3-5 后仍成立
- `weakened`:经核验证据被削弱(misrepresentation / scoop / fallacy 击中)
- `flipped`:从正面变成负面命中

`weakened` 与 `flipped` 都进 Critic 节。

## Step 7 — Critic Synthesis

汇总 Step 2-6 的所有发现到一个 Critic 列表。每条:

```
[<type>] [<severity>] <一句话 critique> — evidence: <具体引证>
```

- `<type>`:`inconsistency` / `misrepresentation` / `scoop-risk` / `logical-fallacy` / `rubric-fail` / `feasibility-flaw`
- `<severity>`:`dealbreaker` / `serious` / `minor`
- evidence 必须 concrete:论文 + 段落、URL、proposal 内具体行号或节名、repo 文件路径

**纪律**:同 `/proposal` skill,不接受空泛 critique。"看起来类似"、"可能有问题"全部丢弃。

## Step 8 — Generator Counter-defense(可选)

对每条 `dealbreaker` 与 `serious`,**给原作一次申辩机会**:

- 是否有非显而易见的 reading 让该 critique 不成立?
- 是否有不大改 proposal 主体就能修补的小调整?

写出 counter-defense 候选,**不强行 defend**——defend 不下来就在 Critic 节标"counter-defense 不成立"。

这一步避免 review 单方面把 proposal 打死,呼应 `/proposal` skill 的 "Reframing 优先于否决" 纪律。

## Step 9 — Reframings(条件)

触发条件同 `/proposal` skill:`dealbreaker ≥ 1` 或 `serious ≥ 3` 且 Step 8 counter-defense 不成立。

做法:
- proposal 已有 Reframings 节 → 在末尾**追加**新 reframing(不删除既有)
- 没有该节 → 新建,放在 Critic 节后

每个新 reframing 仍要写:
- 怎么具体绕开新 critic 顾虑
- 自身新顾虑
- 与 prior work 关系

## Step 10 — Apply Edits to the Proposal

按 `--mode` 决定写法。三种模式都遵守:**不删除原内容,只增量修补**(用户的"final clean version"原则在 review 场景下做例外——保留 Steel-man 历史给人看演化轨迹更重要)。

### Mode `inline`(默认)

对 proposal 文件做以下修改:

1. **Frontmatter**:
   - `last_updated` → 今日
   - 老 schema 补 `category` 与 `verdict: pending`
   - `related_papers / related_concepts / related_systems` 补新发现的引用(去重)
   - `novelty` / `feasibility`:**不直接覆盖**——若 review 强烈建议下调,在 Verdict 节写明,frontmatter 等人改
2. **正文逐节**:
   - `相关工作(仓库内)` / `相关工作(外部)`:append 新发现的论文条目(Step 4c-d)
   - `Steel-man`:不动(它是历史快照)
   - `Critic`:append 新 critic(Step 7),按 severity 倒序
   - `Reframings`:append 新 reframing(Step 9)
   - `可行性评估`:发现 misrepresentation 时改正具体数字 / 描述
   - `实现规划`:发现 inconsistency 时**不直接改**,而在受影响的 milestone 末尾加一行 `> [Review {date}] {issue + suggested fix}`,留给人改
   - `Verdict`:append 一段「[Review {date}]」更新决策摘要;`AI 推荐`部分可改但保留旧推荐对照
3. **末尾追加 `## Review Log` 节**(若已存在 → append entry,不覆盖):

```markdown
## Review Log

### [{YYYY-MM-DD}] proposal-review v1

- 模式:inline / surface / report
- 引用核验:{N} 篇内部 paper / {M} 个外部 URL / {K} 个 repo;{P} 处 mischaracterization 已修正
- 新增 critic:{n_dealbreaker} dealbreaker / {n_serious} serious / {n_minor} minor
- 新发现 prior work:{Q} 篇(其中 {scoop_count} 篇 scoop-risk)
- 一致性问题:{R} 处
- Logical fallacies:{S} 处
- Reframings 新增:{有/无}
- AI 建议:{keep / revise / reframe / archive}(决策权仍在你)
```

### Mode `surface`

只在末尾加 `## Review Log` 节,内容同上;**不**改其它节、不改 frontmatter `last_updated` 之外的字段。适合用户只想看一眼有什么问题。

### Mode `report`

proposal 文件只改 `last_updated` 与末尾 `## Review Log`(简短指向 report 文件);完整 review 写到:

`proposals/_reviews/{Slug}-{YYYYMMDD}.md`

Report frontmatter:

```yaml
---
type: proposal-review
target: "[[{Slug}]]"
target_path: "proposals/{Slug}.md"
reviewed_at: {YYYY-MM-DD}
mode: report
deep: {true|false}
recommendation: {keep | revise | reframe | archive}
---
```

Report 正文结构:

```markdown
# Review of {title}

## Summary
{3-5 句:原 proposal 主张 + 本次 review 最严重发现 + AI 推荐}

## 引用核验明细
- 内部:逐条 verified / mischaracterized / unverifiable
- 外部:逐条
- 系统/repo:逐条

## Internal Consistency
{Step 2 命中清单}

## Logical Fallacies
{Step 5 命中清单}

## Fresh Prior-Work
{Step 4c-d 命中清单 + scoop 判定}

## Taste Rubric Re-evaluation
{Step 6 表格,标 still-strong / weakened / flipped}

## Critic 列表
{Step 7 全量}

## Generator Counter-defense
{Step 8}

## Reframings(若触发)
{Step 9}

## 推荐
- {keep | revise | reframe | archive}
- 一段说明
- 决策权在人
```

## Step 11 — 追加 `proposals/_log.md`

不论模式,都 append:

```markdown
## [{YYYY-MM-DD}] {Slug} (review)

- target: proposals/{Slug}.md
- mode: {inline|surface|report}
- deep: {true|false}
- 引用核验:{N} 内 / {M} 外 / {K} repo;{P} 处修正
- 新增 critic:{a} dealbreaker / {b} serious / {c} minor
- 新发现 prior work:{Q}({scoop} scoop-risk)
- 一致性问题:{R}
- 谬误:{S}
- AI 推荐:{keep|revise|reframe|archive}
- report file:{有则 `proposals/_reviews/{Slug}-{YYYYMMDD}.md`,无则 "无"}
```

## Step 12 — 不写 `wiki/log.md`

`wiki/log.md` 是 wiki 层的活动日志,proposal 与 proposal-review 都是独立层,**不进 wiki/log.md**。所有 review 活动只 append `proposals/_log.md`(Step 11)。

## Step 13 — 简短汇报

```
review 完成:proposals/{Slug}.md
模式:{mode}({deep ? "deep" : "normal"})
引用核验:{N} 内 / {M} 外 / {K} repo({P} 处修正)
新增 critic:{a}/{b}/{c}(dealbreaker/serious/minor)
新发现 prior work:{Q}({scoop} scoop-risk)
一致性问题:{R} 处
谬误:{S} 处
reframing 触发:{有/无}
AI 推荐:{keep|revise|reframe|archive}
report file:{路径或"无"}
失败记忆已更新:proposals/_log.md
```

## Important Notes

- **Review 不替代决策**:本 skill 不改 `status` 与 `verdict` 字段。再狠的 critique 也只是 evidence,decision 在人。
- **不删除原内容**:Steel-man、原 Critic、原 Reframings 都保留——proposal 的演化轨迹本身有价值。新发现 append 不 overwrite。Verdict 节可以 append 更新版,但旧版保留对照。
- **改正 vs 追加的边界**:数字、年份、作者名、明确事实错误 → inline 改正;主观判断、framing 偏好、决策推荐 → 追加,不动原文。
- **Critic 必须 concrete**:同 `/proposal` skill 的纪律。每条 critique 必须给出具体论文 + 段落 / URL / 文件 + 行号 / proposal 节 + 行号。"看起来"、"可能"、"似乎"全部丢弃。
- **Counter-defense 是必经环节**:不让 review 单方面打死 proposal。给原作一次申辩,再下结论。
- **Failure memory 双向用**:Step 0 读历史 review;若本 proposal 之前被 review 过且当时的 critique 仍成立 → 本次 review 引用该历史,标"重复未解决"。
- **Schema 升级是顺手事**:遇到老 schema 补 `category` + `verdict`,但不强制重写已有节,逐步演化。
- **不污染 wiki**:proposal-review 产物不进 `wiki/index.md`,不被 `wiki-update` / `wiki-lint` 处理。proposal 文件本身的 wikilink 引仓库内 paper 仍走标准规则。
- **token 预算**:默认 ~30k,`--deep` ~80k。控不住时优先级:核验 > 一致性 > 新 prior work > 谬误。
- **review 一次只针对一个 proposal**:用户要批量 review 时让用户分次调用。
- **wikilink 规范**:同主仓库——内部 `[[X]]`,frontmatter wikilink 双引号包裹,表格内 `|` 转义 `\|`,禁止 `[[X]](path)` 混合写法。
- **不写 commit、不动 git**:本 skill 只编辑 proposal 文件 + 写 log,不做 git 操作。
