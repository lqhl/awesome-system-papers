---
type: paper
name: LLMStation
full_title: Resource Multiplexing in Tuning and Serving Large Language Models
authors: [Yongjun He, Haofeng Yang, Yao Lu, Ana Klimovic, Gustavo Alonso]
venue: ATC
year: 2025
tags: [llm-serving, peft, lora, gpu-multiplexing, scheduling, slo]
source_pdf: "[[atc2025-he-yongjun.pdf]]"
source_md: "[[atc2025-he-yongjun]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# LLMStation：调优和服务大型语言模型中的资源复用（ATC 2025）

> **原题**：Resource Multiplexing in Tuning and Serving Large Language Models

> **一句话总结**：LLMStation 把 [[LoRA]] PEFT 与 LLM serving 放到同一组 GPU 上，利用 decoding memory-bound、PEFT compute-bound 且 serving 负载波动的观察，通过迭代级 SLO-aware 调度、可挂起 Autograd 和 forward/decode fusion，在满足 P99 TTFT/TPOT SLO 的前提下比 FineInfer、vLLM+torchtune、chunked-training 提高 1.38-14.77x PEFT 吞吐。

## 问题与动机

论文要解决的是一个越来越常见但很尴尬的部署状态：同一批 GPU 既要负责在线 LLM inference，又要持续或频繁地做 PEFT fine-tuning。在线 serving 往往按峰值负载预留资源，但 BurstGPT、Chatbot Arena 这类真实 trace 里请求率有明显短时波动；另一方面，组织或个人会持续上传和维护大量 adapter，论文引用 Hugging Face 2024 年热门 open-source model series 上超过十万级 adapter 上传作为背景信号。

直接把 GPU 分给单一任务会浪费 decoding 阶段的空闲 compute。论文指出 autoregressive decoding 每步只处理最新 token，但要搬运整模型和 [[KV-Cache]]，典型 MFU 低于 5%；而 [[LoRA]] PEFT 的 forward/backward 更偏 compute-intensive。直觉上，二者应该能互补：serving 的 memory-bound decoding 和 PEFT 的 compute-bound training 可以共享同一 base model 和同一张 GPU 的不同资源瓶颈。

现有 multiplexing 方案卡在 SLO 和粒度上。时间复用要在 inference 和 tuning engine 之间切换，模型加载和 engine 初始化可达秒级到分钟级；FineInfer 这类 temporal multiplexing 虽然保护 decoding TPOT，但长序列或大模型 PEFT step 会阻塞新的 prefill，导致 TTFT 违反 SLO。空间复用如 Nvidia MPS 能限制 SM 百分比，但比例在启动后固定，低负载时浪费 PEFT 吞吐，高负载时又容易干扰 serving；论文在 RTX 3090 上展示 Llama-3.1-8B tuning/serving 共置时 P99 TTFT 和 TPOT 分别可恶化到 13.2x 和 3.6x。chunked-training 能把 PEFT 切细，但短 chunk 难以打满 GPU，还会引入额外 2N 次模型权重从 HBM 到 SRAM 的搬运。

LLMStation 的目标不是做一个全通用 GPU virtualization layer，而是在 PEFT + inference 这个窄但真实的场景里，把调度粒度推进到 inference iteration / PEFT layer tasklet 级别：每轮 decoding 前根据 SLO 预算决定能塞多少 PEFT work，并在 serving 压力变化时立即调整。

## 关键观察 / 隐含假设

- **观察 1：LLM serving 的短时波动留下了可利用的 GPU 空隙。** 论文用 BurstGPT 和 Chatbot Arena trace 说明请求负载存在 minute-level fluctuation，多模型负载还会不均衡；这意味着按峰值 provision 的 GPU 在低谷时有空闲。
  - **依赖假设**：部署方有足够稳定的 PEFT 队列，可以把这些碎片化空隙转化成有价值的 fine-tuning throughput，而不是偶发的一两个后台任务。
  - **可能失效场景**：如果 serving 负载长期接近饱和，或 PEFT 作业有严格 completion deadline 而不是可 opportunistic 执行，吞吐收益会显著收缩。
- **观察 2：decoding 与 PEFT 的主导瓶颈互补。** decoding 常被 HBM 带宽和 [[KV-Cache]] 访问限制，PEFT forward/backward 更能消耗 compute；论文据此把 PEFT tasklet 插入 decoding iteration，希望在不增加 TPOT 太多的情况下填满 SM。
  - **依赖假设**：模型结构、adapter 形态和 batch/sequence 分布能让 memory-bound 与 compute-bound 的组合成立；[[LoRA]] rank 和 adapter access distribution 不会让 serving 本身先违反 SLO。
  - **可能失效场景**：超长 context、极大 batch、uniform adapter access 或更 compute-heavy 的 decode kernel 可能让 decoding 自身已经占满关键资源，co-execution 只会扩大尾延迟。
- **观察 3：PEFT 必须被切到比 step 更细的粒度。** FineInfer 的 temporal scheduling 只能等当前 PEFT step 结束后再处理 prefill；随着 input sequence length 和 model size 增长，单 sample fine-tuning latency 会超过常用 TTFT SLO。
  - **依赖假设**：把 backward path 改成 coroutine 后，layer-level 或 operator-level suspend/resume 的开销足够低，且不会破坏 PyTorch Autograd 的 correctness。
  - **可能失效场景**：多 GPU 同步、NCCL 抖动、operator 粒度过细、或 PyTorch/模型图升级导致 coroutine 改造成本上升时，调度收益可能被同步和维护成本吞掉。
- **假设 1：iteration-level latency 可以被可靠预测或缓存。** Scheduler 需要知道当前 decode batch、PEFT phase、sequence length、hardware/model/adapter tuple 下的 co-execution latency；论文先用线性 latency predictor，之后用 profiling / runtime record cache。
  - **证据强度**：中。scheduler 平均开销 18 us，cache 命中后小于 1 us；但 predictor 在用 RTX 3090/H100 训练、A100 测试时 R2 只有 0.73 和 0.69，真正可靠性主要来自运行后缓存，而不是 cold-start 泛化。
- **假设 2：共享 base model 是 PEFT + serving 共置的核心前提。** LLMStation 的 memory manager 只保留一份 base model、adapter 和 inference state，PEFT 独占 fine-tuning state；这让 vLLM+torchtune 这类 out-of-the-box baseline 在大模型上天然吃亏。
  - **证据强度**：强。70B 实验中 vLLM+torchtune 因无法共享 base model 只能把 serving 和 tuning 放到不同 server，而 LLMStation 能利用两台 server 的剩余资源。

## 核心方法

LLMStation 的控制面是 SLO-aware iteration-level scheduler。每轮循环先取 inference queue 和 fine-tuning queue：如果有新 inference request，优先执行 prefill，并暂停 PEFT worker；进入 decoding 阶段后，scheduler 根据当前 inference batch、PEFT batch、PEFT 所处 phase、hardware/model/adapter 配置查询 profiling/cache 或调用 latency predictor，再由 planner 计算本轮可执行的 PEFT tasklet 数。没有 PEFT queue 时退化为 [[Continuous-Batching]]；没有 inference queue 时退化为普通 fine-tuning。

Planner 的目标是最大化本轮 PEFT tasklet 数，同时满足 decoding SLO 和显存约束。论文把 decoding tasklet 单独执行 latency 记为 `l_d0`，与 PEFT 共执行时 decoding latency 记为 `l_d`，PEFT tasklet latency 记为 `l_p`，推导出 PEFT tasklet 上界。实现上还会计算 inference 与 PEFT 的 peak memory usage，避免计划出一个 SLO 可行但显存不可行的 batch。

为了让 backward pass 可调度，LLMStation 修改 PyTorch Autograd，把 backward call chain 中的 nested function 变成 C++ stackless coroutine：调用改为 `co_await`，返回改为 `co_return`。PEFT worker 通过 coroutine executor 在 scheduler 指定的 layer 数后主动 suspend，把控制权还给 scheduler；下一轮 decoding 前再根据新的 SLO 预算 resume。这是论文最关键的工程转折：没有 suspendable Autograd，PEFT 只能以 step 为粒度被抢占，无法跟 inference iteration 对齐。

Forward pass 与 decoding 的共执行由 Fusion engine 处理。对 Transformer layer 中的 QKV projection、AttnOutput projection、GateUP 和 Down projection，Fusion engine 将 PEFT token tensor `(S_f, H)` 与 inference token tensor `(S_i, H)` composite 成 `(S_f + S_i, H)` 一起做 projection，从而摊薄 kernel launch、data movement 和 compute overhead；attention 本身仍拆开执行，因为 inference 需要写入/读取 [[KV-Cache]]，PEFT forward 需要自己的训练状态。adapter computation 借鉴 [[Punica]] 风格的 batched adapter handling，与 [[vLLM]] 继承来的 serving path 结合。

Memory manager 把 base model、adapter、inference state 作为 PEFT worker 和 inference worker 共享对象，只让 fine-tuning state 独占。GPU memory 不足以容纳新 inference state 时，LLMStation 可以把部分 GPU tensor swap 到 CPU memory，再在资源恢复时换回。分布式场景下，论文采用 [[Tensor-Parallelism]]：QKV/GateUP 按列切，AttnOutput/Down 按行切，并在相应 forward/backward 边界插入 all-reduce。

实现规模约 3k LOC，组合了多个已有系统：Autograd engine 来自修改 PyTorch，inference/memory/cache manager 建在 [[vLLM]] 上，fusion engine 建在 FineInfer 上，parallelism 参考 Nanotron，并用 Hugging Face PEFT 对齐 fine-tuning 结果以确认实现正确性。

## 设计取舍

- **细粒度调度换来 profiling/prediction 复杂度**：iteration-level planner 可以随请求波动调整 PEFT work，但必须维护以 hardware、model、adapter、decode batch size、PEFT input length 为 key 的 latency cache。cold-start 或 workload 突变时，SLO 安全性依赖 predictor 和保守预算。
- **用户态 Autograd 改造避开硬件/driver 改动，但增加维护面**：C++ stackless coroutine 比 GPU context switch 轻得多，单 GPU overhead 小于 0.5%；不过修改 PyTorch backward path 意味着模型兼容性、debuggability、版本升级和异常恢复都要由系统承担。
- **fusion 聚焦 decode + PEFT forward，而不是把所有阶段都混在一起**：prefill 到来时 PEFT 通常要暂停，因为 TTFT 对用户更敏感；这让严格 TTFT SLO 下 LLMStation 的 PEFT 吞吐仍会受限。
- **共享 base model 提升 memory efficiency，但收窄适用范围**：LLMStation 最适合 serving 与 PEFT 围绕同一个 base model 或少量 shared base model 展开；多 base model、full fine-tuning、或者需要强隔离的多租户环境会削弱该设计。
- **decoding SLO 近似 TPOT，但不完全等价**：论文承认 monolithic serving 中 decoding SLO 与 TPOT 不完全相同，只有 disaggregated serving 下二者更接近；当前 planner 不是严格 TPOT-aware。

## 实验与结果

- **实验设置**：模型覆盖 Llama-3.1-8B、Llama-2-13B、Llama-3.1-70B；硬件配置为 2x RTX 3090、4x RTX 3090、2 台 4x H100 server；数据集使用 ShareGPT 做 inference input、Alpaca 做 PEFT input，请求 trace 使用 synthetic steady rate 和 BurstGPT。
- **SLO 与指标**：端到端主指标是在不违反 P99 TTFT 和 P99 TPOT SLO 时能达到的 PEFT throughput。默认 P99 TTFT SLO 为 500 ms，P99 TPOT SLO 为 8B 的 50 ms、较大模型的 80 ms。
- **Synthetic workload 主结果**：在 Llama-8B 和 Llama-13B、RTX 3090 配置下，低 inference request rate（≤0.5 req/s）时，LLMStation 相比 FineInfer / vLLM+torchtune / chunked-training 分别提高 2.38-8.17x、2.53-14.77x、1.57-2.18x PEFT 吞吐。
- **70B 跨 server 结果**：在 8x H100 serving Llama-70B 时，当 inference 请求不能饱和单台 server，LLMStation 相比 FineInfer / vLLM+torchtune / chunked-training 最高提高 1.77x、1.8x、1.38x；当 inference 需要两台 server 才能满足 SLO 时，FineInfer 和 vLLM+torchtune 的 PEFT 吞吐降到 0，而 LLMStation 还能利用剩余资源。
- **Real-world trace 结果**：BurstGPT trace 平均 4.15 req/s。real-world burst 会让更多 decoding phase batching 在一起，给 PEFT 留出空间；但随着 TPOT SLO 放宽，chunked-training 的 chunk size 可变大，和 LLMStation 的差距缩小。严格 TTFT SLO 下，LLMStation 也受限，因为 prefill 只能在当前 decoding step 之后执行。
- **Latency tradeoff**：不设 SLO、固定 PEFT throughput 时，Llama-8B on 2x RTX 3090 下，LLMStation 相比 FineInfer / vLLM+torchtune / chunked-training 最高降低 P99 TTFT 33.13x / 52.64x / 1.4x，降低 P99 TPOT 2.29x / 362.49x / 1.29x。Llama-70B on 8x H100 下，相比 FineInfer / chunked-training 最高降低 P99 TTFT 180.48x / 1.23x，降低 P99 TPOT 14.22x / 1.24x。
- **Overhead**：Autograd coroutine suspend/resume 在单 GPU fine-tuning 中额外 latency 小于 0.5%；多 GPU fine-tuning 最高 18%，主要来自 inter-GPU / inter-process synchronization。Scheduler planner + predictor 平均 18 us/iteration，cache 命中时小于 1 us。
- **Adapter sensitivity**：在 Llama-8B + 2x RTX 3090、8 个 LoRA adapter 设置下，LLMStation 在 adapter access distribution 和 LoRA rank sweep 中相比分别最高 2.98x / 2.41x / 1.74x 与 2.98x / 2.41x / 1.73x；但 uniform adapter access 下所有系统都降到 0，因为 serving inference alone 已经违反 P99 TTFT SLO。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| LLMStation improves SLO-limited PEFT throughput at low arrival rates | 2.38–8.17× vs FineInfer; 2.53–14.77× vs vLLM+torchtune (§6.2, Fig.9) | 8B/13B, RTX3090, synthetic rate ≤0.5 req/s, specified P99 SLOs | high |
| Two H100 servers retain cross-server residual-resource benefit | highest ratios 1.77×/1.8×/1.38× against three baselines (§6.2, Fig.9) | 70B on two 4×H100 servers | high |
| Strict TTFT constrains concurrent PEFT under real request variation | BurstGPT average 4.15 req/s; prefill waits for current decode (§6.2, Fig.9) | mechanism boundary, not a universal speedup | high |
| Iteration scheduling overhead is low on one GPU but higher on multiple GPUs | backward overhead <0.5% single GPU, up to 18% multi-GPU; planner 18µs/iteration (§6.4, Fig.12) | listed Llama models and suspend/resume scheme | high |
| Uniform adapter access can exhaust multiplexing slack | 8 adapters/rank 32: all throughputs zero when serving violates P99 TTFT (§6.5, Fig.13) | 8B, 2×RTX3090, BurstGPT workload | high |

## 批判性分析

### 论证链条

论文的主链条基本闭合：先用负载波动、decoding MFU 低、PEFT compute-intensive、context switch 和 MPS interference 说明“单一时间/空间复用不够”；再把调度粒度推进到 inference iteration 与 PEFT layer tasklet；最后用 synthetic + BurstGPT trace 展示在 SLO 下 PEFT throughput 增加。Observation、design 和 result 的对应关系很清楚，尤其是 FineInfer 卡 TTFT、MPS 卡动态资源比例、chunked-training 卡 data movement 这三条 baseline 分解。

真正的外推在“resource multiplexing in LLM deployments”这个大 claim 上。实验证明的是 PEFT + serving、shared base model、LoRA adapter、TP-dominated server 内/跨 server 设置下的共置收益；它还没有证明更一般的 GPU virtualization、多租户 isolation、heterogeneous model pool 或 full fine-tuning 场景。论文自己也把“future GPU virtualization foundation”放在更远的位置，这个边界应该保留。

### 假设压力测试

LLMStation 最怕的 workload 是 serving 本身已经吃满 SLO slack。uniform adapter access 实验里所有系统 PEFT throughput 为 0，就是一个很好的反例：如果多 adapter serving 让 inference alone 都违反 TTFT，PEFT multiplexing 没有空间。类似地，长 context decode、heavy speculative decoding verification、或更高 batch 可能把 decode 从“memory-bound 且 compute 有余量”推向复合瓶颈。

第二个压力点是 latency cache 的时效性。论文的 predictor R2 不是特别高，但系统依赖 runtime record cache 快速接管；这在 stable hardware/model/adapter tuple 下合理，在热升级 kernel、改变 tensor parallel degree、混用不同 LoRA rank、NCCL contention 或 GPU thermal throttling 时需要 profile invalidation 和安全余量。论文没有把这些作为独立 failure mode 评估。

第三个压力点是 PEFT 作业语义。论文用 PEFT samples/s 衡量后台训练吞吐，但真实持续 fine-tuning 更关心 adapter quality、deadline、数据新鲜度、checkpoint cadence 和训练失败恢复。LLMStation 证明了吞吐和 SLO 的调度可行性，但没有充分回答“这些被切碎、被暂停/恢复的 PEFT 作业在生产训练生命周期中如何管理”。

### 实验可信度

实验优点是 baseline 选择覆盖了 out-of-the-box spatial sharing、FineInfer temporal sharing 和 chunked-training，且作者说明会调优 FineInfer deferral bound、MPS active thread percentage 和 chunk size。ShareGPT、Alpaca、BurstGPT 也是 serving/tuning 论文里常见且可复现的输入来源。70B + 8x H100 结果让论文不只停留在小模型单机玩具设置。

短板是 production representativeness 仍有限。BurstGPT trace 代表公共 workload 的请求到达形态，但不等于企业内持续 PEFT + online serving 的真实联合 trace；PEFT queue、adapter 更新频率、数据 drift、租户隔离和作业优先级都由实验设定间接假设。vLLM+torchtune 作为 out-of-the-box baseline 很有意义，但由于不能共享 base model，在 70B 场景结构性吃亏；这证明“需要一体化系统”，但不完全证明 LLMStation 的每个细粒度机制都必要。

metric 也偏系统 throughput/latency。论文说 fine-tuning 结果与 Hugging Face PEFT 对齐，但主实验没有展示任务质量、收敛曲线、adapter checkpoint consistency 或长时间连续训练中 suspend/resume 对训练 pipeline 的影响。对系统论文这是可以接受的范围，但对“continuous fine-tuning after deployment”这个动机来说，质量侧证据偏少。

### 系统性缺陷

论文未充分讨论 observability 和 failure handling。一个 PEFT backward coroutine 被 suspend 在 layer/operator 中间时，调试、取消、异常退出、checkpoint、重试和资源回收都会比普通 PyTorch training 更复杂；memory manager 还可能把 tensor swap 到 CPU，这些状态如何在 worker crash 或 request cancellation 下保持一致，论文没有展开。

多租户隔离也基本没有覆盖。LLMStation 的设计目标是 controllable interference，但不是 hard isolation；如果同一 GPU 上有多个应用、不同租户 adapter、或优先级不同的 PEFT job，scheduler 是否需要 fairness、quota、admission control 和 per-tenant SLO accounting，论文没有给出机制。

并行策略边界清楚但偏窄。论文只考虑 [[Tensor-Parallelism]]，不处理 pipeline parallelism，也不做 workload-aware dynamic parallelization。对于跨节点低带宽、prefill/decode disaggregation、或 DynamoLLM 式定期调整 TP degree 的部署，LLMStation 需要重新定义 scheduler 的资源视图。

## 局限与后续工作

- **局限 1：适用窗口依赖 serving SLO slack。** 当 inference alone 已接近或违反 TTFT/TPOT SLO 时，LLMStation 无法创造额外空间。后续应在不同 request burstiness、context length、adapter distribution 和 target SLO 下画出“可 multiplex 区域”。
- **局限 2：decoding SLO 不是严格 TPOT-aware。** 当前 planner 用每个 decoding iteration 的 latency 近似控制 TPOT。未来可以维护每个 running request 的累计 TPOT debt，把 scheduler 变成 request-level SLO accounting，而不是 iteration-level slack accounting。
- **局限 3：Autograd 改造的工程风险未被长期评估。** 需要测 PyTorch 版本升级、不同 model graph、gradient checkpointing、quantization、mixed precision 和 optimizer state 管理对 coroutine backward path 的兼容性。
- **Future work 1：生产联合 trace 评估。** 收集或合成同时包含 inference arrivals、PEFT job arrivals、adapter update frequency、tenant priority 的 trace，比较 cost、deadline miss、tail latency 和 adapter freshness，而不只看 PEFT samples/s。
- **Future work 2：把 operator-level suspend 与 chunked-training 结合。** 论文指出 LLMStation 可在 operator graph 上 suspend，超长 context PEFT 可结合 chunked-training；这需要量化 layer-level、operator-level、chunk-level 三种粒度在 overhead 和 SLO slack 利用率上的 crossover point。
- **Future work 3：面向 disaggregated serving 和 PP 的 scheduler。** 在 prefill/decode 分离、pipeline parallelism、跨节点 KV routing 下，PEFT tasklet 应该插在哪个 stage、如何跨资源池预算 SLO，是一个比当前 TP setting 更接近生产集群的问题。
- **Future work 4：安全余量与 profile invalidation。** 给 latency cache 加版本、温度、NCCL contention、adapter rank/distribution 等 invalidation signal，并评估 conservative planner 对吞吐和 SLO violation rate 的影响。

## 相关

- **相关概念**：[[LoRA]]、PEFT、[[KV-Cache]]、[[Continuous-Batching]]、[[Tensor-Parallelism]]、SLO-aware scheduling、GPU multiplexing
- **同类系统**：[[vLLM]]、FineInfer、FlexLLM、[[Punica]]、[[SLoRA]]、[[Orca]]
- **相关论文页**：[[vLLM-SOSP23]]
- **同会议**：[[ATC-2025]]
