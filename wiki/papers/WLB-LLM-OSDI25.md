---
type: paper
name: WLB-LLM
full_title: "WLB-LLM: Workload-Balanced 4D Parallelism for Large Language Model Training"
authors: [Zheng Wang, Anna Cai, Xinfeng Xie, Zaifeng Pan, Yue Guan, et al.]
venue: OSDI
year: 2025
tags: [llm-training, parallelism, workload-balance, long-context, pipeline-parallelism]
source_pdf: "[[osdi25-wang-zheng.pdf]]"
source_md: "[[osdi25-wang-zheng]]"
---

# WLB-LLM: Workload-Balanced 4D Parallelism for Large Language Model Training (OSDI 2025)

> **一句话总结**：在 4D 并行（DP+PP+CP+TP）LLM 训练中通过 variable-length packing + outlier delay + per-document sharding 消除 PP 和 CP 两层的 workload imbalance，内部训练框架平均提速 1.23×。

## 问题

8K GPU 规模训练 405B LLM（128K 上下文）时，GPU 之间计算延迟差异高达 1.44×，同步 barrier 让所有 GPU 等最慢的那个，拖低端到端训练效率。根因是注意力计算的 input-dependent 特性：因为跨文档的 attention 被 mask 掉，长文档尾部 token 需要 attend 到更多前文，per-token 算力强度严重不均。

4D 并行 ([[Pipeline-Parallelism]] + context parallelism + [[Tensor-Parallelism]] + data parallelism) 的现有框架 (Megatron-LM 等) 在 DP/PP 级把文档固定长度打包，CP 级把 sequence 等分成 2×CP_size 块，完全不考虑算力异质，不可避免出现：（1）micro-batch 间不平衡（某个微批恰好塞进一条超长文档时）；（2）CP 组内 document shard 不平衡。PP 级的流水线依赖还会把 imbalance 放大到整个训练步的关键路径。

## 核心方法

**PP 级 variable-length packing + outlier delay**：不再强制 micro-batch 等长。优化目标改为平衡每个 micro-batch 的总算力（attention 的二次项 + GEMM/collective/elementwise 的线性项之和），用 ILP 描述、运行时用启发式算法求解。由于长文档 token 总量占比小（< half context 的文档贡献 > 75% token），WLB-LLM 用多级等待队列把极端长文档「延迟」到积累够一个 global batch 的 micro-batch 数再统一插入，每个 micro-batch 分到一条长文档，平衡度接近最优，且只扰动少量 token 的 data loader 随机性，不显著影响 convergence。

**CP 级 per-document sharding**：不再把整个 sequence 等分成 chunks，而是对每个 document 单独做 sharding。设计了自适应算法在 runtime 根据输入选择最佳 sharding 策略（考虑 kernel 效率和平衡度之间的 tradeoff）。

## 关键结果

- 内部 LLM 训练框架（Meta）平均提速 1.23×
- 跨多种 model scale（550M / 7B / 30B / 70B）和 context window（64K / 128K）有一致改进
- 分析了 packing window 扩大带来 balance 提升但 data randomness 下降导致 loss 上升的 tradeoff，证明 fixed-length packing 不能同时兼顾两者
- 在 8K GPU 405B 训练 trace 中明确识别出 PP 和 CP 两层 imbalance 源

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Attention]]
- **同会议**：[[OSDI-2025]]
