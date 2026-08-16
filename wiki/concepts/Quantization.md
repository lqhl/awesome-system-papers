---
type: concept
aliases: [quantization, Quantization, quantized, INT8, FP8, INT4, W8A8, W4A16, PTQ, QAT, post-training quantization, quantization-aware training, mixed-precision]
parent: "[[LLM-Inference]]"
last_updated: 2026-08-14
tags: [model-compression, llm-inference, efficiency]
---

# Quantization

> 量化（quantization）用较少 bit 表示权重、激活、[[KV-Cache]] 或训练状态，以减少容量、内存带宽和通信；它能否真正加速，取决于数值格式、缩放粒度、硬件指令、kernel 与工作负载是否一起匹配。

## 核心思想

浮点或整数张量通常不能直接删掉低位。系统先按某个范围选择缩放因子（scale），把高精度值映射到有限的低精度取值；非对称整数格式还会使用 zero point。计算时可以先反量化（dequantize）再算，也可以由 Tensor Core 等硬件直接执行低精度矩阵乘，并用 FP16、BF16、FP32 或 INT32 累加。

量化至少有四个彼此独立的选择轴：

- **量化对象**：weight-only 主要省模型读取；weight + activation 可以使用低精度矩阵单元；KV 量化主要扩展上下文和 batch；gradient、optimizer state 与 collective 量化主要服务训练。
- **量化时机**：后训练量化（post-training quantization，PTQ）不重新训练或只做少量校准；量化感知训练（quantization-aware training，QAT）让模型在训练中适应误差，成本更高但通常更稳。
- **数值格式**：INT8、INT4、FP8、FP4、NVFP4、MXFP4 的动态范围、特殊值、scale 表示和硬件支持不同。写“4-bit”不足以确定算术语义。
- **缩放粒度**：per-tensor 实现简单但容易被 outlier 支配；per-channel、per-group、per-token、block-wise 更能适应分布，却增加 scale metadata、索引和 kernel 复杂度。

模型命名中，W4A8 表示 4-bit 权重和 8-bit activation，W4A16 表示权重 4-bit、activation 16-bit。这个标记仍没有说明 scale 粒度、对称/非对称、累加精度、KV dtype 和校准数据，所以不同论文的 W4A8 不能默认等价。

## 为什么重要

LLM decode 常要每步重新读取大量权重和越来越长的 KV，低 batch 时容易受 HBM 带宽限制。weight-only INT4 能让模型进入更小显存，或让同一 GPU 放更多 batch；KV 量化则直接改变可保存的 token 数。对训练，FP8/FP4 还会减少激活、梯度和通信字节，并提高硬件矩阵乘吞吐。

但理论 bit 数不等于端到端收益。低精度硬件若只支持对称组合，W4A8 可能需要 padding、拆 bitplane、生成 partial product 或先反量化；这些开销可以吃掉全部带宽收益。[[ADAngel-OSDI26]] 的核心证据正是：prefill、decode、`M/N/K` 与 bit-width 改变时，Padding、Split、Bitwise 三种实现的胜负会交叉。

量化也不是只看 perplexity 的压缩开关。[[DriftBench-MLSys26]] 说明，同一权重和输入在不同精度、硬件和框架上可能出现功能 flip；Math 平均 flip rate 为 16.74%，Code 仅 0.09%。因此生产验收至少要同时看任务质量、功能一致性、峰值内存、TTFT、TPOT、吞吐和能耗。

## 关键观察 / 隐含假设

- **观察：容量收益、算力收益和质量收益是三件事。** weight-only 压缩通常能省容量和带宽，却不一定命中低精度 Tensor Core；W8A8/FP8 更易得到算力收益，但 activation outlier 可能增加质量风险。部署报告必须拆开这三个目标。
- **观察：非对称 bit-width 需要 workload-aware kernel。** [[ADAngel-OSDI26]] 在 Jetson AGX Orin 上为每组模型、GPU 和精度离线扫描策略；Llama-3-8B W4A8 prefill 相对论文所用 TensorRT-LLM 配置的 TTFT 加速为 1.17–2.38 倍，decode 相对 llama.cpp 最高 5.10 倍。对比格式并不完全相同，而且一次 profile 约 5.7 小时、多布局权重占 14.96 GiB，所以不能只保留速度数字。
- **观察：反量化可能比读取压缩权重更贵。** [[QFactory-ATC25]] 将量化 tile 和计算图保留到更晚阶段，再联合安排反量化、内存和 kernel；单 kernel 平均比 BitBLAS 快 1.66 倍，接入 vLLM 的端到端 decode 加速为 1.23 倍。这说明“压得更小”只有在执行图能消费该格式时才有价值。
- **观察：最佳 scale 不一定由最大绝对值决定。** [[ScaleSearch-MLSys26]] 在 NVFP4 scale 邻域 `[-2,+6]` 搜索，合成误差降低约 27%，Qwen3-8B MATH500 PTQ 最高增加 15 分；量化步骤成本为默认路径的 1.74 倍。其 ScaleSearchAttention 主要由仿真验证，没有完整 LLM serving 的 TPOT/QPS，因此不能把接近 SageAttention3 的 kernel 吞吐写成生产服务结论。
- **观察：K 与 V、layer、head 和 token 对误差的敏感度不同。** [[DiffKV-SOSP25]] 用差异化策略把 KV 缩小 2.7–5.7 倍、吞吐提高 1.9–5.4 倍，并报告接近无损；结果支持非均匀精度，但仍只对论文所测模型、任务和压缩预算成立。
- **观察：朴素 KV INT4 可能严重破坏质量。** [[SolidAttention-FAST26]] 报告 Qwen2.5-7B 上其所用 KV INT4 baseline 的平均精度从 71.39 降到 18.63；该结果不能外推到所有 KV quantizer，却足以否定“4-bit KV 天然可用”的假设。
- **观察：低精度训练必须控制数据流中的重复转换。** [[FP8FlowMoE-MLSys26]] 发现 MoE row/column scale 不一致会产生 double quantization；通过 scaling-aware transpose，把 MoE 路径 cast 从 12 次减到 2 次，DeepSeek-V3 671B 训练吞吐最高提高 21%、单卡峰值显存减少 16.5 GB。16B 模型训练 200B token 的曲线与 BF16 重合，但这仍不是所有模型和优化器的通用收敛证明。
- **观察：量化也会改变系统的最优调度和内存设计。** [[DCP-OSDI26]] 明确指出线性层 profile 会随量化、kernel 和 batch 改变；[[DirectKV-OSDI26]] 当前假设 FP16/BF16 KV，FP8/INT4 会要求重写 zero-copy fusion；[[FluxMoE-arXiv26]] 也指出，expert 权重已强量化时，分页和无损压缩的空间收益会缩小。
- **观察：传输压缩与计算量化的目标不同。** [[CacheGen-SIGCOMM24]] 用 token、layer 与 channel 的统计结构压缩跨机器 KV，带宽减少 3.5–4.3 倍，相对重新传文本和量化基线的 TTFT 分别降低 3.1–4.7 倍、3.2–3.7 倍。它优化的是传输 bitstream，不等于让 Attention 直接以该格式计算。
- **假设：校准集能代表部署流量。** PTQ 的 scale、outlier 与 mixed precision 分配依赖校准样本；长推理、代码、Safety、agent tool-use 或分布漂移可能改变误差。DriftBench 的 workload 差异说明，单一 WikiText perplexity 不能替代应用回归。
- **假设：硬件格式和软件版本稳定。** ADAngel 的 oracle map、ScaleSearch 的 E4M3 offset 和 FP8-Flow-MoE 的 transpose 都与特定 ISA、layout 和 kernel 绑定。驱动、模型 shape 或 GPU 代际变化后需要重新验证，而不是沿用旧 profile。

## 设计空间与取舍

- **Weight-only PTQ**：最容易部署，通常先解决模型容量和 decode 权重带宽；activation 保持高精度，计算单元利用率未必提高。[[DecDEC-OSDI25]] 把低 bit 权重残差留在 CPU，并按 activation outlier 取回少量通道；3-bit Llama-3-8B perplexity 从 10.15 降到 9.12，RTX 4050 Mobile 只慢 1.7%，但依赖 CPU–GPU 协同与特定模型。
- **Weight + activation 量化**：W8A8、W4A8 等可利用整数或低精度 Tensor Core；精度和 kernel 路径更复杂。ADAngel 说明静态选一种 mapping 不够，QFactory 说明反量化也要进入图优化。
- **FP8/FP4 浮点格式**：动态范围比同 bit 整数友好，适合训练和新硬件；scale 与 accumulation 仍决定误差。[[FlashAttention-3-NeurIPS24]] 的 FP8 attention 依赖 Hopper pipeline 和 incoherent processing，不能只把 BF16 tensor 改 dtype。
- **KV 量化**：最直接扩展 context 与 batch，但误差会在每个 decode step 被 Attention 读取。可按 K/V、head、layer、token 和 sink block分配不同精度；混合精度更稳，也增加 block metadata 和 kernel 分支。
- **训练状态量化**：FP8 activation/gradient、8-bit optimizer 可以省显存和通信，但必须保证 sharding 边界与量化 block 对齐。[[veScale-FSDP-MLSys26]] 说明传统 element/row shard 会切断 128×128 FP8 或 32×32 INT8 block，因此分片格式也是数值正确性的一部分。
- **QAT 与 mixed-precision search**：通常能得到更好的质量—性能前沿，代价是重新训练、搜索和版本绑定。[[OptiKit-MLSys26]] 把量化、质量门禁、SLO benchmark 和 Bayesian tuning 串成生产 pipeline；三模型族吞吐超过 2 倍、人工工时从约 80–100 小时降到 15–25 小时，但这是 eBay 工具链与所测 recipe 的结果。
- **边缘与本地部署**：内存小不代表一定要 INT4。[[Wang-LocalMoEInference-OSDI26]] 保留 DeepSeek-R1 的约 1 TB 原生 FP8 权重在双路 CPU DRAM，decode 用 AVX-512 在寄存器内转 BF16；单流达到 21.5 token/s。它需要 1.15 TB 主存和服务器 CPU，并非普通笔记本方案。

## 引用本概念的代表性论文

- [[ADAngel-OSDI26]] — 为 W2/W3/W4/W5A8 的 mixed-precision GEMM 按 shape 选择 Padding、Split 或 Bitwise。
- [[Wang-LocalMoEInference-OSDI26]] — 在约 1 TB 原生 FP8 MoE 上按阶段分配 CPU/GPU 执行，而不是进一步压成 INT4。
- [[Sereno-OSDI26]] — 在手机 NPU 上以 Llama-3.1-8B W4A16 测系统争用；量化是实验配置，不是论文的主要贡献。
- [[StriaTrace-OSDI26]] — 在 Qwen3-Coder-30B FP8 MoE 的生产推理实例上验证低开销 tracing；同样把量化当实际部署环境。
- [[QFactory-ATC25]] — 将量化和反量化表示提升为 compiler IR，生成并调优端到端 kernel。
- [[DecDEC-OSDI25]] — 用 CPU 残差按运行时 activation outlier 修复低 bit 权重误差。
- [[DiffKV-SOSP25]] — 按 KV 角色和动态重要性做差异化压缩。
- [[CacheGen-SIGCOMM24]] — 为远端 KV 传输生成带宽自适应压缩 bitstream。
- [[FP8FlowMoE-MLSys26]] — 让 MoE 训练中的 FP8 scale 随数据流一致传递，减少重复量化。
- [[ScaleSearch-MLSys26]] — 搜索 block floating-point scale，并探索 NVFP4 Attention 与 KV。
- [[DriftBench-MLSys26]] — 用功能 flip 而不是仅 perplexity 衡量 precision、hardware 和 framework 迁移风险。
- [[ExecuTorch-MLSys26]] — 通过导出时验证与 4-bit weight recipe 把量化带到边缘 runtime；论文报告模型体积减少 50%。
- [[SolidAttention-FAST26]] — 用质量崩溃反例说明 AIPC 长上下文不能只依赖朴素 KV INT4。
- [[FlashAttention-3-NeurIPS24]] — 将 FP8、异步 Hopper 指令与 Attention pipeline 共同设计。
- [[DeepSeek-V4-arXiv26]] — 使用 FP4 QAT 等全栈低精度设计；模型报告不能替代独立系统复现。
- [[FluxMoE-arXiv26]] — 讨论 MoE 权重 paging 与已有量化之间的容量收益重叠。
- [[veScale-FSDP-MLSys26]] — 让分布式 shard 边界保留量化 block 和矩阵优化器语义。
- [[OptiKit-MLSys26]] — 将 recipe、质量评测、SLO benchmark 和搜索组成企业量化流水线。

## 已知局限 / 开放问题

- **统一质量口径。** 应同时报告 perplexity、任务正确率、Safety、长上下文和功能 flip；不能只选对量化最友好的单一 benchmark。
- **统一系统口径。** 至少给 peak memory、TTFT、TPOT、throughput、energy/token、量化/编译时间和额外 metadata；kernel speedup 不能替代端到端结果。
- **控制格式变量。** baseline 应尽量使用相同 W/A/KV bit、scale 粒度、accumulation 和模型质量；无法相同时要明确说明，像 ADAngel 对 TensorRT-LLM 的比较就不是等格式实验。
- **处理动态 workload。** batch、context、temperature、speculative decoding、MoE routing 和多租户干扰会改变 break-even，需要在线校准或安全 fallback。
- **验证跨硬件迁移。** NVIDIA INT/FP Tensor Core、AMD matrix core、NPU 和 CPU VNNI 的支持不同；可迁移 cost model 仍比每设备穷举更难。
- **研究误差积累。** 长 chain-of-thought、RL rollout、百万 token context 和频繁 KV 迁移会多次消费低精度状态，目前跨阶段误差的系统证据仍不足。
