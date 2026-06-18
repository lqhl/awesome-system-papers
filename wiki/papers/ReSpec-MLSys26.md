---
type: paper
name: ReSpec
full_title: "ReSpec: Towards Optimizing Speculative Decoding in Reinforcement Learning Systems"
authors: [Qiaoling Chen, Zijun Liu, Peng Sun, Shenggui Li, Guoteng Wang, "et al."]
venue: MLSys
year: 2026
tags: [reinforcement-learning, speculative-decoding, llm-training, knowledge-distillation]
source_pdf: "[[8e296a067a37563370ded05f5a3bf3ec.pdf]]"
source_md: "[[8e296a067a37563370ded05f5a3bf3ec]]"
---

# ReSpec: Towards Optimizing Speculative Decoding in Reinforcement Learning Systems (MLSys 2026)

> **一句话总结**：ReSpec 在 VeRL+SGLang 的 RL 生成阶段集成 EAGLE-3 风格 SD，用 Adaptive Server 按 active batch 动态开关 speculation、Online Learner 以 reward-weighted KD 持续对齐 drafter，Qwen2.5 3B–14B 上端到端快 1.5–4.5× 且 reward 曲线与 baseline 一致。

## 问题

RL 后训练里 generation 占迭代时间 75–86%，但 serving 里的 [[Speculative-Decoding]] 直接搬进 RL 会踩三坑：(G1) 大 batch 时 SD 加速递减甚至变慢；(G2) actor 每步更新导致 drafter stale、acceptance length 下降；(G3) 非确定性 verify 路径 + stale drafter + 方差放大，实测 EAGLE-3 在 ~100 step 后 reward 明显下滑。

## 核心方法

**Adaptive Speculative Decoding Server**：
- **Solver**：离线 profile draft/target 延迟，拟合 speedup vs active batch 的 (s,t,n) 配置
- **Scheduler**：监控 batch 内 active sequence 数，大 batch 切 non-spec、小 batch 开 spec；non-spec→spec 时复用 [[KV-Cache|KV]] 建 draft 状态，切换开销近零

**Online Learner**：
- **Reward-weighted KD**：\(L = w(r)\sum_t \mathrm{KL}(p \| q_\theta)\)，高 reward rollout 权重大，避免低质轨迹把 drafter 拉偏
- **Async overlap**：replay buffer 每 I 步更新 drafter，与下一轮 generation 并行，避免 pipeline bubble

基于 EAGLE-3 drafter，~2K LOC（500 Adaptive Server + 1500 Online Learner）。

## 关键结果

- Qwen2.5 3B/7B/14B + GRPO + math：ReSpec validation score 紧贴 no-SD baseline，naïve EAGLE-3 明显发散
- 端到端训练 latency：**1.5–4.5×** speedup（Fig. 13）
- 消融：no-reward KD 与 eagle-only 在 ~125 step 附近 reward 崩溃；reward-weighted KD 持续上升
- Generation 占 RL 迭代 75–86%（Table 1，7B 8K response）

## 相关

- **相关概念**：[[Speculative-Decoding]]、[[Continuous-Batching]]
- **同类系统**：[[SGLang]]、VeRL、FastGRPO、SPEC-RL（concurrent）
- **同会议**：[[MLSys-2026]]
- **对比**：[[SparseSpec-MLSys26]]（inference SD）vs ReSpec（training SD）