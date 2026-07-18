---
type: paper
name: Cosmic
full_title: "Cosmic: Cost-Effective Support for Cloud-Assisted 3D Printing"
authors: [Yuan Yao, Chuan He, Chinedum Okwudire, Harsha V. Madhyastha]
venue: ATC
year: 2025
tags: [serverless, 3d-printing, latency-sensitive, aws-lambda, speculation]
source_pdf: "[[atc2025-yao.pdf]]"
source_md: "[[atc2025-yao]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Cosmic: Cost-Effective Support for Cloud-Assisted 3D Printing (ATC 2025)

> **一句话总结**：LPBF 打印的 SmartScan 控制器要求每个 ~50 ms 时间窗内完成温度矩阵乘法，但 warm [[AWS Lambda]] invocation 中位延迟就有 10.2 ms；Cosmic 用 cell grouping + 近似温度图投机预调度 + 穷举配置搜索，在 30 个打印任务上全部满足时序约束，相对 VM 中位省 2.8× 成本、相对其他 serverless 方案省 2.8×–3.5×。

## 问题与动机

论文关注一种此前 [[Serverless]] 文献几乎没碰过的 workload：把 3D 打印机控制算法搬到云上实时执行。具体场景是 laser powder bed fusion（LPBF）打印中的 SmartScan 控制器——它要在每个时间窗（time window）内决定下一个要激光扫描的 cell，以优化层内温度均匀性、减少残余应力和变形。

这个 workload 和以往 serverless 应用（视频处理、GNN 训练、稀疏图计算）有本质区别：每个 step 的计算窗口只有几十毫秒，而不是秒级或分钟级。作者测量发现，即便在 warm worker 上，[[AWS Lambda]] / Azure Functions 的 function invocation 中位延迟仍有 10.2 ms（p90 13.2 ms），足以让 naive serverless 实现违反 SmartScan 的时序约束。

本地执行也不可行。SmartScan 每步要做温度向量与 heat transfer 矩阵的乘法；以 16 cm² 齿轮为例，单个 cell 矩阵 11.92 GB，127 个 unique matrix 合计 1514 GB，远超打印机 onboard memory；本地 CPU 单次矩阵乘法约 450 ms，而 600–800 mm/s 打印速度下时间窗仅 38–62 ms。超时则打印机 fallback 到随机扫描顺序，打印质量下降。

传统方案是用高内存 VM fleet 常驻全部矩阵。但层间铺粉固定 idle 15 s，太短无法 suspend/resume VM，用户要为 idle 付费；且 VM 从 EBS 按需读 11.92 GB 矩阵要 350 ms，同样无法满足时序。Serverless 的 pay-per-use 和 warm start 免费保留 in-memory state 看似匹配，但简单映射（每 cell 一个 function、按需 invoke）在 4 cm² 齿轮单层就因 invocation + 网络开销多出 2.98 s，总 4.28 s 超过 3.33 s 打印约束。

Cosmic（Cost-effective Serverless for Millisecond Computations）的目标是在 expanded configuration space 里找到**最便宜且能满足时序**的 serverless 部署方案，并给出可复用的 runtime。

## 关键观察 / 隐含假设

- **观察 1：SmartScan 的瓶颈不是纯计算，而是 invocation overhead 与 coordination overhead 的此消彼长**。Invoke-on-demand 每窗都吃 ~10 ms invocation；All-active 把矩阵切到 159 个 worker 并行，但 coordinator 每步要向全部 worker 推 312 KB 温度图，单步最高 50 MB 传输，单层 16 s 远超 13.3 s 约束，其中 270 ms 是实际计算、其余是 coordination。
  - **依赖假设**：coordinator VM 到 Lambda worker 的带宽是系统瓶颈（作者用 iperf 测得约 5 Gbps），且 heat transfer 矩阵的全连通性要求每个 worker 收到完整输入温度图。
  - **可能失效场景**：平台提供 direct worker-to-worker 通信、更低 invocation 路径、或矩阵结构稀疏到可只传局部温度子图时，All-active 的 coordination 假设会弱化。
- **观察 2：相邻时间窗若选中同一 worker group，可完全避免 invocation overhead**。把 N 个 function 分成 G 组、每组承担 1/G 的 cell，连续两窗若落在同组，第二窗无需重新 invoke；作者 ablation 显示 grouping 单独就能把 Invoke-on-demand 的 7/30 可行任务扩到 9 cm² 和 16 cm² 全部可行。
  - **依赖假设**：cell 选择序列在时间上存在局部性，使 group reuse 概率足够高；且 G 不能太大（否则每窗几乎必 invoke）也不能太小（否则 coordination 爆炸）。
  - **可能失效场景**：温度分布导致 SmartScan 在层内频繁跳跃到远距 cell、或 part geometry 使 cell 数极少时，grouping 收益下降。
- **观察 3：用近似温度图（只加 laser 输入、忽略短窗内热扩散）可在 coordinator 侧低成本预测下一 cell，投机命中率约 85%**。扫描单 cell 仅数十毫秒，完整热扩散可延后到 serverless worker 精确计算；近似图不能替代真算法（累积会偏离真实状态），但足以猜 group。
  - **依赖假设**：laser 输入 dominate 短窗内温度变化，且同一 part 的历史打印可估计 speculation accuracy（实测 85% ± 5%，对 30 种初始温度图稳健）。
  - **可能失效场景**：打印速度更快、材料热导率更高、或层内 cell 竞争更激烈时，近似预测准确率下降，投机 invoke 要么浪费成本要么仍 miss deadline。
- **假设 1：warm start 在层间 idle（数十秒）内高度可靠，且 idle memory 不计费**。
  - **证据强度**：强。24 h 实测 50 ms–1 s 间隔 cold start <0.1%；5 s–1 min 间隔 cold start 0.6%–3.2%。作者用 dummy request 保活跨层 worker，成本可忽略。但这是平台行为而非 SLA 保证。
- **假设 2：评估对象限于 z 轴对称 part，使每层 heat transfer matrix 可跨层复用**。
  - **证据强度**：中。简化了数据预计算和 warm state 复用，但限制了工业零件的一般性；非对称 part 每层 matrix 不同，内存与配置搜索复杂度会显著上升。
- **假设 3：打印任务可用 desktop 模拟器 + 真实 SmartScan controller 代表未来工业部署**。
  - **证据强度**：中偏弱。现有 LPBF 打印机驱动只接受预计算序列，论文未在真实打印机上闭环验证；模拟器能精确复现 laser timing 和温度 map 上传，但网络抖动、打印机固件行为、红外相机噪声等 production 因素未覆盖。

## 核心方法

Cosmic 把 serverless 部署抽象为三维配置空间：**cells per group**、**functions per group**、**invocation 策略**（全 persistent / 投机 / 无）。相对文献中三种点解——Invoke-on-demand（G=N）、All-persistent（层初 invoke 全部 function 并挂起至层结束）、All-active（G=1，全 worker 每步活跃）——Cosmic 允许中间 grouping 与投机组合。

**Grouping** 回应观察 1 和 2：在 invocation overhead 与 coordination overhead 间插值。G 小则每步广播目标 worker 少、网络压力低，但 invocation 频繁；G 大则 invocation 少（尤其连续同组 cell），但 coordinator fan-out 增大。每个 group 内 function 数至少能装下该组全部 cell 的 heat transfer matrix。

**Speculation** 回应观察 3：在当前 window 执行期间，coordinator 用近似 SmartScan 预测下一 cell 所属 group，在预计当前 window 结束前 D ms（D = invocation 延迟分布中位数）发起 speculative invoke。命中则下一窗零 invocation 等待；未命中则仍受 invocation 延迟惩罚，但比 All-persistent 少付 idle worker 费用。投机时机平衡成本与掩盖延迟：过早 invoke 增加 billable idle，过晚则 miss deadline；实测 95% 投机实例 billable idle ≤2 ms、latency overhead ≤1.24 ms。

**配置选择与性能模型** 在 print job 开始前约 10 s 穷举全部可行配置。模型输入为 part 特征（cell 数、matrix 大小、温度图大小）、配置参数、平台 profile（invocation 延迟分布、coordinator–worker 带宽、矩阵乘法时间分布）。Per-window 时间拆为两阶段：invoke/投机阶段（按策略、reuse 概率、speculation accuracy 采样延迟）和 coordination+compute 阶段（按 fan-out 和矩阵规模估算）。在满足「单层 runtime < 打印单层时间」的配置中选最低 dollar cost。极端情况下判定不可行并 fallback 到 VM fleet。

**Runtime** 由 coordinator VM（m6g.8xlarge，同 VPC、关 TCP slow start） orchestrate：job 初一次性 invoke 全部 function 预加载 matrix；层内按选定配置 invoke 或投机；每步收集 worker 输出、运行完整 SmartScan 选真 cell、并行维护近似版供下一窗投机。打印机失联时 fallback 随机顺序——这是 cloud-assisted control 的 graceful degradation。

深度实现与公式回 [[atc2025-yao]] 或 [[atc2025-yao.pdf]]。

## 设计取舍

- **穷举配置搜索换最优 cost-timing 点**：10 s 枚举对 30 个 evaluated part 可行，但 part 更大、cell 更多时搜索空间指数增长；换来的是比固定策略（Invoke-on-demand / All-active）更强的 Pareto 覆盖。
- **近似投机换低延迟 invoke 掩盖**：不牺牲 SmartScan 正确性（真算法仍在 worker 跑），但增加 coordinator 侧双轨逻辑；近似误差累积若被误用为真状态会伤质量，故仅限预测用途。
- **ARM Lambda 大规格 worker 换更少并行度**：10 GB / 6 vCPU function 减少 group 数和 coordination fan-out，也提高 speculation accuracy；代价是单 worker 单价更高，且结论绑定 AWS ARM Lambda 定价与性能 profile。
- **对称 part + 预计算 matrix 换跨层 state 复用**：大幅简化内存预算和 warm start 价值；非对称或每层几何变化 part 需重新设计数据生命周期。
- **Desktop 模拟闭环换可大规模重复实验**：避免独占物理打印机、支持细粒度 timing instrumentation；牺牲真实工艺验证与端到端质量 metric（残余应力、变形）的直接测量。

## 实验与结果

- **时序约束**：30 个 job（10 种 part × 9/16/25 cm² 层面积）在 800 mm/s 打印速度下，Cosmic 全部满足每窗 deadline；Invoke-on-demand 仅 7/30；All-active 在 9 cm² 全部可行但 25 cm² 有 11/20 失败；All-persistent 和 VM 全部可行但过配。
- **成本 vs VM**：30 job 中 Cosmic 在 26 个最低成本；相对 VM 中位贵 2.8×、最大 6.3×（Cosmic 更便宜）。1 cm 厚零件平均节省 $1.2 / $4.5 / $18.7（按层面积）；层越大 idle 占比越低（铺粉 15 s 固定），Lambda pay-per-use 优势越大。
- **成本 vs 其他 serverless**：27 个 job 中非 VM 最便宜方案里，Cosmic 在 26 个胜出；相对次优 serverless 方案平均节省 $0.71 / $8.3 / $78.4。整体比「唯一能按时完成的那种 baseline」便宜 2.8×–3.5×。
- **Ablation**：Invoke-on-demand → +grouping → +speculation 逐步把可行 job 从 7 扩到 29（剩 1 个需 all-workers-persistent）；grouping 还降 cost（reuse 避免 invocation）；speculation 在 16 cm² 上进一步降并行度需求。
- **投机质量**：平均准确率 85%，对不同初始温度图 85% ± 5%；投机 timing 中位提前 0.19 ms 就绪，p5–p95 为 −2.00 ms 到 1.24 ms。
- **配置多样性**：30 job 所选 group 数 1–50、组内并行 4–34；仅 3 job 选 all-persistent，21 job 用 speculation。
- **平台测量**：warm invocation 延迟 AWS/Azure 类似；4 cm² 齿轮单层 Lambda 活跃计算 1.30 s + overhead 2.98 s = 4.28 s > 3.33 s 打印时间。

## Critical Analysis

### 论证链条

论文链条清晰：先证明 SmartScan 无法本地跑（内存 1514 GB、450 ms compute vs 50 ms window）→ VM 方案 idle 和 I/O 成本过高 → serverless 有 pricing/warm-start 优势但三种 naive 映射分别死在 invocation（23/30 超时）或 coordination（大 part 16 s/layer）或 cost（All-persistent）→ Cosmic 扩展配置空间并用测量驱动模型选点 → 30 job 全部 timely 且 26/30 最便宜。

最强证据是 ablation（Figure 16/17）：grouping 和 speculation 各自解决不同 failure mode，与 design 动机一一对应。Invocation 延迟测量（Figure 7）直接支撑「warm start 不够、必须 application-level 掩盖」的核心 claim，这一点区别于大量只攻 cold start 的 [[Serverless]] 工作。

较弱跳步是把「3D 打印 cloud control」外推到 AR/VR、在线游戏、自动驾驶车队（Section 7）。这些场景虽有「预加载大数据 + 毫秒决策」形式相似性，但输入预测结构、failure mode、和 dollar cost 模型差异很大；论文未对任一额外 workload 做 profile，泛化仍属设计层面类比。

### 假设压力测试

**Workload**：SmartScan 是顺序、每步依赖上步温度状态的线性 pipeline；Cosmic 的 window-by-window 模型据此成立。若控制算法有分支、批处理多 printer、或允许异步 quality degradation，时序约束和投机逻辑需重写。铺粉 15 s idle 占 9 cm² job 总时间 73%、25 cm² 仍占 49%——Cosmic 的成本优势高度依赖「长 idle + 短 burst compute」节奏；连续扫描型工艺 idle 少，VM 常驻可能更划算。

**硬件 / 部署**：实验在 AWS 单 region，coordinator 与 Lambda 同 VPC；未测跨 region、跨 AZ 延迟、printer 到 cloud 链路抖动。工业 LPBF 车间网络质量若差于 datacenter 内 RTT，coordinator–printer 往返可能成为新瓶颈，论文未讨论。

**规模**：25 cm² 已需最多 50 groups、34 parallel functions/group；论文承认更大 part 的 communication scalability 是 open problem。配置穷举 10 s 在 evaluated part 可行，但 cell 数百上千时搜索与建模本身可能成为 job 启动瓶颈。

**正确性 / SLO**：时序 SLO 在模拟器上验证，未测打印质量（温度均匀性、变形）是否因投机 miss 或近似误差而下降。打印机失联时 fallback 随机扫描——可用性设计合理，但 cloud control 的 safety 与 certification 论文未触及。

### 实验可信度

**Benchmark**：10 种 part 来自 PBF 优化文献和工业造型，3 种层面积覆盖 131 GB–1514 GB 内存需求、38–62 ms 时间窗，多样性较好。但是 simulated printer，非 production trace 驱动的 arrival pattern；每个 job 独立，未测多 printer 共享 coordinator 或并发 job 干扰。

**Baseline**：Invoke-on-demand / All-persistent / All-active 忠实复现 prior serverless 文献策略，且 VM baseline 用 x2gd 高内存比、并扫描 N 取最便宜可行解——对比算公平。4 个 job 上 Cosmic 非最便宜（0.17×–0.94× 有更优解），其中 1 个是模型误估（All-active 实际更便宜），说明模型不是 oracle，但整体 26/30 占优。

**Metric**：覆盖 timing satisfaction、dollar cost、ablation、speculation accuracy/timing；缺 tail latency 分布（仅 median/p90 invocation）、缺真实打印质量、缺 operator 复杂度与故障恢复时间。成本归一化到 Cosmic 便于比较，但未给绝对 cloud bill 敏感性与 region 差异。

### 系统性缺陷

- **平台依赖与定价风险**：核心收益建立在「warm idle memory 免费 + 仅按执行时间计费」；若云厂商缩短 warm 窗口或单独收取 idle memory（Section 7 讨论），Cosmic 需 re-profile 并可能退化到 dummy keep-alive 或更高 persistent 比例，节省倍数会缩小。论文讨论了适应性但未量化新定价下的 break-even。
- **Coordinator 单点**：所有 temperature map fan-out 和 SmartScan 真/近似双轨都在单 VM；更大规模或更高打印速度下 coordinator CPU、网络 egress、故障恢复（论文未讨论）可能成为 fragility。没有 HA coordinator 或 printer-side buffering 设计。
- **可观测性与运维**：配置搜索、投机 miss、group reuse 统计如何暴露给 operator、如何 debug 某层 timeout，论文未描述。30 job 实验是离线 batch，非长期运行 monitoring。
- **模型–现实偏差**：已出现 1/30 job 模型选错配置；heavy-tailed invocation 分布用 per-window 独立采样，未验证相关性（如同一 worker 连续 invoke 是否更快）。对 production 需 online adaptation 或 safety margin，论文未实现。
- **安全与多租户**：Lambda function 预加载 1.5 TB 级 part-specific matrix，tenant 隔离、数据驻留合规、matrix 更新版本管理，论文未讨论。

## 局限与 Future Work

- **局限 1**：评估基于 desktop 模拟器，真实 LPBF 硬件尚未支持动态 SmartScan 闭环；Future work 应在支持红外反馈的工业机上测 end-to-end 打印质量与网络鲁棒性。
- **局限 2**：仅限 z 轴对称 part；Future work 应测量非对称 part 每层独立 matrix 对内存、配置搜索时间和 warm reuse 的影响。
- **局限 3**：更大 part 的 coordinator–worker 通信 scalability 未解决；Future work 可测 direct Lambda-to-Lambda 或 DPU offload 能否打破 coordinator 带宽瓶颈。
- **局限 4**：配置穷举与静态 profile 在极端规模下可能过时；Future work 可做 incremental profiling、online speculation accuracy 更新、或学习式配置推荐并量化 misprediction 代价。
- **局限 5**：云定价与 warm-start 政策变化；Future work 应建立 pricing sensitivity analysis，明确 Cosmic 相对 VM 的 break-even 曲面（数据量 × idle 比 × invocation 延迟）。
- **局限 6**：论文声称可推广到其他毫秒级 pipeline；Future work 应至少选 1 个非 3D 打印 workload（如 AR 位姿更新）完整走通 profile → 配置搜索 → runtime，验证 grouping/speculation 抽象是否足够 workload-agnostic。

## 相关

- **相关概念**：[[Serverless]]、[[Speculative-Execution]]、[[FaaS]]、[[Cold-Start]]、[[AWS-Lambda]]
- **同类系统 / 机制**：SmartScan、Sprocket、Dorylus、SpecFaaS、Xanadu、ORION、ProPack、InfiniCache
- **同会议**：[[ATC-2025]]
- **可对比论文**：[[BurstComputing-ATC25]] 从 job-level 视角优化 serverless 并行突发任务；[[RTSFaaS-ATC25]] 用 RDMA 降低 stateful serverless 事务延迟；[[Torpor-ATC25]] 在 GPU serverless 推理中用 late binding 换资源效率
