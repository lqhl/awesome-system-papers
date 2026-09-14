---
type: paper
name: BatchGen
full_title: "BatchGen: An Architecture for Scalable and Efficient Batch Inference"
authors: [Tairan Xu, Leyang Xue, Zhan Lu, Jinfu Deng, Hongyang Xiao, Yinsicheng Jiang, Congjie He, Matej Sandor, Le Xu, Luo Mai]
venue: OSDI
year: 2026
tags: [batch-inference, moe, coroutine-scheduling, gpu-utilization, kv-cache, offloading]
source_pdf: "[[osdi26-xu-tairan.pdf]]"
source_md: "[[osdi26-xu-tairan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-01-15
---

# 面向可扩展高效批量推理的 BatchGen（OSDI 2026）

> **原题**：BatchGen: An Architecture for Scalable and Efficient Batch Inference

> **一句话总结**：现有推理引擎把序列固定在 GPU 和原子化 forward pass 中，无法应对 MoE 专家批次过小与生成长度长尾；BatchGen 将序列表示为可暂停、合并、拆分、迁移的协程，在 128 GPU 上把批量完成时间最多降低 2.3×，在 24 GB A5000 上相对最强 offloading 基线最多快 9.6×。

## 问题与动机

批量推理的目标是批量完成时间（BCT），而非交互服务的 TTFT 或 TPOT。离线推理、test-time scaling 和 RL rollout 往往包含数千至数百万条序列，并且只有全部序列完成后结果才可用。随着 MoE 模型扩大，单个 token 只激活少数专家；即使全局批次很大，每个专家收到的 token 仍可能不足以填满 GPU。推理阶段的输出长度又呈现长尾，少数序列会成为批次的 straggler。

vLLM、SGLang 和 TensorRT-LLM 等系统主要沿用交互式服务的执行模型：序列及其 KV cache 绑定到固定设备，forward pass 原子执行。因而它们不能在 attention 与 MoE 之间暂停序列、不能动态积累更大的专家批次，也不能在批次末尾把剩余长序列拆到空闲 GPU 上。

## 关键观察 / 隐含假设

- **观察 1：MoE 稀疏性造成序列内部负载不均衡。** 不同 token 选择的专家不同，导致专家层的有效批次远小于全局批次；图 2b 显示现有系统在大批量下仍可能损失约 50% GPU 利用率。
  - **依赖假设**：模型包含具有不同饱和批次大小的模块，尤其是 attention 与 MoE。
  - **可能失效场景**：稠密模型或专家层通信主导时，拆分后增加的状态保存与调度开销可能无法被吞吐收益抵消。
- **观察 2：test-time scaling 产生决定 BCT 的输出长尾。** DeepSeek-R1 生产 trace 中，P99 输出长度是 P95 的 3.78×，最大值是 P95 的 9.2×；现有引擎因此损失约 10%–70% 的可达 GPU 性能（§2.2，图 2c）。
  - **依赖假设**：批量目标允许牺牲单序列延迟，并且序列状态可在 host memory 与 GPU 间迁移。
  - **可能失效场景**：严格交互 SLO、PCIe 带宽不足、host memory 不够，或迁移期间要求强隔离的多租户部署。
- **假设 1：模块边界是安全且足够有收益的 yield 点。** 论文在 transformer MoE 上以 attention/MoE 边界为主要切分位置；这是由模块化模型结构和可保存的 hidden state、KV cache 支撑的，证据强度为强。
- **假设 2：额外调度延迟可由批量执行摊销。** 论文报告每 64 个 decode token 的跨节点同步耗时 5–10 ms，仅占计算时间约 0.1%–0.2%（§5.5）；该比例依赖分钟级 BCT，而非低延迟请求。

## 核心方法

BatchGen 提出 event-driven sequence coroutine architecture。每条序列携带能决定后续执行的状态，包括 KV cache、当前 hidden state、输入输出进度和元数据。模型模块经 wrapper 改造，在运行时生成 coroutine step；协程暂停后进入全局队列，由调度器把它派发到共享 GPU 池，而不是永久绑定某个设备。

四个原语分别对应四类调度动作。`YIELD` 在模块边界保存状态并释放 GPU；`COMBINE` 拼接多个序列的中间 tensor，形成更大的 MoE batch；`PARTITION` 用 tensor parallelism 加速单个长序列，或用 data parallelism 处理多个 straggler；`MIGRATE` 在设备、节点或 host memory 间异步迁移序列状态。它们把序列的执行流从固定任务变成可重组的 DAG。

系统采用分层 yield 策略：attention 后暂停并合并序列，以提高专家批次；forward pass 之间根据内存和负载动态暂停、补入新序列。prefill 通过异步把 KV cache 写入 host memory，decode 使用分页 KV cache 和两页预留策略，只有在需要时扩展。内存布局将 host memory 作为节点级状态源，并用 transient buffer 预取参数和恢复 KV cache。

调度计划由模块级 profiling、roofline 风格性能模型和单层 DAG 模拟自动搜索。候选配置包括 attention/MoE 批次大小及 buffer 容量；以 DAG critical path 最短为目标选取计划（§5.4）。该策略把静态模型特征与运行时长尾管理结合起来。

## 设计取舍

- **吞吐换响应性**：暂停、checkpoint、迁移和合并提高 BCT 吞吐，但会增加单序列等待和调度复杂度，不适合严格交互式服务。
- **host memory 与 PCIe 带宽换 GPU 容量**：offloading 能形成更大专家批次，却使系统可能转为 PCIe-bandwidth-bound；decode 阶段 transfer 难以完全隐藏。
- **切分粒度换内存开销**：每专家一个协程并发度最高但会保存过多状态；BatchGen 主要选择 attention/MoE 分界，牺牲部分细粒度换可部署性。
- **动态并行换重配置成本**：`PARTITION` 可利用空闲 GPU，但需要等待协程 yield，且论文报告其本身可能耗时数秒。

## 实验与结果

- LongBench、6K 序列、16×H20 或 8×H200 上，BatchGen 相对 SGLang-Optimized 提升 1.25–1.66×；8K input/2K output 的 prefill-heavy 负载在 H20 上收益更大（§6.1，表 3）。
- 8×H20 上 DeepSeek-R1 的 batch size 从基线的 8–16 提升到 1800+，速度提升 1.31–1.85×；Kimi-K2 超出全部基线 HBM 容量，只有 BatchGen 完成执行（表 3）。
- RSA test-time scaling 在 16×H20 上，30 分钟 SLO 下完成序列数提升 1.25–1.57×，60 分钟 SLO 下提升 1.66–1.75×（§6.2，表 4）。
- VeRL 的 DeepSeek-R1 RL rollout 中，`PARTITION` 配合 FP8 decoding 将每轮时间降低 5%–10%；长尾序列占剩余 rollout 时间的 30%–80%（§6.3，表 5）。
- 128×H20、10K 请求上，BatchGen 相对 SGLang-Optimized 在 12K/4K 负载提升 1.71–1.82×，在 6.5K/2.8K 负载提升 2.2–2.3×；超过 64 GPU 后受 MoE all-to-all 通信限制，系统改用两个 64-GPU 实例（§6.4）。
- 单张 24 GB A5000 上，面对 GSM8K 和 ChatBotArena，BatchGen 相对 offloading 基线最多快 9.6×；论文将差异归因于更大的专家批次及计算与参数传输重叠（§6.5，表 7）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 协程合并能缓解 MoE 专家批次过小 | 现有系统约 50% 利用率损失；BatchGen 在 LongBench 提升 1.25–1.66×（图 2b，表 3） | Mixtral、DeepSeek-R1、Kimi-K2；H20/H200 | 强 |
| 动态分区能缓解 decode 长尾 | RL rollout 时间降低 5%–10%，长尾占 30%–80% 剩余时间（§6.3，表 5） | 256 序列/轮、16×H20、DeepSeek-R1 | 中 |
| 协程架构可扩展到大 GPU 集群 | 128 GPU 上提升 2.2–2.3×（§6.4，表 5） | 64 GPU 单实例后改为实例复制；MoE 通信出现平台期 | 中 |
| offloading 能让受限显存设备执行超大 MoE | A5000 上最多 9.6×，部分基线无法完成（§6.5，表 7） | 单 GPU、1 TB host memory；CPU attention 优化仅用于该实验 | 强 |

## 批判性分析

### 论证链条

论文的链条在目标负载内基本闭合：MoE 和长尾造成利用率下降，模块级 yield 暴露出可合并的序列，host checkpoint 和动态 GPU 池支持重组，实验分别覆盖批次增大、长尾分区和多节点扩展。最强证据来自 MoE 批次和显存受限实验。论文把“架构适用于一般生成工作负载”推广到 vision-language 和跨模型 pipeline，但这些场景没有实测，属于设计推断。

### 假设压力测试

decode 阶段的最佳 MoE 批次可能需要 16384 个并发请求；论文承认生产长上下文场景通常达不到，只能 best-effort（§7）。host memory 成为统一状态源也引入容量、带宽和故障域约束。128 GPU 的收益不能直接外推到更大单实例，因为 all-to-all 通信已经使收益在 64 GPU 后趋于平台期。

### 实验可信度

实验覆盖四种 MoE 模型、离线推理、RSA、RL rollout 和单卡 offloading，并提供 SGLang kernel 替换实验来区分 runtime 与 kernel 收益。大规模对比中，SGLang 和 vLLM 超过 16 GPU 存在稳定性问题，作者用多个独立 16-GPU data-parallel group 聚合结果；这使比较具有工程现实性，但不等同于完整的统一集群调度对比。严格交互延迟、迁移失败、隔离和长期运维成本没有系统评估。

### 系统性缺陷

实现规模为 13K 行 C++ 加 49K 行 Python，并维护自有 kernel；这会增加模型适配和版本演进成本。`MIGRATE` 需阻塞任务队列以避免状态竞争，`PARTITION` 可能耗时数秒。论文说明了故障时在迁移与重算之间择优，但未报告故障注入下的 BCT、恢复尾延迟和跨租户公平性。

## 局限与后续工作

- **局限 1**：当前实现主要面向 transformer MoE；普通稠密模型、vision-language 模型和跨模型 pipeline 尚未验证。
- **局限 2**：decode 的收益受可获得并发序列数和 host memory 限制，无法保证达到专家饱和批次。
- **后续工作 1**：在真实生产 trace 上测量不同 PCIe、NVLink、RDMA 拓扑下 offloading 与迁移的 BCT/P99 交界点。
- **后续工作 2**：在严格 SLO、多租户和节点故障注入条件下，评估动态合并、迁移、分区对公平性、恢复时间和可观测性的影响。
- **后续工作 3**：将 yield 点搜索扩展到 vision-language 编码器和多模型 pipeline，并比较跨模型协程与现有 disaggregation 的通信成本。

## 相关

- **相关概念**：[[Mixture-of-Experts]]、[[KV-Cache]]、[[Continuous Batching]]、[[PagedAttention]]
- **同类系统**：[[vLLM]]、[[SGLang]]、[[TensorRT-LLM]]、[[FlexGen]]、[[MoE-Lightning]]、[[MegaScale-Infer]]
- **同会议**：[[OSDI-2026]]
