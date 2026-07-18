---
type: paper
name: Dandelion
full_title: "Unlocking True Elasticity for the Cloud-Native Era with Dandelion"
authors: [Tom Kuchler, Pinghe Li, Yazhuo Zhang, Lazar Cvetkovic, Boris Goranov, Tobias Stocker, et al.]
venue: SOSP
year: 2025
tags: [serverless, faas, elasticity, cloud-native, isolation]
source_pdf: "[[3731569.3764803.pdf]]"
source_md: "[[3731569.3764803]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Unlocking True Elasticity for the Cloud-Native Era with Dandelion (SOSP 2025)

> **一句话总结**：即使 [[Firecracker]] snapshot 仍需 >10ms 且 Knative 为降 cold start 平均多占 **16×** 内存；Dandelion 用 pure compute + HTTP communication function DAG，在 **100μs 级** 冷启动 sandbox 上按请求启动，Azure trace 上 committed memory **-96%**，尾延迟波动降 **2–3 个数量级**。

## 问题与动机

[[Serverless]]/FaaS 宣称弹性，但为掩盖 MicroVM 启动成本需大量 warm sandbox（Azure trace：**97%** 请求落在预分配内存）。DRAM 占服务器成本大头，cold start 仍造成 tail 剧增（Figure 2 log scale）。根因：函数运行在 POSIX-like MicroVM，>8ms 花在 demand-paging guest OS snapshot 与重建网络。云原生应用已习惯 REST 调存储/DB/AI——可放弃完整 POSIX 网络栈以换弹性。

## 关键观察 / 隐含假设

- **观察 1**：分解为 **pure compute function**（无阻塞、无 guest OS 网络）+ **communication function**（平台实现 HTTP）可极轻 sandbox 冷启动。
  - **依赖假设**：目标应用 I/O 可经 HTTP 表达；不需 listen socket/incoming connection。
  - **可能失效场景**：OTLP gaming、强状态同步、低延迟 P2P 不适用（论文 non-goals）。
- **观察 2**：KVM hello-world **~52μs** 级 vs Firecracker 函数 **>10ms**——差距主要在 guest OS 网络环境而非 CPU 虚拟化本身。
  - **依赖假设**：CHERI/process/rWasm 等后端可提供足够隔离。
  - **可能失效场景**：Wasm 计算密集仍慢于 native（§2.1 承认）。
- **假设 1**：每 compute 函数独占 core、run-to-completion 可减少上下文切换。
  - **证据强度**：中；适合无阻塞 pure function，communication 侧 cooperative I/O 需 core 超售策略。

## 核心方法

**编程模型**：DAG of pure compute + communication（HTTP，可扩展协议）。DSL 描述数据依赖。

**执行**：compute 用 KVM/process/[[CHERI]]/rWasm 隔离；节点级 cooperative network runtime；按 compute vs comm 函数数弹性分配 CPU。

**应用**：分布式 log 处理、S3 SQL、Text2SQL agent 等。开源 https://github.com/eth-easl/dandelion 。

## 设计取舍

- **取舍 1**：放弃 POSIX 兼容 → 生态与迁移成本。
- **取舍 2**：communication 函数不可用户修改 → 安全但限制扩展协议。
- **边界条件**：vs AWS Athena 短查询 **-40%** latency、**-67%** cost；matmul cold % 敏感（Figure 2）。

## 实验与结果

- 冷启动：**100μs 级**，CHERI **<90μs**；比 Firecracker snapshot **>10×** 快
- Azure Functions trace（100 functions）：committed memory **-96%** vs Knative
- 执行时间方差：**2–3 个数量级** 降低
- vs Athena：短查询 latency **-40%**，cost **-67%**

## Critical Analysis

### 论证链条

「POSIX 网络初始化是弹性瓶颈」+ 云原生 REST 接口 → 拆分 compute/comm → 按请求冷启动，trace 与 microbench 支撑。到「替代主流 Lambda」跳步大：现有函数大量依赖 libc/socket/遗留库；迁移需重写为 inferlet/DAG。

### 假设压力测试

- **安全**：轻量 sandbox 是否等价 MicroVM defense-in-depth——多后端对比有益但长期 CVE 面需跟踪。
- **吞吐**：独占 core per compute 在高并发下 CPU 碎片 vs 吞吐上限。
- **状态**：DAG 无通用跨函数内存共享，复杂 agent 状态需外存。

### 实验可信度

Azure trace replay 有说服力；Athena 对比场景较窄。Wasm 慢路径在 §7.3 有测，但主力 numbers 用 native/KVM/CHERI。

### 系统性缺陷

平台运营 communication function 池的 SLO、DDoS 面、多租户 fair scheduling 论文未充分讨论；与现有 K8s/Knative 集成路径未详述。

## 局限与 Future Work

- **局限 1**：不适合 OTP、在线游戏、频繁状态同步（non-goals）。
- **局限 2**：依赖应用改写为 DAG + pure function  discipline。
- **Future work 1**：混合模式：热路径 Firecracker、冷路径 Dandelion，测量 break-even QPS。
- **Future work 2**：更多 communication primitive（gRPC、queue）对冷启动与 TCB 的影响。

## 相关

- **相关概念**：[[Serverless]]、[[FaaS]]、[[Firecracker]]、[[Cloud-Native]]、[[CHERI]]
- **同类系统**：Knative、SigmaOS、Wasmtime FaaS、AWS Lambda
- **同会议**：[[SOSP-2025]]
