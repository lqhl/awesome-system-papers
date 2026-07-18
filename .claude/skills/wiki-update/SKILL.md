---
name: wiki-update
description: "After writing a new paper wiki page, scan it for entity/concept mentions, especially observations/assumptions/critique sections, then update relevant wiki pages + append log. Triggers on /wiki-update with a paper path or when auto-called by wiki-paper."
---

# Wiki Update Skill

Given a fresh paper wiki page, 扫描其中出现的已知 entity/concept 名，补 wikilink、更新被引页、记 log。**不自动建新 entity/concept 页**——只把高频缺页写入 log 的 TODO 行，人工决定是否升级。

**执行模式：无人值守。**

## Usage

```
/wiki-update <paper-wiki-path>
```

- `paper-wiki-path`：形如 `wiki/papers/{Name}-{Conf}{Year}.md`

## Step 1 — 构建已知 entity/concept 索引

1. `Glob wiki/{entities,concepts}/**/*.md`
2. 对每个文件，从文件名提取主 name（去 `.md`）+ 从 frontmatter `aliases` 提取别名
3. 得到 `{page_name: filename}` 映射，包括所有 aliases

示例：
```
{
  "vLLM": "vLLM.md",
  "Virtual-LLM": "vLLM.md",          # alias
  "KV-Cache": "KV-Cache.md",
  "KV cache": "KV-Cache.md",         # alias
  "kv cache": "KV-Cache.md",         # alias (lowercase)
  "PagedAttention": "PagedAttention.md",
  "Paged Attention": "PagedAttention.md",  # alias
  ...
}
```

## Step 2 — 扫描 paper 页

`Read {paper-wiki-path}`，按 name/alias 匹配：

- **匹配粒度**：整词匹配（regex `\b{Name}\b`），避免 `MoE` 匹配到 `MoEGL`
- **大小写**：按 alias 表里记录的大小写匹配（别名表里一般包含常见变体）
- **首次出现优先**：对每个匹配的 entity/concept，只处理**第一次**出现
- **高价值章节优先**：如果同一术语同时出现在普通叙述和 `关键观察 / 隐含假设`、`核心方法`、`设计取舍`、`Critical Analysis`、`局限与 Future Work` 中，优先给这些章节里的首次出现补 wikilink。这样 backlinks 更容易落在有研究判断的位置。

先运行确定性 linker：

```bash
# 默认 dry-run，只输出 unified diff
python3 .claude/skills/wiki-update/linker.py wiki/papers/{Page}.md

# 审核 diff 后显式应用
python3 .claude/skills/wiki-update/linker.py wiki/papers/{Page}.md --apply
```

脚本按 alias 长度和章节优先级匹配，跳过 frontmatter、code、已有 wikilink，并忽略存在 alias 冲突的术语。只有脚本无法安全定位时才使用手工单点 Edit。

## Step 3 — 补 wikilink（单点编辑）

对每个 entity/concept 的首次出现：

- 若该位置已是 wikilink（已有 `[[...]]`）→ 跳过
- 若不是 wikilink → 用 `Edit` 替换为 `[[{CanonicalName}|{原文}]]`

关键约束：

- 脚本无法处理时用 Edit，不用 replace_all。每次只改首次出现那一处
- old_string 要包含足够上下文（前后各 20-30 字符）以保证唯一
- 若 old_string 不唯一（一段话里该术语出现多次）→ 扩大上下文，或用行号+行内容组合定位
- 若无法安全定位（罕见）→ 跳过该项，在输出里注明

示例：

原文：`该系统基于 vLLM 的 PagedAttention 思路，进一步优化了 KV cache 复用。`

处理后：`该系统基于 [[vLLM|vLLM]] 的 [[PagedAttention|PagedAttention]] 思路，进一步优化了 [[KV-Cache|KV cache]] 复用。`

（注：显示文字保留原文大小写/空格，链接目标用 canonical filename。）

## Step 4 — 更新被引 entity/concept 页

对每个被新加 wikilink 的 entity/concept 页：

1. `Read wiki/{entities|concepts}/{PageName}.md`
2. 找「相关论文」或「演进时间线」节（entity 页是「演进时间线」，concept 页是「相关工作」或「引用本概念的论文」）
3. 检查是否已包含本 paper 的 wikilink（去重）
4. 若未包含，追加一行。摘要优先使用 paper 页里的 observation / assumption / critique 信息，而不是只写“使用了该概念”。

**Entity 页（演进时间线）**：按年份排序插入：
```markdown
- {Year} {Venue}：[[{Name}-{Conf}{Year}]] — {一句话说本论文和此系统的关系；如相关，补一句它依赖或挑战了什么假设}
```

**Concept 页（引用本概念的论文）**：
```markdown
- [[{Name}-{Conf}{Year}]] — {一句话说本论文对此概念的使用/贡献；如相关，说明关键观察、隐含假设或局限}
```

Note：Concept 页如果写了 `## 引用本概念的论文` 节，本 skill 维护此节。如果没写这节（因为 Obsidian backlinks 已经能显示），跳过这步；backlinks 是反向索引的真正源，本 skill 的作用是「额外的人工可读 summary」。

## Step 5 — 高频缺页 watchlist

从 `wiki/.quality.yml` 读取 entity/concept watchlist 与 inbound threshold。不得在 SKILL.md 或实现中复制另一份常量。

扫描 paper 页，若出现 watchlist 里的词但对应 wiki/entities 或 wiki/concepts 没有页 → 在 log.md 追加 TODO 行：

```markdown
- TODO: 考虑建 [[{PageName}]] 页（在 [[{PaperName}-{Conf}{Year}]] 中被引用，但 wiki 暂无）
```

**不自动建页**——避免建空壳页稀释 graph view。

## Step 6 — 追加 log.md

在 `wiki/log.md` 顶部插入一条（倒序）：

```markdown
## [{YYYY-MM-DD}] {PaperName}-{Conf}{Year} wiki-update
- 补 wikilink：[[{Entity1}]]、[[{Concept1}]]、...
- 更新：[[{Entity1}]]、[[{Concept1}]]
- TODO：[[{MissingPage}]]（若有）
```

**禁止** `[[X]](wiki/path/X.md)` 这种 wikilink + paren 混合写法——`[[X]]` 已是有效 Obsidian 链接,后面的路径会被当成字面文本。引用 wiki 页一律只用 `[[X]]`。

## Step 7 — 简短汇报

```
/wiki-update 完成
补 wikilink：{N} 处
更新页：{M} 个
TODO 缺页：{K} 个（见 wiki/log.md）
```

## Important Notes

- **不用 Edit replace_all**：每次只改「首次出现」那一处。重复的 wikilink 会让正文变花。
- **不自动建新 entity/concept 页**。只写 TODO 行到 log。
- **大小写敏感**：保留 paper 原文大小写作为显示文字；链接目标用 canonical filename。
- **别名归一**：`KV cache` / `KV Cache` / `kv-cache` 都应链到 `KV-Cache.md`（别名表里登记）。
- 若 paper 页本身已被某 entity/concept 以 wikilink 形式引用 → 跳过该项，不重复加
- 新版 `wiki-paper` 的高信息量通常在 `关键观察 / 隐含假设` 与 `Critical Analysis`；更新 entity/concept 摘要时优先从这些节提炼一句话
- 无人值守：遇到匹配歧义（如「MoE」出现在两个不同含义的上下文）优先按首次出现处的最近含义处理；若歧义严重，跳过并在输出里注明
- 本 skill 由 `wiki-paper` 自动末尾调用；也可单独手动触发
