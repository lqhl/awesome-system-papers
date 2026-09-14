---
type: paper
name: Prism
full_title: "Prism: Cost-Efficient Multi-LLM Serving via GPU Memory Ballooning"
authors: [Shan Yu, Yifan Qiao, Mingyuan Ma, Yangmin Li, Shuo Yang, et al.]
venue: OSDI
year: 2026
tags: [multi-llm-serving, gpu-sharing, memory-management, kv-cache, slo-aware-scheduling]
source_pdf: "[[osdi26-yu-shan.pdf]]"
source_md: "[[osdi26-yu-shan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-13
---

# 用 GPU 内存弹性共享降低多模型推理成本（OSDI 2026）

> **原题**：Prism: Cost-Efficient Multi-LLM Serving via GPU Memory Ballooning

> **一句话总结**：生产流量中活跃模型组每小时变化 54–766 次，静态空间共享会锁住闲置内存，纯时间共享又会因换入换出抖动；Prism 用 kvcached 将模型权重和 KV cache 统一放进可弹性的 GPU 虚拟内存，再以 KVPR 放置和 slack-aware 调度协调共享，在最多 32 张 H100 上将 TTFT SLO 达标率提高至基线的 3.3 倍，并在相同达标率下减少超过 2 倍 GPU 成本。

## 问题与动机

推理服务商需要同时托管大量基础模型、微调模型和 LoRA 模型，其中许多模型流量低但必须保持可用。为满足 TTFT 和 TPOT 的尾延迟目标，常见做法是为模型预留模型并行 GPU 组；但生产 GPU duty cycle 常低于 30%，闲置模型占用的权重和 KV cache 容量无法被当前活跃模型使用。

现有多模型共享方案各自适合一种流量形态。空间共享让模型常驻并划分 GPU 内存，避免换入换出；时间共享在模型空闲时卸载权重，适合稀疏请求。论文对 58 个模型、4 组生产 trace 的分析显示，真实流量同时具有模型级的 bursty group 迁移和请求级的快速交错。固定空间分区无法回收长时间闲置容量，纯时间共享则会在交错请求期间频繁加载权重。

## 关键观察 / 隐含假设

- **观察 1：活跃模型集合是动态变化的 bursty group。** 四组 trace 中平均只有 23%–50% 的模型同时活跃，活跃集合每小时变化 54–766 次；Novita trace 中模型平均超过 70% 时间空闲（§3.1、图 1、图 12）。
  - **依赖假设**：模型权重可以在 TTFT 预算内从 CPU DRAM 重新加载，且闲置模型的内存确实能被其他模型利用。
  - **可能失效场景**：模型频繁轮换、权重远大于 70B，或 CPU–GPU 互连拥塞时，激进回收会转化为激活抖动。
- **观察 2：请求到达具有高波动和突然转折。** 多数生产模型的请求率 CV 大于 1，并有每小时 40–100 个持续超过 10 秒的空闲区间；相邻日期同一时段的请求率相关性接近 0（§3.2、附录 A.1、图 12–13）。
  - **依赖假设**：在线调度器不能依赖长期预测，只能依据近期到达和当前内存压力做反应式决策。
  - **可能失效场景**：有稳定日周期或可预测预约流量的服务，纯反应式策略可能错过更好的预取和放置机会。
- **假设 1：GPU 内存是多模型推理的主导共享瓶颈。** Prism 将权重与 KV cache 的争用作为 TTFT/TPOT 下降的主要原因；该判断在 H100/A100 实验和论文采用的 LLM 工作负载上证据较强，但对计算受限、通信受限或量化模型未充分验证。

## 核心方法

Prism 的底层机制 kvcached 位于推理引擎和 CUDA 内存分配之间。每个引擎预留大块虚拟地址空间，但物理 GPU page 只按需建立和映射。这样，模型权重与 KV cache 不再由各引擎分别静态占用，空闲模型的页面可以被回收给其他模型。2 MB page、部分填充 page 优先复用和异步预分配降低了重新映射与碎片开销。

kvcached 在虚拟空间中重排各层 K/V 向量，使一次批量分配替代原本的 2L 次 page 分配。KV cache manager 将不同模型的 token block 分到不同物理 page，以容纳不同层数、head dimension 和 token block 大小。elastic tensor（eTensor）通过 PyTorch 扩展接口暴露普通 tensor 语义，因此无需修改 attention kernel，也能保留 CUDA Graph 兼容性。这是对 [[PagedAttention]] 单模型内存池边界的跨模型扩展。

模型激活使用预热 engine pool，复用已经初始化的虚拟地址空间和分布式 context。模型权重被切成 tensor 级小块，在同一节点的多个 GPU 上并行加载，再通过 NVLink 汇聚到目标 GPU。源实例在迁移期间继续服务，减少迁移对 TTFT 的影响。

控制面分成两层。全局放置按模型的 SLO 加权 token memory demand 排序，把模型放到结果 KV Pressure Ratio（KVPR）最低的 GPU，尽量让高需求模型与低需求模型互补。GPU 本地调度使用共享请求队列，按 TTFT deadline 排序；若加入请求会导致超期，则移除执行时间最长的请求。这对应 Moore–Hodgson 的最少迟到作业算法，并优先保护更紧的 TTFT SLO。

## 设计取舍

- **弹性换取运行时复杂度**：虚拟地址、物理 page、KV block 映射和 engine 生命周期都需要额外控制面；实现包含约 10,400 行 Python 和 774 行 C++。
- **TTFT 优先于 TPOT**：调度显式优化 TTFT，TPOT 的改善主要来自降低内存争用和抢占。若 decode 阶段的 SLO 更严格，单纯的队列排序未必足够。
- **反应式回收依赖阈值**：附录 A.4 显示约 45 秒的 idle eviction threshold 在测试 trace 上较合适；低于 40 秒会频繁激活，高于 80 秒又会锁住闲置内存。不同租户和模型分布需要重新校准。

## 实验与结果

- 在两张 GPU 上服务 8 个模型时，Prism 在 Hyperbolic trace 上达到 99% TTFT SLO 的请求容量分别是 MuxServe++ 和静态分区的 2.3 倍与 3.5 倍；Arena-Chat 上超过所有基线 3 倍（图 5）。
- 大规模实验包含 58 个模型、最多 32 张 H100。Prism 用 16 张 GPU 达到接近 99% TTFT 达标率，MuxServe++ 需要 32 张；在特定 SLO scale 下，Prism 只需 16 张 GPU 即达到 99% TTFT，而静态分区和其他方案需要更多（§7.4、图 9）。
- 模型激活耗时为：1B–8B 少于 0.7 秒，14B 为 1.3 秒，超过 70B 的模型约 1.5 秒（图 10）。一次 8B 模型迁移通过 NVLink 约 20 ms，源实例可继续服务。
- 在没有动态共享机会的最坏场景中，A100-40G 上两个 Llama-3.2-3B 模型的 TTFT 开销为 3–4%，TPOT 开销为 7–13%（§7.5、图 14）。
- 两个生产 shadow replay 部署中，Company A 的每 GPU token throughput 平均提高 3.89 倍，Company B 的 revenue per GPU 提高 2.86 倍，报告称 tail latency 不变且无 SLO violation（§7.6、图 11）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 生产多模型流量同时需要空间驻留和时间回收 | 23%–50% 平均并发活跃模型、54–766 次/小时集合变化；纯策略在图 2 中分别出现 thrashing 和排队 | 4 组 trace，58 个模型 | 强 |
| 弹性跨模型内存能提升高峰吞吐 | Prism 在模型 1 低需求、模型 2 激增后扩大 KV cache 使用并提高吞吐（图 6） | 两模型 Arena-Chat 片段 | 强 |
| KVPR 放置和本地调度共同改善 SLO | 开启全局放置后 TTFT/TPOT 达标率提高；本地调度使模型 2 达标率提高超过 40%（图 7–8） | 2 GPU、8 模型或 2 模型微基准 | 中 |
| Prism 能降低生产成本 | 16/32 GPU 大规模对比；Company A 3.89× throughput、Company B 2.86× revenue/GPU（图 9、11） | H100 集群、trace replay 与两家部署 | 中 |

## 批判性分析

### 论证链条

论文的链条基本闭合：trace 证明静态空间共享和纯时间共享分别在不同时间尺度失败；kvcached 提供跨模型物理内存弹性；KVPR 与 slack-aware 队列分别处理集群级和 GPU 级争用；消融实验显示两层控制面各自有收益。论文没有把模型预测作为核心依赖，符合 trace 中接近零的跨日相关性。

但“GPU 内存是主导瓶颈”仍是范围性判断。实验集中在 H100/A100 和若干 LLM serving engine；计算、网络、CPU tokenizer、通信或长输出导致的 decode 瓶颈没有被系统地分离。生产收益采用 shadow replay，能控制流量变化，但没有公开足够的模型 mix、GPU 数量和成本基线，外部读者难以复核 3.89 倍与 2.86 倍数字。

### 假设压力测试

模型激活虽然在论文平台上低于 2 秒，但 CPU DRAM 中的 checkpoint locality、PCIe 拥塞和多租户同时激活会改变这一结果。并行加载依赖同节点多 GPU 和 NVLink；论文声称无 NVLink 时可用 GPUDirect RDMA 或回退到数秒级重新激活，但没有给出完整的非 NVLink 端到端 SLO 曲线。

KVPR 使用近期 token rate 和 TPOT SLO 估计压力，不知道未来输出长度。长输出、请求取消、prefix reuse 或 LoRA adapter 大量切换可能使当前压力估计偏离实际。共享物理内存也扩大了故障影响域；论文未充分讨论 page 映射错误、engine 崩溃后的 KV 状态恢复和跨租户隔离。

### 实验可信度

基线覆盖静态分区、空间共享、时间共享和 serverless 激活，且 MuxServe 被移植到 SGLang 并扩展为 MuxServe++，这是较公平的比较。论文使用真实 trace，并报告了主结果、两层调度消融、激活耗时和最坏情况下的弹性开销。

限制在于 trace 通过复制请求数放大负载，保留了模式但不一定保留排队反馈；模型集合虽有 58 个，却在部分实验中只选 8 或 18 个模型。TTFT SLO 从专用 GPU 的 P95 延迟缩放得到，可能与真实业务目标不同。对量化、prefix caching、speculative decoding 和更复杂 TP/PP 拓扑的覆盖不足。

### 系统性缺陷

kvcached 需要 CUDA VMM、PyTorch 扩展和与引擎内存语义的精确配合，兼容性风险集中在 CUDA、驱动、模型架构和引擎版本升级。全局 Python scheduler、Redis 和 ZeroMQ 增加了控制路径组件，论文未报告控制面故障、网络分区、状态恢复和监控成本。模型迁移保持源实例服务会短期复制权重和 KV 状态，峰值内存预算与并发迁移策略仍需明确。

## 局限与后续工作

- **局限 1**：主要性能结论来自 H100/A100、SGLang 和有限的公开 trace；非 NVLink、量化模型、prefix reuse 及不同推理引擎的表现未充分验证。
- **局限 2**：idle threshold 与 load monitoring window 需要按工作负载调参；论文没有给出在线自适应策略及其稳定性保证。
- **后续工作 1**：在无 NVLink 的多节点集群中测量 58 个模型的激活、迁移和 SLO 达标率，并把网络带宽、并发迁移数和模型大小作为独立变量。
- **后续工作 2**：加入输出长度预测误差、请求取消和 prefix reuse，比较 KVPR 与带不确定性区间的压力估计在 P99 TTFT/TPOT 下的差异。
- **后续工作 3**：构造 page 映射故障、engine 崩溃和调度器重启实验，量化共享内存回收对 KV 正确性、恢复时间和租户隔离的影响。

## 相关

- **相关概念**：[[PagedAttention]]、[[KV-Cache]]、[[CUDA]]
- **同类系统**：[[SGLang]]、[[vLLM]]、[[MuxServe]]、[[ServerlessLLM]]、[[Aegaeon]]
- **同会议**：[[OSDI-2026]]
- **对比**：[[MuxServe-vs-Prism]]
