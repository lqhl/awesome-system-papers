---
type: paper
name: KNighter
full_title: "KNighter: Transforming Static Analysis with LLM-Synthesized Checkers"
authors: [Chenyuan Yang, Zijie Zhao, Zichen Xie, Haoyu Li, Lingming Zhang]
venue: SOSP
year: 2025
tags: [static-analysis, llm, linux-kernel, bug-detection, checker-synthesis]
source_pdf: "[[3731569.3764827.pdf]]"
source_md: "[[3731569.3764827]]"
---

# KNighter: Transforming Static Analysis with LLM-Synthesized Checkers (SOSP 2025)

> **一句话总结**:不让 LLM 直接扫代码,而是让 LLM 从历史 patch 合成 Clang Static Analyzer(CSA)checker——多阶段合成 + 自动 refinement 管线,检查器用 historical patch 做 validation 避免幻觉。在 Linux kernel 上从 61 个 patch 里成功合成 61% 的高质量检查器(经 triage agent 后 FP 率 ~35%),已经挖出 92 个长潜伏漏洞(平均 4.3 年),77 确认、57 修复、30 拿到 CVE 编号。

## 问题

大规模系统(Linux kernel 3000 万+ LoC)的静态分析面临二元困境:
- **传统静态分析**:规则/模型精确但模式有限,需要领域专家编写,难覆盖新 bug 类型
- **直接用 LLM 扫**:LLM 上下文窗口有限、扫整库成本高(devm_kzalloc 单个函数在 5.4K 文件中出现 7K+ 次),还会幻觉

能否二者结合——让 LLM 去生成 checker,而不是去当 checker?

## 核心方法

**KNighter = 从 patch commit 自动合成 CSA checker 的 agent 管线**,输出的 checker 跑的是 CPU(不再调 LLM),正好符合经济性。

**两阶段管线**:

1. **Checker synthesis**:
   - 分析 patch 识别 bug pattern
   - LLM 起草检测 plan
   - 基于 plan 用 [[Clang-Static-Analyzer]] API 生成 checker 代码
   - 编译错误用 syntax-repair agent 修复
   - **Validity 校验**:checker 必须能在 patch 前代码上报警、patch 后代码不报警(用 historical patch 做 ground truth,根治 LLM 幻觉)

2. **Checker refinement**:
   - 把 valid checker 放到整库扫,产生 bug report
   - **Triage agent** 评估每个 report 是否 false positive
   - 根据 triage 结果迭代精调 checker,降 FP 率
   - 当报告数和 FP 率都可控时产出 plausible checker

**举例**:针对 `devm_kzalloc` 返回值未 NULL-check 的 null-pointer dereference,合成的 checker 用 4 个 CSA callback(`checkPostCall` 识别返回点、`checkBranchCondition` 识别 `if (!ptr)`/`if (ptr == NULL)` 检查点、`checkLocation` 报警解引用、`checkBind` 追踪指针别名),该模式自 2017 年起至少 6 次出现,但 Smatch 等专业工具从未覆盖。

## 关键结果

- 在 61 个多样化 bug-fix patch 上,61% 能合成高质量 checker
- Triage agent 辅助下 FP 率约 35%
- 检测出 **92 个 Linux kernel 新漏洞**,平均潜伏 4.3 年
- **77 个被开发者确认,57 个修复,30 个分配 CVE**
- 发现的漏洞与 Smatch 等专家手写 checker 正交(补充而非重叠)
- 首个全自动 LLM checker 合成系统,代码开源(ise-uiuc/KNighter)

## 相关

- **相关概念**:[[Static-Analysis]]、[[LLM-Agents]]、[[Clang-Static-Analyzer]]
- **同类系统**:Smatch、Coverity
- **同会议**:[[SOSP-2025]]
