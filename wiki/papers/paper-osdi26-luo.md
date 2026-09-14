---
type: paper
name: DirectKV
full_title: "No Buffer, No Bottleneck: Efficient Zero-Copy KV Cache Offloading for Long-Context LLMs"
authors: [Shutian Luo, Haiying Shen]
venue: OSDI
year: 2026
tags: [llm-inference, kv-cache, zero-copy, gpu-memory, heterogeneous-computing]
source_pdf: "[[osdi26-luo.pdf]]"
source_md: "[[osdi26-luo]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-09-14
---

# 面向长上下文 LLM 的零拷贝 KV cache 卸载（OSDI 2026）

> **原题**：No Buffer, No Bottleneck: Efficient Zero-Copy KV Cache Offloading for Long-Context LLMs

> **一句话总结**：现有 CPU 卸载方案仍需 HBM staging buffer 并反复搬运 KV；DirectKV 假设平台具备 GH200 的 NVLink-C2C 高带宽，把 KV 留在 pinned CPU memory 中由 GPU kernel 直接读取，再以 CPU-aware tiling、warp-level pipeline 和 projection-attention fusion 降低通信，GH200 上平均节省 43% GPU memory，端到端最高加速 1.2×。

## 问题与动机

长上下文推理中，KV cache 随序列长度线性增长，可能超过 GPU HBM。swap-based 方案把 KV block 搬入 GPU staging buffer，既占用 HBM，也使每层 swap-in/swap-out 放大 CPU–GPU 流量。把 attention 放到 CPU 又牺牲 GPU 算力。

DirectKV 选择另一条路径：在 GH200/GB200 这类 CPU–GPU 紧耦合平台上，使用 NVLink-C2C 让 GPU kernel 直接读取 CPU-resident KV。论文的难点不在地址可见性，而在访问模式：沿用 HBM 假设设计的矩阵乘法会反复取远端 KV，使互连带宽和 L2 locality 成为瓶颈。

## 关键观察 / 隐含假设

- **观察 1**：朴素 zero-copy 在 GH200 的矩阵乘法案例中延迟 106 ms，而 HBM baseline 为 52 ms；L2 hit rate 从约 77% 降至 32.3%（图 2、图 3）。重复读取远端 operand 会放大互连流量。
  - **依赖假设**：KV tile 足够大且并发度足够高，使瓶颈主要是持续 CPU–GPU bandwidth，而非单次 remote-load latency。
  - **可能失效场景**：PCIe 平台、低并发 decode、pageable memory、或 KV 落到 SSD/远端内存时，DirectKV 的访问延迟可能无法隐藏。
- **观察 2**：在 CPU–GPU bandwidth 不对称时，牺牲部分 HBM traffic 换取减少 CPU traffic 更划算。CPU-aware tiling 把 B tile 保留在 SMEM，使 CPU 流量从 33.5 GB 降到 0.4 GB，延迟从 106 ms 降到 54 ms（图 4、图 5）。
- **假设 1**：pinned host memory 中的 KV 不会被 CPU 并发修改；这是论文不依赖 GH200 unified page table 的原因。该假设对常规 decode 成立，但多线程 cache mutation、淘汰或 RDMA 写入时需要额外同步。

## 核心方法

DirectKV 由离线 Kernel Generator、运行时 Kernel Adaptor、Attention Fusion Engine 和 KV Cache Manager 组成（图 8）。Manager 用 `cudaHostAlloc` 分配 pinned CPU buffers；GPU 获得 device-visible pointer，在 kernel 内直接访问 KV，避免显式 `cudaMemcpyAsync` 和 HBM staging buffer。

CPU-aware tiling 针对 prefill 让 KV tile 在 SMEM 中复用，遍历 Q 而非反复遍历 KV。新增的 C/O 中间结果读写被转移到更快的 HBM。decode 只有一个新 query token，因此改为遍历 KV 一次，把输出保留在 registers 中。两种 phase 使用不同的迭代方向，回应了不同的复用关系。

warp-level pipeline 把 producer、consumer（prefill 还包括 storer）warp group 分开，用 TMA/异步搬运预取下一 tile，同时计算当前 tile。projection 与 attention 融合后，刚生成的 K/V 保留在 SMEM 并立即参与 attention，减少写回 CPU 后再读取的往返。

系统在 FlashAttention-3 和 CUTLASS 上实现，针对 precision、head dimension、tile size 及 prefill/decode phase 离线实例化 CUDA kernels，运行时选择候选 kernel。

## 设计取舍

- **带宽换容量**：把 KV 放入 CPU memory 能释放 HBM，但每次 attention 仍依赖互连；在 PCIe 上更像容量扩展机制，而非性能优化。
- **HBM 流量换互连流量**：CPU-aware tiling 增加中间结果的 HBM 读写，论文接受这一成本，因为 GH200 HBM 约 4 TB/s，高于 NVLink-C2C 的 900 GB/s 双向带宽。
- **专用 kernel 换通用性**：约 5,300 行 CUDA/C++ 代码和大量离线 kernel 变体带来调优收益，也增加了对 Hopper、SMEM 容量和 CUDA 版本的依赖。

## 实验与结果

- GH200 上 DirectKV 平均使用 47 GB GPU memory；Neo、Pie、FlexGen 分别约 86、88、74 GB，GPU memory 相比这些卸载方案降低 43%（图 11）。
- 在 1k–32k context、Llama-3.1-8B、OPT-13B/30B 和 ShareGPT/Alpaca workload 上，DirectKV 是支持该长度的卸载方案中延迟最低者，平均加速 1.2×；16k 时约比 Neo/Pie 快 1.3×，比 FlexGen 快 1.7×（图 11）。
- 请求率达到 30 req/s 时，Llama-3.1-8B 延迟为 0.75 s，其他卸载方案为 1.55–2.95 s；OPT-13B 上 DirectKV 仍支持 30 req/s，而 SGLang OOM（图 10）。
- CPU-aware zero-copy 相比朴素 zero-copy 最多减少 50% CPU–GPU transfer volume，并在三个模型上最多降低 70% inference latency（图 12）。
- 融合 kernel 的 HBM throughput 最高提高 3.5×，latency 降低 2.5–3.0×；NVLink-C2C 相比 PCIe 最多降低 attention latency 4.2×（图 13、图 14）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| DirectKV 能在不增加 HBM staging buffer 的情况下扩展 KV capacity | pinned CPU memory 设计与 47 GB GPU memory（§6、图 11） | 单节点 GH200，96 GB HBM，CPU pinned memory | 强 |
| CPU-aware tiling 缓解 zero-copy 的主通信瓶颈 | CPU 流量 33.5 GB→0.4 GB、延迟 106→54 ms（§2.4.1、图 5） | GH200 矩阵乘法与三个模型 | 强 |
| DirectKV 在长上下文下优于其他卸载方案 | 16k/32k latency 与 OOM 对比（§7.3.2、图 11） | Llama-3.1-8B、OPT-13B/30B，最高 32K | 中 |
| 高收益依赖高带宽互连 | NVLink-C2C 相对 PCIe 最多 4.2×（§7.4.3、图 14） | GH200 与 H100/PCIe，对比非同一完整平台 | 强 |

## 批判性分析

### 论证链条

从朴素 zero-copy 的远端重复读取，到 tile 复用、流水线和融合，设计回应关系清楚。端到端结果也与 memory savings 和 microbenchmark 方向一致。论文把“高效”主要定义为 GH200 上的延迟和容量折中；它没有证明 DirectKV 在 PCIe 或多节点远端内存上仍有相同性能收益。

### 假设压力测试

论文的工作负载主要是最高 32K context、最高 30 req/s 的稳定区域，并以 Poisson arrival 生成请求。真实生产 trace 的 burstiness、prefix sharing、动态 batch 和 cache eviction 可能改变 tile 复用及调度行为。DirectKV 还假定 host memory 有足够容量，且 KV access 可由大量 SM 并发摊平；小 batch decode 或更短上下文可能无法隐藏互连延迟。

### 实验可信度

模型、数据集、请求率、context length 和多个卸载基线覆盖了主要性能边界，并有组件消融。SGLang 在 KV 全部适合 HBM 时天然占优，比较体现了容量与性能折中。评测集中在 GH200，未报告多租户隔离、故障恢复、pinned memory 分配失败、功耗或云端成本；“支持 30 req/s”的公平性也依赖各系统具体 batching 配置。

### 系统性缺陷

约 5,300 行专用 CUDA 代码、离线 kernel candidate pool 和 Hopper 特化会增加维护成本。论文未给出 kernel 编译数量、二进制体积、运行时选择开销，以及模型结构变化（例如不同 GQA 配置或量化格式）下的覆盖率。CPU memory 压力、NUMA/多 socket、cache eviction 与跨机 RDMA 的一致性和恢复流程也未实现。

## 局限与后续工作

- **局限 1**：在 PCIe 上 DirectKV 主要提供容量扩展；论文测得 NVLink-C2C 相比 PCIe 的 attention latency 最多降低 4.2×，说明互连仍是硬上限。
- **局限 2**：当前设计是 node-local；跨服务器 KV、context parallel 和多级存储需要额外的所有权、预取、错误处理和调度机制。
- **后续工作 1**：在真实 bursty trace、动态 batching、prefix cache 和 cache eviction 同时启用时，测量 pinned-memory pressure、P99 latency 与 OOM/recovery 行为。
- **后续工作 2**：比较 DirectKV 与压缩、量化、分层 KV cache 的组合，在相同质量约束和总内存成本下报告 throughput/$ 与尾延迟。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[FlashAttention]]、zero-copy memory
- **同类系统**：[[SGLang]]、[[FlexGen]]、[[Pie]]、[[Neo]]
- **同会议**：[[OSDI-2026]]
