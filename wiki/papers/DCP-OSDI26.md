---
type: paper
name: DCP
full_title: "Revisiting Pipeline Parallelism for LLM Serving"
authors: [Soonjae Hwang, Jeongseob Ahn]
venue: OSDI
year: 2026
tags: [llm-serving, pipeline-parallelism, chunked-prefill, scheduling, latency-slo]
source_pdf: "[[osdi26-hwang.pdf]]"
source_md: "[[osdi26-hwang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 重新审视大模型服务中的流水线并行（OSDI 2026）

> **原题**：Revisiting Pipeline Parallelism for LLM Serving

> **一句话总结**：论文发现，PCIe GPU 上的流水线并行虽然避免了张量并行频繁的 All-Reduce，却会因 prompt 长短、prefill/decode 混合和 decode batch 大小变化产生 stage bubble；动态 chunked prefill（DCP）按 SLO 实时选择 chunk，delay scheduling（DS）再重排 decode 请求，在 4×A100 PCIe 上让流水线并行取得高于张量并行的 goodput，并显著降低尾延迟。

> **命名说明**：论文没有给整套实现起一个系统名，只命名了 DCP、adaptive latency prediction（ALP）和 DS 三项技术；本页采用论文的主要机制名 DCP，DS 是与它配合的解码调度机制。

## 问题与动机

单机多 GPU 的 [[LLM]] 服务通常采用张量并行（tensor parallelism，TP）。它能把一层计算分到多张卡上，但几乎每层都要做 collective；在 NVLink 上这可能值得，在 PCIe 或其他低带宽互连上，频繁 All-Reduce 会成为瓶颈。流水线并行（pipeline parallelism，PP）只在 stage 之间传 activation，通信少得多，却把每个时刻不同 microbatch 的计算量是否相等变成关键问题。

在线请求不是固定形状。新请求的 prompt 长短不同，prefill 可能和已有请求的 decode 混在一起，每个 decode microbatch 的活跃请求数还会随完成时间变化。论文区分三种失衡：两个 prompt 长度不同造成 P–P，prefill 与 decode 混合造成 P–D，decode 请求数不同造成 D–D。任何一种都会让快 stage 等慢 stage，形成 bubble。

静态 chunked prefill 不能同时解决这些情况。chunk 小时，一次 prefill 占用短，P–P/P–D bubble 较少，但矩阵规模太小，GPU 吞吐下降、TTFT 可能恶化；chunk 大时 GPU 更饱和，却会让 decode 等待。论文的例子中，2,048-token prefill 和 128-token prefill 连续进入流水线会造成 627 ms bubble。最佳 chunk 因负载、序列分布、模型和 SLO 而变，不能在部署前选一次就结束。

## 关键观察 / 隐含假设

- **观察 1：prefill 延迟大体随本轮 token 数增长。** 因此缩小 chunk 能缩短占住一个 stage 的时间并减少 P–P/P–D 失衡，但也会降低大矩阵计算效率。
  - **隐含假设**：模型的线性层仍占主要计算，kernel 和硬件对 token 数的关系可通过少量离线 profile 稳定刻画。
- **观察 2：TTFT 和 TPOT 给 chunk 大小施加相反约束。** 等待队列使 TTFT 接近上限时，要用更大 chunk 提高 prefill 吞吐；TPOT 接近上限时，要用更小 chunk 减少 decode 等待。最合适的是同时满足两者的最小 chunk。
  - **隐含假设**：近期到达率和 token 分布能代表短期未来，SLO slack 也能及时反映负载变化。
- **观察 3：decode 延迟对请求数不是平滑线性的，而有硬件高效边界。** A100 上 batch 96 到 128 只差约 5%，128 到 160 却差约 31%；处理 129 个 token 几乎和 256 个一样贵。把 stage 的 batch 对齐到 128、256、384 等边界，可能以很少的有效工作损失换来较大 bubble 减少（图 3）。
  - **隐含假设**：高效边界在模型、kernel 和硬件版本不变时稳定，且临时 preempt 请求的代价小于减少的等待。
- **观察 4：prefill-heavy 与 decode-heavy 需要不同控制器。** DCP 只能改变 prefill chunk；没有 prefill 的 iteration 仍会有 D–D 失衡，必须另外重排 decode 请求。

## 核心方法

### 1. 贪心式动态分块预填充（Greedy DCP）

Greedy DCP 在离散集合中选择 chunk，例如 128、256，直到 2,048。chunk 改变要经过整个流水线深度才能完全生效，所以控制器每隔一个 pipeline depth 的 scheduling iterations 才调整一次。它读取前几轮的 TTFT slack、TPOT slack 和空闲 [[KV-Cache|KV-cache]] 比例：

1. KV 空间低于水位时，选比当前运行请求数大的最小候选，让在途请求更快结束并释放 KV；
2. TPOT 已违约，或 TTFT 余量很大、说明负载较轻时，减小 chunk 来压 bubble；
3. TTFT 余量很小而 TPOT 仍宽松时，增大 chunk，提高吞吐并排空等待队列。

方法简单，但它只看已经发生的延迟，反馈又被 pipeline depth 推迟。负载快速变化时，控制器会一直追赶移动的目标，其他 stage 留下的旧大 chunk 还会污染当前测量。

### 2. Predictive DCP 与 ALP

Predictive DCP 为每个候选 chunk 预测本轮延迟和吞吐。adaptive latency prediction（ALP）把延迟拆成两部分：线性层用离线 profile 的 `α₀ × batched_tokens + α₁`；[[Attention|attention]] 用 past-context×prefill、prefill²、decode-context 和残差四组特征。每轮测得真实延迟后，递归最小二乘（RLS）带 forgetting factor 在线更新 attention 参数，因此不需要预先训练一个神经网络。

调度器先用预测 TPOT 排除太慢的候选，形成 chunk 的上界；再根据滑动窗口中的请求到达率、token 分布，以及已经等太久请求的剩余 TTFT 预算，算出最低 prefill 吞吐，形成下界。若有可行区间，就选其中最小 chunk 来减少 bubble；若系统过载，就选仍满足 TPOT 的最大 chunk，优先排空队列。可用 KV、上一轮延迟、等待队列和运行 batch 会在每轮重新输入（图 6）。

### 3. Delay scheduling 处理 D–D 失衡

decode-only 阶段中，每个请求每轮只产生一个 token，线性层成本主要由活跃请求数决定。DS 检查每个 microbatch 是否落在硬件高效边界附近：若只比边界多一点，就暂时 preempt 多出的请求，把 batch 压回边界；若差得很多，就靠恢复旧请求或暂停新请求，把各 microbatch 调到接近平均值。

选择谁被暂停也看 TPOT slack。余量不足时，论文优先暂停较老请求，让较新的请求保持较好 TPOT；余量充足时，优先暂停较新请求，让旧请求尽早完成、释放 KV，并降低等待请求的 TTFT。这个策略改善总体完成时间，却会把额外延迟集中到一部分请求上，论文的 synthetic decode-heavy 实验也确实观察到 P99 TPOT 变差。

### 4. 实现范围

三项技术实现于 SGLang 0.4.1，不改变模型权重或请求语义。它调的是 chunk 和 microbatch 内的请求，不重新切分 pipeline stage，也不联合选择 TP/PP 比例。论文评估的是单机同构 GPU、dense Qwen2.5 模型；[[MoE|MoE]]、异构 stage、跨节点网络和动态模型切换没有进入实现验证。

## 设计取舍

- **较小 chunk 换较少 bubble**：轻载时有利于 TPOT，重载时会损失 GPU 利用率和 TTFT；DCP 的工作就是在两个约束之间移动。
- **预测模型换更快响应**：ALP 比 greedy 更能处理 pipeline 延迟反馈，但依赖离线 linear-layer profile，并假定在线 attention 模型能跟上工作负载变化。
- **总体效率换单请求公平**：DS 可以让更多请求整体更早完成，却可能反复暂停某些请求。只看 P90 goodput 不足以保证每个用户的 tail latency。
- **PP 优势依赖互连**：论文针对 [[PCIe|PCIe]] 4.0。NVLink/NVSwitch 上 TP 通信成本更低，结论可能反转；跨节点 PP 又会增加 activation 网络开销。
- **固定 stage partition**：调度器缓解动态失衡，但不能修复模型层切分本身不均、某个 stage 持有更多 KV 或特殊 operator 的静态失衡。

## 实验与结果

- **设置与口径**：平台是 4×NVIDIA A100 40 GB PCIe 4.0、AMD EPYC 9754、768 GB 内存，软件为 [[PyTorch|PyTorch]] 2.5.1、CUDA 12.4、FlashInfer 和 SGLang 0.4.1。模型是 BF16 Qwen2.5-32B/14B。主要工作负载为 Azure Conversation、ShareGPT、CNN，以及把 CNN 输入/输出分布倒转得到的 decode-heavy trace；主实验到达过程为 Poisson。goodput 是同时满足 P90 TTFT 2,000 ms 和 P90 TPOT 200 ms 的最高请求率（§5.1）。
- **32B 主结果**：图 9 为每个工作负载离线选择最佳固定 chunk 的 `PP_static`，Azure/CNN/ShareGPT 为 512，CNN-Reversed 为 256。相对这个较强基线，DCP goodput 相近、TTFT 略高，但 TPOT/E2E 更低：Azure 上 greedy 降 19%/18%，predictive 降 35%/31%；CNN 上分别降 27%/28% 和 42%/36%；ShareGPT 上 predictive 降 36%/24%。DS 在前三个 prefill-heavy 负载很少触发，在 CNN-Reversed 才明显改善 TTFT 和 goodput。
- **14B、iteration 与预测器**：Azure 的最佳固定 chunk 改为 1,024，说明最佳值会随模型变化。greedy 和 predictive 相对 `PP_static` 最多降低 TPOT 40% 和 50%；这两个数字都指 TPOT，不是“TPOT 与 E2E 各降 40%/50%”。Azure 32B 的 P90 iteration latency 从 51.68 ms 降到 29.56/21.53 ms，predictive 的 P99 从 65.34 降到 30.94 ms（2.11 倍）。ALP 的 MAPE 为 3.26%，只比两层 DNN 高 0.70 个百分点，但预测只需 0.002875 ms、模型 0.643 KB，也无需离线训练（图 10–11、表 1）。
- **SLO 范围**：图 12 的 TP 和 PP 基线都用默认 chunk 2,048，不是前面逐工作负载调优的 `PP_static`。SLO 从 1.0 缩到 0.4 时，Azure 32B 的 DCP/PP goodput 优势从 2.7 倍增到 5.4 倍，14B 从 1.7 倍增到 2.4 倍；CNN-Reversed 上 DS 最高提高 1.4 倍。SLO 低于 0.6 后 DS 来不及积累足够请求，收益下降；32B、scale=0.2 时最小 chunk 也违反 TPOT，所有 PP 方案 goodput 都为 0。
- **合成负载**：prefill-heavy 使用输入 512–1,024、输出 32–64 token，5 req/s；decode-heavy 交换两者，14 req/s。前者中 DCP 在 TTFT、TPOT、E2E 上都低于 TP 和 PP，predictive 相对 greedy 的 P99 TPOT/E2E 再降 25%/13%。后者中，PP 相对 TP 的平均 TTFT/TPOT/E2E 分别改善 2.82/1.30/1.38 倍；DS 相对 predictive 让 E2E 平均少 4,062 ms、P99 少 8,088 ms，但 P99 TPOT 反而差 15%（图 13）。
- **真实到达轨迹**：作者重放 Azure Conversation 前 15 分钟，并把到达率缩为原来的 0.9，使 `PP_static` 约有 90% SLO attainment。TP、默认 `PP_2048`、`PP_static` 分别达到 1.9%、1.6%、92.5%，DCP 为 93.5%/94.5%；在标准 200 ms TPOT 下总通过率差距不大，但把 TPOT 收紧到 150 ms 后，greedy/predictive 是 `PP_static` 的 3.06/4.14 倍，60 秒内完成的请求数为 1.3/1.6 倍（图 14）。这是缩放后的一段 trace，不是在线生产部署。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| 在线 PP 的主要损失来自随请求阶段和大小变化的 pipeline imbalance | 图 2–4 的 P–P、P–D、D–D characterization；图 11 的 iteration tail | 4×A100、Qwen2.5、SGLang | 强 |
| DCP 能在不明显损失 goodput 的同时降低 prefill-heavy 延迟 | 图 9–10：多 trace 上 TPOT/E2E 下降，goodput 接近调优后的固定 PP | 两个 dense 模型、Poisson 到达 | 强 |
| 轻量 ALP 足以指导 chunk 选择 | 表 1：3.26% MAPE，0.002875 ms，端到端与更复杂模型近似 | 单个 AzureConv 验证负载，kernel/模型固定 | 中 |
| DS 能缓解 decode-only 的 D–D 失衡 | 图 10、12–13：goodput、TTFT 和 E2E 改善 | 同时出现 P99 TPOT 恶化 15%，公平性未系统评估 | 中 |
| 动态 PP 可在低带宽互连上超过 TP | 图 9–14 中 DCP/DS goodput 高于 TP | 单机 PCIe 4.0；不能外推到 NVLink 或跨节点 | 中 |

## 批判性分析

### 论证链条

论文先把“PP 不适合在线服务”拆成三种可测的 imbalance，再分别给 prefill 和 decode 设计控制器，最后用 iteration CDF、SLO sweep 和合成负载验证每个机制，论证路径清楚。它真正支持的结论是：在低带宽单机互连和给定 SLO 下，动态调度可以让 PP 优于 TP；它没有证明 PP 普遍替代 TP。旧的固定 PP 如果按 workload 离线调优，goodput 已经很接近 DCP，DCP 更稳定的优势主要是不同负载下的 TPOT/E2E 和免去固定 chunk 对变化负载的不适应。

### 假设压力测试

Greedy 假定过去 slack 还能指导未来，predictive 则假定滑动窗口中的到达率和 token 分布短期稳定。突发流量、多租户干扰、[[Speculative-Decoding|speculative decoding]] 或 kernel 切换都可能让预测失真。DS 的年龄策略不是无饥饿证明：TPOT 紧张时反复暂停旧请求，可能长期牺牲同一批用户；余量充足时暂停新请求，又可能拉高首次输出等待。MoE 的 expert 路由不均也不能只用 token 数或请求数建模。

### 实验可信度

作者同时使用真实长度分布、合成机制实验、两种模型、调优的固定 PP、SLO 扫描、真实到达 trace 和预测器消融，数字也给到 P99 iteration/latency，证据较完整。不过，baseline 只包括作者在 SGLang 上实现的 TP 与默认/离线调优静态 PP，没有和其他动态 chunk 控制器或 phase-disaggregated serving 做端到端比较。主 rate sweep 仍是 Poisson；真实 trace 被截取 15 分钟并缩放；图 12 的 PP baseline 固定用 2,048，而非每点重新调优。goodput 只要求 P90 TTFT/TPOT，通过率和平均效率可能掩盖 P99 受害者，图 13 已展示 DS 的 P99 TPOT 会差 15%。

### 系统性缺陷

ALP 的线性层 profile 会随 GPU、[[Quantization|quantization]]、kernel、模型和 batch 实现变化，需要重新采样。调度器与 SGLang 的 batch/KV 管理紧密耦合，且 preemption 会增加状态管理和公平性策略。系统只动态调 chunk 和请求，没有联合优化 stage partition、KV placement、TP/PP 混合度或跨节点通信。4 卡结果也没有展示 pipeline depth 增大后，控制反馈延迟是否使 greedy 和 predictive 更难稳定。

## 局限与后续工作

- **局限 1**：只测单机 4×A100 PCIe 4.0 与两个 dense Qwen2.5 模型，缺少 NVLink、NPU、8/16 卡、跨节点和 MoE。
- **局限 2**：SLO 重点是 P90；DS 已出现 P99 TPOT 回退，但没有逐请求 slowdown、饥饿率或租户公平性。
- **局限 3**：不联合调整 pipeline 切分、并行策略和 KV 放置，也没有生产线上长期运行结果。
- **后续工作 1**：在 PCIe、NVLink、[[RDMA|RoCE]] 和多种 pipeline depth 上画出 TP、PP 与 hybrid parallelism 的 crossover 边界。
- **后续工作 2**：加入 burst、优先级和多租户 trace，限制每个请求最大连续 preemption，并报告 P99.9 与饥饿率。
- **后续工作 3**：让预测器同时考虑 MoE expert load、异构 stage 和 KV pressure，联合选择 stage partition 与 chunk。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Chunked-Prefill]]、[[Goodput]]、[[Latency-SLO]]
- **相关系统**：[[SGLang]]、[[Qwen2.5]]
- **同会议**：[[OSDI-2026]]
