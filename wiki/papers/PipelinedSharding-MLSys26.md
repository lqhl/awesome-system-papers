---
type: paper
name: PipelinedSharding
full_title: "EFFICIENT, VRAM-CONSTRAINED XLM INFERENCE ON CLIENTS"
authors: [NVIDIA authors]
venue: MLSys
year: 2026
tags: [client-inference, vram, llm-serving, llama-cpp, vlm]
source_pdf: "[[eb160de1de89d9058fcb0b968dbbbd68.pdf]]"
source_md: "[[eb160de1de89d9058fcb0b968dbbbd68]]"
---

# EFFICIENT, VRAM-CONSTRAINED XLM INFERENCE ON CLIENTS (MLSys 2026)

> **一句话总结**：客户端 **VRAM** 预算远小于磁盘权重时，llama.cpp 手动 offload 难调；**Pipelined Sharding** 用 token-tier 调度（context vs decode）在 GPU/CPU/PCIe 间流水线 shard，**VLMOpt** 优化视觉编码，使 qwen235b 在 **2GB VRAM** 仍 **7.7 TPS**（1K ctx），TTFT/TPS 平均 **2×/3.7×**，Cosmos-Reason1 VRAM **10×** 降至 **2GB**。

## 问题与动机

游戏/边缘 [[LLM]]/VLM（NVIDIA IGI SDK、Cosmos-Reason1）需在用户指定 VRAM 上限内交互式推理。权重远大于 VRAM，需 CPU RAM + PCIe 流式。llama.cpp 手动 CPU offload 在 MoE/KV 竞争时 TTFT 差；高分辨率 VLM 常 OOM。

## 关键观察 / 隐含假设

- **观察 1：context phase（高 token 数）与 decode phase（KV 膨胀）最优执行计划不同——token tier 应用 Static GPU-only vs Dynamic oversubscribe。**
  - **依赖假设**：benchmark profile 驱动 schedule cost model 准确。
  - **可能失效场景**：极短 prompt+长 decode 边界需在线重选 plan。

- **观察 2：在 2G VRAM，qwen235b（77GB disk）仍可达 **≥5 TPS** interactive 至 16K ctx；64K ctx TPS speedup 最高 **30×**。**
  - **依赖假设**：PCIe gen5 权重流式可隐藏；UKV/nUKV 路径可选。
  - **可能失效场景**：PCIe gen3 TTFT speedup 仅 **1.2×→2.4×** 仍有益但缩小。

- **观察 3：VLMOpt + pipelined sharding 使 CR1 从 vLLM **20GB** 需求降到 **2GB** 可跑高分辨率任务。**
  - **依赖假设**：llama.cpp 多模态路径；vLLM baseline 多模态效率异常需知。
  - **可能失效场景**：视频输入 llama.cpp 未支持（论文仅 image）。

- **假设 1**：batch>1 时 token-tier 仍可扩展，batch-wide TPS 平均 **2.3×**（最高 **8.2×**）。**
  - **证据强度**：**强**——多 VRAM budget/ctx/batch 矩阵。

## 核心方法

**Pipelined sharding**：按层/子层 shard 在 GPU 驻留与 CPU 流式间流水线；scheduler 依 token tier、ctx len、VRAM budget 选 plan。

**VLMOpt**：图像 encode/decode 与 LLM 流水线协同，降峰值 VRAM。

**实现**：llama.cpp b6097 之上；面向 IGI SDK/CR1 产品路径。

## 设计取舍

- **自动 scheduler vs 手动 knob**：赢得鲁棒性，profile 前期成本。
- **CPU offload 全量 KV vs 选择性**：动态 oversubscribe 换 PCIe 压力。
- **llama.cpp vs vLLM**：客户端可部署性优先，非 datacenter 吞吐记录。
- **边界条件**：RTX 5090/4090 等 client GPU；MoE 大模型为主。

## 实验与结果

- Interactive：TTFT avg **2×**（max **6.7×**），TPS avg **3.7×**（max **30×**），E2EL avg **2×**。
- Batched：batch-wide TPS avg **2.3×**，max **8.2×**（qwen30b 4K bs16）。
- CR1：VRAM **10×** 降；多分辨率 baseline OOM 配置可运行。
- qwen235b @2G：7.7 TPS @1K，5.2 TPS @16K。

## Critical Analysis

### 论证链条

VRAM≪模型 → token-phase heterogeneity → profiled pipelined sharding + VLMOpt → 极端预算可交互，工程链条扎实。

### 假设压力测试

Apple Silicon/统一内存路径不同。多应用并发争用 host RAM 未测。

### 实验可信度

artifact 可复现 Table4/Fig2 等；vLLM 对比受多模态实现影响。绝对 TPS 随硬件变，相对 trend 为主。

### 系统性缺陷

论文未讨论安全模型权重流式、功耗热节流、Windows 驱动差异。

## 局限与 Future Work

- **局限 1**：视频 多模态未覆盖。
- **局限 2**：强依赖 llama.cpp 生态。
- **Future work 1**：与 Windows GPU 内存 budget API 深度集成。
- **Future work 2**：disaggregated 云辅助 client offload 混合模式。

## 相关

- **相关概念**：[[KV-Cache]]、[[MoE]]、[[VLM]]、[[Edge-Inference]]
- **同类系统**：llama.cpp、IGI SDK
- **同会议**：[[MLSys-2026]]