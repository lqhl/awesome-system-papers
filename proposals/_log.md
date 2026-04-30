# Proposals Log

> Proposal 层的时间线记录（独立于 wiki/log.md）。按倒序排列，最新在上。

## [2026-04-30] ThinkingModelKVCache
- 基于 probe: `proposals/_probes/thinking-model-kv-cache.md`
- 核心赌注：thinking model 的 CoT trace 让所有现有 KV cache heuristic（recency/stability/attention score）翻车
- Taste 评估：Workload 真实性 ✓ / Counterintuitive ✓ / 10x ✓ / Model-proof ✓ / Abstraction ~ (counterintuitive finding 替代新抽象)
- Target: OSDI 2027 / SOSP 2027（取决于 M1 测量结果）

## [2026-04-30] Probe: Thinking Model KV Cache Management
- 生成：`proposals/_probes/thinking-model-kv-cache.md`
- 覆盖 17 篇论文，4 个 candidate blank，5 个 key unknown
- 核心发现：所有 KV cache tiering/compression heuristic（recency/stability/attention score）的隐含假设在 thinking model CoT trace 下未经验证
