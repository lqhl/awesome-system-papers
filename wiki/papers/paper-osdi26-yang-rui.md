---
type: paper
name: Rakaia
full_title: "Scalable In-Kernel Scheduling for TCP-Based RPCs"
authors: [Rui Yang, Konstantinos Prasopoulos, Edouard Bugnion]
venue: OSDI
year: 2026
tags: [rpc, tcp, kernel, scheduling, hol-blocking, grpc]
source_pdf: "[[osdi26-yang-rui.pdf]]"
source_md: "[[osdi26-yang-rui]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向 TCP RPC 的可扩展内核调度（OSDI 2026）

> **原题**：Scalable In-Kernel Scheduling for TCP-Based RPCs

> **一句话总结**：TCP 只提供按连接组织的字节流，导致 RPC 在连接内外发生队头阻塞；Rakaia 在 Linux TCP 接收路径中解析消息，并用跨连接的每核队列和 work stealing 调度，使服务端接近消息共享 FIFO，在 20 个连接、100µs 任务上约达到 TCP-CS 的 4 倍吞吐，并将 gRPC-Go/C++ 的 throughput-under-SLO 分别提高至多 1.56×/2.69×。

## 问题与动机

RPC 是消息通信，但 POSIX TCP API 暴露的是按连接排列的字节流。一个慢请求会阻塞同一连接上的后续请求；不同连接固定分配到不同线程时，连接间的请求不均衡又会让部分 CPU 空闲。gRPC 在用户态重建消息边界，依靠 I/O 线程、工作队列和 worker pool 近似消息级调度，但这引入了线程切换、同步和运行时调度开销。

已有的消息型传输或用户态网络栈可以绕开这些问题，却需要定制客户端、网络栈或硬件。KCM 已把 TCP 消息解析移入内核，但仍把消息绑定到原 TCP 连接，无法在连接之间实现真正的 work conservation。Rakaia 的目标是在保持 TCP/TLS 兼容性的同时，把消息解析和调度提前到内核 TCP 接收路径。

## 关键观察 / 隐含假设

- **观察 1：连接级队列无法稳定逼近消息共享队列。** 离散事件模拟显示，connection-partitioned FIFO 同时遭受连接间和连接内队头阻塞；connection-shared FIFO 仍会遭受连接内队头阻塞，且效果强烈依赖连接数（图 2）。
  - **依赖假设**：RPC 服务时间存在不均匀性，且少量连接可能承载并发请求。
  - **可能失效场景**：所有请求服务时间近似固定，或连接数足够大且请求均匀时，连接级模型与消息级模型的差距会缩小。
- **观察 2：用户态重建消息语义的成本在短任务和高连接数下占比上升。** gRPC-Go 在 80 个连接时约有 1,077 个 goroutine，在 5,000 个连接时约有 17,000 个；调度和栈管理开销随之增加（图 9、表 2）。
  - **证据强度**：强。论文给出了不同连接数下的 CPU 时间分解和吞吐曲线。
- **假设 1：内核能够在接收 softirq 路径中安全、低开销地完成协议解析。** 这要求协议有可识别的消息边界，且解析状态不会造成不可控的内核内存或锁竞争。
  - **可能失效场景**：复杂协议、超大消息、恶意输入或需要大量状态的协议可能放大内核解析成本。
- **假设 2：保留 TCP 的可靠有序传输比采用定制消息传输更适合部署。** 该选择牺牲了丢包后的跨消息进展能力，也继承了 TCP 在 incast 场景中的拥塞控制限制。

## 核心方法

Rakaia 将每条 TCP 连接挂接一个协议解析器，在内核 TCP 接收路径中把字节流重组成完整消息。Memcached 使用长度字段和 opaque 字段；HTTP/2 则按 stream ID 缓存 frame，在收到 END_STREAM 后组装 RPC 消息。PING、WINDOW_UPDATE 等 gRPC 控制帧也在内核处理，减少用户态往返。

解析出的消息不再绑定原 TCP 连接。Rakaia 向每个应用线程暴露一个 connection-oblivious 的消息 socket；消息进入每个 socket 的本地 FIFO 队列，调度器用 power-of-two choices 将其放入两个候选队列中较短者。空闲 worker 通过直接交接获得新消息，队列为空时从其他非空队列窃取任务。这样得到逻辑集中、物理分布的消息队列，避免单一全局锁。

响应发送需要找到消息原属 TCP 连接。Rakaia 将 `rakaia_psock` 指针随消息保存，用户态发送时仍只操作 Rakaia socket。多个 worker 同时向同一 TCP socket 发送时，消息先进入无锁化目标为主的暂存队列；一个线程取得发送资格并批量转入 TCP 写队列，其他线程立即返回，降低 TCP socket lock 的竞争。

实现是 Linux v6.8 上约 3,000 行的动态内核模块，另需约 60 行注册新 socket 类型的补丁。Rakaia 复用 Linux TCP 栈、GRO/TSO/GSO 等优化，并通过 kTLS 支持加密流量。

## 设计取舍

- **内核解析换取用户态开销下降**：I/O 线程、消息 demultiplexing 和工作队列被移除，但协议解析、HTTP/2 状态和内存压力进入内核，扩大了内核代码的安全与维护边界。
- **每核队列换取可扩展性**：P2C 和 stealing 避免全局队列锁，但调度不再是严格的全局 FIFO，未来的优先级、租户隔离和公平性策略需要额外设计。
- **独立 skb 换取故障路径简单**：每条消息单独复制，避免共享 skb 在部分失败时的回收复杂度；代价是可能增加 skb 分配和复制开销。
- **保留 TCP 换取部署兼容性**：Rakaia 不能消除 TCP 丢包导致的传输级队头阻塞，也不适用于完全由 SmartNIC 卸载 TCP 的部署。

## 实验与结果

- 在 100µs 任务、20 个连接的场景，Rakaia 约维持 160 KQPS；TCP-CS 在 bimodal 服务时间下约 40 KQPS，Rakaia 约为其 4 倍（图 7）。
- 连接数从 20 增至 5,000 时，Rakaia 仍接近理论消息共享队列；即使 5,000 个连接，仍比 TCP-CS 高约 7%（图 7）。
- 在 20µs 任务、80 个连接时，用户态 Worker Pool 对服务时间分布更敏感；KCM 甚至低于 TCP-CS，而 Rakaia 保持优势（图 8）。
- gRPC-Go 的 throughput-under-SLO 至多提高 1.56×；gRPC-C++ 的 async/callback API 在 5,000 个连接下分别提高 2.69×/2.67×（图 9）。
- kTLS 会因 workqueue 解密形成瓶颈；当前实现仍能工作，但软中断内安全解密尚未成熟（图 10）。
- Silo 的 TPC-C 工作负载在 5,000 个连接下提高 1.39×；OpenTelemetry Collector 在 Jaeger 后端配置下从 92 KQPS 提高到 131 KQPS，即 1.42×（图 11、图 12）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 消息级调度能减少连接内外队头阻塞 | 模拟与实测，图 2、图 7 | 20 核服务器；合成服务时间；20–5,000 连接 | 强 |
| Rakaia 的内核路径开销低于用户态消息管线 | gRPC CPU 分解，表 2；连接扩展，图 9 | gRPC-Go/C++；最多 5,000 连接；20 线程 | 强 |
| Rakaia 能改善真实 RPC 应用 | Silo/TPC-C 与 OpenTelemetry，图 11、图 12 | 两个应用；特定硬件和 SLO | 中 |
| TCP 兼容性同时保留了传输级限制 | 讨论 §6；未给出与 Homa/QUIC 的统一对照 | 未系统评估 incast、丢包和 WAN | 中 |

## 批判性分析

### 论证链条

论文的主链条较完整：队列模型说明连接级调度的结构性问题，Rakaia 将消息解析和调度放在 TCP 接收路径，微基准验证其接近消息共享模型，gRPC 和真实应用验证用户态收益。实验还覆盖了任务时长、连接数、服务时间分布和 TLS，能支撑“减少用户态协调开销”的结论。

但“适合生产部署”的外推仍有限。评测集中在单机服务端和受控连接数，未覆盖跨机架网络、丢包、连接 churn、恶意协议输入、内存压力或多租户隔离。Rakaia 的内核模块对协议和 HTTP/2 控制面承担更多责任，这些运维与安全成本没有用实验量化。

### 假设压力测试

当请求服务时间更短、服务时间方差更大或连接数较少时，Rakaia 的收益更可信，因为用户态固定开销和队头阻塞更容易暴露。反过来，固定服务时间、极高连接数或网络传输成为主导瓶颈时，收益可能收窄。kTLS 当前把解密放入 workqueue，说明“接收路径内完成全部工作”的假设受现有内核实现限制。

Rakaia 消除了 RPC 消息级队头阻塞，但不能消除 TCP 的按序交付约束。单条连接丢包仍会阻塞该连接上的后续字节；多连接只能缓解而不能改变这一传输语义。

### 实验可信度

基线包括 TCP-CP、TCP-CS、Worker Pool、KCM 和 gRPC 的多种 API，且使用理论 M/G/20 曲线作参考。消融覆盖连接数和服务时间分布，CPU 分解也直接对应论文关于用户态调度开销的解释。缺口在于没有统一比较 QUIC、Homa 或用户态网络栈，也没有报告内核内存占用、解析失败、故障恢复和长期运行稳定性。

### 系统性缺陷

协议解析器目前以内核模块形式提供，新增协议需要内核代码或未来的 eBPF 扩展。内核解析错误可能比用户态解析错误带来更高的故障影响面。论文未讨论版本兼容、模块升级、观测工具、租户公平性和资源配额。调度器目前主要优化吞吐和尾延迟，尚未展示优先级 SLO、请求取消或请求级 deadline 的实现。

## 局限与后续工作

- **局限 1**：kTLS 解密仍通过 workqueue，TLS 路径未达到非 TLS 路径的软中断集成程度。
- **局限 2**：Rakaia 继承 TCP 的丢包队头阻塞、发送方拥塞控制和 incast 弱点。
- **局限 3**：当前支持的协议解析器主要是 Memcached 和 HTTP/2/gRPC，内核协议扩展和安全边界尚未充分评估。
- **后续工作 1**：在受控丢包率、不同 RTT 和 incast 规模下，比较 Rakaia、QUIC、Homa 和 gRPC 的 P99/P999 延迟及恢复时间。
- **后续工作 2**：加入 deadline/priority 调度，测量 P99 SLO、租户公平性和队列状态开销，而不只比较 FIFO throughput-under-SLO。
- **后续工作 3**：实现安全的 softirq kTLS 解密，并分别报告 CPU、内存、skb 分配和协议解析成本。

## 相关

- **相关概念**：[[TCP]]、[[HOL Blocking]]、[[Work Stealing]]、[[kTLS]]
- **同类系统**：[[gRPC]]、[[KCM]]、[[Homa]]、[[QUIC]]
- **同会议**：[[OSDI-2026]]
