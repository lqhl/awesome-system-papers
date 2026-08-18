---
type: paper
name: SkyWalker
full_title: "SkyWalker: A Locality-Aware Cross-Region Load Balancer for LLM Inference"
authors: [Tian Xia, Ziming Mao, Jamison Kerney, Ethan J. Jackson, Zhifei Li, Jiarong Xing, Scott Shenker, Ion Stoica]
venue: EuroSys
year: 2026
tags: [llm-inference, multi-region, load-balancing, prefix-caching, cloud-cost, area/ai-infra]
source_pdf: "[[eurosys26-xia-skywalker.pdf]]"
source_md: "[[eurosys26-xia-skywalker]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-17
---

# SkyWalker：面向 LLM 推理的局部性感知跨区域负载均衡（EuroSys 2026）

> **原题**：SkyWalker: A Locality-Aware Cross-Region Load Balancer for LLM Inference

> **一句话总结**：SkyWalker 利用不同 region 日周期错峰，把容量规划从“各地峰值之和”改为“全球聚合峰值”，再以跨区域 prefix-aware routing 和 selective pushing 保住 [[KV-Cache]] locality 与负载平衡；真实 workload 上吞吐提高 1.12–2.06×、延迟降低 1.74–6.30×，总成本降低 25%（§5，图 9–14）。

## 问题与动机

LLM provider 通常在每个 region 按本地峰值购买 reserved/on-prem GPU，低谷期容量无法共享。论文对 WildChat 五区域 trace 的分析显示，各地 load variance 为 2.88–32.64×，聚合后只有 1.29×；按全球峰值预留理论上可省 40.5%（§2.2，图 3）。

跨区路由不能直接套普通 web load balancer：LLM 请求持续数秒到数十秒，output length 不可预测；同时相同 session/prefix 应命中同一 replica 的 cache。

## 关键观察 / 隐含假设

- **观察 1**：region 间日周期具有可聚合的时间错位，静态本地峰值 provisioning 存在结构性浪费（§2.2）。
- **观察 2**：以 queue length 或 round-robin 分配无法表达连续 batching 是否还能接纳请求（§2.3）。
- **假设 1**：跨区 RTT 相对完整 [[LLM|LLM]] service time 足够小，且业务允许请求跨 region。
  - **证据强度**：中；TTFT-sensitive、数据驻留场景可能不成立。

## 核心方法

每个 region 保留本地 load balancer，避免中央协调点。SkyWalker 提供基于 user/session consistent hashing 的轻量方案，以及 distributed prefix trie，用有限的跨区 metadata 保留 [[Prefix-Caching]] locality。

selective pushing 不预测请求输出长度，而是观察 replica 是否有 pending admission capacity；本地过载时只把必要请求推向有余量的远端 region。这把不可预测 service time 转换为可观测的 queue/admission signal。

## 设计取舍

- **跨区共享换更低 provisioning cost**：增加 WAN RTT、流量费和数据合规问题。
- **分布式局部状态换可扩展性**：避免中心瓶颈，但 metadata 可能暂时不一致。
- **selective push 换少预测**：对突发反应快，却可能在控制延迟下振荡。

## 实验与结果

- WildChat 等三个真实 workload 上，相对 region-local/现有 load balancer 吞吐提高 1.12–2.06×、latency 降低 1.74–6.30×（§5.2–5.4，图 9–13）。
- 跨区共享使实际 serving cost 降低 25%；理论 trace aggregation 上界是 40.5%，两者不可混写（§2.2、§5.5，图 3、14）。
- prefix-aware routing 在测试中提高 cache hit，selective pushing 缓解单个长请求造成的 load skew（§5.3，图 11–12）。
- 实验覆盖 3 个 region 级 testbed/trace 驱动 workload，未覆盖大规模 WAN partition 或 regulatory routing constraint。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 跨区聚合能降低静态容量成本 | 实际省 25%，trace 上界 40.5%（图 3、14） | 选定地域流量与价格 | 强 |
| locality 与 load balance 可兼得 | 吞吐/延迟最高 2.06×/6.30×（§5） | 三类 workload、有限 region | 中强 |
| pending-based push 优于长度预测 | policy 对比与长尾 workload（§5.3） | output distribution 与控制周期固定 | 中 |

## 批判性分析

### 论证链条

从 diurnal aggregation 到 capacity sharing 的经济动机很强，prefix routing 与 selective push 分别回应 cache 和不可预测长度。成本收益依赖流量地理分布，不是 load-balancer 本身的固定性质。

### 假设压力测试

全球同时高峰、WAN partition、跨区 egress 高价或 data residency 会使远端 capacity 不可用。更短模型/更快硬件会提高 WAN RTT 在 TTFT 中的占比。

### 实验可信度

真实 trace 和 end-to-end metric 较完整，也区分理论上界与实际成本。region 数量、故障注入和跨云异构性不足以证明全球规模稳定性。

### 系统性缺陷

分布式 prefix metadata、session stickiness 和跨区故障恢复扩大了控制面。请求已推远端后若 region 失效，KV state 与生成进度如何迁移未深入评估。

## 局限与后续工作

- 注入 WAN partition、region outage 与 simultaneous global peak，测稳定性和 P99 TTFT。
- 将 egress、carbon、residency 与 session migration 纳入 routing objective。

## 相关

- **相关概念**：[[Prefix-Caching]]、[[KV-Cache]]、[[Continuous-Batching]]、[[LLM-Inference]]
- **同类系统**：[[SkyServe-EuroSys25]]、Preble、[[SGLang|SGLang]] Router
- **同会议**：EuroSys 2026

