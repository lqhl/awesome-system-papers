---
type: paper
name: StriaTrace
full_title: StriaTrace: Efficient Tracing and Diagnosis for Online LLM Inference (Operational Systems)
authors: [Haonan Wu, Yanqing Chen, Kun Qian, Xue Li, Jingbo Xu, Erci Xu, Ennan Zhai, Wenyuan Yu, Guangtao Xue, Jingren Zhou]
venue: OSDI
year: 2026
tags: [llm-inference, tracing, anomaly-diagnosis, observability, tail-latency]
source_pdf: "[[osdi26-wu-haonan.pdf]]"
source_md: "[[osdi26-wu-haonan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-14
---

# 面向在线 LLM 推理的低开销追踪与诊断（OSDI 2026）

> **原题**：StriaTrace: Efficient Tracing and Diagnosis for Online LLM Inference (Operational Systems)

> **一句话总结**：在线 LLM 推理的异常通常是偶发的、受动态 token 工作负载影响的尾延迟事件；StriaTrace 只追踪同步边界、关键路径和异常片段，并用按实例拟合的 P99 roofline 筛选高保真 trace，在生产中把追踪开销控制到约 1% 以下，已覆盖 1,700 多个实例和每天超过 1.8 亿请求。

## 问题与动机

在线推理同时受 TTFT 和 TPOT 约束。论文在一个超过 2K 实例的服务中观察到，平均延迟可以满足目标，但尾部仍有 5.34% 请求违反 TTFT SLO、1.18% token 违反 TPOT SLO。流式执行、动态批处理、prefix KV cache、prefill/decode 分离和多种并行策略使得离线复现很困难。

通用 profiler 能提供细节，却会直接扰动热路径。训练诊断工具依赖固定 batch 和静态执行模式，也不能处理在线推理中的一次性异常。论文因此把目标限定为生产 triage：持续保留足够的跨层上下文，先定位异常 rank、阶段和可疑函数，再交给 SRE 确认根因，而不是承诺自动生成最终根因。

## 关键观察 / 隐含假设

- **观察 1：同步边界足以恢复请求的宏观因果链。** 一个 vLLM 推理 step 会触发超过 10,000 次 EngineCore 函数调用，但真正决定阶段推进的是跨进程 RPC 和外部 KV cache 等同步点（表 2，§5.2.1）。
  - **依赖假设**：关键阻塞和阶段转换都经过可稳定识别的边界。
  - **可能失效场景**：异步后台任务在边界之外改变关键路径，或框架升级后出现未覆盖的新同步关系。
- **观察 2：GPU kernel 时间线可以暴露主导瓶颈。** 稀疏 kernel 表示 CPU/host 侧没有及时发射工作，密集 kernel 则表明设备执行占据关键路径（图 6，§5.3.1）。
  - **依赖假设**：kernel 间空洞能够代表 host 侧停顿，且无需 CUDA API 级信息即可解释异常。
  - **可能失效场景**：driver/runtime API 抖动、复杂 stream 依赖或短暂 micro-stall 被 kernel 时间线掩盖。
- **观察 3：step 延迟与 token 数量在同一 serving instance 内具有稳定正相关。** 生产数据的 P99 回归线达到 R²=0.98（图 7，§5.4.1）。
  - **证据强度**：中。实验支持一个实例上的线性关系，但跨模型、硬件、路由分布和版本的稳定性仍需单独验证。

## 核心方法

StriaTrace 由部署在 serving instance 上的分布式 collector 和集中式分析后端组成。CPU 侧在 EngineCore、GPUWorker 以及外部 KV cache 交互处放置同步边界和 semantic span；GPU 侧只记录 kernel 与 memory copy 的起止时间，并携带 request、instance 和 rank 元数据。这样可以把请求层、框架层和 kernel 层在 Perfetto 中对齐。

CPU 追踪采用“少量静态点 + 异常时采样”的混合策略。常态下只记录 schedule、execute_model、sample_tokens 等关键 span；异常附近再用 10 ms 间隔的 py-spy 获取 Python 栈和 GIL 状态。导出不使用可能在后台争抢 GIL 的 OpenTelemetry batch thread，而是在 CPU 等待 GPU 的窗口主动 flush，隐藏 I/O 成本。

GPU 侧放弃 CUPTI 的 CUDA Runtime/Driver API 全量订阅，只保留硬件执行区间。正常 step 丢弃完整 kernel trace，仅保留聚合指标；动态 roofline 判为异常时才保存高保真记录。论文报告该策略把数据量压到原始流的约 1.6%。

roofline 不是预先写死的硬件模型，而是针对每个 serving instance 按 token 数量拟合历史延迟的 P99 回归线。模型启动阶段收集样本，之后周期性更新；越过 roofline 的 step 进入异常报告。后端再把主导 semantic span、py-spy 栈、GIL 状态和异常 kernel 相关联，给 SRE 提供候选瓶颈。

## 设计取舍

- **覆盖率换开销**：不追踪全部函数和 CUDA API，降低了持续监控成本，但微小的 driver/runtime stall 只能依靠 kernel 空洞间接推断。
- **异常保留换存储**：正常请求没有完整 GPU 证据，若 roofline 错过了异常，事后无法恢复丢弃的细节。
- **实例内经验模型换通用理论模型**：按实例拟合适应不同模型和部署组合，但在基线本身已退化时可能把慢状态当成正常状态。论文报告约 7% 报警最终是自然 workload 方差，典型原因是 MoE 的 Expert Parallelism 路由不均衡。

## 实验与结果

- 在 8 张 NVIDIA H20、Qwen3-Coder-30B-FP8、TP=8、prefill/decode 分离环境中，完整 StriaTrace 的 TPOT 开销随并发从 8 到 256 降低，Median 从 5.2% 降至 0.6%；CPU-only 配置的 Median 和 P99 开销始终低于 1%（图 9a，§6.2）。
- 同一环境中，TTFT Median 开销从并发 8 时的 2.7% 降至并发 256 时的 0.8%；对照的 TProf 在并发 8 时使 Median/P99 TTFT 增加到基线的 3.0×/3.2×（图 9b）。
- 在 TP=4 的故障注入实验中，StriaTrace 对 host-side stall 和 device-side contention 的注入异常都达到 100% recall（图 10，§6.3）。
- decode 实例的 NSys 和 TProf 数据带宽至少是 StriaTrace 的 38 倍；生产部署后完整 trace 保留量约为原始 GPU 流的 1.6%（表 3，§5.3.2）。
- 一个生产 straggler 案例中，step 延迟从约 75 ms 偶发升至 160 ms 以上；StriaTrace 定位到单个 rank 的 `sample` 阶段和约 80 ms GPU 空洞，最终将 `make_ndarray_with_pad` 的 P99 从 110 ms 降到 43 ms（图 11，§7.1）。
- 生产中运行 6 个月，覆盖 1,700 多个实例、两个旗舰模型和每天超过 1.8 亿请求，诊断了数百个异常、19 类根因（§6.4，表 4）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 选择性追踪可用于在线生产 | 图 9、表 3；CPU 低于 1%，完整系统在高并发时低于 1% | H20、vLLM、Qwen3-Coder-30B、TP=8、PD 部署 | 强 |
| 经验 roofline 能识别动态异常 | 图 7 的 R²=0.98，图 10 的注入 recall=100% | 两类合成故障，另有约 7% 生产误报 | 中 |
| 跨 CPU/GPU trace 能缩小根因搜索空间 | 图 11、§7.1；160 ms straggler 定位到单 rank 和具体 Python 函数 | 生产案例，最终仍需 SRE 确认 | 强 |
| 方法具备生产规模可用性 | §6.4：1,700+ 实例、1.8 亿请求/日、6 个月 | Alibaba 两个服务，NVIDIA 生态 | 中 |

## 批判性分析

### 论证链条

论文的链条基本闭合：动态在线工作负载导致偶发尾延迟；全量 tracing 会改变热路径；同步边界和关键路径提供低成本结构信息；经验 roofline 负责筛选；异常时的 CPU/GPU 关联负责定位。生产案例证明这套链条能找到具体代码和编译配置问题。

但 100% recall 只来自两种人为注入故障，不能推出对全部生产根因的召回率。持续退化也可能被 roofline 自适应地吸收，论文明确展示了 CUDA Graph 被关闭时不会触发 roofline 报警。

### 假设压力测试

按 token 数量做一元回归隐含了实例内部 workload 变化主要由 token 数量解释。MoE 路由不均衡、prefix cache 命中率、请求参数和 rank-level contention 都可能在 token 数量相同的情况下改变延迟。若模型版本或调度策略快速变化，周期性 retrain 可能暂时把新退化纳入基线。

CPU 采样间隔为 10 ms，适合几十毫秒级停顿，却可能漏掉大量短 micro-stall。GPU 侧只记录 kernel 区间，也无法直接区分所有 CUDA API、driver 和调度层原因。论文将这些场景定位为后续离线加点，而非在线自动诊断。

### 实验可信度

实验硬件和 PD 部署接近生产，且与 NSys、TProf、Scalene 对比，覆盖了 TTFT、TPOT、P99 和数据带宽。局限是主要工作负载集中在一个 Qwen MoE 模型和 NVIDIA H20，故障检测用合成注入，缺少不同模型、GPU 代际和真实异常的系统化 precision/recall 分析。

### 系统性缺陷

框架相关的同步点需要手工维护。论文称六个月内 vLLM 关键路径仅发生一次重大变化，但其他框架或高频改版未必如此。集中式 backend 还引入了 trace 传输、存储和多租户隔离问题，论文没有给出后端故障、数据丢失或敏感请求元数据治理的评测。

## 局限与后续工作

- **局限 1**：roofline 在持续退化时可能自适应到错误基线，且生产误报约 7%。
- **局限 2**：10 ms py-spy 采样和 kernel-only GPU tracing 对短暂、细粒度 stall 的覆盖不足。
- **局限 3**：结论主要建立在 NVIDIA CUPTI 和 vLLM 上，跨 AMD/ROCm 的兼容性只停留在设计讨论。
- **后续工作 1**：评估多变量 roofline，将 token 数、KV cache 命中率、EP routing skew 和 rank-level contention 纳入模型，并在版本切换时检测基线漂移。
- **后续工作 2**：建立真实生产异常的带标签数据集，报告不同根因类别的 precision、recall、检测延迟和丢失 trace 比例。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[MoE]]
- **同类系统**：[[vLLM]]、[[SGLang]]
- **同会议**：[[OSDI-2026]]
