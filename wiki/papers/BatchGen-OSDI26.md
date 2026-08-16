---
type: paper
name: BatchGen
full_title: "BatchGen: An Architecture for Scalable and Efficient Batch Inference"
authors: [Tairan Xu, Leyang Xue, Zhan Lu, Jinfu Deng, Hongyang Xiao, Yinsicheng Jiang, Congjie He, Matej Sandor, Le Xu, Luo Mai]
venue: OSDI
year: 2026
tags: [llm-inference, batch-inference, coroutine, mixture-of-experts, scheduling]
source_pdf: "[[osdi26-xu-tairan.pdf]]"
source_md: "[[osdi26-xu-tairan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# BatchGen：面向大规模批推理的序列协程架构（OSDI 2026）

> **原题**：BatchGen: An Architecture for Scalable and Efficient Batch Inference

> **一句话总结**：BatchGen认为互动服务“一个sequence长期绑一张GPU、一次forward不可中断”的执行模型不适合离线大批量任务：MoE tokens分散到几百个experts后，每个expert仍吃不到足够batch；heavy-tail output又让最后几条sequence拖住整批。它把sequence表示成可`YIELD/COMBINE/PARTITION/MIGRATE`的event-driven coroutine，在attention–MoE边界重组大batch、在末尾用idle GPUs加速straggler；10K-request、128-H20评测中BCT最高改善2.3倍，单A5000 offloading相对最强可运行基线最高9.6倍。

## 问题与动机

离线生成、model evaluation、test-time scaling和RL rollout不要求每条request立即响应，而是关心整批完成时间（batch completion time，BCT）。BatchGen把BCT定义为batch提交到最后一条sequence完成；若系统分sub-batches提前返回，单条sequence completion time由所属sub-batch决定。它明确优化BCT，而不是interactive serving的TTFT/TPOT（§1、§2.1、图 1）。

第一类浪费来自[[Mixture-of-Experts|MoE]]内部。即使global batch有百万tokens，每个token只路由少数experts，数百个experts再切分后，per-expert GEMM仍可能远低于GPU饱和点。论文测得SGLang mixed或P/D disaggregated在足够多输入下仍约有50% GPU未利用；传统engine一次forward把attention和MoE绑定为同一batch，无法在二者之间等待更多sequence再重组（§2.2、图 2b）。

第二类浪费来自sequence间heavy tail。production DeepSeek-R1 trace中，P99 output length是P95的3.78倍，最大值是P95的9.2倍；短sequence结束后，少数stragglers决定BCT，多数GPU空转。作者称现有engine及disaggregated variant因此损失约10%–70%可达到的GPU性能（§2.2、图 2c）。

现有[[vLLM]]、[[SGLang]]和[[TensorRT-LLM]]把sequence state与GPU固定绑定，并将一次model forward作为atomic scheduling unit。BatchGen的核心问题是：batch workload愿意牺牲单sequence latency，能否把neural module boundary变成yield point，让runtime按当时的batch、memory和idle GPUs重新组织计算（§3）。

## 关键观察 / 隐含假设

- **观察 1：sequence是独立且可恢复的调度单位。** 当前module、hidden state、[[KV-Cache]]和生成metadata足以决定后续执行；在module boundary暂停后可在另一device恢复，不改变计算依赖（§3–§4.1、图 4）。
  - **依赖假设**：sequence间没有共享mutable state或跨sequence算子；“可迁移”也不等于state很小，2K DeepSeek-R1 MLA KV示例已达144 MB（§5.5）。
- **观察 2：[[Attention|attention]]与[[MoE|MoE]]的最佳batch不同。** attention在较小batch已饱和，稀疏MoE需要更大的global batch；在两者间yield可让多个attention sub-batches合并后再执行experts（§4.3、图 6、算法 1）。
  - **依赖假设**：等待/保存hidden states与KV transfer小于larger expert GEMM带来的收益；这更适合batch而非低latency服务。
- **观察 3：long-tail只能运行时发现。** output length事前未知，静态placement无法知道哪些GPU先空；在batch drain后，coroutine可迁移多条stragglers，或把单条sequence改成tensor parallel（§5.1、§5.3）。
  - **可能失效场景**：tail不重、batch较小或network慢时，5–10秒parallelism reconfiguration可能比剩余计算更贵。
- **观察 4：prefill compute可隐藏offload，decode通常不能。** prefill attention计算密集，KV可逐layer异步写host，GPU同时最多保留约两层；decode每步算术强度低，restore/offload更容易落在critical path（§5.2、图 7）。
  - **依赖假设**：每节点有大host DRAM和足够[[PCIe|PCIe]] bandwidth；主testbed每node给2 TB host memory。
- **观察 5：batch BCT能摊销调度开销。** hidden checkpoint低于5 µs、metadata低于10 µs，但cross-node sync每64 tokens需5–10 ms，`PARTITION`重配约5–10秒；后者只在十多分钟batch末尾通常触发一次（§5.5、表 2）。
- **假设 1：系统拥有大量待处理sequence，可持续oversubscribe。** production描述会向instance投放远超并发容量的requests，让COMBINE有选择空间；low-arrival或严格FIFO服务不能获得相同batching freedom（§6.4）。
- **假设 2：Transformer MoE的重复layer可由单层profile代表。** static plan只profile一个代表layer并搜索`B_attn/B_moe/buffer`；异构layer、dynamic routing或kernel drift下预测精度未验证（§5.4）。

## 核心方法

### 序列协程（sequence coroutine）抽象

wrapper包住选定的`torch.nn.Module`，在module退出处生成event和successor。每个coroutine记录当前位置、hidden output、KV与callback；global scheduler从inactive queue取一个或多个coroutines dispatch到空闲GPU（§4.1、图 3–5）。四个primitives是：

- `YIELD`：保存当前state并释放GPU，类似`await`；
- `COMBINE`：把多个yielded tensors拼成batch并隐式resume；
- `PARTITION`：把一条长sequence用tensor parallel分到多GPU，或把多条tail sequences数据并行分散；
- `MIGRATE`：异步搬KV与metadata到另一device/node，由scheduler记录physical location。

yield point并非全部动态决定。MoE intra-forward使用按模型静态选好的option B：attention按`B_attn`运行、checkpoint并yield，再把多个hidden states合为`B_moe`执行MoE。把每个expert都变coroutine虽并行度最高，但million-scale coroutine state使memory不可接受；attention+MoE完全合并又失去expert batching（§4.3、图 6、算法 1）。

### runtime调度与long-tail处理

main loop持续选择inactive sequences并COMBINE。每decode一个KV page（默认64 tokens），dynamic sequence manager依次等待async append、移除已完成sequence、给将耗尽page的sequence扩容或yield到host，再从prefilled/suspended pool恢复新sequence。内存不足时优先yield decoded length最大的sequence，以释放更多GPU KV pages（§5.3）。

不同node的active count失衡时，`MIGRATE`搬suspended sequences；任务queue需短暂block以防执行/迁移race。没有waiting sequence可refill、global active count低于阈值时，`ONLONGTAIL`等待目标GPU上的coroutines都yield：多stragglers用[[Data-Parallelism|DP]]，单straggler用[[Tensor-Parallelism|TP]]。MHA/GQA KV按heads切分，MLA compressed KV则复制（§5.1、§5.3、算法 2）。

### host-first memory与自动plan

host memory保存shared model weights和node上所有sequence KV，作为checkpoint store。prefill只在GPU留resident small parameters、parameter ring buffer与single KV buffer；attention后逐layer把KV异步写host。decode用[[PagedAttention|paged KV]] manager，每条active sequence先预留两个future pages，需要时再扩（§5.2、图 7）。

planner profile一个representative layer在不同batch下的attention、MoE和collective cost，构建少于100 nodes的execution DAG，加入parameter prefetch、KV offload/restore和dependencies，枚举`B_attn`、`B_moe`与buffer sizes并选critical path最短的配置。这是离线static plan；runtime只在其允许的yield points上动态组合/迁移（§5.4）。

系统约13K行C++与49K行Python，control plane基于定制Ray；提供OpenAI-compatible batch API、huge-page host pool、mmap checkpoint cold start，以及在node failure时估算“迁移KV”和“重新prefill”谁更快。但failure recovery只有设计描述，没有评测（§5.6、图 8）。

## 设计取舍

- **BCT换per-sequence latency**：等待更多coroutines能形成大expert batch；一条sequence可能被yield/offload多次，不适合毫秒级interactive SLO。
- **module-level弹性换state movement**：打破atomic forward；hidden/KV checkpoint、host restore和network migration成为新开销与正确性面。
- **host作为checkpoint store换大DRAM/PCIe依赖**：GPU可容纳更多active work；每node需要TB级DRAM，decode transfer难被计算隐藏。
- **静态yield plan换搜索可控**：单层profile+DAG可自动选择常用配置；不能应对layer异质性或在线workload/kernel变化。
- **末尾动态TP换重配成本**：idle GPUs加速极长straggler；`PARTITION`本身5–10秒，只在remaining work足够大时划算。
- **oversubscription换调度自由**：pool始终有requests可选；严格arrival-order、公平性或不同tenant deadline会缩小COMBINE空间。
- **64-GPU高效instance换单实例无限扩展**：MoE all-to-all让收益在64 GPUs后饱和，128规模实际复制两个64-GPU instances（§6.4）。

## 实验与结果

- **平台、模型和baseline**：8–128张NVIDIA H20/H200，node内NVLink/PCIe 5.0、每node 2 TB host DRAM、node间200 Gb/s [[RDMA|RDMA]] InfiniBand；模型为Mixtral-8×7B/8×22B、DeepSeek-R1 671B、Kimi-K2 1T。主基线是vLLM 0.11.2、SGLang 0.5.5.post3及穷举调优的SGLang-Optimized（§6、表 3）。
- **6K-sequence离线推理**：16×H20和8×H200的8K-input/2K-output、2K/8K workloads上，相对SGLang-Optimized为1.25–1.66倍；8×H20的DeepSeek-R1因offload让batch从8–16增到1800+，BCT改善1.31–1.85倍。Kimi-K2在8×H20只有BatchGen能完成，但仍需659.8/1693.6分钟。16×H20的8K/2K上还比[[TensorRT-LLM|TensorRT-LLM]]快10%（§6.1、表 3）。
- **test-time scaling与RL rollout**：16×H20 DeepSeek-R1 RSA中，30分钟SLO可完成sequence数为SGLang-Opt的1.25–1.57倍，60分钟为1.66–1.75倍。VeRL每轮256 sequences时，active降至不多于8且length超过40K后触发`PARTITION+FP8`，rollout time降低5%–10%；论文没有报告整个训练最终wall time或quality（§6.2–§6.3、表 4）。
- **32–128 GPU规模**：10K DeepSeek-R1 requests上，12K/4K workload比SGLang-Opt快1.71–1.82倍，6.5K/2.8K快2.2–2.3倍。SGLang/vLLM超过16 GPUs有stability issue，因此baseline是多个独立16-GPU groups聚合；BatchGen也在64 GPUs后plateau，128用两个64-GPU instances。使用SGLang kernels的BatchGen*反而比原BatchGen更快，说明headline不是custom kernel贡献，也暴露其自有kernel仍有优化空间（§6.4、表 5）。
- **与P/D分离比较**：128×H20、10K requests、8K/2K workload中，SGLang P/D ratio从1:7到7:1需38.6–137.9分钟，相差3.6倍；最好4:4仍为38.6分钟，BatchGen不调ratio为17.5分钟，即2.2倍。但P/D baseline仍由8个16-GPU units组成，不是一个稳定的128-GPU engine（§6.4、表 6）。
- **单GPU与primitive成本**：A5000 24 GB+1 TB host上，Mixtral-8×22B ChatBotArena相对最强可运行offloading baseline从295.0小时降到30.8小时，约9.6倍；DeepSeek-R1只有BatchGen完成，但GSM8K/ChatBotArena仍需41.3/328.5小时，且FlexGen/MoE-Lightning是作者按论文重实现、single-GPU还额外把attention放CPU。常用yield低于10 µs，offloaded COMBINE约0.2 ms/sequence/layer，而`PARTITION`约5–10秒（§5.5、§6.5、表 2、7）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| attention–MoE间重组可提高batch inference效率 | 6K sequences上多平台比SGLang-Opt快1.25–1.85倍（表 3） | 四个MoE模型、H20/H200；没有dense/VLM结果 | 强（覆盖配置内） |
| coroutine能缓解runtime long-tail | RL tail触发PARTITION后rollout缩短5%–10%（§6.3） | 16×H20、DeepSeek-R1、synthetic threshold；无完整training result | 中到强 |
| 架构可扩到大fleet | 128-H20上最高2.3倍，BatchGen*仍保持/超过收益（表 5） | baseline按16-GPU groups聚合；BatchGen单instance也只扩至64 | 中 |
| 不需手调P/D ratio也能高效运行 | 17.5分钟对最佳SGLang P/D 38.6分钟（表 6） | 单8K/2K workload、128 H20；ratio units固定16 GPUs | 强（该配置） |
| coroutine offloading能让小显存跑大MoE | A5000上最高9.6倍；DeepSeek-R1仅BatchGen完成（表 7） | 1 TB host、作者重实现两基线、absolute time可达数百小时 | 中到强 |

## 批判性分析

### 论证链条

论文从两个production-shaped observations出发：per-expert batch不足与output heavy tail；COMBINE直接扩大expert batch，PARTITION/MIGRATE直接利用tail阶段idle GPUs，机制映射清楚。BatchGen*使用SGLang kernels仍取得更强结果，证明主要收益确实来自runtime scheduling而非kernel。但把它称为通用“batch inference architecture”仍偏早：实现与全部主实验都围绕Transformer MoE，dense、VLM、multi-model pipeline只列为future work。

### 假设压力测试

若global batch不足、arrival不持续或SLO要求严格arrival order，scheduler无法等待足够sequence组成`B_moe`。若expert routing极不平衡，扩大global batch未必消除hot-expert straggler。若context很长，KV restore的0.2 ms/sequence/layer会随sequence数和layers累积；若host DRAM/PCIe/RDMA较弱，迁移和offload进入critical path。若tail剩余计算少于5–10秒，`PARTITION`只增加BCT。若模型layers高度异构，代表层plan会选择错误buffer/batch。

### 实验可信度

四个大MoE、offline/RSA/RL、8–128 GPU和单A5000覆盖规模与资源两端；使用SGLang-Optimized而非默认配置，也用BatchGen*隔离kernel贡献，是明显优点。公平性边界是：SGLang/vLLM超过16 GPUs不稳定，故128-GPU不是同构单instance竞争；limited-memory的FlexGen和MoE-Lightning不是原实现，且BatchGen额外CPU attention；production deployment没有trace、availability或长期成本数字。结果多为单个BCT表格，没有run variance、tail SCT、fairness、energy或输出一致性测试。

### 系统性缺陷

event-driven scheduler、host KV single source、module wrappers、custom kernels、Ray control plane和phase-dependent parallelism合计约62K LoC，工程面很大。频繁checkpoint与migration增加partial-copy、cancel、node failure和version consistency风险；虽然系统描述了迁移或recompute恢复，却没有failure injection。oversubscription会让runtime重排requests，tenant isolation、priority、deadline和starvation没有定义。host DRAM容量与pinned/pageable分配、PCIe contention和checkpoint durability也未量化。单instance的all-to-all ceiling意味着上层仍需instance sizing与input partition，并未消除集群层调度。

## 局限与后续工作

- 在dense、VLM、SSM和multi-model generation pipeline上实现不同yield points，验证抽象是否仍优于普通[[Continuous-Batching|continuous batching]]。
- 报告BCT之外的SCT分布、p95/p99、request reorder、tenant fairness与minute-scale SLO violation。
- 对`B_attn/B_moe`、KV长度、PCIe/RDMA带宽和host容量扫参，给出COMBINE/offload的break-even surface。
- 注入GPU/node/network failure，验证in-flight coroutine、host KV checkpoint及“migrate vs recompute”恢复正确性与时间。
- 在线校正单层performance model，处理routing skew、heterogeneous layers、kernel update和shared-cluster interference。
- 比较energy/request、GPU-hour、host-DRAM cost及A5000数百小时任务的实际经济性，而不只报告相对speedup。

## 相关

- **相关概念**：[[Batch-Inference]]、[[Coroutine]]、[[Mixture-of-Experts]]、[[Straggler]]、[[KV-Cache]]
- **相关系统**：[[SGLang]]、[[vLLM]]
- **同会议**：[[OSDI-2026]]
