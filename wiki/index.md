# Wiki 索引

> 最后更新：2026-08-17

本 wiki 是所有 LLM 生成的综合层，跨论文的实体、概念、比较、主题页都住在这里。Raw sources（`papers/` 和 `markdowns/`）不属于 wiki，它们是 wiki 的材料。

## 链接

- [GitHub 仓库](https://github.com/lqhl/awesome-system-papers) — 源码、PDF、MinerU 解析、agent skills
- [在线 Wiki](https://papers.lqhl.me) — Quartz 静态站点

## 会议综述

- [[FAST-2026]] — 44 篇 | LLM 训练/推理存储栈占约 20%，云厂商 production paper 浓度爆发（Apple/Alibaba/Huawei/Tencent/ByteDance），CXL 仿真器与 disaggregated I/O 成新工具链
- [[MLSys-2026]] — 135 篇 | KV/attention/speculative/serving 四线占约 35%，MoE 成建制 + RAG 推理一等公民，AI4AI 与 Agent 系统并列扩张，可审计 ML 集群化
- [[OSDI-2026]] — 136 篇 | 17 类全文重读：AI 系统、解聚内存、异构硬件与生产可靠性并行推进，细粒度控制、跨层协同和明确证据边界成为共同方法
- [[ATC-2025]] — 100 篇 | LLM serving 全面进入多模型多租户托管，国内 hyperscaler 生产论文密度爆发，SmartNIC/DPU/Tofino/PIM/CXL 异构硬件横贯主线，Rust framekernel + model checking 工程交付
- [[OSDI-2025]] — 53 篇 | 形式验证与 silent-failure 可靠性居首，LLM 系统向「极值硬件 + 生产可靠性」两端分化，CXL/XPU/量子重写抽象层
- [[SOSP-2025]] — 66 篇 | LLM 全栈生产化(应用层抽象+训练可靠性),形式方法工程交付化,eBPF 密集成阵,CXL/SmartNIC/CHERI 在 OS 抽象层集中重写

## 实体

### 系统

- [[vLLM]] — UC Berkeley 高吞吐 LLM serving 框架，PagedAttention 起源
- [[SGLang]] — LMSYS 的 LLM serving 框架，RadixAttention + 结构化生成 DSL
- [[KTransformers]] — kvcache-ai CPU/GPU 异构 MoE 推理引擎，AMX Expert 执行 + Expert Deferral
- [[DwarfStar]] — antirez/ds4，本地 DeepSeek V4 Flash / PRO 专用 inference engine，覆盖 SSD expert streaming 与 disk KV session
- [[DeepSpeed]] — Microsoft 分布式训练库，ZeRO / pipeline / UCP checkpointing 的生产集成栈
- [[Megatron]] — NVIDIA Megatron-LM/Core，TP/PP/EP 工业训练 runtime 与论文常见 baseline
- [[Mooncake]] — Moonshot KVCache-centric disaggregated serving，Transfer Engine + Store
- [[TensorRT-LLM]] — NVIDIA 生产 LLM inference 栈，论文常见工业 baseline

### 组织/实验室

（待生成）

### 基准

（待生成）

## 概念

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

## 对比

（按需手动触发生成）

## 主题

- [[AI-Infra]] — 27 篇 | MoE/KV/稀疏注意力扩展到 CPU-GPU 异构 serving、离线重排、跨区域资源和 agent/RL 系统基础设施
- [[Auto-Research]] — 33 篇 | 用目标自主性、长程持续、验证对象、知识新颖性和人工关口五条正交轴重审自动科研；区分性能优化、硬验证与科学发现，并将 GEPA 定位为短程工程优化 + 自动评估器驱动
- [[Finance]] — 6 篇 | formulaic alpha baseline → LLM agent + TS foundation model 自动化 → News Shock 文本异常 → UPSA 高维 nonlinear portfolio shrinkage
- [[Foundation]] — 7 篇 | 架构奠基（Transformer 2017）→ attention kernel 基础设施（FlashAttention 2022/2024）→ LLM Serving 基础设施（vLLM/SOSP 2023 + SGLang）→ 开源 frontier（DeepSeek-V4 2026）
- [[Operating-Systems]] — 9 篇 | OS service、内存分配、firmware/eBPF 隔离、CXL microkernel、serverless 与 managed runtime
- [[Storage-Systems]] — 8 篇 | DNA storage、云块索引、生成式文件系统、AI storage 与 RNIC-managed disaggregated memory

## 论文

`wiki/papers/` 下每篇论文一页，按系统/方法命名（如 `vLLM-SOSP23.md`、`fabric-lib-MLSys26.md`）。由于数量多（预计 500+），不在本 index 中逐篇列出，通过 theme / conference / entity / concept 页的反向链接到达。

当前已有：
- arXiv / AI-Infra 专题（11 篇）：[[Libra-ICLR26]]、[[AttnRes-arXiv26]]、[[MSA-arXiv26]]、[[LatencyOptimal-MoELB-INET4AI25]]、[[FluxMoE-arXiv26]]、[[MOE-INFINITY-arXiv24]]、[[ContextAwareMoE-CXLNDP-arXiv25]]、[[OD-MoE-arXiv25]]、[[CoX-MoE-DAC26]]、[[IceCache-arXiv26]]、[[MoE-nD-arXiv26]]
- Foundation 专题（7 篇）：[[Transformer-NeurIPS17]]、[[FlashAttention-NeurIPS22]]、[[FlashAttention-2-ICLR24]]、[[FlashAttention-3-NeurIPS24]]、[[vLLM-SOSP23]]、[[SGLang-NeurIPS24]]、[[DeepSeek-V4-arXiv26]]
- Auto-Research 专题（33 篇）：[[MLAgentBench-ICML24]]、[[OpenHands-ICLR25]]、[[AI-Scientist-arXiv24]]、[[MLE-Bench-ICLR25]]、[[AI-Scientist-v2-arXiv25]]、[[Auto-Research-arXiv25]]、[[MLR-Bench-arXiv25]]、[[AlphaEvolve-arXiv25]]、[[ASI-ARCH-arXiv25]]、[[Kosmos-AI-Scientist-arXiv25]]、[[FunSearch-Nature24]]、[[AutoScientists-arXiv26]]、[[BES-arXiv26]]、[[GEPA-ICLR26]]、[[AlphaProofNexus-arXiv26]]、[[AstaBench-ICLR26]]、[[DeepScientist-ICLR26]]、[[InnovatorBench-ICLR26]]、[[RE-Bench-ICML25]]、[[Co-Scientist-Nature26]]、[[SR-Scientist-ICLR26]]、[[HeurekaBench-ICLR26]]、[[DDR-Bench-ICML26]]、[[PaperBench-ICML25]]、[[CausalGame-ICML26]]、[[Robin-Nature26]]、[[MetaMuse-ICLR26]]、[[CausalEvolve-ICLR26]]、[[ICL-EF-ICML26]]、[[ResearchClawBench-arXiv26]]、[[Li-LongHorizonResearchEvaluation-arXiv26]]、[[EviGraph-arXiv26]]、[[OmniScientist-arXiv26]]
- Finance 专题（6 篇）：[[101-Alphas-arXiv15]]、[[151-Trading-Strategies-SSRN18]]、[[TimesFM-Fin-arXiv24]]、[[RD-Agent-Quant-arXiv25]]、[[NewsShock-NBER26]]、[[UPSA-NBER23]]
- [[ATC-2025]]（100 篇）见会议综述页
- [[FAST-2026]]（44 篇）见会议综述页
- [[MLSys-2026]]（135 篇）见会议综述页
- [[OSDI-2026]]（136 篇）见会议综述页
- [[OSDI-2025]]（53 篇）见会议综述页
- [[SOSP-2025]]（66 篇）见会议综述页

---

## 使用说明

- 所有内部链接用 Obsidian wikilink 格式 `[[PageName]]` 或 `[[PageName|显示文字]]`，不写路径，不加 `.md` 后缀
- 链接到 PDF 源文件时保留后缀：`[[sosp23-kwon-pagedattention.pdf]]`
- 本文件由 `wiki-survey`、`wiki-update` 等 skill 在生成新页面时追加条目；人工可以补充一句话描述
