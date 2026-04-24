# Wiki Index

> 最后更新: 2026-04-24

本 wiki 是所有 LLM 生成的综合层，跨论文的实体、概念、比较、主题页都住在这里。Raw sources（`papers/` 和 `markdowns/`）不属于 wiki，它们是 wiki 的材料。

## Conferences

- [[MLSys-2026]] — 79 篇 | KV/attention/speculative 三线占 ~30%，MoE 与 AI4AI 成建制进入，可审计 ML 集群化

## Entities

### Systems

- [[vLLM]] — UC Berkeley 高吞吐 LLM serving 框架，PagedAttention 起源
- [[SGLang]] — LMSYS 的 LLM serving 框架，RadixAttention + 结构化生成 DSL

### Orgs / Labs

（待生成）

### Benchmarks

（待生成）

## Concepts

- [[KV-Cache]] — LLM 推理的核心内存对象，过去三年 serving 论文的优化主线
- [[MoE]] — Mixture of Experts，2024+ frontier LLM 事实架构，系统层痛点集中
- [[PagedAttention]] — 把 KV cache 当 OS 虚存分页管理（vLLM 引入）
- [[Speculative-Decoding]] — 用 draft model 并行验证多 token，无 quality loss 加速
- [[Disaggregation]] — prefill / decode 拆到不同 GPU，配合 RDMA KV transfer

## Comparisons

（按需手动触发生成）

## Themes

- [[AI-Infra]] — AI 基础设施综述（5 篇 paper：TransferEngine / Libra / INET4AI MoE LB / AttnRes / MSA）
- [[Foundation]] — 2 篇 | 2017 Transformer 与 2026 DeepSeek-V4 两端,构成 LLM 架构 9 年传承线

## Papers

`wiki/papers/` 下每篇论文一页，按系统/方法命名（如 `vLLM-SOSP23.md`、`TransferEngine-arXiv25.md`）。由于数量多（预计 500+），不在本 index 中逐篇列出，通过 theme / conference / entity / concept 页的反向链接到达。

当前已有：
- arXiv / AI-Infra 专题（6 篇）：[[TransferEngine-arXiv25]]、[[Libra-arXiv26]]、[[AttnRes-arXiv26]]、[[MSA-arXiv26]]、[[LatencyOptimal-MoELB-INET4AI25]]、[[FluxMoE-arXiv26]]
- Foundation 专题（2 篇）：[[Transformer-NeurIPS17]]、[[DeepSeek-V4-arXiv26]]
- [[MLSys-2026]]（79 篇）见会议综述页

---

## 使用说明

- 所有内部链接用 Obsidian wikilink 格式 `[[PageName]]` 或 `[[PageName|显示文字]]`，不写路径，不加 `.md` 后缀
- 链接到 PDF 源文件时保留后缀：`[[sosp2023-kwon.pdf]]`
- 本文件由 `wiki-survey`、`wiki-update` 等 skill 在生成新页面时追加条目；人工可以补充一句话描述
