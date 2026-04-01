---
name: papers-digest
description: "Generate a README digest for a papers directory (conference or topic). Categorizes all papers, analyzes trends, and identifies opportunities for small labs. Triggers on: /papers-digest <dir>, '整理会议论文', '生成论文索引'."
---

# Papers Digest Skill

Read all paper reports in a directory and generate a comprehensive README.md with categorization, trend analysis, and research opportunities.

## Usage

```
/papers-digest <dir> [--skip-reports]
```

- `dir`: subdirectory name under `papers/`, e.g. `osdi-2025`, `sosp-2025`, `ai-infra`, `finance`
- `--skip-reports`: skip report generation step, only build README from existing reports

## Step 1 — Ensure Reports Exist

Unless `--skip-reports` is given:

1. List all `.pdf` files in `papers/{dir}/`
2. List all `.md` files in `reports/{dir}/` (excluding `README.md`)
3. Identify PDFs without a corresponding report (same basename, `.pdf` → `.md`)

**For conference directories** (name matches `{conf}-{year}` pattern like `osdi-2025`, `sosp-2025`, `atc-2024`, `nsdi-2025`, `mlsys-2025`, `fast-2025`):
```bash
bash ./scripts/batch_paper_reports.sh {dir}
```
Wait for completion before proceeding.

**For topic directories** (`ai-infra`, `foundation`, `finance`, `agent`, etc.):
For each missing report, generate it directly using the same approach as the `paper-report` skill:
- Extract PDF text with pdfplumber (`uv run python -c "..."`)
- Write the report to `reports/{dir}/{basename}.md`
- Follow the exact report structure defined in the `paper-report` skill

## Step 2 — Read All Reports

Read all `.md` files (excluding `README.md`) in `reports/{dir}/`.

For large directories (>20 reports), read in batches of ~10 files to avoid context overflow.

From each report, extract:
- **论文标题** (from `# Title` header)
- **作者** (from `**作者**` line)
- **会议/来源** (from `**会议**` line, if present)
- **要解决的问题** (from 二、要解决的问题 — distill to 1-2 sentences)
- **核心贡献** (from 八、总结 or 七、总结 — the main contribution)
- **关键发现/观点** — **最重要**：论文作者的核心观察/发现/假设——使整篇论文的方法成立的前提。如果这个观察不成立，论文的方法论就不成立。优先从报告的"洞察与设计(三)"开头的 **关键洞察** 字段直接提取；若报告为旧格式（无此字段），则综合理解核心设计(三)、实验结果(五)和批判性分析(六)来提炼。注意：这是作者的观察，不是读者的评价。
- **Topic/area** (inferred from 一、背景 + 三、核心设计)

## Step 3 — Generate README

Write `reports/{dir}/README.md`. All text in **Chinese**, technical terms in **English**.

### For Conference Directories

```markdown
# {Conference Full Name} {Year} 论文概览

> 共 N 篇论文 | 生成日期: YYYY-MM-DD

---

## 论文分类索引

### {Category 1}（N 篇）

#### [Paper Title](./filename.md)
- **作者**：First Author et al.
- **要解决的问题**：一两句话说明
- **核心贡献**：一两句话说明
- **关键发现/观点**：这篇论文成立的核心前提——如果这个发现/观点不成立，整篇论文就不成立

#### [Paper Title 2](./filename2.md)
...

### {Category 2}（N 篇）
...

---

## 研究趋势分析

{3–5 段深入分析：
- 这届会议的主导研究主题是什么？
- 出现了哪些新的范式或方法论变迁？
- 有哪些跨领域交叉的趋势？
- 社区正在收敛到哪些共性问题？
- 与往年相比有什么显著变化？}

---

## 小实验室的机会窗口

{面向资源有限的小团队（3–5 人，无大规模 GPU 集群），分析可行的研究方向。
不要推荐需要大规模工程投入、海量数据或大量算力的方向。

每个方向应包含：
- **方向名称和描述**
- **为什么小团队能做**：所需资源、技能、时间是否可控
- **哪些论文指向了这个空白**：引用具体论文标题
- **具体的 open problems**：可以直接作为研究课题的问题}
```

### For Topic Directories

```markdown
# {Topic Name} 论文索引

> 共 N 篇论文 | 最后更新: YYYY-MM-DD

---

## 论文列表

#### [Paper Title](./filename.md)
- **作者**：First Author et al.
- **会议/来源**：Venue Year
- **要解决的问题**：一两句话
- **核心贡献**：一两句话
- **关键发现/观点**：这篇论文成立的核心前提

#### [Paper Title 2](./filename2.md)
...

---

## 主题综述

{这个 topic 的整体脉络、关键技术演进、论文之间的关系和依赖}

---

## 值得关注的方向

{基于这些论文，小实验室可以跟进的研究方向和 open problems。
同样聚焦于不需要大规模资源的方向。}
```

## Important Notes

- **Topic categories are dynamic** — do NOT use a fixed taxonomy. Infer categories from the actual paper content in this specific directory.
- **每篇论文必须出现且只出现一次**。如果一篇论文跨多个类别，放在最核心的那个类别里。
- **关键发现/观点** 是最重要的字段。不要写空泛的描述。它应该是一个具体的、可以被证伪的 claim。例如："Prefill 和 Decode 阶段的计算特性差异足够大，值得用不同的硬件配置分别处理"，而不是"提出了一种新的调度方法"。
- 生成完成后，告诉用户输出路径和论文总数。
