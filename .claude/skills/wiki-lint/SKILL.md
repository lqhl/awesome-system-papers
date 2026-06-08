---
name: wiki-lint
description: "Health-check the wiki: orphan pages, broken wikilinks, missing frontmatter, high-frequency terms that lack pages, log.md format breakage, aliases conflicts. Triggers on /wiki-lint, '检查 wiki', 'wiki 体检'."
---

# Wiki Lint Skill

定期对 `wiki/` 做一次健康检查，发现的问题以 **报告** 形式输出（默认 read-only），附摘要写入 `log.md`。`--fix` 仅做最小安全修补（补 frontmatter、规范 log 行）。

**执行模式：read-only by default.**

## Usage

```
/wiki-lint [--fix]
```

- 无参数：只扫描 + 报告
- `--fix`：最小安全修补
  - 补齐 `last_updated` 字段（若缺）
  - 规范 log.md 行首（若某行 `## ` 但不符合 `[YYYY-MM-DD]` 格式）
  - **不**自动建页、不改内容、不重排 aliases

## 检查项

### 1. Broken wikilinks

扫描 `wiki/**/*.md` 里所有 `[[target]]` 或 `[[target|display]]`：

- 如果 `target` 以 `.pdf` 结尾 → 检查 `papers/**/` 下是否有对应文件
- 否则 → 检查 `wiki/**/`、`markdowns/**/` 下是否有对应 `.md` 文件
- 不存在 → 列为 broken link，附源文件路径 + 行号

注意：Obsidian 允许 wikilink 指向**不存在的文件**（显示为橘色链接，鼓励创建），某些情况是有意为之（比如 [[KV-Cache]] 暂时还没建页）。这类属于「**缺页**」而非「broken」——通过是否在 watchlist 区分。

### 1a. Hybrid wikilink + paren

扫描 `wiki/**/*.md` 里 `[[X]](...)` 这种 wikilink 紧跟半角小括号的写法——`[[X]]` 已是有效 Obsidian 链接,`(...)` 会被 markdown 解析器误读成链接 URL,导致渲染异常或链接失效。

- 错误模式：`\]\]\(`（即两个 `]]` 紧跟一个 `(`,中间无空格）
- 修法：去掉 `(...)` 部分（路径冗余）或把 `(` 换成全角 `（`（注释场景）
- 示例：`[[Finance]](wiki/themes/Finance.md)` → `[[Finance]]`；`[[RDMA]](inbound 10)` → `[[RDMA]]（inbound 10）`
- 命中行直接列入报告,`--fix` 模式不自动改（需人工判断是删 paren 还是换全角）

### 2. 高频缺页 watchlist

**目标**：找出 paper 页里频繁出现但 wiki 里没有对应 entity/concept 页的术语。

流程：

1. `Glob wiki/papers/*.md`
2. 对每个 paper 页，Read + grep watchlist 里的术语（本 skill 内置 watchlist，与 `wiki-update` 一致）
3. 统计每个术语的 inbound count
4. 对比 `wiki/entities/` 和 `wiki/concepts/`：
   - 已有对应页 → 跳过
   - 无对应页且 inbound ≥ 5（concept 阈值）或 inbound ≥ 3（entity 阈值）→ 列为「建议建页」

输出示例：
```
缺页 watchlist（建议建页）：
- Prefix-Caching (concept, inbound=28) — 缺页
- TensorRT-LLM (entity, inbound=15) — 缺页
- RadixAttention (concept, inbound=12) — 缺页
```

### 3. Orphan pages

找出**既无入站链接、也未在 index.md 出现**的 wiki 页：

- 对每个 `wiki/**/*.md`，反向查找是否有其他页 wikilink 到它（Grep）
- 若一个 entity/concept/comparison/theme 页既无入站 wikilink 也未在 `index.md` 出现 → orphan
- Paper 页一般不检查 orphan（新 paper 可能还没被其他页引用，但会被会议页引用）

### 4. Frontmatter 必填字段

对每类页检查 frontmatter：

- `type: paper`：`name, full_title, authors, venue, year, tags, source_pdf, source_md` 必填
- `type: conference`：`venue, year, paper_count, first_generated, last_updated` 必填
- `type: entity`：`kind, aliases, status, last_updated` 必填
- `type: concept`：`aliases, last_updated` 必填
- `type: comparison`：`subjects, last_updated` 必填
- `type: theme`：`last_updated, tags` 必填
- `type: proposal`：`name, title, status, created, related_papers, related_concepts, related_systems, novelty, feasibility, effort` 必填；`tags` 和 `target_venue` 建议填
- `type: probe`：`topic, created, probed_papers` 必填

缺字段 → 列为 warning，附文件路径 + 缺失字段名。

### 4a. Frontmatter wikilink quoted

扫描 frontmatter 里 `source_pdf` / `source_md` / `parent` / `introduced_by` / `subjects` 等字段，匹配未 quoted 的 wikilink：

- 错误模式 `^(parent|source_pdf|source_md|introduced_by|subjects):\s*\[\[`（即 `key: [[Value]]` 没有引号）
- 正确模式 `key: "[[Value]]"` 或 `key: ["[[A]]", "[[B]]"]`

未 quoted 的列为 warning，`--fix` 模式可自动加引号。原因：YAML 把 `[[X]]` 解析为嵌套数组而非字符串，Obsidian properties 面板会显示字面 `[["X"]]` 不可点击。

### 5. log.md 格式

扫描 `wiki/log.md`：

- 每条 `## ` 开头的行必须符合 `^## \[\d{4}-\d{2}-\d{2}\] .+$` 格式
- 违规行列出
- `--fix` 模式下，若能从上下文推断日期（如下一条 log 条目的日期），补齐；否则保留

### 6. Aliases 冲突

扫描所有 entity/concept 页的 `aliases` frontmatter：

- 建立 `{alias: [pages]}` 反向索引
- 若某 alias 指向 > 1 个页 → 冲突，列出

### 7. Paper 页未引用任何 entity/concept

`wiki/papers/*.md` 里若整篇 0 个 `[[...]]`（除 frontmatter 的 source_pdf/source_md 外）→ warning：可能 `wiki-update` 漏处理，或论文太特殊没有已建页对应的术语。

### 8. 命名规范

- Paper 页文件名必须符合 `{Name}-{Conf}{Year}.md`（`-OSDI25` / `-SOSP25` / `-MLSys26` / `-arXiv25` 等）
- Conference 页文件名必须符合 `{Conf}-{Year}.md`（大写 conf + 4 位年份）
- Entity / Concept / Comparison / Theme 页文件名用 PascalCase 或 kebab-case，全局唯一
- Proposal 页文件名用 PascalCase（如 `ThinkingModelKVCache.md`）
- Probe 页文件名用 kebab-case（如 `thinking-model-kv-cache.md`）
- 违规 → 列出

### 9. Proposal 缺 probe

对 `wiki/proposals/*.md`（`type: proposal`），检查是否有对应的 probe 文档：

- 从 proposal frontmatter 的 `related_concepts` / `related_papers` 推断可能的 probe slug
- 或从提案正文中「基于 probe」段落提取
- 若无法推断对应的 probe，不报 warning（非强制）
- 若可推断但 `wiki/proposals/probes/` 下不存在 → warning

### 10. Proposals/_log.md 格式

扫描 `wiki/proposals/_log.md`（同 check 5 的格式规则）：

- 每条 `## ` 开头的行必须符合 `^## \[\d{4}-\d{2}-\d{2}\] .+$` 格式
- 违规行列出

## 输出格式

```markdown
# Wiki Lint Report ({YYYY-MM-DD})

## Summary

- Broken wikilinks: {N}
- Hybrid wikilink + paren: {N1}
- 高频缺页建议：{M}
- Orphan pages: {K}
- Frontmatter warnings: {L}
- Log 格式违规: {P}
- Alias 冲突: {Q}
- Paper 页无 wikilink: {R}
- 命名违规: {S}
- Proposal 缺 probe: {T}
- Proposals log 格式违规: {U}

## Details

### 1. Broken wikilinks

- `wiki/papers/vLLM-SOSP23.md:42`: `[[NonExistent]]` —— 目标不存在

### 2. 高频缺页建议

...

(其余详细列出)

## 修复建议

- 建页：[[Prefix-Caching]]、[[TensorRT-LLM]]
- 手动修复 broken link 或创建对应页
- 可用 `/wiki-lint --fix` 补齐 `last_updated` / 规范 log
```

## --fix 模式

只做下列最小修补（不改内容、不建页）：

- 给缺 `last_updated` 字段的 wiki 页补今天的日期
- 给 `log.md` 里形如 `## 2026-04-24 foo`（缺 `[ ]`）的行补齐为 `## [2026-04-24] foo`
- 其余所有问题仅报告，不修改

## Step Final — 记 log

Lint 完成后，在 `wiki/log.md` 顶部追加一条：

```markdown
## [{YYYY-MM-DD}] wiki-lint
- Broken: {N} | 缺页: {M} | Orphan: {K} | Frontmatter: {L} | Log 违规: {P} | Alias 冲突: {Q} | 命名违规: {S} | Proposal: {T}
- 详见本次 lint report
- 模式：{read-only | --fix}
```

## Important Notes

- **只读默认**：未传 `--fix` 时不改任何 wiki 文件
- **`--fix` 很保守**：只做 3 类最小修补，绝不建页、不重写内容、不改链接
- **Watchlist 是动态的**：第一版硬编码与 `wiki-update` 同步；未来可以提取到 `wiki/.watchlist.yml`
- **不做 AI 判断**：lint 是规则扫描，不调用 LLM 推断内容对错。对错交给人或 `wiki-query`
- **Proposal/Probe 纳入 scope**：因已移入 `wiki/proposals/`，`wiki/**/*.md` glob 自动覆盖
- 无人值守：大报告不要询问，直接输出
