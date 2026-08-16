---
type: entity
kind: system
aliases: [KTransformers, ktransformers]
status: active
last_updated: 2026-08-14
tags: [llm-inference, moe, cpu-gpu-hybrid, expert-offloading, amx]
source_url: "https://github.com/kvcache-ai/ktransformers"
---

# KTransformers

> KTransformers 是面向低并发本地 [[MoE]] 推理的 CPU–GPU 混合系统。它不把所有权重搬进 GPU，而是让 GPU 执行 attention 和稠密部分，让 CPU DRAM 容纳并执行大多数 routed experts。

## 是什么

[[KTransformers-SOSP25]] 的目标是在一台有大容量主存、但 GPU 显存放不下整个模型的机器上运行 DeepSeek-V3/R1 这类超大 MoE。它把 attention、shared experts 等放在 GPU，routed expert 权重主要放在 CPU DRAM；prefill 的 CPU expert 使用 AMX 矩阵核，低 batch decode 使用 AVX-512 路径。

系统有三个主要机制：

1. 按算术强度选 AMX 或 AVX-512，并对权重做适合 cache 和 NUMA 的预排布。
2. 用一个 [[CUDA-Graph]] 覆盖整段 decode，减少每层反复从 CPU 发起 GPU kernel 的开销。
3. 可选的 Expert Deferral 把一部分 expert 推迟到下一层 attention 期间，用近似执行顺序换 CPU/GPU 重叠。

这个定位很窄：论文所有主要性能实验都是 batch size 1，并不是面向多租户、大 batch 的云端 serving engine。

## 关键观察 / 隐含假设

- **CPU 算得慢不只是带宽问题。** 原始 profiling 中，一台 A100+双路 Xeon 运行 671B MoE 时 GPU 利用率低于 30%，AMX 只达峰值的约 7%；对照系统每 token 还可产生 7,000 多次 kernel launch。因此 KTransformers 同时修改 CPU kernel、权重布局和 GPU 发射路径，而不是只做 offload（[[KTransformers-SOSP25]]）。
- **prefill 与 decode 不应强行共用一条 CPU 路径。** KTransformers 的 AMX prefill 优化取得了很大加速，但 [[Wang-LocalMoEInference-OSDI26]] 在更长 prompt 上发现，把 expert 权重流式送到 GPU 计算更合适；该系统只在 4K token 以上启用这条路径，短 prompt 仍留在 CPU。这表明“CPU 算 expert”不是与阶段无关的答案。
- **Expert Deferral 是近似优化，不是免费的并行。** 它只用于 decode，最高额外提升约 45%；DeepSeek-V3 的 LiveBench 平均分数下降约 0.5 个百分点。评测覆盖较少，不能推导每个任务都只损失 0.5%。
- **收益依赖硬件与预处理。** AMX/AVX-512、双路 [[NUMA]] 内存带宽、离线权重重排和固定模型形状都在设计中。换成低带宽桌面 CPU、无 AMX 平台或频繁更换模型时，结果不能直接外推。
- **本地交互性能不等于云端 SLO。** [[Wang-LocalMoEInference-OSDI26]] 在双路 1.15 TB DRAM+1–2 张 RTX 5090 上报告原始 FP8 DeepSeek-R1 单流 21.5 token/s，并把 20 token/s、30 秒 TTFT 当作交互目标；但没有多租户排队、p99、可用性或成本证据。它也不能把 KTransformers 的低并发定位改写成云服务。

## 设计路线与取舍

| 路线 | expert 权重放在哪里 | 在哪里算 | 主要优点 | 主要代价 |
|---|---|---|---|---|
| KTransformers | CPU DRAM | CPU | 不用每层搬权重到 GPU | 依赖 CPU 带宽、AMX/AVX 和低并发 |
| 流式长 prefill | CPU DRAM 是权威副本 | GPU | 长 prompt 可用计算遮住权重传输 | 短 prompt 不划算，还需显存环形缓冲 |
| expert paging/cache | GPU、DRAM 或 NVMe 分层 | 主要在 GPU | 保留 GPU kernel 生态 | 冷 expert miss 和链路传输可进入关键路径 |

KTransformers 的取舍是“尽量少搬权重，在 CPU 上把 expert 算快”。[[FluxMoE-arXiv26]]、[[MOE-INFINITY-arXiv24]] 和 [[OD-MoE-arXiv25]] 分别探索 GPU paging、NVMe/DRAM cache 和预测式加载；这些论文中并没有都在同一硬件、同一精度下与 KTransformers 做对照，所以这里只把它们当作设计空间，不排统一性能名次。

## 演进时间线

- **2025·SOSP**：[[KTransformers-SOSP25]] 系统化提出 AMX expert kernel、单 CUDA Graph 异步调度和 Expert Deferral。
- **2025–2026**：[[ContextAwareMoE-CXLNDP-arXiv25]]、[[CoX-MoE-DAC26]]、[[FluxMoE-arXiv26]] 等工作把它作为 CPU–GPU 混合 MoE 路线的代表。
- **2026·OSDI**：[[Wang-LocalMoEInference-OSDI26]] 进一步把长 prefill、短 prefill 和 decode 拆成三条执行路径，也直接暴露了 KTransformers 在长 prompt 和原始 FP8 模型上的边界。

## 相关概念

- [[MoE]]
- [[KV-Cache]]
- [[CUDA-Graph]]
- [[NUMA]]
- [[Quantization]]

## 相关论文

- [[KTransformers-SOSP25]] — 系统本身的机制、batch=1 评测与近似精度边界。
- [[Wang-LocalMoEInference-OSDI26]] — 长 prefill 流式上 GPU、decode 留 CPU 的对照路线。
- [[FluxMoE-arXiv26]] — 在 serving engine 中分页管理 expert 权重，将 HBM 在 expert 和 KV 之间分配。
- [[MOE-INFINITY-arXiv24]] — 用 NVMe/DRAM 多级 expert cache 运行超大 MoE。
- [[OD-MoE-arXiv25]] — 用预测加载代替长期 expert cache。
