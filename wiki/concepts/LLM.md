---
type: concept
aliases: [LLM, large language model, Large Language Models, foundation model, LLMs]
last_updated: 2026-07-30
tags: [llm-inference, llm-training, foundation-model, agents, serving]
---

# LLM

> 大语言模型（Large Language Model，LLM）在系统研究中既是训练/服务的重型 workload，也是 agent、代码生成和运维系统中的非确定性组件。

## 核心思想

LLM 以 Transformer 自回归生成 token。训练组合 data/tensor/pipeline/expert parallel 与 checkpoint；推理分为 compute-heavy prefill 和 memory-bandwidth-heavy decode，并维护随 context 增长的 [[KV-Cache]]。模型规模、长序列与多租户 SLO 将 GPU HBM、互连、storage 和 scheduler 绑在同一关键路径。

当 LLM 作为系统组件时，系统还必须处理 hallucination、cost、latency variance 与 version drift；symbolic verifier、retrieval、cache 和 execution sandbox 往往比换模型更决定可靠性。

## 为什么重要

OSDI 2026 展示了从硬件到运维的完整跨度：[[Prism-OSDI26]] 统一 weights/KV 的弹性 GPU memory sharing；[[EcoServe-OSDI26]] 在普通 Ethernet 上以部分 phase disaggregation 保留 locality；[[AEGIS-OSDI26]] 在 3500 万 GPU-hours 中检测训练 SDC；[[NeuroSymbolicProof-OSDI26]] 将 LLM proposal 与 Isabelle pruning/closure 组合；[[gigiprofiler-OSDI26]] 用 LLM 做语义召回、再用静态/动态分析验证。

这些工作共同说明：LLM 的系统优化不只追求 tokens/s，还要同时约束 TTFT、TPOT、model quality、fault recovery、energy 与可验证性。

## 关键观察 / 隐含假设

- **观察：memory object 常先于 FLOPs 成为瓶颈。** [[Prism-OSDI26]]、[[DirectKV-OSDI26]]、[[Strata-OSDI26]] 分别从共享、direct access 和层级 cache 处理 weights/KV。
- **观察：phase/role heterogeneity 是一等属性。** [[RollArt-OSDI26]]、[[RobustRL-OSDI26]] 区分 rollout/trainer/tool/reward，[[EcoServe-OSDI26]] 区分 prefill/decode。
- **观察：LLM 输出必须接确定性边界。** [[NeuroSymbolicProof-OSDI26]]、[[Ote-OSDI26]]、[[gigiprofiler-OSDI26]] 都用 verifier/analysis 剪除错误候选。
- **假设：profile 与 locality 在控制周期内稳定。** workload drift、模型升级或 agent behavior change 会让离线计划失效。

## 设计空间与取舍

- **Training / serving / agent runtime**：资源形态、正确性目标和并行策略不同。
- **Co-location / disaggregation**：共置保存 locality，解聚隔离 phase 却搬运 KV/state。
- **Static optimization / online control**：静态 plan 开销低，在线系统适应 drift 但增加控制复杂度。
- **Model-only / neuro-symbolic**：纯 LLM 灵活，符号验证提高可靠性但限制任务接口。

## 引用本概念的论文

- [[Prism-OSDI26]] — weights/KV 弹性共享与 10K+ GPU 部署。
- [[EcoServe-OSDI26]] — Ethernet 集群的部分解耦 serving。
- [[RollArt-OSDI26]] — 3000+ GPU agentic RL 调度。
- [[AEGIS-OSDI26]] — production LLM training SDC detection。
- [[NeuroSymbolicProof-OSDI26]] — LLM 与 theorem prover 联合验证。
- [[OpenTela-OSDI26]] — 跨 HPC 机构的开放 serving overlay。

## 已知局限 / 开放问题

- 系统指标与 model quality/convergence 常被分开评估，需要联合 benchmark。
- 模型、runtime、hardware 升级造成的 output drift 和性能 drift 缺少可组合契约。
- 更强模型不会自动消除 memory、network、fault 与 verification 问题，反而可能放大规模成本。
