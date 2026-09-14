---
type: paper
name: Hwang-PipelineParallelism
full_title: Revisiting Pipeline Parallelism for LLM Serving
authors: [Soonjae Hwang, Jeongseob Ahn]
venue: OSDI
year: 2026
tags: [llm-serving, pipeline-parallelism, dynamic-scheduling, chunked-prefill, goodput]
source_pdf: "[[osdi26-hwang.pdf]]"
source_md: "[[osdi26-hwang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 重新审视 LLM 服务中的流水线并行（OSDI 2026）

> **原题**：Revisiting Pipeline Parallelism for LLM Serving

> **一句话总结**：在线请求的输入长度、prefill/decode 混合和 decode batch 大小会让流水线阶段失衡；论文在 SGLang 中用动态 chunked-prefill、延迟调度和在线延迟预测减少 bubbles，在 4 张 PCIe A100 上对 Qwen2.5-32B 的 AzureConv 工作负载将 TPOT 和端到端延迟最多降低 35% 和 31%。

## 问题与动机

单机多 GPU 的 LLM 服务通常采用 tensor parallelism（TP），因为每张 GPU 在每轮执行相同计算，负载容易平衡。但 TP 需要频繁的 collective communication；在 PCIe 连接的 GPU 上，这部分开销可能抵消并行计算收益。Pipeline parallelism（PP）只在相邻阶段间传递激活，通信量较小，却会因流水线阶段工作量不同而产生空闲周期。

论文关注在线服务中的 PP。请求到达时间、输入长度和所处阶段不断变化，使固定 microbatch 调度难以保持平衡。作者将问题分成 prefill-prefill（P-P）、prefill-decode（P-D）和 decode-decode（D-D）三类失衡，并分别设计 chunk size 控制与 microbatch 重平衡机制。

## 关键观察 / 隐含假设

- **观察 1：** prefill 的计算时间主要随输入序列长度增长。两个长度分别为 2048 和 128 的 prefill 顺序执行时，会形成约 627 ms 的 pipeline bubble（图 3、§3.1.2）。
  - **依赖假设：** 请求输入长度差异是在线工作负载中的主要 prefill 失衡来源。
  - **可能失效场景：** 输入长度高度集中，或 attention、通信成为主导瓶颈时，缩小 chunk size 的收益会减少。
- **观察 2：** decode 延迟主要受 batch 中请求数影响，且线性层在某些 batch 边界存在阶梯式效率变化。A100 上 batch size 从 128 增至 129 时，线性操作的效率差距可达约 31%（图 3）。
  - **依赖假设：** 将 decode microbatch 对齐到 128、256 等硬件高效边界能减少 D-D 失衡。
  - **可能失效场景：** GPU、模型形状或 kernel 实现变化后，高效 batch 边界可能不同。
- **假设 1：** TTFT slack 和 TPOT slack 足以作为在线 chunk size 控制信号。该假设有中等证据支持：动态方法在多个 trace 上降低延迟，但快速变化负载下反馈延迟仍可能导致控制滞后。
- **假设 2：** 线性层延迟可由离线 profiling 预测，而 attention 延迟可用近期观测在线校准。论文在 AzureConv 上报告了较低的预测误差，但没有在更多模型、硬件和突发模式下验证预测漂移。

## 核心方法

论文在 SGLang 上实现三项机制。第一项是动态 chunked-prefill：把长 prompt 切成可调大小的块，以减少 P-P 和 P-D bubbles。chunk 越小，阶段间工作量越接近，但每轮处理 token 数下降，TTFT 可能因吞吐不足而上升。

greedy 方法每隔若干个 pipeline depth 的调度迭代，根据 TTFT/TPOT slack 增减 chunk size。TPOT 快要违反 SLO 或负载较低时减小 chunk；TTFT slack 不足且 TPOT 仍有余量时增大 chunk。它还检查 KV cache 水位，避免大 chunk 造成显存分配失败。

predictive 方法为每个候选 chunk 预测迭代延迟和吞吐。线性层部分用离线 profiling 建模，attention 部分根据当前 prefill、历史上下文和 decode 请求特征在线更新，并使用 Recursive Least Squares（RLS）适应负载变化。调度器先用 TPOT SLO 排除过大的 chunk，再用满足 TTFT SLO 所需的吞吐量确定下界，最终选择最小可行 chunk。

第二项是 delay scheduling。decode-only 迭代中，系统暂时延迟部分请求，把 microbatch 大小对齐到硬件高效边界，或向所有 microbatch 的平均请求数靠拢。TPOT slack 紧张时优先延迟较老请求；显存或 TTFT 压力较大时则延迟较新请求，以尽快完成老请求并释放 KV cache。

## 设计取舍

- **小 chunk 与 GPU 利用率：** 小 chunk 减少 bubbles，却降低单轮计算效率；大 chunk 提高吞吐，却可能拖慢 decode。动态控制把 TTFT 和 TPOT SLO 作为约束，但控制参数和预测误差会影响稳定性。
- **延迟请求与整体 goodput：** delay scheduling 牺牲部分请求的 TPOT，换取阶段平衡、较低 TTFT 和更早释放 KV cache。论文中的 Azure trace 实验显示，P99 TPOT 可能因此恶化 15%。
- **PP 的通信优势与调度复杂度：** PP 适合 PCIe 等带宽受限环境，但需要维护 microbatch、chunk、请求延迟和跨阶段状态；相比之下，TP 的负载平衡更直接。

## 实验与结果

- 实验使用 4 张 NVIDIA A100 40GB、PCIe 4.0、Qwen2.5-32B/14B、SGLang 0.4.1，以及 Azure Conversation、ShareGPT、CNN 和反转后的 CNN-Reversed trace（§5.1）。
- 在 Qwen2.5-32B 的 AzureConv 上，相比离线调优的 PP，greedy 动态 chunk 将 TPOT/E2E 延迟最多降低 19%/18%，predictive 方法降低 35%/31%（图 9、§5.2.1）。
- 在 CNN 工作负载上，predictive 方法相对静态 PP 将 TPOT/E2E 延迟降低 42%/36%；ShareGPT 上分别降低 36%/24%（§5.2.1）。
- AzureConv 的每轮迭代 P90 延迟从静态 PP 的 51.68 ms 降至 predictive 方法的 21.53 ms；P99 从 65.34 ms 降至 30.94 ms，即约 2.11× 改善（图 11）。
- decode-heavy 的 CNN-Reversed 上，delay scheduling 将迭代 P90 从 28.94 ms 降至 24.53 ms，并带来最高约 1.4× 的 goodput 提升；但在极紧 TPOT SLO 下，其激活阈值难以满足，收益快速下降（图 12、§5.2.3）。
- 真实 Azure trace 中，静态 PP 的 SLO attainment 为 92.5%；当 TPOT SLO 收紧到 150 ms，greedy 和 predictive 方法的 attainment 分别是静态 PP 的 3.06× 和 4.14×（图 14、§5.2.5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 动态 chunk size 能减少 prefill 导致的 PP bubbles | AzureConv 上 predictive 方法将 TPOT/E2E 延迟最多降低 35%/31%（图 9、§5.2.1） | 4×A100、Qwen2.5、三类主要 trace | 强 |
| predictive 控制比 reactive greedy 更能降低尾延迟 | AzureConv 迭代 P99 从 65.34 ms 降至 30.94 ms（图 11） | 固定模型和单机 PCIe 拓扑 | 中 |
| delay scheduling 能处理 decode-heavy 的 D-D 失衡 | CNN-Reversed goodput 最高提升约 1.4×，迭代 P90 降至 24.53 ms（图 12、§5.2.3） | 反转 CNN trace；极紧 SLO 下收益下降 | 中 |
| PP 加本文机制可超过 TP | 作者在 Qwen2.5-32B/14B 和多个 trace 上报告更高 goodput（图 9、图 10） | 4 张 PCIe A100；不代表 NVLink 或更大规模集群 | 中 |

## 批判性分析

### 论证链条

论文从三类工作量失衡出发，将 prefill 失衡交给动态 chunk，将 decode 失衡交给请求延迟。图 11 的迭代延迟分布支持 predictive 方法确实减少了 bubbles。论证仍有一个边界：PP 相对 TP 的优势依赖 PCIe 通信开销，不能直接外推到 NVLink 机器；论文也没有系统量化控制器自身的调度开销。

### 假设压力测试

预测器使用固定模型结构、离线线性层 profiling 和近期 attention 反馈。模型切换、kernel 版本变化、GPU 代际变化或请求分布突变都可能使模型失准。delay scheduling 用请求数近似 decode 计算量，长上下文请求、不同 KV cache 状态或异构请求可能破坏这一近似。

### 实验可信度

实验覆盖两个模型、多个真实 trace、合成 prefill-heavy/decode-heavy 负载，并报告 goodput、TTFT、TPOT、E2E 和迭代延迟。静态 PP 的 chunk size 通过每个 workload 的离线搜索得到，属于较强基线。限制是硬件仅为 4 张 A100，且真实 trace 实验主要围绕 AzureConv；没有多租户、故障恢复、规模扩展和不同 GPU kernel 边界的评估。

### 系统性缺陷

动态调度增加了请求挂起与恢复、KV cache 水位控制和预测器状态管理。论文未讨论故障恢复、调度器重启、请求取消、优先级队列和可观测性。delay scheduling 还可能造成个别请求长期被延迟，论文没有给出公平性或 starvation 分析。

## 局限与后续工作

- **局限 1：** 主要结论建立在单机 4×A100 PCIe 环境上，无法说明 NVLink、高速网络或更多 pipeline stages 下的收益。
- **局限 2：** 预测模型和 decode batch 边界依赖具体模型、GPU 和 kernel；跨硬件迁移需要重新 profiling 或校准。
- **局限 3：** delay scheduling 用暂时延迟换取整体性能，可能提高部分请求的 TPOT；公平性、starvation 和请求级 SLO 仍需单独约束。
- **后续工作 1：** 在多 GPU 代际、不同 interconnect 和 8 个以上 pipeline stages 上测量预测误差、控制开销与 goodput 的关系。
- **后续工作 2：** 引入逐请求年龄、公平性和 P99 SLO 约束，验证 delay scheduling 是否能避免长期延迟个别请求。

## 相关

- **相关概念：** [[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[KV-Cache]]、[[Chunked-Prefill]]
- **同类系统：** [[SGLang]]、[[vLLM]]、[[Sarathi-Serve]]
- **同会议：** [[OSDI-2026]]
