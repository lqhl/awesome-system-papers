---
type: paper
name: LMCache
full_title: "LMCache: An Efficient KV Cache Layer for Enterprise-Scale LLM Inference"
authors: [Yuhan Liu, Jiayi Yao, Yihua Cheng, Yuwei An, Xiaokun Chen, Shaoting Feng, Yuyang Huang, Samuel Shen, Rui Zhang, Kuntai Du, Junchen Jiang]
venue: arXiv
year: 2025
tags: [kv-cache, llm-serving, cache-layer, disaggregation, prefix-caching]
source_pdf: "[[arxiv25-liu-lmcache.pdf]]"
source_md: "[[arxiv25-liu-lmcache]]"
---

# LMCache: An Efficient KV Cache Layer for Enterprise-Scale LLM Inference (arXiv 2025)

> **一句话总结**：UChicago/Tensormesh 团队（CacheGen + CacheBlend 的同一组人）的全栈开源 KV cache 层——把 KV cache 从 GPU 内存中提取出来，支持在 GPU/CPU/SSD/remote storage 之间持久化存储和跨请求复用（prefix caching + PD disaggregation 双场景），用 batched data movement + 大 chunk 传输 + zero-copy 做到最高 15× 吞吐提升，已获工业界广泛部署。

## 问题

KV cache 在传统 LLM serving 中是一次性使用的 GPU 内存对象。但两个趋势迫使它走出 GPU：

1. **跨请求 cache reuse**：同一份长 context 被多个 query 复用（文档分析、多轮对话），GPU 内存不够存所有 prefix
2. **Prefill-Decode disaggregation**：prefill 节点生成的 KV cache 需要传输给 decode 节点

LMCache 的 real-world telemetry 显示：用户的 KV cache 总量持续增长，远超过 GPU 内存容量；超出 GPU 内存的 token 复用率也在快速增长。

## 核心方法

**三方面贡献**：

**1. 高性能数据搬运**：
- **Batched data movement**：GPU ↔ CPU memory 的 KV cache 搬运做批量化，pipeline 重叠 compute 和 I/O
- **大 chunk 传输**：不用 vLLM 原生的小 page（16 token / 20-63 KB），改用可配置的大 chunk（MB 级），打满 PCIe/NVMe/网络带宽
- **Zero-copy**：在不同 storage tier 之间移动 KV cache 时避免不必要的数据拷贝

**2. Modular connector**：设计标准化 connector 接口，解耦 LMCache 与快速演进的推理引擎（vLLM / [[SGLang]]）——引擎内部 KV cache layout 变化不影响 LMCache 集成

**3. First-class control API**：暴露 pin / lookup / cleanup / movement / compression 等 KV cache 管理原语，让上层 scheduler/router 可以做 **KV-aware query routing**（把 query 路由到已有相关 KV cache 的节点）

支持 multi-tier storage：GPU → CPU → local SSD → remote disk/Redis，以及 Ethernet / RDMA / NVLink 等多种传输网络。

## 关键结果

- 与 vLLM 结合：multi-round QA + document analysis workload 上 **最高 15× 吞吐提升**，**至少 2× 延迟降低**
- Local prefix caching / distributed prefix reuse / PD disaggregation 三个场景均显著优于基线
- 已在多家企业部署，Docker pull 持续增长
- 两个来自生产环境的洞察：(1) remote storage 后端在 prefill delay 上有意想不到的收益；(2) context truncation（工业界广泛使用的技术）会**使 prefix cache hit ratio 减半**

## 相关

- **相关概念**：[[KV-Cache]]、[[Prefix-Caching]]、[[Disaggregation]]、[[PagedAttention]]
- **前驱工作**：[[CacheGen-SIGCOMM24|CacheGen]]（KV 压缩传输）、[[CacheBlend-EuroSys25|CacheBlend]]（多 chunk KV 融合）
- **同类系统**：NVIDIA Dynamo KVBM、InfiniStore (ByteDance)、Mooncake
- **集成框架**：[[vLLM]]、[[SGLang]]
- **作者线**：Yuhan Liu、Jiayi Yao、Kuntai Du ([vLLM])、Junchen Jiang — UChicago/Tensormesh LMCache 团队的全栈作品
