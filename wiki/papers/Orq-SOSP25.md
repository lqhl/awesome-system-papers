---
type: paper
name: Orq
full_title: "Orq: Complex Analytics on Private Data with Strong Security Guarantees"
authors: [Eli Baum, Sam Buxbaum, Nitin Mathai, Muhammad Faisal, Vasiliki Kalavri, et al.]
venue: SOSP
year: 2025
tags: [mpc, secure-analytics, oblivious-computation, relational-query, tpc-h]
source_pdf: "[[3731569.3764833.pdf]]"
source_md: "[[3731569.3764833]]"
---

# Orq: Complex Analytics on Private Data with Strong Security Guarantees (SOSP 2025)

> **一句话总结**:outsourced MPC 下的关系查询引擎,通过 join-aggregation 算子融合把 k-way join 从 $O(n^{k+1})$ 降到 $O(n \log n)$,首次在 MPC 下完整跑出 TPC-H SF=10 benchmark。

## 问题

MPC (Multi-Party Computation) 允许多方在不暴露明文的前提下协同计算,但要 oblivious——所有请求不依赖数据内容。这导致 join 在最坏情况下必须算笛卡尔积,$n$ 行 × $n$ 行输出 $n^2$;k-way join 变成 $O(n^{k+1})$。以往方案要么做 Cartesian product(贵)、要么硬设上限(silently 丢记录)、要么泄露 join 结果大小(不安全)。Secrecy 走 $O(n^2)$ 无泄露;Scape 降到 $O(n \log^2 n)$ 但泄露 result size。问题对 [[TPC-H]] 这类多表 join + aggregation 的现实 workload 尤其致命。

## 核心方法

Orq 针对 outsourced MPC 场景(data owner 把 secret share 发给若干非共谋 server,server 执行,输出 share 给 analyst)。核心洞察:MPC 场景的 aggregation 函数通常可分解(decomposable/algebraic),且查询输出大小可以用 data-independent 的 bound $u(n)$ 上界。

1. **Join-aggregation 融合算子**:MapReduce 风格地把 aggregation "eagerly" 下推到 join 过程,避免物化 Cartesian product。支持 inner/outer/semi/anti join,可与 filter 等算子级联。对所有出现过的 MPC 查询(31 条,包括 TPC-H 与以往工作),开销等于输入排序——$O(n \log n)$ ops、$O(\log n)$ rounds、$O(n)$ 内存。
2. **通用 oblivious shuffling/sorting**:把现有技术推广到不同 MPC 协议,为表格数据优化(避免冗余列置换),配合 butterfly 控制流减少通信轮数。data-parallel 向量化实现。
3. **协议无关黑盒设计**:算子只用 +、×、⊕、∧ 四种 MPC 原语,可替换协议。论文实例化三套:ABY(semi-honest, dishonest-majority)、Araki et al.(semi-honest, honest-majority)、Fantastic Four(malicious, honest-majority)。
4. **系统层**:dataflow-style API(类 [[Spark]]/Conclave);data-parallel vectorized runtime;amortize 网络开销的通信层——所有组件从头搭建。

Oblivious 表格用 secret-shared validity bit 区分 real/dummy 行,server 全程只操作 worst-case 大小。

## 关键结果

- **首次**在纯 MPC 下完整跑通 TPC-H(Scale Factor 10,以往要么靠 trusted compute、要么允许泄露才能达到此规模)。
- 在 LAN/WAN 上较 SOTA 关系型 MPC 系统(Secrecy、Scape、SecretFlow、Senate、Conclave 等)**显著**加速,可处理数据大 **一个数量级**。
- Oblivious sorting 可达 5 亿行,**10×** 于最好公开结果。
- 支持 semi-honest 与 malicious 两种威胁模型。
- 开源:https://github.com/CASP-Systems-BU/orq。

## 相关

- **相关概念**:[[MPC]]、[[Oblivious-Computation]]、[[Secret-Sharing]]、[[TPC-H]]、[[Relational-Query]]
- **同类系统**:Secrecy、Scape、SecretFlow、Senate、Conclave、Flock
- **同会议**:[[SOSP-2025]]
