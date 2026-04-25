---
type: paper
name: Radical
full_title: "Running Consistent Applications Closer to Users with Radical for Lower Latency"
authors: [Nicolaas Kaashoek, Oleg A. Golev, Austin T. Li, Amit Levy, Wyatt Lloyd]
venue: SOSP
year: 2025
tags: [edge-computing, linearizability, speculative-execution, serverless, consistency]
source_pdf: "[[3731569.3764831.pdf]]"
source_md: "[[3731569.3764831]]"
---

# Running Consistent Applications Closer to Users with Radical for Lower Latency (SOSP 2025)

> **一句话总结**:通过静态分析 + 推测执行 + 单次 Lock-Validate-WriteIntent (LVI) 协议,让强一致应用部署到 edge/near-user 点上享受低延迟,获得移出 datacenter 84-89% 的理论延迟收益,同时仍保证 Linearizability。

## 问题

社交、订票、论坛等强一致应用通常只能跑在 primary datacenter 里,贴着存储。想要近用户部署降低端到端延迟,要么每次操作跨地域访存(慢),要么用 geo-replicated 存储(受 PRAM impossibility 限制,读写延迟之和 ≥ 副本间距)。结果:近用户部署往往比集中部署还慢。

## 核心方法

Radical 把存储留在 primary datacenter,在每个 near-user 位置放一个 **eventually consistent cache** + 运行时。核心是新的 **Lock-Validate-WriteIntent (LVI) 协议**:

1. **函数注册阶段**:用 symbolic execution + dependency analysis 对 serverless 请求 handler ?? 静态抽取出 $f^{rw}$,它在同样输入下返回本次将要 read/write 的 key 集合(read/write set)。
2. **请求执行阶段**:先跑 $f^{rw}$ 拿到 read/write set,然后**并行**做两件事:(a) 在 near-user cache 上推测执行 ??;(b) 发一个 **LVI 请求**到 near-storage,携带 cache 里各 key 的版本号。
3. **近存储端**:acquire 读/写锁,做 validate(对比版本);若通过,则为要写的 key 建 write intent + 定时器,返回。若失败,在 near-storage 本地跑一遍 backup $f$ 并把新值和 stale 项捎回 near-user 更新 cache。
4. **Durable write**:客户端收到结果后,near-user 发 write followup 带上推测写;若 followup 超时,near-storage 用 **deterministic re-execution**(函数编译为 [[WebAssembly]] 子集、无 timer/随机源)重放函数确保一致。

只在函数执行时间 ≥ 20 ms 时受益(足以掩盖 LVI RTT)。支持任何提供 Linearizability 的后端(DynamoDB、BigTable、CosmosDB)。

## 关键结果

- 在 VA / CA / IE / DE / JP 五地部署,跑 social media / hotel booking / online forum(15 个 serverless 函数)。
- 获得移出 datacenter 理论最大延迟改进的 **84–88%**,即端到端延迟下降 **28–35%**。
- 缓存额外成本约为 baseline 的 **1.3×**。
- 静态分析对所有测试 handler 都成功抽出 read/write set;5 个应用 27 个函数均可编成 deterministic Wasm。

## 相关

- **相关概念**:[[Linearizability]]、[[Speculative-Execution]]、[[Serverless]]、[[WebAssembly]]、[[Static-Analysis]]、[[PRAM-Impossibility]]
- **对比系统**:Spanner、DynamoDB Global Tables
- **同会议**:[[SOSP-2025]]
