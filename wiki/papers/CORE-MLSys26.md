---
type: paper
name: CORE
full_title: "Rethinking DVFS for Mobile LLMs: Unified Energy-Aware Scheduling with CORE"
authors: [Zongpu Zhang, Pranab Dash, Qiang Xu, Y. Charlie Hu, Jian Li, Haibing Guan]
venue: MLSys
year: 2026
tags: [mobile-inference, dvfs, energy-efficiency, llm, llama-cpp]
source_pdf: "[[aab3238922bcc25a6f606eb525ffdc56.pdf]]"
source_md: "[[aab3238922bcc25a6f606eb525ffdc56]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Rethinking DVFS for Mobile LLMs: Unified Energy-Aware Scheduling with CORE (MLSys 2026)

> **一句话总结**：移动 [[LLM]]（[[llama.cpp]] OpenCL）即使用 GPU 仍重度占用 CPU/内存，而 Android 独立 EAS/Quickstep/interactive governor 缺乏协同，导致同等能耗下 TTFT/TPOT 可比最优频率差 **23–40%**；CORE 离线 profiling 搜 CPU/GPU/MIF 联合频率表，运行时按请求切换，Pixel 7 上 TTFT **-8.5–17.7%**、TPOT **-27.8–39.6%** 且不增每 token 能耗。

## 问题与动机

On-device LLM 受电池限制；默认 DVFS 各组件独立降频，GPU 推理时 CPU 喂 kernel（OpenCL 浅队列）却被 EAS 判为低负载，形成 antagonistic downward spiral。

## 关键观察 / 隐含假设

- 观察 1：2808 组 Pin 频率组合中，大量点在同等能耗下 latency 优于 Gov（Fig. 1）；Pin-Opt E2E 最高 63% 降幅（128 prefill + 256 decode）。
  - **依赖假设**：ShareGPT 式负载；batch=1 移动推理。
  - **可能失效场景**：不同 SoC（非 Tensor G2）需重 profiling。

- 观察 2：单独 GPU governor 为保利用率选过低频率；固定 CPU/MEM 时 Pin GPU 更高频可 34–41% 降 TPOT 且能耗相近。
  - **依赖假设**：decode memory-bound、prefill compute-bound 需不同联合频率。
  - **可能失效场景**：更大模型 MLP 主导时 GPU governor 行为变化（论文已部分讨论）。

- **观察 3：prefill 与 decode 最优频率组合不同，需分阶段表。**
  - **依赖假设**：离线表可覆盖主要 prompt/decode 长度桶。
  - **可能失效场景**：连续流式输入边界未定义时 TTFT 策略模糊。

## 核心方法

**CORE（Coordinated Optimization of Resource Energy）**：

1. **Offline**：轻量 profiling 在能耗预算下最小化 latency（或反向），得 prefill/decode 频率组合。
2. **Runtime**：按请求阶段查表设 f_CPU、f_GPU、f_MEM（通过 governor min=max pin）。

原型扩展 llama.cpp；TinyLlama 1.1B、StableLM 3B、Llama-2 7B；Pixel 7/7 Pro。

## 设计取舍

- **查表 vs 在线学习**：稳定可预测，新场景需重 offline。
- **Pin 频率 vs 改 governor**：无 OS 内核改动，用户需 root/工程模式。
- **GPU-primary 路径 vs NPU**：论文聚焦 OpenCL GPU；NNAPI/NPU 未覆盖。
- **边界条件**：单用户 batch=1；长会话发热降频未动态适应。

## 实验与结果

- vs Gov：TTFT **8.5–17.7%**↓，TPOT **27.8–39.6%**↓，energy/token 不增。
- Pin-Opt 展示默认 governor 距 Pareto 前沿远（**40.4%** TTFT 等上界）。
- 分阶段 governor 隔离实验支撑根因分析（§5）。

## Critical Analysis

### 论证链条

测量→根因（缺协同）→CORE 两阶段，因果清楚。表格式方案在热节流时可能过时。

### 假设压力测试

多应用并发争用 DVFS；vendor 固件更新改变频率表；NPU 路径成为主流后 OpenCL CPU 喂入假设弱化。

### 实验可信度

控制实验充分（Monsoon 功耗）；模型/设备有限。缺 iOS 或其他 Android SoC。

### 系统性缺陷

需 root pin 频率，非 mass-market；热状态未闭环；论文未讨论量化/Spec decode 叠加。

## 局限与 Future Work

- **局限**：设备特定表；热节流动态性；仅 llama.cpp+OpenCL 栈。
- **Future work**：在线轻量自适应；集成厂商 NPU governor；多应用公平性。

## 相关

- **相关概念**：[[DVFS]]
- **同类系统**：[[llama.cpp]]、[[CORE]]（本论文系统名）
- **同会议**：[[MLSys-2026]]
