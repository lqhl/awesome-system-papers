---
type: paper
name: HyperTinyPW
full_title: "Once-for-All Channel Mixers (HYPERTINYPW): Generative Compression for TinyML"
authors: [Yassien Shaalan]
venue: MLSys
year: 2026
tags: [tinyml, mcu, compression, ecg, pointwise-conv]
source_pdf: "[[6512bd43d9caa6e02c990b0a82652dca.pdf]]"
source_md: "[[6512bd43d9caa6e02c990b0a82652dca]]"
---

# Once-for-All Channel Mixers (HYPERTINYPW): Generative Compression for TinyML (MLSys 2026)

> **一句话总结**：HYPERTINYPW 用共享 micro-MLP 在 load-time 从 per-layer code 生成 1×1 PW 权重（PW1 保留 INT8），225 kB flash 达到 1.4 MB CNN 的 ≥95% macro-F1（6.31× 压缩），32–64 kB 预算下仍保持均衡检测。

## 问题

MCU 上 separable 1D CNN 的 **pointwise (1×1) mixer** 在 INT8 [[Quantization]] 后仍占 flash 大头，常超 64 kB。量化/剪枝/低秩仍要为每层存完整 PW；HyperNetwork/CondConv 等动态生成通常 per-input，带来分支与 SRAM 抖动，不适合实时 MCU。

## 核心方法

**Compression-as-generation**：每层 tiny code $z_l$ 经共享 generator $g_\phi$ 映射为 embedding，再经 per-layer head（可 factorize 为 $A_l B$）reshape 为 PW 矩阵。**仅在 boot/lazy load 时生成一次**，缓存后 steady-state 用标准 CMSIS-NN/TFLM INT8 kernel，无 per-input 分支。

**Hybrid 设计**：PW1 保持 stored INT8（形态敏感 early mixing）；PW2:L 合成。跨层共享 latent basis 减少冗余。

**Packed-byte accounting**：generator、heads、codes、PW1、backbone 全部计入 deployable flash。

## 关键结果

- Apnea-ECG / PTB-XL：**225 kB 时 6.31× 更小（84.15% 少字节）**，保留大模型 **≥95% macro-F1**
- 32–64 kB 预算：compact baseline 退化时仍保持 balanced detection
- Steady-state latency/energy 与 INT8 separable CNN baseline 匹配
- 三数据集（Apnea-ECG、PTB-XL、MIT-BIH）record/patient-wise split 验证

## 相关

- **相关概念**：[[Quantization]]、TinyML、depthwise separable conv
- **同类系统**：MCUNet、CMSIS-NN、TFLM
- **同会议**：[[MLSys-2026]]