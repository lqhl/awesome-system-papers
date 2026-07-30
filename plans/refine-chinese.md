# 剩余 Wiki 中英文混杂治理计划

## 摘要

- 以 `b8d310f9` 为写作基准：正文、章节、表头和普通概念以中文为主；系统名、模型名、benchmark、API、指标、变量、代码标识保留英文。
- 逐篇回源复核剩余 429 篇旧模板论文页，覆盖约 33.8 MiB、256,905 行 source markdown；发现数字、归因或证据边界错误时同步修正，并在批次提交说明中记录。
- 随后治理 17 个 entity、45 个 concept、5 个 conference、3 个 theme、4 个 proposal、5 个 probe 和 `wiki/index.md`，共审计 509 个剩余知识页。
- `wiki/reports/` 保留在仓库中，但加入 Quartz `ignorePatterns`，不再发布，也不参与语言检查；`wiki/log.md` 与 `wiki/proposals/_log.md` 保持 append-only。

## 实施变更

### 1. 建立语言回归门槛

- 先为 `wiki-lint` 增加测试，再实现 `language_warnings` 和面向指定文件的 `--language-only PATH...` 检查。
- 论文页强制检查：
  - H1 含中文译名，并有与 `full_title` 对应的 `> **原题**`。
  - 禁止 `Claim–Evidence Map`、`Critical Analysis`、`局限与 Future Work` 等旧标题和英文证据表头。
  - 普通英文长句必须改为中文叙述；frontmatter、原题、代码块、公式、URL 和专名不误报。
- 其他知识页检查章节、表头和普通叙述；entity/concept/conference 的规范英文专名 H1 可以保留，proposal/probe/theme 的描述性标题必须中文为主。
- 默认 lint 将语言问题视为 actionable；迁移过程中允许全局计数单调下降，但每个已完成批次必须通过定向检查。
- 内容扫描排除 `wiki/reports/**`；更新 `wiki-lint` 文档说明报告属于未发布的运维产物。

### 2. 逐篇回源重写论文页

- 按 `finance(5) → foundation(7) → ai-infra(19) → FAST-2026(44) → OSDI-2025(53) → SOSP-2025(66) → ATC-2025(100) → MLSys-2026(135)` 的顺序处理。
- 每次以 3 篇为复核工作单元；同一 source 目录内按文件名字典序推进，每个提交不超过 15 篇且不跨目录。
- 对每篇完整阅读正文和相关附录；表格、公式或数字解析可疑时回 PDF 窄窗口核验。超长的 `151-Trading-Strategies-SSRN18` 单独处理。
- 原地重写并保留文件名、`name`、`source_pdf`、`source_md` 和 wikilink target；不触发逐页 `wiki-update`，避免反复改写下游页面。
- 更新 `last_reviewed`；只有全文和证据均核实后才保留 `complete/full-text`，否则按现有质量枚举降级。
- 语义修正不得在正文保留修改痕迹；详细修正写入该批次 Git 提交说明，`wiki/log.md` 每个 source corpus 只追加一条汇总。

### 3. 重建下游知识页

- 论文语料全部稳定后，基于最终入站论文重建现有 entity/concept；不新建页面、不批量回填旧链接、不改 aliases，除非原文直接证明 alias 错误。
- 再重建 5 个 conference 和 `AI-Infra`、`Finance`、`Foundation` 三个剩余 theme，重新核对 paper count、分类、设计空间矩阵、共同观察和假设冲突。
- 最后复核 5 个 probe 和 4 个 proposal：验证内部论文论断及外部引用，但不新增研究方向、不改变核心假设、status、taste 结论或 venue gradient；正文、章节和表头改为中文。
- 更新 `wiki/index.md` 的中文描述；proposal/probe 变更只向 `wiki/proposals/_log.md` 追加一条汇总，不写 `wiki/log.md`。
- 已治理的 23 篇 auto-research 页面、CausalGame、`Optimize-Anything` 和 `Auto-Research` 作为基准，除非下游事实修正影响它们，否则不重写。

### 4. 发布配置

- 在 `quartz/quartz.config.ts` 的 `ignorePatterns` 中加入 `reports`。
- 保留 `link_report.py`、`repair_manifest.py` 及其现有默认输出路径，不删除 `wiki/reports/`。
- 不修改 `papers/` 和 `markdowns/` 原始层，不重命名任何知识页。

## 测试与验收

- 单元测试覆盖中文 H1/原题、旧章节拒绝、中文表头、英文长段检测，以及 frontmatter、代码、公式、URL、API/专名豁免。
- 每个 3 篇单元执行定向语言检查、paper structure/quality 检查、source 链接核对和人工 diff 审查；任何数字、locator 或 wikilink target 变化都必须有来源依据。
- 每个提交执行：
  - `python3 -m unittest discover -s .claude/skills/wiki-lint -p 'test_*.py'`
  - `python3 .claude/skills/wiki-lint/lint.py --summary-only`
  - `git diff --check`
- 最终验收要求：
  - `language_warnings=0`。
  - `paper_structure=0`、`paper_quality=0`，frontmatter、hybrid link、alias、orphan 和命名关键违规均为 0。
  - 429 篇论文均有中文 H1、英文原题行和中文固定章节；无旧英文结构标题。
  - 所有 PDF/Markdown source link 可解析；有意保留的 prospective wikilink 不要求清零。
  - `cd quartz && npx quartz build -d ../wiki` 成功，生成目录中不存在 `reports/` 页面。

## 假设与默认

- “全文复核”指完整核验论文主文和支撑 wiki 论断的相关附录，不机械阅读无关参考文献列表。
- 英文专名是否保留按 AGENTS.md 现有规则判断；普通可翻译概念首次写成“中文解释（English）”，后续优先中文。
- 本轮不扩展 wiki 图谱、不创建新 entity/concept、不更改文件标识；范围只包含语言治理以及回源过程中发现的事实修正。
