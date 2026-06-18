---
type: paper
name: DAS
full_title: "Beat the Long Tail: Distribution-Aware Speculative Decoding for RL Training"
authors: [Zelei Shao, Vikranth Srivatsa, Sanjana Srivastava, Qingyang Wu, Alpay Ariyak, "et al."]
venue: MLSys
year: 2026
tags: [rl-training, speculative-decoding, rollout, suffix-tree, long-tail]
source_pdf: "[[f899139df5e1059396431415e770c6dd.pdf]]"
source_md: "[[f899139df5e1059396431415e770c6dd]]"
---

# Beat the Long Tail: Distribution-Aware Speculative Decoding for RL Training (MLSys 2026)

> **一句话总结**：DAS 为 RL rollout 定制 [[Speculative-Decoding]]：per-problem 滑动窗口 suffix tree 作 training-free drafter（跟踪 policy drift），再按预测生成长度给 long-tail 请求更大 draft budget，在 VeRL+[[vLLM]] 上 rollout 时间降 **50%**（代码任务 ~25%），训练曲线不变。

## 问题

RL post-training 中 **rollout 占 >70%** 墙钟时间。Serving 式 [[Speculative-Decoding]] 不适用，因为：

1. **Batch makespan = max 完成时间**：short 序列先结束导致 effective batch collapse，long straggler 决定步长
2. **跨 epoch 重复同一 dataset**：历史 rollout 可复用为 draft 信号
3. **Policy 持续更新**：EAGLE 等静态 drafter acceptance 平坦甚至下降

并发工作 SPEC-RL / FastGRPO / RhymeRL 或改分布、或耗额外显存、或缺 problem/window awareness。

## 核心方法

**Adaptive nonparametric drafter**：
- 增量 suffix tree（Ukkonen）：O(m) 查询、亚毫秒更新；suffix array 更新需 O(n) rebuild
- 比 EAGLE 在 RL 训练中 acceptance 持续上升

**Per-problem tree + sliding window**：
- 全局树因 policy drift 与跨题迁移差；每题独立 tree，窗口 16/32 epoch 刷新
- 小模型可关 prefix trie 降 CPU 开销

**Length-aware speculative budget**：
- 线性 forward 延迟模型 + 饱和 acceptance 形；按预测长度把 draft budget 倾斜给 long/high-latency 请求
- 运行时按历史 posterior 动态升级 short→medium→long class
- Unlimited budget 因 verification 成本反降 **15%** vs distribution-aware

集成于 VeRL + [[vLLM]]，lossless（分布保持）。

## 关键结果

- 数学 RL（DeepScaleR-7B）：rollout 时间 **>50%** 降低，reward 曲线与 VeRL 一致
- 代码 RL（Qwen3-8B、2×8 H100）：约 **25%** rollout 加速，reward 持平
- seq len 8k→16k 仍 **>30%** 加速；batch 32→16 收益比例保持
- Suffix tree vs suffix array：speculation **2–20×** 更快、更新快 **3 个数量级**
- DAPO policy 下仍 **>30%** 加速

## 相关

- **相关概念**：[[Speculative-Decoding]]、RL-Post-Training、Long-Tail-Scheduling
- **同类系统**：EAGLE、SuffixDecoding、SPEC-RL、FastGRPO、RhymeRL、VeRL、[[vLLM]]
- **同会议**：[[MLSys-2026]]