---
type: paper
name: DShuffle
full_title: "DShuffle: DPU-Optimized Shuffle Framework for Large-scale Data Processing"
authors: [Chen Ding, Sicen Li, Kai Lu, Ting Yao, Daohui Wang, et al.]
venue: ATC
year: 2025
tags: [dpu, spark, shuffle, big-data, smartnic, offload]
source_pdf: "[[atc2025-ding.pdf]]"
source_md: "[[atc2025-ding]]"
---

# DShuffle: DPU-Optimized Shuffle Framework for Large-scale Data Processing (ATC 2025)

> **一句话总结**：把 Spark shuffle 的序列化 / 预处理 / I/O 全部 offload 到 BlueField-3 DPU，DPA 256 硬件线程并行 serialization、DPU 直写本地盘 / RDMA 远端盘，整体任务时间相比 native Spark 缩短约 16%，map shuffle 时间降 62.7%。

## 问题

Spark shuffle 在 285 GB sort 任务中占整个 job 70% 时间，吃掉约 30 个 CPU 核（其中 64-69% 是 (de)serialization + GC）。简单把 shuffle naive offload 到 DPU 反而拖慢 1.52-1.68×：DPU 通用核比 host x86 慢、板载 32 GB DDR5 容量有限，map 计算会因 DPU 内存满而 stall。

## 核心方法

DShuffle 把 shuffle 拆成 serialization / preprocessing / I/O 三阶段，pipeline 在 DPU 上执行：

1. **DPA-Offloaded Serializer**：利用 BlueField-3 DPA (Data Path Accelerator) 的 256 个硬件线程，通过 load/store 直接遍历 host JVM 的对象树并并行 batch serialize，与 host CPU 速度相当。
2. **Fine-grained pipeline shuffle**：inter-worker 把 DPA Serializer / DShuffle Worker / DSpill Worker 用 SPSC 无锁队列串成 pipeline，intra-worker 用 Boost.Fibers 协程切分细粒度任务避免核占用浪费；deserialization 仍交回 host CPU 避免大量 PCIe 小请求。
3. **DPU-Direct Spilling**：DPU 通过 PCIe P2P 直写本地盘 / RDMA 直送远端 DPU，host 上预分配固定大小文件块、partition 在 host 上以只读方式 mount，DPU 写完后 DMA 通知 reducer 读，完全消除 host CPU/JVM 参与的 I/O。

实现 6700 行（500 行 Java JNI + 1000 行 C++ JNI + 4000 行 DPU C++ + 1200 行 DPA hardware code）。深入实现回 [[atc2025-ding]]。

## 关键结果

- HiBench Sort 285 GB：vs native Spark / naive offload，整体执行时间减 16% / 36%。
- Shuffle 阶段时间相比 native Spark 减 62.7%，相比 naive offload 减 70.7%。
- Reduce 阶段时间相比 native Spark / naive offload 减 45.6% / 50.2%。
- Map 阶段 host CPU 用量从 30 核降到 24 核（serialization 卸载到 DPA）。
- 效果随 dataset 增大更显著：30→285 GB 加速比单调上升。

## 相关

- **相关概念**：[[DPU]]、[[Shuffle]]、[[RDMA]]、[[PCIe-P2P]]、[[Coroutine]]
- **同类系统**：SmartShuffle（不开源）、ZCOT
- **同会议**：[[ATC-2025]]
