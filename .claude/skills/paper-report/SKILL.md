---
name: paper-report
description: Use this skill when the user wants to read a research paper PDF and generate a structured introduction/analysis report in Markdown. Triggers on requests like "阅读论文并生成报告", "读这篇论文", "/paper-report <pdf>", or similar.
---

# Paper Report Skill

Generate a structured Chinese Markdown report for a research paper PDF.

**执行模式:无人值守 (unattended)。** 本 skill 通常在批量处理或后台 loop 中运行,不要中途询问用户做选择。遇到问题(markdown 不存在、文件过大、解析有瑕疵、链接缺失等)直接 fallback 到合适的默认行为并继续推进,在最终输出里简短说明所做的取舍即可。

## Usage

```
/paper-report <pdf_path> [output_path]
```

- `pdf_path`: PDF 路径,**必须位于 `papers/{dir}/` 下**(相对仓库根目录或绝对路径都可)。`inbox/` 或其他散落位置的 PDF 一律拒绝并提示用户先把论文分类到合适的 `papers/{topic}/` 子目录。
- `output_path`: (Optional) Output Markdown file path. If omitted, auto-inferred from pdf_path.

## Pre-flight Checks

执行任何步骤前,先做两个校验:

1. **路径校验**:若 `pdf_path` 不在 `papers/<subdir>/` 下,立即终止并输出:「论文应先分类到 `papers/<topic>/`(如 `papers/ai-infra/`、`papers/osdi-2025/`),inbox 或散落路径下的 PDF 不接受」,然后退出。
2. **报告幂等**:若目标 `reports/{dir}/{stem}.md` 已存在,默认 **skip** 并输出「报告已存在,跳过:<path>」,然后退出。如需强制重写,用户应手动删除旧报告再重跑。

## Output Path Inference

If no output_path is provided, infer from the PDF path:

| PDF location | Report location |
|---|---|
| `papers/sosp-2025/xxx.pdf` | `reports/sosp-2025/xxx.md` |
| `papers/osdi-2025/xxx.pdf` | `reports/osdi-2025/xxx.md` |
| `papers/ai-infra/xxx.pdf` | `reports/ai-infra/xxx.md` |
| `papers/{any}/xxx.pdf` | `reports/{any}/xxx.md` |

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

无人值守:即使目录下有大量未处理 PDF,也直接执行 mineru,不要询问。可在执行前简短提示「目录有 N 篇未解析 PDF,mineru 预计耗时 ~N×75s」,然后立即继续。

## Step 1 — Read the Markdown (Full Read by Default)

Primary source: `markdowns/{dir}/{stem}/{stem}.md`

**默认全量阅读 markdown,图片按预算阅读。** 把 PDF 转成 markdown 的核心目的就是用低 token 成本换取 Opus 1M context 的完整理解 —— markdown 的 token 开销比 PDF 渲染图小一个数量级,即使是 30+ 页的长论文,完整 markdown 通常也只有 30k–80k tokens,远低于上下文上限。完整阅读能避免因跳读漏掉关键的 cross-section 引用、设计权衡、实验细节,产出的报告质量显著优于片段式阅读。

具体步骤:

1. **`Read` 整个 markdown 文件**,不要预先 Grep 章节后选择性读。Read 工具默认读 2000 行,对 mineru 输出几乎覆盖全文;若文件超过 2000 行,用 `offset` 接续读完剩余部分,确保零遗漏。

2. **按预算读取图片**。Markdown 中以 `![](images/{hash}.jpg)` 引用的每张图都通过 `Read markdowns/{dir}/{stem}/images/{hash}.jpg` 加载。注意单张 jpg 经 vision 模型约 1.5k–4k tokens,30 张图 ≈ 100k tokens,**不可全开**。

   预算策略:
   - **图片总数 ≤ 20**:全部读
   - **图片总数 > 20**:按以下优先级取前 ~20 张
     1. 架构图 / 系统流程图 / 总览图(通常出现在 Introduction 和 Design 节首,最关键)
     2. 主结果表 / 端到端性能图
     3. 关键 ablation / 设计权衡图
     4. (跳过)重复柱状图、microbenchmark 子图、纯代码截图、纯文本表格(已在 markdown 中重建)
   - 并行发起多个 Read 调用以提升效率

3. **超大体量退化**(无人值守,直接执行,无需询问):
   - Markdown 文件 > 5000 行:读正文部分,跳过 References / Appendix
   - 在最终报告里简短注明跳过了哪些部分

## Step 2 — Quality Fallback to PDF

If you encounter any of these issues while reading the markdown, fall back to reading the original PDF for that specific section:

- **Garbled formulas** — empty LaTeX arrays (`\begin{array}...{{}}...\end{array}`), misplaced subscripts/superscripts, dense math turning into symbol soup
- **Broken tables** — `<table>` cells containing LaTeX command noise (e.g., `$\checkmark^{\pmb{\mathscr{s}}}$` in evaluation comparison tables)
- **Displaced characters** — Greek letters or punctuation out of order (e.g., `"A (v k )-SBIBD...λ,,λ"` when the original reads `"A (v, k, λ)-SBIBD"`)
- **Suspected typos in critical numbers** — e.g., `"1 61×"` where context suggests `"1.61×"`
- **Any claim you're about to quote verbatim** if the surrounding text looks suspicious

**定位 PDF 页码的步骤**(避免盲目读全 PDF):

1. 在 markdown 里 `Grep` 出可疑片段附近的章节标题(`^## 4 Design`)或独特短语(论文里某个特殊术语、表号 "Table 3"、公式编号 "Eq. (5)")
2. 估算章节对应页码范围(典型 14 页 USENIX 论文):Abstract+Intro 1–2 页,Background 2–3 页,Design 4–8 页,Implementation 8–10 页,Evaluation 10–14 页
3. 只 Read 1–2 页的窄窗口,例如 `Read papers/{dir}/{stem}.pdf pages=6-7`

PDF 每页 ~1500–3000 token,**不要** `Read papers/.../foo.pdf` 不带 pages 参数 —— 长论文会撑爆 context。

## Step 3 — Write the Report

Write the report in **Chinese**。章节序号统一用阿拉伯数字 `1.` 至 `8.`,**不**使用「一、二、三」中文序号。Section 7 省略时,**不要 renumber**,Section 8 仍叫 8(序号留 7 的空缺优于 renumber 出错)。

报告结构:

````markdown
---
title: {论文完整标题}
authors: [Author1, Author2, ...]
year: {YYYY}
venue: {OSDI / ATC / NSDI / SOSP / MLSys / FAST / arXiv / ...}
tags: [tag1, tag2, tag3]
---

# {论文完整标题}

**作者**：{清洗后的作者列表}
**会议**：{标准会议名 + 年份}
**链接**：{规则见下}
**源文件**：[[{filename.pdf}]]

---

## 1. 背景

{研究背景:领域现状、技术趋势、为什么这个问题重要}

---

## 2. 要解决的问题

{明确指出现有方案的不足、pain points,可以分多个子问题}

---

## 3. 洞察与设计

**关键洞察**：{提炼论文作者的核心观察/发现/假设——这是使整篇论文的方法成立的前提。如果这个观察不成立,论文的方法论就不成立。注意:这里要写的是作者的观察,不是读者的评价}

{基于上述洞察,介绍系统/算法的核心思路和设计方案。包含关键抽象、架构图描述、设计决策}

---

## 4. 实现细节

{具体的实现方式:关键数据结构、算法伪代码要点、与已有框架的集成方式、代码规模等}

---

## 5. 实验结果

{实验平台、基线、主要指标、关键数字。尽量用表格整理}

---

## 6. 批判性分析

{用批判性思维审视论文,重点检查:
- 逻辑谬误(如用微基准结果代表端到端收益)
- 前后矛盾(如问题定义与实验结论不一致)
- 实验设计不足(基线不公平、规模太小、只报 best case)
- 系统假设过于乐观
- 未解决的问题被轻描淡写}

---

## 7. AI Infra / MLSys 视角

{**仅当论文与 AI 系统、ML 基础设施、分布式训练/推理、模型优化等方向有关联时才写本节,否则整节省略,Section 8 序号不变(不要 renumber)。**

从 AI Infra / MLSys 研究者的角度评估:
- 这篇论文对 AI 系统研究有什么启发或借鉴价值?
- 其中哪些技术、设计思路或 insight 可以迁移到 AI Infra 场景?
- 有哪些值得跟进的 future work 方向?具体到可操作的研究问题
- 如果要基于这篇论文做延伸工作,最有价值的切入点是什么?}

---

## 8. 总结

{一段话概括核心贡献、适用场景、主要局限}
````

### Frontmatter 字段约定

- `title`: 完整论文标题,与 `# {title}` 一致
- `authors`: YAML 列表,只放姓名(去脚标、邮箱),如 `[Alice Wang, Bob Chen, Carol Liu]`;> 10 人时取前 5 人 + `et al.`
- `year`: 4 位年份数字
- `venue`: 简写,如 `OSDI`、`SOSP`、`MLSys`、`NSDI`、`ATC`、`FAST`、`arXiv`(arXiv 论文用此)
- `tags`: 3–6 个英文小写 tag,多词用 `-` 连接,如 `[llm-inference, kv-cache, scheduling]`。从论文核心技术、所在子领域中提炼,便于 Obsidian Bases 检索

### 标题与作者清洗

mineru 输出的论文头部经常带噪声(脚标、邮箱、affiliation),需清洗:

- **标题**:去掉行首/行尾的脚标符号(`∗`、`†`、`‡`、`§`)、HTML 上下标 tag、版权字样
- **作者**:格式 `First Last, First Last, ...`,去掉:
  - 上标数字/符号(affiliation 角标、邮箱角标)
  - 邮箱地址 (`alice@a.edu`)
  - 内联的 affiliation 字符串
- 作者超过 10 人:取前 5 人 + `et al.`
- 单位若需要保留,在 `**作者**` 行后再加一行 `**单位**：Inst1, Inst2, Inst3`;frontmatter 中**不要**塞 affiliation

### 链接字段 fallback

PDF 正文很少自带 DOI / URL,按下表生成,无需打开浏览器验证:

| 来源 | 链接格式 | 示例 |
|---|---|---|
| USENIX (OSDI/ATC/NSDI/FAST) | `https://www.usenix.org/conference/{conf}{yy}/presentation/{firstauthor-lastname}` | `https://www.usenix.org/conference/osdi25/presentation/zhang` |
| SOSP (文件名 `{p_doi}.{a_doi}.pdf`) | `https://doi.org/10.1145/{p_doi}.{a_doi}` | `https://doi.org/10.1145/3731569.3764795` |
| MLSys | `https://proceedings.mlsys.org/paper_files/paper/{year}` | 链接到当年 proceedings 总目录 |
| arXiv (文件名形如 `2412.09880v1.pdf`) | `https://arxiv.org/abs/{id}` | `https://arxiv.org/abs/2412.09880` |
| 其他 / 推断不出 | `—` | (留破折号) |

## Important Notes

- All section headers and body text must be in **Chinese**
- 章节序号统一用阿拉伯数字 `1.` 至 `8.`,**不**使用「一、二、三」中文序号
- Keep technical terms in their original English form (e.g., FlashAttention, RLHF, KV cache)
- In section 6, be genuinely critical — don't just repeat limitations the authors already acknowledged; look for what they glossed over
- Section 7 is **optional** — only include it if the paper is relevant to AI systems, ML infrastructure, distributed training/inference, model optimization, or closely related areas. If the paper is about unrelated topics (e.g., pure networking, storage systems without AI angle, databases), 整节省略,**Section 8 序号不变,不要 renumber**
- For the 源文件 link, use `[[filename.pdf]]` (Obsidian wikilink, filename only, no path)
- In section 3, the **关键洞察** must be the paper author's core observation/discovery/assumption — the foundational premise that makes their approach work. It is NOT the reader's critique or opinion. Examples:
  - ✅ "不同阶段的 cache 驻留特性差异足够大,值得用不同的硬件资源配置分别处理" (author's observation)
  - ❌ "speedup 范围 1.03×–5.46× 跨度过大" (reader's critique → belongs in section 6)
  - ❌ "提出了一种新的线程模型" (method summary, not an insight)
- After writing the report, briefly state the output path. Do NOT ask the user to confirm or choose anything — this skill runs unattended
- 通用 fallback 原则:遇到任何不确定情况(链接缺失、作者单位推断不出、章节序号冲突等)直接选合理默认值并继续,不要打断流程向用户提问
