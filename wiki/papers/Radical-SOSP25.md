---
type: paper
name: Radical
full_title: "Running Consistent Applications Closer to Users with Radical for Lower Latency"
authors: [Nicolaas Kaashoek, Oleg A. Golev, Austin T. Li, Amit Levy, Wyatt Lloyd]
venue: SOSP
year: 2025
tags: [edge-computing, linearizability, serverless, speculative-execution, storage]
source_pdf: "[[3731569.3764831.pdf]]"
source_md: "[[3731569.3764831]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-17
---

# Running Consistent Applications Closer to Users with Radical for Lower Latency (SOSP 2025)

> **一句话总结**：Radical 用静态分析和 LVI 将确定性 Wasm handler 的 speculative execution 与验证重叠。在 AWS 原型的三种应用中，端到端 latency 相对 primary-datacenter baseline 改善 **28%–35%**；这相当于 inconsistent near-user lower bound 可得改善的 **84%–89%**，不是实际端到端改善幅度。

## 问题与动机

新 edge/datacenter 让应用可靠近用户，但 social/booking/forum 等 **强一致** 应用仍放中心：remote primary storage 每次访问都远；geo-replicated store（[[Spanner]]/DynamoDB global）受 PRAM 下界——read+write 延迟 ≥ 副本间最大距离。图 1 显示 geo-replication 对远端用户常 **不如** 中心化。

Radical 思路：storage 留 primary，edge 放 **eventually consistent cache** + **speculative execution**，并行发单轮 LVI 协调，成功则返回 speculative 结果，否则 fallback primary。

## 关键观察 / 隐含假设

- **观察 1**：要重叠 speculative execution 与协调，不能边执行边 validate read——需 **事先知道 read/write set**。
  - **依赖假设**：handler 可静态分析为 serverless function；存储访问显式；read/write set 可精确提取。
  - **可能失效场景**：动态 SQL/反射/间接存储访问使分析不全，需 fallback primary。
- **观察 2**：speculative write 不能等成功后再第二 RTT 写 storage；LVI 用 **write lock + write intent + deterministic re-execution** 在单请求内完成。
  - **依赖假设**：应用编译为 deterministic [[WebAssembly]] 子集；handler 确定性重放产生相同写。
  - **可能失效场景**：非确定性（时间、随机）破坏 re-execution；intent timer 误触发额外 primary 执行。
- **观察 3**：只有 execution time 足够长（论文：**≥20ms**）才能 hide LVI RTT。
  - **依赖假设**：microservice handler 常达 tens of ms。
  - **可能失效场景**：极短 handler 无收益甚至更慢。

## 核心方法

1. **Static analyzer**：per serverless handler 提取 read/write set。
2. **Speculative execution**：对 edge cache 执行；并行 LVI 到 primary storage。
3. **LVI protocol**：acquire read/write locks；validate cache 版本；setup write intents；失败则 primary 重执行。
4. **Deterministic Wasm**：保证 intent 触发的 re-execution 一致。
5. **Eventual cache** at edge；linearizable 语义相对 primary。

## 设计取舍

- **Single primary storage vs geo-replication**：降 storage 复杂度，edge 仍付一次 WAN RTT（与 speculation 重叠）。
- **Static analysis vs runtime tracking**：零 runtime 开销，但 expressiveness 受限。
- **Deterministic Wasm vs native code**：可验证一致性，限制语言特性。
- **Write intents + locks**：避免双 RTT，但 failure 时可能短暂 locking——依赖 intent 超时恢复。

## 实验与结果

**指标、基线与边界**：end-to-end latency、LVI validation rate、monthly cost；Radical vs primary-datacenter deployment；AWS、3 applications/15 functions/5 locations、DynamoDB cache/primary（§5）。

- 三个 microservices 共 **15** serverless functions，评测 handler 均可提取 read/write set；该覆盖只说明该评测集（§5.1–5.2，Table 1）。
- 相对 primary-datacenter baseline，latency 改善 **28%–35%**；为 inconsistent near-user lower-bound 改善的 hotel **89%**、social **88%**、forum **84%**（§5.3，Fig.4）。
- LVI validation success 约 **95%**；失败后在 near-storage re-execution（§5.3）。
- ≤50k reads/s、500 writes/s 的 AWS 成本模型中为 **$1413.36/月 vs $1077.36/月**，增加 **31%**（§5.7）。

## Claim–Evidence Map

| Claim | Evidence | Baseline / evaluation boundary | Locator | Confidence |
|---|---|---|---|---|
| 分析覆盖限于评测 handlers | 15 functions 均成功提取 read/write set | 3 AWS microservices；不泛化 dynamic access/ORM | §5.1–5.2，Table 1 | high |
| latency 实测改善与理论 lower bound 比例不同 | 28%–35% actual；84%/88%/89% lower-bound fraction | vs primary datacenter；非 DynamoDB global-tables head-to-head | §5.3，Fig.4 | high |
| 验证成功率是 latency 收益的前提 | 约 95% LVI validation success | 评测 workload；failure 走 near-storage re-execution | §5.3 | high |
| 20 ms 是经验近似而非阈值 | hotel-review 13 ms，forum handlers 16/18 ms | 被测 AWS 原型；direct near-storage execution | §5.5–5.6，Fig.6 | high |
| 成本增加受 workload/provider 假设约束 | $1413.36 vs $1077.36，+31% | AWS、≤50k reads/s/500 writes/s；含 cache/LVI server | §5.7 | high |

## Critical Analysis

### 论证链条

「PRAM 下界不可消但可重叠」+「LVI 单 RTT」+「static RW set」在 15 个函数上闭合。到任意 Java Spring/ORM 应用的推广需重新验证分析覆盖率。

### 假设压力测试

- 20ms 阈值下短 handler 占主导则 Radical 无意义。
- Edge cache stale + validator bug 可能违反 linearizability——依赖 protocol 正确性（论文有论证，非 machine-checked）。
- 1.3× 成本在轻流量 edge PoP 可能不经济。

### 实验可信度

- 真实 geo latency setting；三应用有代表性。
- 对比 centralized vs geo-replicated 动机图清晰；与最新 edge-DB 产品对比有限。
- Wasm determinism 限制使 baseline 非「原样应用」。

### 系统性缺陷

- 论文未讨论 cache 失效风暴、primary 故障时 intent 行为。
- Multi-tenant edge 节点 fair-share 未讨论。
- 静态分析维护成本随代码变更增长。

## 局限与 Future Work

- **局限**：≥20ms handler；deterministic Wasm；静态 RW set；成本 1.3×。
- **Future work**：partial dynamic tracking；弱化 determinism 需求；与 CRDT/transactional memory 比较。

## 相关

- **相关概念**：[[Linearizability]]、Edge-Computing、[[WebAssembly]]、[[Spanner]]、Speculative-Execution
- **同类系统**：[[Spanner]]、DynamoDB Global Tables、Faasm edge、Cloudflare Workers+Durable Objects
- **同会议**：[[SOSP-2025]]
