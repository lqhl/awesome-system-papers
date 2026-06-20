---
type: paper
name: Kitty
full_title: "KITTY: ACCURATE AND EFFICIENT 2-BIT KV CACHE QUANTIZATION WITH DYNAMIC CHANNEL-WISE PRECISION BOOST"
authors: [Haojun Xia, Xiaoxia Wu, Jisen Li, Robert Wu, et al.]
venue: MLSys
year: 2026
tags: [kv-cache, quantization, llm-inference, mixed-precision, triton]
source_pdf: "[[e369853df766fa44e1ed0ff613f563bd.pdf]]"
source_md: "[[e369853df766fa44e1ed0ff613f563bd]]"
---

# KITTY: ACCURATE AND EFFICIENT 2-BIT KV CACHE QUANTIZATION WITH DYNAMIC CHANNEL-WISE PRECISION BOOST (MLSys 2026)

> **一句话总结**：[[KIVI]] 等 [[KV-Cache]] **INT2** 在 reasoning LLM 上平均掉 **10–15** 点，而 **INT4** 近无损；Kitty 对 Key cache 按通道敏感度动态保留少量 **INT4** 通道、其余 **INT2**，算法–系统协同的 page 布局+Triton dequant，在 Qwen3/LLaMA3 七项任务近无损下 KV 内存 **~8×** 减、同预算吞吐 **2.1–4.1×**。

## 问题与动机

长 context [[LLM]] serving 中 [[KV-Cache]] 随 batch×length 爆炸（LLaMA3-70B 32×128K **>1.2TB**）。[[Post-Training-Quantization]] 可动态压 KV；4-bit 尚可，2-bit 严重伤 reasoning（表1：Qwen3 **-15.23** avg，LLaMA3 **-10.15**）。均匀提 Key 全精度有效但费内存；需 **channel-wise** 混合精度。

## 关键观察 / 隐含假设

- **观察 1：Key cache 通道幅度与量化敏感度高度不均；少量关键通道 dominate attention score 误差。**
  - **依赖假设**：离线/在线 ranking 通道敏感度可复用或轻量更新。
  - **可能失效场景**：新模型族通道模式漂移需重标定。

- **观察 2：Sink tokens（前32）+ K INT4/V INT2 组合优于反向；Key 提精度比 Value 更关键（KIVI-K4V2* 接近 FP16）。**
  - **依赖假设**：默认 S=32,R=128,G=128 平衡精度/压缩。
  - **可能失效场景**：极短 context sink 收益小。

- **观察 3：动态 4-bit boost 若 scattered read 会毁 GPU 效率；拆成两个统一 INT2 tensor 的 page 布局可 coalesced dequant。**
  - **依赖假设**：Triton page dequant + runtime pipeline 与 prefill/decode 集成。
  - **可能失效场景**：非 Triton 后端需重写 kernel。

- **假设 1**：近 **8×** KV 内存→**8×** batch 或 **2.1–4.1×** 吞吐（同内存预算）。**
  - **证据强度**：**强**——七任务两模型族+系统实测。

## 核心方法

**Dynamic Channel-wise Precision Boost**：按敏感度选 top-ρ Key channels 保持 INT4，其余 INT2；Value 侧 per-token sliding window（sink+local FP16/量化混合，继承 KIVI 思路）。

**Kitty page layout**：每 mixed-precision Key page 拆两统一 2-bit 张量，避免 hard-coded mask/scatter。

**Triton kernels**：量化新 token、cache update、attention dequant；轻量 runtime。

## 设计取舍

- **Channel boost vs token boost（[[KIVI]]/outlier）**：对齐硬件 coalescing，非稀疏 outlier 路径。
- **2-bit bulk + 少量 4-bit vs 全 4-bit**：更大压缩，ρ 调优关键。
- **PTQ vs QAT**：免重训，上限受 PTQ 约束。
- **边界条件**：Qwen3、LLaMA3 8B 级；B200 等 datacenter GPU。

## 实验与结果

- 七项任务两模型：近零精度损失 vs FP16（reasoning 含 MATH/GPQA）。
- KV 内存 **~8×** 减；batch **8×** 或吞吐 **2.1–4.1×**（同预算）。
- 优于 KIVI INT2 与多种 KV 量化基线。

## Critical Analysis

### 论证链条

INT2 统一量化失败 → 通道不均 → 动态 boost + 系统布局 → 8× 内存且精度保，算法–系统闭合典范。

### 假设压力测试

70B+、[[Tensor-Parallel]]、[[Speculative-Decoding]] 多副本 KV 时 boost 策略是否 per-rank 一致未详。与 [[FlexiCache]] offload 正交但未联合。

### 实验可信度

任务覆盖 reasoning；系统吞吐实测。缺：长运行 numerical drift、多租户 isolation。

### 系统性缺陷

论文未讨论 ρ 自动选择运维、与 [[vLLM]]/[[SGLang]] 默认集成路径。极端长 context promote 通道集合变化未跟踪。

## 局限与 Future Work

- **局限 1**：ρ 与 (S,R,G) 需 per-model 调参。
- **局限 2**：依赖 Triton 生态。
- **Future work 1**：在线通道敏感度 telemetry 驱动 ρ。
- **Future work 2**：与 [[CAGE]]/weight quant 联合测 W4A4K2 全栈。

## 相关

- **相关概念**：[[KV-Cache]]、[[Quantization]]、[[KIVI]]、[[PagedAttention]]
- **同类系统**：KIVI、BitDecoding、KVQuant
- **同会议**：[[MLSys-2026]]