---
type: paper
name: AFaaS
full_title: "Fork in the Road: Reflections and Optimizations for Cold Start Latency in Production Serverless Systems"
authors: [Xiaohu Chai, Tianyu Zhou, Keyang Hu, Jianfeng Tan, Tiwei Bie, et al.]
venue: OSDI
year: 2025
tags: [serverless, cold-start, faas, containers, production]
source_pdf: "[[osdi25-chai-xiaohu.pdf]]"
source_md: "[[osdi25-chai-xiaohu]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# AFaaS：岔路口：生产无服务器系统冷启动延迟的思考和优化（OSDI 2025）

> **原题**：Fork in the Road: Reflections and Optimizations for Cold Start Latency in Production Serverless Systems

> **一句话总结**：Ant Group trace 显示超过 50% 的函数 cold-start probability 大于 0.75；AFaaS 用 FRI、资源池化/共享与树形 seed 优化控制路径、资源 contention 和 user-code init。作者报告系统部署超过 18 个月；8 个 Node.js 生产函数的一日统计中 startup latency 为 5.45–9.41 ms，平均 E2E 相对 CataOnly 为 1.80×–8.14×（§2.1、§6.6，Fig. 4/18，Table 2）。

## 问题与动机

Serverless 冷启动常达数百 ms–数秒，而函数体常仅 50–100 ms。Ant Group 超过 5 万个函数、日均约 1 亿调用，超过 50% 函数的 cold-start probability 大于 0.75，超过 35% 为 1；热实例缓存 1 分钟限制使冷启动仍占多数（§2.1，Fig. 4）。

论文指出三类被忽视的 **E2E** 瓶颈：(1) **control path**（containerd→shim→engine 二进制加载，Catalyzer 下 18–25 ms）；(2) **资源 contention**（clone/netns/seccomp 在高并发下 tail 爆炸）；(3) **user code init**（Node 函数 275 ms 中 238 ms 加载依赖）。

## 关键观察 / 隐含假设

- **观察 1**：fork 类优化只加速 sandbox clone，不缩短 OCI 控制链与用户代码加载，E2E 仍 dominated by 被忽略阶段。
  - **依赖假设**：生产使用 micro-VM 安全容器（Catalyzer/sfork），非普通 runc。
  - **可能失效场景**：极简函数、极短依赖；非 VM 隔离平台。
- **观察 2**：高并发下 IPC namespace、veth、seccomp 编译争用 host 内核锁，导致吞吐从 110 FPS 降至 45 FPS（×24 持续 1h）。
  - **依赖假设**：瓶颈在 host 内核而非 guest；seed 共享 netns/IPC 不破坏安全隔离（用户代码在 guest OS）。
  - **证据强度**：强——分阶段 profiling + 优化后波动下降。
- **假设 1**：OCI 为长运行容器设计，serverless 应专用 **FRI**（插件化函数调用替代每次加载 engine 二进制）。
  - **证据强度**：强——BinaryLoad 18.02 ms 被消除；生产 18 个月部署。

## 核心方法

**FRI**：containerd-faas-package 插件直接 RPC 调 create/fork/activate；root seed 创建后不再加载 AFaaS runtime 二进制。

**资源池化/共享**：veth/cgroup 池；seed 共享 netns/IPC；seccomp 预编译；网络栈 shareable 部分预初始化。

**树形 seed**：level-0（guest OS）→ level-1（语言 runtime）→ level-2（用户代码）；CoW 多级 fork，best-effort 选最近 seed。

## 设计取舍

- **取舍 1**：牺牲 OCI 通用模块化，换 FaaS 特化控制面。
- **取舍 2**：共享 namespace 换 latency；每实例仍从干净 seed fork 并在执行后销毁（安全）。
- **边界条件**：大 user-code seed 的内存收益变小；长执行函数的平均/P99 E2E speedup 仅 1.05×–1.14× / 1.07×–1.15×（§6.2，Fig. 11c）。

## 实验与结果

- **Sequential E2E**：相对 CataOnly，短 initialization/execution functions 的 average/P99 speedup 为 3.76×–6.68× / 6.31×–11.74×；长 user-code initialization 为 4.09×–31.48× / 6.19×–34.51×，长 execution functions 仅 1.05×–1.14× / 1.07×–1.15×（§6.2，Fig. 11；单台 24-core Xeon、512GB，Function-Bench/SeBS，每函数 sequential 1 分钟）。
- **Concurrency**：JS workload、concurrency 1–24 下，AFaaS E2E / cold-start 为 16.34–39.56 / 6.97–14.55 ms，CataOnly 为 51.32–117.92 / 38.39–74.05 ms（§6.2，Fig. 12；每系统 400 samples，同一单机）。
- **Seed memory**：相同 user code 的 level-2 seeds 相对 CataOnly 节省 28.11%–84.91% memory；VP/IR 等大 user code 收益较小（§6.5，Fig. 17；只测 seed memory，不代表 fleet-level cost）。
- **Production functions**：8 个 Node.js functions 的一日 server-side 平均中，startup latency 为 5.45–9.41 ms，average E2E 相对 CataOnly 为 1.80×–8.14×（§6.6，Table 2，Fig. 18）。AFaaS 为线上统计；CataOnly 在同硬件按相同 pattern 运行，但 peer responses 为 mocked，并非同时线上 A/B。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| AFaaS 显著降低短函数与长 user-init 函数的 E2E latency | §6.2, Fig. 11 | 单台 Xeon；Function-Bench/SeBS；sequential 1 minute；baseline CataOnly | strong |
| AFaaS 在 1–24 concurrency 下减少 JS E2E/cold-start latency | §6.2, Fig. 12 | 单机；wrk；JS；400 samples/system；baseline CataOnly | strong |
| Level-2 seeds 相对 CataOnly 节省 28.11%–84.91% memory | §6.5, Fig. 17 | selected functions；相同 user code；仅 seed memory | medium |
| 生产函数中 average E2E speedup 为 1.80×–8.14× | §6.6, Table 2, Fig. 18 | 8 Node.js functions；AFaaS online day；mocked CataOnly peer responses | medium |

## 批判性分析

### 论证链条

生产 trace 定位三 gap → FRI/池化/seed 树分别对应 → E2E 与并发稳定性提升。链条在 Ant 安全容器栈上闭合；泛化到其他云厂商需重实现 FRI 与 seed 策略。

### 假设压力测试

- 非 VM 隔离或不同 shim 架构时 FRI 收益未知。
- 多租户恶意 netns 共享若配置错误有隔离风险（论文有安全分析但生产误配仍危险）。
- 极冷函数（无 language seed 命中）回退到 root seed，延迟上升。

### 实验可信度

生产 trace + 18 个月部署是强项；对比含 Catalyzer 变体而非仅开源 stack；缺 AWS Lambda 等跨云对比。

### 系统性缺陷

论文未讨论：跨节点 seed 调度、函数版本滚动时 seed 失效、FRI 与 Kubernetes 生态标准化冲突。

## 局限与后续工作

- **局限 1**：深度绑定 Catalyzer/安全容器栈。
- **局限 2**：长执行函数 E2E 收益有限。
- **Future work 1**：跨节点 seed 共享（RDMA/CXL 类方案）与成本模型。
- **Future work 2**：FRI 标准化与多 runtime 插件生态。

## 相关

- **同类系统**：AWS Lambda、Catalyzer、Firecracker、gVisor、RunD
- **同会议**：[[OSDI-2025]]
