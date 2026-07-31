---
type: paper
name: vBPF
full_title: "Virtualizing eBPF with Late-Binding"
authors: [Jing Zhang, Xiaguannan Song, Dong Du, Yubin Xia, Binyu Zang, et al.]
venue: OSDI
year: 2026
tags: [ebpf, virtualization, multi-tenancy]
source_pdf: "[[osdi26-zhang-jing.pdf]]"
source_md: "[[osdi26-zhang-jing]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 通过晚绑定虚拟化 eBPF
> **原题**：Virtualizing eBPF with Late-Binding

## 问题与动机

eBPF 的 static binding 把逻辑程序固定到物理 kernel hook，默认单一信任域。多个租户附着同一 hook 时既会线性遍历，也会共享 execution context 和 kernel object，造成性能干扰与状态破坏。

## 关键观察 / 隐含假设

- 物理 hook 可退化为通用 interposition point，程序选择延迟到事件归属确定之后。
- 编译器可自动隔离 tenant state。
- 假设运行时能准确把中断驱动事件归属到租户。

## 核心方法

[[vBPF]] 用 late binding 解耦 tenant program 与 physical hook：Sniffer 做事件归属，Dispatcher 以 `O(1)` lookup 代替线性遍历，compiler-assisted framework 隔离状态。原型基于 Linux 6.12。

## 实验与结果

多租户 contention 下，vBPF 相对 native eBPF 将 lmbench latency 最高降低 3.9×，PostgreSQL throughput 提高 29%（§7，图 12）。边界是 Linux eBPF 多租户共存及论文支持的 hook 类型。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| static binding 是共享 hook 冲突根因 | 多租户 microbenchmark 显示线性争用 | §2 | 强 |
| late binding 同时改善隔离与性能 | lmbench 3.9×、PostgreSQL 29% | §7 | 强 |

## 批判性分析

### 论证链条
论文从绑定模型而非单个 workaround 解释问题，并用三个机制覆盖 attribution、dispatch、state。

### 假设压力测试
归属不明确的 softirq、跨租户共享 socket 或复杂 global state 会挑战隔离边界。

### 实验可信度
内核原型与真实数据库负载较有说服力；security proof、完整 hook coverage 和 verifier 交互仍需展开。

## 局限与后续工作

- 后续应覆盖更多 attach type、形式化 tenant isolation，并评估动态程序更新和恶意程序的最坏开销。

## 相关

- [[OSDI-2026]]
- [[eBPF]]
- [[Multi-Tenancy]]
