---
type: paper
name: CLONE
full_title: "CLONE: Customizing LLMs for Efficient Latency-Aware Inference at the Edge"
authors: [Chunlin Tian, Xinpeng Qin, Kahou Tam, Li Li, Zijian Wang, et al.]
venue: ATC
year: 2025
tags: [edge-llm, llm-inference, dvfs, lora, pruning, hardware-accelerator]
source_pdf: "[[atc2025-tian.pdf]]"
source_md: "[[atc2025-tian]]"
---

# CLONE: Customizing LLMs for Efficient Latency-Aware Inference at the Edge (ATC 2025)

> **一句话总结**：边缘 LLM 部署的算法-硬件协同设计，离线 device-specific pruning + 在线 LoRA-MoE/层级 DVFS + 28nm 加速器；推理加速最高 11.92×、能耗最高节省 7.36×。

## 问题

边缘设备（手机、机器人、IoT）部署 LLM 受 SwaP（Space/Weight/Power）严格约束：Llama-7B FP16 需 ~14 GB 内存，但典型边缘设备只有 4–12 GB；推理 1 个 token 需 ~14 TFLOPs（VGG-19 的 360×）；GPT-3 单条推理耗 300 J（ResNet-50 的 400×）。已有方案分散——pruning/quantization/NAS 不考虑系统层；DVFS 把 LLM 当 black-box workload，忽略 auto-regressive 与 stochastic I/O；并发应用干扰下运行时方差大。需要算法 + 系统协同。

## 核心方法

CLONE 分两阶段：

- **离线 device-specific tailoring**：把 LLM pruning 重构为 generative task。先用启发式 [[Pruning]] 方法（LLM-Pruner、ShortGPT、SliceGPT）+ 随机扰动收集 (ratio, score) 对，score 为 $f(r_i) = \frac{1}{ppl_i}(\frac{E}{e_i})^{...}(\frac{T}{t_i})^{...}$ 综合 perplexity、能耗、延迟约束。LSTM encoder-decoder + FFN evaluator 把离散 ratio 嵌入连续表征空间 Θ，gradient ascent 沿 evaluator 梯度找最优表征 $\mathcal{E}_r^*$，beam search 解码出最优 layer-wise pruning ratio。然后用多个 plug-and-play [[LoRA]] adapter 为不同下游 app fine-tune。
- **在线 latency-aware inference**：(1) request-wise MoE router 用 BGE sentence embedding + cosine similarity 做 parameter-free soft gating，根据 prompt 动态混合 LoRA expert（公式 $\sigma(x,\phi)=\cos(\Gamma(x), \Gamma(\phi))$ 后 softmax）；(2) learning-based DVFS——MLP-based RL 控制器在 layer 边界 per-token 动态调 $V_{DD}$ 和 $F_{req}$，state 用前台 app 强度 + TTFT/TPOT target，reward 是能耗（power LUT 查表）。
- **28nm 加速器**：LPU（LoRA Processing Unit）用 eNVM 存 LoRA module 避免 SRAM leakage 与 DRAM 重载；SFU（Special Function Unit）配 fast-switching LDO + ADPLL 实现连续细粒度 DVFS；core 1.588 mm²；通过 PCIe 接入 Jetson 平台。

## 关键结果

- 在 Jetson Orin NX / Orin Nano 上跑 WikiText2，相比 Random/SliceGPT/LLMPruner/ShortGPT/FlexGen/OpenLLaMA-3B 等 baseline：能耗从 5.47–26.04 Wh 降到 3.46–3.54 Wh，延迟从 506–4674 s 降到 322–392 s。
- 推理加速最高 11.92×、能耗节省最高 7.36×。
- WikiText2/PTB 上 PPL 比 Random 好 5.1× / 3.4×；BBH/MMLU/Commonsense 87 task 比 Random 提升 6%–15.1%、比其他 baseline 平均 2.4%–6.1%。
- 关闭硬件加速器（CLONE-HW）能耗 4.81 Wh、延迟 462.72 s 仍优于全部 baseline，说明算法层独立有效。
- 跨 Llama-7B/Llama2-7B/Llama2-13B/Vicuna-7B 验证 generality（不是一次性 software-ASIC）。

## 相关

- **相关概念**：[[LoRA]]、[[MoE]]、[[Pruning]]、DVFS、Edge LLM、[[KV-Cache]]
- **同会议**：[[ATC-2025]]
