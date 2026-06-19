---
name: wiki-entity-concept
description: "Rebuild one wiki entity or concept page from regenerated paper pages and inbound wikilinks. Triggers on /wiki-entity-concept <page-name> or when rebuilding entity/concept pages after a paper wiki rebuild."
---

# Wiki Entity / Concept Rebuild Skill

Rebuild exactly one `wiki/entities/{Page}.md` or `wiki/concepts/{Page}.md` page from the current regenerated paper wiki corpus. This skill is for rebuild workers: each worker owns one output file and must not edit shared files.

## Usage

```
/wiki-entity-concept <page-name> --kind {entity|concept} [--output <path>]
```

- `page-name`: canonical filename stem, e.g. `vLLM`, `KV-Cache`
- `--kind entity`: write `wiki/entities/{Page}.md`
- `--kind concept`: write `wiki/concepts/{Page}.md`
- `--output <path>`: optional forced output path; must be under `wiki/entities/` or `wiki/concepts/`

## Inputs

1. Read the old page if it exists and preserve useful stable metadata:
   - `aliases`
   - entity `kind`, `status`, `tags`
   - concept `parent`, `tags`
2. Search regenerated paper pages for inbound wikilinks:
   - `[[{Page}]]`
   - `[[{Page}|...]]`
   - aliases from old frontmatter, if available
3. Read all directly inbound paper pages. If inbound > 30, read the first 30 most relevant pages plus all pages whose title or summary strongly centers this entity/concept.

## Output Templates

### Entity

```markdown
---
type: entity
kind: {system|org|benchmark|dataset|tool}
aliases: [...]
status: {active|inactive|unknown}
last_updated: YYYY-MM-DD
tags: [...]
---

# {Page}

> {一句话说明这个 entity 是什么、为什么在 wiki 图谱中重要。}

## 是什么

{2-4 段。说明 entity 的角色、边界、主要能力/用途，不做 marketing。}

## 关键观察 / 隐含假设

- **观察 / 假设 1**：{从 inbound paper 的 critical note 中提炼。必须附 wikilink 证据。}

## 演进时间线

- {Year} {Venue}：[[Paper]] — {该 paper 如何改变/使用/挑战这个 entity。}

## 相关概念

- [[Concept1]]、[[Concept2]]

## 相关论文

- [[Paper1]] — {一句话关系}
```

### Concept

```markdown
---
type: concept
aliases: [...]
last_updated: YYYY-MM-DD
tags: [...]
---

# {Page}

> {一句话定义 concept，并说明它解决什么系统问题。}

## 核心思想

{2-4 段。解释机制、抽象、适用边界。}

## 为什么重要

{2-4 段。说明它在多个 paper 中反复出现的原因、资源/正确性/SLO/部署含义。}

## 关键观察 / 隐含假设

- **观察 / 假设 1**：{从 paper 页的 `关键观察 / 隐含假设` 和 `Critical Analysis` 聚合，必须有 wikilink 证据。}

## 设计空间与取舍

- **路线 1**：{不同 paper 如何实现该概念，以及牺牲什么。}

## 引用本概念的论文

- [[Paper1]] — {一句话说明该 paper 如何使用/推进/挑战该概念。}

## 已知局限 / 开放问题

- {来自 paper 页 `局限与 Future Work` 的可验证 open problem。}
```

## Rules

- Use Chinese prose; keep technical terms in English.
- Use Obsidian wikilinks only; no markdown links for internal wiki pages.
- Quote any frontmatter wikilinks.
- Do not create shell pages. If there are no inbound papers and no strong reason from old page metadata, report that the page should not be rebuilt.
- Do not edit `wiki/index.md`, `wiki/log.md`, paper pages, conference pages, or theme pages.
- Preserve aliases when reasonable; add obvious aliases only when supported by paper text.
- Distinguish paper claims from your synthesis: use wording like “这些论文共同假设...” when aggregating.
