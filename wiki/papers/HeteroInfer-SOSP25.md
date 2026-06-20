---
type: paper
name: HeteroInfer
full_title: "Characterizing Mobile SoC for Accelerating Heterogeneous LLM Inference"
authors: [Le Chen, Dahu Feng, Erhu Feng, Yingrui Wang, Rong Zhao, Yubin Xia, et al.]
venue: SOSP
year: 2025
tags: [mobile-llm, npu, gpu, heterogeneous-computing, soc]
source_pdf: "[[3731569.3764808.pdf]]"
source_md: "[[3731569.3764808]]"
---

# Characterizing Mobile SoC for Accelerating Heterogeneous LLM Inference (SOSP 2025)

> **一句话总结**：移动端 [[NPU]] 峰值算力可达 [[GPU]] 数倍但 shape/order 敏感，GPU-NPU 同步可达 **~400μs** 接近单 kernel 时间；HeteroInfer 在 Snapdragon 8 Gen 3 上联合 GPU+NPU+UMA 微秒同步，端到端比 SOTA 单后端 **1.34–6.02×**，prefill 首破 **1000 tok/s**、decode **50 tok/s**（十亿参数级、高精度）。

## 问题与动机

本地 [[LLM-Inference]] 需隐私/low latency，手机 SoC 集成 Adreno GPU + Hexagon [[NPU]]。现有引擎（MNN、MLC、llm.npu 等）通常**单后端**；云侧异构方案不适配 UMA 移动 SoC。三障碍：① NPU/GPU 算力悬殊，盲目并行未必赚；② 异构同步 **~400μs**；③ decode 内存带宽瓶颈，单处理器难饱和 **~68GB/s** 理论带宽。

## 关键观察 / 隐含假设

- **观察 1**：NPU 性能强依赖 tensor order/size/shape；GPU 更稳，适合作「性能下界」补充。
  - **依赖假设**：QNN NPU op + OpenCL GPU kernel 可分区执行同一层。
  - **可能失效场景**：新 SoC 代际 QNN graph 限制变化需重编译。
- **观察 2**：UMA 共享地址空间 + 双处理器并发可把内存带宽从单 GPU **40–45GB/s** 提到 **~60GB/s**。
  - **依赖假设**：带宽是 decode 瓶颈主导因素（非仅算力）。
  - **可能失效场景**：极短 context 时同步固定成本主导。
- **假设 1**：可预测 kernel 等待时间实现 **μs 级** fast sync，避免传统 fence 400μs 级开销。
  - **证据强度**：中强；profiler 驱动 tensor partition solver。

## 核心方法

**HeteroInfer**：CPU 作控制面；NPU 主算力、GPU 辅算力。

技术：prefill/decode 不同 **tensor partitioning**；layer-level + tensor-level 并行；**fast synchronization**（predictable wait）；**partition solver**（hardware profiler）。

实现：Snapdragon 8 Gen 3，OpenCL + Qualcomm QNN，**不用** activation quant/sparsity（保精度）。

## 设计取舍

- **取舍 1**：放弃 INT-only NPU 捷径 → 精度不降但压缩比不如 Qualcomm-AI 类方案。
- **取舍 2**：深度绑定 Qualcomm 栈 → 迁移 Apple A18/MTK 需重做 profiler。
- **边界条件**：与游戏并发：prefill **+2.2%**、decode **+17.7%** 慢，FPS 稳定。

## 实验与结果

- 端到端：**1.34–6.02×** vs SOTA GPU-only/NPU-only
- Prefill：**3.69×** vs PI-2(NPU)、**8.68×** vs MNN(GPU)；序列长度不对齐 NPU graph 时 **2.12×** vs padding
- Decode：**1.50–2.53×**
- 首次移动端 **>1000 tok/s** prefill、**>50 tok/s** decode（B 级模型、高精度）
- 与游戏并发：无明显 FPS drop

## Critical Analysis

### 论证链条

characterization → partition+sync → 全面超 SOTA，mobile 场景闭合。到「任意 SoC」外推弱：profiler/solver 与 QNN graph shape 强耦合；云侧 [[HeteroInfer]] 类思路是否适用未讨论（非目标）。

### 假设压力测试

- **精度**：宣称不降 accuracy，但 benchmark 套件与长上下文生成质量需独立验证。
- **功耗**：吞吐提升下的电池热节流行为论文有游戏干扰实验，纯 LLM 长会话温控未详述。
- **OS 调度**：Android 后台 CPU/GPU/NPU 频率治理影响稳定性。

### 实验可信度

工业级引擎 + 多 baseline 表（Table 1）全面；SenseTime/高通生态作者可信。缺与 Apple Neural Engine 方案横向对比。

### 系统性缺陷

QNN 闭源部分、graph 编译失败 fallback；多应用公平调度、系统级 [[LLM]] 服务 API 论文未覆盖。

## 局限与 Future Work

- **局限 1**：Qualcomm 栈绑定。
- **局限 2**：decode 与游戏并发仍有 **17.7%** 损失。
- **Future work 1**：跨厂商 SoC profiler 自动迁移，测量 solver 重用率。
- **Future work 2**：与 INT/混合精度 NPU 路径对比能耗-精度 Pareto。

## 相关

- **相关概念**：[[LLM-Inference]]、[[NPU]]、[[GPU]]、[[SoC]]、[[Unified-Memory]]
- **同类系统**：MNN-LLM、MLC、PowerInfer2、llm.npu、Qualcomm-AI
- **同会议**：[[SOSP-2025]]