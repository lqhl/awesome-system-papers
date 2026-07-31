---
type: paper
name: Strata
full_title: "Strata: Hierarchical Context Caching for Long Context Language Model Serving"
authors: [Zhiqiang Xie, Ziyi Xu, Mark Zhao, Yuwei An, Vikram Sharma Mailthody, et al.]
venue: OSDI
year: 2026
tags: [llm-serving, kv-cache, storage-hierarchy]
source_pdf: "[[osdi26-xie-zhiqiang.pdf]]"
source_md: "[[osdi26-xie-zhiqiang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 长上下文 [[LLM|LLM]] 服务的分层上下文缓存
> **原题**：Strata: Hierarchical Context Caching for Long Context Language Model Serving

## 问题与动机

长上下文复用要求把 [[KV-Cache]] 扩展到 GPU、CPU、SSD，但各层碎片化布局会把命中转成大量小传输；若调度器只看是否命中，不看加载完成时间，GPU 仍会阻塞。

## 关键观察 / 隐含假设

- host/SSD 适合连续大 I/O，GPU 计算布局则适合模型访问，二者不必相同。
- KV 加载可以与别的 prefill/decode 工作重叠。
- 假设请求存在足够前缀复用，且层级带宽可被批量传输利用。

## 核心方法

[[Strata]] 用 GPU-assisted I/O 解耦 host 与 GPU 布局，将碎片重排放到设备侧并形成大传输；cache-aware scheduler 同时考虑命中位置和可用时间，以机会工作隐藏加载停顿。实现集成到 [[SGLang]]。

## 实验与结果

在长上下文 serving workload 上，Strata 相对 [[vLLM|vLLM]]-LMCache 吞吐最高提升 5×，相对 NVIDIA [[TensorRT-LLM|TensorRT-LLM]] 最高提升 3.75×（§7，图 13）。在未优化层级缓存中，KV transfer 可阻塞 74% prefill 时间；边界是具有前缀复用且 CPU/SSD cache 可命中的请求。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| 命中不等于及时可用 | 基线中 74% prefill 时间被传输阻塞 | §2 | 强 |
| 布局解耦与调度协同能恢复吞吐 | 相对 LMCache 最高 5× | §7 | 强 |

## 批判性分析

### 论证链条
论文把层级缓存问题从容量命中重新表述为传输粒度和 ready-time，并分别给出数据面与调度面机制。

### 假设压力测试
低复用、随机上下文、SSD 抖动或 decode 主导负载会削弱收益。

### 实验可信度
多强基线和生产 SGLang 实现增强可信度，但不同 SSD/[[PCIe|PCIe]] 拓扑下的收益区间仍需展开。

## 局限与后续工作

- 可探索多租户 cache fairness、写入放大、故障恢复，以及跨节点远程 KV 层级。

## 相关

- [[OSDI-2026]]
- [[SGLang]]
- [[KV-Cache]]
