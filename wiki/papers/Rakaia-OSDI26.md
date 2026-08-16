---
type: paper
name: Rakaia
full_title: "Rakaia: Scalable In-Kernel Scheduling for TCP-Based RPCs"
authors: [Rui Yang, Konstantinos Prasopoulos, Edouard Bugnion]
venue: OSDI
year: 2026
tags: [rpc, tcp, kernel, scheduling, head-of-line-blocking]
source_pdf: "[[osdi26-yang-rui.pdf]]"
source_md: "[[osdi26-yang-rui]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# TCP RPC 的可扩展内核内调度（OSDI 2026）

> **原题**：Rakaia: Scalable In-Kernel Scheduling for TCP-Based RPCs

> **一句话总结**：Rakaia 认为 TCP RPC 的核心错配是 userspace 只看到“每连接 byte stream”，而调度真正需要“跨连接的完整 message”；它在 Linux receive softirq 中解析 Memcached/HTTP/2 message，用每核 FIFO、power-of-two choices 与 work stealing 做全局 work-conserving scheduling，在 20-thread 单机实验中相对 KCM 的 throughput-under-SLO 最多提高 5 倍，gRPC-Go/C++ 最多提高 1.56/2.69 倍，但 TLS、协议覆盖和 kernel parser 安全仍是明显边界。

## 问题与动机

[[TCP]] 给 POSIX userspace 暴露按 connection 排序的 byte stream，而 [[RPC]] 是离散 message。一个 thread 固定服务一批 connection 时，某连接变忙会造成跨连接负载不均；一个 connection 同时含多个 RPC 时，慢 request 又会挡住后面的 request。前者是 inter-connection head-of-line blocking，后者是 intra-connection HOL。增加 connection 数可以缓解这两类问题，却会把 fd、thread/goroutine 和同步成本推高。

[[gRPC]] 在 userspace 用 I/O thread、HTTP/2 stream reassembly、work queue 和 worker pool 近似 message-level scheduling。这样能并发执行同一 TCP connection 上的 RPC，却引入 context switch、queue synchronization 和 runtime scheduling。论文测到 gRPC-Go 从 80 增至 5,000 connection 时，goroutine 由约 1,077 增到 16,946，throughput-under-SLO 反而下降 11%（表 2、§5.3）。

改用 Homa、eRPC 或 userspace network stack 可以天然按 message 调度，但需要换 client、transport、硬件或基础设施。Linux KCM 保留 TCP wire compatibility，也在 kernel 用 strparser 找 message boundary；可它仍按每条 TCP connection 向 thread 分发，T 个 thread、C 条 connection 要创建 `T×C` 个 KCM socket，既有跨连接 HOL，又难扩展。Rakaia 的目标是在不改 client 和 TCP wire protocol 的前提下，把调度单位真正降到 message。

## 关键观察 / 隐含假设

- **观察 1：message-shared FIFO（MS）才是 work-conserving 的 queue model。** 离散事件模拟中，connection-partitioned FIFO 同时受两类 HOL，connection-shared FIFO 仍受 connection 内 HOL；MS 让任意 idle worker 取下一条完整 message，p99 latency 最低（图 1–2）。
  - **依赖假设**：request 可以在 message 完整到达后脱离原 connection 并发处理，protocol 允许 response 按 request/stream ID 匹配。
  - **可能失效场景**：应用要求同连接严格串行副作用，或 handler 共享未同步状态时，out-of-order execution 可能改变应用语义。
- **观察 2：connection/core 比越高，纯 HOL 收益越小，系统开销越重要。** 20 connection、bimodal 100-µs task 时 Rakaia 约 160 KQPS、TCP-CS 约 40 KQPS；5,000 connection 时 TCP-CS 已接近 MS，Rakaia只剩约 7% 优势（图 7）。
  - **依赖假设**：in-kernel parsing、queueing 和 stealing 的固定成本必须低于 userspace 协调成本，才能在高 connection 数仍有净收益。
  - **证据强度**：强。模拟与三档 connection 数的实机曲线趋势一致。
- **观察 3：TCP receive softirq 是最早可同时看到有序 byte 和 kernel scheduling state 的位置。** 在这里解析后可直接把 message 交给空闲 worker，避免重新唤醒 userspace I/O layer（§3）。
  - **依赖假设**：message length/结束标记能由受信任的 bounded parser 从 header 得到；encrypted traffic 必须先在 kernel 变回 plaintext。
  - **可能失效场景**：userspace TLS、完全 offload TCP 的 SmartNIC、无长度 framing 或复杂动态 protocol 都不能直接使用当前路径。
- **假设 1：run-to-completion FIFO 足以表达目标 SLO。** Rakaia 只决定哪条 ready message 给哪个 worker，不抢占已经运行的长 handler，也没有 priority/deadline/fairness policy。
  - **证据强度**：中。固定、exponential、bimodal 和 TPC-C 覆盖 service-time variation，但没有多 tenant priority 或 overload shedding。

## 核心方法

每个 application worker 创建一个 `AF_RAKAIA` message socket，所有 TCP connection 仍由原 Linux stack 维护。Server accept connection 后调用 `rakaia_attach`，把现有 TCP socket 与 protocol parser 关联；userspace 之后只对自己的 Rakaia socket 调 `recvmsg/sendmsg`，不用为每条 TCP connection 维护 fd 或 I/O thread。当前内建 Memcached binary protocol 与 HTTP/2 parser（表 1、§3.2）。

Receive path 复用 KCM 的 strparser。Memcached 直接从 fixed header 读 payload length；HTTP/2 parser 读取 stream ID、length、type 和 flag，用 per-stream hash table 聚合多个 frame，收到 `END_STREAM` 后才形成完整 RPC。PING、WINDOW_UPDATE 等 gRPC 用到的 control frame 也直接在 kernel 处理。每条 message 的首个 skb 隐藏对应 `rakaia_psock` pointer，worker 收到后 socket 内部缓存它，后续 response 可回到原 TCP connection，而 userspace 不接触 connection identity（图 4–5、§3.3）。

论文口中的“逻辑集中 message queue”在物理上不是单个全局锁队列。每个 Rakaia socket/core 有本地 FIFO；新 message 用 power-of-two choices（P2C）随机看两个 queue，进入更短者。若目标 worker idle 就直接 handoff；worker 先取本地 queue，空时通过 non-empty bitmap 找 victim 并 stealing。这样在 light load 少排队，在 heavy load 分散 contention，同时保持“系统里有 ready message 就不让 worker 空闲”（图 4）。

Transmit path 要解决多个 worker 同时回同一 TCP socket 的 lock contention。每条 response 先独立分配 skb，放入该 `rakaia_psock` 的 virtual send queue。第一个看到 `tx_in_use=false` 的 sender 成为 delegated transmitter，拿一次 TCP socket lock，把期间积累的 skb 批量移到真正 send buffer 并 `tcp_push`；其他 sender 只 enqueue 后返回。Transmitter 反复检查 virtual queue，清空后才释放 ownership（算法 1、§3.4）。独立 skb 多一次 allocation，却简化 partial-copy failure 与内存回收。

TLS 通过 [[kTLS]] 组合：handshake 仍在 userspace，session key 交给 kernel；receive 侧先解密 TLS record，再给 strparser 看 plaintext，send 侧反向加密。当前 kTLS 不能安全地在并发 softirq 中解密，Rakaia 暂时把工作交给 Linux workqueue，因此有额外 scheduling bottleneck（图 6、§3.5）。普通 OpenSSL/userspace TLS 无法让 kernel parser 看见 message。

实现是 Linux 6.8 上约 3,000 行 C 的动态 kernel module，另有约 60 行 kernel patch 注册新 socket type；没有改变 TCP wire semantics。作者还修改 gRPC-Go 1.75.0 与 gRPC-C++ 1.78.1，把 server receive/send path 接到 Rakaia。Client 无需修改，但 server kernel 与 RPC runtime 都需要部署相应代码（§4–§5.1）。

## 设计取舍

- **保留 TCP 换部署兼容性**：继承成熟 congestion control、TSO/GSO/GRO、client 与 PKI；也继承丢包导致的 transport-level HOL 和 incast 问题。
- **把 HTTP/2 control plane 下沉 kernel 换少 syscall/context switch**：性能更好，但扩大 kernel attack surface，protocol bug 可能影响整机而非单个 process。
- **分布式近似全局 queue 换扩展性**：P2C 和 stealing 避免 global lock，却不能保证严格 FIFO 或绝对最短队列，只保证近似均衡与 work conservation。
- **每 response 独立 skb 换简单 failure path**：避免批量 copy 的复杂回滚，可能放弃同 connection response 合并带来的 allocation/packetization 优势。
- **kTLS 换 kernel plaintext 可见性**：保留 end-to-end encryption，但当前 workqueue 解密削弱短任务收益，且 Go gRPC 还不能组合 kTLS。
- **边界条件**：大量独立、短、CPU-bound RPC 且 server 可改 kernel 时最适合；长计算、网络瓶颈、userspace TLS 或 full TCP offload 环境收益受限。

## 实验与结果

- **设置与 metric**：CloudLab xl170 server 使用单颗 10-core Intel Xeon E5-2640v4 2.4 GHz，开启 hyperthread、共 20 hardware thread，Ubuntu 24.04/Linux 6.8。扩展 Lancet client 一次建立 20/80/5,000 条 connection，以 Poisson open-loop 发送；报告 client 端 p99 latency–achieved load 曲线。Synthetic handler 为 20 或 100 µs，service time 取 fixed、exponential 或 90% 半均值加 10% 5.5 倍均值的 bimodal；实验均为 compute-bound。基线含 TCP-CP、TCP-CS、调优后的 userspace Worker Pool、KCM、gRPC-POSIX（§5.1）。
- **Queue model 与 connection scaling**：100-µs、20-connection 下，Rakaia 三种分布都约维持 160 KQPS；bimodal 时 TCP-CS 约 40 KQPS、KCM 约 30 KQPS，Rakaia 分别约为 4 倍和 5 倍。到 5,000 connection，TCP-CS 因 HOL 被连接数稀释而接近理论 MS，Rakaia仍高约 7%；说明它的最大收益在低 connection/core、service variance 高的区域（图 7、§5.2）。
- **细粒度任务**：20-µs、80-connection 时，userspace Worker Pool 对 I/O/worker 配比和 service distribution 很敏感，KCM 甚至落后 TCP-CP/CS；Rakaia 在 fixed、exponential、bimodal 三种曲线中都保持更晚的 p99 latency 上升。论文没有给单一 speedup，而用完整 latency–load 曲线证明固定开销较低（图 8）。
- **gRPC**：gRPC-Go 在 80 connection 时，Rakaia 比 POSIX 多承受 39% load；5,000 connection 时优势增到 1.56 倍。170 KQPS 下，gRPC-POSIX-5000 有 16,946 goroutine，Rakaia-5000 只有 33；kernel CPU time 仅增加 1.8 percentage point，userspace time 减少 22.7 point。gRPC-C++ 相对 async/callback API 在 80 connection 提高 2.00/2.33 倍，在 5,000 connection 提高 2.69/2.67 倍（图 9、表 2、§5.3）。
- **TLS 边界**：100-µs task 下 Rakaia-kTLS 约 120–130 KQPS，略低于 TCP-CS/Worker Pool TLS 的约 130–140 KQPS；20-µs 下约 320–340 KQPS，也低于 TCP-CS-TLS 的约 380 KQPS，但高于未为 TLS 重调的 Worker Pool TLS（约 200–220 KQPS）。gRPC-Rakaia 没有进入 TLS 实验，因为 Go standard library 尚不支持 kTLS（图 10、§5.4）。
- **应用结果**：Silo TPC-C 在 500-µs p99 SLO 下，裸 Rakaia 为 350 KQPS，TCP-CS 为 309 KQPS，Worker Pool 为 299 KQPS；gRPC-Rakaia 对 Silo 在 80/5,000 connection 分别提高 1.25/1.39 倍。OpenTelemetry no-op exporter 在 2-ms p99 SLO 下从 142 提到 192 KQPS（1.35 倍）；接 Jaeger 后从 92 提到 131 KQPS（1.42 倍），但 backend export client path 未被 Rakaia 加速（图 11–12、§5.5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Message-level scheduling 消除两类 queue HOL | 图 2、图 7 | Poisson arrival；20 thread；三种 synthetic service distribution | 强 |
| Rakaia 比 KCM 更 work-conserving 且可随 connection 扩展 | 图 7–8 | 20/80/5,000 connection；20/100-µs CPU task | 强 |
| 下沉调度能减少 gRPC runtime overhead | 图 9、表 2 | gRPC-Go/C++；80/5,000 connection；170-KQPS CPU breakdown | 强 |
| Rakaia 能改善更真实的 RPC frontend | 图 11–12 | 简化 Silo TPC-C、OpenTelemetry no-op/Jaeger | 中 |
| TLS 可组合但当前实现仍有性能瓶颈 | 图 10、§5.4 | kTLS microbenchmark；未评 gRPC-Rakaia TLS | 强 |

## 批判性分析

### 论证链条

论文先用零系统开销的 queue simulation 分离 HOL 本身，再用实机观察同样的 connection-scaling 趋势，最后把收益带到 gRPC 和两种应用，论证很扎实。设计也确实同时满足“尽早得到 message”和“不要单个 global lock”：strparser 回应语义恢复，per-core P2C/stealing 回应 scheduling scalability。缺少的是组件级消融；论文没有分别关闭 direct handoff、stealing、P2C 或 TX delegation 来量化各自贡献，因而“receive scheduling”和“send contention reduction”的收益未完全拆开。

### 假设压力测试

Rakaia 最适合独立、run-to-completion request。如果应用依赖同 connection handler 顺序、需要 priority/deadline 或长任务抢占，当前 FIFO 可能仍产生 application-level queueing。5,000 connection 时 TCP-CS 已只落后约 7%，表明 connection 足够多时核心 opportunity 缩小。Payload 较大、NIC/network 饱和后，实验中的 CPU-bound 结论也可能改变。协议必须有 kernel 可解析的边界；userspace TLS、custom compression/framing 或 SmartNIC full TCP offload 都会挡住这条路径。

### 实验可信度

理论曲线、六种 synthetic workload、五类 baseline、两个 gRPC 实现、Silo 与 OpenTelemetry 形成很完整的梯度，p99-vs-load 也比单点 throughput 更可靠。但所有结果来自一台 20-hardware-thread 老款 Xeon server，没有验证更多 core、[[NUMA|NUMA]]、多 socket、100-Gbps NIC 或多 tenant。Worker Pool 的 unencrypted 参数做过 sweep，而 TLS 实验沿用未加密配置，因而 Rakaia 对它的 TLS 优势不宜过度解读。Silo 关闭 garbage collection 且省略 SQL marshalling，只是较真实的 handler distribution；论文也只报告 p99，没有 p99.9、failure 或 overload stability。

### 系统性缺陷

把 Memcached/HTTP/2 frame parsing、flow control、PING 和 WINDOW_UPDATE 放进 kernel 会显著扩大可攻击面；论文没有 malformed-frame fuzzing、memory bound、tenant isolation 或 parser verifier。Server 要安装 module、约 60 行 kernel patch并修改 gRPC runtime，虽然 client 和 wire protocol 不变，仍不是无修改部署。当前只支持两类 parser，新增协议需 kernel/eBPF extension。kTLS workqueue 已是实测瓶颈；TCP packet loss HOL、sender-driven incast 和 full-offload SmartNIC 不兼容则是架构边界。Scheduler crash、queue backpressure、worker failure 与 observability 均未讨论。

## 局限与后续工作

- **局限 1**：只评 20 hardware thread 的单机 CPU-bound server，不能证明 scheduler 在 64–256 core、NUMA 或 network-bound workload 上仍扩展。
- **局限 2**：当前 parser 仅覆盖 Memcached binary protocol 和 gRPC 所需 HTTP/2；kernel parser 安全性未系统评测。
- **局限 3**：TLS 依赖 kTLS，Go gRPC 尚不可用，softirq 不能并发解密使 workqueue 成为瓶颈。
- **局限 4**：保留 TCP 意味着 packet-loss HOL 与 incast 不会消失；FIFO run-to-completion 也没有 priority、deadline 或 preemption。
- **后续工作 1**：对 HTTP/2/Memcached parser 做 coverage-guided fuzzing、形式化 length/buffer bound 检查和多 tenant resource accounting。
- **后续工作 2**：在 64/128/256 core、双 NUMA 和 25/100/200-Gbps NIC 上分解 parse、P2C、stealing、syscall 与 TX delegation 成本。
- **后续工作 3**：实现 safe softirq kTLS decryption 并接入 gRPC-Go，按相同调优预算重测 Rakaia、TCP-CS 与 Worker Pool TLS。
- **后续工作 4**：加入 bounded priority/deadline queue 和 long-handler preemption，测量 fairness、p99.9、overload recovery 与 starvation。

## 相关

- **相关概念**：[[RPC]]、[[TCP]]、[[Head-of-Line-Blocking]]、[[Work-Conserving-Scheduling]]、[[Kernel-Networking]]
- **相关系统**：[[gRPC]]、[[KCM]]、[[Homa]]、[[eRPC]]、[[kTLS]]
- **相关机制**：[[RSS]]、[[HTTP2]]、[[io_uring]]、[[eBPF]]
- **同会议**：[[OSDI-2026]]
