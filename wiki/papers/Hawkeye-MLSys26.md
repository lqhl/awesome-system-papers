---
type: paper
name: Hawkeye
full_title: "Hawkeye: Reproducing GPU-Level Non-Determinism"
authors: [Erez Badash, Dan Boneh, Ilan Komargodski, Megha Srivastava]
venue: MLSys
year: 2026
tags: [verifiable-ml, gpu-simulation, tensor-core, reproducibility]
source_pdf: "[[73278a4a86960eeb576a8fd4c9ec6997.pdf]]"
source_md: "[[73278a4a86960eeb576a8fd4c9ec6997]]"
---

# Hawkeye: Reproducing GPU-Level Non-Determinism (MLSys 2026)

> **一句话总结**：用 targeted CUDA/PTX 测试逆向 Ampere/Hopper/Lovelace Tensor Core 的累加顺序、内部精度、rounding 与 subnormal 行为，在 CPU 上 bit-exact 复现 4096×4096 MatMul（FP16/BF16/FP8），为可验证 ML 提供零开销 oracle。

## 问题

ML-as-a-service 需第三方审计，但 Tensor Core 非确定性（累加顺序、rounding）使 CPU 重放与 GPU 结果 bitwise 不一致，无法区分作弊与硬件差异。

## 核心方法

**测试套件**：summation order、internal precision、rounding mode、normalization stage、subnormal handling——对 16×16 tile MMA 逐属性隔离。

**模拟器**：把 characterization 编码进 CPU simulator，复现 grouped summation 等硬件路径（如 Ampere FP16 Algorithm 13–14）。

**范围**：Ampere、Hopper、Ada Lovelace；FP16、BF16、FP8 E4M3。

## 关键结果

- 随机 16×16 tile：**100%** bit-exact（数十万组）
- 4096×4096 MatMul：CPU 复现与 GPU **100%** 一致（FP16 Ampere ~50.8s avg）
- 例：FP16 向量点积 L40S=0、A100=0.0020，说明架构差异可被精确建模

## 相关

- **相关概念**：[[Quantization]]、[[Tensor-Parallelism]]
- **同类系统**：Srivastava et al. verifiable training、pyxis-roc element-wise 复现
- **同会议**：[[MLSys-2026]]