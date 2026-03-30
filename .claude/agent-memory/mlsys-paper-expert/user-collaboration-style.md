---
name: user-collaboration-style
description: Writing preferences for MLSys paper reports - Chinese body, 9 sections, critical analysis, ~800-1500 words
type: user
---

## Report Writing Preferences

**Language**: Chinese body text, English for technical terms (native code, method names, model names).

**Report Structure** (9 sections):
1. 论文基本信息
2. 研究背景与动机
3. 研究问题与核心挑战
4. 主要贡献
5. 核心方法与设计
6. 实验设置
7. 实验结果
8. 潜在问题与局限性
9. 个人评注

**Length**: 800-1500 words per report

**Output Path**: `/Users/qliu/workspace/awesome-system-papers/reports/mlsys-2025/{basename_without_pdf}.md`

**Critical Analysis Standards**:
- Check for logical contradictions in claims
- Verify baseline comprehensiveness (are all relevant baselines included?)
- Assess fairness of comparisons (same settings, same metrics?)
- Identify where paper overstates results
- Note missing ablation studies or generalization experiments
- Be specific about quantitative claims (don't just say "significant" — cite numbers)

**Tone**: Authoritative but acknowledge uncertainty where appropriate. Provide actionable insights, not just summaries.

**What NOT to save**: Code patterns, conventions, file paths — these can be derived from the project state.
