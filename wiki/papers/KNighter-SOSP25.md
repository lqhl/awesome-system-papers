---
type: paper
name: KNighter
full_title: "KNighter: Transforming Static Analysis with LLM-Synthesized Checkers"
authors: [Chenyuan Yang, Zijie Zhao, Zichen Xie, Haoyu Li, Lingming Zhang]
venue: SOSP
year: 2025
tags: [static-analysis, llm, linux-kernel, bug-finding, checker-synthesis]
source_pdf: "[[3731569.3764827.pdf]]"
source_md: "[[3731569.3764827]]"
---

# KNighter: Transforming Static Analysis with LLM-Synthesized Checkers (SOSP 2025)

> **一句话总结**：直接让 LLM 扫 3000 万行 [[Linux-Kernel]] 不现实；KNighter 从历史 patch 用 LLM **合成** Clang Static Analyzer checker，再在全库跑，61 个 diverse patch 中 61% 合成成功、~35% FP（triage 后），已发现 92 个新 bug（平均潜伏 4.3 年）、30 CVE。

## 问题与动机

OS kernel 静态分析需覆盖多样 bug pattern 与巨大 codebase。传统 analyzer 依赖专家手写规则，窄且维护贵；LLM 可从 patch 学 pattern，但整库扫描受 context window 与成本限制，且易 hallucinate。核心 insight：**用 LLM 生成 checker，而非用 LLM 直接审代码**——把成本摊到可复用、可验证、人类可读的规则上。

## 关键观察 / 隐含假设

- **观察 1**：历史 bug-fix patch 含丰富 context，适合提炼为 specialized checker，绕过整库 LLM 推理。
  - **依赖假设**：patch 与 bug pattern 对齐；合成 checker 可用原始 patch 做 correctness validation。
  - **可能失效场景**：复杂 semantic bug 难以从局部 patch 泛化为 path-sensitive checker。
- **观察 2**：合成 checker 必须经 multi-stage pipeline + automated refinement（triage agent）才可达 deployable FP 率。
  - **依赖假设**：CSA 作为 backend 足够表达 Linux kernel 常见 defect。
  - **可能失效场景**：需 whole-program 或 inter-procedural 深度分析的模式 CSA 表达力不足。
- **观察 3**：检出 bug 与现有 expert analyzer **正交**，说明 patch-driven synthesis 补盲区。
  - **依赖假设**：Linux patch stream 持续供给新 pattern。
  - **证据强度**：强。92 bug / 30 CVE 为硬证据。

## 核心方法

1. **Multi-stage synthesis**：从 patch 分解子任务生成 CSA checker 逻辑。
2. **Validation against original patch**：用 patch 作为 oracle 检验 checker 能否召回修复点。
3. **Automated refinement pipeline**：triage agent 迭代降 false positive。
4. **Deployment**：checker 人类可读、可维护，全库扫描成本远低于 repeat LLM。

基于开源 CSA；目标 Linux kernel。

## 设计取舍

- **Checker synthesis vs direct LLM analysis**：可扩展、可 trace，但受 patch 质量与 CSA 表达力限。
- **Automated refinement vs manual FP 清洗**：降人力，但 triage agent 自身可能漏报/误杀。
- **Linux-specific toolchain vs 通用 framework**：深集成，移植需重做。

## 实验与结果

- 61 diverse bug-fix patches：**61%** 合成 high-quality checker。
- FP rate ~**35%**（aided by triage agent）。
- 已发现 **92** 新 critical long-latent bugs（平均 **4.3** 年）；**77** confirmed、**57** fixed、**30** CVE。
- 与 expert-written analyzer 检出正交。

## Critical Analysis

### 论证链条

「LLM 不能直接 scale → 合成 checker → patch validate → 全库扫」链条由 CVE 与 upstream fix 闭合。从 61% synthesis rate 外推到「多数新 bug class 可自动化」仍激进——失败 39% 的 pattern 特征未系统分类。

### 假设压力测试

- Patch 只反映已修复 bug，对 zero-day pattern 无帮助。
- CSA 路径爆炸下 checker 可能 FP/FN 同时恶化——论文报告 aggregate FP，缺 per-checker 长期 drift 数据。
- Adversarial patch 是否可误导 synthesis——论文未讨论。

### 实验可信度

- 真实 kernel bug/CVE 证据极强。
- 61 patch 样本相对 30M LOC 仍小；缺少与 CodeQL/自定义 Klint 的全面对照矩阵。
- FP 35% 是否可接受取决于 triage 人力——生产成本模型未公开。

### 系统性缺陷

- 论文未讨论 checker 合入主线 CSA/CI 的 latency 与 kernel 版本跟进。
- Semantic correctness of synthesized checker w.r.t. intent 仍可能偏离 patch 作者本意。
- 对 non-C kernel code（assembly）覆盖有限。

## 局限与 Future Work

- **局限**：依赖 patch + CSA；39% synthesis 失败；FP 仍高；Linux-centric。
- **Future work**：跨 analyzer backend；从 issue/discussion 学 pattern；证明合成 checker soundness 片段。

## 相关

- **相关概念**：[[Linux-Kernel]]、Static Analysis、LLM、Clang Static Analyzer
- **同类系统**：Coccinelle、Smatch、Coverity、GPT-driven code review
- **同会议**：[[SOSP-2025]]