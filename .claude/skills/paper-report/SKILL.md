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

## PDF Extraction

Use pdfplumber to extract all text, reading in batches of ~4 pages at a time:

```python
import pdfplumber

with pdfplumber.open("path/to/paper.pdf") as pdf:
    print(f"Total pages: {len(pdf.pages)}")
    for i, page in enumerate(pdf.pages):
        print(f"--- Page {i+1} ---")
        print(page.extract_text())
```

Run with: `uv run python -c "..."`

Read all pages. For papers longer than 20 pages, read in 2-3 batches.

## Report Structure

Write the report in **Chinese**. Follow this exact structure:

```markdown
# {论文完整标题}

**作者**：{作者列表，含单位}
**会议**：{会议名称和年份}
**链接**：{DOI URL、会议页面链接或其他原始链接}
**源文件**：[{filename.pdf}]({pdf的相对路径，相对于report文件所在目录})

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
- For the 源文件 link, compute the relative path from the output report file to the PDF file
- In section 三, the **关键洞察** must be the paper author's core observation/discovery/assumption — the foundational premise that makes their approach work. It is NOT the reader's critique or opinion. Examples:
  - ✅ "不同阶段的 cache 驻留特性差异足够大，值得用不同的硬件资源配置分别处理" (author's observation)
  - ❌ "speedup 范围 1.03×–5.46× 跨度过大" (reader's critique → belongs in section 六)
  - ❌ "提出了一种新的线程模型" (method summary, not an insight)
- After writing the report, confirm the output path to the user
