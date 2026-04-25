---
type: paper
name: Spirit
full_title: "Spirit: Fair Allocation of Interdependent Resources in Remote Memory Systems"
authors: [Seung-seob Lee, Jachym Putta, Ziming Mao, Anurag Khandelwal]
venue: SOSP
year: 2025
tags: [remote-memory, fair-allocation, auction, rdma, multi-tenant]
source_pdf: "[[3731569.3764805.pdf]]"
source_md: "[[3731569.3764805]]"
---

# Spirit: Fair Allocation of Interdependent Resources in Remote Memory Systems (SOSP 2025)

> **一句话总结**:基于微观经济学 CEEI/Walrasian 拍卖的 Symbiosis 算法,在 swap-based remote memory 里对 cache 和网络带宽做联合分配,保证 Pareto-optimal/envy-free/sharing-incentive,对多个真实应用提升性能最高 21.6%,平均收敛 140 ms。

## 问题

Swap-based remote memory 系统([[vLLM]] 之外的内存层,如 Infiniswap、Leap、Hydra、AIFM)里,本地 cache 和跨网带宽对应用性能有 **interdependence**:skewed KV store 加点 cache 能大幅省带宽,stream 应用再多 cache 也没用。同一 throughput 可由很多 ⟨cache, bandwidth⟩ 组合达到,但关系是 application-specific 且运行前不可知。经典多资源分配如 [[DRF]] 假设资源独立、demand 固定、已知——放到这里用户都会 over-claim,退化成静态划分;而硬件 cache 的资源分配方案又要改硬件、违反 transparency。

## 核心方法

Spirit 重新定义目标为 **performance fairness**(每个 app 的 data access throughput 公平),引入 **Symbiosis** 拍卖算法:

- 所有 app 初始分到等额 credits,cache 和 bandwidth 初始等价(p_c = p_b = 0.5)
- 每轮 auction 每个 app 在预算内最大化自己的 f_i(c, b)(性能函数)
- 若总需求超出某资源容量,用 **binary search** 调资源价格(抢手的涨、冷门的跌),让下一轮总需求向 capacity 收敛
- f_i 单调性保证 demand 会被价格拉过去,证明收敛到 Pareto-optimal、envy-free、满足 sharing-incentive

**Runtime 估计 f_i** 解决拍卖不 strategy-proof:不靠用户报值,靠 [[PEBS]] 采样 + 梯度下降回归,在线估计每个 app 在不同 ⟨c, b⟩ 下的 memory access rate,直接供 Symbiosis 迭代。数据面两模块:resource enforcer(按分配结果逐出 cache / 限网发)和 performance monitor(采访问率喂回估计器)。保持 swap-based 系统的 transparency(不改应用、不改硬件)。

## 关键结果

- 评测了 STREAM(带宽敏感)、Memcached + Meta trace(cache 敏感)、DLRM(compute-bound)、DeathStarBench SocialNetwork(cache 敏感微服务)
- 相对传统多资源分配,性能提升最高 21.6%
- 同时保持 envy-free / sharing-incentive / Pareto-efficient
- 平均收敛时间低至 140 ms,适合动态 workload
- 24 app 实例下仍稳定
- 代码开源 (github.com/yale-nova/spirit)

## 相关

- **相关概念**:[[DRF]]、[[Remote-Memory]]、[[Fair-Scheduling]]、[[PEBS]]、CEEI / Walrasian auction
- **同类工作**:DRFQ、Infiniswap、Leap、Hydra、AIFM;硬件 cache 分配(Intel CAT、Cache Allocation Technology)
- **同会议**:[[SOSP-2025]]
