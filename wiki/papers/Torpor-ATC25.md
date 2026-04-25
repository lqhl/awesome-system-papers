---
type: paper
name: Torpor
full_title: "Torpor: GPU-Enabled Serverless Computing for Low-Latency, Resource-Efficient Inference"
authors: [Minchen Yu, Ao Wang, Dong Chen, Haoxuan Yu, Xiaonan Luo, et al.]
venue: ATC
year: 2025
tags: [serverless, gpu-pooling, llm-serving, model-swapping, late-binding]
source_pdf: "[[atc2025-yu.pdf]]"
source_md: "[[atc2025-yu]]"
---

# Torpor: GPU-Enabled Serverless Computing for Low-Latency, Resource-Efficient Inference (ATC 2025)

> **一句话总结**：用 host-memory + late binding + 按需 model swap（PCIe/NVLink）替代 serverless 推理的 GPU 早绑定，4-GPU 节点上同时服务 480 个推理函数仍满足 ms 级 SLO；Alibaba Cloud 试点节省用户 70%、平台 65% GPU 成本。

## 问题

AWS Lambda、Alibaba Function Compute 等 serverless 平台支持 GPU 时仍走"早绑定"——容器一启动就独占一张 GPU，函数 idle 时用户照付。生产 trace 显示 85% 推理函数 ≤1 次/分钟、97% ≤1 次/秒，早绑定造成严重 GPU 浪费且 cross-GPU 负载不均；改成 cold-start 按需启动则要花几十秒（GPU container 初始化、ML 框架启动、模型 init），远超 ms 级推理 SLO。理想方案要四个属性：pay-per-GPU-use、GPU efficient、SLO compliant、model-agnostic（保护用户 IP）；现有方案没人全占。

## 核心方法

每个 worker node 跑一个 GPU server 把本地 GPU 池化，函数容器以 model-agnostic 方式通过 CUDA API redirection 访问任意 GPU；idle 模型常驻 host memory（TB 级），请求到达再 swap 到 GPU。挑战与应对：

- **低延迟 GPU remoting**：异步 API 重定向——把 cudaLaunchKernel 等非阻塞 API 不等返回直接发，仅同步 cudaMalloc 等 blocking API；批合并连续 API 调用。比 GVirtuS 的同步重定向 ResNet-152 延迟降 88%、Bert-qa 降 37%
- **流水化模型 swap**：pinned memory pool、parameter-group-level 流水让传输与计算重叠；group size 用硬件 elbow point（≈2 MB）profiling 决定，无需模型结构知识；优先用 NVLink 跨 GPU swap、PCIe 兜底
- **Memory 管理**：block-level address translation 隐藏跨 GPU 物理地址差异；扩展 Buddy allocator 共享同尺寸 block 避免碎片
- **SLO-aware 三策略**：(1) 用 RRC（required request count）= (pn-m)/(1-p) 量化函数距离 SLO 的"努力"，高 RRC 优先级低；(2) interference-aware scheduling 优先复用已加载 GPU、其次 NVLink、最后 PCIe，并避开邻居正在 swap 重模型的 GPU；(3) eviction 时优先 evict 轻模型（其 swap 不占满 PCIe）、剩重模型再 LRU

深度细节回 [[atc2025-yu]]。

## 关键结果

- 单 V100 上能并发服务百级推理函数，比 Alibaba Cloud 现有 GPU 服务降本 10×
- 4-GPU worker 节点用真实 trace 跑 480 个函数，全部满足 ms 级 SLO；6 worker 集群跑 1000+ 函数仍 SLO-compliant，而 Native/NonSwap/SimpleSwap 都崩
- Alibaba Cloud pilot：用户 GPU 成本省 70%，平台 GPU 配额省 65%
- 函数启动：Torpor 需要 0.03–4 s（model+runtime），cold start 要 8–61 s
- ResNet-152 GPU remoting 比 Native 还快（CPU-side cuDNN 描述符配置被分流）

## 相关

- **相关概念**：[[Serverless]]、[[GPU-Pooling]]、[[Model-Swapping]]、[[CUDA-API-Remoting]]、[[Cold-Start]]、[[NVLink]]、[[KV-Cache]]
- **同类系统**：[[INFless]]、[[DGSF]]、[[Molecule]]、[[PipeSwitch]]
- **同会议**：[[ATC-2025]]
