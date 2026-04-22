---
name: paper-report
description: Use this skill when the user wants to read a research paper PDF and generate a structured introduction/analysis report in Markdown. Triggers on requests like "阅读论文并生成报告", "读这篇论文", "/paper-report <pdf>", or similar.
---

# Paper Report Skill

Generate a structured Chinese Markdown report for a research paper PDF.

## Usage

```
/paper-report <pdf_path> [output_path]
```

- `pdf_path`: Path to the PDF (relative to project root or absolute)
- `output_path`: (Optional) Output Markdown file path. If omitted, auto-inferred from pdf_path.

## Output Path Inference

If no output_path is provided, infer from the PDF path:

| PDF location | Report location |
|---|---|
| `papers/sosp-2025/xxx.pdf` | `reports/sosp-2025/xxx.md` |
| `papers/osdi-2025/xxx.pdf` | `reports/osdi-2025/xxx.md` |
| `papers/ai-infra/xxx.pdf` | `reports/ai-infra/xxx.md` |
| `papers/{any}/xxx.pdf` | `reports/{any}/xxx.md` |
| any other path | same directory, `xxx.md` |

## Step 0 — Ensure Markdown Exists

**Before reading the paper, ensure the mineru-parsed markdown exists.**

Markdown path is inferred from the PDF path:

| PDF location | Markdown location |
|---|---|
| `papers/{dir}/{stem}.pdf` | `markdowns/{dir}/{stem}/{stem}.md` |

If the markdown file does not exist, run:

```bash
uv run scripts/run_mineru.py papers/{dir} markdowns/{dir} -j 2 -m txt
```

The script scans the whole `papers/{dir}` and skips any PDF whose target markdown already exists, so running it for a single new PDF is cheap and idempotent. `-m txt` is correct for LaTeX-typeset academic PDFs (see CLAUDE.md "PDF → Markdown 解析" for rationale).

If the directory has many unprocessed PDFs, warn the user that mineru will take a while (~60–90s per paper on Mac, sequential) before proceeding.

## Step 1 — Read the Markdown

Primary source: `markdowns/{dir}/{stem}/{stem}.md`

Use the `Read` tool. For long papers (>20 pages), read sections selectively instead of dumping the whole file:

- Use `Grep -n "^#{1,3} " ...md` first to get the section heading map
- Read **Abstract + Introduction** (usually lines 1–150) to understand the problem and contribution
- Jump to **Design / Method** sections (e.g., `## 3`, `## 4`) for the approach
- Jump to **Evaluation** section (usually `## 6` or `## 7`) for numbers and comparisons
- Read **Conclusion** at the end

Figures are referenced inline as `![](images/{hash}.jpg)`. Read a figure via `Read markdowns/{dir}/{stem}/images/{hash}.jpg` when you need to understand its content (e.g., architecture diagrams, result plots).

## Step 2 — Quality Fallback to PDF

If you encounter any of these issues while reading the markdown, fall back to reading the original PDF for that specific section:

- **Garbled formulas** — empty LaTeX arrays (`\begin{array}...{{}}...\end{array}`), misplaced subscripts/superscripts, dense math turning into symbol soup
- **Broken tables** — `<table>` cells containing LaTeX command noise (e.g., `$\checkmark^{\pmb{\mathscr{s}}}$` in evaluation comparison tables)
- **Displaced characters** — Greek letters or punctuation out of order (e.g., `"A (v k )-SBIBD...λ,,λ"` when the original reads `"A (v, k, λ)-SBIBD"`)
- **Suspected typos in critical numbers** — e.g., `"1 61×"` where context suggests `"1.61×"`
- **Any claim you're about to quote verbatim** if the surrounding text looks suspicious

Fall back command:

```
Read papers/{dir}/{stem}.pdf pages=<N-M>
```

The PDF is returned as rendered page images for the vision model. Use this **sparingly** — each page costs ~1500–3000 tokens. Target specific pages (e.g., `pages=6-7` for the evaluation table on page 6–7), not the whole paper.

## Step 3 — Write the Report

Write the report in **Chinese**. Follow this exact structure:

```markdown
# {论文完整标题}

**作者**：{作者列表，含单位}
**会议**：{会议名称和年份}
**链接**：{DOI URL、会议页面链接或其他原始链接}
**源文件**：[[{filename.pdf}]]

---

## 一、背景

{研究背景：领域现状、技术趋势、为什么这个问题重要}

---

## 二、要解决的问题

{明确指出现有方案的不足、pain points，可以分多个子问题}

---

## 三、洞察与设计

**关键洞察**：{提炼论文作者的核心观察/发现/假设——这是使整篇论文的方法成立的前提。如果这个观察不成立，论文的方法论就不成立。注意：这里要写的是作者的观察，不是读者的评价。}

{基于上述洞察，介绍系统/算法的核心思路和设计方案。包含关键抽象、架构图描述、设计决策}

---

## 四、实现细节

{具体的实现方式：关键数据结构、算法伪代码要点、与已有框架的集成方式、代码规模等}

---

## 五、实验结果

{实验平台、基线、主要指标、关键数字。尽量用表格整理}

---

## 六、批判性分析

{用批判性思维审视论文，重点检查：
- 逻辑谬误（如用微基准结果代表端到端收益）
- 前后矛盾（如问题定义与实验结论不一致）
- 实验设计不足（基线不公平、规模太小、只报 best case）
- 系统假设过于乐观
- 未解决的问题被轻描淡写}

---

## 七、AI Infra / MLSys 视角

{**仅当论文与 AI 系统、ML 基础设施、分布式训练/推理、模型优化等方向有关联时才写本节，否则省略。**

从 AI Infra / MLSys 研究者的角度评估：
- 这篇论文对 AI 系统研究有什么启发或借鉴价值？
- 其中哪些技术、设计思路或 insight 可以迁移到 AI Infra 场景？
- 有哪些值得跟进的 future work 方向？具体到可操作的研究问题
- 如果要基于这篇论文做延伸工作，最有价值的切入点是什么？}

---

## 八、总结

{一段话概括核心贡献、适用场景、主要局限}
```

## Important Notes

- All section headers and body text must be in **Chinese**
- Keep technical terms in their original English form (e.g., FlashAttention, RLHF, KV cache)
- In section 六, be genuinely critical — don't just repeat limitations the authors already acknowledged; look for what they glossed over
- Section 七 is **optional** — only include it if the paper is relevant to AI systems, ML infrastructure, distributed training/inference, model optimization, or closely related areas. If the paper is about unrelated topics (e.g., pure networking, storage systems without AI angle, databases), omit section 七 entirely and renumber 八 to 七
- For the 源文件 link, use `[[filename.pdf]]` (Obsidian wikilink, filename only, no path)
- In section 三, the **关键洞察** must be the paper author's core observation/discovery/assumption — the foundational premise that makes their approach work. It is NOT the reader's critique or opinion. Examples:
  - ✅ "不同阶段的 cache 驻留特性差异足够大，值得用不同的硬件资源配置分别处理" (author's observation)
  - ❌ "speedup 范围 1.03×–5.46× 跨度过大" (reader's critique → belongs in section 六)
  - ❌ "提出了一种新的线程模型" (method summary, not an insight)
- After writing the report, confirm the output path to the user
