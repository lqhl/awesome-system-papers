---
type: paper
name: MOE-INFINITY
full_title: "MOE-INFINITY: Efficient MoE Inference on Personal Machines with Sparsity-Aware Expert Cache"
authors: [Leyang Xue, Yao Fu, Zhan Lu, Chuanhao Sun, Luo Mai, Mahesh Marina]
venue: arXiv
year: 2024
tags: [llm-inference, moe, expert-cache, offloading, personal-computing]
source_pdf: "[[arxiv24-xue-moe-infinity.pdf]]"
source_md: "[[arxiv24-xue-moe-infinity]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# MOE-INFINITY：具有稀疏感知专家缓存的个人计算机上的高效 MoE 推理（arXiv 2024）

> **原题**：MOE-INFINITY: Efficient MoE Inference on Personal Machines with Sparsity-Aware Expert Cache

> **一句话总结**：MOE-INFINITY 把 personal-machine [[MoE]] 推理的核心假设押在 batch size = 1 时 request 内 expert 激活高度稀疏且可按历史 request pattern 匹配，用 Expert Activation Matrix Collection 做 expert cache 驱逐和预取，在单张 RTX A5000 上让 DeepSeek-V2-Lite TPOT 从 vLLM 的 485ms 降到 155ms，并报告跨模型 3.1-16.7x per-token latency 改善。

## 问题与动机

这篇论文要解决的是「大 [[MoE]] 模型在个人机器上能不能跑得像全量驻留 GPU 一样快」的问题。MoE 的理论优势是每个 token 只激活少数 expert，但真实部署时总参数仍然巨大：expert 权重占模型参数主体，常常只能放在 host memory，再通过 PCIe 搬到 GPU。对于只有 24-48GB GPU memory 的个人机器，瓶颈不是算力本身，而是 expert 权重在 CPU/GPU 之间的搬运和 GPU 等待。

作者认为现有 offloading 系统把问题看错了。DeepSpeed-Inference、Mixtral-Offloading 这类系统常按计算图依赖或下一层顺序做 prefetch，近似把 MoE 当成 dense model 的动态版本；vLLM/Ollama 等 on-demand 或 LRU/LFU 风格缓存又缺少对 router 稀疏性的预测。结果是两类失败：要么预取太多不需要的 expert 把 PCIe 堵住，要么 cache hit rate 低导致 GPU 等待 on-demand fetch。论文 Table 1 中 DeepSeek-V2-Lite 在单张 A5000 上，vLLM 平均 TPOT 485ms、DeepSpeed 737ms、Mixtral-Offloading 1250ms、Ollama 2590ms，而 MOE-INFINITY 是 155ms。

论文的 deployment scope 很明确：personal machine、single user、通常 batch size 为 1。它不是为云端 [[Continuous-Batching]] 场景设计的通用 MoE serving 系统。这个范围收窄是贡献成立的关键，因为单 request 内的 expert 复用 skew 会被多 request 聚合抹平；如果把不同用户请求混在一起，作者依赖的 request-level pattern 就不再自然出现。

## 关键观察 / 隐含假设

- **观察 1：单 request decode 阶段的 expert working set 很小，可以放进有限 GPU cache。** 作者在多种 MoE 模型和任务上统计发现，DeepSeek、QWen-MoE、NLLB、Switch 这类约百 expert 模型中，一个 request 内反复激活的 expert 少于 5%；即使 Mixtral expert 数少、单个 expert 大，单 request 激活比例也约 25%。
  - **依赖假设**：personal deployment 的常态是 batch size = 1，且用户一次主要处理一个 prompt；GPU memory 除 dense 参数和 [[KV-Cache]] 外仍能留出足够 expert buffer。
  - **可能失效场景**：多用户 continuous batching、agent 并发工具调用、serverless 本地队列、或很长 context 使 KV cache 挤压 expert cache 时，working set 可能不再小到足以稳定命中。

- **观察 2：expert reuse skew 存在于 request 内，但跨 request 聚合后趋于均匀。** Figure 2 展示 Mixtral 和 DeepSeek 的单条 sequence 中少数 expert 明显更热；但合并 1000 条 sequence 后，各 expert reuse count 接近均匀。因此全局 LFU/counting 方法无法知道当前 request 未来更可能重用哪组 expert。
  - **依赖假设**：router 学到的 expert specialization 会让同一 prompt/context 在 decode 中持续落到相似 expert group，而不同 prompt 之间 group 转移难预测。
  - **可能失效场景**：如果模型 router 更均匀、负载均衡正则更强、或 workload 内 prompt 风格快速变化，历史 request-level pattern 对当前 request 的预测价值会下降。

- **观察 3：request-level EAM 可以聚成少量 activation groups，但 group transition 难预测。** 作者用 K-means 对 request-level Expert Activation Matrix 聚类，1000 个样本中常见 group 数约 10-30；但 Markov transition 的最高概率约 0.3，多数低于 0.12。这说明可行策略不是学习 request 间转移，而是拿当前 request 的 partial EAM 去匹配历史相似 EAM。
  - **依赖假设**：在线匹配历史 EAM 的计算和存储开销足够低，并且最近历史足以覆盖当前 workload 的 activation groups。
  - **证据强度**：中。聚类和 transition 分析支撑方向，但数据集来自 BIGBench、FLAN、MMLU 的离线任务集合，离真实个人桌面 workload 还有距离。

- **假设 1：host DRAM 足以容纳完整 expert 参数，PCIe 是主导瓶颈。** 实现把 dense 参数和 KV cache 留在 GPU，把 expert 全量放在 host memory；评估对不同模型配置了 32GB 到 1TB host memory。
  - **证据强度**：中。对单机 workstation 合理，但对普通消费级个人电脑、统一内存设备、NVMe offload、或 CXL/NVLink 拓扑，瓶颈排序可能不同。

- **假设 2：缓存策略主要影响 latency，不改变模型正确性。** MOE-INFINITY 只缓存和预取 router 已经或可能要用的 expert 权重；miss 时仍 on-demand fetch，因此语义上不近似路由决策。
  - **证据强度**：强。方法不改变模型输出路径；真正风险在 tail latency、资源隔离和故障恢复，而不是模型精度。

## 核心方法

MOE-INFINITY 的核心抽象是 Expert Activation Matrix（EAM）。对一个有 L 个 MoE layer、每层 E 个 expert 的模型，EAM 是 L x E 的计数矩阵，记录每层每个 expert 被 token routed 的次数。论文区分 iteration-level EAM（iEAM）和 request-level EAM（rEAM）：iEAM 描述一次 forward iteration 中已经经过的层，rEAM 累积一个 request 的 prefill 或 decode 过程。这个抽象把 router 的动态行为变成可比较的稀疏矩阵，而不是把 expert 当成普通 cache line。

Expert Activation Matrix Collection（EAMC）是在线历史库。一个 request 结束后，系统把它的 rEAM 记录进 EAMC；新 request decode 时，系统用当前 iEAM 与 EAMC 中历史 rEAM 做 cosine distance 匹配。匹配到相似 EAM 后，把这些历史矩阵按行归一化聚合，得到 predicted EAM（pEAM），也就是每层每个 expert 的 future activation likelihood。cosine distance 的选择回应了两个问题：不同序列长度下只比较相对激活频率，以及稀疏向量中高频 expert 的相似性更重要。

pEAM 同时驱动 prefetch 和 eviction。对于 prefetch，MoE layer 顺序执行，系统优先预取未来层更可能被激活的 expert，并通过 layer proximity 给更近的层更高优先级。对于 eviction，当 expert cache 满时，系统对 cache 中每个 expert 计算 future reuse priority，驱逐预测复用概率最低的 expert。这个策略直接回应「全局计数会被跨 request 均匀化」的观察：它不问某个 expert 总体热不热，而问它在当前 request 所属 activation group 中还会不会热。

实现上，MOE-INFINITY 保留 dense 参数和 [[KV-Cache]] 在 GPU，offload expert 权重到 host DRAM。每个 GPU 有独立 I/O thread，使用 pinned memory 和 DMA 在 PCIe 上搬运 expert；论文声称一个线程足以 saturate PCIe 4.0 32GB/s。多 GPU 场景下，系统用 expert ID hashing 做 [[Expert-Parallelism]]，并在 NUMA 环境中预分区 expert 到对应 NUMA node。EAMC 可随 checkpoint 持久化，用于故障后恢复 prefetch/cache 性能。

EAMC 自身也有简单替换策略：容量固定，新的 rEAM 到来时，与已有 EAM 比较 cosine distance，替换最相似的旧项。这个设计偏 worst-is-better：不做昂贵 clustering，不维护复杂 learned predictor，而是保留近期和多样性。Appendix 报告 1K EAM 查询约 21us、10K EAM 约 226us，低于模型 decode latency 的 1%；容量上界用 sphere covering 给出理论讨论，但实际系统采用小容量经验设置。

## 设计取舍

- **把问题限定到 batch size = 1，换来强 activation locality。** 这是论文最重要的取舍：personal-machine 场景被刻意区分于云端 [[Continuous-Batching]]。收益是 request-level pattern 清晰，代价是方法对多请求混合的泛化不强。
- **保守保持模型语义，牺牲部分实现复杂度。** 系统不改 router、不改 expert 选择，miss 后仍 fetch 正确 expert；但要在推理 runtime 中维护 EAM、EAMC、prefetch thread、cache priority、NUMA/GPU expert mapping。
- **固定容量 EAMC 简化在线成本，牺牲理论最优。** 作者承认更复杂的 clustering 可能增强代表性，但对 Arctic-128x4B/FLAN 这类百万 EAM、4480 维向量 workload，离线聚类成本不实际。
- **优先 GPU 常驻 KV cache，牺牲 expert cache 容量。** 长 context 下这让系统避免像 [[vLLM]] 那样把 KV cache traffic 与 expert fetch 叠加，但 context 继续变长时 expert buffer 会被压缩到 2GB/1GB，最终退化到 on-demand fetching。
- **边界条件**：当模型有多 expert、小 expert、低 activation ratio 时设计很优雅；当模型像 Mixtral 一样 expert 数少但单 expert 大、activation ratio 高，或 workload shift 很快、host memory/PCIe 不匹配时，收益明显变脆。

## 实验与结果

- **DeepSeek-V2-Lite 单卡主结果**：Table 1 在 NVIDIA A5000 24GB + PCIe 4.0 上报告 MOE-INFINITY 平均 TPOT 155ms、tail TPOT 169ms、GPU idle time 51ms；对比 vLLM 485ms/493ms/254ms、DeepSpeed 737ms/803ms/513ms、Mixtral-Offloading 1250ms/1530ms/754ms、Ollama 2590ms/2599ms/2073ms。
- **跨模型 end-to-end**：prompt length 512、decode length 32、BIGBench/FLAN/MMLU 共 290 个任务。Switch、NLLB、DeepSeek 上 MOE-INFINITY 分别达到约 155ms、531ms、155ms latency，接近全模型驻留 GPU 的性能；NLLB 和 Switch 的非 offloading 对照分别需要 8 GPUs 和 4 GPUs。
- **Mixtral 是弱势场景**：Mixtral-8x7B expert 少且大、每 token 激活比例高，MOE-INFINITY latency 约 836ms，只比 BrainStorm/Mixtral-Offloading 等 offloading baseline 好约 1.4x；这说明方法收益依赖「多 expert + 低选择比例」。
- **Arctic 大模型可用性**：Snowflake Arctic 参数约 900GB，MOE-INFINITY 是论文评估中唯一能在单 GPU 上给出竞争性性能的 serving 系统；但这也依赖 1TB host memory，离普通个人设备有一定距离。
- **long context**：DeepSeek-V2-Lite 在 4K 到 128K context 下，context 增长使 GPU 中 KV cache 变大、expert buffer 变小；在 2^16 context buffer 约 2GB、2^17 约 1GB 时性能退化。MOE-INFINITY 的 on-demand fetching 额外增加约 137ms，低于 vLLM/Mixtral-Offloading 的退化。
- **EAMC capacity**：容量从 1 增到 120 时，NLLB、Switch、Mixtral 都接近最低平均 latency；论文解释为约 3% 请求容量即可覆盖大部分 activation pattern。
- **workload shift recovery**：Table 3 显示任务内或数据集间切换后恢复低 latency 需要的 request 数通常是几十个；例如 NLLB 在 MMLU tasks 为 0-14-43，Mixtral 在 BIGBench tasks 为 0-11-49，Arctic 在 MMLU -> BIGBench 为 2-28-41。

## 批判性分析

### 论证链条

论文的逻辑链条总体闭合：personal machine batch size = 1 -> request 内 expert reuse skew -> 跨 request 频率均匀导致 LRU/LFU/counting 不够 -> 用当前 partial EAM 匹配历史 request EAM -> 预测 future expert reuse -> cache eviction/prefetch 降低 PCIe traffic 和 GPU idle。Table 1 和 Figure 7 的 latency/GPU idle 结果与这个链条一致，尤其是 BrainStorm 和 DeepSpeed 因 inaccurate prefetch 造成 PCIe contention 的解释。

最容易被外推过度的是「personal machine」这个标签。论文评估的是 single GPU workstation 加大量 host DRAM，而不是普通笔记本或消费级桌面。Arctic 需要 1TB host memory，NLLB 需要 256GB，Mixtral 需要 128GB；因此它证明的是「单 GPU + 足够 DRAM 的本地 workstation」可行，不等于所有个人机器都能轻松部署大 MoE。

### 假设压力测试

第一层压力来自 workload 形态。如果个人 AI agent 开始并发跑多个子任务，或者本地 serving stack 也做 micro-batching，request-level EAM 会被多个 context 混合。作者的关键观察反而说明跨 request skew 会消失，所以这类场景可能让 EAMC 匹配退化。

第二层压力来自模型结构。Mixtral 结果已经暴露出低 expert count、高 activation ratio、单 expert 大的模型并不特别适合这种 cache。未来 MoE router 若更强调均衡、shared expert、fine-grained expert、或动态 expert composition，rEAM 的 group pattern 可能更难稳定复用。

第三层压力来自 memory hierarchy。论文默认 expert 全量进 host DRAM，PCIe 是主要路径；如果设备是 Apple unified memory、CXL memory pool、NVLink CPU-GPU、NVMe tiering，或者 GPU HBM 更大到能容纳大部分 expert，cache/prefetch 的最优点会改变。MOE-INFINITY 的 EAM 抽象仍可能有用，但系统设计不一定原样成立。

### 实验可信度

实验覆盖的模型比较广：DeepSeek、Switch、NLLB、Mixtral、Arctic，覆盖 expert 数和 expert 大小差异；任务集也有 BIGBench、FLAN、MMLU 共 290 个任务。baseline 包括 vLLM、Ollama/Llama.cpp、Mixtral-Offloading、DeepSpeed-Inference、BrainStorm 复现版，基本覆盖个人机器 MoE offloading 的直接对手。

不足是 workload 代表性仍偏 benchmark。BIGBench/FLAN/MMLU 能制造多任务输入，但不等价于真实个人使用中的长会话、多轮聊天、工具调用、代码生成、RAG、image/text 混合请求。论文测了 long-context generation，但没有给出真实 trace 下 prompt locality、session locality、请求间间隔和并发的影响。

baseline 公平性有一个小风险：BrainStorm 非开源，作者是在 MOE-INFINITY 中复现其 model-level analysis；DeepSpeed/FastGen、vLLM、Ollama 对不同 MoE model 的支持程度也不完全一致。论文给出系统级 latency，但对每个 baseline 的 cache size、prefetch policy、CPU thread、pinned memory 配置细节解释有限。结论方向可信，精确倍数需要谨慎引用。

### 系统性缺陷

论文主要优化 average TPOT 和部分 tail TPOT，没有系统讨论多租户隔离、公平性、优先级抢占、观测性或运维调试。personal machine 场景可以弱化这些问题，但一旦系统被用作本地服务或团队共享 workstation，这些就会重新出现。

EAMC 的恢复和 workload shift 适应需要几十个 request。对 benchmark 来说这很小，但对个人机器的低频任务切换可能并不小：用户从代码生成切到翻译，再切到长文总结时，每个模式可能只有少量请求。此时冷启动和切换窗口内 latency 会更影响体验。

长 context 下 MOE-INFINITY 选择让 KV cache 常驻 GPU，这是合理取舍，但也把 expert cache 变成被动剩余空间。论文报告 128K context 下所有系统最终 OOM，并没有探索 KV cache 压缩、分层 KV cache、或 prompt/session aware expert cache 的联合优化。

## 局限与后续工作

- **局限 1：部署模型是 single-user batch size = 1。** 后续应在受控 micro-batching 下测量 EAM 匹配质量、cache hit rate、TPOT/tail TPOT，找出并发度从 1 增加到 N 时收益何时崩塌。
- **局限 2：真实个人 workload 缺失。** 可以收集本地 chatbot/agent/code-assistant trace，比较 benchmark task shift 与真实 session shift 下的 EAMC recovery request 数、冷启动 TPOT 和 cache churn。
- **局限 3：memory hierarchy 单一。** 论文主要评估 PCIe 4.0 + host DRAM；future work 可以把同一 EAM policy 放到 unified memory、CXL memory、NVLink、NVMe tiering 上，测量瓶颈是否从 PCIe bandwidth 转向 page fault、NUMA 或 storage latency。
- **局限 4：与 [[KV-Cache]] 管理割裂。** long context 结果说明 KV cache 与 expert cache 在 GPU memory 上竞争；一个可验证方向是联合优化 KV cache placement/quantization 和 expert cache capacity，看 32K-128K context 下 TPOT 是否能保持平滑。
- **局限 5：EAMC policy 仍是启发式。** 固定容量 + 最近/多样性替换简单有效，但可以客观比较 against session-aware, task-aware, 或 prompt-embedding-assisted EAM selection，指标包括 query overhead、hit rate、workload shift recovery 和 tail TPOT。

## 相关

- **相关概念**：[[MoE]]、[[KV-Cache]]、[[Continuous-Batching]]、[[Expert-Parallelism]]
- **同类系统**：[[vLLM]]
- **同主题**：[[AI-Infra]]
- **对比**：[[OD-MoE-arXiv25]]、[[ContextAwareMoE-CXLNDP-arXiv25]]、[[CoX-MoE-DAC26]]、[[MoE-Serving-Tax-MLSys26]]
