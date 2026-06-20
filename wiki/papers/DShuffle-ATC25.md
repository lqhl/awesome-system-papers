---
type: paper
name: DShuffle
full_title: "DShuffle: DPU-Optimized Shuffle Framework for Large-scale Data Processing"
authors: [Chen Ding, Sicen Li, Kai Lu, Ting Yao, Daohui Wang, Huatao Wu, Jiguang Wan, Zhihu Tan, Changsheng Xie]
venue: ATC
year: 2025
tags: [dpu, spark, shuffle, smartnic, rdma, big-data]
source_pdf: "[[atc2025-ding.pdf]]"
source_md: "[[atc2025-ding]]"
---

# DShuffle: DPU-Optimized Shuffle Framework for Large-scale Data Processing (ATC 2025)

> **一句话总结**：DShuffle 的关键观察是现代 Spark shuffle 在大数据 sort 中已经从纯 I/O bottleneck 转成 host CPU / GC / serialization bottleneck；它把 serialization、preprocessing、I/O 拆成 DPA + DPU pipeline + DPU-direct spilling 三段，在 BlueField-3 两节点 Spark 集群上把 285 GB sort 从 513 s 降到 431 s，并把 shuffle 阶段时间比 native Spark 降 62.7%。

## 问题与动机

这篇论文瞄准的是 [[Spark]] / Hadoop 这类大数据框架里的 [[Shuffle]]：map 端把中间结果按 partition 重排、serialize、写盘或发网，reduce 端再拉取、deserialize、merge/sort。传统理解常把 shuffle 视为网络和磁盘 I/O 问题，但作者在现代硬件上观察到，I/O 设备变快以后，host CPU 上的 serialization、GC、临时对象管理和数据搬运变成新的主导开销。

作者用 2-node Spark 集群跑 285 GB HiBench Sort，shuffle 阶段约 226 s，占 job 的最大部分；shuffle 消耗约 30 个 CPU cores，但网络和存储带宽利用率只有 25% 和 51%。进一步看 HiBench 的不同 workload，Sort / TeraSort 这类 shuffle-intensive workload 中，(de)serialization 和 GC 约占总时间 64%-69%。这给论文一个明确的 systems claim：如果只继续优化网络/磁盘 I/O，而不从 host 上移走 serialization 和 GC 压力，Spark shuffle 仍会卡在 CPU/JVM 路径上。

[[DPU]] 是论文选择的卸载位置，因为它正好在 host、NIC、disk 和远端节点的数据路径上，并且 BlueField-3 这类 SoC DPU 有 ARM cores、32 GB onboard memory、ConnectX-7 network 和 DPA hardware threads。可是论文也强调，"offload to DPU" 本身不是解法：naive offload 把 partition/sort/network I/O 丢到 DPU 后，job 反而慢 1.52-1.68x。根因是 DPU general-purpose cores 比 host x86 cores 慢，而且 DPU memory 小，intermediate data 堆积后会反过来 stall host map computation。

所以 DShuffle 的问题定义不是简单的 "用 DPU 加速 shuffle"，而是更窄也更有价值的命题：如何把 shuffle 拆成适合 DPU data-path 的阶段，让 host CPU 和 JVM heap 从 shuffle 中脱身，同时不让 DPU 的低频 cores 和有限 memory 成为新的瓶颈。

## 关键观察 / 隐含假设

- **观察 1：在作者测试的 Spark sort workload 中，shuffle 的主瓶颈是 host CPU / GC，而不是网络或 SSD 带宽。** 证据是 285 GB Sort 中 shuffle 消耗约 30 CPU cores，但网络 / 存储只到 25% / 51% 利用率；HiBench breakdown 里 Sort / TeraSort 的 (de)serialization + GC 占 64%-69%。
  - **依赖假设**：workload 必须有大量 JVM object serialization、临时对象和中间结果 spilling；硬件也必须足够快，使网络和磁盘不先饱和。
  - **可能失效场景**：columnar/native execution engine、compression-heavy shuffle、慢网络/慢盘环境、或者 WordCount 这类 compute-dominated workload 下，DShuffle 可减少的那部分不再主导。
- **观察 2：naive DPU offload 会把 host bottleneck 换成 DPU bottleneck。** Figure 4 中，Naive Offload 在 30/60/120/285 GB Sort 上分别从 57/125/216/513 s 变成 89/191/353/797 s，数据越大越糟。
  - **依赖假设**：DPU general-purpose cores 和 onboard memory 明显弱于 host；如果未来 DPU cores 更强、memory 更大，DShuffle 的 pipeline 仍有价值，但 naive offload 的反例强度会下降。
  - **可能失效场景**：DPU 专用 accelerator 已经覆盖 partition/sort/spill，或 workload 足够小到不触发 DPU memory pressure，naive offload 可能没有这么差。
- **假设 1：DPA 可以安全、高效地遍历 JVM heap object tree。** DShuffle serializer 需要读取 JVM heap base/size、compressed pointer 设置和 class/type metadata，然后由 DPA hardware threads 从 root object address 直接 load/store。
  - **证据强度**：中。component evaluation 显示超过 2 个 DPA cores 后 serialization latency 低于 Java/Kryo，但论文没有深入讨论 GC 移动对象、safepoint、JVM 版本差异、对象并发修改和安全隔离。
- **假设 2：DPU-direct spilling 的部署前提可以接受。** DShuffle 需要预分配固定大小文件块，让 host read-only mount，DPU read-write mount，并通过 direct I/O、PCIe P2P 和 [[RDMA]] 管理本地/远端 spilling。
  - **证据强度**：中偏弱。论文证明了原型性能收益，但对文件块回收、故障恢复、权限隔离、multi-tenant 配额、PCIe P2P 可用性和运维复杂度讨论很少。
- **假设 3：把 shuffle 资源压力转移到 DPU 是集群层面的净收益。** DShuffle 释放 host CPU 给 map/reduce，但 DPU 变成共享瓶颈；作者的 scalability 实验也显示约 6 个并发 workload 后 DPU compute/memory 开始饱和。
  - **证据强度**：中。论文覆盖了并发 workload，但规模只有两台物理机，不能直接外推到生产 multi-tenant Spark cluster。

## 核心方法

DShuffle 的架构保留 Spark 侧的轻量 DShuffle Agent，并在 driver 上放一个 DShuffle Scheduler。host agent 接收 shuffle request、把请求和 metadata 转交给 DPU，并轮询结果；真正的数据面由 DPU 侧三个组件组成：DPA-Based Serializer、DShuffle Worker 和 DSpill Worker。这个拆分直接回应观察 1：把最容易制造 host CPU/GC 压力的 serialization 和 I/O 从 JVM 路径里搬走。

**DPA-offloaded serialization** 负责解决 "serialization 不能只靠 DPU ARM cores" 的问题。普通 DPU core 访问 host memory latency 高、频率低，直接跑 Java object traversal 会慢；DShuffle 让 DPA hardware threads 读取 JVM heap 参数和 class metadata，从 root object address 并行遍历 object tree，把离散字段复制到连续 buffer。它提供与 Java serializer 类似的 init、type registration、serialization、deserialization 接口，因此 Spark 上层主要替换 shuffle writer，而不是重写应用逻辑。这个设计的边界也很清楚：serialization 适合 DPA，因为它是并行 memory access；deserialization 仍留在 host，因为创建大量 Java objects 会要求 DPA 与 JVM 频繁跨 PCIe 交互。

**Fine-grained pipeline shuffle** 负责解决观察 2 中 naive offload 被 DPU core 和 memory 拖住的问题。DShuffle 不把 preprocessing 和 I/O 放在一个串行 DPU worker 里，而是把 map side 切成 DPA Serializer -> DShuffle Worker -> DSpill Worker 的 pipeline：当前 batch 被 preprocessing 时，下一个 batch 已经可继续 serialization；preprocessing 完成后立刻交给 spill/network worker。worker 间用 SPSC lock-free queues，worker 内部再按 key segment 开线程，并用 Boost.Fibers 做 coroutine-style fine-grained tasks，减少 DPU cores 被 polling / waiting 固定占住的浪费。

**DPU-direct spilling** 是第三个关键点。传统 Spark 或 naive offload 即使把部分 shuffle 计算卸到 DPU，最终 spilling 仍常回到 host block manager 和 JVM I/O 路径，制造临时对象、数据拷贝和 GC。DShuffle 让 DPU 直接通过 [[PCIe-P2P]] 写本地 disk，或通过 RDMA 把数据发到远端 DPU 后直写远端 disk。host 预先创建固定大小文件块并保持 metadata 稳定，DPU 写完一个 32 MB block 后用 DMA 通知 reducer，reducer 再按 metadata 用 direct I/O 读取。这回应了假设 2：性能收益来自绕开 host I/O 栈，但代价是需要专门的磁盘分区和更紧的 host/DPU 协同。

实现上，DShuffle 基于 Spark 2.4.3 和 NVIDIA BlueField-3 / DOCA 2.9。代码约 6,700 行：host 侧约 500 行 Java interface、1,000 行 C++ JNI；DPU worker 约 4,000 行 C++，支持 DMA/RDMA/TCP transmission layer；DPA serializer 约 1,000 行 JNI metadata 处理和 1,200 行 DPA hardware code。深度实现细节回 [[atc2025-ding]]。

## 设计取舍

- **完全卸载 vs 动态回退**：DShuffle 追求 shuffle path 不消耗 host CPU，这比 SmartShuffle 式动态 offload 更激进；收益是释放 host 给 map/reduce，风险是 DPU 饱和后缺少细粒度 host fallback。
- **DPA serialization vs JVM 透明性**：DPA 直接读 JVM object layout 可以避开 CPU serialization，但绑定 JVM heap metadata、compressed object pointer、type registration 和对象布局细节，跨 JVM 版本或 GC 策略时可能脆。
- **pipeline granularity vs 调度复杂度**：细粒度 batch/pipeline 防止 DPU memory 堆积，也平衡 serializer、preprocess、spill 阶段；代价是 DPU 侧 queues、coroutines、worker 数和 scheduler state 都进入正确性/调优面。
- **DPU-direct disk writes vs 运维简单性**：预分配 file blocks + read-only/read-write split mount 能绕开 host I/O 和 GC，但这不是普通 Spark 部署默认模型；容量规划、故障恢复、权限隔离和观测都更复杂。
- **边界条件**：DShuffle 在 shuffle-heavy、大中间结果、host CPU/GC 显著的 Spark workload 上优雅；在 compute-heavy workload、DPU 被多个 job 共享打满、或 network/storage 已经先饱和的环境里会变脆。

## 实验与结果

- **环境**：2-node testbed；每节点 Intel Xeon Gold 6418H server，24 cores @ 4.0 GHz，HT disabled，64 GB DRAM，Samsung 980 Pro 2 TB SSD；NVIDIA BlueField-3 DPU，ConnectX-7 双 100 Gbps ports，16 ARMv8.2 cores，32 GB DDR5，DPA 16 RISC-V cores / 256 hardware threads。每节点部署 16-core、32 GB Spark executor。
- **baseline**：Native Spark、Naive Offloading、DShuffle。SmartShuffle 不开源，所以没有直接系统对比；Naive Offloading 类似 offload partition/sort/network I/O，但不含 SmartShuffle 的 dynamic offload policy。
- **主结果**：285 GB Sort / 32 partitions 下，Native Spark 约 513 s，Naive Offload 约 797 s，DShuffle 约 431 s；即 DShuffle 比 native Spark 降约 16%，比 naive offload 降约 46%。
- **shuffle 时间**：DShuffle 比 native Spark / naive offload 分别降低 shuffle execution time 62.7% / 70.7%；map phase host CPU 从 native Spark 的约 30 cores 降到 24 cores。
- **reduce 时间**：DShuffle 比 native Spark / naive offload 分别降低 reduce phase time 45.6% / 50.2%，主要来自 direct spilling 和 serialization/GC 减少。
- **ablation**：在 Naive Offload 上逐步启用 DPA serialization、pipeline、DPU-direct spilling，整体时间分别再降 13.2%、17.4%、15.1%；serialization 占比从 naive offload 的 15% 降到 3%，最终 DShuffle 中 compute 占比上升到 48%，说明原本的 shuffle/GC/I/O 开销被显著压缩。
- **dataset size**：30/60/120/285 GB 下，DShuffle 分别约 56/100/180/431 s；数据越大，DShuffle 相比 Spark 的收益越明显，因为 serialization、GC 和 spilling 比例上升。
- **partition number**：partition 从 32 增到 192 时，DShuffle 的 whole-job / reduce time 随 parallelism 增加而下降；naive offload 的 map time 反而随 partition 增多上升，作者归因于更多 data forwarding network requests。
- **workload 覆盖**：Sort、TeraSort、Repartition 这类 shuffle-heavy workload 有明显收益；WordCount 主要是 map computation，DShuffle 与 native Spark 接近，说明它不是通用 Spark 加速器。
- **component**：单个 DPA core serialization latency 高于 Java/Kryo，但超过 2 个 DPA cores 后低于 Java/Kryo；15 个 DPU worker threads 时 worker bandwidth 达约 10.53 GB/s，接近 100 Gbps network limit。
- **concurrency**：并发 100 GB Sort workload 增加时，DShuffle 仍快于 native Spark；但约 6 个并发 workload 后 DPU compute 和 memory 开始饱和，收益增量下降。

## Critical Analysis

### 论证链条

论文的 observation -> design -> result 链条相对闭合。作者先证明在目标环境中 shuffle-heavy Spark workload 的主要开销已经转向 host CPU/GC/serialization，再证明 naive DPU offload 会失败，最后用三个设计分别补上 serialization、DPU execution pipeline、spilling I/O 这三个断点。ablation 也能把收益拆回到 DPA serialization、pipeline 和 direct spilling，不是单一大优化的黑箱结果。

主要跳步在 "industrial-grade Spark" 到 "large-scale data processing" 的外推。实验是两节点集群、HiBench synthetic workload、compression disabled、Spark 2.4.3。它足以支撑 "在 BF-3 小集群上，shuffle-heavy Spark job 可以被这种 DPU pipeline 加速"，但还不足以证明生产 Spark 集群里 tenant mix、faults、stragglers、compression、SQL operator diversity 和 data skew 下都成立。

### 假设压力测试

最脆的假设是 JVM object layout 和 GC 语义。DPA serializer 需要对 host JVM heap 做跨设备读取，这在固定 benchmark 上可控，但生产 JVM 的 GC 移动、对象生命周期、class evolution、不同 serializer / encoder、Spark SQL UnsafeRow / Tungsten path 都可能改变收益或正确性边界。论文没有把这些作为一等问题展开。

第二个压力点是 DPU 作为共享资源。DShuffle 把 host CPU 压力搬到了 DPU，scalability 实验已经显示 DPU 在约 6 个 concurrent workloads 后开始饱和。如果一个 cloud server 的 DPU 同时承担 vSwitch、security、storage virtualization、telemetry 和 shuffle offload，DShuffle 需要 admission control / isolation / priority，而论文只展示了 Spark workload 内部的 scheduler。

第三个压力点是 I/O path 的部署依赖。PCIe P2P、DPU-side disk access、read-only/read-write split mount、fixed-size file block preallocation 都要求硬件拓扑和运维模型配合。换成云虚拟机、managed Spark service、remote/disaggregated storage、encrypted disks 或严格 multi-tenant storage isolation 时，DPU-direct spilling 未必能无缝落地。

### 实验可信度

实验对论文的核心机制是有说服力的：有 motivation measurement、naive offload 反例、component microbenchmark、ablation、dataset size、partition number、workload type 和 concurrency。Figure 11 的分阶段开启尤其有价值，因为它证明 DShuffle 的三个设计都在补实际瓶颈。

不足也明显。SmartShuffle 是最相关 baseline，但因为不开源只能做 qualitative comparison，Naive Offloading 缺少 dynamic offload policy，可能放大了 DShuffle 对 "已有 DPU shuffle offload" 的优势。测试规模只有两节点，网络是 100 Gbps，SSD 是本地 Samsung 980 Pro，不能覆盖 rack-level shuffle、heterogeneous cluster 和 straggler-heavy production trace。metrics 也偏 performance：没有 power/cost、tail latency、fault recovery time、DPU resource interference、CPU/DPU utilization under mixed services。

### 系统性缺陷

论文未充分讨论 failure recovery。DPU 直接写 disk block、远端 RDMA 写入、scheduler 分配 reduce target、host reducer 消费后释放 file block，这条路径一旦 DPU reset、host crash、partial write 或 scheduler state 丢失，需要清楚的 replay / cleanup / idempotence 机制。Spark 本身有 lineage 和 task retry，但 DPU-side preallocated blocks 和 remote writes 如何纳入 retry 语义，论文没有展开。

资源隔离也是缺口。DPU memory 只有 32 GB，DPA hardware threads 和 ARM cores 也有限；多 job、多 executor、多 tenant 竞争时，DShuffle 需要限制 queue growth、spill partition space、RDMA bandwidth 和 DPA threads。否则它可能从 "释放 host CPU" 变成 "制造 DPU head-of-line blocking"。

可观测性和可维护性同样缺少实证。DShuffle 横跨 Spark Java、JNI、DPU C++、DPA hardware code、DOCA、RDMA 和 disk path；调试一个错误可能要跨 JVM heap metadata、DMA buffer、DPU worker queue 和 on-disk block metadata。论文给了代码规模，但没有给部署故障、upgrade、debug 或 operator-facing telemetry 的经验。

## 局限与 Future Work

- **局限 1：规模小。** 两节点 HiBench 能说明机制，但不足以证明 rack-level shuffle、data skew、stragglers 和 production multi-tenant workload 下的稳定收益。
- **局限 2：baseline 不完整。** SmartShuffle 不开源导致没有直接对比，Naive Offloading 不能代表所有 DPU shuffle offload 设计。
- **局限 3：JVM / Spark path 假设较强。** DPA serializer 对 JVM heap metadata 和 object layout 的依赖，需要在不同 GC、Spark SQL encoder、UnsafeRow、Kryo/schema workload 下重新验证。
- **局限 4：可靠性与隔离未覆盖。** 论文未评估 DPU crash、partial spill write、RDMA failure、executor retry、multi-tenant DPU contention 和 spill partition exhaustion。
- **Future work 1：用生产 trace 做 admission-control measurement。** 在 mixed Spark workload + DPU background services 下测 DPU core/memory/RDMA saturation，并给出 per-job admission control 或 QoS policy。
- **Future work 2：验证 DPA serializer 的 JVM 兼容矩阵。** 系统性测试 G1/ZGC/Shenandoah、compressed oops、UnsafeRow、Kryo、Java native serializer、不同 object mutability 下的 correctness 和 performance。
- **Future work 3：把 DPU-direct spilling 纳入 Spark fault model。** 设计可客观测试的 block metadata replay、partial write cleanup、remote spill idempotence 和 task retry protocol。
- **Future work 4：补 power/cost/host-DPU opportunity cost。** DShuffle 释放 host CPU，但占用 BF-3 DPA/ARM/network/disk path；需要比较 "加 DPU offload" 与 "加 host CPU / shuffle service / faster serializer" 的总拥有成本。

## 相关

- **相关概念**：[[DPU]]、[[Shuffle]]、[[Spark]]、[[RDMA]]、[[PCIe-P2P]]、[[Garbage-Collection]]、[[Coroutine]]
- **同类系统**：SmartShuffle、ZCOT、Skyway、Cereal、Celeborn、Exoshuffle
- **同会议**：[[ATC-2025]]
