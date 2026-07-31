---
type: paper
name: KAIROX
full_title: "KAIROX: Adaptive GPU–CPU Hybrid LLM Inference via Online Neuron Balancing"
authors: [Yapeng Jiang, Minghao Gan, Zicong Hong, Wuhui Chen, Junyuan Liang, Yue Yu, Meng Guo, Zibin Zheng]
venue: OSDI
year: 2026
tags: [llm-inference, gpu-cpu, activation-sparsity, edge-computing, offloading]
source_pdf: "[[osdi26-jiang-yapeng.pdf]]"
source_md: "[[osdi26-jiang-yapeng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 在线 Neuron Balancing 的 GPU–CPU Hybrid [[LLM|LLM]] Inference（OSDI 2026）

> **原题**：KAIROX: Adaptive GPU–CPU Hybrid LLM Inference via Online Neuron Balancing

> **一句话总结**：consumer PC 上静态 hot/cold neuron placement 会随 batch 与 semantic drift 把 CPU 变成瓶颈；KAIROX 提前预测下一层、用 Temporal Activation Momentum 保留持续热点并反馈调节迁移强度，相对 llama.cpp/PowerInfer/Neuralink/Q-Infer 标准生成最高提升 7.57×/3.70×/6.35×/3.76×。

## 问题与动机

模型大于 VRAM 时，llama.cpp 按 layer 把部分权重/计算留 CPU，CPU 可占 90%以上 latency。activation-sparse system 只计算预测 active FFN neuron，并离线把频繁 neuron 放 GPU；但 batch 增加与 token semantic drift 会激活大量“cold” neuron，静态 CPU workload 从 102.8 ms 增至 551.7 ms，TPOT 可在 50–200 ms 波动。

在线把 active neuron 移 GPU 可利用闲置 GPU，却产生 PCIe transfer；立即搬每个新 active neuron 又会追逐 one-hit wonder、挤掉持续热点。KAIROX 需要同时决定何时提前搬、哪些值得搬，以及 CPU-bound/I/O-bound 时搬多少。

## 关键观察 / 隐含假设

- **观察 1**：FFN 占约 70% parameter、decode 约 80% compute，activation 可被轻量 predictor 预测且具 co-activation/temporal locality（§2）。
  - **依赖假设**：目标模型有足够 neuron [[Sparse-Attention|sparsity]]、预测错误不显著损害 output quality。
  - **可能失效场景**：dense/non-ReLU activation、[[MoE|MoE]] routing 主导、fine-tuned domain 改变 locality。
- **观察 2**：layer `i` [[Attention|attention]] 后即可预测 `i+1` FFN，把 transfer 与当前 FFN CPU/GPU compute overlap（§5）。
  - **依赖假设**：predictor 与 actual activation 相关，overlap window 长于必要 [[PCIe|PCIe]] transfer。
  - **可能失效场景**：CPU compute 很短、PCIe 慢、predictor GPU contention 抢占 main kernel。
- **观察 3**：CPU latency 与 reload latency 是反向瓶颈，固定 migration intensity 无法跨 model/hardware/phase 最优（§7、图 10–11）。
  - **依赖假设**：runtime feedback 稳定且变化慢于 controller 收敛。
- **假设 1**：neuron-level sparse kernel/index overhead 在 batch 不大时低于 dense GEMM；论文也观察某些 speculative batch 中 llama.cpp 反超 sparse baseline。
  - **证据强度**：强，评测明确暴露边界。

## 核心方法

Live Pipeline 在 layer `i` attention 完成后运行 adjacent predictor 得到 `i+1` active neuron，按 co-activation group/reorder 发起 host→GPU prefetch；同时执行 layer `i` FFN 的 CPU/GPU sparse compute，再 merge result。除首层外 predictor 被 CPU MLP overlap，有效 end-to-end overhead 仅 1%–2%。

Temporal Activation Momentum（TAM）为 neuron group 维护带 decay 的 activation score；持续多 token active 累积 momentum，瞬时 spike 迅速衰减。GPU cache eviction/admission 按 TAM，而非当前 top-k/LRU，避免反复 transfer one-hit wonder。

Adaptive Neuron Balancer 观察 normalized CPU compute 与 reload latency，在线调 decay/intensity `λ`：CPU-bound 且 PCIe 有余量就 aggressive migrate，I/O-bound 则提高保守程度。每 layer 可收敛不同 `λ`，例如高层约 0.85、reload 少于 75 groups/step。

## 设计取舍

- **dynamic placement 换 PCIe traffic**：适应 drift/batch，但若 locality 弱则迁移无收益。
- **momentum 换 responsiveness**：过滤 spike，突然永久 phase change 时会迟缓。
- **feedback controller 换 static simplicity**：跨硬件适配，threshold/oscillation/measurement overhead 增加。
- **activation sparsity 换 kernel irregularity**：小 batch 有利，大 batch dense GEMM 可能更快。

## 实验与结果

- PC-Low：RTX 3080 Ti 12 GB、12 CPU threads、PCIe 3.0×16；PC-High：RTX 4090 24 GB、16 threads、PCIe 4.0×16；context 1024、output 512，对比 llama.cpp、PowerInfer、Neuralink、Q-Infer（§9、Appendix A）。
- standard completion 最高相对四 baseline 分别 7.57×、3.70×、6.35×、3.76×；相对 llama.cpp 两 PC geomean 3.15×/3.93×，相对 sparse baseline 约 2.1×（§9.2）。
- [[Speculative-Decoding|speculative decoding]]（5 draft tokens）相对 llama.cpp geomean 2.23×/2.91×；对 sparse baseline 为 1.53–2.11×/1.53–1.88×（§9.2）。
- static TAM 相对 Top-K 将 reload latency 降约 1.8–2.2×；ablation 中 Live Pipeline 提升 1.91×/1.39×，加 balancing 到 3.32×/2.88×，adaptive 最终 3.70×/3.46×（§9.3–9.4）。
- GPU utilization 最高提高 5.35×/2.98×；PC-Low 仅 7 GB VRAM 跑约 14 GB Bamboo-7B 仍约 25 tokens/s，PC-High 14 GB budget 超过 baseline 24 GB（§9.3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| online balancing 显著优于 static/offload baseline | §9.2：geomean 约 2.1× sparse baseline、最高 7.57× | 两 consumer PC、多 sparse/[[Quantization\|quantized]] model | 强 |
| TAM 过滤 transient transfer | §9.3、图 10：reload latency 低 1.8–2.2× | 两 model、PC-Low | 强 |
| feedback adaptation 有独立增益 | §9.4、图 15：3.32→3.70×、2.88→3.46× | incremental ablation | 强 |
| pipeline 隐藏 predictor cost | §9.6：isolated 5%–10%，e2e 1%–2% | Nsight、所测 layer/pipeline | 中 |

## 批判性分析

### 论证链条

论文从 static placement 的 CPU overload 与 naive reload 的 I/O overload 推出三项设计，ablation 清楚显示 online balancing 是主收益、pipeline/controller 为增量，链条完整。相比 llama.cpp 的最大倍数混合了 sparsity本身；相对 PowerInfer/Neuralink/Q-Infer约 2.1×更能代表 novelty。

### 假设压力测试

activation predictor 的 accuracy/quality effect未在主结果中突出，错误 false-negative 可能改变 logits；若是 approximate sparse model，应同时报告 task quality/perplexity。dense activation 或大 batch 下 sparse index overhead上升，论文已观察 llama.cpp 有时超过 PowerInfer/Neuralink。PCIe/CPU phase 快速切换可能使 controller oscillate。

### 实验可信度

两档真实 PC、多个 model/quantization、standard/speculative、VRAM sensitivity、TPOT trace、utilization 与 ablation 覆盖扎实。缺少 output quality、energy、CPU memory bandwidth与端到端应用 latency；hardware 仅 NVIDIA+x86 discrete memory，不适用于 unified-memory mobile/Mac。

### 系统性缺陷

neuron transfer/cache/controller 扩大运行时状态，request cancellation、multi-process GPU sharing、OOM 与 predictor/model version mismatch未讨论。局部迁移还会改变 power/thermal，consumer PC 长时间 throttling可能推翻短 benchmark equilibrium。KAIROX 基于 llama.cpp fork，跟进 model architecture/kernel演进成本较高。

## 局限与后续工作

- **局限 1**：依赖 activation sparsity/predictor，未系统报告 quality loss。
- **局限 2**：只覆盖 discrete NVIDIA GPU consumer PC，不覆盖 unified memory/NPU。
- **局限 3**：controller 在多 tenant、thermal throttling 和 burst request 下未验证。
- **后续工作 1**：按 predictor threshold 扫 throughput–perplexity/task accuracy，建立 no-regression quality guard。
- **后续工作 2**：加入 temperature/power/memory-bandwidth feedback，运行小时级 workload 验证 controller 不振荡且不热降频。
- **后续工作 3**：在 concurrent request/speculative batch sweep 下动态选择 sparse或dense GEMM，客观测 break-even batch。

## 相关

- **相关概念**：[[Activation-Sparsity]]、[[Model-Offloading]]、[[Heterogeneous-Inference]]、[[Neuron-Cache]]
- **同类系统**：[[llama.cpp]]、[[PowerInfer]]、[[Neuralink]]、[[Q-Infer]]
- **同会议**：[[OSDI-2026]]
