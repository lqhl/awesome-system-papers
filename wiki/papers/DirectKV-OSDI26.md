---
type: paper
name: DirectKV
full_title: "No Buffer, No Bottleneck: Efficient Zero-Copy KV Cache Offloading for Long-Context LLMs"
authors: [Shutian Luo, Haiying Shen]
venue: OSDI
year: 2026
tags: [llm-serving, kv-cache, zero-copy, cpu-gpu-memory, nvlink-c2c]
source_pdf: "[[osdi26-luo.pdf]]"
source_md: "[[osdi26-luo]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 长上下文 [[LLM|LLM]] 的零拷贝 KV Cache 卸载（OSDI 2026）

> **原题**：No Buffer, No Bottleneck: Efficient Zero-Copy KV Cache Offloading for Long-Context LLMs

> **一句话总结**：DirectKV利用GH200/GB200的NVLink-C2C，让attention kernel直接读取CPU-resident KV，不再stage进HBM；CPU-memory-aware layout、QKV-attention fusion和warp pipeline使transfer最多减50%、GPU memory减43%、端到端最高1.2×。

## 问题与动机

现有CPU KV offload仍需GPU staging buffer：先host→HBM，再由attention读HBM，既占capacity又产生两份movement。PCIe latency/bandwidth使direct remote load不现实，但NVLink-C2C提供高带宽cache-coherent CPU–GPU互连，改变了设计点；关键是kernel必须适应远低于HBM的带宽/更高latency。

## 关键观察 / 隐含假设

- **观察 1**：论文识别出的主要瓶颈来自既有系统抽象与实际工作负载之间的错配。
- **观察 2**：将控制粒度下沉到论文提出的核心对象后，可以减少不必要的同步、搬移或串行等待。

## 核心方法

DirectKV取消staging，CUDA [[Attention|attention]] kernel直接访问CPU pinned/unified memory。它重排KV layout与coalesced access以减少remote transaction，并把KV generation/QKV projection与attention融合，让新K/V留在shared/register而不写回再读。warp-level pipeline重叠CPU fetch、matrix compute与writeback，隐藏individual access stall。

依赖NVLink-C2C约900 GB/s aggregate；在[[PCIe|PCIe]]-only平台，kernel优化无法克服物理带宽。CPU memory必须有足够[[NUMA|NUMA]] bandwidth，且GPU direct-access语义稳定。

## 实验与结果

- GH200上CPU–GPU transfer相对naive zero-copy最多降50%，GPU memory平均节省35 GB/43%。
- 多模型/长context下相对offload baselines平均约1.2×、部分约1.3×–1.7×；高load baseline OOM时仍可服务30 req/s。
- fused CPU-aware kernel HBM throughput最高3.5×、latency低2.5×–3.0×；NVLink-C2C场景attention latency最高改善4.2×。
- 与SGLang相比，KV全fit时它未必最低latency；价值在长context/capacity pressure下。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| staging buffer可被直接CPU访问取代 | end-to-end/memory | GH200 NVLink-C2C | 强 |
| CPU-aware fusion隐藏remote latency | component ablation | 三种模型 | 强 |
| GPU capacity显著增加 | memory measurement | 96GB配置 | 强 |
| 适用于一般CPU-GPU平台 | PCIe discussion | PCIe收益有限 | 弱 |

> **证据定位**：端到端结果与组件消融见 §6。

## 批判性分析

### 论证链条

DirectKV的贡献来自hardware inflection point，结论不能外推到PCIe A100/H100集群。43% memory saving以CPU memory/bandwidth为代价，multi-GPU/NUMA contention未充分展示；CPU成为共享KV tier后也可能形成noisy neighbor。kernel需针对model/layout维护，生态成本高于swap-based通用系统。

### 假设压力测试

核心假设一旦不成立，收益会退化或需要回退路径；上述适用边界应作为部署前的压力测试重点。

### 实验可信度

论文的定量结果支持其主要机制，但硬件、工作负载和基线范围限定了结论的可推广性。

## 局限与后续工作

- 多GPU共享Grace memory时测bandwidth contention与tail latency。
- 加入adaptive placement，让hot KV留HBM、cold KV direct CPU而无需大staging。
- 在GB200及PCIe/[[CXL|CXL]]多代平台绘制zero-copy crossover。

## 相关

- **相关概念**：[[KV-Cache]]、[[Zero-Copy]]、[[KV-Cache-Offloading]]、[[NVLink-C2C]]
- **相关系统**：[[SGLang]]、[[FlexGen]]
- **同会议**：[[OSDI-2026]]
