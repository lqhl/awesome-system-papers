---
type: paper
name: PPipe
full_title: "PPipe: Efficient Video Analytics Serving on Heterogeneous GPU Clusters via Pool-Based Pipeline Parallelism"
authors: [Z. Jonny Kong, Qiang Xu, Y. Charlie Hu]
venue: ATC
year: 2025
tags: [video-analytics, inference-serving, heterogeneous-gpu, pipeline-parallelism, milp]
source_pdf: "[[atc2025-kong.pdf]]"
source_md: "[[atc2025-kong]]"
---

# PPipe: Efficient Video Analytics Serving on Heterogeneous GPU Clusters via Pool-Based Pipeline Parallelism (ATC 2025)

> **一句话总结**：PPipe 的核心观察是 CNN 视频分析中「层间计算特性」与「GPU 代际差异」会交互改变 per-layer latency ratio，使低端 GPU 在 GPU-aware 分区下可 offload 部分推理而不显著拉长 E2E latency；它用 pool-based [[Pipeline-Parallelism]] + MILP 控制面 + 资源预留式自适应 batching，在 100-GPU 模拟与 16-GPU GCP testbed 上相对 baseline 提升 serving throughput 32.2–75.1%、低端 GPU 利用率至 73.6%，并保持 99% SLO attainment。

## 问题与动机

视频分析系统仍大量依赖 CNN（ResNet、EfficientNet、CenterNet 等）对摄像头流做实时推理，常见 latency SLO 约 200 ms。与此同时，云厂商和私有集群因 GPU 换代快、退役成本高，普遍积累 V100、L4、T4、P4 等混合资源。问题是：低端 GPU 单独跑整模型往往连 SLO 都过不了——论文在 [[TensorRT]] 上测得 P4 相对 L4 慢 3.0×–7.9×，18 个 CNN 里仅 22% 在 P4、batch=4 时不超 200 ms；而按峰值负载 provisioning 又会带来 off-peak 严重 under-utilization。

现有异构 serving 工作（[[Hercules]]、Scrooge、Inferline 等）大多把整模型放到某类 GPU 上，或做多模型 placement，**没有利用 DNN 层内 diversity**。训练领域的 [[Pipeline-Parallelism]] 也不直接适用：chain pipeline 要求各 stage latency 严格匹配，否则 pipeline stall；且若高端 GPU 比低端快 10×，朴素均分 1/10 层到低端 GPU 就会让总 latency 拉长 1.9×。

PPipe 的动机是：在 latency-bound、bursty 的在线 serving 场景下，把异构集群里「本来很难单独用」的低端 GPU 变成有效算力，同时提升高端 GPU 的集群级吞吐，而不是简单把慢任务丢给慢卡。

## 关键观察 / 隐含假设

- **观察 1：同一 CNN 的不同层，在不同 GPU 类型上的相对 latency ratio 并不恒定，且趋势可因 GPU 对而定。**
  - **证据**：EfficientNet-B8 上，P4/L4 的 per-layer latency ratio 早期约 1.7、后期显著升高；但 P4/V100 上趋势相反，早期层 ratio 更高。18 个评估模型均呈现跨层 varying ratio。根因是层大小、arithmetic intensity 与 GPU SM 数、ops:bytes 等设计 trade-off 的交互。
  - **依赖假设**：目标 workload 是 CNN backbone / detection / segmentation 等层结构可 profile、可切分的 vision 模型；分区点处的 intermediate feature map 尺寸与传输成本可接受。
  - **可能失效场景**：[[Transformer]]、MoE、RNN 等层间依赖或 activation 尺寸截然不同的结构；模型极度 memory-bound 到 datacenter GPU 装不下；或层数极少、分区收益被 feature map 传输吞没。
- **观察 2：pool-based pipeline 比 chain pipeline 更能消化异构集群里的 GPU 数量不平衡与 per-partition latency 差异。**
  - **证据**：相对 DART-r（复制 low/high GPU 对的 chain pipeline），PPipe 在 Poisson trace 上平均高 32.2% load factor，Bursty 上高 35.8%；低端 GPU 利用率从 DART-r 的 29.5% 提到 73.6%，而 NP 仅 8.1%。
  - **依赖假设**：各 partition pool 的吞吐可通过 $N_i \cdot b_i / t_i$ 匹配；集群网络带宽足以让 feature map 传输只占 SLO 一小部分（论文以 GCP 32 Gbps 估算 CenterNet 传输 0.8–13.2 ms）。
  - **可能失效场景**：多 GPU 同机共享 NIC 导致严重 contention（论文 D3）；partition 过多使传输占比飙升；或 pool 内 GPU 故障/慢节点未被建模。
- **观察 3：MILP 最优计划在同步、锁步到达下成立，但真实 serving 的异步 bursty 到达会引入 D1 初始 batching、D2 跨 partition 排队、D3 网络竞争三类额外延迟。**
  - **证据**：reactive 分布式 scheduler（每 pool 独立 adaptive batching）在 HC2-L 上 load factor 仅 0.71，PPipe 资源预留 scheduler 达 0.92；EfficientNet-B8 上 reactive 的 99% 分位传输达 35.7 ms，远超理论 5.1 ms。
  - **依赖假设**：控制面可周期性重算（约小时级 workload 变化）；数据面能在毫秒级 probe/reserve；SLO 可扣除经验 margin（默认 40%）以桥接 plan 与 runtime。
  - **可能失效场景**：极端 burst 使任何 batching 都超时；margin 调错导致 plan 与 runtime 长期偏离；或 scheduler 单点成为瓶颈（论文称开销可忽略，但未测超大规模）。
- **假设 1：视频分析 serving workload 可用 Azure Function (MAF) serverless trace 代表，且 CNN 模型集合覆盖主要生产场景。**
  - **证据强度**：中。MAF 被 AlpaServe 等沿用，有 Poisson 与 Bursty 两种模式；但 trace 源自 serverless 而非摄像头流，多模型并行用 round-robin 分配比例也较简化。
- **假设 2：vision 模型在 datacenter GPU 上不是 memory 瓶颈，MILP 可忽略 GPU memory 约束。**
  - **证据强度**：中。对 18 个 CNN 合理，但论文未讨论超大 feature map、多租户共置或 concurrent 多 pipeline 的显存压力。
- **假设 3：分区边界 float16 [[Quantization]] 不影响任务精度。**
  - **证据强度**：强（在该实验集上）。识别/检测/分割 accuracy drop 仅 0.00%–0.01%；但未覆盖更敏感任务或更大模型。

## 核心方法

PPipe 分为 offline profiling、MILP **控制面**、资源预留 **数据面** 三阶段，回应上述观察。

**Pool-based pipeline parallelism**：每个 model partition 绑定一个同类型 GPU **pool**，请求顺序经过各 partition，但在每个 pool 内可走任意 GPU。与训练式单链 [[Pipeline-Parallelism]] 不同，各 pool 可有不同 GPU 数 $N_i$、latency $t_i$、统一 batch size $b_i$，只要吞吐匹配且 E2E latency 低于 SLO。一个集群可同时跑多条 pooled pipeline，对应不同分区方案。

**MILP 控制面**：输入为各层（经 pre-partition 后的 block）在不同 GPU 类型、batch size、virtual GPU 份额下的 profile、集群各类型 GPU 数量、互联带宽与 SLO。决策变量包括分区起止层、每条 pipeline 的 GPU 类型/数量/batch size。约束包括：每条 pipeline 总 latency（推理 + feature map 传输）≤ SLO；各 GPU 类型用量不超库存；pipeline 吞吐受最慢 partition 限制。默认目标最大化集群总吞吐；多模型时最大化最低归一化吞吐。为缓解 C1 搜索空间爆炸，先把平均 613 层的模型按选定 GPU 上的 runtime **pre-partition** 成 $N{=}10$ 个近似等时 block，MILP 只在 block 边界选点，求解时间从 80 层直接搜的 7+ 小时降到平均 **3.5 s**。

**Batch size unification + virtual GPU**：为简化数据面跨 partition 的 batch split/merge，同一 pooled pipeline 内强制统一 batch size。高端 GPU 倾向更大 batch，于是引入 1/1、1/2、1/3、1/4 **virtual GPU**（运行时靠 NVIDIA [[MPS]]），让 MILP 在统一 batch 下仍能为不同 partition 分配合适算力份额。

**Resource-reservation adaptive batching 数据面**：对每个待调度 batch，(1) 对各 pipeline 以 MILP 统一 batch size 调用 `probe()`，选 waiting time 最低者；(2) 从该 batch size 向下搜索最大可满足队首请求 deadline 的 batch；(3) `reserve()` 占用 GPU 与 uplink/downlink 带宽的时间区间。`probe()` 贪心地为每个 pool 选最早完成的 GPU，并保证发送端 uplink 与接收端 downlink 同时可用。节点执行后 **feedback correction** 修正预留表；控制面另从 SLO 扣除 **40% margin** 使 runtime batch size 尽量贴近 MILP 计划。实现上控制面 2.7 kLOC Python + Gurobi，数据面 9.0 kLOC（Java 离散事件模拟器 + Julia/C++ 原型，NCCL 传 feature map）。深度细节回 [[atc2025-kong]] 或 [[source_pdf]]。

## 设计取舍

- **用 MILP 全局最优换求解复杂度与运行时近似**：MILP 假设同步到达、忽略 memory，需 pre-partition、virtual GPU、SLO margin 和独立数据面来弥补；收益是异构资源与多 pipeline 组合可被 holistically 优化。GPU 类型增至 4 时求解约 77 s，仍可接受小时级重规划。
- **用 pool 灵活性换调度与实现复杂度**：相对 DART-r 的固定 chain，pool 要在 pipeline 选择、path 选择、batch size、网络双向带宽上联合决策；收益是低端 GPU 超额库存可被吃满，吞吐匹配不再要求 stage latency 相等。
- **用 batch 统一 + MPS 换数据面可实现性**：避免跨 stage merge/split；代价是高端 GPU 可能被迫缩小有效 batch，且同机多 vGPU 加剧 NIC 共享 contention（D3），必须靠资源预留而非静态带宽均分。
- **用 pre-partition 降搜索空间换分区粒度**：$N{=}10$ 是经验平衡点；更细则 MILP 变慢，更粗则可能错过层间 latency ratio 突变处的最优切点。
- **用周期性 plan 迁移换 workload 适应性**：负载比例变时重跑 MILP 并 flush pipeline，停机约 1× SLO（百毫秒级）；相对小时级触发可忽略，但论文未讨论迁移期间 in-flight 请求与多租户隔离。
- **边界条件**：SLO 设为最快 GPU（L4）batch=1 延迟的 5× 时收益最大；2× 过紧时 PPipe 退化为类似 NP 的全高端 GPU；10× 过松时 NP 也能直接用低端 GPU，gap 缩小。高端 GPU 占比越高（12:4），PPipe 相对 NP 提升从 64% 降到 5.6%。

## 实验与结果

- **环境**：4 组异构集群 HC1–HC4（L4/P4、L4/T4、V100/P4、V100/T4）；大配置 100 GPU 离散事件模拟，小配置 16 GPU GCP testbed。有效网络带宽取标称值 1/5 以反映 GCP tail latency。18 个 CNN，覆盖识别/检测/分割；workload 来自 MAF 2019（Poisson）与 2021（Bursty）。
- **主结果（100 GPU，99% SLO attainment）**：PPipe 相对 NP 平均 load factor 高 48.0%（Poisson）/ 75.1%（Bursty）；相对 DART-r 高 32.2% / 35.8%。低端 GPU 利用率 NP 8.1%、DART-r 29.5%、PPipe **73.6%**，高端 GPU 三者均高。Bursty 下各框架 load factor 下降，但 PPipe 仍保留大部分相对优势（相对 NP 仍达 90.3% Poisson 水平）。
- **Testbed（16 GPU）**：相对 NP 高 42.6%–52.8% load factor；相对 DART-r 高 16.7%–34.1%。模拟器结论在真实 GCP 上方向一致。
- **Ablation**：资源预留数据面 vs reactive 分布式 batching，HC2-L 上 0.92 vs 0.71 load factor；说明网络 contention 跟踪是主要增益来源之一。
- **开销**：MILP 平均 3.5 s；100-GPU 集群每 batch 调度平均 3.58 次 `probe()`，总开销 < 9 μs。分区边界 float16 量化 accuracy drop ≤ 0.01%。
- **敏感性**：SLO margin 40% 时相对 NP 增益最大（52.8% on HC1-S）；20%/60% 仍有 24.9%/16.4%。MILP 随 GPU **实例数** 增至 100k 几乎不变，随 GPU **类型数** 增至 4 约 77 s。

## Critical Analysis

### 论证链条

主链条较完整：测量证明 per-layer latency ratio 非均匀 → GPU-aware 分区可把「慢卡擅长的层」offload 出去 → pool 结构解决 GPU 数量不均与 stage latency 不匹配 → MILP 在 profile 数据上给出吞吐最优 plan → 异步到达与网络 contention 由资源预留数据面闭合 → 模拟与 testbed 上吞吐、利用率、SLO 三线提升。

较弱环节是把 MAF serverless trace 外推到摄像头视频流 serving。论文沿用了 AlpaServe 等惯例，但没有用真实 video pipeline DAG（多模型级联、帧采样率变化）验证。另一个跳步是「CNN 非 memory-bound」：18 个模型内成立，但未证明对更大分辨率、多路并发 pipeline 仍成立。

### 假设压力测试

**模型族迁移**是最大压力点。结论明确写在 future work：Transformer 视频模型、LLM 视觉骨干的层特性与 activation 尺寸不同，per-layer ratio 规律可能消失，分区传输成本可能主导。当前 18 CNN + MAF trace 不能支撑对「异构 serving 通用解法」的外推。

**硬件与云环境**也敏感。实验绑定 GCP 机型与 1/5 有效带宽；换 AWS、on-prem 拓扑或更新 NIC 共享策略，D3 与 margin 需重标定。MPS virtual GPU 的隔离性与性能干扰论文一笔带过，多租户同机共跑时 vGPU 是否稳定未被测试。

**负载形态**：Bursty trace 已比 Poisson 难，但仍是单入口请求流；真实 video analytics 有 per-camera 独立到达、关键帧抽样、多租户混合模型。论文未讨论多 DNN DAG（Inferline 类）与 partition pipeline 的组合。

### 实验可信度

Baseline 设计相对公平：NP 与 DART-r 也接入 PPipe 数据面，主对比隔离了 pool vs chain / partition vs no-partition 的收益；§7.4 单独验证数据面。100 GPU 模拟 + 16 GPU 真机、4 种 GPU 配比、18 模型，覆盖面在 ATC 系统论文中属扎实。

缺口包括：未与 AlpaServe（homogeneous pipeline + 多模型复用）在相同异构集群上对比；DART 原版 CPU+GPU 链未测；生产 video DAG workload 缺失。99% SLO 是聚合指标，tail latency 分布、drop 原因分解、迁移瞬间抖动论文着墨不多。Gurobi 商业求解器也影响可复现性与部署成本，论文未讨论开源 solver 替代。

### 系统性缺陷

**故障与弹性**：论文未讨论 GPU 掉线、MILP 求解失败、profiler 漂移、模型版本热更新时的降级策略。pool 内任 GPU 变慢会改变 `probe()` 假设，但无 straggler 显式处理。

**多租户与隔离**：MPS vGPU、共享 NIC 预留表是全局 scheduler 视角，未分析多 job 争抢同一集群时的 fairness 与 SLO 隔离。

**可观测性与运维**：plan 迁移、margin 调参、profile 过期、pipeline flush 对运维是黑盒；论文未提供生产级监控接口或 debug 工具。

**成本面**：更高低端 GPU 利用率降低资源浪费，但 MILP 离线 profile、Gurobi、控制面周期重算与权重预加载的 engineering cost 相对传统整模型 serving 更高，论文未量化 TCO。

## 局限与 Future Work

- **局限 1**：评估限于 18 个 CNN 与 MAF trace，未覆盖 transformer 视频模型、多模型 DAG pipeline、或 memory-heavy 大分辨率输入。
- **局限 2**：MILP 忽略 GPU memory，且默认最多 3 partition、2 GPU 类型组合；更大搜索空间与 memory 约束下的可扩展性未验证。
- **局限 3**：网络与 margin（40%）高度依赖 GCP 测量；跨云/跨代硬件需重新 profile 与标定，论文未给出自动化 recalibration 流程。
- **局限 4**：故障恢复、多租户隔离、straggler 与 plan 迁移期间的请求语义论文未讨论。
- **Future work 1**（论文自述）：扩展到 transformer 类模型，研究其在高低端 GPU 间的 partition 与 SLO 满足策略。
- **Future work 2**：用真实 video analytics production trace（per-camera 到达、多阶段 DAG）测量 pool pipeline 相对 whole-model placement 的收益边界。
- **Future work 3**：将 GPU memory、多 partition 上限、开源 MILP solver 纳入控制面，量化 plan 质量与求解时间的 trade-off。
- **Future work 4**：在共享 NIC / 多租户场景下测量 MPS vGPU 干扰与资源预留 scheduler 的 fairness，并设计 tenant-aware reservation。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Continuous-Batching]]、[[Quantization]]、[[Tensor-Parallelism]]、[[Adaptive-Batching]]、[[Heterogeneous-Cluster]]
- **同类系统**：[[AlpaServe]]、[[DART]]、[[Hercules]]、[[Inferline]]、Clipper、Clockwork
- **同会议**：[[ATC-2025]]
- **对比**：pool-based vs chain-based [[Pipeline-Parallelism]]；PPipe 数据面 vs reactive per-pool batching（§7.4）