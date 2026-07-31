---
type: paper
name: SANI
full_title: "Unleash All Cores: Asymmetry-aware Scalable DNN Inference on Mobile CPUs"
authors: [Qianlong Sang, Puyi He, Huanghuang Liang, Yili Gong, Chuang Hu, Xiaobo Zhou, Dazhao Cheng]
venue: OSDI
year: 2026
tags: [mobile-inference, asymmetric-multiprocessing, scheduling, arm]
source_pdf: "[[osdi26-sang.pdf]]"
source_md: "[[osdi26-sang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# SANI：面向非对称移动 CPU 的可扩展 DNN 推理（OSDI 2026）

> **原题**：Unleash All Cores: Asymmetry-aware Scalable DNN Inference on Mobile CPUs

SANI 同时适配 big/LITTLE core 的 kernel affinity 与动态任务粒度，使慢核不再拖住同步 barrier，并在 workload migration 时转换 kernel layout。

## 问题与动机

移动 SoC 的 LITTLE cores 更节能，但把 operator 输出均匀切给所有核会使 big cores 等待慢核，加入 LITTLE 后端到端 latency 反而最多增加 37%。静态比例不适应后台 interference，极细动态 task 又产生 dequeue overhead；统一 kernel 还忽略两类微架构各自偏好的 tile/SIMD 实现。

## 关键观察 / 隐含假设

### 关键观察

- core–kernel affinity 可产生超过 30% 的差异，调度 workload 数量与选择执行 kernel 必须联合处理。
- 快核适合合并大 task 降低 acquisition overhead，慢核或被干扰核适合拆小 task 降低 barrier wait。
- 以 kernel-agnostic block 统一不同 tile layout，可在迁移时重映射 index，而不复制 tensor 数据。

### 隐含假设

- DNN operator 输出可细分为彼此独立 blocks，任务迁移不需要跨核显式数据移动。
- 运行时反馈能及时反映 core speed，背景干扰变化慢于 scheduler 调整。
- CPU 是可接受的推理目标；大型 on-device [[LLM|LLM]] 仍主要交给 NPU，不是论文重点。

## 核心方法

### 亲和性感知的 kernel 分发器

初始化时用考虑 SIMD width、cache hierarchy 与 operator shape 的 cost model，为 big/LITTLE cluster 分别选择最快 kernel，而非全核共享实现。

### 自适应粒度调度器

每个线程报告执行速度；scheduler 对 block 做 Merge/Split，让快核拿更大连续工作、慢核拿更小工作，在 wait latency 与 queue overhead 间动态寻找平衡。

### 按需 kernel 切换器

workload 跨 cluster stealing/migration 时，switcher 把统一 block index 映射到目标 kernel 的 tile layout，使目标核继续执行 affinity-optimal code。

## 设计取舍

- 多 kernel variant 与 index transform 换来异构效率，但增加初始化、代码体积和 correctness 测试空间。
- 动态 scheduler 比静态比例鲁棒，却需持续反馈和同步 metadata。
- operator-level parallelism适合 CNN/GEMM，不覆盖强序列依赖或 NPU-only operator。
- all-core 模式优化 latency；若只追求最低能耗，LITTLE-only 仍可能更优。

## 实验与结果

- 在 Pixel 9、Find X3 Pro、Redmi K60、OnePlus Ace 和 Odroid XU4 五款 SoC、六个模型上，SANI 相比 Native 平均 latency 降低 17.6%–23.7%，单模型最高 29.5%（§5.2，图 10）。
- 按模型汇总，MobileNetV2、SqueezeNet、ShuffleNet、ResNet-50、Inception-V3 与 GPT-2 latency 分别降低 15.7%、17.7%、21.0%、19.3%、29.5% 和 16.1%。
- 在不同背景 CPU stress 下，SANI 相比基线 latency 降低 20%–40%；即使迁移发生，execution latency 仍低 7%–10%，支持动态粒度与 kernel switch 的联合作用。
- ResNet-50 energy 相比 Native、AsyMo、MNN 分别降低 34.1%–35.3%、32.5%–39.0%、37.1%–37.3%；其他模型/线程配置改善约 5.5%–30.5%。
- 异构消融中 affinity issuer 为 SqueezeNet/ShuffleNet贡献 9.5%/9.6%，adaptive scheduler 再贡献 10.5%/13.5%，kernel switcher 贡献 7.1%/8.0%；同构核上 switcher 仅 0%–0.2%。
- SANI 的核心控制路径少于总 inference latency 的 1%，额外 memory footprint 较小；论文未给出所有设备的绝对字节和 cold-start 分布。

## 论断—证据表

| 论断 | 机制 | 证据 | 边界 |
|---|---|---|---|
| 加入 LITTLE 核不应依赖均匀切分 | adaptive Merge/Split | 五款 SoC 平均 latency 降低 17.6%–23.7% | 需可分块 operator |
| kernel affinity 与负载均衡同等重要 | cluster-specific issuer/switcher | 两组件分别贡献最高 9.6%/8.0% | 维护多 kernel variant |
| all-core 可同时提速与节能 | LITTLE 承担合适粒度工作 | ResNet-50 energy 最高降低 39% | latency-first 设置，不保证全局最低能耗 |
| 设计适应 runtime interference | 在线速度反馈 | stress 下 latency 降低 20%–40% | 未覆盖温控降频的长时间行为 |

## 批判性分析

### 论证链条

论文用“performance-collapse paradox”建立鲜明反例，并将 root cause 分解为 task imbalance 与 kernel mismatch。跨五款商业 SoC 的端到端、energy、stress 和消融结果对每个机制都有直接支持。

### 假设压力测试

热降频、OS 调度迁核和 DVFS 可能比短期反馈变化更快；模型出现不可拆 operator 或 cache sharing 时，大 task 分配会改变内存争用。若 NPU 可用且更快，CPU 方案只在 fallback/小模型场景有意义。

### 实验可信度

设备和模型覆盖优于单开发板研究，且比较 Arm-CL、MNN、AsyMo。缺少用户交互 workload 的 p95/p99、温度与持续功耗、DVFS 默认策略、app 共存，以及现代 transformer/LLM 的完整端到端结果。

### 系统性缺陷

SANI 需要框架掌握 operator 实现、微架构 cost 与 runtime scheduling 三层信息，移植新 ISA/SoC 的 tuning 成本高。所谓 scalable 主要指核配置，不是模型、并发请求或长期移动 workload 的规模。

## 局限与后续工作

- 纳入 DVFS、thermal throttling、OS migration 与长期背景 app 干扰。
- 在 transformer、小型 LLM 和多请求场景报告端到端 p99 与 energy/token。
- 自动生成/验证 cluster-specific kernels，降低新 SoC porting 成本。
- 与 GPU/NPU heterogeneous execution 联合调度，而非只在 CPU 内分配。

## 相关

- [[Mobile-Inference]]
- [[big.LITTLE]]
- [[Arm-Compute-Library]]
- [[Heterogeneous-Scheduling]]
