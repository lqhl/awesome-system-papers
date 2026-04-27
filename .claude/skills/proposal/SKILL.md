---
name: proposal
description: "Use this skill when the user wants to turn a research idea into a structured proposal — survey related work (both internal repo papers via wiki and external arxiv / recent papers via web search), evaluate novelty, evaluate code-implementation feasibility, and lay out an implementation plan. Triggers on /proposal <idea>, '生成 proposal', '论文 idea 调研', '评估 idea novelty', 'idea 可行性', '帮我看看这个 idea 有没有人做过', '这个 idea 能不能落地'. Output is a single markdown page in proposals/ with unified Obsidian frontmatter."
---

# Proposal Skill

把一个 research idea 转成 `proposals/{Slug}.md`：调研 + 评 novelty + 评可行性 + 出实现规划。是研究计划,不是投稿用的 paper draft。

## 核心设计原则

这个 skill 的产出是**给人做最终决策的素材**,不是 AI 自己拍板的结论。要避免 LLM 自我批评循环里常见的失败模式:

- **Generator 与 Critic 分离**:同一个 agent 既写又批,批评必赢——idea 总能被找出"已有类似工作"否决。本 skill 把两者拆成两个独立 phase,各自有独立的 prompt 纪律。
- **Critic 必须 concrete**:不允许"看起来已被覆盖"这种空泛断言;每个否定点必须指出**具体哪篇论文 + 具体哪一点重复**(系统名 + 段落级 evidence)。
- **不让 AI 自我枪毙**:novelty/feasibility 评分都标记为 `generator-claim` 与 `critic-counter` 双值,**最终 verdict 留给人**(`status: draft`,`verdict: pending`)。即使 critic 很狠,也不自动 archive。
- **Reframings 优先于否决**:critic 指出致命问题时,先尝试 1-2 个"改框路径"——很多 idea 不是 idea 本身错,是 framing 不对。
- **嵌入 Taste Rubric**:用结构化 rubric 替代直觉打分,让评估可重复、可挑战。
- **Failure memory**:`proposals/_log.md` 跟踪所有曾经评过的 idea + 拒绝原因。新 idea 进来先扫一遍,避免重复劳动,也避免"上次否了的 idea 这次又否一遍同样理由"。
- **AI 负责广度,人负责深度**:AI 把所有相关论文/角度铺开;人来做最后的 taste filter。

整个过程读多写少。一次执行预算 ~30k token。

## Usage

```
/proposal <idea description> [--slug <name>] [--no-web] [--from-problem] [--category <mlsys|agent|generic>]
```

- `<idea description>`:自由文本。越具体越好。
- `--slug`:手指文件名(PascalCase,无空格)。不指定时按下文 fallback 推断。
- `--no-web`:跳过外部 WebSearch。
- `--from-problem`:**问题驱动模式**——idea 描述是一个 problem area(如"agent serving 的 multi-turn KV cache 管理"),skill 先去找声称解决该 problem 但 eval 有明显 gap 的论文,再据此构造 idea 候选。
- `--category`:强制指定 taste rubric 类别(默认 auto-detect)。

## Step 0 — Pre-flight + Failure Memory

1. `mkdir -p proposals/`(幂等)。
2. 取今日日期(`currentDate` 上下文)。
3. **读 `proposals/_log.md`**(若存在):扫历史 idea,看新 idea 是否与某条历史高度相似。相似阈值:tag 重叠 ≥ 2 个 + 关键词匹配。命中则在最终 Verdict 节里**显式提示用户**:"上次评过类似 idea `<Slug>`,verdict `<X>`,主要 critic 顾虑 `<reason>`。本次重新评估的差异点是 `<...>`。" 不强行复用结论。
4. 决定 `Slug`,fallback 顺序:
   1. `--slug` 传入 → 直接用
   2. idea 自带系统/方法名 → 用它(PascalCase,保留原大小写,如 `vLLM2Disagg`)
   3. 没有命名 → 提炼 2-4 词的核心动作+对象
5. **冲突处理**:`Glob proposals/{Slug}.md` 命中 → 加 `-{YYYYMM}` 后缀。再冲突加 `-v2`、`-v3`。

## Step 1 — 关键词抽取 + Category 判定

1. 把 idea 拆成 3-6 个**检索关键词**(技术术语 / 问题描述 / 系统名)。
2. **判 category**(用于后续选 taste rubric):
   - **mlsys**:出现 KV cache、scheduler、kernel、disaggregation、distributed training、quantization、speculative decoding、checkpoint、fault tolerance 等关键词 → `mlsys`
   - **agent**:出现 agent、tool use、planning、multi-agent、reflexion、RAG with action loop、long-horizon 等 → `agent`
   - **generic**:不明显归属上述类 → `generic`
   - 用户传 `--category` 时直接用之。

## Step 2 — 内部调研(wiki 优先)

走 `wiki/`,**不**全仓库 grep。

### 2a — 走 wiki/index.md

`Read wiki/index.md`,关键词命中:concept / entity / theme / comparison / conference 页加入待读列表。

### 2b — 读相关 wiki 页 + 顺 wikilink

并行 Read 3-5 个 wiki 页,从每页提取:
- wikilink 到的 paper 页 → 候选 internal references
- 子方向 / open problems / 已知 critique

挑 **8-15 篇最相关 paper 页** Read。判断标准:
- 同一 problem 不同方法 → **必读**(直接对比)
- 同一方法不同 problem → 选读
- 时间线起源论文 → **必读**(避免不知道祖宗工作)

### 2c — Fallback 到 markdowns(按需)

paper wiki 页太简、需要具体数字/实验/实现细节 → 从 frontmatter 拿 `source_md`,先 `Grep` 关键词再 Read 窄窗口。**不**整篇全读。

### 2d — `--from-problem` 模式专属

如果用户传了 `--from-problem`:
- 在挑出的 8-15 篇候选论文中,**逐篇扫"评估章节"**,标记每篇的 evaluation gap:
  - workload 是否人为构造(非 production trace)?
  - baseline 是否过时(没对比近期工作)?
  - hardware 是否单一(一种 GPU 型号 / 单数据中心)?
  - 是否只测了 happy path,没测 failure / tail / adversarial?
- 把这些 gap 整理成 "**问题但未真正解决**" 列表 → 后面 generator 据此构造 idea 候选。

### 2e — 内部空白识别

记下:wiki 里**没找到**直接对应工作的角度 → 潜在 novelty 信号。诚实标注,不假装"内部已穷尽"。

## Step 3 — 外部调研(WebSearch + WebFetch)

除非 `--no-web` 或无 web 工具。

### 3a — WebSearch 探最新论文

每个核心关键词组合 1-3 次 WebSearch,优先 `site:arxiv.org`:
- `WebSearch query="<关键词组合> site:arxiv.org 2025"` 或 `2026`
- 也可 `WebSearch query="<关键词组合> OSDI OR SOSP OR MLSys 2025"`
- 取前 5-10 个结果,挑年份新、标题高度相关的 3-5 篇

**避免**重复仓库内已有论文。

### 3b — WebFetch abstract

只读 abstract,不读全文。从每篇提取:
- 它解决什么 problem
- 用什么方法
- 与本 idea 的 **具体差距 / 相似度**(不是"看起来类似"——要能说出"它的方法 X 不能处理 Y 场景,本 idea 的方法 Z 能")

### 3c — 外部参考收集

收集箱条目:`{title, first_author + et al., year, url, 1-2 句关系描述}`。**关系描述**必须 concrete:不允许"covers similar topic",要写"它的 X 假设了 Y,本 idea 不依赖 Y"或"它已经做了 X,本 idea 的 X 是 superseded"。

Web 工具不可用时:在最终输出明确标注 `外部调研:跳过`。

## Step 4 — Taste Rubric

按 Step 1 判定的 category 选 rubric。这一步的产出会同时喂给 Generator(找正面命中)和 Critic(找反面命中)。

### Rubric: MLSys / AI Infra(`category: mlsys`)

| 维度 | 问题 |
|---|---|
| Workload 真实性 | 问题来自 production observation 还是人为构造?实验配置是实际部署会用的吗? |
| 硬件趋势对齐 | 下一代硬件上这个优化还成立吗?是在解决正在变大的问题还是正在消失的? |
| Abstraction 层次 | 改动在 stack 哪一层?是否需要用户改代码(adoption barrier)? |
| 10x vs 2x | 是挤最后 20% 性能,还是打开了新的 design space? |

### Rubric: Agent Systems(`category: agent`)

| 维度 | 问题 |
|---|---|
| Model-proof | 这个问题会随 model 进步自动消失吗?好的系统工作解决的是即使模型变强也存在的问题 |
| Workload 特征 | Agent 调用模式和传统 LLM serving 的本质区别是否被理解?(多轮依赖、动态 branching、长生命周期 session) |
| Framework vs System | 有没有涉及真正的 resource management / scheduling / fault tolerance?还是只是 prompt 工程套壳 |
| Multi-agent 必要性 | 拆成多个 agent 是否真的比 single agent + better prompting 好? |

### Rubric: Generic(`category: generic`)

| 维度 | 问题 |
|---|---|
| Reviewer 视角 | Baseline 最新吗?对比条件公平吗?Ablation 说明了每个设计选择的必要性吗? |
| Occam's Razor | 同样效果能不能用更简单的方法?系统复杂度和收益成正比吗? |
| Adoption | 发完论文有人会 adopt 吗?还是只是 paper system? |

**通用三条**(任何 category 都过一遍):上面 generic rubric 三条**必填**——即使是 mlsys 或 agent,也要顺手过一下 reviewer / Occam / adoption 三个角度。

## Step 5 — Generator Phase(Steel-man)

**Prompt 纪律**:这一步只做 idea 的"最强辩护人"。不允许在这一步否定 idea。任何顾虑暂存到 Step 6 的 critic 段。

产出:

1. **Novelty thesis**:1-3 句话,具体说出 idea 在哪一点上**确实是新的**。引证仓库内 wikilink 或外部 URL,说明"prior work 做了 X,本 idea 做的 X' 与 X 的差异是 Y"。
2. **Taste rubric 正面命中**:用 Step 4 选的 rubric,逐维度给出本 idea 在该维度上的**正面证据**。允许"在某维度上本 idea 没有特别强,但也没有 disqualify"——但不允许跳过维度。
3. **Reframing 候选**(预留):列出 2-3 个 idea 的 alternative framing,即"如果别人来包装这个 idea,可能怎么讲"。后面 critic 要是把主 framing 打死,这些是备选。

## Step 6 — Critic Phase(Devil's Advocate)

**Prompt 纪律**:这一步只挑刺。要求每条 critique 都满足以下三条之一,否则不写:

1. **Concrete prior-work overlap**:指出**具体论文** + **具体重复点**。例:"`[[X-OSDI24]]` 的 §4.2 已经做了 KV cache cross-request reuse,本 idea 的 reuse 机制 (§Idea 第 2 段) 与之差异不明显"。**不接受**:"已有类似工作"、"很多人做过"、"covers similar topic"。
2. **Rubric 反面命中**:用 Step 4 rubric,具体指出在某维度上的硬伤。例:"workload 真实性维度:本 idea 的 trace 是合成的,production observation 缺失"。
3. **可证伪假设**:指出 idea 依赖的某个未经验证的核心假设。例:"假设 KL 漂移在 K-step async 下保持 < ε,但 [Asynchronous RLHF] §5.3 的实测数据表明 K=8 时 KL 已超 ε"。

每条 critique 标 severity:`dealbreaker` / `serious` / `minor`。

**Critic 不下 verdict**——只列证据。最终判定在 Step 8。

## Step 7 — Reframings(条件)

**触发条件**:Step 6 产出至少 1 个 `dealbreaker` 或 ≥ 3 个 `serious` 顾虑。

**做法**:针对最严重的顾虑,从 Step 5 预留的 reframing 候选里挑 1-2 个,展开:
- 这个 reframing 怎么具体绕开 critic 的顾虑?
- 这个 reframing 自己又会引入什么新顾虑?(诚实标注)
- 这个 reframing 与 prior work 的关系如何?

不触发时:本节写 `Critic 顾虑可控,不需 reframing`。

## Step 8 — 可行性评估

把 idea(以及 reframings,如果有)拆成可工程化的组件:

- **核心组件**:3-7 个需要构建的模块(algorithm / scheduler / kernel / protocol)。
- **可复用代码**:能借的 baseline / 开源框架(`vLLM` / `SGLang` / `Megatron` / huggingface trl 等),列具体仓库或论文。
- **数据 / 算力需求**:benchmark + 硬件规模(几张 H100、是否需要多机 RDMA)。
- **关键技术风险**:未经验证的核心假设、可能 dealbreaker 的工程难点。
- **可行性分级**:`low` / `medium` / `high`
  - `high`:3-5 人小团队 4-8 周可完成 MVP;硬件门槛低(单机 8 卡内);不依赖未公开数据
  - `medium`:需要明确解决 1-2 个技术风险;硬件需要中等规模(16-64 卡)
  - `low`:依赖大规模专属硬件 / 未公开数据 / 需要先解决一个独立的 open problem

## Step 9 — 实现规划

按 milestone 拆,**每个 milestone 给可验证 deliverable**(不是"研究 X"这种伪 milestone):

- 至少 3 个 milestone(M1: 准备/baseline,M2: 核心方法,M3: 完整评测)
- 时间用相对量("~2 weeks"),不要绝对日期
- 验证标准必须**可机器/客观判定**("在 MMLU 上达到 X% accuracy" 而不是"work well")
- 标记 go/no-go gate:某 milestone 后若不达预期,pivot 到 reframing(如果有)或 archive

## Step 10 — Verdict(留给人)

**这一步不是 AI 拍板,而是把 generator + critic + reframing 的证据**结构化呈现**给人**。

写一段决策摘要:

```
- Generator 主张:<1-2 句>
- Critic 最强顾虑:<1-2 句,引最严重的 critique>
- Reframings:<有/无,主要 alternative 是 X>
- Failure memory:<Step 0 命中过就写,否则空>
- 推荐路径:<proceed | reframe | defer | archive>(AI 推荐,可挑战)
```

**`status` frontmatter 永远初始为 `draft`**——即使 critic 很狠也不自动 archive。`verdict` 字段标 `pending`(默认)、`proceed`、`reframe`、`defer`、`archive`,但**默认 `pending`,等人改**。

`novelty` 字段记 generator 的主张(`high` / `medium` / `low`),`feasibility` 记 Step 8 的判定。**两者都是评分快照,verdict 才是行动指令**。

## Step 11 — Write `proposals/{Slug}.md`

正文用**中文**,技术术语保留英文。

### Frontmatter(统一字段,必填)

```yaml
---
type: proposal
name: {Slug}
title: {一句话 idea 标题,<= 80 字符}
status: draft
created: {YYYY-MM-DD}
last_updated: {YYYY-MM-DD}
tags: [tag1, tag2, tag3]
related_papers: ["[[X-Conf25]]", "[[Y-Conf24]]"]
related_concepts: ["[[Concept1]]", "[[Concept2]]"]
related_systems: ["[[System1]]"]
category: {mlsys | agent | generic}
novelty: {low | medium | high}
feasibility: {low | medium | high}
effort: {short | medium | long}
verdict: pending
---
```

字段说明:
- `category`:**新**——Step 1 判定的类别,决定了用哪套 rubric
- `verdict`:**新**——`pending`(默认) / `proceed` / `reframe` / `defer` / `archive`,留给人改
- `novelty`/`feasibility`:generator/Step 8 的评分快照,**不是**最终决策
- `effort`:`short` (< 2 周) / `medium` (2-8 周) / `long` (> 8 周)
- 其它沿用原规则。

### 正文结构

```markdown
# {title}

> **TL;DR**:{一句话 + 核心方法 + 预期结果指标}

## Idea

{2-4 段:问题动机、提议方法、预期收益}

## 相关工作(仓库内)

按子主题分组(动态推断,2-4 组)。每组 3-6 条,每条一行 wikilink + 一句话与本 idea 关系。

### {Subtopic 1}
- [[{Name}-{Conf}{Year}]] — {差距 / 相似 / 可借,一句话}

## 相关工作(外部)

每条 markdown link 到 URL。

- {Author} et al. ({Year}) [{Title}]({URL}) — {差距 / 相似,一句话}

> 若 Step 3 跳过:`本次未跑 WebSearch;后续若纳入仓库需补外部调研。`

## Taste Rubric({category})

| 维度 | 评估 |
|---|---|
| {维度 1} | {一句话评估,可同时含 + 与 −} |
| ... | ... |

## Steel-man(generator 视角)

- **Novelty thesis**:{1-3 句具体新颖点,引证 [[X]] 或 URL}
- **Rubric 正面命中**:
  - {维度 1}:{正面证据}
  - ...
- **Reframing 候选**:
  - {Alt 1}:{1 句话}
  - {Alt 2}:{1 句话}

## Critic(devil's advocate 视角)

每条 critique 标 severity。

- **[dealbreaker]** {具体论文 + 具体重复点 / rubric 反面 / 可证伪假设}
- **[serious]** ...
- **[minor]** ...

## Reframings

{若 Step 7 触发}

### Reframing 1: {alt 名}
- 怎么绕开 critic:{...}
- 自身新顾虑:{...}
- 与 prior work 关系:{...}

{若未触发}:Critic 顾虑可控,不需 reframing。

## 可行性评估

- **核心组件**:
  - {组件:作用 + 工作量}
- **可复用代码**:[[{System}]]、[GitHub repo](url)
- **数据 / 算力**:{benchmark + 硬件}
- **关键风险**:
  - {风险:何时验证 / 缓解}
- **总体判断**:{low | medium | high} — {1 段说明}

## 实现规划

### M1 — {名}(~{时间})
- {deliverable}
- 验证标准:{客观指标}

### M2 — ...
### M3 — ...

> **Go/No-Go gates**:M{N} 后若 {条件不达},pivot 到 {reframing 或 archive}。

## Verdict(待人决策)

- **Generator 主张**:{1-2 句}
- **Critic 最强顾虑**:{1-2 句}
- **Reframings**:{有/无,主要 alt 是 X}
- **Failure memory 命中**:{有则引,否则"无"}
- **AI 推荐**:{proceed / reframe / defer / archive} — {1 句理由}
- **决策权在你**:`status` 维持 `draft`,`verdict` 维持 `pending` 直到人手改。

## 开放问题

- {不确定点 1}
- {不确定点 2}

## 参考

- 内部相关:[[Concept1]]、[[System1]]
- 外部链接已在「相关工作(外部)」展开
```

### 写作原则

1. **wikilink 密度高**:内部一律 `[[wikilink]]`,外部用 markdown link。表格里 `|` 转义 `\|`。
2. **Critic 不允许空话**:每条 critique 必须 concrete(论文 + 段落 / rubric / 假设)。空话直接删。
3. **不重复全文**:每节有焦点,不在多节里 echo 同一段。
4. **Open Questions 必填**:100% 自信的 idea 通常没想透。
5. **不污染 wiki**:proposal 不进 `wiki/index.md`,不被 `wiki-update` 扫,不被 `wiki-lint` 检查。引仓库内论文 wikilink,引外部 URL。

## Step 12 — 追加 `proposals/_log.md`(failure memory)

`proposals/_log.md` 是本 skill 的**持久化历史**。每次生成 proposal 都 append 一条。新 idea 进来时(Step 0)读这个文件,做相似度比对。

格式(append 在文件**末尾**,正序时间):

```markdown
## [{YYYY-MM-DD}] {Slug}

- title: {title}
- category: {mlsys | agent | generic}
- tags: {tag1, tag2, tag3}
- novelty(generator): {low|medium|high}
- feasibility: {low|medium|high}
- verdict(initial AI 推荐): {proceed|reframe|defer|archive}
- 主要 critique:{1-2 句最严重的 critic 顾虑}
- 主要 reframing:{有则 1 句,否则"无"}
- file: `proposals/{Slug}.md`
```

文件不存在时先创建,加一行标题:

```markdown
# Proposal Log

本文件 append-only 跟踪所有曾经评过的 idea + 拒绝 / 接受原因。供 `/proposal` skill 在 Step 0 做相似度检查,避免重复评估,也避免遗忘历史 critique。
```

## Step 13 — 不写 `wiki/log.md`

`wiki/log.md` 是 wiki 层的活动日志,proposal 是独立层,**不进 wiki/log.md**。proposal 生成只 append `proposals/_log.md`(Step 12)。

## Step 14 — 简短汇报

```
生成:proposals/{Slug}.md
title:{title}
category:{mlsys|agent|generic}
内部引用:{N} 篇 paper / {M} 个 concept
外部引用:{K} 条 (或「跳过」)
novelty(generator):{low/medium/high}
feasibility:{low/medium/high}
critic 主要顾虑:{1 句}
reframing:{有/无}
verdict:pending — 等你 review
失败记忆已更新:proposals/_log.md
```

## Important Notes

- **Generator/Critic 严格分离**:一个 phase 里只做一件事。Generator 不允许吐槽,Critic 不允许找补。最终结论留给 Verdict + 人。
- **Critic 必须 concrete**:每条否定都要有具体论文 + 具体段落 / 维度 / 假设。"已有类似工作"是无效 critique,直接删。
- **不自动 archive**:`status: draft`,`verdict: pending`。即使 novelty=low 也不自动归档——历史经验是 AI 在这一步过度否定。让人决定是否保留为种子。
- **Reframing 优先于否决**:dealbreaker 出现时,先尝试改框,不直接 archive。很多 idea 不是 idea 错,是 framing 不对。
- **Failure memory 双向使用**:既避免重复评估,也避免遗忘——上次否的理由这次还成立吗?用户可能在间隔期看到了新论文。
- **Taste rubric 是 floor 不是 ceiling**:维度都过一遍,但不要被框死。出现 rubric 之外的洞见时,写进 Steel-man 或 Critic 的自由文本节。
- **proposal 是研究计划,不是 paper draft**:不写 contributions、abstract、future work。落点是「该不该做、怎么做」。
- **wikilink 规范**:内部一律 `[[X]]`,frontmatter wikilink 必须双引号包裹;表格内 `|` 转义 `\|`;禁止 `[[X]](path)` 混合写法。
- **不同 idea 不同 proposal**:一个 idea 一份。"idea"实际是两个独立方向时,按主要那个写,次要写进 Open Questions 建议拆分。
- **相对日期**:milestone 用相对量("~2 weeks");frontmatter 用绝对日期。
- **token 预算**:单次 ~30k 内。控不住时优先砍 WebFetch 数量,然后砍 wiki paper 页数。Generator 与 Critic 各自的 token 预算大致对半。
