# Proposals Log

> Proposal 层的时间线记录（独立于 wiki/log.md）。按倒序排列，最新在上。

## [2026-06-28] HeteroSmallClusterMultiModelAgent
- 基于 probe: `wiki/proposals/probes/hetero-small-cluster-multi-model-agent.md`
- 核心赌注：cold-catalog pooling（[[CrossPool-arXiv26]] 等）在 warm 小 catalog agent 场景失效；{weights, KV, expert} 需要 StateBudget 统一驻留规划，且 weights 可能先于 KV 触顶异构小集群内存天花板
- Taste 评估：Workload ✓ / Counterintuitive ✓ / 10x (reframed) ✓ / Model-proof ✓ / Abstraction ✓ — 5/5 通过
- Target: OSDI 2027 / SOSP 2027（取决于 M1 H1–H3 测量）

## [2026-06-26] Probe: 异构小集群 Multi-Model Agent Serving
- 生成：`wiki/proposals/probes/hetero-small-cluster-multi-model-agent.md`
- 补缺：[[CrossPool-arXiv26]] wiki 页 + mineru `markdowns/ai-infra/arxiv26-ye-crosspool/`
- 覆盖 18 篇 wiki 论文，5 个 candidate blank，7 个 key unknown
- 核心发现：[[CrossPool-arXiv26]]/[[Aegaeon-SOSP25]]/[[Weaver-ATC25]] 的 cold-catalog pooling 假设与小团队 warm-switching agent 栈冲突；权重/KV/expert 驻留决策在异构紧缺集群上尚无统一 planner

## [2026-06-23] Probe: KV-lifecycle storage layer
- 生成：`wiki/proposals/probes/kv-lifecycle-storage-layer.md`
- 覆盖 32 篇 wiki 论文、8 个外部系统 / 文档 / 预印本信号、8 个 candidate blank、8 个 key unknown
- 核心发现：FAST26 / MLSys26 已经把 KV cache 从 GPU block manager 推向 storage layer，但缺少统一的 lifecycle state machine、typed KV object contract、device-aware placement、tenant/failure/correctness 边界

## [2026-06-09] Probe: MoE Expert Weights and KV Cache Offload
- 生成：`wiki/proposals/probes/moe-kv-cache-offload.md`
- 覆盖 20 篇 wiki 论文、8 篇外部论文 / RFC / 工业系统、6 个 candidate blank、8 个 key unknown
- 核心发现：expert offload 与 KV offload 各自成熟，但几乎没有工作把两类对象放进同一个 HBM/CPU/NVMe 预算器；关键未知是双 miss 时的带宽仲裁、隐藏窗口和正确性边界

## [2026-06-08] Recover: ElasticMoEP2P
- 从 git log（commit bef67ed, ideas/elastic-moe-p2p.md）恢复
- 原创建日期：2026-04-05，原状态：deprecated（因 CRAFT MLSys'26 压缩 novelty 空间）
- 放入 proposals/ElasticMoEP2P.md，status: archived
- 保留完整的技术方案、对比分析、实验规划，供未来 pivot 参考

## [2026-05-06] ImportanceGuidedKVTiering
- 基于 probe: `proposals/_probes/subquadratic-sparse-attention.md`
- 核心赌注：sparse attention 的 block importance scores（当前被丢弃的计算副产品）是 KV cache tier placement 的最优信号，跨 query 聚合后 quality 超越 LRU ≥ 20%
- Taste 评估：Workload 真实性 ✓ / Counterintuitive ✓ / 10x (reframed as cost-per-query) ✓ / Model-proof ✓ / Abstraction ✓ — 5/5 通过
- 关键张力：如果 post-hoc extraction (H4) 验证 → 技术适用于所有已部署模型，adoption barrier 极低；如果 H1 不通过 → pivot to negative result

## [2026-05-06] Probe: Subquadratic Sparse Attention
- 生成：`proposals/_probes/subquadratic-sparse-attention.md`
- 覆盖 12 篇论文（wiki 内 10 篇 + 外部 2 篇），5 个 candidate blank，5 个 key unknown
- 核心发现：content-dependent sparse attention 在 2025-2026 成为第三条路线（exact attention → sparse attention ↔ linear/SSM），但 NSA/SSA/DSA/Twilight 四种策略在是否需要 dense fallback、训练阶段、selection 开销上存在根本分歧

## [2026-04-30] ThinkingModelKVCache
- 基于 probe: `proposals/_probes/thinking-model-kv-cache.md`
- 核心赌注：thinking model 的 CoT trace 让所有现有 KV cache heuristic（recency/stability/attention score）翻车
- Taste 评估：Workload 真实性 ✓ / Counterintuitive ✓ / 10x ✓ / Model-proof ✓ / Abstraction ~ (counterintuitive finding 替代新抽象)
- Target: OSDI 2027 / SOSP 2027（取决于 M1 测量结果）

## [2026-04-30] Probe: Thinking Model KV Cache Management
- 生成：`proposals/_probes/thinking-model-kv-cache.md`
- 覆盖 17 篇论文，4 个 candidate blank，5 个 key unknown
- 核心发现：所有 KV cache tiering/compression heuristic（recency/stability/attention score）的隐含假设在 thinking model CoT trace 下未经验证
