---
type: paper
name: Auto-Research
full_title: "A Vision for Auto Research with LLM Agents"
authors: [Chengwei Liu, Chong Wang, Jiayue Cao, Jingquan Ge, Kun Wang, et al.]
venue: arXiv
year: 2025
tags: [auto-research, multi-agent, llm-agent, scientific-discovery, vision-paper]
source_pdf: "[[2504.18765v3.pdf]]"
source_md: "[[2504.18765v3]]"
---

# A Vision for Auto Research with LLM Agents (arXiv 2025)

> **一句话总结**:NTU/南开团队提出的 Agent-Based Auto Research 愿景框架,把科研 lifecycle 拆成 8 个阶段(literature/idea/method/experiment/paper/evaluation/rebuttal/promotion),并用 AutoReview prototype 在 6 篇论文 18 条人工 review 上达到 key point 召回率 41.94%、精度 38.81%,代码生成 72%-78% 可直接执行。

## 问题

科研工作流碎片化严重——literature review、idea、method、experiment、writing、review、rebuttal、promotion 每个阶段都要求不同技能;方法学知识分布不均,学生/早期研究者缺少系统指导;不同于工程学科的模块化,科研 reasoning 缺乏复用性。现有的 LLM 科研辅助工具多是 point solution(只做 literature 或只做 writing),缺少端到端的多 agent 协作架构。

## 核心方法

Vision/blueprint paper,不是单个系统。核心是一个**四阶段八模块**的 multi-agent 框架:

- **Preliminary Research**:Literature(retrieval → synthesis → report)+ Idea(problem decomposition、generalization、combining techniques、new problems、empirical studies)+ Method
- **Empirical Study**:Experiment(benchmark/baseline/metric 识别、code implementation、结果分析)
- **Paper Development**:Paper writing + Evaluation(peer-review 模拟)+ Rebuttal
- **Dissemination**:Promotion(跨平台 content optimization)

Method 阶段是全文最具体的设计:**Method Planner + Heuristic Solution Designer** 两个 agent 的 plan-and-execute 范式。Planner 用 chain-of-thought 把研究问题拆成子任务,按 solvability/completeness/non-redundancy 评估;Solution Designer 对每个子任务生成候选方法,用启发式函数打分(relevance、feasibility、reliability、cost),类似 A* 搜索或 Tree-of-Thoughts。若某步无可行方法则反馈给 Planner 重规划。

Evaluation 模块通过 Analysts/Reviewers/Meta-reviewer 多 agent 模拟 peer review,覆盖 novelty/rigor/relevance/verifiability/presentation 五维度。Promotion 模块(Promotion-Zero 原型)做平台自适应的 content 生成与 engagement 反馈闭环。

与已有工作的差异:相比 [[AI-Scientist-v2-arXiv25]] 聚焦 end-to-end 生成单篇论文、[[MLAgentBench-ICML24]] 专注 ML 实验执行、[[MLE-Bench-ICLR25]] 侧重 Kaggle 式基准,本文更偏**顶层架构愿景**,把 rebuttal、promotion 等长尾阶段也纳入视野。

## 关键结果

- **Literature** 模块:针对 "Kernel Fuzzing + Intelligent Mutation" 主题,成功完成关键词生成、PDF 解析、知识图谱构建、LaTeX draft 初稿;定性验证可行。
- **Idea**:在 744 篇 ICSE/FSE/ASE/ISSTA 论文上统计 idea 类型分布,发现 problem decomposition + combination 是主流;LLM 在两个代表 case(PyPI 恶意包检测、DynaMO)上可生成合理 idea,但深度不及 published work。
- **Method**:在 sFlow cryptomining 检测 case 上,Planner 生成 4 步 pipeline(清洗/分组/特征抽取/ML 分类),Solution Designer 为每步选出 LSTM 等具体方法,人工验证"实用且有效"。
- **Experiment**:100 CV/NLP 任务,benchmark 识别正确率 90%,baseline 对齐 78%,mAP+IoU 多指标组合与 human review 95% 匹配;Python 代码生成 72%-78% 无需修改可跑。
- **Evaluation (AutoReview prototype)**:6 篇论文 18 条专家 review 共 62 个关键点,AutoReview 生成 67 点,重合 26 点(precision 38.81%,recall 41.94%);novelty/rigor 重合 >50%,relevance/verifiability/presentation 重合偏低;打分倾向保守(3-4 分中位)。

## 相关

- **相关概念**:plan-and-execute、chain-of-thought、Tree-of-Thoughts、multi-agent collaboration、peer-review simulation
- **同类系统**:[[AI-Scientist-v2-arXiv25]]、[[MLAgentBench-ICML24]]、[[OpenHands-ICLR25]]、[[MLE-Bench-ICLR25]]、[[MLR-Bench-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[AlphaEvolve-arXiv25]]
- **同主题**:[[Auto-Research]]
