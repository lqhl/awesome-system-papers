---
type: paper
name: Bidaw
full_title: "Bidaw: Enhancing Key-Value Caching for Interactive LLM Serving via Bidirectional Computation–Storage Awareness"
authors: [Shipeng Hu, Guangyan Zhang, Yuqi Zhou, Yaya Wei, Ziyan Zhong, Jike Chen]
venue: FAST
year: 2026
tags: [llm-serving, kv-cache, two-tier-storage, scheduling, eviction]
source_pdf: "[[fast2026-hu-shipeng.pdf]]"
source_md: "[[fast2026-hu-shipeng]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Bidaw：通过双向计算-存储感知增强交互式 LLM 服务的键值缓存（FAST 2026）

> **原题**：Bidaw: Enhancing Key-Value Caching for Interactive LLM Serving via Bidirectional Computation–Storage Awareness

> **一句话总结**：在交互式多轮对话 workload 上观察到 [[KV-Cache]] 时间局部性极差（80% weighted reuse distance 超 200 GB 性能层）且 I/O 延迟变异系数 >90%，Bidaw 让 [[vLLM]] 推理引擎与 host memory + SSD 两层存储双向感知——dual queue + disk-HRRN 调度防 I/O 阻塞、上轮答案长度预测驱逐提升命中率——相比 CachedAttention/FlashGen 延迟降最多 3.58×、吞吐升 1.83×，逼近全量 host memory 理想上界。

## 问题与动机

交互式 LLM 服务（虚拟陪伴、Duolingo 角色扮演、客服等）要求人机交替、低延迟响应。每轮推理需加载该用户全部历史 [[KV-Cache]] 以保证上下文连贯；GPU 显存有限，历史 KV 通常被驱逐后只能重算。作者从中国电信百万轮真实 trace（interactive conversation workload）测得：平均每用户 **22.4** 轮对话，历史 KV 回填占 **93.1%** 计算量。

本地部署场景（隐私、成本约束）普遍采用 **两层存储**：性能层（host memory，通常 1.6–3.2× GPU 显存）+ 容量层（SSD，几 GB/s 带宽）。CachedAttention 与 FlashGen 是当前 SOTA，但作者在 OPT-13B + 200 GB host memory + 1.5 GB/s SSD 上复现发现，相比「全部 KV 命中性能层」的理想方案，端到端响应延迟最高 **3.8×**、吞吐低 **2.0×**——KV 加载已成为系统瓶颈，而非 GPU 算力。

根因是 **计算引擎与两层存储互不感知**：

1. **调度侧**：引擎按 FCFS 调度，不知道各请求 KV 所在层与大小；一个慢的容量层 I/O 会阻塞后续仅需性能层 I/O 的请求（I/O-induced request blocking）。
2. **存储侧**：驱逐策略只看自身访问历史（queue-enhanced / LRU / FIFO），但交互式对话中用户阅读思考导致请求间歇到达，KV 访问时间局部性极差，性能层命中率仅 ~20%。

Bidaw 的目标是在 **无损**（不改变模型输出）前提下，通过 compute↔storage 双向感知，把两层 KV 缓存的加载效率拉近全 host memory 理想上界。

## 关键观察 / 隐含假设

- **观察 1**：交互式对话中 KV 长期驻留、并发缓存体量迅速超过性能层容量。
  - **证据**：用户对话时长 CDF 长尾明显；平均 22.4 轮/用户；随到达率上升，OPT-13B 并发 KV 可达性能层（200 GB）的 **3.91×**。
  - **依赖假设**：用户断连前 KV 不删除；单卡 A800 可承载的到达率范围内测量（避免算力瓶颈掩盖 I/O 问题）。
  - **可能失效场景**：短会话、burst 式批量提交（非交互）、或 [[Mooncake]] 类超长上下文 workload（平均 query 12k tokens）时，容量压力形态不同。

- **观察 2**：KV 访问 **时间局部性极差**——weighted reuse distance（两次访问间其他唯一 KV 的累计大小）很大。
  - **证据**：OPT-13B、30 users/min 下，**80%** 访问的 weighted reuse distance 超过 200 GB 性能层容量（Figure 6a）。
  - **依赖假设**：用户读完模型回答后才发下一轮；多用户并发交错访问。
  - **可能失效场景**：ShareGPT 等公开 trace 用 Poisson 合成时间戳时，人类阅读间隔信号消失，驱逐策略增益大幅缩水（论文实测吞吐仅 +1.40× vs 自家 workload 的 1.83×）。

- **观察 3**：请求间 KV 加载时间变异极大（变异系数 **>90%**），即使 5 s 内连续到达的请求亦然。
  - **证据**：两层带宽差距（host memory vs 1.5 GB/s SSD）叠加历史长度差异导致 Key/Value 尺寸分布宽（Figure 8）。
  - **依赖假设**：容量层 I/O 在关键路径上（数百 ms），且 layer-wise overlap 无效（首层计算仅数十 ms）。
  - **可能失效场景**：NVMe/[[RDMA]] 池化内存作容量层、或 [[Disaggregation]] 架构把 KV 放远端高速 fabric 时，dual queue 分离的收益可能缩小。

- **观察 4**：上一轮模型回答长度与下一次 KV 访问的 weighted reuse distance **下界**强正相关（Spearman **0.94–0.98**）。
  - **依赖假设**：人类在环——长回答需要更多阅读/思考时间，期间其他用户请求插入。
  - **证据强度**：**强**——12 组不同时间段/到达率 trace 一致；但这是对 **下界** 的相关性，完整 reuse distance 分布仍需 ghost cache 估计。
  - **可能失效场景**：语音实时对话、多模态即时反馈、或 assistant 主动追问（无长阅读间隔）时相关性可能减弱。

- **假设 1**：MHA 模型可缓存 normalized activation（tensor 6）再在低优先级 CUDA stream 转回 KV，cost efficiency（saved compute / storage）高于直接缓存 KV（51.0 vs 30.5）。
  - **证据强度**：**中**——OPT-13B 单模型分析 + ablation 贡献 1.10× 吞吐；GQA 模型 KV 已够小，论文明确不适用。
  - **可能失效场景**：GPU SM 利用率已高、或转换与主推理争用内存带宽时，低优先级 stream 收益不确定。

## 核心方法

Bidaw 基于 [[vLLM]] 实现，保留 [[Continuous-Batching]] 与 inclusive caching（性能层与容量层双份，换快速驱逐）。核心是三组机制，分别回应上述观察：

### I/O-aware request scheduling（回应观察 3）

- **Dual queue**：KV 已在性能层 → ready queue（可立即调度 GPU）；在容量层 → preparing queue（后台预取至性能层后再晋升）。
- **Ready queue**：FCFS，但晋升时按 **原始到达时间** 插入（非晋升时间），减轻尾延迟；GPU 内存不足时跳过 oversized 请求（同 FlashGen）。
- **Preparing queue**：自定义 **disk-HRRN**——`response ratio = 1 + waiting_time / KV_size`，优先发起小 KV 的容量层读，同时等待时间累积防止大 KV 饿死。

这样慢容量层 I/O 不再阻塞仅需性能层 I/O 的请求（Figure 11 示例：FCFS 先服务 request 1 导致 GPU 空闲，Bidaw 先算 request 3–5）。

### Previous-answer-based eviction（回应观察 2、4）

驱逐目标：最大化性能层命中率。流程：

1. 用上轮答案长度估计下次访问 weighted reuse distance 的 **下界**，裁剪不可能桶。
2. 维护后台 **ghost cache** 跑 Belady 最优策略，对过去 trace 统计各 fine-grained reuse distance 桶的 hit rate（promising vs extreme 区间）。
3. 结合用户历史访问分布与各桶 hit potential，算 overall hit potential（式 2），驱逐 potential 最低的用户 KV 至容量层。

关键洞察：即使 reuse distance 超过性能层容量，Belady 仍能在「promising」区间保持非零命中率；queue-enhanced 因在线等待队列通常 <50 请求，信号太弱。

### Storage-efficient tensor caching（回应观察 1 的容量压力）

对 MHA 模型（Llama、Qwen、OPT 等），缓存 **normalized activation** 而非 KV，加载后在空闲 SM（论文观测 >30% 空闲）上用低优先级 CUDA stream 转回 KV。配合 **mix-grained [[PagedAttention]]** 分配（历史/query 用 256-token big block，response 用 16-token small block）提升 CPU-GPU 传输带宽利用率。

## 设计取舍

- **取舍 1：双向感知 vs 实现复杂度**。引擎需感知每层 KV 位置与大小，存储需接收模型答案元数据；相比 CachedAttention/FlashGen 的「各管各」，Bidaw 增加调度器（均 0.62 ms/次）与驱逐管理器（0.35 ms/次），但相对数百 ms–数 s 的端到端延迟可忽略。
- 取舍 2：inclusive caching vs 空间效率。性能层与容量层双份拷贝换 O(1) 驱逐（同 FlashGen），写流量不在关键路径但 总存储 footprint 近似翻倍——与 tensor 6 缓存的空间节省形成对冲。
- **取舍 3：人类行为信号 vs 泛化性**。答案长度驱动的驱逐在真实交互 trace 上极强，但对无真实时间戳的 ShareGPT（Poisson 合成）几乎失效；论文诚实报告公开 workload 增益缩水。
- **取舍 4：无损 vs 压缩路线**。明确不采用 H2O/Impress 等 lossy KV 裁剪（长上下文精度下降、回答变长反而增延迟），与量化/稀疏 KV 正交。
- **边界条件**：单卡本地部署、SSD 带宽 1.5 GB/s（RAID-5 四盘）、PCIe 4.0；GQA 模型跳过 tensor 优化；依赖用户级会话状态（非跨用户 prompt 共享如 MeanCache）。

## 实验与结果

**环境**：单 A800 80GB、200 GB host memory、1.5 GB/s SSD、PCIe Gen4。模型 OPT-6.7B/13B/30B、Qwen-7B/14B。Baselines：[[vLLM]]（全重算）、自实现 CachedAttention/FlashGen、模拟全性能层理想上界。

- **端到端延迟**：OPT-13B 上 Bidaw 比 SOTA 延迟最高降 **3.58×**；跨模型平均降 **83.9%**；在相近延迟下吞吐高 **1.43–1.83×**。
- **容量敏感性**：host memory 从 120 GB 到 200 GB，Bidaw 仍比 SOTA 支持 **1.75–2.19×** 到达率。
- **命中率**：previous-answer 驱逐比 queue-enhanced miss rate 降 **57.6%**，比 LRU/FIFO 降 **69.9%**。
- **排队时间**：I/O-aware 调度均 2.45 s vs FCFS 5.76 s（**-57.5%**）。
- **尾延迟**（OPT-30B）：P99 比 CachedAttention/FlashGen 降 **47.0%/56.8%**。
- **Ablation**（OPT-30B）：仅调度 **1.58×**；+驱逐再 **1.25×** 吞吐；+tensor 缓存再 **1.10×**。
- **5 GB/s SSD 模拟**：FlashGen 15.18→20.23 users/min，Bidaw 27.81→30.35 users/min，I/O 瓶颈未消除时 Bidaw 仍领先。
- **ShareGPT**：吞吐 +1.40×（低于自家 workload），延迟仍降 56.9–69.8%。
- **开销**：调度 0.62 ms、驱逐 0.35 ms、KV 转换数十 ms，均相对端到端延迟可忽略。

## 批判性分析

### 论证链条

观察（交互式 KV 局部性差 + I/O 延迟高方差 + 并发 KV 超性能层）→ 根因（compute/storage 互不感知）→ 双向机制（dual queue 调度 + 答案长度驱逐 + 空间高效张量）→ 命中率与排队时间改善 → 端到端延迟/吞吐逼近理想上界。链条在 **单卡、本地 SSD、真实交互时间戳、MHA 模型** 设定下闭合较好；ablation 逐步叠加三项技术，支持因果归因。

薄弱跳步：(1) CachedAttention/FlashGen 为基于 vLLM 的重实现，非作者原版闭源系统，可能存在实现差距；(2) 「逼近理想上界」多在特定到达率点比较，未给出全曲线距离上界的定量 gap；(3) ghost cache 的 Belady 统计依赖过去 trace 窗口，冷启动与 workload 漂移时的收敛未讨论。

### 假设压力测试

- **非交互式 serving**：批量 API、代码补全等无「阅读间隔」场景，previous-answer 驱逐退化为 ghost cache + 历史分布，增益可能接近更精细的 LRU 变体——ShareGPT + Poisson 时间戳已部分验证此风险。
- **高速容量层**：若容量层升级为 [[RDMA]] 池化内存（[[Mooncake]]）或 CXL 扩展内存，容量层与性能层带宽差距缩小，dual queue 分离与 disk-HRRN 的价值下降；论文刻意聚焦「低成本本地 SSD」 niche，未与 Mooncake 端到端对比。
- **多卡 / 分布式**：实验仅单 GPU；高到达率下算力、PCIe、SSD 可能同时成为瓶颈，调度与驱逐的 global 视角未扩展。
- **GQA / 超大模型**：tensor 6 优化不适用 GQA；OPT-30B 等大模型 KV 加载与计算成本更高，FlashGen 的 selective re-computation 行为使 baseline 对比更复杂，读者需结合模型规模解读。
- **答案长度 ↔ reuse distance**：相关性针对 **下界** 而非点估计；极端 outlier（IQR 剔除后）仍可能存在，prob 分布归一化对桶划分敏感——论文未 ablate 桶粒度 $m$。

### 实验可信度

- **Benchmark 代表性**：百万轮中国电信交互 trace 对「虚拟陪伴/客服」类场景代表性强，优于仅 5.7 轮均值的 ShareGPT；但 query/response 均较短（36/45 tokens），与 Mooncake 超长上下文不同 niche。
- **Baseline 公平性**：同基于 vLLM、同 inclusive caching、同 continuous batching，较公平；vLLM 无缓存作为下界合理。FlashGen 在 OPT-30B 上因部分重算略慢于 CachedAttention，说明 baseline 行为已被仔细复现。
- **Ablation**：三项技术逐步叠加（Figure 21），支撑设计分解；缺少单独「仅驱逐 / 仅 tensor 缓存」的交叉消融。
- **Metrics**：覆盖均值延迟、吞吐、P90/P95/P99、miss rate、排队时间、开销；**未测** 驱逐期间 foreground 延迟抖动、SSD 写放大寿命、多租户公平性、故障恢复（host memory 丢数据后 inclusive 副本一致性）。

### 系统性缺陷

- **存储双倍开销**：inclusive caching 使 SSD 容量需求近似翻倍，论文未量化长期存储成本与 RAID 可靠性对生产的影响。
- **Ghost cache 运维**：需维护过去 I/O trace 窗口与桶统计，workload 分布突变（促销、新功能）时 hit potential 可能滞后——论文未讨论在线自适应刷新策略。
- **单点 GPU**：无请求路由、无跨节点 KV 迁移；与 [[Disaggregation]] prefill/decode 分离架构的集成未涉及。
- **可观测性**：未描述如何监控 preparing queue 深度、驱逐命中率 per-bucket、tensor 转换 stream 争用。
- **正确性**：调度重排不影响单请求内 token 生成顺序，无损 claim 成立；但 waiting request 不被驱逐的语义在极高并发下是否与 inclusive 副本同步，论文仅一句带过。

## 局限与后续工作

- **局限 1**：驱逐策略强依赖交互式对话中「人类阅读间隔」与答案长度的相关性；对合成时间戳或无用户思考间隔的 workload 增益显著下降（ShareGPT 已验证）。
- **局限 2**：storage-efficient tensor 缓存仅适用于 MHA；GQA、[[MoE]] 等结构需另选中间张量，论文未展开。
- **局限 3**：单卡本地部署，未评估多 GPU tensor parallel 下 KV 分片与两层存储的交互；未与 [[RDMA]] 内存池方案比性价比。
- **局限 4**：inclusive 双份存储的容量与写放大成本未量化；ghost cache 冷启动与 trace 过期策略未定义。
- **Future work 1**：在真实时间戳的公开多轮 trace（或自行采集）上测量答案长度信号的衰减条件，设计不依赖人类行为的 fallback 驱逐（如结合 [[Prefix-Caching]] 语义）。
- **Future work 2**：将 dual queue 调度与 [[Disaggregation]]、[[Chunked-Prefill]] 结合，测量容量层为 CXL/NVMe 时机制是否仍必要。
- **Future work 3**：评估 exclusive caching + 异步写回能否在保持命中率前提下减半 SSD footprint，并测 SSD 耐久与 tail latency 权衡。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Prefix-Caching]]、[[Disaggregation]]、Belady 最优替换、HRRN 调度
- **同类系统**：[[vLLM]]、CachedAttention、FlashGen、[[HCache]]、[[Mooncake]]、MeanCache
- **同会议**：[[FAST-2026]]
- **对比**：Bidaw 相对 CachedAttention/FlashGen 用引擎↔存储双向感知换实现复杂度；相对 [[Mooncake]] 走低成本本地 SSD 而非 RDMA 池化；相对 H2O/Impress 坚持无损 KV
