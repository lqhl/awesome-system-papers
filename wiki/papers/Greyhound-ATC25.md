---
type: paper
name: Greyhound
full_title: "Greyhound: Hunting Fail-Slows in Hybrid-Parallel Training at Scale"
authors: [Tianyuan Wu, Wei Wang, Yinghao Yu, Siran Yang, Wenchao Wu, et al.]
venue: ATC
year: 2025
tags: [llm-training, fail-slow, straggler, hybrid-parallelism, characterization]
source_pdf: "[[atc2025-wu-tianyuan.pdf]]"
source_md: "[[atc2025-wu-tianyuan]]"
---

# Greyhound: Hunting Fail-Slows in Hybrid-Parallel Training at Scale (ATC 2025)

> **一句话总结**：在 10K+ GPU 阿里生产集群上，fail-slow 以短暂计算退化与更持久的网络拥塞形式出现，使 ≥512 GPU 大作业平均 JCT 拖慢 1.34×；Greyhound 用 LD_PRELOAD hook [[NCCL]] + BOCD 在线变点检测定位慢 GPU/链路，再以 ski-rental 式四级缓解（micro-batch 重分配 → topology 调整 → checkpoint-restart）在 256 H800 上端到端吞吐提升 1.58×、检测准确率 99.8%。

## 问题与动机

大规模 [[LLM-Training]] 在 [[Tensor-Parallelism]]、[[Data-Parallelism]]、[[Pipeline-Parallelism]] 混合并行下，每个 iteration 边界都要同步，任一计算或通信组件变慢都会把整个 job 拖成 straggler。这类 **fail-slow**（组件仍运行但性能退化）与 fail-stop（挂死/崩溃）不同：不会触发明显错误，却长期侵蚀吞吐。业界在 ByteDance MegaScale、Meta Llama 3 等报告里零星提及，但缺乏系统化的生产表征和自动化应对方案。

当前实践主要靠人工发现 fail-slow，然后按 fail-stop 处理——[[Checkpointing]] 后重启到健康节点。这对动辄数周、数千 GPU 的训练 job 代价极高：论文引用 GPT2-100B checkpoint dump 近 100 分钟，而生产集群 fail-slow 平均持续约 72 分钟。更糟的是，简单 telemetry（GPU SM 利用率、RNIC CNP）在同步训练下几乎无用：straggler 出现时**所有 GPU 利用率一起掉**；多租户集群里链路共享，CNP 激增也不等于本 job 通信变慢。

Greyhound 要回答两个问题：(1) hyperscale hybrid-parallel 训练里 fail-slow 到底长什么样、多严重；(2) 能否在不停全 job、不依赖特定训练框架的前提下，自动检测并分级缓解。

## 关键观察 / 隐含假设

- **观察 1：fail-slow 是短暂、可恢复的，计算与通信根因分布不同。** 在 10K+ GPU、4000 节点、RoCE spine-leaf 的阿里共享集群上，499 个 probing job 显示：单节点计算 fail-slow 发生率 <2%（6/392），平均持续 10 分钟，JCT 拖慢 11.79%，主因 CPU contention 与 GPU thermal throttling；4 节点 probing 中 42/107 遇通信 fail-slow，平均持续 24 分钟，JCT 拖慢 15.45%，几乎全是网络拥塞。
  - **依赖假设**：probing job 的 GPT2 规模与混合并行配置能代表生产大 job 的 per-node/per-link 压力形态；spot job 随机调度能采样到集群中代表性的 contention 模式。
  - **可能失效场景**：probing 规模远小于 512–1024 GPU 生产 job，无法复现跨 spine 的多路径拥塞叠加；专用 8×GPU/节点 大 job 不走 CPU colocation，计算 fail-slow 画像会变化。

- **观察 2：规模放大后 fail-slow 更频繁、更持久、常复合出现。** 2024 年 7 月 trace 中 27 个 ≥512 GPU 大 job，16 个遇 fail-slow，平均持续 72 分钟，JCT 平均拖慢 34.59%，20% 拖慢 >50%；13 个纯网络拥塞，3 个网络+GPU 复合。Case study 显示 1024-GPU job 可同时遭遇长达数小时的网络拥塞与 GPU 温控，吞吐可跌至正常的 10%。
  - **依赖假设**：大 job 独占 8×GPU/节点、不与其他 workload colocate，因此 CPU contention 可忽略，fail-slow 以网络为主；同步 barrier 使局部退化立即传播到全局 iteration time。
  - **可能失效场景**：异步训练、gradient accumulation 不等 barrier、或 pipeline bubble 足够大能部分掩盖 straggler 时，观测到的 JCT 影响会变小。论文未评估这些训练范式。

- **观察 3：iteration time 可从 NCCL 通信调用序列在线恢复，且 slow iteration 可用统计变点检测。** Greyhound-DETECT 用 ACF 从 hook 到的 AllReduce/AllGather 等调用序列推断 recurring period，相对 ground truth iteration time 误差 <1.2%；BOCD + 前后均值差 >10% 的 verification（BOCD+V）在计算 fail-slow 上 100% 准确、通信 fail-slow 上 99.1%，FPR 均为 0。
  - **依赖假设**：训练框架最终都走标准 collective 接口（NCCL/ACCL 等 top-level API 一致）；iteration 内通信模式稳定，ACF 能找到清晰周期；fail-slow 表现为 iteration time 跃升 ≥10%。
  - **可能失效场景**：自定义通信库、频繁改变 parallel topology、或 fail-slow 仅在某些 compute+comm 交织模式下出现（论文承认无法检测这类 rare co-execution pattern）时，周期推断与变点检测可能失效。

- **假设 1：fail-slow 持续时长未知，缓解策略应按「租金 vs 买断」在线升级。** 四级策略 S1（忽略）→ S2（DP micro-batch 重分配）→ S3（PP/DP topology 调整）→ S4（checkpoint-restart）效果递增、开销递增；累计 slowdown 达到下一档 action overhead 时才升级，类比 ski-rental 问题。
  - **证据强度**：中。256-GPU 注入实验显示端到端有效，但 ski-rental 阈值依赖预估的 strategy overhead，真实生产里 overhead 随模型规模、存储带宽、调度器行为波动；论文未做 sensitivity analysis。

- **假设 2：短暂挂起训练做 targeted micro-benchmark 比全集群 SuperBench 式验证可接受。** validation 阶段 trap NCCL 调用挂起 job，对可疑组跑 GEMM 与 O(1) Ring/Tree P2P 测试，正常 GPU 上 <5 s，fail-slow 下仍 <5 s 总开销。
  - **证据强度**：强（testbed 有数字）。但挂起本身在极长 pipeline 或复杂 optimizer state 下是否引入隐性副作用，论文未讨论；多租户集群里暂停是否触发调度器抢占也未覆盖。

## 核心方法

Greyhound 拆成检测与缓解两个子系统，对应「先定位、再按代价递进处理」。

**Greyhound-DETECT**（framework-agnostic，约 5.5k LOC C++/Python）采用 master-worker 三阶段 workflow：

1. **Tracking**：每个 worker 通过 `LD_PRELOAD` shim hook [[NCCL]] 顶层 collective（AllReduce、AllGather、ReduceScatter 等），记录调用类型与时间戳；LocalAnalyzer 用 ACF 找 recurring period，推算 iteration time，再用 BOCD 在线找变点，并用前后窗口均值差 >10% 过滤 jitter。
2. **Profiling**：检测到 slow iteration 后，GPU Monitor 在 intercepted NCCL 调用中注入 CUDA event，测量各 communication group 耗时；GlobalAnalyzer 把同数据量的 group 聚成 comparable cluster，执行时间超 median 10% 的标为可疑组——把搜索空间从全集群缩到少数 group。
3. **Validation**：对可疑组 trap NCCL 调用短暂挂起训练（无需 checkpoint），并行跑 GEMM 算力测试与 Ring/Tree 拓扑的 O(1) P2P 带宽测试，定位慢 GPU 或慢链路。

worker 通信用 shared memory + Redis；benchmark 复用训练 CUDA context 与 NCCL communicator，避免重初始化开销。检测模块与 [[Megatron-LM]]、[[DeepSpeed]] 等框架解耦，只依赖底层通信库接口一致性。

**Greyhound-MITIGATE**（Megatron-LM plugin，约 1.5k LOC Python）接收 Redis 中的 straggler ID，按 ski-rental 启发式选择四级策略：

- **S1 Ignore**：等待自恢复，零开销，对长时拥塞无效。
- **S2 Adjust micro-batch**：针对计算 straggler，用 [[Data-Parallelism]] 组内 profile 到的 per-microbatch 时间 $t_i$，解 QP 最小化各组 $m_i t_i$ 方差（cvxpy，512 DP 组仍 <36 s），配合 weighted gradient aggregation 保持训练语义不变；不改 global batch size 与 micro-batch 大小，[[Pipeline-Parallelism]] 1F1B 峰值显存不受影响。
- **S3 Adjust topology**：针对通信 straggler，把拥塞链路从 heavy-traffic DP group 换到 light-traffic PP group（PP 每 GPU 流量通常比 DP gradient sync 小两个数量级）；多个 straggler 时合并到最少 PP stage，利用「同 stage 内只取最慢者」降低 pipeline 拉长。
- **S4 Checkpoint-restart**：最后手段，替换慢组件。

topology 调整通过 pause → 内存 dump 参数 → P2P RDMA swap → resume 实现，约 1 分钟，比 disk-based C/R 暂停时间最高省 6.72×。深度实现细节回 [[atc2025-wu-tianyuan]] 或 [[atc2025-wu-tianyuan.pdf]]。

## 设计取舍

- **非侵入检测 vs 框架内缓解。** DETECT 用 LD_PRELOAD 保持 framework-agnostic，部署成本低；MITIGATE 必须改 Megatron-LM 的 micro-batch 分配与 topology，无法做到完全透明。换用 FSDP、自定义 parallel runtime 需重新集成缓解逻辑。

- **短暂挂起 vs 全 job benchmark。** 相比 [[SuperBench]] 式停训全量验证，Greyhound 只对可疑组做秒级测试，把定位开销压到可忽略；代价是 validation 窗口内训练完全停顿，且 trap NCCL 的实现复杂度与 deadlock 风险由工程承担。

- **Ski-rental 渐进缓解 vs 立即激进动作。** 避免对短暂 fail-slow 过度反应（micro-batch/topology 调整也有数十秒到分钟级开销）；但若 fail-slow 一开始就极严重，S1 等待会白白损失大量 iteration。阈值基于预估 overhead，缺少在线学习。

- **Topology 调整利用 PP 轻流量特性。** 在 DP 拥塞时把链路让给 PP 有效（severe congestion 下 iteration time 最高缓解 1.23×），但要求 PP stage 划分允许 swap、且 straggler 数量不超过单 stage GPU 数；全部链路都慢时无调整空间。

- **生产表征 + 受控注入评估。** 10K GPU 集群 trace 与 probing 提供罕见的一手 fail-slow 数据；256-GPU 有效性实验用 nvidia-smi 锁频与 side-channel 带宽争抢注入，可控但未必覆盖真实 thermal、固件、RNIC 硬件退化等根因。

## 实验与结果

- **生产表征**：10K+ GPU 集群，392 单节点 / 107 四节点 probing + 27 个 ≥512 GPU 大 job trace；大 job 59% 遇 fail-slow，平均 JCT 拖慢 34.59%，复合问题可使吞吐跌至 10%。
- **检测准确率**：BOCD+V 对 499 probing job 与人工标注 cross-validation，整体 498/499（99.8%）；计算 fail-slow 100%（392/392），通信 fail-slow 99.1%（106/107），FPR 均为 0；tracking overhead 平均 0.39%，最大 1.1%。
- **Iteration time 估计**：单节点多并行配置相对误差 <1.2%，4 节点 (2TP,4DP) 仅 0.1%。
- **S2 micro-batch**：8 GPU 单节点，单 DP 组 medium fail-slow 下 iteration time 从 1.31s 降到 0.83s（1.59×）；多 DP 组同时慢时调整空间缩小。
- **S3 topology**：16 GPU 两节点，4 PP stage severe congestion 下 iteration time 缓解 1.23×；straggler 合并到单 PP stage 可把 1.6–1.7× 压到 1.3×。
- **256 H800 端到端**：GPT2-40B、(8TP,16DP,2PP)，注入 12 个 fail-slow（含复合场景）；检测 100%、平均反应 10.56 s；无 Greyhound 吞吐从 37.4 降到 18.9 iter/min，有 Greyhound 恢复到 29.8 iter/min（**1.58×**）。

## Critical Analysis

### 论证链条

论文链条整体闭合：**生产测量**证明 fail-slow 普遍且损害大 → **telemetry 不够**说明需要 iteration-level 信号 → **NCCL hook + BOCD** 能在线检测 → **profiling/validation** 能缩小定位 → **分级缓解**比一律 checkpoint-restart 更划算 → **256-GPU 注入实验**验证端到端收益。

最强贡献是第一篇系统的 hyperscale fail-slow 表征：把「大家都说有 straggler」推进到可量化的频率、时长、根因分布，并说明规模放大后的复合效应。检测设计也扎实：framework-agnostic shim、BOCD+V 消融、与 sliding window / 纯 BOCD 对比，说明 verification 步骤不可或缺。

主要跳步在 **「probing + 人工 trace 检查」→「任意生产大 job 上自动化闭环」**。macro-scale trace 靠人工 inspect 16/27 个慢 job，DETECT 工具虽参与 probing，但大 job 上的在线 MITIGATE 未在生产跑；256-GPU 实验是人工注入 schedule，不是真实拥塞 trace replay。

### 假设压力测试

**多租户 vs 专用大 job**：probing 反映 colocated spot workload 下的 CPU/网络 contention；≥512 GPU 大 job 独占节点，根因画像偏向网络。把 probing 上的计算 fail-slow 频率（<2%）外推到所有训练形态会偏低。

**同步训练依赖**：若 job 使用 async pipeline、局部梯度累积、或允许 drop slow update（LLM 生产通常不允许），fail-slow 对 JCT 的放大系数会下降。论文明确面向 state-of-the-art 同步 hybrid parallelism，外推边界需牢记。

**NCCL hook 假设**：LD_PRELOAD 对自定义 collective、MSCCL 图、或 future 通信 runtime 是否稳定，论文只论证 ACCL 接口一致性。Mycroft 式 flow-level trace 与 Greyhound 的 iteration-level BOCD 互补，但论文未对比 Holmes（NSDI'25，同期只检测不缓解）在相同 trace 上的定位精度。

**Ski-rental 阈值**：strategy overhead（S2 QP、S3 参数 swap、S4 checkpoint）在 1T 参数、慢存储、或 cloud 抢占场景下可能远高于论文 testbed，导致该升级时仍在 S1 等待，或不该升级时已触发 S3 扰动 topology。

### 实验可信度

baseline 选择合理：检测侧对比 sliding window 与 BOCD 变体；缓解侧做 S2/S3 分 severity、多 DP/PP 配置消融。生产 499 job 交叉验证是很有说服力的证据。

不足也较明显：(1) **缓解实验全是人工注入**，nvidia-smi 锁频与 side-channel 争抢不能代表真实 thermal、光模块、交换机 buffer 退化；(2) **端到端只有 256 GPU**，相对 claim 的 10K GPU hyperscale 仍差一个数量级，且注入 schedule 已知 ground truth；(3) **MITIGATE 仅 Megatron-LM**，未证明能 plug 到 ByteDance/DeepSpeed 生产栈；(4) **无 tail latency / 收敛性验证**，S2 weighted aggregation 理论上等价，但长期训练 loss 曲线论文未展示。

### 系统性缺陷

- **尾延迟与训练正确性**：论文未报告 mitigation 是否引入 iteration 时间方差增大、数值行为变化，或 topology swap 后的 optimizer state 一致性。
- **故障恢复与隔离**：S4 之后慢节点如何隔离、是否会被调度器再次分配，论文未讨论；多 fail-slow 并发时的 planner 互斥也未展开。
- **可观测性**：系统输出 straggler ID 与策略切换日志，但是否能对接集群 ticket / 自动换机 / 网络运维，论文未涉及。
- **运维成本**：LD_PRELOAD + Redis + 全局 controller 的部署、升级、与 K8s/Gang scheduling 集成，论文未讨论。
- **与 fail-stop 栈关系**：明确正交于 Gemini/Oobleck 等 fail-stop 恢复，但复合故障（先 fail-slow 再 hang）的行为论文未覆盖。

## 局限与 Future Work

- **局限 1：检测盲区。** 仅在特定 compute+communication 交织模式下出现的 fail-slow（类似 SuperBench 报告的 hardware batch defect）当前设计检测不到；连续 <10% 的渐变退化会导致通信 fail-slow 2.3% FNR。
- **局限 2：缓解绑定 Megatron。** DETECT 虽 framework-agnostic，MITIGATE 的 micro-batch 与 topology 逻辑深度依赖 Megatron-LM 并行 API；迁移到其他框架需重写。
- **局限 3：规模鸿沟。** 生产表征在 10K GPU，但端到端缓解只验证到 256 GPU 注入；真实 1024-GPU 复合拥塞下的 planner 行为仍是推断。
- **Future work 1**：用生产大 job 的 non-injected trace 做 replay，测量 DETECT 误报率与 MITIGATE 策略切换是否过度——需要集群方开放更细粒度 timeline 与换机记录。
- **Future work 2**：把 ski-rental 阈值做成在线估计（根据历史 fail-slow 持续时间分布、实时 checkpoint 带宽），并与 [[SMon-OSDI25]] 式 what-if 分析结合，在升级 S3/S4 前预测 JCT 收益是否大于 action cost。
- **Future work 3**：与网络层协同（traffic isolation、job-aware scheduling，如 CASSINI/Crux 方向），从源头降低通信 fail-slow 频率，而不只在训练 runtime 侧缓解。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Data-Parallelism]]、[[NCCL]]、[[Checkpointing]]、[[RDMA]]
- **同类系统**：[[Megatron-LM]]、[[DeepSpeed]]、[[SMon-OSDI25]]（straggler what-if 分析）、[[Optimus-ATC25]]（同会议大规模训练优化）
- **同会议**：[[ATC-2025]]
- **对比**：fail-stop 恢复（Gemini、Oobleck）处理崩溃；Greyhound 处理仍运行但变慢的组件，二者正交但 S4 最终仍回到 checkpoint-restart