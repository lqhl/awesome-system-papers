# Wiki Index

> 最后更新：2026-06-20（加入 GitHub / 在线 Wiki 链接）

本 wiki 是所有 LLM 生成的综合层，跨论文的实体、概念、比较、主题页都住在这里。Raw sources（`papers/` 和 `markdowns/`）不属于 wiki，它们是 wiki 的材料。

## 链接

- [GitHub 仓库](https://github.com/lqhl/awesome-system-papers) — 源码、PDF、MinerU 解析、agent skills
- [在线 Wiki](https://papers.lqhl.me) — Quartz 静态站点

## Conferences

- [[ATC-2025]] — 100 篇 | LLM serving 全面进入多模型多租户托管，国内 hyperscaler 生产论文密度爆发，SmartNIC/DPU/Tofino/PIM/CXL 异构硬件横贯主线，Rust framekernel + model checking 工程交付
- [[FAST-2026]] — 44 篇 | LLM 训练/推理存储栈占 ~20%，云厂商 production paper 浓度爆发（Apple/Alibaba/Huawei/Tencent/ByteDance），CXL 仿真器与 disaggregated I/O 成新工具链
- [[MLSys-2026]] — 136 篇 | KV/attention/speculative/serving 四线占 ~35%，MoE 成建制 + RAG 推理一等公民，AI4AI 与 Agent 系统并列扩张，可审计 ML 集群化
- [[OSDI-2025]] — 53 篇 | 形式验证与 silent-failure 可靠性居首，LLM 系统向「极值硬件 + 生产可靠性」两端分化，CXL/XPU/量子重写抽象层
- [[SOSP-2025]] — 66 篇 | LLM 全栈生产化(应用层抽象+训练可靠性),形式方法工程交付化,eBPF 密集成阵,CXL/SmartNIC/CHERI 在 OS 抽象层集中重写

## Entities

### Systems

- [[vLLM]] — UC Berkeley 高吞吐 LLM serving 框架，PagedAttention 起源
- [[SGLang]] — LMSYS 的 LLM serving 框架，RadixAttention + 结构化生成 DSL
- [[KTransformers]] — kvcache-ai CPU/GPU heterogeneous MoE inference engine，AMX expert execution + Expert Deferral
- [[DwarfStar]] — antirez/ds4，本地 DeepSeek V4 Flash / PRO 专用 inference engine，覆盖 SSD expert streaming 与 disk KV session
- [[DeepSpeed]] — Microsoft 分布式训练库，ZeRO / pipeline / UCP checkpointing 的生产集成栈
- [[Megatron]] — NVIDIA Megatron-LM/Core，TP/PP/EP 工业训练 runtime 与论文常见 baseline
- [[Mooncake]] — Moonshot KVCache-centric disaggregated serving，Transfer Engine + Store
- [[TensorRT-LLM]] — NVIDIA 生产 LLM inference 栈，论文常见工业 baseline

### Orgs / Labs

（待生成）

### Benchmarks

（待生成）

## Concepts

- [[Attention]] — Transformer 核心算子，O(N²) 复杂度是近 8 年系统工作的共同敌人
- [[Flash-Attention]] — IO-aware exact attention kernel，tiling + online softmax
- [[KV-Cache]] — LLM 推理的核心内存对象，过去三年 serving 论文的优化主线
- [[Prefix-Caching]] — 复用共享 prompt/context 前缀的 KV cache，降低重复 prefill
- [[RAG]] — 检索增强生成，从应用模式升级为端到端 serving pipeline 问题
- [[PagedAttention]] — 把 KV cache 当 OS 虚存分页管理（vLLM 引入）
- [[Continuous-Batching]] — iteration-level scheduling，LLM serving 事实标准
- [[Chunked-Prefill]] — 把长 prompt prefill 切片捎带 decode，平衡 TTFT/TBT
- [[Disaggregation]] — prefill / decode 拆到不同 GPU，配合 RDMA KV transfer
- [[Speculative-Decoding]] — 用 draft model 并行验证多 token，无 quality loss 加速
- [[MoE]] — Mixture of Experts，2024+ frontier LLM 事实架构，系统层痛点集中
- [[Expert-Parallelism]] — MoE 专用并行，AllToAll 重通信 + LB 敏感
- [[Tensor-Parallelism]] — 层内切权重 + 每层 AllReduce，跨机带宽门槛高
- [[Pipeline-Parallelism]] — 层间切 stage + micro-batch 流水，跨机主力
- [[Quantization]] — INT8/FP8/INT4/MXFP4，显存算力双收益
- [[LoRA]] — 低秩微调，推理零 overhead，多租户 serving 标配
- [[RDMA]] — AI 集群网络底座，IB/RoCEv2 + GPUDirect
- [[RadixAttention]] — radix tree 跨请求 KV 索引 + cache-aware scheduling（SGLang 引入）
- [[Sparse-Attention]] — 稀疏 attention 从妥协走向可选设计空间（NSA 等）
- [[LLM]] — 系统论文中的 workload 总称（serving / training / agent / codegen）
- [[LLM-Inference]] — 在线 serving 语境：prefill/decode、调度、KV、并行与 SLO 管理
- [[CXL]] — Compute Express Link 内存池化与机架级 disaggregation
- [[Data-Parallelism]] — DP / ZeRO / 梯度同步与弹性扩缩
- [[NVMe]] — NVMe SSD 接口与软件栈瓶颈
- [[F2FS]] — Flash-Friendly File System，移动/嵌入式主力 LFS
- [[eBPF]] — 内核可编程扩展面（SOSP/OSDI 密集议题）

## Comparisons

（按需手动触发生成）

## Themes

- [[AI-Infra]] — 18 篇 | MoE 效率 + KV Cache 复用与传输（CacheGen→CacheBlend→LMCache 三部曲）+ 跨厂商通信 + 长记忆 + KV 后处理与可编辑性 + MoE expert offloading / KV compression 新分支
- [[Auto-Research]] — 14 篇 | 从 2023 MLAgentBench toy task 到 2025 AlphaEvolve 56 年来首次改进 Strassen,再到 2026 AutoScientists 将 long-running multi-agent coordination 变成核心系统问题、BES 将自改进 LLM 采样推进到 bidirectional evolutionary search、AlphaProof Nexus 将 LLM+形式化验证推进到自主解决 9 个 Erdős 开放问题
- [[Finance]] — 5 篇 | formulaic alpha baseline → LLM agent + TS foundation model 两条自动化路径 → News Shock LLM 嵌入揭示最大资产定价异常（Sharpe 3.1）
- [[Foundation]] — 7 篇 | 架构奠基（Transformer 2017）→ attention kernel 基础设施（FlashAttention 2022/2024）→ LLM Serving 基础设施（vLLM/SOSP 2023 + SGLang）→ 开源 frontier（DeepSeek-V4 2026）

## Papers

`wiki/papers/` 下每篇论文一页，按系统/方法命名（如 `vLLM-SOSP23.md`、`fabric-lib-MLSys26.md`）。由于数量多（预计 500+），不在本 index 中逐篇列出，通过 theme / conference / entity / concept 页的反向链接到达。

当前已有：
- arXiv / AI-Infra 专题（11 篇）：[[Libra-ICLR26]]、[[AttnRes-arXiv26]]、[[MSA-arXiv26]]、[[LatencyOptimal-MoELB-INET4AI25]]、[[FluxMoE-arXiv26]]、[[MOE-INFINITY-arXiv24]]、[[ContextAwareMoE-CXLNDP-arXiv25]]、[[OD-MoE-arXiv25]]、[[CoX-MoE-DAC26]]、[[IceCache-arXiv26]]、[[MoE-nD-arXiv26]]
- Foundation 专题（7 篇）：[[Transformer-NeurIPS17]]、[[FlashAttention-NeurIPS22]]、[[FlashAttention-2-ICLR24]]、[[FlashAttention-3-NeurIPS24]]、[[vLLM-SOSP23]]、[[SGLang-NeurIPS24]]、[[DeepSeek-V4-arXiv26]]
- Auto-Research 专题（14 篇）：[[MLAgentBench-ICML24]]、[[OpenHands-ICLR25]]、[[AI-Scientist-arXiv24]]、[[MLE-Bench-ICLR25]]、[[AI-Scientist-v2-arXiv25]]、[[Auto-Research-arXiv25]]、[[MLR-Bench-arXiv25]]、[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[FunSearch-Nature24]]、[[AutoScientists-arXiv26]]、[[BES-arXiv26]]、[[AlphaProofNexus-arXiv26]]
- Finance 专题（5 篇）：[[101-Alphas-arXiv15]]、[[151-Trading-Strategies-SSRN18]]、[[TimesFM-Fin-arXiv24]]、[[RD-Agent-Quant-arXiv25]]、[[NewsShock-NBER26]]
- [[ATC-2025]]（100 篇）见会议综述页
- [[FAST-2026]]（44 篇）见会议综述页
- [[MLSys-2026]]（136 篇）见会议综述页
- [[OSDI-2025]]（53 篇）见会议综述页
- [[SOSP-2025]]（66 篇）见会议综述页

---

## 使用说明

- 所有内部链接用 Obsidian wikilink 格式 `[[PageName]]` 或 `[[PageName|显示文字]]`，不写路径，不加 `.md` 后缀
- 链接到 PDF 源文件时保留后缀：`[[sosp23-kwon-pagedattention.pdf]]`
- 本文件由 `wiki-survey`、`wiki-update` 等 skill 在生成新页面时追加条目；人工可以补充一句话描述
