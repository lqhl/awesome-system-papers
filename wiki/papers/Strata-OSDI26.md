---
type: paper
name: Strata
full_title: "Strata: Hierarchical Context Caching for Long Context Language Model Serving"
authors: [Zhiqiang Xie, Ziyi Xu, Mark Zhao, Yuwei An, Vikram Sharma Mailthody, Scott Mahlke, Michael Garland, Christos Kozyrakis]
venue: OSDI
year: 2026
tags: [llm-serving, kv-cache, storage-hierarchy, gpu-assisted-io, cache-aware-scheduling]
source_pdf: "[[osdi26-xie-zhiqiang.pdf]]"
source_md: "[[osdi26-xie-zhiqiang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Strata：面向长上下文 LLM 服务的分层上下文缓存（OSDI 2026）

> **原题**：Strata: Hierarchical Context Caching for Long Context Language Model Serving

> **一句话总结**：Strata把分层 [[KV-Cache]] 的问题从“慢层有没有命中”改成“命中的数据何时能真正供GPU使用”：用少量GPU线程并行搬运几千个碎片页面，并在搬运时把host/storage的page-first布局转换成GPU计算需要的layer-first布局；调度器再推迟delay hit、平衡load/compute并用decode填I/O气泡。H200长上下文评测中，它在相同平均TTFT下相对vLLM-LMCache最高提升5倍吞吐，相对TensorRT-LLM-HiCache最高3.75倍。

## 问题与动机

长上下文 [[LLM-Inference|LLM 推理]]应用会反复查询文档、对话历史或agent memory。若每次都重新prefill几十万tokens，计算代价很高；prefix/context caching保存已有K/V状态，只计算新增tokens。但GPU HBM容量有限，例如论文估算40 GB只能容纳Llama-8B约0.3M tokens的KV，生产系统因此把缓存扩到CPU DRAM、SSD或remote memory（§1–§2）。

“CPU/SSD里命中”并不等于请求能立即执行。[[PagedAttention]] 为减少GPU碎片使用1–32-token小页，一个context的KV又按layer散落成大量非连续片段。逐页调用`cudaMemcpyAsync`时，每次只有几KB，启动和driver延迟占主导；8192-token KV在PCIe 5.0上只达到理论带宽约22%，在更快的Grace-Hopper互连上反而只有约5%（§3.1、图 3）。

简单增大page也不行。ShareGPT+Mistral-24B实验把page从1增到512 tokens时，cache match粒度变粗，average TTFT最高约2倍、P90最高2.9倍。真正需要的是“小逻辑页用于命中，大物理并发用于传输”，而不是在cache hit rate与I/O bandwidth中二选一（§3.1、图 2）。

第二个问题是调度。layer-wise prefill只能在算第N层时加载N+1层；当历史cache很长、新query很短，load time大于compute time，即使I/O达到PCIe理论带宽的75%，仍有最高24%的prefill时间停在等待。相同context的多个请求若在第一次cache miss完成前同时到达，还会发生延迟命中（delay hit）：后来的请求本应命中，却重复计算同一长prefix（§1、§3.2）。

## 关键观察 / 隐含假设

- **观察 1：碎片I/O需要提高并发度，不必放大cache page。** GPU可让数千threads各搬128-byte片段，聚合利用host-GPU链路；逻辑page仍可保持1 token以维持细粒度prefix match（§3.1、§4.2）。
  - **代价假设**：搬运kernel会占SM、register和cache。两block配置在H200达到48 GB/s，但并发prefill下降少于5%、decode少于10%；它不是“免费DMA”（§4.2、图 5）。
- **观察 2：GPU计算布局与慢层传输布局不必相同。** GPU使用layer-first，使每层[[Attention|attention]]读连续K/V；host/SSD使用page-first，使一个page跨所有layers形成大连续块。I/O kernel只多算一次destination offset即可在线转置（§4.2.1、图 6）。
  - **依赖假设**：转换是规则重排，offset算术相对搬运很小；不同attention/KV layout或压缩编码可能需要新kernel。
- **观察 3：CPU↔GPU bandwidth应像HBM和compute一样成为scheduler的一等资源。** batch不能只按FIFO/token budget组成，还要让新增token计算时间覆盖已命中历史KV的load time（§3.2、§4.3.2）。
  - **依赖假设**：每请求的load tokens与compute tokens可从HiRadixTree准确估算，hardware/model的loading-bound阈值可离线profile。
- **观察 4：cache miss是有持续时间的状态，而非一个瞬时事件。** [[Mooncake|Mooncake]] tool-agent trace中，38%请求与一秒内另一请求共享至少6K tokens；异步scheduler会把整个batch执行时间都变成miss resolution window（§3.2）。
  - **代价假设**：推迟匹配in-flight prefix的请求可省重复prefill，却会增加个体等待。论文只用100 matched tokens阈值和队首优先缓解，没有SLO/fairness保证。
- **观察 5：load [[PCIe|PCIe]]与decode主要使用不同瓶颈。** loading饱和PCIe，decode主要饱和HBM，因此loading-bound prefill等待时插入decode batch可填bubble，且资源冲突相对有限（§4.3.3、图 7）。
  - **可能失效场景**：GPU I/O kernel仍占SM；大decode batch、attention-heavy decode或统一内存平台可能让两者竞争更强。
- **观察 6：cache distance决定优化重点。** 相似请求紧邻时delay-hit deferral最有用；距离大时CPU命中更多、GPU I/O和balanced batch更重要（§5.3.3、图 11）。
- **假设 1：目标是prefill-dominated的long-context reuse。** 低复用、single-turn、长generation或主要使用sparse/linear attention的服务不在核心覆盖范围（§3、§6）。

## 核心方法

### 数据面：GPU-assisted I/O与分层布局

Strata在SGLang内加入Cache Controller，管理GPU HBM、CPU pinned DRAM和external storage；HiRadixTree把token-prefix节点扩展为页表，记录每页的GPU/CPU index、命中次数和状态。scheduler选出batch后发起load，GPU executor逐层用CUDA events等待对应KV就绪；新产生的KV异步备份到慢层（§4.1、图 4）。

CPU↔GPU loading不提交许多小`cudaMemcpyAsync`，而是启动I/O CUDA kernel：大量threads从registered host memory读取小chunk，经register写到GPU global memory。为降低干扰，kernel只用少量大blocks并用cache-bypass instruction；默认host→GPU为2个1024-thread blocks，GPU→host backup为1个block。H200 microbenchmark中，2 blocks约48 GB/s，继续加blocks带宽几乎不增，却明显压低prefill/decode（§4.2、图 5）。

重排能力让GPU保持layer-first、host和disk保持page-first。一个逻辑page在GPU可分散到L个layer spans，写出时由threads聚成一个连续host page；加载时反向scatter。cache matching仍按小page进行，慢层I/O却能读写连续大block（§4.2.1、图 6）。

SSD命中后，Cache Controller在请求排队时机会prefetch到DRAM；默认best-effort策略在请求被选中时停止未完成prefetch，使用当时已有的GPU/host cache。也可配置等待完成或timeout。这个路径只把storage latency与queue delay重叠，不保证SSD数据在执行前全部到位（§4.2.1）。

### 控制面：三阶段cache-aware scheduling

**第一阶段处理delay hit。** HiRadixTree加入transient nodes：`in-queue`表示新context已在等待，`in-flight`表示正在计算。新请求若匹配超过默认100 tokens的transient prefix，就推迟到下一round并放到waiting queue前部；原请求完成后，transient node才变成带memory index的普通cache node（§4.3.1、图 7）。

**第二阶段形成balanced batch。** scheduler从队首请求开始，以aggregate loaded tokens/new compute tokens估算batch是否loading-bound，默认临界ratio为100。会使ratio超标的请求暂存到deprioritized list，同时优先加入与已选context共享一次load的bundle hit；若batch最后没满再补回。每轮强制从原队首开始且保留deprioritized顺序，避免永久starvation（§4.3.2、算法 1）。

**第三阶段填I/O bubble。** 若batch仍loading-bound，executor暂缓prefill，在KV加载期间先运行已经准备好的decode batch。Strata沿用SGLang的prefill/decode co-location与[[Continuous-Batching|continuous batching]]：同一GPU按时间交替prefill和decode，不是物理P/D分离（§4.1、§4.3.3）。

### 写入与淘汰策略

Cache Controller提供write-back（将被GPU淘汰时才备份）、write-through（每次产生KV即备份）和默认selective write-through。后者给HiRadixTree node计访问次数，超过阈值才备份；默认阈值2，设为1等价write-through。各层默认LRU淘汰。策略显式暴露写带宽、持久性、容量和未来复用之间的取舍（§4.4）。

## 设计取舍

- **GPU线程搬数据换DMA碎片开销**：小page可饱和链路；I/O kernel与模型kernel竞争SM/register/cache，配置必须按GPU调优。
- **布局解耦换双向重排kernel**：GPU计算与SSD传输都连续；KV格式、tensor parallel layout变化会增加实现维护。
- **推迟delay hit换个体TTFT**：避免同prefix重复prefill；同一请求可能因前序长miss等待更久，aggregate throughput与公平性冲突。
- **重排FIFO换更平衡的batch**：load/compute更匹配；请求顺序不再严格FIFO，只用“每批从队首开始”防饿死。
- **decode填bubble换prefill-first语义**：提高总利用率；decode与I/O并非完全独立，重负载下仍可能干扰。
- **机会式SSD prefetch换可预测性**：利用queue delay且不阻塞；SSD抖动或短queue时只能拿到部分cache，命中收益不稳定。
- **精确prefix caching换模型覆盖**：不改变模型输出；dense KV假设难直接适配sparse、linear或hybrid attention。

## 实验与结果

- **平台、模型与基线**：主测试节点有8×H200、Sapphire Rapids CPU和1.6 TB DRAM，每GPU经PCIe 5.0 x16连接CPU；8B/14B用单GPU，Llama-70B用4-GPU tensor parallel。另测8×H20+Intel P5510 [[NVMe|NVMe]]（读约7 GB/s）和单GH200。基线为vLLM 0.8.5+LMCache 0.2.1、TensorRT-LLM 0.17 HiCache、SGLang 0.4.5及作者实现的SGLang-HiCache；各系统page size不同：Strata/SGLang为1，其他hierarchical基线为32（§5.1）。
- **工作负载与指标**：LooGLE、NarrativeQA代表重复文档问答，ReviewMT代表长上下文多agent会话，ShareGPT代表短上下文；arrival用Poisson模拟，in-flight上限128，CPU cache通常给1 TB。指标是average TTFT和output-token throughput，不含p95/p99；“倍数”来自throughput–average-TTFT曲线上相同TTFT的比较（§5.1–§5.2、表 1）。
- **长上下文端到端**：LooGLE上，Llama-8B相对SGLang-HiCache/vLLM-LMCache/TRT-LLM-HiCache最高为3.2/2.6/1.9倍，Qwen-14B为3.9/2.1/1.9倍，Llama-70B为5/5/3.75倍。ReviewMT的8B对应1.7/2.3/2.3倍。长context系统约达95% cache hit；headline的5倍与3.75倍来自特定70B workload/curve点，不是所有模型平均值（§5.2.1、图 8）。
- **warm cache与短上下文**：NarrativeQA先预计算全部CPU KV并清空GPU后，Strata相对vLLM-LMCache在8B/14B/70B分别最高2.3/2.6/2.5倍；TRT-LLM不支持prewarm而未参评。ShareGPT上Strata与主流系统大致相当，但底层SGLang在8B/70B本就略慢，论文只证明“没有明显额外退化”，不是全面最快（§5.2.2–§5.2.3、图 8）。
- **组件与cache-distance消融**：在Qwen-14B+LooGLE上，只加scheduler和只加GPU I/O，峰值吞吐分别最高1.8和2.3倍于SGLang-HiCache。min-distance时delay-hit mitigation增加42%；shuffle/max-distance时I/O增加76%/95%，balanced batch再加11%/12%，stall hiding再加8%/3%。这些是按阶段累加的相对贡献，不能简单相加成总speedup（§5.3.1、§5.3.3、图 9、11）。
- **page、SSD layout与新互连**：SGLang-HiCache即使把page调到最佳512，也只有Strata-IO吞吐的93%，且cache hit低2.4%。8×H20+DeepSeek-V3、12 req/s时，page-first SSD layout把average TTFT从5.03降到2.42秒（2.1倍），throughput从27.43升到36.41 token/s（1.3倍）。GH200上，传统copy从PCIe机10.8升到19.43 GB/s，Strata-IO从40.3升到150.5 GB/s，说明软件并发决定能否利用更快互连（§5.3.2、§5.3.5、§5.4、图 10、13–15）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| GPU-assisted I/O解决小page带宽不足 | 2 blocks在H200约48 GB/s；Strata-IO峰值吞吐最高为HiCache 2.3倍（图 5、9） | pinned CPU memory、特定CUDA/GPU；decode干扰可达约10% | 强（该平台） |
| I/O与scheduler必须协同 | scheduler-only最高1.8倍、I/O-only最高2.3倍，完整Strata在高负载保持更好曲线（图 9） | 单个Qwen-14B+LooGLE消融；无完整交互factorial test | 中到强 |
| Strata显著提高长上下文服务吞吐 | 相同average TTFT下，vLLM-LMCache最高5倍、TRT-LLM-HiCache最高3.75倍（图 8） | 峰值来自70B特定工作负载；Poisson合成arrival、平均TTFT | 强（评测条件内） |
| page-first慢层布局有实际SSD收益 | H20-storage上TTFT 5.03→2.42秒，throughput 27.43→36.41 token/s（图 13） | 单模型、单NVMe、固定12 req/s，基线已用page 32 | 强（该点） |
| 更快host-GPU硬件仍需要I/O软件 | GH200上传统copy 19.43 GB/s，Strata-IO 150.5 GB/s并接近oracle TTFT曲线（图 14–15） | 单GH200、Llama-8B+LooGLE；oracle只模拟无限带宽 | 中到强 |

## 批判性分析

### 论证链条

论文把“cache hit”拆成命中位置、传输完成时间和同时到达状态，问题定义比只追求hit rate更完整。小page的命中/I/O冲突由图2–3实证，GPU-assisted I/O处理数据面，三阶段scheduler处理控制面，消融也显示二者各自有效。较弱的外推是“deployed in production”：正文只说已在若干领先AI公司部署，没有production trace、故障率、SLO达成率或线上ablation；所有定量结论仍来自benchmark。

### 假设压力测试

若请求几乎不复用prefix，CPU/SSD cache写入和HiRadixTree管理只增加开销，Strata会退化到底层SGLang。若generation远长于prefill，搬历史KV不再是主项，decode填bubble也没有足够prefill bubble。若GPU已被compute占满，I/O kernel的SM竞争可能大于图5；若host memory未pin、[[NUMA|NUMA]]跨socket或remote cache经NIC访问，48 GB/s结果不能照搬。若arrival很稀疏，delay hit少且queue短，deferral/balanced batching的重排空间变小。若相同prefix请求持续洪泛，队首优先仍可能让其他租户的请求长期处于不利位置。

### 实验可信度

三种模型规模、四类数据、三种硬件、多个成熟hierarchical cache基线、warm-cache/short-context/SSD/GH200实验，覆盖面较好；版本、page size、CPU cache额度和arrival方法也披露清楚。限制是主要指标只有average TTFT和吞吐，没有P90/P99、每请求SLO或公平性；到达时间并非真实trace而是Poisson模拟，Mooncake delay-hit图又是unlimited-cache simulator而非实机。不同engine有不同base kernel与默认GPU memory policy，page size也不一致，尽管符合各自惯例，仍不完全隔离cache机制。大多数端到端实验不用SSD，disk结论只来自单独一点。

### 系统性缺陷

GPU-assisted I/O把原本由DMA engine承担的工作移到通用SM，会与未来更compute-heavy的模型争资源，并需要为NVIDIA/AMD、KV dtype、[[Tensor-Parallelism|TP]] layout分别维护kernel。scheduler用profile得到的固定load/compute threshold 100，硬件共享、模型切换、thermal throttling或SSD抖动时可能失准。HiRadixTree同时承担prefix index、页表、transient状态和访问计数，成为并发一致性与恢复复杂点；论文没有讨论controller/scheduler crash、in-flight node清理或cache metadata重建。cache write/eviction只有策略描述，没有写放大、SSD寿命、capacity partition和多租户隔离结果。系统仍是单compute-instance方案，跨节点cache pool与全局调度只是未来集成方向。

## 局限与后续工作

- 在真实线上arrival trace上报告per-request TTFT的p50/p95/p99、SLO violation、deferral次数与tenant fairness，而不只看average curve。
- 联合扫I/O blocks、prefill/decode batch、load/compute threshold和GPU利用率，做在线反馈控制以适配模型与硬件变化。
- 对CPU NUMA、unpinned/remote memory、多个NVMe、SSD queue depth和network KV pool分别测试layout与prefetch策略。
- 测write-back/write-through/selective策略的hit rate、write bytes、SSD寿命、eviction stall和crash durability。
- 注入scheduler/cache-controller/GPU process故障，验证transient nodes、in-flight transfer和半写入cache的恢复语义。
- 扩展sparse、linear与hybrid attention，并说明page match、layout transform和load-cost model如何变化。
- 与支持同样prewarm、相同page size和相同底层kernel的基线做controlled comparison，进一步隔离engine差异。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Hierarchical-KV-Cache]]、[[Prefix-Caching]]
- **相关系统**：[[SGLang]]、[[vLLM]]、[[TensorRT-LLM]]、[[LMCache]]
- **同会议**：[[OSDI-2026]]
