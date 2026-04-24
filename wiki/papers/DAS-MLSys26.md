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

> **一句话总结**：DAS 为 RL post-training 的 rollout 阶段定制 [[Speculative-Decoding]]：用 per-problem 滑动窗口 suffix tree 作为 training-free 的 drafter（适应 policy drift），再按预测生成长度给 long-tail 请求分配更大的 draft budget，把 rollout 延迟降低 50%，不影响训练曲线。

## 问题

**RL rollout 主导训练时间**（>70%）。直接套用 serving 系统的 [[Speculative-Decoding]] 失效，因为 RL 有三个独特属性：

1. **All-or-nothing 完成语义**：batch 中所有 sample 必须完成才能进下一步训练 → long-tail straggler 决定 makespan；short 完成后 effective batch size collapse，GPU idle
2. **Dataset 跨 epoch 重用**：同一 prompt 被反复 rollout → 历史 trajectory 可做 drafter
3. **Target model 持续变化**：policy drift 让 pre-trained draft model（如 EAGLE）的 calibration 失效

现有 RL-SD 工作（SPEC-RL、FastGRPO、RhymeRL）或改变输出分布、或需额外 memory 开销、或缺 problem-difficulty 和 window awareness。

## 核心方法

**1. Adaptive nonparametric drafter（用 suffix tree）**：
- 用 Ukkonen 算法增量维护 O(m) 查询、亚毫秒更新的 suffix tree（suffix array 更新要 O(n) rebuild，不可行）
- 每次 rollout 取 current context 在 tree 里找 longest match，沿匹配路径生成多 token draft，target model 并行验证
- 比 EAGLE 的 flat acceptance 更好：随训练进行 acceptance 还在上涨

**2. Per-problem suffix tree + prefix trie**：
- 全局树因 policy drift + 跨 problem 迁移差而效果差
- 每个 problem 独立 suffix tree，用 prefix trie 做路由；小模型可关掉 trie 直接查
- 跟 domain-specific pattern 更对齐

**3. Sliding window history**：
- 因 policy drift，远期 trajectory 预测力下降（Fig 2 对角块结构）
- 按滑动窗口（16 或 32 epoch）重建 drafter，平衡 bias-stability trade-off
- 窗口 size 与 optimizer step scale 挂钩

**4. Length-aware speculative budget（核心创新）**：
- Forward-pass 延迟线性拟合：$t_{\text{fwd}} = c_{\text{base}} + c_{\text{tok}} n_{\text{toks}}$（MRE ≈ 12%）
- Accepted token 饱和形：$A_i(p_i) = k_i l_i (1 - e^{-\alpha_i p_i / l_i})$
- Batch makespan = $\max_i$ 剩余 token 的 forward passes
- 按预测生成长度给"长"请求分配更大 draft budget，不均匀分配避免 short 请求浪费

## 关键结果

- 在数学（DeepScaleR）和代码（Luo et al., 2025a）任务上相比 VeRL 降低 **up to 50% 生成时间**
- 模型 1.5B–8B，6 台 H100 服务器
- **训练曲线完全一致**（不改变输出分布）
- Suffix tree vs suffix array：speculation 快 2–20×、更新快 3 orders of magnitude
- Per-problem scoped tree 比 global tree 同时有更高 acceptance 和更低 latency

## 相关

- **相关概念**：[[Speculative-Decoding]]、RL-Post-Training、Long-Tail-Scheduling
- **同类系统**：EAGLE/EAGLE-2/EAGLE-3、SuffixDecoding、PLD+、SPEC-RL、FastGRPO、RhymeRL、VeRL、[[vLLM]]
- **同会议**：[[MLSys-2026]]
