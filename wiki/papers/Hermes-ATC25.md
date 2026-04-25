---
type: paper
name: Hermes
full_title: "Accelerating Model Training on Ascend Chips: An Industrial System for Profiling, Analysis and Optimization"
authors: [Yuhang Zhou, Zibo Wang, Zhibin Wang, Ruyi Zhang, Chen Tian, et al.]
venue: ATC
year: 2025
tags: [training, profiling, npu, ascend, bottleneck-analysis]
source_pdf: "[[atc2025-zhou.pdf]]"
source_md: "[[atc2025-zhou]]"
---

# Accelerating Model Training on Ascend Chips: An Industrial System for Profiling, Analysis and Optimization (ATC 2025)

> **一句话总结**：基于 3 年 135 个华为 Ascend NPU 训练优化案例提炼出的工业系统 Hermes，做 coarse-to-fine profiling + hierarchical bottleneck 分析 + 优化建议；在 PanGu-α、MobileNetV1、9000+ NPU MoE 训练上分别 3.05×、1.91×、1.19× 加速。

## 问题

大模型训练动辄数万卡数月，profiling-analysis-optimization 链路面临三大问题：
- **profiling 太重**：PyTorch Profiler 把单步 8B Llama-3 训练时间从 85s 拉到 150s，连续监测不可接受。
- **bottleneck 分析靠人**：现有工具只覆盖单一类型（PRESTO 只看 I/O，R-Pingmesh 只看 RDMA），缺乏跨 host/device/network 的整体分析；CPU 调度瓶颈常被忽视（占 37%）。
- **优化选择无指导**：DayDream/dPRO 只针对 data parallelism。
- 同时 Ascend NPU 与 NVIDIA GPU 在 AICore/AICPU/HCCS 等架构差异，需要专用 profiling 接口。

## 核心方法

Hermes 包含三大模块（支持 PyTorch + MindSpore）：

1. **Coarse-to-Fine Profiling**：lightweight monitor 持续收集 step time / throughput / MFU / bandwidth 等少量关键指标识别异常 step/device，再触发 fine-grained profiler 做算子级分析。dynamic profiling 通过共享内存解耦配置，无需中断训练。
2. **Hierarchical Bottleneck Analysis**：先做 inter-operator parallel 分析（multi-component overlap + critical path），再做 intra-operator 分析。Intra-operator 覆盖：queue-based I/O 分析（device/host/data 三级队列定位 reading/processing/fetching 瓶颈）、CPU 5 类原因（编译/dispatch/GC/资源争抢/环境）、roofline-based 计算分析、通信分析（synchronization waste 比例 + bandwidth contention / RDMA 重传 / 小包 / 字节对齐 / 网络配置）。
3. **Bottleneck Cause-Optimization Match**：基于 135 案例建表，关键经验包括：CPU 瓶颈占 37%、computation 99% 是 underutilization、computation 与 communication 抢 HBM 带宽掉 20-40%、I/O 瓶颈源自远程访问、网络问题主要是 port flapping 和 link failure。配套 mstt advisor 自动出 HTML 报告。

深度细节回 [[atc2025-zhou]] 或 [[atc2025-zhou.pdf]]。

## 关键结果

- profiling 开销：7B Bloom 训练时间从 1300s 降到 1000s（vs detailed profiling），230B PanGu 从 120min 到 102min；内存仅 +5-9%、CPU +4%。
- 真实生产案例加速：100B PanGu-α 3.05×、MobileNetV1-SSD 1.91×、9000+ NPU MoE 训练 1.19×。
- ResNet50 单卡 I/O 优化：把 num\_worker 从 1 调到 12，step time 从 90ms 降到 18ms（5.34×）。
- VGG16 8 卡 gradient fusion 优化：non-overlap 通信从 21.76ms 降到 3.59ms，step 从 76.5ms 降到 56.6ms（1.35×）。
- GPT-3 训练发现 Prometheus 错误部署占 4000% CPU，停掉后 step time 从 444ms 降到 374ms，性能波动从 128 step 降到 4 step（共 4989）。

## 相关

- **相关概念**：[[Profiling]]、[[Critical-Path]]、[[Roofline-Model]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Data-Parallelism]]、[[RDMA]]
- **同类系统**：DayDream、dPRO、PRESTO、R-Pingmesh、Syndicate
- **同会议**：[[ATC-2025]]
