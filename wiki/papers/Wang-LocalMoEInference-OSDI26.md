---
type: paper
name: Wang-LocalMoEInference
full_title: "Achieving Cloud-Grade SLOs for Local Mixture-of-Experts Inference through CPU–GPU Hybrid Design"
authors: [Wenxin Wang, Yule Hou, Yu Ji, Peng Qu, Youhui Zhang]
venue: OSDI
year: 2026
tags: [llm-serving, mixture-of-experts, cpu-gpu, local-inference, expert-parallelism]
source_pdf: "[[osdi26-wang-wenxin.pdf]]"
source_md: "[[osdi26-wang-wenxin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用 CPU–GPU 混合设计让本地 MoE 达到云端响应目标（OSDI 2026）

> **原题**：Achieving Cloud-Grade SLOs for Local Mixture-of-Experts Inference through CPU–GPU Hybrid Design

> **一句话总结**：这项工作不是把整模型塞进消费级 GPU，而是让约 1 TB 原生 FP8 MoE 权重留在双路 CPU 的 DRAM：长 prefill 把专家权重流式送入 1–2 张 RTX 5090，decode 则直接在 CPU 上读稀疏激活的专家。配合 SmallEP、节点内 prefill/decode 分离和 AVX-512 FP8 GEMV，DeepSeek-R1 671B 的单流 FP8 decode 达 21.5 token/s，双 GPU 可让约 45K-token prompt 的 TTFT 控制在论文定义的 30 秒目标内。

## 问题与动机

大 MoE 每个 token 只激活少数专家，所以本地低并发推理不必在每一步读取全部参数。已有 CPU–GPU 混合系统据此把 attention、shared expert 等稠密部分放 GPU，把 routed experts 留在容量更大但带宽更低的 CPU DRAM。不过，KTransformers 等系统仍有四个差距：常依赖 INT4、蒸馏或改 routing；长 prompt 的 CPU prefill 很慢；单请求 decode 低于论文采用的 20 token/s 响应基线；prefill 与 decode 或多条 decode 同时到来时，延迟明显恶化（§1–§2.2）。

论文把“cloud-grade”具体化为两个本地交互目标：长 prompt 的 TTFT 不超过 30 秒、单请求 decode 至少约 20 token/s。它没有声称复现云服务的可用性、tail SLO、多租户隔离或弹性扩缩容。目标平台也不是普通桌面机，而是一台双路服务器 CPU、1.15 TB DDR5、1–2 张消费级 GPU 的单节点（§3、§4.1）。

核心矛盾是 prefill 与 decode 需要不同执行方式。长 prefill 是高算术强度 GEMM，适合 GPU，但完整模型放不进 VRAM；小 batch decode 是带宽受限的 GEMV，只访问被路由到的专家，适合大容量、多通道 CPU DRAM。系统因此不追求一条统一 offload 路径，而是按阶段重新组织权重和计算（§2.2）。

## 关键观察 / 隐含假设

- **观察 1：长 prefill 应搬权重到 GPU 算，而不是让 CPU 持续算专家。** 当 prompt 超过约 512 tokens，CPU [[MoE|MoE]] GEMM逐渐成为 TTFT 主项；GPU 即使反复接收权重，长序列上的计算也足以隐藏传输（§2.2.2、§3.1）。
  - **依赖假设**：prompt 足够长且 [[PCIe|PCIe]] 传输可与计算重叠。4K 及以下，stream setup 与搬权重反而使 SLP 没有优势。
- **观察 2：有限 VRAM 只需容纳“正在执行和即将执行”的权重。** loader、model、unloader 三条线程/stream用 ON/OFF event在 sub-layer 粒度流水；expert ring buffer重复利用显存槽位，无须对 DeepSeek-V3 的约 44.5K 个 expert tensors反复 `cudaMalloc/free`（§3.1、图 5）。
  - **依赖假设**：模型权重在推理时不变，host DRAM可保留权威副本；若模型本身放不进主存，这条路径不成立。
- **观察 3：云端的大规模 expert parallelism 不适合只有两张、且无 P2P 的本地 GPU。** 标准 EP=2 的 dispatch/combine在20K prefill单层中占约31%时间；SmallEP先复制 token，再本地 routing和局部归约，在 EP size 不大于每 token 激活专家数时减少峰值链路流量（§2.2.3、§3.2、图 3、图 6）。
  - **依赖假设**：EP规模很小，重复 gating/sorting的成本低；若 GPU很多或高速互连可用，标准 EP的分散通信可能更合适。
- **观察 4：decode 时 CPU 与 GPU轮流空闲，可用两条请求填补彼此空洞。** 每层 [[Attention|attention]]约350 µs、MoE约450 µs；dual-batch让请求 A 的 GPU attention与请求 B 的 CPU MoE重叠，而不是把两条请求的所有专家合成一个更宽、更吃 DRAM带宽的 batch（§3.3.1、图 7）。
  - **依赖假设**：attention与MoE耗时接近，且只有小规模并发；更大 batch仍会扩大激活专家集合和内存流量。
- **观察 5：[[Quantization|FP8]]权重可保持压缩存储，在寄存器内转成 BF16做 dot product。** CPU没有原生 FP8矩阵指令；post-scaling kernel先把 E4M3FN位模式展开成 BF16，完成 `vdpbf16ps` 累加后按128-element scale block统一缩放，避免在hot path物化FP32或完整BF16权重（§3.4、图 9–10）。
  - **依赖假设**：目标 CPU支持所需 AVX-512/BF16指令与高 DRAM带宽；“原生 FP8”指原模型权重格式和专用kernel，并非CPU硬件直接执行 FP8 MAC。
- **假设 1：20 token/s 与 30 秒 TTFT 足以代表云端体验。** 这是论文引用的响应目标，但没有生产 trace、p99、排队、公平性或可用性数据支撑更广义的“cloud-grade”（§1、§4）。

## 核心方法

### SLP：用显存环形缓冲流式执行长 prefill

Stream-Loading Prefill（SLP）把 prefill 完全放到 GPU。loader 提前从 DRAM 把 attention 或下一个 expert 权重装入 GPU并发出 ON event；model stream 等待权重就绪后执行，结束后发出 OFF event；unloader收到 OFF后释放普通 tensor，或直接复用 expert ring-buffer slot。对于短 prompt，ring buffer可覆盖整层专家以拉长预取距离；超过约50K tokens、计算成为主项后，可缩到两个 ping-pong slot以给 activation腾显存（§3.1、图 5）。

系统按长度切换路径：256–2K时 CPU AMX/AVX更有利，默认到4K仍走 AVX FP8，超过4K才使用 SLP/DSLP。这个切换是“流式加载适合长上下文”的必要条件，不是对所有 prefill都更快（§4.2、图 13–14）。

### DSLP 与 SmallEP：为两张 PCIe GPU重写通信

Distributed SLP（DSLP）将 zig-zag StripedAttention 的 context parallelism与 expert parallelism结合。SmallEP不先把每个 token 的每条 expert route分别 dispatch：两张 GPU先 All-Gather得到完整 `[N,D]` tokens，各自本地 gate/sort并只计算所拥有专家，再把所有本地专家的结果先归约成 `[N,D]` partial sum，最后 All-to-All并完成归约（§3.2、图 6）。

代价是每张 GPU都重复 gating和sorting，并保留完整 token batch；论文测得这部分每层少于10 ms、低于5%。在20K-token单层 microbenchmark中，CP2+EP2比单 GPU低21% latency；SmallEP再比标准 EP低18%，整体 DSLP吞吐为单 GPU SLP的1.64倍（§2.2.3、图 3）。

### 两种并发：dual-batch 与节点内 P/D 分离

dual-batch用两条 host thread和 CUDA stream交错两个 microbatches，让 GPU attention与 CPU专家计算同时进行。节点内 [[Disaggregation|prefill-decode disaggregation]]则把一张 GPU给长 prefill，另一张给 decode/短 [[Chunked-Prefill|chunked prefill]]；两个process共享一份 DRAM权重，SLP ring buffer负责无额外 host copy的访问，避免为 P/D各存一份约TB级模型（§3.3）。

调度策略是：少于约2K的请求走 chunked prefill；长请求在近期没有 decode时用两 GPU DSLP，否则用单 GPU SLP与decode分离。prefill按 FCFS，decode动态batch到目标上限（例子为6）。因此“P/D分离”需要两张 GPU，也会在 decode繁忙时放弃 DSLP的最高 prefill吞吐（§3.3.2）。

### CPU 解码后端（decode backend）

FP8 kernel沿输出维度切 tile、沿 K维度按128-element scale block迭代，并把缩放延迟到一个block的局部点积结束后，减少4倍 scaling multiply；最终达到947 GB/s。MoE执行再按 NUMA node、expert和输出片段分任务：gate/up并行，每个expert只在进入down projection前做局部barrier。INT4路径把activation conversion和SiLU/aggregation相关转换融进前后projection，使每层只保留两次global barrier（§3.4–§3.5、图 10–12）。

## 设计取舍

- **阶段专用路径换调度复杂度**：短 prefill用CPU、长 prefill用SLP/DSLP、decode又回CPU专家；runtime必须按长度和并发状态选路径。
- **DRAM容量与带宽换GPU VRAM**：完整FP8权重可留在1.15 TB DRAM；低通道数、单socket机器的decode预计随有效DRAM带宽近似线性下降（§6）。
- **显式权重流水换实现简单性**：loader/model/unloader和每个module的events提供可预测显存；也引入ring-buffer sizing、生命周期和同步错误风险。
- **SmallEP减少PCIe流量换重复计算和token副本**：只在小EP、激活expert数不少于EP size时有理论优势。
- **双GPU分离换最高prefill速度**：并发decode存在时，一张GPU被保留给decode，长prefill不能同时使用完整DSLP。
- **native-format FP8换特定CPU依赖**：避免二次INT4量化并保留模型发布格式；性能依赖AVX-512/BF16和高带宽NUMA平台，不能直接外推到普通PC。

## 实验与结果

- **平台、模型和基线**：主机为2× AMD EPYC 9355、24条48 GB DDR5-6400（总1.15 TB、理论1228 GB/s）和2× RTX 5090 32 GB；模型为原始FP8 DeepSeek-R1 671B、Kimi-K2 1T及Q4_K_M DeepSeek-R1。多数本地基线在同机测试，但 KTransformers公开的AMX prefill来自另一平台；其超过8K的结果是线性外推，不是实测（§4.1–§4.2、图 13–14）。
- **长 prefill**：FP8 SLP在20K附近约1,200 token/s，双卡DSLP在32K附近超过1,800 token/s；20K–32K范围，SLP比同机AVX快一个数量级以上，比“估算的”KT AMX快2.8倍，DSLP又是SLP的1.64倍。SLP/DSLP让4K–32K均低于30秒TTFT，摘要进一步报告单卡支持约32K、双卡约45K prompt/30秒；4K及以下不占优（§4.2、图 13–14）。
- **原始FP8 decode与小并发**：DeepSeek-R1短context单流21.5 token/s，到32K仍约20；Kimi-K2单流22.4。两条等长请求的总吞吐33.6 token/s，32K时31.1，即每请求约16。batch size 2时本系统每请求从21.5降到16.8（下降21.7%），KT INT4从22.7降到13.6（下降40%）；不过两系统模型精度不同（§4.3、图 15–16）。
- **INT4 decode基线**：同一Q4_K_M DeepSeek-R1上，本系统在1K–8K维持28 token/s，对 KTransformers约22、ik_llama.cpp约14；到128K仍19，而KT约15。Q4_K_M只需404 GB RAM，但这是量化模型结果，不能用来证明FP8模型在低内存机器上也能运行（§4.4、图 17）。
- **并发干扰**：为让单独请求都持续约20秒，KT用4K INT4 prefill，本系统用24K FP8 prefill，所以图18适合比较归一化干扰，不是同一请求的绝对延迟。1P+2D时本系统TTFT增加18%；所有混合负载中TPOT最多变为1.54倍、总完成时间最多1.67倍，KT分别为2.45倍与2.53倍。摘要的“少于15% latency increase”不能概括最重的1P+2D场景（§4.5、图 18）。
- **kernel与质量**：真实MoE形状上，优化FP8 GEMV为15.5 µs、947 GB/s，标准版本21.7 µs、678 GB/s，并比OpenBLAS/AOCL的FP32/BF16 kernel低4–5倍latency；datatype不同使它不是严格同精度kernel对比。MMLU-Redux/Pro上，DeepSeek-V3.1和Kimi-K2-Instruct相对官方Exact Match低0.29–1.17个百分点，最大差值约1.17个百分点；只测两个任务且生成配置不完全一致（§4.6–§4.7、表 1–2）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 流式加载能让有限VRAM执行原始FP8大MoE的长prefill | 20K–32K时SLP约比AVX快一个数量级以上；单卡约32K prompt低于30秒TTFT（图 13–14） | 双路1.15 TB DRAM+RTX 5090；短prompt无优势，KT长序列数值含外推 | 强（该平台长context） |
| SmallEP适合本地两卡PCIe环境 | 20K单层比标准EP再低18% latency，DSLP为SLP吞吐1.64倍（图 3、§3.2） | EP=2、无GPU P2P；没有多GPU/不同top-k sweep | 强（测量点内） |
| 原始FP8模型可达到论文采用的20 token/s响应线 | DeepSeek-R1单流21.5、32K约20；Kimi-K2为22.4 token/s（图 15） | 高带宽双路EPYC；平均throughput而非p99 TPOT | 强（该节点） |
| 并发机制比KT更能控制相对干扰 | TPOT最坏1.54倍对2.45倍，总时间1.67倍对2.53倍（图 18） | prompt长度与precision故意不同，只比较归一化干扰 | 中 |
| 系统保留官方模型质量 | 两模型、两个MMLU变体的EM比官方值低0.29–1.17个百分点（表 2） | 非同generation config，覆盖面窄，无长context质量测试 | 中 |

## 批判性分析

### 论证链条

论文先把本地MoE拆成四个可测差距，再为prefill、decode和两类并发分别提供机制，组件与目标对应清楚。SLP证明“有限VRAM不等于prefill必须在CPU”，SmallEP也确实从小EP的通信公式推导设计。较弱的一步是把两个平均响应阈值上升为“cloud-grade”：实验没有queueing tail、admission control、multi-tenant fairness、failure、availability、cost/token或energy/token；它证明的是昂贵单节点上的云端风格交互速度。

### 假设压力测试

若DRAM从24 channels降到桌面级2–4 channels，论文自己预计占decode约60%的CPU MoE会随带宽近似线性变慢，很可能跌破20 token/s。若GPU VRAM不足以放11.3–16.9 GB的单卡expert ring buffer（DSLP每卡约5.6–8.5 GB），16K等中长prompt的传输/计算重叠会变差。若PCIe更慢、NUMA placement错误或decode数量增多，SLP权重传输与decode专家读取会争同一DRAM；图18已在1P+2D看到18% TTFT上升。若EP size大于激活expert数，SmallEP的通信优势不再由论文推导保证。

### 实验可信度

实验覆盖FP8/INT4、两种大MoE、prefill长度、decode context、batch、P/D混合、kernel microbenchmark和两个质量任务，组件闭环较完整，也明确披露KT AMX长序列为估算。主要公平性问题有三处：KT公开AMX prefill来自不同机器；并发图用4K INT4对24K FP8来等化单独运行时间；图16用本系统FP8对KT INT4比较batch scaling。所有主结果集中在一台极高DRAM容量/带宽、最新GPU的节点，没有重复试验方差、p95/p99、功耗或成本数据。

### 系统性缺陷

系统依赖一组彼此耦合的专用优化，而非一个自动适配的通用抽象：长度阈值、ring-buffer大小、DSLP/分离选择、decode batch上限、NUMA任务切分都需针对模型和硬件调优。节点内P/D分离仍共享DRAM与PCIe，不能提供真正资源隔离。完整模型需约TB级主存，双路EPYC和两张5090的价格、功耗、散热与可维护性未量化。FP8 kernel依赖新CPU指令；不同FP8 scale格式、routing top-k、expert shape或dense/hybrid模型可能要重写。最后，论文没有讨论多用户KV管理、请求取消、OOM恢复、GPU故障或持续服务升级。

## 局限与后续工作

- 在单socket、桌面DDR5、不同EPYC/Xeon代际、PCIe 4.0及16/24 GB GPU上画出TTFT/TPS随DRAM带宽、VRAM ring buffer和PCIe带宽的退化曲线。
- 报告TTFT/TPOT的p50/p95/p99、真实到达trace、排队与admission control，并加入3–10条并发decode和长prefill burst。
- 对同一precision、同一prompt和同一机器比较KTransformers等基线；把公开实测、同机实测和外推值在图表中严格分开。
- 测端到端energy/token、整机成本、内存成本和闲置功耗，再讨论相对云端租用或GPU supernode的成本优势。
- 自动profile并选择AVX/SLP/DSLP/P-D分离、ring-buffer长度和batch上限，同时给出SLO违约时的回退策略。
- 扩展不同MoE routing、FP8/FP4 scale格式和模型结构，并在长context推理、代码、数学任务上验证质量。

## 相关

- **相关概念**：[[Mixture-of-Experts]]、[[Prefill-Decode-Disaggregation]]、[[Expert-Parallelism]]、[[CPU-GPU-Offloading]]、[[NUMA]]
- **相关系统**：[[DeepSeek-V3]]、[[KTransformers]]
- **同会议**：[[OSDI-2026]]
