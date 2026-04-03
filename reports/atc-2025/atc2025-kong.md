# PPipe: Efficient Video Analytics Serving on Heterogeneous GPU Clusters via Pool-Based Pipeline Parallelism

**作者**：Z. Jonny Kong, Qiang Xu, Y. Charlie Hu（Purdue University）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/kong
**源文件**：[[atc2025-kong.pdf]]

---

## 一、背景

视频分析系统广泛部署于交通监控、公共安全、医疗监护等领域，全球视频分析市场预计从 2023 年的 32 亿美元增长至 2030 年的 191 亿美元。这些系统依赖 CNN 模型在云端 GPU 上进行推理，面临严格的延迟 SLO（如 200ms）和突发请求到达的挑战。

由于 GPU 迭代速度快、价格高、供应有限，云厂商和私有组织越来越多地运行**异构 GPU 集群**——新旧 GPU 共存。然而，低端 GPU 上的推理延迟通常是高端 GPU 的 3x–7.9x，导致低端 GPU 难以在延迟约束下有效参与推理服务，造成资源浪费。

Pipeline parallelism 在 DNN 训练中已被广泛研究，但在**延迟受限的模型推理服务**中，特别是异构 GPU 集群上的应用，仍处于空白状态。

---

## 二、要解决的问题

1. **低端 GPU 资源浪费**：在异构集群中，低端 GPU 因整体模型推理延迟超过 SLO 而无法被使用（仅 22% 的 DNN 能在 NVIDIA P4 上以 batch size 4 在 200ms 内完成推理），导致大量 GPU 资源闲置。

2. **朴素 pipeline parallelism 的局限性**：将模型简单分割到异构 GPU 链上效果有限——如果高端 GPU 比低端快 10x，仅将 1/10 层放在低端 GPU 上就会导致 1.9x 的延迟膨胀。单链 pipeline 要求各 partition 延迟匹配以避免 stall，限制了分区灵活性。

3. **MILP 理想假设与运行时动态的差距**：MILP 求解器假设请求同步到达，但实际中请求异步且突发，引入初始 batching delay（D1）、跨 partition 排队延迟（D2）和网络带宽竞争延迟（D3），导致 SLO 违约。

4. **MILP 搜索空间过大**：DNN 模型平均 613.2 层，需在所有层间搜索最优分区点，加上 batch size 和 GPU 数量维度，求解时间超过 7 小时。

---

## 三、洞察与设计

**关键洞察**：异构 GPU 集群中存在两种多样性——模型层间的计算特性多样性和 GPU 类型间的架构差异——它们可以**协同利用**。具体而言，同一 DNN 模型的不同层在不同 GPU 上的延迟比（latency ratio）差异显著：例如 EfficientNet-B8 的早期层在 P4 和 L4 上延迟比约 1.7（接近），而后期层比率远高于此。反之，P4 和 V100 上的趋势完全相反。这意味着通过 GPU-aware 的模型分区，可以让每种 GPU 运行它最擅长的层，从而在最小化延迟膨胀的同时充分利用低端 GPU。

基于此洞察，PPipe 提出 **pool-based pipeline parallelism**：

- **Pool-based pipeline**：每个 model partition 关联一个 GPU pool（同类型 GPU 的集合），请求可以被 pool 中任意 GPU 处理。不同 partition 允许使用不同数量的 GPU、不同推理延迟、不同 batch size，只需各 pool 的吞吐量匹配（N₁×b₁/t₁ = N₂×b₂/t₂）且总延迟不超 SLO。同时可部署多条不同分区方案的 pipeline。

- **MILP-based control plane**：以 per-layer profiling 数据为输入，求解最优的 pipeline 配置（分区点、GPU 分配、batch size），最大化集群推理吞吐量。

- **Resource reservation-based adaptive batching（data plane）**：维护 GPU 和网络的实时/未来资源可用性表，通过 probe() 函数探测各 pipeline path 的最优 batch 和路径选择，动态调整 batch size 以应对请求突发，保证 SLO。

---

## 四、实现细节

**DNN Pre-Partitioning**：将 DNN 层预分组为 N=10 个等时间块（基于选定 GPU 类型上的运行时间），将 MILP 搜索空间从数百层缩减到 10 个块之间的分区点。MILP 求解时间从 7 小时降至平均 3.5 秒。

**Batch Size Unification**：引入 virtual GPU 概念（通过 NVIDIA MPS 将物理 GPU 分为 1/1、1/2、1/3、1/4），使同一 pipeline 内所有 partition 统一 batch size。在 MILP 中为 vGPU 类型建模，仅轻微扩展搜索空间，同时消除了跨 partition 的 batch split/merge 复杂性。

**Adaptive Batching 两步调度**：
1. **Step 1**：对每条 pipeline 以其统一 batch size 调用 probe()，选择等待时间最短的 pipeline。
2. **Step 2**：在选中 pipeline 上从 MILP batch size 开始递减搜索，找到能满足 SLO 的最大实际 batch size；通过 reserve() 预留资源后 dispatch。

**Feedback Correction**：各节点实时上报实际资源使用时间，修正调度器的资源可用性视图。

**额外 SLO Margin**：控制平面 MILP 求解时扣除经验确定的 margin（默认 40%），弥补理想假设与运行时差距。

**实现规模**：离线阶段 + 控制平面 Python 2.7 kLOC（Gurobi 求解器）；数据平面包含 Java 离散事件模拟器 + Julia/C++ 原型实现共 9.0 kLOC；使用 NCCL 传输 feature map，float32→float16 量化传输，精度损失 ≤0.01%。

---

## 五、实验结果

**集群配置**：4 种异构集群（HC1-HC4），每种含 100-GPU 大规模仿真和 16-GPU Google Cloud 实测两个版本。GPU 类型包括 NVIDIA V100、L4、T4、P4，高低端 GPU 默认比例 25:75。

**模型**：18 个 CNN 模型，覆盖识别、检测、分割等任务。SLO 默认为最快 GPU（L4）batch size 1 推理延迟的 5 倍。

**Baselines**：NP（无分区，代表现有异构服务方案）、DART-r（单链 pipeline 改进版）。

| 指标 | PPipe vs NP | PPipe vs DART-r |
|------|-------------|-----------------|
| 吞吐量提升（Poisson） | +48.0% | +32.2% |
| 吞吐量提升（Bursty） | +75.1% | +35.8% |
| 低端 GPU 利用率 | 73.6%（NP: 8.1%） | 73.6%（DART-r: 29.5%） |
| 16-GPU 实测吞吐量提升 | +42.6%–52.8% | +16.7%–34.1% |

**其他关键结果**：
- MILP 求解平均 3.5 秒，可扩展至 100k GPU 实例无显著增长
- 调度开销：平均 3.58 次 probe() 调用 / batch，总开销 <9μs
- Ablation：resource reservation vs reactive scheduler，load factor 0.92 vs 0.71
- SLO scale=2x 时 PPipe 退化为 NP（SLO 太紧无法用低端 GPU）；scale=10x 时低端 GPU 本身也能满足 SLO，收益趋小
- 高低端 GPU 比 2:14 时提升 64%，12:4 时提升 5.64%

---

## 六、批判性分析

1. **仅评估 CNN 模型，缺乏 Transformer 覆盖**：论文明确局限于 CNN（18 个视频分析模型），但当前推理负载日益由 Vision Transformer、LLM 等主导。作者在 conclusion 中提到"future work 将扩展到 Transformer"，但未讨论其方法对 Transformer 模型的适用性——Transformer 的 layer 计算模式更均匀（self-attention + FFN 重复堆叠），层间 latency ratio 多样性可能远不如 CNN，这会削弱核心洞察的适用性。

2. **40% SLO margin 的经验性较强**：控制平面扣除 40% margin 是关键调参，论文 sensitivity analysis 显示 20%–60% 范围内性能差异显著（24.9% vs 52.8% vs 16.4% improvement over NP），但未给出自动化确定 margin 的方法。在不同集群配置和负载模式下，最优 margin 可能不同。

3. **网络假设过于特定**：实验中有效带宽被设为标称值的 1/5（"to accommodate the observed 5× network tail latency on Google Cloud"），这一修正系数是否对其他云平台同样适用？论文未讨论网络拓扑和 bandwidth 变化对系统的影响。

4. **Baseline 选择有限**：仅对比 NP 和 DART-r，但 NP 本身就是一个较弱的 baseline（不做任何分区）。缺少与 AlpaServe（同样使用 pipeline parallelism 但面向同构集群）在异构场景下的改造对比，也没有与简单的 model parallelism（如 tensor parallelism）方案对比。

5. **GPU 内存约束被忽略**：论文声称"CNN 模型在数据中心 GPU 上通常不受内存限制"因此 MILP 不建模 GPU 内存。这在 CNN 场景可能成立，但使得该方法难以直接迁移到内存受限的场景（如更大的模型或多模型共存）。

6. **Virtual GPU 通过 MPS 实现的干扰问题**：论文通过同时在所有 vGPU 上运行相同 DNN 来捕获 profiling 干扰，但实际运行中不同 vGPU 可能运行不同 partition（不同层的不同计算特征），dry profiling 和实际的干扰模式可能有差异。

---

## 七、AI Infra / MLSys 视角

1. **层粒度异构感知的启发**：PPipe 的核心发现——不同 DNN 层在不同 GPU 上的相对性能差异显著——对 LLM 推理的异构部署有启发意义。例如 Transformer 中 attention 层（memory-bound）和 FFN 层（compute-bound）对 GPU 架构的适配性不同，可以探索将 prefill 和 decode 阶段映射到不同 GPU 类型。

2. **Pool-based pipeline 可迁移到 LLM serving**：当前 LLM serving（如 vLLM、SGLang）主要假设同构集群。PPipe 的 pool-based pipeline 思想可用于异构 LLM 推理——例如将 KV cache 密集的 decode 阶段放在内存大但算力弱的 GPU 上，prefill 放在算力强的 GPU 上。

3. **Resource reservation scheduling 的借鉴**：PPipe 的 probe()/reserve() 机制提供了一种轻量级、前瞻性的资源调度范式，相比 reactive scheduling 在突发负载下优势明显（load factor 0.92 vs 0.71）。这种思路可应用于 LLM serving 的 request scheduling，特别是 prefill-decode disaggregation 场景中的跨阶段资源协调。

4. **值得跟进的方向**：
   - 将 PPipe 的 per-layer latency ratio diversity 分析扩展到 Transformer/MoE 模型，验证核心洞察在现代模型架构上是否成立
   - 将 pool-based pipeline parallelism 与 prefill-decode disaggregation 结合，在异构集群上同时优化 TTFT 和 TPOT
   - 探索 MILP-based control plane + adaptive data plane 的范式在 LLM continuous batching 场景下的适用性

---

## 八、总结

PPipe 是首个在异构 GPU 集群上探索延迟受限 pipeline parallel 推理服务的系统，通过 pool-based pipeline parallelism、MILP 控制平面和 resource reservation-based adaptive batching 三重设计，将低端 GPU 利用率从 8.1% 提升至 73.6%，实现 32.2%–75.1% 的吞吐量提升。其方法目前限于 CNN 视频分析场景，向 Transformer 模型的扩展以及自动化 margin 调优是主要的未来工作方向。
