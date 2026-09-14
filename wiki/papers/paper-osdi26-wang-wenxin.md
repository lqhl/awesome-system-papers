---
type: paper
name: Wang-MoEInference
full_title: Achieving Cloud-Grade SLOs for Local Mixture-of-Experts Inference through CPU–GPU Hybrid Design
authors: [Wenxin Wang, Yule Hou, Yu Ji, Peng Qu, Youhui Zhang]
venue: OSDI
year: 2026
tags: [moe-inference, cpu-gpu-hybrid, fp8, long-context, local-serving]
source_pdf: "[[osdi26-wang-wenxin.pdf]]"
source_md: "[[osdi26-wang-wenxin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向本地 MoE 推理的云级 SLO（OSDI 2026）

> **原题**：Achieving Cloud-Grade SLOs for Local Mixture-of-Experts Inference through CPU–GPU Hybrid Design

> **一句话总结**：论文观察到本地大规模 MoE 推理的瓶颈分别落在长上下文 prefill 的 CPU 计算、PCIe 专家通信和小批量 decode 的 DRAM 带宽上，于是用 SLP/DSLP、SmallEP、节点内 prefill–decode 解耦、双批次重叠以及 AVX-512 FP8 GEMV 重排执行路径，在双路 EPYC 9355、1–2 张 RTX 5090 上将原精度 FP8 DeepSeek-R1 的 TTFT 压到 32K–45K token 的 30 秒目标内，并达到约 20–22 tokens/s decode。

## 问题与动机

本地部署大规模 MoE 模型受 VRAM 容量限制，通常依赖 INT4、蒸馏或改路由模型。论文把云端服务的 30 秒 TTFT 和每请求至少 20 tokens/s decode 作为本地 QoS 参照，指出现有方案在模型完整性、长上下文 prefill、decode 响应速度和并发稳定性上同时存在缺口。

作者针对的是“完整模型权重放入主机 DRAM、计算由 CPU 与消费级 GPU 分担”的节点，而不是拥有大容量 VRAM、高速互联和高并发的 GPU 集群。设计目标是让 CPU 承担容量与带宽，GPU 承担 prefill 的高计算强度部分，并避免直接套用云端大规模并行方案。

## 关键观察 / 隐含假设

- **观察 1：长上下文 prefill 由 CPU 侧 MoE 计算主导。** 在 8K、16K、32K 输入上，CPU prefill 的 TTFT 快速增长；KTransformers 的 AMX prefill 在 8K 以后也难以维持 30 秒目标（§2.2.2、图 13–14）。
  - **依赖假设**：输入足够长，GPU 计算收益能够抵消权重经 PCIe 传输的成本。
  - **可能失效场景**：短于约 4K 的输入中，传输和初始化开销可能超过 GPU 加速收益；低带宽 PCIe 或更低端 GPU 也会削弱 SLP。
- **观察 2：两卡本地 EP 的主要代价是 PCIe dispatch/combine，而不是专家计算。** 在 20K token 单层 prefill 中，标准 CP2+EP2 的 dispatch/combine 约占层时间 31%；SmallEP 将通信量约减半，端到端层延迟再降 18%（图 3、§3.2）。
  - **依赖假设**：EP size 较小，尤其是 2，且每 token 激活专家数不少于 EP size。
  - **可能失效场景**：更大的 EP、NVLink 等高速互联或激活专家数变化后，All-Gather 的复制成本可能不再占优。
- **观察 3：小批量 decode 是 CPU DRAM 带宽受限的 skinny GEMV。** 作者估算 KTransformers 只利用了双路 DDR5 理论带宽的一半左右（§2.2.1、§6）。
  - **证据强度**：中。带宽估算和端到端结果一致，但缺少更多 CPU SKU、真实生产 trace 和功耗数据。
- **假设 1：完整 FP8 模型权重能够放入约 1.15 TB 主机内存。** 该假设是原精度本地服务的容量前提，不能推广到更大的模型或较小内存节点。
- **假设 2：低并发本地请求允许针对 batch size 1–6 定制执行。** 双批次重叠利用了 attention 与 CPU MoE 的交替空闲窗口，但并未证明在高并发云端工作负载下仍然适用。

## 核心方法

**Stream-loading prefill（SLP）** 将 prefill 拆成 loader、model、unloader 三个线程和 CUDA stream，在子层粒度用事件协调。loader 把专家权重从 DRAM 流式搬到 GPU，model 执行模块，unloader 及时回收 GPU 权重。跨层复用专家 ring buffer，避免 DeepSeek-V3 中约 44.5K 个张量频繁 `cudaMalloc/cudaFree`。这直接回应观察 1：用 GPU 计算替代 CPU 专家计算，同时将搬运与计算重叠，保持显存有界。

**Distributed SLP（DSLP）** 在两张消费级 GPU 上结合 zig-zag StripedAttention 的 context parallelism 和小规模 expert parallelism。**SmallEP** 先 All-Gather 未排序 token，各 rank 独立 gate/sort，只保留本地专家 token；专家计算后先做本地加权归约，再交换形状为 `[N,D]` 的部分结果。它以重复 gate/sort 换取较低的 PCIe 峰值通信，针对观察 2 的小 EP 场景。

并发部分包含两种机制。节点内 prefill–decode 解耦让一张 GPU 处理 SLP prefill，另一张 GPU 处理 decode，并用专家 ring buffer 共享 DRAM 中的权重副本，避免重复存储和拷贝。双批次 attention–MoE overlap 则让两个请求交错运行 GPU attention 与 CPU MoE，填补约 350µs attention 和 450µs MoE 之间的设备空闲。

为原精度 FP8 decode，论文实现 AVX-512 FP8 GEMV。它把 FP8 权重直接扩展为 BF16，在 `vdpbf16ps` 中完成点积，最后对 FP32 累加结果做缩放，避免 FP32 热路径的寄存器压力。进一步按 128 个元素的 scale block 累加后再缩放，减少重复乘法。CPU MoE 侧再使用按专家的细粒度 barrier、gate/up 与 down 的依赖划分，以及量化转换融合。

## 设计取舍

- **显存与带宽换取吞吐**：SLP 保留原精度权重，但每层专家权重必须反复经过 PCIe；短输入时传输成为主导开销。
- **通信减少与重复计算交换**：SmallEP 复制所有 token 并重复 gate/sort，论文测得该额外开销每层少于 10 ms、低于端到端层延迟的 5%，但该结论只覆盖 EP=2 的目标配置。
- **并发隔离与 GPU 资源占用交换**：prefill–decode 解耦至少需要两张 GPU；单 GPU 节点只能退化到 chunked prefill 或共享执行路径。
- **性能与工程复杂度交换**：显式 loader/unloader、ring buffer、跨线程事件和 NUMA 同步比 Unified Memory 更可控，但增加了模型适配和故障排查成本。论文未报告异常退出、权重一致性或长期运行碎片化问题。

## 实验与结果

- 双路 AMD EPYC 9355、1.15 TB DDR5-6400、1–2 张 RTX 5090 上，FP8 SLP 在 20K–32K 长度相对 AVX CPU prefill 超过一个数量级，相对估算的 KTransformers AMX 约 2.8×；两卡 DSLP 达到 SLP 的 1.64×（图 13）。
- SLP/DSLP 在 4K–32K token 输入内保持 TTFT 少于 30 秒；DSLP 支持约 45K token 在 30 秒内完成，SLP 支持约 32K（图 14）。4K 以下 CPU 路径更有竞争力。
- 原精度 FP8 DeepSeek-R1 671B 单流达到 21.5 tokens/s，32K context 仍约 20 tokens/s；Kimi-K2 单流为 22.4 tokens/s。两路并发总吞吐 33.6 tokens/s，32K 时为 31.1 tokens/s（图 15）。
- batch size 2/4/6 时，双批次方案相对 batch 1 的总吞吐分别为 1.56×/1.58×/1.61×；batch 2 的每请求速度为 16.8 tokens/s，而 KTransformers 从 22.7 降至 13.6 tokens/s（图 16）。
- Q4_K_M DeepSeek-R1 上，短上下文 decode 为 28 tokens/s，128K 时仍为 19 tokens/s；KTransformers 从约 22 降至约 15 tokens/s（图 17）。
- FP8 GEMV 优化 kernel 延迟 15.5 µs、带宽 947 GB/s，相比标准 kernel 的 21.7 µs/678 GB/s；与 OpenBLAS、AOCL-BLAS 的比较覆盖 FP32/BF16，但基线并不原生支持 FP8（表 1）。
- 并发 1P+2D 时，SLP TTFT 增加 18%；整体最坏完成时间相对单请求基线增加 1.67×，KTransformers 为 2.53×（图 18）。MMLU-Redux 和 MMLU-Pro 的端到端分数与官方结果差异约 1–1.2 个百分点（表 2）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| GPU 流式加载能解决长上下文 prefill 的 CPU 计算瓶颈 | 图 13–14：SLP/DSLP 在 20K–32K 超过 CPU AVX，并保持 TTFT <30 s | 双路 EPYC 9355、RTX 5090、DeepSeek FP8；KTransformers 长输入部分为估算 | 中 |
| SmallEP 适合 PCIe 上的两卡小 EP | 图 3、§3.2：通信约减半，层延迟较标准 EP 再降 18% | 20K token 单层 microbenchmark，主要是 EP=2 | 中 |
| 原精度 FP8 本地 decode 可达到云级响应速度 | 图 15：DeepSeek-R1 21.5 tokens/s，Kimi-K2 22.4 tokens/s | 特定双路 CPU、短至 32K context、低并发 | 中 |
| 并发请求下用户级速度退化较小 | 图 16、18：batch 2 每请求 16.8 tokens/s，1P+2D 最坏总延迟增 1.67× | 仅少量并发，固定约 20 秒请求，未覆盖高并发生产 trace | 中 |
| FP8 kernel 没有明显损害模型质量 | 表 2：两项 benchmark 与官方分数差 1–1.2 个百分点 | 官方结果与本地生成配置可能不完全一致，未给出完整精度敏感性分析 | 弱至中 |

## 批判性分析

### 论证链条

论文把四类 QoS 缺口映射到四组机制，整体链条是闭合的：长 prefill 使用 GPU 和重叠传输，双卡通信使用 SmallEP，decode 带宽瓶颈使用 FP8 GEMV 与细粒度并行，并发争用使用解耦和双批次重叠。主要跳步在“云级 SLO”的定义：30 秒 TTFT 和 20 tokens/s 是响应速度参照，不等同于云服务的成本、可用性、错误恢复和多租户隔离。

### 假设压力测试

SLP 的性能依赖 DRAM→GPU 的持续 PCIe 流量、足够的 ring buffer 显存和稳定的 GPU 计算吞吐。低端 PCIe、较小 VRAM 或同时存在更多 decode 请求时，DRAM 争用会削弱重叠；论文自己观察到 1P+2D 的 TTFT 已增加 18%。SmallEP 的通信公式和优势集中在 EP=2；拓展到更多 GPU 时 All-Gather 复制和 gate/sort 成本需要重新测量。

### 实验可信度

实验覆盖完整 FP8 与 Q4_K_M、长上下文、单流和少量并发，并包含 kernel 隔离实验与质量检查。限制是 KTransformers 的长上下文数字部分是估算或引用其他平台，未必是严格同机对照；并发请求是人为固定时长，缺少公开生产到达过程、P99、功耗、每 token 成本和故障恢复测量。质量对照使用官方分数，生成配置差异也可能解释 1–1.2 个百分点的偏差。

### 系统性缺陷

完整 FP8 DeepSeek-R1 需要约 TB 级 DRAM，硬件门槛高。两卡解耦会牺牲可用 GPU 资源，且权重共享与跨进程 ring buffer 增加运行时状态。论文未讨论多租户隔离、OOM 后恢复、GPU/CPU 故障、权重版本一致性、在线取消请求和长期运维。调度策略中的 5 分钟窗口、batch target 6 等参数也没有针对不同流量分布做敏感性分析。

## 局限与后续工作

- **局限 1**：主要结论绑定双路 EPYC 9355、RTX 5090 和约 1.15 TB DRAM；论文只定性讨论更低端硬件，没有系统的硬件缩放曲线。
- **局限 2**：SmallEP 的优势尚未在 EP>2、GPU–GPU P2P、不同激活专家数或非均匀路由下验证。
- **局限 3**：并发评测最多覆盖 1P+2D 和 batch 6，不能推出高并发吞吐、P99 SLO 或多租户隔离结论。
- **后续工作 1**：在单路 CPU、不同 DRAM 带宽、PCIe 代际和 16/24 GB GPU 上测量 SLP 的 TTFT、带宽利用率与 ring-buffer 拐点。
- **后续工作 2**：构造真实请求到达 trace，报告 P50/P95/P99 TTFT/TPOT、功耗、成本和故障恢复时间，并比较 chunked prefill、节点内解耦和更大 batch 的调度边界。

## 相关

- **相关概念**：[[Mixture-of-Experts]]、[[FP8]]、[[Context-Parallelism]]、[[Expert-Parallelism]]、[[NUMA]]、[[Chunked-Prefill]]
- **同类系统**：[[KTransformers]]、[[llama.cpp]]、[[vLLM]]、[[SGLang]]
- **同会议**：[[OSDI-2026]]
