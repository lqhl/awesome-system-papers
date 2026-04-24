---
type: paper
name: DecDEC
full_title: "DecDEC: A Systems Approach to Advancing Low-Bit LLM Quantization"
authors: [Yeonhong Park, Jake Hyun, Hojoon Kim, Jae W. Lee]
venue: OSDI
year: 2025
tags: [llm-inference, quantization, on-device, gpu, heterogeneous-memory]
source_pdf: "[[osdi25-park-yeonhong.pdf]]"
source_md: "[[osdi25-park-yeonhong]]"
---

# DecDEC: A Systems Approach to Advancing Low-Bit LLM Quantization (OSDI 2025)

> **一句话总结**：DecDEC 把 LLM 量化权重的残差存在 CPU 上，每步解码时根据实时 activation outlier 动态取回 salient 通道的残差做误差补偿，3-bit Llama-3-8B 上 perplexity 从 10.15 降到 9.12（优于 3.5-bit），GPU 内存开销 <0.0003%、RTX 4050 Mobile 仅 1.7% 推理减速。

## 问题

低位 [[Quantization]]（3/4-bit weight-only PTQ）是 LLM 上端侧落地的主流方案，但精度损失在 3-bit 显著。既要精度、又要低显存和低延迟：GPU 显存紧张不能加参数，PCIe 带宽（~32 GB/s）比 GPU 显存（~1 TB/s）低一个量级又限制了跨 CPU 的补偿信息传输。

过往针对 activation outlier 的方法（AWQ、SqueezeLLM、其他 outlier-aware 量化）都是**离线**在 calibration set 上**静态**挑出 salient channel。但作者测量发现 activation outlier 分布在每个 decoding step 之间高度动态——按静态分析挑出的 top-1% / top-5% outlier，与真正运行时的 ground-truth recall 只有 ~20%。静态方法遗漏了大多数真实热通道。

## 核心方法

**DecDEC (Decoding with Dynamic Error Compensation)** 是一个推理时方案，核心公式把每个 linear 从 $Wx$ 增强为 $(\widehat{W} + R \odot M) x$，其中 $\widehat{W}$ 是量化权重（在 GPU 上），$R$ 是 FP16 残差（存在 **CPU** 内存），$M$ 是按当前 activation 动态生成的二值 mask，只选中 top-k salient 输入通道。

实现上有四个关键：

1. **残差再量化**：$R$ 以 4-bit 对称 uniform quantize 存在 CPU，每输出通道一个 scale。4-bit 在一致传输量下误差最低（vs 2/8/16-bit）。
2. **Zero-copy residual fetch**：用 CUDA zero-copy 取代 `cudaMemcpy`——按行粒度（几十 KB）小传输时 DMA 开销过大，zero-copy 让 GPU 发 cacheline 级请求，适合细粒度。
3. **Fast approximate Top-K**：把 4096-D activation 切成 4 个 1024-D chunk，每 chunk 内独立桶排 bucket-based Top-K；桶边界按 calibration 数据离线校准（$b_0^k, b_{15}^k$ 两个锚点，其余均匀切），平衡精度与对 out-of-distribution 值的鲁棒性，必要时对最后一个桶随机选剩余 slot。
4. **Kernel fusion**：Top-K 选 + 残差 fetch + residual GEMV + 累加到 base GEMV 结果全部 fuse 进一个 CUDA kernel；所有动作在与 base GEMV 平行的 CUDA stream 上运行，目标是藏在 base GEMV 的时间里。

作者还提供了 **parameter tuner** 两阶段自动选择 $n_{tb}$（thread block 数）和 $k_{chunk}$（每 chunk 选取通道数），以满足用户给定的目标 slowdown 上限。

## 关键结果

- 3-bit Llama-3-8B-Instruct：perplexity **10.15 → 9.12**（超过 3.5-bit 基线），GPU 内存增加 **<0.0003%**、RTX 4050 Mobile 推理减速仅 **1.7%**
- 对 AWQ、SqueezeLLM 这两种 SOTA PTQ 方法都能增强；3-bit Phi-3 perplexity 5.96 → 5.53（AWQ）、5.92 → 5.45（SqueezeLLM）
- MT-Bench、BBH 等 benchmark 上 3-bit/3.5-bit 模型普遍有明显提升
- 相比静态选通道（Hessian-based）和随机选，DecDEC 在同等通道数下 perplexity 更低，且 recall vs exact Top-K 达 ~80%（vs 静态 ~30%）
- 在 5 款消费级 GPU（RTX 4090/4080S/4070S + 4070M/4050M）上验证 knee-point 行为与理论预测一致

## 相关

- **相关概念**：[[Quantization]]、weight-only PTQ、activation outlier、salient channel、Top-K、CUDA zero-copy、PCIe bandwidth、GEMV
- **同类方法**：AWQ、SqueezeLLM、GPTQ、SmoothQuant、LUT-GEMM kernel
- **相关场景**：on-device LLM inference（desktop/laptop/edge GPU）
- **同会议**：[[OSDI-2025]]
