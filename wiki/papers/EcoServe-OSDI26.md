---
type: paper
name: EcoServe
full_title: "Efficient LLM Serving on Commodity GPU Clusters with Data-Reduced Cross-Instance Orchestration"
authors: [Jiangsu Du, Hongbin Zhang, Taosheng Wei, Zhenyi Zheng, Jiazhi Jiang, Kaiyi Wu, Zhiguang Chen, Yutong Lu]
venue: OSDI
year: 2026
tags: [llm-serving, scheduling, gpu-cluster, disaggregation, kv-cache]
source_pdf: "[[osdi26-du.pdf]]"
source_md: "[[osdi26-du]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向普通 GPU 集群的低数据量跨实例 [[LLM|LLM]] 编排（OSDI 2026）

> **原题**：Efficient LLM Serving on Commodity GPU Clusters with Data-Reduced Cross-Instance Orchestration

> **一句话总结**：NoDG 受 prefill/decode interference，FuDG 又在普通 Ethernet 上受 KV-cache transfer 限制；EcoServe 以时间维度部分解耦（PaDG）、多实例 rolling activation、SLO-aware routing 和 mitosis scaling 保留 KV cache 本地性，在 L20/10GbE 集群上相对 vLLM、Sarathi、DistServe、MoonCake goodput 最高提升 1.96×、1.99×、2.51×、2.40×。

## 问题与动机

[[LLM-Inference|LLM inference]] 的 prefill 是 compute-heavy，decode 是 memory-heavy，并分别受 TTFT 与 TPOT SLO 约束。NoDG 将两者放同一 instance，频繁切换和 hybrid/chunked batching 会让 prefill 阻塞 decode、decode又难积累大 batch；FuDG 分配独立 prefill/decode instance，消除 interference，却必须跨实例传 KV cache。LLaMA-30B 在 8×A800 prefill node 的理论 KV output rate 可达 39 GB/s，需要至少 400 Gbps network（§2.4.2），而大量生产集群仍是 [[PCIe|PCIe]] GPU 加 10/25GbE。

EcoServe 提出第三点：部分解耦（partially disaggregated, PaDG）。同一 instance 仍拥有完整模型和 KV cache，但把 prefill/decode 分到更长的时间窗口；多个 instance 再错峰进入 prefill window，使 macro-instance 始终有入口处理新请求。它用 intra-/inter-instance coordination 换取低 data movement。

## 关键观察 / 隐含假设

- **观察 1**：NoDG 的问题不仅是单次 prefill 长，而是 phase switching 阻止 decode 形成高 arithmetic-intensity batch；适度拉长每阶段可以减少 interference（§2.4.1、§3.1.1）。
  - **依赖假设**：多个 instance 能错峰提供 prefill availability，且 workload 有足够并发积累 decode。
  - **可能失效场景**：单 instance/低并发时 PaDG 退化为 NoDG，论文也观察到新增 instance 带来 superlinear gain。
- **观察 2**：decode 早于 TPOT deadline 产生的 slack 可“借给”prefill；只要短窗口 mean saved TPOT 覆盖 pending prefill time，就能切 phase 而不破坏 SLO（算法 1）。
  - **依赖假设**：profiling 能准确预测 prefill duration，output progress 可代表未来 decode slack。
  - **可能失效场景**：burst arrival、长尾 prompt、decode kernel variability 与未知 output length 会让 estimate 偏差。
- **观察 3**：commodity network 上 FuDG 的 KV transfer 与 prefill/decode load balance 可能比计算本身更快成为瓶颈（图 8/9）。
  - **依赖假设**：模型可完整复制到每个 PaDG instance，GPU memory 足以同时容纳 weight 与 active KV。
- **假设 1**：用户感知 TTFT 应包含等待 phase switch 的时间，TPOT 从真正进入 decode 后开始计；这种严格定义可公平比较三类策略（§3.2）。
  - **证据强度**：合理但非行业统一，和其他系统报告的 TTFT/TPOT 口径可能不完全一致。

## 核心方法

PaDG 在 instance 内优先连续执行 decode，积累 slack 后切到 prefill window；KV cache 始终本地，不发生 FuDG 的跨 instance copy。macro-instance 含多个同构 instance，rolling activation 让它们周期性错峰切到 prefill，新请求总被路由到将满足 TTFT 的 instance（图 5）。

hierarchical scheduler 分 overall、macro-instance、instance 三层。instance 周期上传 decode progress、memory 与 phase status；macro scheduler cyclic scan candidate，先用 profile 估 pending prefill total time，再检查既有 request 的 mean saved TPOT 与剩余 KV memory，三项都满足才 admission（算法 1、§3.3）。

mitosis scaling 以 instance 而非整组 prefill/decode pair 调容量。macro-instance size 在 lower/upper bound `Nl/Nu` 间增长；满后像细胞分裂出新 macro instance，缩容则反向合并。serializable proxy 保存 request/KV 的逻辑 ownership，使 instance 完成已有 request 后可在 macro instance 间迁移，减少大粒度扩缩造成的 capacity jump（§3.4、图 7）。

## 设计取舍

- **避免网络换模型复制**：每个 PaDG instance 都有完整服务能力，省 KV transfer，却不能像 FuDG 那样按 prefill/decode 的不同 memory/compute需求独立配比。
- **吞吐换调度预测**：长 phase window 改善 batching，但一旦 admission/slack estimate 错误，TTFT 或 TPOT 会集中违约。
- **macro coordination 换状态开销**：高层要持续收集每实例进度；status staleness 可能导致多个请求同时消费同一 slack。
- **弹性简化换迁移约束**：proxy 只做 logical migration，removed instance 必须跑完已分配 request，缩容不是立即释放。
- **边界条件**：普通 interconnect、relaxed/moderate SLO、足够多实例时最适合；H100+NVLink/400Gb [[RDMA|IB]] 下 FuDG差距明显缩小。

## 实验与结果

- 三套集群：64×L20 48 GB/10GbE、16×A800 80 GB/25Gb RoCE、16×H100 80 GB/NVLink+每 GPU 400Gb IB；模型为 LLaMA-30B、CodeLlama2-34B、Qwen2-72B，数据为 Alpaca、ShareGPT、LongBench（§4.1）。
- L20/A800 commodity cluster 上 EcoServe 在所有 case 胜出；P90 goodput 相对 vLLM、Sarathi 平均高 2.01×、1.87×，相对 DistServe、MoonCake 高 3.43×、3.41×（图 8/9）。
- H100 high-performance cluster 上 margin 缩小：相对 vLLM/Sarathi 为 1.34×/1.25×，相对 DistServe/MoonCake 为 1.75×/1.24×（§4.2.1）。
- 按模型聚合，相对 NoDG 在 Llama-30B、CodeLlama2-34B、Qwen2-72B 吞吐平均高 1.59×、1.83×、1.76×；相对 FuDG 为 4.82×、2.15×、1.79×（§4.2.2）。
- 最严格 `(TTFT=1s, TPOT=50ms)` 下 EcoServe P99 throughput 从 42 降至 18 rps（57.1%）；vLLM 从 16 到 6.4（60%），Sarathi 从 28 到 7.6（72.9%）（图 10）。
- 1→4 instances 时 CodeLlama2-34B 与 Qwen2-72B throughput 分别达 4.96×、5.47×，说明多实例同时增加 capacity 和减少 phase interference（图 12）。
- rolling activation 相对 random instance selection、adaptive admission 相对固定 TTFT-fraction interval 在三模型/P50-P99 下均更高（图 15/16）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| PaDG 在 commodity network 上优于 NoDG/FuDG | 图 8/9、§4.2.1 | 30B/34B/72B、L20 10GbE 与 A800 25Gb RoCE | 强 |
| 优势来自减少 interference 与 KV network data | §4.2.2–4.2.4 | 跨模型、dataset、cluster 对比，未完全隔离工程质量差异 | 中 |
| rolling activation 和 adaptive routing 都有独立贡献 | 图 15/16 | A800、ShareGPT、三模型 | 强 |
| PaDG 更兼容 pipeline parallelism | 图 14 | CodeLlama2-34B、L20、[[Tensor-Parallelism\|TP]]=2/PP=2 vs TP=4/PP=1 | 中 |
| 细粒度 instance scaling 可跟随动态负载 | §4.5、图 12/13 | CodeLlama2-34B、ShareGPT、预设 Nl/Nu | 中 |

## 批判性分析

### 论证链条

论文用 hardware reality 解释 FuDG 不普适，再把“时间解耦+跨实例错峰”作为低数据量中间点，设计逻辑成立。跨网络档位结果也支持：interconnect 越强，PaDG 相对 FuDG 优势越小。需要警惕的是 DistServe prototype 被称为未维护、MoonCake 仍有 pause/buffer issue，部分优势可能来自 baseline engineering maturity，而非策略本身。

### 假设压力测试

算法用 mean saved TPOT 检查 existing decode，可能让少数 slow request 的 tail 被平均值掩盖；论文报告 attainment，但没有按 request age/output length 做 fairness。output length 未知且 bursty arrival 会改变 instance phase duration，status queue 延迟又可能消费过时 memory/slack。长 context 还会让本地 KV memory 而非 network先成为 PaDG瓶颈。

### 实验可信度

三代 GPU、三种 network、三个模型、三 dataset、P50/P90/P99 SLO、burst/scaling/ablation 覆盖广。局限是模型截至 72B dense，缺少 [[MoE|MoE]]、长 context production trace 与成本/功耗；Llama-30B 在 LongBench 因 2048 context truncation 实际 workload 更轻。个别 baseline execution failure 被省略，需谨慎解读“所有 case”。

### 系统性缺陷

macro scheduler 与 per-instance status queue 是控制面热点，论文未量化 scheduling overhead、stale state、scheduler failure 与跨节点 partition。PaDG 以完整 instance 为单位复制 weight，可能比 FuDG 需要更多 GPU memory/capacity。缩容要 drain request，长输出会使 release 延迟不可控；proxy serialization 对 KV ownership 和 failure recovery 的正确性未做 fault injection。

## 局限与后续工作

- **局限 1**：单 instance/低并发退化为 NoDG，收益依赖 macro instance 的额外 replication。
- **局限 2**：mean TPOT slack 不能直接保证每个 request 的 tail fairness。
- **局限 3**：模型复制与本地 KV memory 使 ultra-long context、大 MoE 的适配未知。
- **后续工作 1**：用 production burst trace 测 status staleness、SLO false admission、per-request p99.9 与 starvation，而非只看 aggregate attainment。
- **后续工作 2**：在相同 GPU-dollar、memory budget 与 energy 下比较 PaDG/FuDG/NoDG，区分“多复制实例”与调度本身的收益。
- **后续工作 3**：注入 scheduler/node failure 和缩容中断，验证 proxy/KV/request ownership 恢复且不重复输出 token。

## 相关

- **相关概念**：[[LLM-Serving]]、[[Prefill-Decode-Disaggregation]]、[[KV-Cache]]、[[Goodput]]、[[Pipeline-Parallelism]]
- **同类系统**：[[vLLM]]、[[Sarathi]]、[[DistServe]]、[[Mooncake]]
- **同会议**：[[OSDI-2026]]
