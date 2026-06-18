---
type: paper
name: CORE
full_title: "Rethinking DVFS for Mobile LLMs: Unified Energy-Aware Scheduling with CORE"
authors: [Zongpu Zhang, Pranab Dash, Qiang Xu, Y. Charlie Hu, Jian Li, Haibing Guan]
venue: MLSys
year: 2026
tags: [mobile-llm, dvfs, energy-efficiency, llama-cpp, edge-inference]
source_pdf: "[[aab3238922bcc25a6f606eb525ffdc56.pdf]]"
source_md: "[[aab3238922bcc25a6f606eb525ffdc56]]"
---

# Rethinking DVFS for Mobile LLMs: Unified Energy-Aware Scheduling with CORE (MLSys 2026)

> **一句话总结**：首次系统分析 Android CPU/GPU/memory 三 governor 在移动 LLM 推理中的拮抗降频效应，提出统一 governor CORE 离线搜频 + 运行时应用，在 llama.cpp 上 TTFT 降 8.5–17.7%、TPOT 降 27.8–39.6%，且不增加每 token 能耗。

## 问题

移动 LLM（llama.cpp + OpenCL）同时占用 CPU、GPU、memory 三路功耗，但 Android 上 EAS、Quickstep、interactive 三 governor **独立决策**。实测 2808 种 Pin 频率组合中，默认 governor 可比最优组合慢 **23.0–40.4%** 或能耗高 **5.0–16.6%**。根因：decode 阶段 GPU/CPU 利用率低 → 各 governor 降频 → OpenCL runtime 喂 GPU 变慢 → 利用率更低，形成 **downward spiral**。

## 核心方法

**CORE（Coordinated Optimization of Resource Energy）** 两阶段：

1. **Offline profiling**（每 device–model 一次，开发者随 app 分发）：按 prefill 长度五档 + 固定 decode 长度采样；两步搜频——先 GPU（dominant），再 CPU；memory 保持默认（已接近最优）
2. **Runtime**：prefill/decode 阶段切换预计算频率组合

支持两目标：**G1** 给定能耗预算最小化延迟；**G2** 给定 TTFT/TPOT 目标最小化能耗。搜频平均只需 **~15–31 次** 推理（相对 2808 组合 **374×** 缩减），TinyLlama 全设置约 17.7 分钟。

已作为 llama.cpp 扩展开源（~2K 行 Python）。

## 关键结果

- Pin-Opt vs Gov：E2E 延迟最高降 **63%**（128 prefill + 256 decode，TinyLlama）
- ShareGPT 200 请求 trace（G1，等总能耗）：TinyLlama TTFT/TPOT/E2E 降 **14.6% / 27.8% / 23.2%**；StableLM TPOT 降 **38.3%**
- G2（等 TTFT）：TinyLlama 总能耗降 **7.5%**；DS-Qwen 降 **15.8%**
- Decode antagonistic：GPU governor 选频可比最优高 **41.0%** TPOT（TinyLlama）

## 相关

- **相关概念**：DVFS、mobile inference、OpenCL、prefill/decode
- **同类系统**：llama.cpp、Android EAS/Quickstep
- **同会议**：[[MLSys-2026]]