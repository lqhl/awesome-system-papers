---
name: wiki-query
description: "Answer natural-language questions by walking the wiki: start from wiki/index.md, drill into relevant pages, traverse paper wikilinks, use observations/assumptions/critical analysis, and fall back to markdowns when needed. Triggers on /wiki-query {question}, '问 wiki'."
---

# Wiki 查询 Skill

回答跨论文问题时优先走 wiki 而不是满库 grep。Wiki 是 LLM 综合过的「半熟」知识层，比 raw markdown 快、比单篇 paper 全。

**执行模式：交互。** 答案输出到对话，不落盘；若用户后续要求存档，再显式 `Write` 到 `wiki/themes/` 或 `wiki/comparisons/`。

## 共享中文写作契约

在生成对话答案、表格、延伸阅读摘要或存档页前，必须完整阅读并执行 [中文写作与术语解释契约](../_shared/chinese-writing.md)。常用系统缩写直接使用；短答案只解释非标准术语，长篇跨领域答案确有需要时才增加简短的「阅读提示」。

## 用法

```
/wiki-query <question>
```

问题示例：
- `KV cache 的分页管理是怎么演进的？`
- `vLLM 和 SGLang 在调度策略上有什么本质区别？`
- `最近两年 disaggregation 相关的论文有哪些？`
- `MoE 负载均衡的 open problems 是什么？`

## 步骤 1 — 从 index 起步

`Read wiki/index.md` 找到与问题相关的：

- Entity 页（系统/组织/benchmark）
- Concept 页（技术/机制）
- Conference 页（若问题涉及某会议）
- Theme 页（若问题涉及跨论文趋势）
- Comparison 页（若问题涉及系统对比）

**决策原则**：至少打开 2-3 个相关 wiki 页，别只读 1 个。不相关的不打开。

## 步骤 2 — 读 wiki 页并顺 wikilink

Read 选中的 wiki 页。对每页：

1. 读完主体内容
2. 识别页内 wikilink 到的 paper 页（`[[{Name}-{Conf}{Year}]]`）
3. 按问题判断是否需要深入读 paper 页：
   - 问题要具体数字/结果 → 需要读 paper 页
   - 问题要概念/脉络 → wiki 页本身可能已够
   - 问题问「是否成立 / 有什么问题 / 开放问题 / 后续工作 / 适合做什么」→ 必须读论文页里的 `关键观察 / 隐含假设`、`批判性分析`、`局限与后续工作`
4. Read 相关的 paper 页（一次最多 5-10 篇，避免上下文爆炸）

读新版 paper 页时按问题优先级取证：

- **演进/分类问题**：读 `问题与动机`、`核心方法`、`设计取舍`
- **可行性/是否站得住问题**：读 `关键观察 / 隐含假设`、`批判性分析`
- **开放问题 / proposal 前置问题**：读 `局限与后续工作`，再回看假设压力测试
- **数字/实验问题**：读 `实验与结果`；若细节不够，再 fallback 到 markdown

## 步骤 3 — 必要时回到原始 Markdown

如果 wiki 页和 paper 页都不够，fallback 到 `markdowns/`：

- 从 paper 页 frontmatter 读 `source_md`
- `Read markdowns/{dir}/{stem}/{stem}.md`
- 优先用 `Grep` 在 markdown 里查找关键词（章节标题、术语、公式编号）再 Read 窄窗口，避免全文读

## 步骤 4 — 综合答案

输出前在内部统一本次答案的术语表达，对相同概念只选一种写法，不默认输出术语表。来源页的中英混写不是可以照抄的引用格式。

输出结构建议：

- **简答**（1-3 句直接回答问题）
- **展开**（分 2-4 个小节，每段 wikilink 证据）
- **假设/证据/判断分离**（当问题涉及 critique）：明确区分论文 claim、wiki 页中的 critical inference、以及需要继续读原文或补实验的未知点
- **相关 wiki 页**：列出本次走过的 3-5 个核心 wiki 页作为「延伸阅读」
- **信息缺口**（如有）：坦诚说明哪里缺数据，需要读原始 markdown 补

**所有引用用 wikilink**：`[[{Name}-{Conf}{Year}]]` 或 `[[{Concept}]]`，不用 `[text](url)`。

### 答案示例

```markdown
## 简答
KV 缓存（key-value cache，KV cache）的分页管理，是把 LLM 推理中的中间状态当作操作系统虚拟内存分页处理。该路线从 [[PagedAttention]] 起步，后续分化出前缀共享、按注意力头管理和解聚部署等方向。

## 演进脉络

### 起源：PagedAttention (2023)
[[vLLM-SOSP23]] 提出 [[PagedAttention]]...

### 分化一：感知前缀复用
[[SGLang-OSDI25]] 用 RadixAttention...

### 分化二：感知注意力头
[[FlexiCache-MLSys26]] 观察到注意力头在时间维度上具有稳定性...

## 延伸
- [[KV-Cache]]（概念总览页）
- [[PagedAttention]]
- [[vLLM-vs-SGLang]]
```

## 步骤 5 — 存档（可选）

若用户明确要求「把答案存到 wiki 里」：

- 综述型问题 → `Write wiki/themes/{ShortName}.md`
- 对比型问题 → `Write wiki/comparisons/{A}-vs-{B}.md`
- 按 CLAUDE.md 的 theme / comparison 模板填写
- 写文件前完成共享契约的成稿语义审计，再运行定向 `wiki-lint --language-only`

存档后在 `wiki/log.md` 追加一条：
```markdown
## [{YYYY-MM-DD}] query 存档：{Title}
- 生成：[[{ShortName}]]
- 原问题：{一句话}
```

**禁止** `[[{ShortName}]](wiki/themes/{ShortName}.md)` 这种 wikilink + paren 混合写法——`[[X]]` 已是有效 Obsidian 链接,后面的路径会被当成字面文本。

## 重要说明

- **不要 grep 全仓库**。走 wiki 是为了省上下文。除非问题明确涉及 wiki 没覆盖的角度。
- **一次读多个 wiki 页**（≤ 3 个），不要串行单点读。
- **论文页是研究笔记**，优先使用其中的 `关键观察 / 隐含假设`、`批判性分析`、`局限与后续工作`；细节不足时再回到原始 Markdown。
- 回答的中文叙述、术语解释和可读性必须通过共享写作契约；专名、指标和代码标识按契约保留并首次解释。
- **Wikilink 密度**：答案每段至少 1 个 wikilink 作证据
- **坦诚缺口**：如果某 claim 在 wiki 里找不到证据，说「wiki 中未查到，需要读原始 markdown」；如果是自己的推断，显式标注为推断
- 答案不自动存档——用户要求才存
