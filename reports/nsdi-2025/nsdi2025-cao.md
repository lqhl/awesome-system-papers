# Making Serverless Pay-For-Use a Reality with Leopard

**作者**：Tingjia Cao, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau, Tyler Caraza-Harter (University of Wisconsin-Madison)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/cao
**源文件**：[nsdi2025-cao.pdf](../../papers/nsdi-2025/nsdi2025-cao.pdf)

---

## 一、背景

Serverless computing（FaaS）因其事件驱动架构和"按使用付费"（pay-for-use, PFU）计费模型而日益流行。AWS Lambda、Azure Functions、Google Cloud Functions 等主流平台均声称提供 PFU 计费。然而，"按使用付费"在实际中的含义远比表面宣传更复杂——云厂商所说的"pay for what you use"实际上更接近于"按墙钟时间的细粒度计费"，而非按实际资源消耗计费。

当前主流 serverless 平台的计费模型本质上都遵循 SLIM（Static, Linear, Interactive-only Model）模式：用户仅能配置一个内存上限，CPU 按固定比例分配，费用 = 执行时间 × 内存上限，不区分交互式与批处理任务。这种模型在四个强假设成立时才等价于真正的按使用付费：(1) 资源使用在调用期间恒定不变；(2) 不同调用间资源使用相似；(3) CPU 与内存使用成线性比例；(4) 所有调用都是交互式的。

---

## 二、要解决的问题

本文系统性地揭示了 SLIM 模型与真实资源消耗之间的差距：

1. **资源使用在单次调用中剧烈波动**（违反 Assumption SI）：实测 22 个 serverless 函数发现，CPU 并行度和内存使用在一次调用期间变化剧烈，用峰值作为上限导致大量资源闲置但仍被计费。

2. **不同调用间资源需求差异巨大**（违反 Assumption SE）：输入大小不同导致资源消耗差异显著——大输入的 CPU 使用是小输入的 3 倍，内存使用高达 16 倍，但 SLIM 对所有调用使用相同的资源配置。

3. **CPU 与内存使用不成比例**（违反 Assumption L）：91% 的函数相对于 AWS Lambda 的固定 CPU-内存比需要更多 CPU，CPU 密集型函数不得不为未使用的内存付费。

4. **并非所有调用都需要交互式 QoS**（违反 Assumption I）：许多函数（如模型训练、视频分析后台任务）不需要低延迟保证，但 SLIM 统一按交互式标准分配和计费资源。

核心问题：现有计费模型导致用户为未使用的资源付费，同时平台资源利用率低下——SLIM 下超过 50% 的 CPU 和 75% 的内存被浪费。

---

## 三、洞察与设计

**关键洞察**：Serverless 函数存在大量"已分配但未使用"的资源，而这些闲置资源可以通过计费模型的重新设计被"转售"给其他函数使用——关键在于让用户能够声明哪些资源是刚性需求（reserved），哪些是弹性可借用的（spot/preemptible），从而实现提供者和用户的双赢。

### NPFU 计费模型

基于上述洞察，作者提出 Nearly Pay-for-Use (NPFU) 计费模型，提供四个解耦的 knob：

- **cpu-cap**：CPU 上限
- **spot-cores**：cpu-cap 中不急需的部分，可被其他函数借用
- **mem-cap**：内存上限
- **preemptible-mem**：标记调用是否可被抢占（用于批处理任务）

NPFU 采用 **used/lent** 计费函数：
- CPU 成本 = reserved-cputime × C_r + borrowed-cputime × C_s − lent-cputime × C_s
- 内存成本类似，非抢占式实例出借闲置内存可获折扣，抢占式实例按实际使用量以低价计费

这样，交互式函数的闲置 reserved 资源可以低价出售给批处理函数，交互式函数获得折扣，批处理函数获得低成本资源，平台获得更高利用率。

### Leopard 系统

为支持 NPFU，作者构建了 Leopard 平台（基于 OpenLambda），在系统栈的每一层引入计费感知：

1. **CPU 调度（cpu.resv_cpuset）**：修改 Linux CFS 调度器，引入新的 cgroup 接口。Reserved task 在其保留核上有最高优先级可立即抢占；空闲保留核可被 spot task 使用。既不像 CPU pinning 那样浪费资源，也不像 weighted sharing 那样无法保证隔离。

2. **OOM Killer（sandbox evictor）**：新增 memory.oom.listener 和 memory.oom.victim cgroup API，将 OOM 时的牺牲者选择权交给用户态 evictor，优先杀运行时间最短、资源使用最少的 preemptible sandbox，避免误杀非抢占式实例。

3. **准入控制**：交互式调用需有足够未保留资源才可准入；批处理调用只需当前有空闲资源即可准入。通过历史数据预测是否可能发生抢占。

4. **负载均衡**：低负载时综合考虑 alignment score（多维资源匹配度）和 locality score（减少冷启动）；高负载时按 QoS 区分——交互式任务按 reserved-load 分配，批处理任务按 usage-load 分配。

---

## 四、实现细节

- **cpu.resv_cpuset 实现**：修改 Linux CFS 调度器核心逻辑。核心 run queue 区分 reserving task 和 spot task，调度时优先选择 reserving task；若无 reserving task 可运行，则从最忙的 run queue 拉取 reserving task，否则调度 spot task。Reserving task 唤醒时立即抢占 spot task。负载均衡也按 task 类别分开处理。

- **CPU 计费追踪**：修改 cgroup cpuacct 子系统，新增 resv_usage、spot_usage、lent_usage 三个接口。在 cgroup_account_cputime 回调中根据当前 CPU 是否属于该 cgroup 的 reserved set 来增量更新对应计数器，开销为简单算术运算，可忽略不计。

- **OOM 处理**：用户态 evictor 通过 memory.oom.listener 注册回调，收到信号后选择牺牲者并通过 memory.oom.victim 通知内核，通信开销约 0.4 ms。

- **BilliBench (BB)**：新的计费导向 benchmark，包含 22 个真实 serverless 函数（涵盖编译、视频分析、批处理、数据库操作、ML 推理/训练等 7 个领域），结合 Azure 生产 trace 的调用模式与 BB 函数的细粒度资源使用数据，生成可配置的合成 trace。

- **实验环境**：基于 Linux kernel v6.7-rc2（cgroups V1），Ubuntu 22.04，双路 Intel Xeon Silver（每路 10 物理核），禁用超线程。集群含 1 个负载均衡节点 + 8 个 worker 节点。

---

## 五、实验结果

### Provider 侧

| 指标 | SLIM | SIM | NPFU |
|------|------|-----|------|
| 吞吐量提升（相对 SLIM） | 1x | 1.3x | 2.3x |
| CPU 利用率 | <50% | 提升 | ~80% |
| 内存利用率 | <25% | 提升 | ~90% |

- 从 SLIM 到 SIM（解耦 CPU/内存）提升 1.3x 吞吐量
- 从 SIM 到 NPFU（spot cores + preemptible memory）再提升 1.6x

### User 侧

| 计费模型 | 交互式函数成本（相对 SLIM） | 批处理函数成本（相对 SLIM） |
|----------|---------------------------|---------------------------|
| SLIM | 100% | 100% |
| SIM | ~50% 函数更便宜 | 部分函数略贵 |
| SPFU | 部分函数贵 50%+ | 成本转嫁 |
| NPFU | 66% | 41% |

- NPFU 下约 40% 的函数成本降低一半以上
- 批处理任务获益更大，因为使用低价 spot 资源

### Job Completion Time

- 高负载下 NPFU 显著降低交互式函数 JCT（因更高吞吐量减少排队）
- 批处理任务可能比 SLIM 慢最多 3 倍（因可被抢占），但部分也能更快完成

### 大规模模拟

- 160 worker 集群模拟结果与 8 worker 实验一致
- 约 5% 的交互式函数在 NPFU 下比 SLIM 贵 15%

### 组件评估

- cpu.resv_cpuset 同时实现零 CPU 浪费和正确的性能隔离（CPU pinning 浪费 ~4s CPU 时间，weighted sharing 使 F2 慢 20%）
- Leopard 负载均衡器在所有负载条件下表现优于或持平 Consistent Hashing、Least-Loaded、Hermod

---

## 六、批判性分析

1. **Benchmark 的代表性存疑**：BilliBench 仅包含 22 个函数，虽然覆盖多个领域，但与 Azure 生产环境 52,000 函数的多样性相差甚远。BB Trace 通过随机映射 Azure 函数到 BB 函数来补全资源使用细节，这种映射方式可能引入系统性偏差——一个 ML 训练函数的资源波动模式被随机分配给数据库查询函数是否合理？

2. **"双赢"结论的前提条件较强**：NPFU 的优势高度依赖于存在足够多的批处理任务来消化交互式任务的闲置资源。实验显示当批处理比例低时，NPFU 的优势明显缩小，部分交互式函数甚至更贵。在纯交互式工作负载下，NPFU 退化为复杂版 SIM。

3. **用户配置复杂度被低估**：NPFU 引入 4 个 knob（cpu-cap, spot-cores, mem-cap, preemptible-mem），论文声称这比 SLIM 的单个需要精确调优的 knob 更简单，但实际上用户需要理解 reserved vs spot 的定价差异、抢占风险、以及如何设置 spot-cores 数量来平衡成本与延迟——这对大多数 serverless 用户来说是更高的认知负担。

4. **抢占式内存的可行性问题**：论文假设被抢占的批处理函数可以简单重新排队，但许多实际的批处理函数有中间状态（如部分完成的 ML 训练、数据处理 pipeline），重新执行的代价可能很高。论文未讨论 checkpointing 或增量计算等缓解方案。

5. **实验规模与真实环境的差距**：8 worker 物理集群 + 160 worker 模拟器与真实云规模（数千至数万台机器）相差甚远。大规模下的负载均衡、资源碎片化（stranded resources）、以及多租户间的相互干扰可能表现出不同的特征。论文在 §4.3.5 提到了 NUMA 感知、分数核、alignment vs locality 冲突等局限性，但未做定量评估。

6. **与现有 overcommit 方案的比较不够公平**：论文在 related work 中批评 Owl、Golgi、Jiagu 等 overcommit 方案"打破 SLIM 承诺"，但这些系统通过预测用户性能来避免 QoS 违约。NPFU 的 spot/preemptible 机制本质上也是一种 overcommit，只是通过计费模型将风险转嫁给用户。缺少与这些系统在相同工作负载下的直接性能对比。

---

## 七、AI Infra / MLSys 视角

1. **对 ML 推理/训练服务计费的启发**：当前 ML 推理服务（如 vLLM、TensorRT-LLM）面临类似问题——GPU 资源按预留量计费，但实际利用率因请求 batch size、序列长度波动而不稳定。NPFU 的 reserved/spot 解耦思路可以迁移到 GPU serverless 推理场景：为 SLO-sensitive 的在线推理保留 GPU 核心，将空闲周期以低价出售给离线推理或微调任务。

2. **与 GPU sharing/MPS 的结合**：Leopard 的 cpu.resv_cpuset 思路可以启发 GPU 时间片调度的设计。当前 NVIDIA MPS/MIG 提供的是静态隔离，类似于 CPU pinning 的局限性。一个"reserved GPU set"抽象——保证任务在需要时获得 GPU SM 的优先访问权，空闲时出借给低优先级任务——是值得探索的方向。

3. **可操作的 future work 方向**：
   - **GPU serverless 的 NPFU 计费**：为 GPU 推理函数设计类似的 spot-SMs / preemptible-GPU-memory 机制，需要解决 GPU 上下文切换代价远高于 CPU 的核心挑战
   - **Heterogeneous resource 的 NPFU 扩展**：AI 工作负载涉及 CPU、GPU、HBM、NVLink bandwidth 等多种资源，如何为每种资源设计 reserved/spot 语义？
   - **Checkpointing-aware 抢占**：对于长时间运行的 ML 训练任务，结合 checkpoint 机制设计更智能的抢占策略，避免大量重计算

4. **BilliBench 对 AI 工作负载的扩展**：当前 BB 函数套件中的 ML 工作负载较简单（KMeans、KNN、Logistic Regression），缺少 Transformer 推理、LoRA 微调、RAG pipeline 等现代 AI 工作负载。将 BB 扩展到 GPU 密集型 AI 函数是有价值的工作。

---

## 八、总结

本文提出了 NPFU 计费模型和 Leopard 系统，通过解耦 CPU/内存、区分 reserved/spot 资源、以及引入 preemptible 语义，使 serverless 计费更接近真实资源消耗。Leopard 在系统栈各层（CFS 调度器、OOM killer、准入控制、负载均衡）引入计费感知，实现了 2.3x 吞吐量提升和 34%-59% 的用户成本降低。论文的核心贡献在于将计费模型从系统设计的"事后补充"提升为"核心设计要素"，这一视角对云计算系统设计有普遍意义。主要局限在于 benchmark 规模有限、对批处理比例敏感、以及从 CPU/内存到 GPU 等异构资源的泛化尚未验证。
