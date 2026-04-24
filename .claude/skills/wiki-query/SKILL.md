---
name: wiki-query
description: "Answer natural-language questions by walking the wiki: start from wiki/index.md, drill into relevant entity/concept/comparison/theme pages, traverse paper wikilinks, fall back to markdowns/ when needed. Triggers on /wiki-query <question>, '问 wiki'."
---

# Wiki Query Skill

回答跨论文问题时优先走 wiki 而不是满库 grep。Wiki 是 LLM 综合过的「半熟」知识层，比 raw markdown 快、比单篇 paper 全。

**执行模式：交互。** 答案输出到对话，不落盘；若用户后续要求存档，再显式 `Write` 到 `wiki/themes/` 或 `wiki/comparisons/`。

## Usage

```
/wiki-query <question>
```

问题示例：
- `KV cache 的分页管理是怎么演进的？`
- `vLLM 和 SGLang 在调度策略上有什么本质区别？`
- `最近两年 disaggregation 相关的论文有哪些？`
- `MoE 负载均衡的 open problems 是什么？`

## Step 1 — 从 index 起步

`Read wiki/index.md` 找到与问题相关的：

- Entity 页（系统/组织/benchmark）
- Concept 页（技术/机制）
- Conference 页（若问题涉及某会议）
- Theme 页（若问题涉及跨论文趋势）
- Comparison 页（若问题涉及系统对比）

**决策原则**：至少打开 2-3 个相关 wiki 页，别只读 1 个。不相关的不打开。

## Step 2 — 读 wiki 页并顺 wikilink

Read 选中的 wiki 页。对每页：

1. 读完主体内容
2. 识别页内 wikilink 到的 paper 页（`[[{Name}-{Conf}{Year}]]`）
3. 按问题判断是否需要深入读 paper 页：
   - 问题要具体数字/结果 → 需要读 paper 页
   - 问题要概念/脉络 → wiki 页本身可能已够
4. Read 相关的 paper 页（一次最多 5-10 篇，避免上下文爆炸）

## Step 3 — Fallback 到 markdowns

如果 wiki 页和 paper 页都不够（paper 页是极简版，细节不在其中），fallback 到 `markdowns/`：

- 从 paper 页 frontmatter 读 `source_md`
- `Read markdowns/{dir}/{stem}/{stem}.md`
- 优先用 `Grep` 在 markdown 里查找关键词（章节标题、术语、公式编号）再 Read 窄窗口，避免全文读

## Step 4 — 综合答案

输出结构建议：

- **简答**（1-3 句直接回答问题）
- **展开**（分 2-4 个小节，每段 wikilink 证据）
- **相关 wiki 页**：列出本次走过的 3-5 个核心 wiki 页作为「延伸阅读」
- **信息缺口**（如有）：坦诚说明哪里缺数据，需要读原始 markdown 补

**所有引用用 wikilink**：`[[{Name}-{Conf}{Year}]]` 或 `[[{Concept}]]`，不用 `[text](url)`。

### 答案示例

```markdown
## 简答
KV cache 的分页管理核心思想是把 LLM 推理的 cache 当 OS 虚存分页处理，从 [[PagedAttention]] 起步，到近两年分化出 prefix sharing / attention-head-aware / disaggregated 等多条路线。

## 演进脉络

### 起源：PagedAttention (2023)
[[vLLM-SOSP23]] 提出 [[PagedAttention]]...

### 分化一：prefix-aware
[[SGLang-OSDI25]] 用 RadixAttention...

### 分化二：head-aware
[[FlexiCache-MLSys26]] 观察到 attention head 时域稳定性...

## 延伸
- [[KV-Cache]]（概念总览页）
- [[PagedAttention]]
- [[vLLM-vs-SGLang]]
```

## Step 5 — 存档（可选）

若用户明确要求「把答案存到 wiki 里」：

- 综述型问题 → `Write wiki/themes/{ShortName}.md`
- 对比型问题 → `Write wiki/comparisons/{A}-vs-{B}.md`
- 按 CLAUDE.md 的 theme / comparison 模板填写

存档后在 `wiki/log.md` 追加一条：
```markdown
## [{YYYY-MM-DD}] query 存档：{Title}
- 生成：[[{ShortName}]]
- 原问题：{一句话}
```

**禁止** `[[{ShortName}]](wiki/themes/{ShortName}.md)` 这种 wikilink + paren 混合写法——`[[X]]` 已是有效 Obsidian 链接,后面的路径会被当成字面文本。

## Important Notes

- **不要 grep 全仓库**。走 wiki 是为了省上下文。除非问题明确涉及 wiki 没覆盖的角度。
- **一次读多个 wiki 页**（≤ 3 个），不要串行单点读。
- **Paper 页是极简的**，不要期望 paper 页能回答所有细节，fallback 到 markdowns 是正常路径。
- **Wikilink 密度**：答案每段至少 1 个 wikilink 作证据
- **坦诚缺口**：如果某 claim 在 wiki 里找不到证据，说「wiki 中未查到，需要读原始 markdown」，不要瞎编
- 答案不自动存档——用户要求才存
