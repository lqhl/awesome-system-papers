---
type: paper
name: DCP
full_title: "DCP: Addressing Input Dynamism In Long-Context Training via Dynamic Context Parallelism"
authors: [Chenyu Jiang, Zhenkun Cai, Ye Tian, Zhen Jia, Yida Wang, Chuan Wu]
venue: SOSP
year: 2025
tags: [long-context, context-parallelism, llm-training, attention, hypergraph-partitioning]
source_pdf: "[[3731569.3764849.pdf]]"
source_md: "[[3731569.3764849]]"
---

# DCP: Addressing Input Dynamism In Long-Context Training via Dynamic Context Parallelism (SOSP 2025)

> **一句话总结**:长上下文训练中把 attention 的 Q/KV 切成细粒度 block,按 hypergraph partitioning 每个 iteration 动态分配到设备,causal mask 下 attention 加速 1.19–2.45×、稀疏 mask 下 2.15–3.77×,端到端训练加速最高 1.46×。

## 问题

长上下文模型(GPT-4o 128K、Claude 3.5 200K、Gemini 2.5 Pro 2M)训练用 context parallelism(CP),把单序列均分到所有设备。现有 CP([[Ring-Attention]]、LoongTrain、TransformerEngine)用静态配置,忽略两种 input dynamism:(1) **序列长度方差**——LongAlign 上长序列只占 0.11%,但短序列仍走相同 CP 度数,产生冗余 KV 通信;(2) **注意力模式方差**——shared question mask(RLHF/DPO)、lambda mask、causal blockwise mask 等稀疏 mask 下,静态 placement 造成严重计算不均衡和通信冗余(shared question mask 例子中 48 个 KV block 里 38 个是冗余传输)。简单的 "改 CP/DP 度" 又在 memory(线性随 token)和 compute(二次随 token)间无法兼顾。

## 核心方法

**Block 表示**:把 attention 的 Q 和 KV 沿 batch/head/SeqQ/SeqKV 四个维度切成细粒度 data block,computation block 捕获 Q-KV 对之间是否需要算(反映 mask 结构)。Block 级 placement 允许"长序列用 CP、短序列用 DP"这种混合配置。

**Hypergraph partitioning 规划器**:每个 iteration 根据 seq len 和 mask,把 block 分配到设备公式化为 hypergraph 划分问题——边表示 KV 通信需求,点权反映 memory/compute load。目标最小化通信代价,约束是 memory/compute balance,调用成熟算法求解。planning 在线运行,与 GPU 训练重叠(data prefetch)。

**执行器 + 指令集**:planner 产出每设备的执行计划,序列化成 5 种 DCP instruction(对应 attention 执行的基本操作,如 recv KV、compute partial attention、rescale-and-sum)。executor 用 [[FlashAttention]] fused kernel 或 Triton 执行,最小化细粒度并行的 overhead。用户接口简单:替换 attention 实现 + 可选 mask 函数 + DCPDataloader。

## 关键结果

- Attention micro-benchmark:causal mask 1.19–2.45×、sparse mask 2.15–3.77× 加速
- 端到端 8B GPT 训练:causal 0.94–1.16×、sparse 1.00–1.46× 加速
- 在 Amazon EC2 p4d.24xlarge 集群(400Gbps)上测试 4TP × 16CP 配置
- 有效处理 LongAlign、LongDataCollection 等长尾序列长度分布
- 支持 shared question mask、lambda mask、causal blockwise mask 等现有框架无法处理的稀疏模式

## 相关

- **相关概念**:[[Context-Parallelism]]、[[Attention]]、[[FlashAttention]]、[[Ring-Attention]]、[[Hypergraph-Partitioning]]、[[Long-Context]]
- **同类系统**:TransformerEngine、LoongTrain、[[Megatron]]、Ring Attention
- **同会议**:[[SOSP-2025]]
