---
type: paper
name: KernelBypassTCP
full_title: "Opening Up Kernel-Bypass TCP Stacks"
authors: [Shinichi Awamoto, Michio Honda]
venue: ATC
year: 2025
tags: [networking, tcp, kernel-bypass, dpdk, benchmarking, datacenter-rpc]
source_pdf: "[[atc2025-awamoto.pdf]]"
source_md: "[[atc2025-awamoto]]"
---

# Opening Up Kernel-Bypass TCP Stacks (ATC 2025)

> **一句话总结**：这篇论文把 Linux、mTCP、F-Stack、IX、TAS、Demikernel 放到同一 nophttpd 和 25GbE 测试台上，关键观察是 [[Kernel-Bypass]] TCP 的优势强依赖 workload 和 execution model：Linux 单连接 2 MB bulk transfer 到 14.69 Gb/s、64 B unloaded RTT 也有 17 us，而 IX 在并发 RPC 吞吐上领先 30-684%，所以还不存在同时覆盖 bulk transfer、small RPC、高连接数和多核扩展的通用 kernel-bypass [[TCP]] stack。

## 问题与动机

论文要回答的问题不是“再提出一个更快的 TCP stack”，而是更基础的 operational question：如果一个团队想在 datacenter 或 cloud 里采用 kernel-bypass TCP，它到底应该相信哪类架构、在哪些 workload 上获益、需要付出多少应用改造和维护成本。已有论文通常只拿自己的系统对比 Linux 加一两个 baseline，而且会选择最能展示自身优势的 workload，导致运维者看不到同一批 stack 在 bulk transfer、small request-response、连接规模和多核扩展上的横向轮廓。

这个问题之所以重要，是因为 [[TCP]] 在生产里不是单纯的 packet pump。它和应用线程、文件描述符、资源 accounting、fault isolation、packet filter、queuing discipline、congestion control、loss recovery、TCP option negotiation、observability 工具都纠缠在一起。把 TCP 搬到用户态或者专用 datapath 之后，吞吐和延迟可能变好，但 Linux 内核长期积累的协议特性、调试工具和维护节奏也被一并拿掉。

作者的 claim 有明确边界：这是一张 2024 年左右、基于可运行 artifact 的 performance snapshot，而不是对所有 kernel-bypass 或 kernel-enhancement 技术的最终裁判。论文选择了 Linux、mTCP、F-Stack、IX、TAS、Demikernel 六个 stack，用统一硬件和统一 workload 重新测它们，重点观察架构选择如何影响基本 TCP server workload。

## 关键观察 / 隐含假设

- **观察 1**：没有一个 stack 同时覆盖大数据传输、小消息低延迟、高连接并发和多核扩展。
  - **证据**：Linux 在单连接 2 MB response 上达到 14.69 Gb/s，F-Stack 到 13.66 Gb/s；IX 和 Demikernel 在 bulk transfer 中落后，但 IX 在并发连接吞吐上比其他 stack 高 30-684%，并且在 16 核以内多核吞吐通常最好。Demikernel 64 B unloaded RTT 最低，为 13 us，但连接数升高后吞吐和尾延迟都不占优。
  - **依赖假设**：论文选择的四类 basic workload 能代表 operator 真正在乎的 TCP server 压力源。
  - **可能失效场景**：短连接、TLS、proxy/load balancer、混合 bulk+RPC、带真实 application compute 的 workload，或者 100/200/400GbE NIC 上的瓶颈，可能改变排序。

- **观察 2**：把 TCP 放到 [[DPDK]] 上并不自动赢过 kernel stack。
  - **证据**：F-Stack 使用 FreeBSD TCP over DPDK，但 bulk transfer 仍低于 Linux；perf 显示 Linux 和 F-Stack 在 TCP/IP/Ethernet protocol processing 上分别消耗 50.5% 和 52.5% CPU time，而按 request/s 换算后 Linux 的 TCP packet processing efficiency 比 F-Stack 高约 19.6%。并发连接测试里 F-Stack 和 Linux 吞吐接近，也削弱了“syscall overhead 是主要瓶颈”的简单解释。
  - **依赖假设**：F-Stack 的 FreeBSD TCP 和 DPDK integration 足够代表“继承成熟 kernel TCP 实现再放到用户态”的路线。
  - **可能失效场景**：如果 F-Stack 有未公开的生产分支、不同 DPDK/NIC 版本、或更适合 run-to-completion 的应用结构，结果可能更好。

- **观察 3**：execution model 和 API shape 本身就是性能机制。
  - **证据**：IX 的 run-to-completion 模型在并发 RPC 上强，但 bulk transfer 受 packet-level buffer API 和 ACK-clock interaction 影响；Demikernel 的 Rust coroutine 和 packet buffer API 给小消息带来低 unloaded latency，却因 single-threaded stack 无法测多核扩展；TAS 的 dedicated datapath thread 让 16 到 24 核吞吐提升 67%，但需要人工搜索 stack/application core split。
  - **依赖假设**：nophttpd 针对每个 stack 原生 API 优化后，剩下差异主要来自 stack 架构而不是应用实现失误。
  - **可能失效场景**：真实应用如果有共享状态、blocking I/O、复杂调度或 CPU-heavy request processing，run-to-completion 和 dedicated datapath 的相对优势可能重排。

- **假设 1**：禁用 [[TSO]] 是公平比较，而不是改变生产结论的关键干预。
  - **证据强度**：中。mTCP 和 Demikernel 不支持 TSO，所以禁用能避免让 Linux/F-Stack 因功能更全而在实验中“天然获利”；但 production Linux 往往会开启 TSO、GSO 或 BigTCP，bulk transfer 结论可能低估了成熟 kernel stack 的真实优势。

- **假设 2**：25GbE、两台机器 back-to-back、8 秒 benchmark 足以暴露关键架构差异。
  - **证据强度**：中。四类 workload 的结果差异很大，说明 benchmark 能区分架构；但论文没有覆盖多 NIC、leaf-spine fabric、长时间稳定性、功耗、failure recovery 和多租户隔离。

## 核心方法

论文的核心方法是构造一个“尽量少应用噪声，但不强行统一 API”的 measurement harness。作者实现了 nophttpd，一个只从内存返回静态数据的最小 HTTP server。关键选择是不给六个 stack 套统一 wrapper，而是分别用各自最自然的 API 和 execution model 写 server：Linux 用 epoll，mTCP 用 socket-like API，F-Stack 用 callback/event 模型，IX 和 Demikernel 处理 packet-sized TX/RX buffer，TAS 通过 LD_PRELOAD 保持接近 POSIX 的应用接口。

这个选择直接回应了观察 3。统一 wrapper 看起来更整洁，但会把不同 execution model 压平成同一接口，从而人为惩罚某些 stack。相反，per-stack nophttpd 让每个 stack 尽量跑在“对自己友好”的应用结构上，代价是工程量更大，也暴露了真实 porting cost。

实验环境是两台相同服务器直连：Intel Xeon Gold 5418N Sapphire Rapids，Intel XXV710-DA2 25GbE NIC，Linux 5.18。作者关闭未用 CPU core，关闭 TSO 以兼容 mTCP 和 Demikernel，并把每个 benchmark 跑 8 秒。client 端使用修改过的 wrk，修掉原 wrk 在高线程数下 stat aggregation contention 的问题；多核 server 测试时，还会 downclock server core 来避免 client 先成为瓶颈。

workload 分四类：单连接 bulk transfer，其中 client 发小请求、server 返回最大 2 MB response；单连接小消息 unloaded latency，其中 response payload 为 64 B 起，关闭 interrupt moderation，并让 Linux 侧 busy-poll epoll event descriptor；并发连接吞吐和延迟，使用 100 到 1600 个 persistent TCP connection；多核扩展，使用 4800 个连接和 1 到 24 个 server CPU core。

被测 stack 的差异正是论文想解释的变量。mTCP 把 application thread 和 stack thread 成对放在同一 core 上，强调 lock-free 和 per-core partitioning，但要求 [[RSS]] hash、local port 和线程分配配合。F-Stack 把 FreeBSD TCP 移到 [[DPDK]] 上，每 core 一个 process，继承较完整的 TCP feature，但需要应用适配 callback 和共享内存。IX 用 run-to-completion 和低层 packet buffer API，论文实际采用 Reflex 里的 IX 版本以绕开原实现不稳定性。TAS 让用户态 datapath thread 负责 TCP fast path，应用通过 LD_PRELOAD 调用类似 POSIX 的接口，但作者为了公平测试还给它补了 Window Scaling 和 large window 支持。Demikernel 用 Rust coroutine 和 custom TCP/IP stack，强调 microsecond latency，但单线程 stack 限制多核扩展。

## 设计取舍

- **公平性 vs 生产真实性**：禁用 TSO、使用 nophttpd、两机直连都让 stack 差异更清楚，但这不是完整生产环境。真实系统会有 TLS、kernel packet filters、observability、resource accounting、多租户隔离、load balancing 和更复杂的 application state。
- **per-stack optimization vs 可移植应用**：分别为每个 stack 写原生 nophttpd 能减少 wrapper 偏差，却也说明“支持 socket-like API”不等于低迁移成本。F-Stack 的 per-core process、Demikernel/IX 的 packet-level API、mTCP 的 connection context 都会改动应用结构。
- **snapshot value vs artifact aging**：论文为了跑起来修了 bug、补 feature、搜索配置，这让结果更接近 best effort；但也说明研究 artifact 的维护状态本身会影响性能结论。
- **run-to-completion vs bulk transfer**：IX 和 Demikernel 的低延迟路径适合小 RPC，但当大 response 依赖 ACK-clock 持续推进时，application processing 和 stack activity 绑在同一线程里可能会妨碍及时发包。
- **dedicated datapath vs resource allocation**：TAS 把 stack 和 application thread 分离，有利于多核和异构 core 分配，但最优 stack/application core ratio 依赖 workload，需要手工或自动 tuning。

## 实验与结果

- **Bulk transfer**：单连接 2 MB response 下，Linux 达到 14.69 Gb/s，F-Stack 达到 13.66 Gb/s；mTCP 和 TAS 大致在 10-12 Gb/s；IX 和 Demikernel 最低。论文推断 IX/Demikernel 的 packet-sized buffer API 和 run-to-completion 模型不适合多 packet 大对象发送。
- **F-Stack 不自动赢 Linux**：Linux 和 F-Stack 的 TCP/IP/Ethernet protocol processing CPU 占比分别是 50.5% 和 52.5%，但按 880 vs 735 requests/s 换算，Linux packet processing efficiency 高约 19.6%。这支持“kernel emulation overhead 抵消 DPDK packet I/O 优势”的解释。
- **Small message unloaded latency**：64 B response 下 Demikernel P50 RTT 为 13 us，Linux busy-poll 为 17 us，IX 约 20 us；mTCP 和 F-Stack 明显更高。mTCP P99 latency 可到 123-124 ms，显示 batching 和 app-stack thread interaction 对 tail latency 不友好。
- **消息变大后的低延迟 stack 反转**：当 message size 超过 32 KB，IX 和 Demikernel 的 P50/P99 开始高于 Linux，和它们在 bulk transfer 中的弱点一致。
- **Concurrent connections**：单核并发连接测试中，IX 吞吐领先其他 stack 30-684%；mTCP 比 TAS 高 17-95%，尽管 TAS 多用一个 core；Linux 和 F-Stack 几乎一样，说明去掉 syscall 并不一定解决高连接数下的瓶颈。
- **Concurrent latency**：IX 在最多 400 个连接时 tail latency 也较强，P50 latency 比 Demikernel 低 73-85%，但连接数更高后 tail 结果会反转。F-Stack、TAS、Demikernel 在高连接数时都出现明显 tail latency 问题。
- **Multicore scalability**：4800 连接下，IX 在 16 core 以内多数场景最好，相比 TAS 高 16-384%，相比 mTCP 最高高 456%；TAS 从 16 到 24 core 有 67% 吞吐提升，显示更好的后段扩展斜率；mTCP 从 16 到 24 core 仅提升 8.7%；Demikernel 因 single-threaded stack 未能测试多核。
- **实现与配置成本**：mTCP 需要特定 RSS seed 和 local port selection；TAS 需要 Window Scaling 修补、buffer tuning、bandwidth limiter 关闭和 core split 搜索；IX 有编译/linking/debugging 难题；F-Stack 要求应用适配 multi-process/callback；Demikernel 要求 async API、manual segmentation 和 Rust coroutine model。

## Critical Analysis

### 论证链条

论文的论证链条比较闭合：先指出已有 kernel-bypass TCP work 缺少统一横向比较，再把六个代表 stack 放到同一硬件、同一 client、同一组基本 workload 上，最后用 workload ranking 的反转说明“kernel-bypass 是否值得用”不是单一答案。尤其是 Linux bulk transfer 强、IX concurrent RPC 强、Demikernel unloaded latency 强这组三角关系，有力支撑了“没有 one-size-fits-all stack”的结论。

更脆的地方在于“practical kernel-bypass stack”这个外推。论文确实讨论了应用 porting、配置、维护、profiling 和 production feature 缺口，但这些部分更多来自作者经验和 qualitative analysis，不像吞吐/延迟曲线那样被系统量化。因此，性能 claim 很强，运维可行性 claim 合理但证据粒度更粗。

### 假设压力测试

第一个压力点是 hardware generation。实验用 25GbE，且禁用 TSO。对于 100/200/400GbE 或开启 BigTCP/TSO/GSO 的 Linux，bulk transfer 瓶颈可能进一步向 NIC、PCIe、memory subsystem 或 host interconnect 移动。论文的方向性结论可能仍成立，但具体 ranking 需要重测。

第二个压力点是 workload composition。论文把 bulk transfer、small latency、concurrent RPC、多核扩展分开测，这适合归因；但真实服务常常混合大 response、小 RPC、background replication、TLS、metrics export 和 control-plane traffic。IX 这类 run-to-completion stack 在混合 workload 里如何在 ACK-clock 大流和 latency-sensitive 小流之间调度，论文没有直接证明。

第三个压力点是 production semantics。kernel-bypass stack 是否能支撑资源隔离、fault containment、packet filtering、queuing discipline、TCP option evolution、debug tooling、traffic observability 和 orchestration integration，比单纯吞吐更难。论文指出这些风险，但没有把它们变成可比较的 benchmark。

### 实验可信度

作为 measurement paper，这篇的强项是“为了公平真的把东西跑起来了”。作者没有简单复用各系统原论文的 demo，而是写统一 nophttpd、修 client bottleneck、给 TAS 补缺失 TCP feature、为 mTCP 处理 RSS seed、选择 Reflex 里的 IX。这个工程工作让结果比单纯读论文表格可信得多。

主要弱点是实验覆盖面仍窄。只有一类 NIC、一档主机、一种 datacenter back-to-back 拓扑、一个轻量 HTTP server、8 秒 benchmark。论文没有系统呈现 run-to-run variance，也没有覆盖 failure、long-running stability、memory footprint、power efficiency、packet loss/congestion、mixed traffic 或 real application。禁用 TSO 是公平选择，但对 production recommendation 来说会低估成熟 kernel stack 的功能优势。

baseline 选择也有 availability bias。论文测的是可拿到、可修到能跑的 stack，而不是每个系统作者内部最新版本。对研究社区这很有价值，因为外部可复现性本来就是问题；但对某个 vendor 或 hyperscaler 的内部 stack，不能直接套用这些结果。

### 系统性缺陷

论文最重要的系统性提醒是：kernel-bypass 的隐性成本不是“重写几个 socket call”，而是重新承担 kernel stack 多年演化出来的生态责任。mTCP 的 RSS/local port 约束会影响部署弹性；F-Stack 的 multi-process model 会逼应用处理 shared state；IX 和 Demikernel 的 low-level API 会让应用重构；TAS 的 socket-like 外观仍掩盖不了 TCP feature 缺失和 core split tuning。

另一个缺陷是可观测性。Linux 有 perf、KernelShark、PacketDrill、tracepoint 和大量工程知识；kernel-bypass stack 忙轮询时 CPU usage 常年 100%，常规 live metric 很难说明瓶颈。论文提到 NSight 可能帮助跨 application/NIC tracing，但它不替代 fine-grained software overhead analysis。

## 局限与 Future Work

- **局限 1**：没有测试短连接性能。论文理由是很多 datacenter RPC 复用连接，但 load balancer、proxy、serverless 和 failure recovery 路径仍可能制造短连接或连接 churn。
- **局限 2**：没有测试 capped-throughput latency。作者明确说这个 workload 难，因为要让不同 stack 的“负载程度”一致，而不是仅仅 request rate 一致。
- **局限 3**：没有测试 parallel bulk transfer，因为 25GbE NIC 带宽有限。这限制了对 storage、ML checkpoint、replication 和多流吞吐的判断。
- **局限 4**：没有覆盖 kernel-enhancement 方案，如 [[io_uring]]、MegaPipe、StackMap、NetChannel，也没有覆盖 SmartNIC 或 NIC flow processing 方案，如 FlexTOE、AccelTCP。
- **局限 5**：没有把 production feature support 做成定量矩阵。TCP options、congestion control、loss recovery、packet filters、resource accounting、fault isolation 和 orchestration integration 都会影响 adoption。
- **Future work 1**：在 100/200/400GbE、开启 TSO/GSO/BigTCP、不同 NIC 和 NUMA 拓扑下重跑同一 harness，测吞吐、tail latency、CPU cycle/byte 和 energy/request。
- **Future work 2**：构造 mixed workload benchmark，同时包含 small RPC、large response、background bulk flow 和不同 connection lifetimes，验证 run-to-completion、dedicated datapath 和 kernel scheduling 的交互。
- **Future work 3**：把 porting effort 和 operability 量化，例如 required code changes、unsupported socket options、可用 tracing hooks、failure containment、配置搜索空间和 long-running stability。
- **Future work 4**：扩展 artifact 成社区维护的 stackbench，持续跟踪 Linux、F-Stack、TAS、IX-family、Demikernel、Junction/LUNA 类系统和 kernel-enhancement API 的演化。

## 相关

- **相关概念**：[[Kernel-Bypass]]、[[TCP]]、[[DPDK]]、[[RSS]]、[[TSO]]、[[io_uring]]、[[Datacenter-RPC]]、[[RDMA]]
- **同类系统**：[[mTCP]]、[[F-Stack]]、[[IX]]、[[TAS]]、[[Demikernel]]、[[Linux]]、[[Junction]]、[[Shenango]]、[[ZygOS]]、[[Shinjuku]]、[[LUNA]]
- **同会议**：[[ATC-2025]]
