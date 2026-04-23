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
- `--skip-reports`: 跳过 Step 1,直接进入 Step 2。适用场景:已完成所有 `paper-report`,只想重新生成 README(例如调整分类口径、更新趋势分析、补充新的 open problems)时使用

## Idempotency

若 `reports/{dir}/README.md` 已存在,默认**覆盖**,但保留首次生成日期:

- 解析旧文件顶部 `> 共 N 篇论文 | 生成日期: YYYY-MM-DD` 中的「生成日期」
- 新版顶部写为 `> 共 N 篇论文 | 生成日期: <旧日期> | 最后更新: <今天>`
- 若解析不到旧日期(首次生成),写 `> 共 N 篇论文 | 生成日期: <今天>`

## Step 1 — Ensure Reports Exist

Unless `--skip-reports` is given:

1. List all `.pdf` files in `papers/{dir}/`
2. List all `.md` files in `reports/{dir}/` (excluding `README.md`)
3. Identify PDFs without a corresponding report (same basename, `.pdf` → `.md`)

### Step 1a — Pre-generate mineru markdowns(必须先于 Step 1b 完成)

**严格串行**:Step 1a 必须先于 Step 1b 完成,**不可并行**。原因:mineru-api 是单例,若 Step 1b 的并行 `paper-report` 调用各自尝试启动 mineru-api 会冲突;Step 1a 一次性处理完,后续 `paper-report` 仅做 Read,彻底消除竞态。

```bash
uv run scripts/run_mineru.py papers/{dir} markdowns/{dir} -j 2 -m txt
```

The script is idempotent — PDFs whose markdown already exists are skipped. 大目录耗时 ~60–90s/PDF(Mac 上 mineru-api 串行)。

### Step 1b — Generate missing reports

**For conference directories** (name matches `{conf}-{year}` pattern like `osdi-2025`, `sosp-2025`, `atc-2024`, `nsdi-2025`, `mlsys-2025`, `fast-2025`):
```bash
bash ./scripts/batch_paper_reports.sh {dir}
```
The batch script itself also re-runs the mineru step (belt-and-suspenders; idempotent), then parallel-invokes `/paper-report` for each missing report. Wait for completion before proceeding.

**For topic directories** (`ai-infra`, `foundation`, `finance`, `agent`, etc.):
For each missing report, invoke the `paper-report` skill (or its workflow):
- The markdown is already available at `markdowns/{dir}/{basename}/{basename}.md` from Step 1a
- Read that markdown, fall back to the PDF only on suspected parsing errors
- Write the report to `reports/{dir}/{basename}.md`
- Follow the exact report structure defined in the `paper-report` skill

## Step 2 — Read All Reports

Read all `.md` files (excluding `README.md`) in `reports/{dir}/`.

**默认全量加载所有 report**。每篇 report 约 5–10k tokens,Opus 1M context 可轻松容纳 100+ 篇 report,不要过早分批。只在以下情况才分批:

- 报告数 > 200(目前不会出现)
- 单篇报告异常超过 30k tokens(通常是某个报告把整篇论文 verbatim 复制了)

**兼容新旧报告格式**(读取时必须兼容):

- 新报告章节序号用阿拉伯数字,如 `## 3. 洞察与设计`、`## 8. 总结`
- 旧报告章节序号用中文,如 `## 三、洞察与设计`、`## 八、总结`
- `**关键洞察**` 字段在两种格式下标记相同,直接 Grep 该字符串即可定位
- 「总结」是最后一节,无论序号是 7/8 还是 七/八,按章节顺序取最后一节即可

From each report, extract:
- **论文标题** (from `# Title` header)
- **作者** (from `**作者**` line)
- **会议/来源** (from `**会议**` line, if present)
- **要解决的问题** (from 「要解决的问题」节 — distill to 1-2 sentences)
- **核心贡献** (from 「总结」节 — 论文的核心贡献)
- **关键发现/观点** — **最重要**:论文作者的核心观察/发现/假设——使整篇论文的方法成立的前提。如果这个观察不成立,论文的方法论就不成立。优先从报告的「洞察与设计」节开头的 `**关键洞察**` 字段直接提取;若报告为旧格式(无此字段),则综合理解核心设计、实验结果、批判性分析三节来提炼。注意:这是作者的观察,不是读者的评价。
- **Topic/area** (inferred from「背景」+「洞察与设计」两节)

## Step 3 — Generate README

Write `reports/{dir}/README.md`. All text in **Chinese**, technical terms in **English**.

### Categorization Guidelines

- 类别数量目标 **5–10 个**,每类 **3–10 篇**
- 某类别 < 3 篇时,合并到相邻类别或归入「其他」
- 某类别 > 10 篇时,拆为更细的子主题
- **每篇论文必须出现且只出现一次**。跨类别时归入最核心的那个
- **分类是动态的**:根据本目录实际论文内容推断,不要套用固定 taxonomy

### For Conference Directories

```markdown
# {Conference Full Name} {Year} 论文概览

> 共 N 篇论文 | 生成日期: YYYY-MM-DD [| 最后更新: YYYY-MM-DD]

---

## 论文分类索引

### {Category 1}（N 篇）

#### [[filename|Paper Title]]
- **作者**：First Author et al.
- **要解决的问题**：一两句话说明
- **核心贡献**：一两句话说明
- **关键发现/观点**：这篇论文成立的核心前提——如果这个发现/观点不成立,整篇论文就不成立

#### [[filename2|Paper Title 2]]
...

### {Category 2}（N 篇）
...

---

## 研究趋势分析

{3–5 段深入分析。**每段必须引用 2–3 篇具体论文作为证据**,引用格式 `[[filename|short title]]`,空泛断言无效。

关注的问题:
- 这届会议的主导研究主题是什么?
- 出现了哪些新的范式或方法论变迁?
- 有哪些跨领域交叉的趋势?
- 社区正在收敛到哪些共性问题?
- 与往年相比有什么显著变化?

示例段落格式:
> KV cache 管理成为 LLM 推理系统的核心议题。[[osdi25-zhu-kan|NanoFlow]] 提出 ... ,[[sosp25-foo|FlashCache]] 进一步 ... ,[[mlsys25-bar|BlockTree]] 则 ...}

---

## 值得关注的方向

{面向资源有限的小团队（3–5 人,无大规模 GPU 集群),分析可行的研究方向。
不要推荐需要大规模工程投入、海量数据或大量算力的方向。

每个方向应包含:
- **方向名称和描述**
- **为什么小团队能做**:所需资源、技能、时间是否可控
- **哪些论文指向了这个空白**:引用具体论文(用 wikilink)
- **具体的 open problems**:可以直接作为研究课题的问题}
```

### For Topic Directories

```markdown
# {Topic Name} 论文索引

> 共 N 篇论文 | 生成日期: YYYY-MM-DD [| 最后更新: YYYY-MM-DD]

---

## 论文列表

#### [[filename|Paper Title]]
- **作者**：First Author et al.
- **会议/来源**：Venue Year
- **要解决的问题**：一两句话
- **核心贡献**：一两句话
- **关键发现/观点**：这篇论文成立的核心前提

#### [[filename2|Paper Title 2]]
...

---

## 主题综述

{这个 topic 的整体脉络、关键技术演进、论文之间的关系和依赖。
**每段必须引用 2–3 篇具体论文作为证据**,格式 `[[filename|short title]]`。}

---

## 值得关注的方向

{基于这些论文,小实验室可以跟进的研究方向和 open problems。
同样聚焦于不需要大规模资源的方向,结构与 conference 模板相同。}
```

## Step 4 — Update Global Index

写完 `reports/{dir}/README.md` 后,**回写全局索引** `reports/README.md`:

- 若全局索引已含本 dir 的条目:更新该行的「论文数量」「最后更新日期」
- 若不含:在合适位置追加(会议按年份倒序排列,topic 按字母序排列),格式:
  ```markdown
  - [[{dir}/README|{Conf Year / Topic Name}]] — N 篇 | 更新于 YYYY-MM-DD
  ```
- 若 `reports/README.md` 不存在,新建一个最简版索引(标题 + 两个子节:会议论文、Topic 论文)

## Important Notes

- **Topic categories are dynamic** — do NOT use a fixed taxonomy. Infer categories from the actual paper content in this specific directory.
- **每篇论文必须出现且只出现一次**。如果一篇论文跨多个类别,放在最核心的那个类别里。
- **关键发现/观点** 是最重要的字段。不要写空泛的描述。它应该是一个具体的、可以被证伪的 claim。例如:"Prefill 和 Decode 阶段的计算特性差异足够大,值得用不同的硬件配置分别处理",而不是"提出了一种新的调度方法"。
- 「研究趋势分析」和「主题综述」每段必须有具体论文引用作证据,空泛断言无效
- 「值得关注的方向」在 conference 和 topic 模板里用同一个标题,不要改成其他叫法
- 生成完成后,告诉用户输出路径(本 dir README + 全局索引)和论文总数。
