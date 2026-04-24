---
type: paper
name: AI-Scientist-v2
full_title: "The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search"
authors: [Yutaro Yamada, Robert Tjarko Lange, Cong Lu, Shengran Hu, Chris Lu, "et al."]
venue: arXiv
year: 2025
tags: [autoresearch, agent, tree-search, scientific-discovery, vlm]
source_pdf: "[[2504.08066v1.pdf]]"
source_md: "[[2504.08066v1]]"
---

# The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (arXiv 2025)

> **一句话总结**：Sakana AI 的 v2 端到端自主科研系统，取消了 v1 的人工 code template 依赖，用 experiment-manager + 并行 agentic tree search + VLM 反馈环跑 4 阶段实验流水线，向 ICLR 2025 ICBINB workshop 投了 3 篇全 AI 生成论文，其中 1 篇拿到 6.33/10 审稿均分（前 45%），成为首个过 peer review 的全 AI 生成论文。

## 问题

[[AI-Scientist-arXiv24|AI Scientist v1]]（Lu et al., 2024）虽然首次做到端到端自动化（hypothesis → code → experiment → manuscript），但有两大瓶颈：

1. **Template 依赖**：每个新 topic 都要人工写一份 baseline 代码模板才能跑
2. **线性实验流**：hypothesis 逐步 sequential refine，无回溯、无并行、探索深度受限

需要一套架构把 AI scientist 从 domain-specific 玩具推进到 domain-general 的真实科研 workflow。

## 核心方法

**去除 template 依赖 + 更开放的 idea generation（§3.1）**：系统不再基于已有代码做增量改动，而是在更高抽象层（类似 grant proposal）做 open-ended brainstorm，中途可调 Semantic Scholar 查新颖性。

**Experiment Progress Manager（§3.2.1）**：四阶段结构化科研流水：

1. Stage 1 Preliminary Investigation：最小可运行原型
2. Stage 2 Hyperparameter Tuning：超参搜索直到 training curve 收敛 + 至少 2 个 dataset 跑通
3. Stage 3 Research Agenda Execution：系统执行 research agenda 直到 compute budget 耗尽
4. Stage 4 Ablation Studies：评估各组件重要性

每个 stage 结束由 LLM-evaluator 挑最佳 node，并跑多次 replication 拿 mean ± std 喂给下个 stage。

**Parallelized Agentic Tree Search（§3.2.2）**：跨所有 4 个 stage 用并行 best-first tree search，灵感来自 AIDE（Jiang et al., 2025，[[MLE-Bench-ICLR25|MLE-Bench]] 冠军 scaffold）。每个 node 包含 {experiment code, plan, error trace, runtime, metrics, LLM feedback, plot script, plot paths, VLM feedback, status}。五种 node 类型：

- **Buggy / Non-buggy**：执行失败 vs 成功
- **Hyperparameter node**（Stage 2）：记忆已测超参避免重复
- **Ablation node**（Stage 4）：评估组件重要性
- **Replication node**：同 parent 不同 seed 重跑
- **Aggregation node**：不做新实验，只合并 replication 结果出带 mean/std 的图

每轮以预定概率选 buggy（触发 debug）vs non-buggy（触发 refinement），多个子节点并行执行。

**VLM Reviewer（§3.4）**：VLM 在两处介入：

- 实验阶段对生成的 figure 打分，label/legend/misleading visualization 问题会把 node 标 buggy
- Manuscript writing 阶段审 figure + caption + 正文引用的一致性，检测 figure 重复、caption 错误

**Manuscript writing**：v1 用 Aider 增量写作，v2 改成 single-pass 生成 + 用 o1 做 reflection，再用 VLM 审图文一致性。

**Dataset loading**：优先用 Hugging Face Hub `datasets.load_dataset`。

## 关键结果

- **ICLR 2025 ICBINB Workshop 盲审**：3 篇全 AI 生成投稿在 43 篇中，1 篇拿到 6/7/6（均分 6.33，前 45%）通过 meta-review 可接收门槛，另 2 篇未过
- **首次**：AI 生成论文过 peer review（事先与 ICLR 领导层、workshop 组织者协调，IRB 批准 H24-02652，接收后按约定撤稿）
- **被接收论文主题**：在 LSTM 序列模型 embedding 上加 compositional regularization 项（相邻 time step embedding 不要差太多）做 compositional generalization，结论是 negative result——正则项没显著提升甚至偶尔伤害性能
- **作者内部复盘发现的瑕疵**：citation hallucination、training/test 集 57% overlap、figure caption 对 validation loss 的解释有误、regularization 应用位置描述不清
- **v1 → v2 特性对比**：codebase drafting 从 topic-specific → domain-general、execution 从 linear → tree-based、支持 parallel experiment、加入 VLM reviewer、首次进入 workshop acceptance
- 开源 [github.com/SakanaAI/AI-Scientist-v2](https://github.com/SakanaAI/AI-Scientist-v2)

**作者自评**：系统离稳定达到 main-track 会议水平还差很远（workshop 接收率 60-80% vs main 20-30%），且 novel 高影响 hypothesis、深度 domain-specific justification 仍是短板。但这是通往 AGR / AI-for-AI 的里程碑。

## 相关

- **相关概念**：Agentic Tree Search、VLM Feedback Loop、Experiment Manager、Compositional Regularization
- **同类系统**：[[AI-Scientist-arXiv24]]（v1 前身）、AI-Researcher（HKU DS Lab）、Intology Zochi、AutoScience Carl、Agent Laboratory、agentRxiv、CycleResearcher、AI Co-Scientist (Google)
- **相关 scaffold**：AIDE（直接启发 v2 的 tree search）、[[OpenHands-ICLR25]]
- **相关 benchmark**：[[MLE-Bench-ICLR25]]、SciCode、BixBench、METR RE-bench
- **同主题**：[[Auto-Research]]
