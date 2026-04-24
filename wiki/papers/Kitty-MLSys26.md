---
type: paper
name: Kitty
full_title: "Kitty: Accurate and Efficient 2-bit KV Cache Quantization with Dynamic Channel-wise Precision Boost"
authors: [Haojun Xia, Xiaoxia Wu, Jisen Li, Robert Wu, Junxiong Wang, "et al."]
venue: MLSys
year: 2026
tags: [kv-cache, quantization, inference, gpu-kernel, long-context]
source_pdf: "[[e369853df766fa44e1ed0ff613f563bd.pdf]]"
source_md: "[[e369853df766fa44e1ed0ff613f563bd]]"
---

# Kitty: Accurate and Efficient 2-bit KV Cache Quantization with Dynamic Channel-wise Precision Boost (MLSys 2026)

> **一句话总结**：Kitty 通过算法-系统协同设计实现 2-bit [[KV-Cache]] 压缩——少量敏感 channel 保留 INT4、其余压到 INT2，配合 page-centric 布局和 Triton dequant kernel，KV 内存减少近 8 倍，吞吐提升 2.1×–4.1×，精度几乎无损。

## 问题

[[KV-Cache]] 是长上下文 LLM 推理的主要内存瓶颈——LLaMA3-70B 服务 32 个 128K 请求需要 1.2 TB 的 KV 缓存，远超单卡 B200 的 192 GB。现有 KIVI 等方法在 4-bit 下能保精度，但 2-bit 下推理精度崩塌：Qwen3-8B 平均下降 15.23、LLaMA3-8B 下降 10.15，尤其在长链推理任务上。

### 核心观察

作者发现 Key cache 的不同 channel 对 2-bit quantization 敏感度差异极大：少部分 channel 的量化误差对 attention score 影响显著，而其余 channel 可以安全压到 2-bit。这启发了 channel-wise precision boost：只把敏感 channel 提升到 INT4。

## 核心方法

**算法层（Dynamic Channel-wise Precision Boost）**：
- Sink token（前 32 个）保持 FP16
- Key cache 按 channel magnitude 选 top-K（12.5% 或 25%）提升到 INT4，其余 INT2
- Value cache 保留最近 local window（128 tokens）FP16，其余 per-token INT2

**系统层关键创新**：
- **Page-centric layout**：以 quantization group（G=128 tokens）为 page 粒度，借鉴 [[PagedAttention]]
- **Dense-Sparse 分解**：把 mixed-precision Key page 分解为两个统一 2-bit 张量——dense tensor 存所有 channel 的低 2 bits，sparse tensor 只存 boosted channel 的高 2 bits，加上 `boost_idx` 映射表
- **Triton dequant kernel**：on-chip 重建 FP16，避免 divergent memory access
- **三阶段 attention pipeline**：(1) 插入新 KV 到 Sink/Q-Buffer/Local；(2) `qk_kernel` + softmax + `sv_kernel` 算 attention；(3) Q-Buffer 满了才触发 quantization，每 G 步最多一次，开销可忽略

## 关键结果

- KV 内存近 **8× 减少**，同内存预算下 batch 可放大 8×
- 吞吐相比 FP16 baseline 提升 **2.1×–4.1×**
- 精度：Qwen3-8B 和 LLaMA3-8B 上，Kitty-Pro（25% boosted channel）在多个 benchmark（GSM8K、MATH-Algebra、GPQA-Diamond、HumanEval、AIME24/25）接近甚至超过 FP16
- 在 Qwen3-14B 和 LLaMA3.3-70B-Instruct 上 Kitty-Pro 达到或略超 FP16

## 相关

- **相关概念**：[[KV-Cache]]、[[Quantization]]、[[PagedAttention]]、[[Attention]]
- **同类系统**：KIVI、KVQuant、BitDecoding、QuaRot、MiniKV
- **同会议**：[[MLSys-2026]]
