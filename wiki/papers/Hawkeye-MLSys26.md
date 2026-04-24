---
type: paper
name: Hawkeye
full_title: "Hawkeye: Reproducing GPU-Level Non-Determinism"
authors: [Erez Badash, Dan Boneh, Ilan Komargodski, Megha Srivastava]
venue: MLSys
year: 2026
tags: [verifiable-ml, gpu, tensor-core, floating-point, determinism, security]
source_pdf: "[[73278a4a86960eeb576a8fd4c9ec6997.pdf]]"
source_md: "[[73278a4a86960eeb576a8fd4c9ec6997]]"
---

# Hawkeye: Reproducing GPU-Level Non-Determinism (MLSys 2026)

> **一句话总结**：通过一系列针对 Tensor Core 的 PTX 级微 benchmark 精确逆向出 rounding / subnormal / 累加顺序，在 CPU 上**bit-exact** 复现 NVIDIA Ampere/Hopper/Ada Lovelace 上 FP16/BF16/FP8 的 16×16 matrix multiply-accumulate，为第三方 ML 审计打通了路径。

## 问题

Verifiable ML（审计 cloud ML 服务有没有偷偷换小模型、少训几步或埋后门）的传统加密方案依赖**确定性计算**，但现代 GPU 的 [[Tensor-Core]] 累加顺序、rounding、subnormal 处理都是实现相关的，同样输入不同架构结果可能不同。

具体例子：FP16 vector-vector 乘 `[65504, 1, -65504, 1] · [1, 0.001, 1, 0.001]`
- L40S (Ada Lovelace) 结果 **0**
- A100 (Ampere) 结果 **0.0020**

前人方案：禁用非确定 HW 特性（慢）、rounding intermediate（存储爆炸）、或干脆假装「discrepancy 够小」（无形式保证，对抗场景会失效）。

## 核心方法

**目标**：给定 GPU 架构和精度，CPU 上精确复现其 Tensor Core 的 $C_{t+1} = C_t + A_t B_t$（tile 16×16，FP16/BF16/FP8）。

**Tensor Core Characterization 方法**

用 inline PTX 调用 `wmma.mma.sync`，设计一套 targeted test：
- **Summation Dependency/Order Test**：定位累加顺序（哪些 partial sum 先合并）。
- **Internal Precision Detection**：推断每步 summation 的内部 bit 宽度。
- **Rounding Mode Detection**：识别每步用哪种 rounding。
- **Normalization Stage Detection**：查出哪几步把中间态归一化回标准 float。
- **Subnormal Behavior Detection**：subnormal 数被怎么处理。

把逆向结果编码成软件模拟器，在 CPU 上按同样 pipeline 跑即可 bit-exact。

**覆盖**：三种架构（Ampere、Hopper、Ada Lovelace）× 三种精度（FP16、BF16、FP8）；Lovelace 架构被发现与 Ampere 结构一致。

## 关键结果

- **100% success rate**：在三种架构 × 三种精度组合下，数十万条随机 16×16 tile 的 mma 全部 bit-for-bit 匹配。
- **跑到 4096 × 4096 matmul** 也复现。
- **CPU oracle 验证模式**：offline 一次 CPU 参考跑可对任意 GPU 执行无损校验，相比重新在 GPU 算几乎零开销。
- **不改 GPU kernel**，只需知道服务用的是哪种 GPU。

## 相关

- **相关概念**：[[Tensor-Core]]、[[Quantization]]、[[Determinism]]
- **同类系统**：pyxis-roc（GPU element-wise 复现但 matmul 未解决）、verifiable training 工作（Srivastava et al. 2024）
- **同会议**：[[MLSys-2026]]
