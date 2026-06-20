---
type: paper
name: Compass
full_title: "Compass: Encrypted Semantic Search with High Accuracy"
authors: [Jinhao Zhu, Liana Patel, Matei Zaharia, Raluca Ada Popa]
venue: OSDI
year: 2025
tags: [encrypted-search, semantic-search, oram, privacy, hnsw]
source_pdf: "[[osdi25-zhu-jinhao.pdf]]"
source_md: "[[osdi25-zhu-jinhao]]"
---

# Compass: Encrypted Semantic Search with High Accuracy (OSDI 2025)

> **一句话总结**：加密搜索长期只有低精度关键词匹配或漏 pattern；Compass 在 Ring ORAM 上对加密 embedding 跑 HNSW 图遍历，用 Directional Neighbor Filtering + Speculative Prefetch + Graph-Traversal Tailored ORAM，精度对齐明文 HNSW，延迟 **0.57–1.28s**（跨区网），比朴素 ORAM+HNSW 最高 **920×**。

## 问题与动机

E2E 加密备份/消息应用需服务端搜索但不泄露数据、查询与访问模式。传统加密倒排索引只做关键词相等，语义差（图 1 MS MARCO）。语义搜索用 embedding 近邻，但加密下 FHE/GarbledRAM 太慢；leaky search 或 TEE 有攻击面。HNSW 图遍历若每访问一节点一次 ORAM 往返，需数千节点、数百 RTT。

## 关键观察 / 隐含假设

- **观察 1**：客户端可缓存小 chunk 的方向信息，在图 walk 时每步只拉取与查询「同方向」邻居 embedding 子集，带宽大幅下降（Directional Neighbor Filtering）。
  - **依赖假设**：个人/企业数据规模下客户端缓存可控（小数据集 **5.5MB** 级）。
  - **可能失效场景**：全球 web 规模索引客户端需 **~0.5GB**，论文承认尚不适合。
- **观察 2**：Speculative Neighbor Prefetch 可合并未来可能访问节点，减少 ORAM 往返次数。
  - **依赖假设**：图局部性使 prefetch 命中率高 enough 抵消额外带宽。
- **假设 1**：Ring ORAM 将计算放客户端、服务端只存密文，可任意距离度量 + 标准 embedding 模型。
  - **证据强度**：强——与 FHE linear scan 等 baseline 数量级差距。

## 核心方法

**索引**：加密 HNSW 存服务端；搜索算法在客户端执行。

**三技术**：DNF（方向过滤）、SNP（推测预取）、GT-ORAM（白盒改造 Ring ORAM 重排与遍历融合）。

**API**：INIT/SEARCH/INSERT/DELETE；支持加密 RAG 检索。

威胁模型：恶意单逻辑 server，不隐藏操作类型（search/insert/delete）；不防 timing side channel。

## 设计取舍

- **取舍 1**：强安全（无 access pattern 泄漏）换客户端计算与带宽工程。
- **取舍 2**：不隐藏操作类型与粗粒度存储大小，换性能（可用 padding 加固）。
- **边界条件**：4 个公开数据集；跨区慢网 latency 数字。

## 实验与结果

- 精度：与明文 SOTA HNSW **对齐**（4 数据集）。
- vs 朴素 ORAM+HNSW：**最高 920×** speedup。
- 用户感知延迟：**0.57–1.28s**（慢跨区网络）。
- 客户端内存：个人场景 **5.5MB** 级；大规模 **~0.5GB**（Tab. 4）。

## Critical Analysis

### 论证链条

「图遍历 + ORAM 太贵」→ 三技术减带宽/RTT → 精度不降 + 秒级延迟，安全模型下 claim 闭合。Global-scale 坦诚不行，诚实边界清晰。

### 假设压力测试

DNF 方向近似是否在高维 embedding 上损 recall？恶意 server 返回错误密文，客户端完整性检查覆盖范围？查询相关 timing 未防。

### 实验可信度

4 数据集多样；baseline 含 HERS/SANNS 等重密码方案。与 Tiptoe（公开 DB）场景不同，对比需注意。

### 系统性缺陷

INSERT/DELETE 频率高时 ORAM 维护成本；多用户数据共享索引优化未做（future work）。

## 局限与 Future Work

- **局限 1**：全球规模 web 搜索客户端内存 **0.5GB** 不可接受。
- **局限 2**：操作类型与 timing 泄漏面仍在。
- **Future work 1**：共享索引与多用户优化。
- **Future work 2**：与 padding 联动的 operation-hiding。

## 相关

- **相关概念**：[[RAG]]
- **同会议**：[[OSDI-2025]]