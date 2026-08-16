---
type: paper
name: Prism
full_title: "Prism: Cost-Efficient Multi-LLM Serving via GPU Memory Ballooning"
authors: [Shan Yu, Yifan Qiao, Mingyuan Ma, Yangmin Li, Shuo Yang, Xinyuan Tong, Yang Wang, Zhiqiang Xie, Yuwei An, Shiyi Cao, Ke Bao, Deepak Vij, Xiaoning Ding, Yichen Wang, Qingda Lu, Zhong Wang, Gao Gao, Harry Xu, Junyi Shu, Jiarong Xing, Ying Sheng]
venue: OSDI
year: 2026
tags: [llm-serving, gpu-memory, multi-model, memory-ballooning, scheduling]
source_pdf: "[[osdi26-yu-shan.pdf]]"
source_md: "[[osdi26-yu-shan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用 GPU 内存气球降低多 LLM 服务成本（OSDI 2026）

> **原题**：Prism: Cost-Efficient Multi-LLM Serving via GPU Memory Ballooning

> **一句话总结**：四组生产 trace 显示，同一时刻只有 23%–50% 的模型活跃，而且活跃集合每小时变化 54–766 次；Prism 因而把权重和 [[KV-Cache]] 都纳入可伸缩的 GPU 内存气球，再用跨 GPU 的 KV 压力放置和单 GPU 的 slack 调度统一空间共享与时间共享，在 58 模型实验中用 16 块 H100 达到接近 99% 的 TTFT SLO 达标率，而 MuxServe++ 要到 32 块才接近这一水平。

## 问题与动机

推理服务商必须长期提供大量基础模型和微调模型，其中很多模型请求很少，却不能离线。为保证首 token 延迟，常见做法是给每个模型固定一组 GPU；论文引用的生产观察显示，这种做法下 GPU duty cycle 经常低于 30%。成本问题的核心因此不是单次推理慢，而是权重和 KV cache 长时间占住显存，其他模型无法复用。

现有共享方案各只适合一种时间尺度。空间共享（space sharing）把多个低流量模型常驻同一 GPU，可以避免切换，但静态 KV 分区无法把 idle 模型的空间让给突然变热的模型。时间共享（time sharing）会驱逐 idle 权重，适合长空闲期，却在多个模型交替来请求时反复从 CPU DRAM 加载权重，数秒冷启动会造成 thrashing。论文在一段生产 trace 上重放 QLM 和静态分区，分别观察到频繁换模和“旁边显存闲置但热点模型排队”的失败（图 2）。

Prism 的切入点是：两种共享最终都在争同一个 GPU 物理内存池。权重驻留决定模型是否可立即运行，KV cache 容量决定可并发的请求数；如果物理页能跨模型动态收回和扩张，就不必预先把模型永久归类为空间共享或时间共享。

## 关键观察 / 隐含假设

- **观察 1：活跃模型形成不断移动的“突发组”。** Hyperbolic、Novita、Arena-Battle、Arena-Chat 四组 trace 覆盖 16–129 个模型、11 天到 16 个月；平均同时活跃的模型仅占 23%–50%，活跃集合却每小时变化 54–766 次（表 1、图 1、附录 A.1）。
  - **依赖假设**：未来多模型服务仍有明显长尾和错开的活跃集合，而不是所有模型持续高负载。
  - **可能失效场景**：模型数量很少、全部持续活跃，或一次热门事件使许多模型同步爆发时，可回收的权重和 KV 空间都会减少。
- **观察 2：同一模型的请求在短时间内也高度波动，不能只靠长期预测。** 多个 trace 中，模型每小时有 40–100 个持续超过 10 秒的 idle interval，许多模型每分钟请求率的变异系数高于 1；相邻两天同一时刻请求率的 Pearson 相关性接近 0（图 1、附录图 12–13）。
  - **依赖假设**：秒级到分钟级的即时测量，比按历史时段静态配置更能代表接下来一小段时间。
  - **可能失效场景**：变化快过迁移和激活速度时，控制器仍会追不上；变化很慢且可预测时，简单的静态放置或 autoscaling 可能已经足够。
- **观察 3：GPU 显存是连接空间共享和时间共享的共同控制对象。** 时间共享主要回收模型权重，空间共享主要调整 KV cache；两者都可以化成物理页在模型间的重新分配（图 4）。
  - **依赖假设**：推理仍主要受显存容量与带宽限制，重新映射 2 MB 页的开销小于重新分配大 tensor 或请求排队的代价。
  - **证据强度**：强。跨模型内存实验、端到端结果和最坏情况下的页映射开销实验相互支持，但只覆盖 CUDA GPU。
- **假设 1：调度器可以用输入长度和历史 prefill 速度估准 TTFT slack。** Moore–Hodgson 调度需要请求 deadline 和执行时间；输出长度未知，因此 Prism 直接优化 TTFT，TPOT 只通过降低内存争用间接受益（§6.2）。
  - **证据强度**：中。实验中 TTFT 和 TPOT 都改善，但估计误差、异构 prompt 处理和突发干扰没有单独量化。

## 核心方法

Prism 把一组共同执行一个模型副本的 GPU 定义为不可再拆的 **GPU group**，前端把请求交给对应模型。模型可以独占一个 group，也可以与其他模型空间共享；长时间 idle 的模型被驱逐到 CPU DRAM，来请求时再激活。Autoscaling 决定副本数量，Prism 只负责已有副本之间如何共享 GPU，二者是正交关系（图 3、§4）。

内存机制是开源的 balloon driver **kvcached**。它位于 [[SGLang]] 与 CUDA 内存之间：每个 engine 初始化时先保留很大的连续虚拟地址区，物理页只在真实需要时创建并映射。这样，某模型的 [[PagedAttention]] KV pool 在应用看来仍是一块普通大 tensor，但 idle 页可以归还给另一个模型的权重或 KV cache。kvcached 用 elastic tensor（eTensor）兼容现有 [[PyTorch|PyTorch]] 和 [[Attention|attention]] kernel，接入 SGLang 只改了 22 行代码（§5.2、§7）。

为支持不同层数、head 数和 token 大小的模型，内部 KV manager 把各模型 token block 放在独立的 2 MB 物理页中，并优先填充部分使用的页。它把同一 token 在所有层的 K/V 向量重排到连续虚拟空间，使一次批量分配替代原来的 `2L` 次页分配；后台线程还预先准备少量空闲页，减少频繁 balloon 的分配延迟（图 4）。

模型激活通过两个手段加速。其一，每块 GPU 保留预初始化的 engine pool，模型被驱逐时只释放物理内存，虚拟地址空间和 distributed context 留给下一次使用；KV virtual-memory manager 再按新模型布局对齐地址。其二，把权重按 tensor 切块，借同一节点的多块 GPU 并行从 CPU DRAM 加载，再通过 NVLink 聚合到目标 GPU；每个辅助 GPU 只需约 30 MB 缓冲（§5.3）。

控制面分两层。全局放置器用 **KV pressure ratio（KVPR）**衡量一块 GPU 上“按 TPOT SLO 加权的 token 内存增长率”与剩余 KV 空间的比例，先放压力最大的模型，再贪心选择放入后 KVPR 最低的 GPU；只有改善超过阈值 `τ` 才迁移，[[Tensor-Parallelism]] 模型的各 shard 还带 anti-affinity。GPU 本地则把不同 engine 的请求放进共享队列，用 prompt 长度、[[Chunked-Prefill|chunked-prefill]] 速度、到达时间和 TTFT SLO 计算 slack，再用 Moore–Hodgson 算法选择能按时完成的请求集合（算法 1–2）。

## 设计取舍

- **以下沉到 CUDA VMM 换透明性**：2 MB 页让不同模型共享物理显存而不改 attention kernel，但方案绑定 CUDA virtual memory、PyTorch extension 和特定 serving-engine 生命周期。
- **以两级启发式换在线可解性**：KVPR 加本地 deadline 调度避免联合 ILP 的组合爆炸，却不能预知输出长度，也不保证全局 placement 与局部请求选择的联合最优。
- **以 CPU DRAM 和同机 GPU 带宽换快速激活**：并行加载明显缩短冷启动，但会占用大量 host memory、[[PCIe|PCIe]]/NVLink 和辅助 GPU 带宽；跨节点或无 NVLink 环境只能退化到 [[RDMA|GPUDirect RDMA]] 或普通重激活。
- **边界条件**：有长尾 idle 模型、足够 CPU DRAM、较快节点内互连且 TTFT 比 TPOT 更优先时最合适；模型全热、显存持续满载或严格多租户隔离下收益和稳定性都可能下降。

## 实验与结果

- **设置与基线**：主测试床有 4 个节点，每节点 8 块 H100-80G、GPU 间 600 GB/s NVLink，节点间 100 Gbps Ethernet，另有双路 52 核 Xeon 8480+ 和 1.7 TB DRAM。比较静态分区 S-Partition、移植到 SGLang 且使用 kvcached 支持异构模型的 MuxServe++、QLM 和 ServerlessLLM；使用 Hyperbolic、Arena-Chat 两组真实到达模式并按倍数放大请求量，最多评测 58 个 1B–70B 模型和 32 块 GPU。SLO 以模型独占 GPU 时的 P95 为基准，再乘不同 scale；指标是 TTFT/TPOT SLO 达标率、吞吐和达到 99% SLO 所需 GPU 数（§7.1、表 2–3）。
- **8 模型、2 GPU 的负载扩展**：在 99% TTFT SLO 达标率下，Prism 在 Hyperbolic trace 可处理的请求量分别是 MuxServe++ 和 S-Partition 的 2.3 倍、3.5 倍；在 Arena-Chat 上比所有基线多处理 3 倍以上请求。QLM 因频繁换模不如静态分区，ServerlessLLM 的完整冷启动最差（图 5 第一行）。
- **资源需求**：18 个 1B–8B 模型中，Prism 在 Hyperbolic 和 Arena-Chat 上分别用 4、5 块 GPU 达到 99% TTFT 和 TPOT，所有基线即使用 8 块也未达到 99% TTFT。58 模型大规模实验中，Prism 用 16 块 H100 达到接近 99% TTFT，MuxServe++ 到 32 块才接近；图 9b 中“Prism 16 块、MuxServe++ 20 块”对应不同 SLO scale，不能直接当作同一 SLO 下的成本对比（图 5 第三行、图 9）。
- **组件证据**：两模型 trace 中，动态跨模型 KV 分配在第 20 秒后把 idle Model1 的空间让给突发 Model2，从而提高总 KV 使用量和吞吐。关闭全局 placement 会让一块 GPU 在 800–1000 秒接近无可用 KV、另一块却 idle；开启后 TTFT/TPOT 达标率都更高。开启本地 arbitration 后，严格 SLO 的 Model2 达标率提高 40 个百分点以上，而 Model1 仍接近 100%（图 6–8）。
- **激活与内存开销**：预初始化 engine 加并行加载把 1B、8B、14B、70B（TP=8）模型从 CPU pageable memory 激活到 GPU 的时间分别降到 0.2、0.7、1.3、1.5 秒。最坏的持续高负载下，两份 Llama-3.2-3B 在 A100-40G 上相对静态分区平均 TTFT/TPOT 开销通常为 3%–5%；论文列出的高负载点中 TPOT 开销可到 13%（图 10、附录 A.3）。
- **生产证据**：截至 2025 年 12 月，kvcached 已用于超过 10,000 块 GPU。两家公司用相同在线流量做 shadow replay：Company A 在数周内每 GPU token 吞吐平均提高 3.89 倍，称没有 SLO violation 且尾延迟不变；Company B 每 GPU 收入提高 2.86 倍。论文未公开集群规模、绝对请求量和误差区间，因此这些结果能证明实用性，但不便独立复现（图 11、§7.6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 动态 bursty group 使固定空间或时间共享都不合适 | 图 1–2、表 1、附录 A.1 | 四个服务商/评测平台 trace；16–129 个模型，11 天至 16 个月 | 强 |
| 内存气球能在同一 GPU 上把闲置模型显存及时交给热点模型 | 图 6、附录 A.3 | 两模型简化 trace；A100/H100、CUDA VMM；持续满载时仍有页映射开销 | 强 |
| 两级调度是端到端 SLO 收益的重要来源 | 图 7–8 | 8 模型/2 GPU placement 实验和 2 模型 arbitration 实验 | 强 |
| Prism 在同一 SLO 下显著减少大规模 GPU 需求 | 图 9a、§7.4 | 58 模型、最多 32 块 H100；trace 请求量经过倍数放大 | 强 |
| 生产部署能提高每 GPU 产出且保持 SLO | 图 11、§7.6 | 两家未具名公司、shadow replay；绝对规模和统计细节未公开 | 中 |

## 批判性分析

### 论证链条

论文的主线很清楚：生产 trace 先证明模型集合在粗粒度上移动、请求在细粒度上交错，再把两种现象分别映射到时间共享和空间共享，最后用一个物理显存机制统一二者。图 6–8 分别证明跨模型页共享、全局 placement 和本地 arbitration 有贡献，端到端图 5/9 再验证组合效果。需要收窄的是“成本降低”：同一 SLO 下最有力的证据是图 9a 的 16 对 32 块 GPU；图 9b 的 16 对 20 使用了不同 SLO scale，旧式一句话比较会夸大可比性。

### 假设压力测试

KVPR 使用近期 token rate 和已知权重，但不知道输出长度；如果长输出、工具调用或 [[Speculative-Decoding|speculative decoding]] 突然改变 KV 增长，placement 可能在一个监控窗口内判断错误。附录显示 idle eviction 低于 40 秒会 thrashing，高于 80 秒又会让 idle 权重占住显存，约 45 秒只是两组 trace 上的经验点。若所有模型同时活跃，balloon 只能重新分配稀缺内存，不能增加容量。无 NVLink 的跨节点迁移、CPU DRAM 不足以及共享互连拥塞也可能使 0.2–1.5 秒激活结论失效；这些场景没有端到端测量。

### 实验可信度

硬件规模达到 32 块 H100，模型从 1B 到 70B，并有真实到达模式、组件实验和生产 shadow replay，证据比只用合成 Poisson workload 更强。限制有三点：其一，四组 trace 只用于 characterization，端到端只重放其中两组且会按倍数放大；其二，SLO 是独占 GPU 的 P95 再乘 scale，部分“达到 99%”发生在很宽松的 scale，必须与具体图一起读；其三，MuxServe++ 是作者移植且借用了 kvcached 的版本，QLM/ServerlessLLM 的工程成熟度也可能影响公平性。论文没有报告置信区间或多次运行方差。

### 系统性缺陷

Prism 把所有 engine 的显存和请求交给共享控制面，扩大了故障与隔离边界。论文未讨论一个 engine 崩溃、错误释放页、模型间侧信道、恶意租户抢占 KV、调度器失联和 migration 中断时如何恢复。GPU-local 队列为了最大化达标请求数会延后长任务，作者声称 admission control 可避免 starvation，但没有给公平性或最大等待时间。10,400 行 Python、774 行 C++、Redis、ZeroMQ、engine pool 和 CUDA VMM 也带来运维复杂度；生产章节没有量化这些组件的故障率和控制面资源开销。

## 局限与后续工作

- **局限 1：硬件与内存层绑定。** 在无 NVLink、PCIe Gen4、跨节点 RDMA 和较小 host DRAM 上复现图 5/9/10，测出激活和迁移何时超过 TTFT budget。
- **局限 2：预测误差没有显式评测。** 可注入输出长度突变、prompt mix 改变和相关模型突发，量化 KVPR 估计误差、迁移次数与 SLO 的关系。
- **局限 3：公平和故障边界缺失。** 需要报告每模型最大排队时间、长期资源份额，并对 engine crash、scheduler crash、OOM 和迁移中断做故障注入。
- **后续工作 1：直接优化 TTFT 与 TPOT。** 在三种以上模型架构上比较“只优化 TTFT”和联合目标，检验 TPOT 的间接受益是否在长 decode workload 中仍成立。
- **后续工作 2：公开可复现实验。** 发布去标识 trace、完整 baseline 配置和多次运行分布，使 58 模型的成本结论可以独立验证。

## 相关

- **相关概念**：[[LLM-Serving]]、[[GPU-Memory]]、[[Memory-Ballooning]]、[[KV-Cache]]、[[PagedAttention]]、[[Tensor-Parallelism]]
- **同类系统**：[[SGLang]]、[[vLLM]]、MuxServe、QLM、ServerlessLLM
- **同会议**：[[OSDI-2026]]
