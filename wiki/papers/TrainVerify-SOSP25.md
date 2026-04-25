---
type: paper
name: TrainVerify
full_title: "TrainVerify: Equivalence-Based Verification for Distributed LLM Training"
authors: [Yunchi Lu, Youshan Miao, Cheng Tan, Peng Huang, Yi Zhu, Xian Zhang, Fan Yang]
venue: SOSP
year: 2025
tags: [llm-training, formal-verification, distributed-training, parallelization, equivalence-checking]
source_pdf: "[[3731569.3764850.pdf]]"
source_md: "[[3731569.3764850]]"
---

# TrainVerify: Equivalence-Based Verification for Distributed LLM Training (SOSP 2025)

> **一句话总结**:把分布式训练执行计划与逻辑 DNN 建模为 symbolic DFG,用分段并行验证 + shape reduction,形式化验证 Llama3 405B 和 DeepSeek-V3 671B 训练计划的并行化等价性,几分钟到半天内完成,消灭"跑几周才发现 loss scaling 错" 这类 silent bug。

## 问题

LLM 训练在万级 GPU 上跑数月数百万美元,但三款主流框架(Megatron-LM、DeepSpeed、nnScaler)commit/issue 里各自有 20+ 个 parallelization-specific bug(op 变换错、调度错、通信错)。这些 bug 通常 **silent**——浮点误差 + 混合精度 + 不同 kernel 实现导致"正常噪声"和"真错误"难以区分,differential testing 在万级 GPU 上不可行(没法跑单卡对照),一个错的 gradient 同步 bug 可能要几周才被发现(MegatronLM loss scaling bug 讨论了几个月才定位)。

## 核心方法

**Parallelization Equivalence (PE)**:把逻辑模型 M 和并行化模型 M' 都表示为 data flow graph(DFG)。形式化要求:∀ 输入 x,对每个逻辑 tensor t,t(x) 必须等于其并行化副本的按 parallelization 方案(identity / all-reduce / concat)组合的结果。这避开了验证整个训练栈的噩梦,只对一个具体的 execution plan 做符号等价检查。

**Symbolic DFG**:定义符号算子覆盖 transformer 常见操作(Linear、MatMul、Softmax、LayerNorm、Embedding 等)+ 并行算子(Chunk、AllReduce、AllToAll)。逻辑 DFG 和并行化 DFG 都转成 symbolic expression,在 real arithmetic 上做等价检查——免疫浮点噪声。

**Staged verification**:大模型的长符号表达式直接验会 intractable。把 DFG 沿 stage(layer/micro-batch)切片,每段独立并发验证,通过相邻段的 input-output lineage metadata 把局部 proof 链起来,保证全局正确。

**Shape reduction**:关键 scalability 技巧——把大 tensor shape(如 [batch, seq=131072, hidden=8192])映射到小 shape 做验证,同时证明结构性质在 scale-up 时保持。允许在小 shape 上跑 SMT solver,再把结果推广到真实大小。

**实现**:集成进 [[nnScaler]] 框架,添加 DFG 覆盖全训练迭代(forward、backward、optimizer、metric)以及 tensor lineage 追踪。

## 关键结果

- 成功验证 Llama3 8B/70B/405B 和 DeepSeek-V3 16B/236B/671B 的执行计划
- 小中型模型数分钟-数小时,最大模型半天内完成
- 能检测/消除真实世界中的 op 变换、调度、通信类 bug(MegatronLM/DeepSpeed/nnScaler 共 25-28 个典型 bug)
- 开源在 github.com/verify-llm/TrainVerify

## 相关

- **相关概念**:[[Distributed-Training]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Formal-Verification]]、[[Data-Flow-Graph]]、[[Symbolic-Execution]]
- **同类系统**:[[nnScaler]]、[[Megatron]]、[[DeepSpeed]]、Alpa
- **同会议**:[[SOSP-2025]]
