---
type: paper
name: HyperTinyPW
full_title: "Once-for-All Channel Mixers (HYPERTINYPW): Generative Compression for TinyML"
authors: [Yassien Shaalan]
venue: MLSys
year: 2026
tags: [tinyml, compression, hypernetwork, mcu, ecg, edge-ai]
source_pdf: "[[6512bd43d9caa6e02c990b0a82652dca.pdf]]"
source_md: "[[6512bd43d9caa6e02c990b0a82652dca]]"
---

# Once-for-All Channel Mixers (HYPERTINYPW): Generative Compression for TinyML (MLSys 2026)

> **一句话总结**：用一个共享 micro-MLP 在 load time 从每层的小 latent code 合成 1×1 pointwise (PW) 卷积权重，替代传统 INT8 存储；225 kB 预算下匹配 1.4 MB CNN 精度（6.31× 压缩、84.15% byte 下降），在 MCU 上保留标准 INT8 推理路径。

## 问题

TinyML 在 MCU（kB 级 flash/SRAM）上部署 separable CNN：depthwise 卷积占大部分 MAC，但 **pointwise（1×1）mixer 占绝大多数参数**——即便 INT8 量化后仍常超 64 kB flash 上限。

已有方案的局限：
- **Quantization / pruning / low-rank**：每层仍各自存储一份权重，解决层内冗余但不解决层间冗余；<64 kB 时仍撑不住。
- **HyperNetworks / CondConv / 动态 filter**：per-input 生成会引入控制流、SRAM 峰值、latency jitter，MCU 实时预算不能容忍。

## 核心方法

**核心想法：compression-as-generation（load-time，非 per-input）**

- 每层 $l$ 只存一个小 code $z_l \in \mathbb{R}^{d_z}$；所有层共享一个生成器 $g_\phi$（micro-MLP），在 boot 或懒加载时算 $h_l = g_\phi(z_l)$，再经 per-layer head $H_l$ 还原成完整 PW 权重矩阵 $\widehat{W}_l$。
- $H_l$ 可进一步分解成 $H_l = A_l B$（per-layer adapter + shared matrix）进一步共享参数。
- **PW1 保留为 stored INT8**（morphology-sensitive 早期 mixing 不能生成），PW2:L 全走生成。
- 合成完权重就缓存，稳态推理用 CMSIS-NN/TFLM 标准 INT8 1×1 conv kernel——**无自定义 op、无 per-input 控制流**。

**TinyML 真实 packed-byte 会计**：显式算 generator、heads、codes、kept PW1、backbone 的 packed bytes（4/6/8-bit 可选），而不是只报浮点参数量。

**复合训练 loss**：CE + focal（不平衡）+ KD + feature matching + soft-F1 + 谱正则 + L1（codes 与 heads 稀疏）。

**部署选项**：boot synthesis（启动慢但推理稳）vs lazy synthesis（启动快但首次用慢）；两者稳态 latency 一致。

## 关键结果

- **Apnea-ECG / PTB-XL / MIT-BIH** 三个 ECG 任务验证。
- **225 kB 档位**：macro-F1 匹配 1.4 MB CNN，压缩 6.31× / 少 84.15% byte，保留 ≥95% 大模型 macro-F1。
- **32–64 kB 档位**：紧预算下仍保持平衡检测，小 baseline 此时已崩。
- **兼容性**：推理走标准 CMSIS-NN kernel，可直接部署到 Arm M-series MCU。

## 相关

- **相关概念**：[[Quantization]]、[[HyperNetwork]]
- **同类系统**：MobileNet、MCUNet、Once-for-All NAS、CondConv、Dynamic Filter Network
- **同会议**：[[MLSys-2026]]
