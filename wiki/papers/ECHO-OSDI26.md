---
type: paper
name: ECHO
full_title: "ECHO: Efficient KV Cache Offloading with Lossless Prefetching for Serving Native Sparse Attention LLMs"
authors: [Guangda Liu, Wenhao Chen, Chengwei Li, Zhenyu Ning, Jing Lin, Yiwu Yao, Quan Chen, Shixuan Sun, Jieru Zhao, Minyi Guo]
venue: OSDI
year: 2026
tags: [llm-serving, kv-cache, sparse-attention, offloading, prefetching]
source_pdf: "[[osdi26-liu-guangda.pdf]]"
source_md: "[[osdi26-liu-guangda]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 原生稀疏注意力模型的 KV Cache 卸载（OSDI 2026）

> **原题**：ECHO: Efficient KV Cache Offloading with Lossless Prefetching for Serving Native Sparse Attention LLMs

> **一句话总结**：ECHO 把原生 [[Sparse-Attention|稀疏注意力]]模型的完整 [[KV-Cache]] 放到 host DRAM，只在 GPU 保留被选 token 的缓存，并把 allocate、free、recall 全部做成可被 [[CUDA-Graph]] 捕获的 GPU 操作；在单台 8×H20 上，它借助 1.8M-token、约 1000 GB 的 host pool 把 InfiniteBench 固定输出吞吐最高提高到 [[SGLang]] 的 2.15 倍、[[vLLM]] 的 4.1 倍，但“无损”只表示预取不会改变最终 exact top-k，主要吞吐收益来自更大并发，而 intra-query prefetch 的端到端贡献最高只有 4%。

## 问题与动机

原生稀疏注意力（native sparse attention）在训练阶段就学会先用轻量 indexer 选择 top-k token，再只对这些 token 做真正 attention。它避免了 training-free pruning 常见的额外精度损失，也把 attention 计算和读取量从随上下文平方增长降到更接近 `O(Lk)`（§1、§2.2）。

但稀疏计算没有消灭历史缓存。DeepSeek Sparse Attention（DSA）仍要保留 MLA latent KV，还多了一份 indexer K cache，所以总缓存继续随上下文线性增长。论文估算 DeepSeek-V3.2 在 8×H20/H200 上虽然总共可容纳约 4.1M/5.2M token，但 MLA 采用 DP，不能把一个 worker 的 KV cache 用 [[Tensor-Parallelism|TP]] 切开，每个 DP worker 只剩约 511K/655K token；真实 SGLang 8×H20 部署还因 graph metadata 等开销只容纳约 380K。100K-token 请求因此每个 worker 只能并发 3–4 个，稀疏 kernel 又需要比 dense kernel 更大的 batch 才能吃满 GPU（图 1–2、§2.4）。

把 KV cache 放到 host DRAM 可以扩大并发，但已有方案有两个问题：

- **动态管理破坏 graph execution。** 每层、每步都会驱逐和召回不同 token。现有 allocator 用动态 tensor slice/concat 和 CPU 控制，不能完整放进 CUDA Graph；而 DeepSeek-V3.2 的 kernel 更多，关掉 graph 会让吞吐下降约 1.5 倍（图 3）。
- **PCIe recall 太慢。** 必须先算完所有 index score 才知道 exact top-k，再从 host 拉入缺失 KV，indexer、recall、attention 串行执行。按上一层或上一步相似性猜 token 虽可预取，却可能漏掉真正 top-k，进一步改变模型输出。

ECHO 因此把问题分为两部分：让动态 cache manager 完全 graph-friendly，再利用 index score 的数值规律提前搬一部分 KV，但在 attention 前仍补齐 exact top-k。

## 关键观察 / 隐含假设

- **观察 1：HBM 容量，而不是稀疏 [[Attention|attention]] 算力，是长上下文并发的第一道上限。** 图 2 中 64K context、batch 8 的 sparse FlashMLA 只有 53% utilization；如果 host pool 能让有效 batch 增大，吞吐还有明显空间（§2.4）。
  - **依赖假设**：请求足够长且到达率足够高，能填满扩大的 batch。短请求或低负载下，offload 只增加管理和传输延迟。
- **观察 2：cache metadata 可以全部变成固定长度 GPU tensor。** GPU/host slot 映射、free bitmap、priority 和 output buffer 都预先分配，allocate/free 用 atomic、argtopk 和 scatter 并行更新，不创建 variable-length tensor（§4）。
  - **依赖假设**：每层 metadata 扫描与 `argtopk` 的成本在更大 pool、更多 layer 和更高 batch 下仍可接受。
- **观察 3：下一 decoding step 的第 k 高 index score 可由历史边界预测。** 图 7 中 `k=2048` 的边界随 step 平滑变化，`α=0.5` 的 EMA 能贴近下一步；当前分块中一旦某 token 的 score 超过预测边界，就能先发起 recall（§5.1）。
  - **依赖假设**：不同模型、layer、位置和输入仍保持这种边界稳定性。预测偏低会多取，偏高会少预取，但不会改变最终结果，因为还有 guaranteed recall。
- **观察 4：prefill 按 query block 顺序执行，天然提供跨 query 的 lookahead。** 在计算 block `i+1` 的 index score 时，可以搬 block `i` 的候选 KV；用粗粒度 radix histogram 得到一个 top-k 子集，比完整 top-k 更便宜（§5.2）。
  - **依赖假设**：不同 query token 的选择有足够重叠，且下一块 indexer 计算时间足以覆盖 recall。论文的保守随机选择 microbenchmark 最多只提高 1.1 倍。
- **观察 5：最终 exact top-k 与预取候选可以分开。** 预测只决定“提前搬什么”，indexer 完成后仍做 exact selection，并 guaranteed recall 所有尚未在 GPU 的选中 token。因此漏预取只损失性能，多预取只浪费带宽，不会把错误 KV 交给 attention（图 5、§3、§5）。
- **假设 1：host DRAM 和 [[PCIe]] 是可独占的大容量二级缓存。** 主实验给 ECHO 约 1000 GB host pool；多模型、多租户、[[NUMA|NUMA]]、page fault、pinning 和 PCIe 争用都没有加入。

## 核心方法

### 1. 每个 DP attention worker 管理两级 KV pool

ECHO 基于 SGLang 和 DeepGEMM。每个 [[Data-Parallelism|DP]] attention worker 有 GPU pool 与更大的 host pool；DSA indexer 的 K cache 永久放 GPU，MLA KV 在生成时写入 host，GPU pool 只缓存最近被稀疏 attention 选中的 token。DP scheduler 把请求分给 worker（图 5、§3）。

GPU pool 必须按 layer 管理，因为不同层的 top-k 不同，cache 状态会分叉；host pool 仍按 model 管理，因为它备份所有 token。驱逐时只删 GPU metadata，无需再写 host；真正 recall 时，GPU kernel 通过 unified virtual memory 直接读 host address，避免 CPU launch（§4.1–§4.2）。

### 2. 可被计算图捕获的缓存管理器（graph-friendly cache manager）

每层维护五类固定长度 tensor：

- `GPUTokenFree`：GPU slot 是否空闲；
- `GPUTokenPriority`：LRU-like 驱逐优先级；
- `GPUIndicesBuffer`：allocate/free 的固定输出区；
- `GPUTokenToHost` 与 `HostTokenToGPU`：双向 slot 映射。

若 host/GPU pool 分别有 `N_H`、`N_G` token，metadata 约为 `4N_H + 13N_G` bytes。论文设置 `N_H=2M`、`N_G=200K` 时每层约 10 MB，DeepSeek-V3.2 全部 61 层约 610 MB HBM（§4.1）。

**Allocate** 让所有 free slot 线程用 `atomicAdd` 竞争固定数量名额，并把结果写进预分配 buffer。**Free** 先保护本步 exact selected token，再用并行 `argtopk` 找最低 priority slot，scatter 清映射。**Recall** 用 `HostTokenToGPU` 找 miss，调用 free/allocate，更新双向映射并由 GPU kernel 从 host 搬数据。三类操作都在 captured graph 内完成（图 6、§4.2）。

### 3. Decoding：用 score 边界做 intra-query prefetch

top-k 的第 k 高 score 等价于一个阈值：任何高于真实阈值的 token 必然在 top-k 中。ECHO 用上一些 step 的第 k 高 score 做 EMA，预测本 step 阈值；indexer 扫 K cache 时，score 超过预测值的 token 立刻交给 prefetch warp（图 7–8、§5.1）。

阈值偏低可能产生超过 2048 个候选，因此系统设置与 context length 成比例的全局上限，避免 PCIe 工作反过来阻塞 indexer。indexer 完成后仍计算真实 top-k，并对所有 cache miss 做 guaranteed recall。这里的“lossless”来自这个补齐步骤，而不是 EMA 永不犯错。

### 4. Prefill：跨 query block 做 inter-query prefetch

完整 radix-select top-k 太慢，ECHO 只按 score 的最高 8 bit 建 256-bin histogram，选取严格高于 threshold bin 的若干最高 bin，因此得到 exact top-k 的一个保守子集。为缩小 threshold bin，它用前一 prefill chunk 末尾 token 的第 k 高 score EMA 平移当前 score；图 9 显示平移后 threshold bin 明显变小（§5.2）。

block `i` 的候选在计算 block `i+1` 时预取。这里也不依赖 approximate subset 保证正确性：最终 attention 前仍补齐所有 exact selected KV。近似只影响提前搬了多少。

### 5. 把 indexer、筛选和搬运融合成流水线

decoding fused kernel 用三类 warp：TMA warp 搬 indexer K 到 shared memory，GEMM warp 算 score，prefetch warp 比较 EMA threshold 并从 host 取 KV。多级 software pipeline 让三者重叠；prefetch stage 分配更多 buffer，避免它卡住 indexer（图 10、§5.3）。

prefill kernel 则外层遍历 Q block、内层遍历 K block；prefetch warp 边收 score 边建 histogram，并在下一个 Q block 计算时搬上一个 block 的候选（图 11）。

### 6. PD disaggregation 下的实际使用方式

论文建议把 prefill 与 decoding 分离。prefill worker 上关闭 offloading，因为一次 prefill 可能选中大量 token，并且 GPU→host 备份会和 host→GPU recall 争 PCIe；prefill 只要 HBM 能放下单个最长请求即可。随后 KV 发到 decoding instance 的 host pool，decoding 再只召回选中的部分（§3）。

因此主吞吐实验不是一个完整 online prefill+decode 服务：作者预先计算请求 KV，把 8×H20 当纯 decoding instance。论文设计了 inter-query prefetch，但 §6.2 主结果没有使用它，§6.4.3 也只有 microbenchmark，没有端到端吞吐消融。

## 设计取舍

- **更大并发换 host 资源。** 1.8M-token pool 消耗约 1000 GB DRAM，突破 HBM 上限的代价是把容量压力和故障域移到 host。
- **固定 tensor 换 HBM metadata。** 完整 graph capture 避免 CPU 控制，却为 DeepSeek-V3.2 付出约 610 MB HBM，并让所有 layer 都有独立状态。
- **per-layer cache 换管理次数。** 只保存真正被该层选中的 KV，提高命中效率；但 allocate/free/recall 从每模型一次变成每层一次。
- **提前多搬换保证不漏。** EMA 与近似 histogram 可以 over-prefetch，却不能替代 exact top-k；guaranteed recall 保护正确性，也意味着预测差时所有串行 recall 仍会回来。
- **吞吐换轻载延迟。** offload 扩大 batch 后利用率更高，但固定管理成本让低请求率的 ITL 和 end-to-end latency 明显变差。
- **PD 隔离换完整评测。** 分离 prefill/decode 避免双向 PCIe 干扰，但主实验用预计算 KV，没计入 prefill 实例资源、KV 传输和路由成本。

## 实验设置

- 单节点有 8×NVIDIA H20 96 GB，host–GPU 为 64 GB/s PCIe Gen5；CPU 是 224-core Xeon Platinum 8480+，host DRAM 1.5 TB（§6.1）。没有 H200、NVLink 或多节点实验。
- 模型是 4-bit AWQ DeepSeek-V3.2-Exp；indexer 与第 0、1、2、60 层保留未量化。长上下文 workload 是 InfiniteBench 中 318 个 80K–100K-token 请求，共约 26M input token；轻载延迟用 100 个 ShareGPT 请求。
- ECHO 与 SGLang 都用 attention DP8、[[MoE|MoE]] TP8；vLLM 因不支持这种组合而对 attention 和 MoE 都用 TP8。三者都开 CUDA Graph、[[Chunked-Prefill|chunked prefill]] 为 2048。这个拓扑差异会影响 vLLM 的 KV duplication 和 per-step latency。
- ECHO host pool 为 1.8M token、约 1000 GB。主吞吐实验预先生成 KV，只测 decoding；固定输出实验每请求 256 token，无上限实验才保留真实长尾输出。

## 实验与结果

- **最大生成吞吐**：所有系统使用可用 HBM、输出固定 256 token 时，低 request rate 下 ECHO 与基线接近；所有请求同时到达时，ECHO 达到 SGLang 的 2.15 倍、vLLM 的 4.1 倍。图中 ECHO effective batch 最高 102，SGLang 约 28–31，vLLM 约 1.5；优势主要来自 host pool 提高并发（图 12a、§6.2）。
- **HBM 更紧时**：ECHO 与 SGLang 的 GPU KV pool 都限制到 200K token，ECHO 最高快 3.10 倍；三者限制到 110K 时，ECHO 最高快 SGLang 4.12 倍。ECHO 甚至因 GPU pool 变小、metadata 管理更轻而略有改善（图 13、§6.2）。
- **真实长尾输出**：不限制输出长度后，DP worker 负载不均削弱 ECHO 与 SGLang。按 InfiniteBench task 分开时，ECHO 对 Code.Debug、En.MC、En.QA 分别提高 27.07%、2.83%、7.11%，但 Code.Run 低 1.74%；每项只有 31–160 个请求，少量长输出会主导总时间（图 12b、图 14、§6.2）。
- **延迟代价**：ShareGPT 轻载下 TTFT 最多增加 7.9%，ITL 增加 2.7%–27.8%。request rate 0.1–0.2 时 end-to-end latency 高 15.9%–19.2%；0.3 以上最多高 7.2%，0.5 到 Inf 低于 4.6%。在 Inf 下，纯 offloading allocate/free/recall/write-back 总计 1.15 ms，只占 all-layer decode 约 0.28%，但更大并发带来的 ReduceScatter jitter 仍增加约 6.8 ms（图 15–16、§6.3）。
- **GPU pool 命中与 intra-query 预取**：InfiniteBench 的多数 layer hit rate 为 0.97–0.99，layer 12/17 为 0.95/0.88。microbenchmark 在 hit rate 0.5/0.9 时，indexer+recall 最多加速 1.29/1.51 倍；0.97 时收益很小。端到端打开 intra-query prefetch 最高只提高 4%，说明主吞吐结论不是由预取贡献（图 17–19、§6.4.1–§6.4.2）。
- **inter-query 预取**：随机化 query 选择的保守 prefill microbenchmark 最多加速 1.1 倍。作者没有给 end-to-end 消融，因为主 PD 实验使用预计算 KV；真实 query 间选择重叠可能更有利，但只是未来假设（图 20、§6.4.3）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| host KV pool 能突破 HBM 并提高长上下文吞吐 | 图 12a：2.15 倍对 SGLang、4.1 倍对 vLLM；图 13：受限 HBM 下 3.10/4.12 倍 | 单台 8×H20、一个 AWQ DSA 模型、预计算 KV、约 1 TB host pool | 强 |
| graph-friendly manager 把动态 offload 成本压到较小 | 图 3b：allocator 低 1.6–1.9 倍延迟；图 16c：offload-specific 路径占 all-layer decode 约 0.28% | 自研 Triton 实现对 SGLang allocator；大 pool 扫描和多租户未测 | 中到强 |
| 预取不改变最终 sparse attention 选择 | 设计在预测后仍做 exact top-k，并 guaranteed recall 所有 miss | 属于机制推理；没有跨模型 bitwise-equivalence 或故障注入实验 | 中到强 |
| intra-query prefetch 能隐藏 recall | 图 18：hit rate 0.5/0.9 时最多 1.29/1.51 倍；图 19 端到端最高 4% | 实际大多数 layer hit rate 已为 0.97–0.99，收益受 MoE 主导时间限制 | 强 |
| ECHO 保持“可比较”的轻载延迟 | 图 15：TTFT 最多高 7.9%，但低 rate ITL 最高高 27.8%、E2E 高 15.9%–19.2% | “可比较”取决于 SLO；吞吐饱和时才降到最多 7.2% E2E 开销 | 中 |

## 批判性分析

### 论证链条

论文从 HBM 限制 batch 出发，用 host pool 放大并发，再用 graph-friendly manager 避免每层 CPU 控制，图 12–13 对这条主链支持很强。预取则是次要贡献：图 19 明确显示 intra-query 对端到端吞吐最高只加 4%，inter-query 又没有端到端结果。因而不能把 2.15 倍主结果解释成“lossless prefetch 的收益”；它主要证明动态 offload + 大 host pool 的容量价值。

### 假设压力测试

当模型没有显式 indexer 或第 k 高 score 不稳定时，cache manager 仍可用，但两种 prefetch 失去提前选择信号。若 GPU pool hit rate 已像图 17 一样接近 0.99，recall 本来就少，融合 prefetch 只增加判断；若 hit rate 很低，PCIe 可能比 indexer 慢，guaranteed recall 仍会暴露。低到达率、短 context 或 strict ITL SLO 下，15.9%–19.2% E2E 与最高 27.8% ITL 开销可能不值得换容量。1 TB host pool 被其他模型、NUMA 和内存带宽共享时，单机结果也可能崩塌。

### 实验可信度

论文给出全系统吞吐、受限 HBM、真实输出长度、轻载 latency、breakdown、hit rate 和两种 prefetch microbenchmark，能把容量收益与预取收益分开。主要外推限制是只有一台 8×H20、一个 4-bit DeepSeek-V3.2-Exp 和两个公开 trace。vLLM 不支持相同 DP+TP，所以 4.1 倍还包含 attention TP 导致的 KV duplication 与 effective batch 只有 1.5 的劣势；SGLang 的 2.15 倍才是更可比的主数字。PD 吞吐实验预计算 KV，也没有计 prefill GPU、跨实例 KV 传输和完整集群成本。

### 系统性缺陷

ECHO 新增每层双向映射、priority、并行 argtopk、UVM host access、fused warp pipeline 和约 610 MB HBM metadata，运行状态比普通 [[PagedAttention|paged KV]] cache 更复杂。约 1000 GB host pool 会带来 NUMA placement、pinning/page fault、host OOM、PCIe backpressure 和多租户隔离问题；论文没有讨论 request cancellation、worker crash、映射不一致或 recall 失败后的恢复。DP worker 在长尾输出下已经出现 load imbalance，扩大并发也会增加 collective jitter。系统没有 host DRAM 能耗、PCIe 利用率、p99、并发模型或多 tenant 干扰数据。

## 局限与后续工作

- **局限 1**：只测 DeepSeek-V3.2-Exp/DSA 和 8×H20；其他 native/block sparse indexer 是否有稳定边界未知。
- **局限 2**：主吞吐实验预先计算 KV，未计 prefill instance、PD 传输、调度和整套资源成本。
- **局限 3**：ECHO 使用约 1 TB host DRAM 与约 610 MB HBM metadata，容量、NUMA、能耗和多租户争用未评估。
- **局限 4**：inter-query prefetch 只有 microbenchmark；intra-query 在真实高 hit-rate workload 的端到端收益最高 4%。
- **后续工作 1**：在 NSA、MoBA、block-sparse 和 training-free 模型上分别测 score-boundary 误差、over-prefetch bytes、guaranteed-recall bytes 与 bitwise output 一致性。
- **后续工作 2**：运行完整 PD 集群，统一计入 prefill/decode GPU、host pool、跨实例传输、功耗、吞吐和 P99 SLO。
- **后续工作 3**：加入 SLO-aware admission：低负载或短 context 关闭 offload，高负载时再扩大 host-backed batch，并报告切换稳定性。
- **后续工作 4**：为双向映射和 UVM recall 增加版本、超时与恢复协议，测试 request cancel、GPU reset、host OOM 和 PCIe 降速。

## 相关

- **相关概念**：[[KV-Cache]]、[[Sparse-Attention]]、[[CUDA-Graph]]、[[PCIe]]、[[LLM-Inference]]
- **相关系统**：[[SGLang]]、[[vLLM]]
- **同会议**：[[OSDI-2026]]
