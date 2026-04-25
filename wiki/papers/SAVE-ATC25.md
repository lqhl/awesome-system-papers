---
type: paper
name: SAVE
full_title: "SAVE: Software-Implemented Fault Tolerance for Model Inference against GPU Memory Bit Flips"
authors: [Wenxin Zheng, Bin Xu, Jinyu Gu, Haibo Chen]
venue: ATC
year: 2025
tags: [fault-tolerance, gpu, inference, edge-ai, bit-flip]
source_pdf: "[[atc2025-zheng.pdf]]"
source_md: "[[atc2025-zheng]]"
---

# SAVE: Software-Implemented Fault Tolerance for Model Inference against GPU Memory Bit Flips (ATC 2025)

> **一句话总结**：基于「不是所有 bit 都同等脆弱」的洞察，SAVE 把模型 bit 分为 robust / ranging / vulnerable 三类，把 vulnerable bit 涉及的计算优先放进 GPU reliable memory（如 NVIDIA Orin safety island），异步用 CPU 验证 unreliable memory；4K bit flip 下精度不掉，<9% 端到端延迟开销。

## 问题

边缘 GPU（自动驾驶、卫星、UAV）由于电压波动、辐射、温度变化导致 GPU memory 频繁 bit flip——一颗卫星每天约 16M 次 flip，UAV 低电压下 flip 率达 3.5%。仅 1 个 bit flip 就能让 ResNet 精度从 82% 跌到 0%。

现有方案两条路都不理想：
- **改模型结构**（RedNet 改激活函数、量化、压缩）：精度或泛化性损失。
- **保留模型，加冗余**（TMR、ECC）：TMR 2-3× 计算开销；ECC 只能纠 1 bit 错且需特定硬件，且面对宇宙射线导致的多 bit flip 失效。

## 核心方法

两个核心 insight：
1. **不是所有硬件 bit 同等可靠**：现代 AI 加速器（NVIDIA Orin）有 bit-flip-free 的 safety island（约 5-6MB），SRAM 也有 soft error 检测。
2. **不是所有 bit flip 都致命**：因模型非线性激活函数，某些 bit 翻转对结果几乎无影响（robust），某些可被范围检查（ranging，如 Sigmoid 输出 sign bit 必为 0），剩下才是 vulnerable bit。

SAVE 四阶段流水：

- **Selection**（离线静态分析）：在 model DAG 上沿层传播数值 range，识别每个 value 的 robust / ranging / vulnerable bit。基于 mathematical perturbation（10⁻⁵ 阈值）和 ReLU/GELU 等激活函数特性。结果存到 bit attribution cache。
- **Allocation**：把矩阵切成子块，按子块中 vulnerable bit 占比优先分配 reliable memory；模型权重始终放 unreliable memory（CPU 有副本可对照）；输入/输出做 in-place 改写以省 reliable memory。
- **Verification**：异步 CPU 验证。weight 用 PCIe DMA 拷回 CPU 比对；ranging bit 在 GPU 上 fused kernel 算 sign bit OR，CPU 校验；vulnerable bit 用 mixed-precision 整数 SIMD 重算（去掉 robust bit 后只剩约一半位宽，转 int16/int8）。
- **Edit**：检测到错误就从故障层重算。

深度细节回 [[atc2025-zheng]] 或 [[atc2025-zheng.pdf]]。

## 关键结果

- 端到端延迟开销平均 +8%（ViT 8-10%、CogACT/RDT 等机器人模型 <9%），对比 TMR 的 3× 显著好。
- 4K virtual consecutive bit flip 下 ResNet-50、ViT、Decision Transformer 精度无衰减；原始模型 3 个 bit flip 就降到 <5%。
- 对比 RedNet：在 Decision Transformer 上 RedNet 32 bit flip 后跌到 <10%，SAVE 保持。
- 提出 AccurateLatency = Latency × (1 + ErrorRate) 指标，SAVE 比 SOTA 低 90%。

## 相关

- **相关概念**：[[Fault-Tolerance]]、[[ECC]]、[[Bit-Flip]]、[[Quantization]]
- **同类系统**：RedNet、Dr.DNA、TMR、FT-ClipAct
- **同会议**：[[ATC-2025]]
