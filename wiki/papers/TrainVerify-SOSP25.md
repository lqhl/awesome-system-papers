---
type: paper
name: TrainVerify
full_title: "TrainVerify: Equivalence-Based Verification for Distributed LLM Training"
authors: [Yunchi Lu, Youshan Miao, Cheng Tan, Peng Huang, Yi Zhu, Xian Zhang]
venue: SOSP
year: 2025
tags: [formal-verification, distributed-training, parallelism, llm-training, equivalence-checking]
source_pdf: "[[3731569.3764850.pdf]]"
source_md: "[[3731569.3764850]]"
---

# TrainVerify: Equivalence-Based Verification for Distributed LLM Training (SOSP 2025)

> **一句话总结**：证明 parallelized DFG 与 logical DFG 的 parallelization equivalence，用 staged verification + shape reduction 在 **分钟–半天** 内验证 Llama3 405B、DeepSeek-V3 671B 训练计划，集成 nnScaler。

## 问题与动机

分布式 [[LLM]] 训练（[[Tensor-Parallelism]]/[[Pipeline-Parallelism]]/[[Data-Parallelism]]/expert parallel）execution plan 极易出 silent bug（错误 gradient、错误 state shard），浪费百万美元 GPU 时。Correct-by-construction 新栈不现实；需在现有框架上验证 **parallelization equivalence**：任意输入下 parallelized DFG 输出 ≡ logical DFG。

## 关键观察 / 隐含假设

- **观察 1**：logical DFG（数学语义）相对可信；materialized execution plan 捕获并行化 essence，验证二者等价可消除 major bug class。
  - **依赖假设**：logical DFG 本身正确（数学+经验验证）；plan 包含全部训练相关算子。
  - **可能失效场景**：runtime 动态行为（conditional branch、NCCL 算法选择）未编入 DFG。
  - **证据强度**：强——可检出真实 parallelization bug case study。
- **观察 2**：端到端符号表达式验证不可 tractable，但按 stage 分割 + shape reduction 可保持 formal correctness 同时降复杂度。
  - **依赖假设**：stage 边界选择保留 lineage；小 shape 证明可 extend 到大 shape。
  - **可能失效场景**：shape reduction 不覆盖的 exotic tensor layout；跨 stage lineage 丢失。
  - **证据强度**：中——TLA+ spec + technical report，最大模型半天验证。
- **假设 1**：集成 nnScaler 并保留 lineage metadata 的工程改动可接受。
  - **证据强度**：强——已开源集成。

## 核心方法

1. **Symbolic DFG**：算子数学语义符号化
2. **Staged verification**：DFG 分 stage 并行验证，链式证明 IO equivalence
3. **Shape reduction**：缩小 tensor shape 验证，证明结构同构时可 extend

集成 nnScaler：增强 DFG 含训练全流程；保留 parallelization 丢弃的 lineage。

## 设计取舍

- **取舍 1**：验证 plan 而非 runtime execution——不覆盖 NCCL hang、SDC 等运行时故障。
- **取舍 2**：shape reduction 需人工/自动证明 extend 条件，增加 upfront 成本。
- **边界条件**：nnScaler 支持的 parallelization 模式；新算子需补 symbolic 语义。

## 实验与结果

- 成功验证 Llama3 8B/70B/405B、DeepSeek-V3 16B/236B/671B plans
- 小/中模型：分钟–小时；最大：**~半天**
- 检出并消除多类真实 parallelization bug
- 开源：https://github.com/verify-llm/TrainVerify

## Critical Analysis

### 论证链条

「silent parallelization bug 代价高 → 验证 equivalence 而非重写栈」定位精准。三技术与 scalability challenge 映射清楚。

### 假设压力测试

- Runtime 与 plan 偏离（framework bug、动态 shape）时 guarantee 失效。
- 新架构（Mamba、MoE EP 复杂 sharding）symbolic 语义维护成本？
- 半天验证 671B 对 CI 仍偏重，需 incremental verification。

### 实验可信度

Frontier model 覆盖是亮点。Bug detection case 有说服力。缺与 training 实际 loss 曲线对比的「验证后零训练异常」长期统计。

### 系统性缺陷

论文未讨论：verified plan 与 PyTorch/NCCL 版本升级后的 re-verify 流程；multi-node 网络 partition 语义不在范围。

## 局限与 Future Work

- **局限 1**：不验证 runtime 执行与浮点数值误差。
- **局限 2**：最大模型验证仍需半天级 CPU 时间。
- **Future work 1**：plan diff 增量验证，仅重证变更 stage。

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Data-Parallelism]]、formal verification
- **同类系统**：nnScaler、[[ByteRobust]]、[[Mycroft]]
- **同会议**：[[SOSP-2025]]