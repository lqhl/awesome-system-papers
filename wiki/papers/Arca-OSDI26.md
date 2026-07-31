---
type: paper
name: Arca
full_title: "Continuation-Centric Computing with Arca"
authors: [Akshay Srivatsan, Yuhan Deng, Katherine Mohr, Emma Sudo, Sebastian Ingino, Francis Chua, Keith Winstein]
venue: OSDI
year: 2026
tags: [operating-system, serverless, continuation, isolation]
source_pdf: "[[osdi26-srivatsan.pdf]]"
source_md: "[[osdi26-srivatsan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# Arca：以 continuation 为中心的计算范式（OSDI 2026）

> **原题**：Continuation-Centric Computing with Arca

Arca 将可序列化、可迁移的 continuation capture 做成 OS syscall，使普通程序能在 I/O 边界把“剩余计算”变成新函数，而不必由开发者预先手写 serverless DAG。

## 问题与动机

serverless 希望以毫秒级 task 精细调度，但现有 Linux process/VM snapshot 要数百毫秒；WebAssembly 启动快却缺少通用 continuation。开发者因此必须把程序人工改写为 CPS 和多个 pure functions，显式传递中间状态。Arca 探索 OS 能否在几微秒内捕获 future，让 provider 按实际 I/O dependency 放置后续计算。

## 关键观察 / 隐含假设

### 关键观察

- 短任务的大量时间用于等待外部服务；在每次 effect/I/O 处结束当前 funclet 并序列化 continuation，可避免占用 sandbox。
- continuation 通常只需保存 private process state，使用 copy-on-write/zero-copy 内存即可比完整 process checkpoint 更轻。
- 把 I/O 表达为“effect + callback continuation”能保持计算纯化，让外部 handler 决定本地执行、迁移或复制。

### 隐含假设

- workload 是短生命周期、I/O/compute 交替且 working set 随阶段变化；长期稳定服务收益有限。
- 应用不依赖 mutable shared memory、复杂线程、持久 socket state 或完整 Linux ABI。
- provider 控制 Arca host 与 effect handler，可安全序列化和恢复 continuation。

## 核心方法

### Arca process 与 effect

Arca process 具有硬件内存保护和 Unix 类计算语义，但外部副作用不直接 syscall；程序返回 effect 描述及 callback。handler 执行 I/O 后恢复 callback continuation。

### Continuation 捕获

kernel syscall 捕获寄存器、页表/内存映射和运行状态，生成可暂停、迁移或复制的 serialized continuation。内存驻留时采用 zero-copy，跨机时只发送 continuation 所需状态。

### 兼容层（Compatibility layer）

修改的 musl libc 把常用 open/read/write/socket 等 POSIX API 翻译为 effects，使部分 C/C++ 程序无需完全重写；目前最复杂 port 是 FFmpeg。

## 设计取舍

- 取消直接 kernel I/O 让 continuation 边界清晰，却打破完整 POSIX compatibility。
- 不支持 mmap、shm_open、clone 等 mutable shared memory，简化 serializability 但排除大量 server 软件。
- 新 OS 能把 snapshot 降到微秒级，部署成本远高于扩展 Linux/container runtime。
- continuation 比输入数据小时迁移有利；反之发送 execution state 未必比发送 data 更便宜。

## 实验与结果

- 128-way 创建/销毁中，Arca process 平均 32.2 µs，WebAssembly 为 110 µs，Linux process 为 540,000 µs，MicroVM 为 742,000 µs（§6.2.1，表 1）。
- Arca continuation snapshot/resume 为 2.55 µs，相比 Linux process checkpoint 的 283,000 µs 与 MicroVM 的 217,000 µs 低约五个数量级。
- 128×128 matrix multiply open-loop workload 中，Arca 在 p95 latency 约束下处理约 18,000 requests/s；Linux process 技术约 10,500 requests/s，MicroVM 在 500 requests/s 已达 42 ms p95。
- image thumbnail workload 中，传统方式 throughput 为 9.42 requests/s，continuation-centric Arca 为 557.3 requests/s，提高约 59 倍；传统方案 98% 时间传图像，Arca 只约 9% 时间传 continuation/data。
- Arca computational request throughput 与 in-process isolation 接近，并比 process-based techniques 高约一个数量级；优势主要来自隔离创建和 zero-copy capture。
- compatibility 仅覆盖部分 POSIX，作者明确称 prototype 有重大限制；性能结果不能外推到未移植的大型多线程应用。

## 论断—证据表

| 论断 | 机制 | 证据 | 边界 |
|---|---|---|---|
| continuation 可成为微秒级 OS primitive | 内核原生 capture 与 zero-copy | snapshot/resume 2.55 µs | 新 OS，功能远少于 Linux |
| continuation-centric 可自动暴露细粒度 DAG | effect + callback | thumbnail throughput 提高约 59 倍 | continuation 必须明显小于移动的数据 |
| 硬件隔离不必牺牲 WebAssembly 级启动速度 | 轻量 Arca process | create/destroy 32.2 µs | 安全模型和攻击面未充分评估 |
| 部分传统程序可迁移 | musl POSIX adapter | 已 port FFmpeg | 无 shared memory/clone，兼容性有限 |

## 批判性分析

### 论证链条

Arca 先以现有 isolation snapshot latency 说明 continuation 不能只是 checkpoint API，再通过新 OS 证明微秒 capture 可行，最后用 data-vs-code migration workload 展示新抽象的系统价值。thumbnail 的 59 倍结果鲜明，但也刻意选择 continuation 很小、input 很大的理想情形。

### 假设压力测试

如果 continuation 包含大 heap、open connection 或外部 mutable state，捕获和迁移成本会急增，effect purity 也会破裂。shared memory、thread synchronization 和 exactly-once effect 在 crash recovery 时如何处理，决定该范式能否支持真实应用。

### 实验可信度

微基准、open-loop compute、thumbnail 与 compatibility 评估能回答 prototype 可行性。缺少多租户安全、cold storage continuation、跨机故障、网络拥塞、真实 FaaS trace 与成本比较；Linux checkpoint 数字也不是最优化 serverless snapshot 的全部代表。

### 系统性缺陷

Arca 的性能来自舍弃大量 Unix state，而 continuation-centric API 与现有生态的兼容张力是根本问题，不只是工程 backlog。effect handler 成为新的可信 I/O kernel 与 durability coordinator，论文尚未给出完整一致性语义。

## 局限与后续工作

- 定义 crash/retry 下 effect 与 continuation 的 exactly-once/at-least-once 语义。
- 支持或显式替代 threads、shared memory、mmap 与长期 socket state。
- 在真实 FaaS trace 上测量 continuation size、remote resume p99 与 storage cost。
- 系统化评估 isolation、安全攻击面和恶意 continuation validation。

## 相关

- [[Serverless-Computing]]
- [[Continuation]]
- [[Process-Checkpointing]]
- [[WebAssembly]]
