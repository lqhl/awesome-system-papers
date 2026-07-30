---
type: paper
name: WaferLLM
full_title: "WaferLLM: Large Language Model Inference at Wafer Scale"
authors: [Congjie He, Yeqi Huang, Pei Mu, Ziming Miao, Jilong Xue, Lingxiao Ma, Fan Yang, Luo Mai]
venue: OSDI
year: 2025
tags: [llm-inference, wafer-scale, accelerator, gemm, distributed-memory]
source_pdf: "[[osdi25-he.pdf]]"
source_md: "[[osdi25-he]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# WaferLLM：晶圆级大型语言模型推理（OSDI 2025）

> **原题**：WaferLLM: Large Language Model Inference at Wafer Scale

> **一句话总结**：WaferLLM 针对 WSE-2 的 mesh NoC 设计 LLM mapping。GEMV microbenchmark 相对单 A100 为 **280–606×**，而 dense per-request E2E inference 相对 A100 SGLang cluster 为 **6–20×**；两者不可混为同一端到端结果。

## 问题与动机

LLM decode 受 **memory bandwidth** 限制；GPU HBM 带宽远不够单请求 TPOT。Wafer-scale（Cerebras WSE：85 万核、40GB on-chip、22PB/s 带宽）提供数量级带宽，但现有系统为 shared memory/全互连设计（[[vLLM]]、Ladder、T10），直接映射 mesh NoC 利用率极低。

## 关键观察 / 隐含假设

- **观察 1**：mesh 上远程访问延迟可达本地 **1000×**（hop+routing 受限），必须把通信模式约束在 PLMR 合规的 cyclic shift / K-tree allreduce 等。
  - **依赖假设**：单芯片可放下目标模型层或子集；权重分区细粒度可行。
  - **可能失效场景**：超大模型层无法片上分区时需 off-wafer，优势缩小。
- **观察 2**：decode 维度过小无法 partition，需 **fine-grained replication** + 低通信 GEMV 聚合。
  - **依赖假设**：MeshGEMV 的 K-tree 满足每核 ≤25 路由路径（WSE-2）。
  - **证据强度**：强——微基准 4–8× 于 Cerebras 优化 GEMV。
- **假设 3**：GPU 式 [[KV-Cache]] 拼接会导致 core 利用skew；**shift** 管理平衡 core 负载。
  - **证据强度**：中——比 PagedAttention 式方案可扩展性高 400×（论文 claim）。

## 核心方法

**PLMR**：Massive Parallelism、non-uniform Latency、per-core Memory、Routing 限制。

**Wafer-scale LLM parallelism**：prefill 细粒度 partition；decode replication。

**MeshGEMM**：cyclic shift + interleaving，满足 M/L/R。

**MeshGEMV**：K-tree allreduce 聚合局部 GEMV。

**KV-cache shift**：避免 concat 型不平衡。

~7k CSL + 2k Python；开源 MeshInfra/WaferLLM。

## 设计取舍

- **取舍 1**：深度绑定 Cerebras 编程模型，换极致单芯片吞吐。
- **取舍 2**：多卡 NVLink/RDMA 集群对比时，WaferLLM 优势随软件/模型限制而小于 GEMV 微基准。
- **边界条件**：当前 LLM 全模型 on-chip 仍受容量与软件成熟度限制。

## 实验与结果

**指标、基线与边界**：TPR/inference throughput、GEMV latency performance、maximum decode length、energy efficiency；WSE-2 WaferLLM vs SGLang A100 clusters/SUMMA/Cannon；dense per-request settings或指定 GEMV shapes（§7）。

- E2E TPR 相对 A100 SGLang clusters 为 **6–20×**；single A100 约 **30–40×**，best multi-GPU SGLang **10–20×**（§7.1、§7.5）。CodeLLaMA-34B/QWen2-72B 为 subset layers 按比例缩放。
- MeshGEMV 两种 shapes 中相对 single A100 为 **280–606×** latency performance、**7.5–16×** energy；相对 best cluster为 **166–210×/45–70×**（§7.5，Table6）。
- LLaMA3-8B maximum decode length **137,548 vs382**（360×）；LLaMA2-13B **6,168 vs16**（385×），指标为 length 而非 token/s（§7.4，Table5）。
- MeshGEMM 大规模仍大于 **70%** compute efficiency，SUMMA/Cannon在720×720 cores少于50%；大矩阵 cycles约少 **17%**（§7.2，Fig.9）。

## 论断—证据表

| 论断 | 证据 | 指标 / 基线 / 评测边界 | 定位 | 置信度 |
|---|---|---|---|---|
| E2E 加速受模型/cluster配置限制 | 6–20×；30–40× single、10–20× best multi-GPU | dense per-request、SGLang A100；subset-layer scaling for 34B/72B | §7.1，§7.5 | high |
| GEMV 巨大倍数是 microbenchmark | 280–606×、7.5–16× energy | two matrix shapes；vs A100/cluster cuBLAS | §7.5，Table6 | high |
| shift KV 改善可生成长度 | 360×/385× | WSE-2 capacity，vs concat/PagedAttention；非 token/s | §7.4，Table5 | high |
| MeshGEMM 结果是 GEMM microbenchmark | >70%、<50%、~17% cycles | WSE core/matrix scales；vs SUMMA/Cannon | §7.2，Fig.9 | high |
| E2E 能效有硬件尺度边界 | 2–2.5× | best SGLang multi-GPU、dense LLaMA/WSE2 | §7.5，Tables7–8 | high |

## 批判性分析

### 论证链条

decode bandwidth bound → wafer 带宽优势 → PLMR 约束算法 → MeshGEMM/V + shift → 大幅 E2E 提升。链条在 WSE-2 实测闭合；迁移 Dojo/其他 mesh 需重调 R/M。

### 假设压力测试

- 超大 MoE、长 context 可能逼离片，PLMR 优势下降。
- 与 [[Disaggregation]] prefill/decode 分离架构的竞争未充分对比。
- 云侧 wafer 实例成本模型论文简略（tokens/$ 有产业引用但非本文重点）。

### 实验可信度

硬件实测强；对比 vLLM/SGLang 多卡需看清网络与 batch 配置。单层/子集层评测外推全模型需谨慎。

### 系统性缺陷

论文未讨论：多租户 serving、故障域、与标准 PyTorch 生态运维差距。

## 局限与后续工作

- **局限 1**：平台与工具链专用性强。
- **局限 2**：GEMV→全模型收益被软件/模型设计稀释。
- **Future work 1**：更大 HBM attach（TSMC SoW）混合 tier。
- **Future work 2**：与 [[Continuous-Batching]]/[[Speculative-Decoding]] serving 策略协同。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Tensor-Parallelism]]、Mesh NoC
- **同类系统**：[[vLLM]]、[[SGLang]]、Cerebras stack、T10、Ladder
- **同会议**：[[OSDI-2025]]
