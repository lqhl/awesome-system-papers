---
type: paper
name: Orq
full_title: "Orq: Complex Analytics on Private Data with Strong Security Guarantees"
authors: [Eli Baum, Sam Buxbaum, Nitin Mathai, Muhammad Faisal, Vasiliki Kalavri, Mayank Varia]
venue: SOSP
year: 2025
tags: [mpc, secure-analytics, oblivious-computation, query-engine, privacy]
source_pdf: "[[3731569.3764833.pdf]]"
source_md: "[[3731569.3764833]]"
---

# Orq: Complex Analytics on Private Data with Strong Security Guarantees (SOSP 2025)

> **一句话总结**：outsourced [[MPC]] 中 oblivious join 的 Cartesian product 导致 $O(n^{k+1})$ 爆炸；Orq 观察 31 个真实/MPC workload 的输出均可被输入规模 $O(n)$ 界定，从而 **join 时 eager aggregation** + oblivious shuffle/sort，首次在纯 MPC 下完成 TPC-H SF=10 全基准，比 SOTA 快一个数量级且可处理 10× 更大数据。

## 问题与动机

[[Secure-Multi-Party-Computation]] 使多方在不信任 server 上联合分析成为可能，但 oblivious 执行隐藏数据分布：filter 返回满长表、join 返回 $n^2$ Cartesian product，多路 join 级联更糟。outsourced 设置无 trusted plaintext compute，[[Secrecy]] 无泄漏但 quadratic；[[Scape]] 快但泄漏 join size。

核心问题：**duplicate keys 的两表 join** 是 cascading effect 症结，先前 fully oblivious 方案或 Cartesian、或截断结果、或泄漏体积。

## 关键观察 / 隐含假设

- **观察 1**：TPC-H 与 prior MPC works 的 31 个 workload 中，查询输出大小均有 **与输入规模相关、与数据分布无关** 的上界 $O(n)$。
  - **依赖假设**：分析类查询返回聚合/有界结果，而非裸 cross join 输出。
  - **可能失效场景**：需输出未聚合超大 join 结果的 ad-hoc SQL 不在支持类。
- **观察 2**：许多聚合可 **decomposable/partial**，允许 MapReduce 式 join-aggregation 流水线，中间结果保持 $O(n)$。
  - **依赖假设**：GROUP BY keys 出现在单表或 one-to-many join 结构可识别。
  - **可能失效场景**：many-to-many 无 decomposable agg 的查询仍可能需 quadratic 或 leakage。
- **观察 3**：oblivious shuffle/sort 可与 butterfly network 结合，在多种 MPC protocol（semi-honest/malicious）黑盒复用。
  - **依赖假设**：参与方数量由 protocol 决定但可支持多 data owner。
  - **证据强度**：强。TPC-H SF10 full benchmark under MPC 为首见硬结果。

## 核心方法

- **Oblivious join-aggregation operator**：支持 inner/outer/semi/anti join + 广类 agg；eager 分解聚合保持中间结果有界。
- **Data-parallel vectorized engine** + dataflow API；通信层 amortize WAN/LAN MPC 成本。
- **Generalized oblivious shuffle/quicksort/radixsort**（tabular-aware，少列置换）。
- **Protocol-agnostic**：黑盒使用 MPC 原语 (+, ×, compare, …)；实例化 semi-honest (honest/dishonest majority) 与 malicious honest-majority。

复杂度：$O(n \log n)$ ops、$O(\log n)$ rounds、$O(n)$ memory（对收集的 workload 类）。

## 设计取舍

- **Workload class restriction vs fully general SQL**：换可 tractable 强安全。
- **No TCB vs Scape-style leakage**：纯 MPC 慢但安全；Orq 大幅缩 gap。
- **Vectorized oblivious primitives vs specialized per-query circuits**：通用引擎，可能非每个 query 最优常数。

## 实验与结果

- **TPC-H SF=10 全基准首次 entirely under MPC**（先前需 leakage 或 trusted compute）。
- 九 prior-work 查询 + TPC-H：比 SOTA relational MPC **数量级**更快；可处理 **10×** 更大输入。
- Oblivious sort 至 **5 亿行**（10× 于 best published）。
- LAN/WAN 部署；三 protocol 实例。

## Critical Analysis

### 论证链条

「31 workload 输出有界 → eager join-agg → sort/shuffle 引擎 → TPC-H SF10」链条强。对 arbitrary SQL（unbounded projection join）的边界需在 Orq compiler 层显式拒绝或 fallback——论文 §2.1 有 class 定义，运维需遵守。

### 假设压力测试

- Analyst 误写不受支持查询可能 silent 截断或失败——错误可用性依赖 static check。
- Malicious protocol 成本仍高；WAN 下 round complexity 仍是尾延迟来源。
- 5 亿行 sort 的内存 $O(n)$ 在 practice 仍是数百 GB 级——需 cluster scale。

### 实验可信度

- TPC-H full under MPC 里程碑式；开源（CASP-Systems-BU/orq）。
- 与 Secrecy/Scape/SecretFlow 对比覆盖 research SOTA。
- 常数因子与 crypto setup 成本需读者看 §6 细表。

### 系统性缺陷

- 论文未讨论 query planner mistake 导致的信息泄漏路径（implementation bug class）。
- Data owner onboarding、key rotation、合规审计工具链未讨论。
- 非 decomposable agg 的完整 catalog 边界需运维文档化。

## 局限与 Future Work

- **局限**：不支持任意 SQL；many-to-many 无界 join；MPC 固有成本仍高。
- **Future work**：compiler 自动判定 tractability；硬件加速 MPC；混合 TEE+MPC 分层。

## 相关

- **相关概念**：[[MPC]]、Oblivious-RAM、Secure-Analytics、[[TPC-H]]、Secret-Sharing
- **同类系统**：Secrecy、Scape、SecretFlow、Senate、Flock
- **同会议**：[[SOSP-2025]]