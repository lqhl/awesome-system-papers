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
last_reviewed: 2026-08-14
---

# Arca：以续延为中心的计算（OSDI 2026）

> **原题**：Continuation-Centric Computing with Arca

> **一句话总结**：Arca 针对短命、计算与 I/O 交替的 serverless 程序，把“从当前位置继续执行所需的状态”做成内核原生续延（continuation），让 libc 在每次 I/O 处自动把普通程序切成纯计算 funclets；不复制内存、仍在本机恢复时 capture+resume 只需 2.55 µs，而把 32 KiB continuation 移到 12 MiB 图片所在节点的案例比搬图片快约 59 倍。

## 问题与动机

细粒度 serverless 希望 provider 在毫秒级重新放置计算、按实际 working set 分配资源，并在数据依赖出现后再决定在哪里运行。现有研究系统因此要求开发者提前把一个程序拆成许多纯函数，再用 DSL、API 或 dependency graph 显式连接 I/O 与中间状态。这个做法能暴露并行性，却把续延传递风格（continuation-passing style，CPS）的改写成本交给应用作者（§1–§2.2）。

另一条路是直接 checkpoint Linux process 或 MicroVM，让“剩余程序”成为可恢复 snapshot；但 process 含 file descriptor、socket buffer 等大量 ambient OS state，捕获和恢复要数百毫秒。WebAssembly sandbox 创建较快，却通常把实例状态与 JIT runtime/host state 混在一起，难以得到便宜且独立的 continuation（§1、§2.2、表 1）。

Arca 的问题设定比通用 Unix 窄：logical function 是开发者理解的一次完整任务；funclet 是不做 I/O、运行到结束的小段纯计算。每当程序请求 I/O，内核捕获当前 continuation，当前 funclet 返回一个“effect + callback”；外部 effect handler 做完 I/O 后再调用 callback。开发者仍可按普通控制流写 C/WASI 程序，provider 却能在每个真实 I/O boundary 重新放置后续计算（图 1–2）。

这不是为 database、daemon 或共享内存服务设计的通用 OS。论文主动限定目标为短生命周期、I/O/compute 交替、资源需求随阶段变化的 workload；长期驻留且 state 很大的服务很少值得迁移（§4.4、§8）。

## 关键观察 / 隐含假设

- **观察 1：开发粒度与调度粒度不必相同。** 开发者可以写一个 logical function，libc 在每个 I/O 调用内部执行 CPS transform，把它自然分成多个 funclet（§2.2、§3.3）。
  - **依赖假设**：程序的关键阶段确实被可拦截的 I/O boundary 分开；纯计算长循环不会自动产生更多调度点。
- **观察 2：procedure-oriented OS 能让 continuation 只包含局部执行状态。** Arca process 主要持有 page table、register file 和 value descriptors，不积累 Unix 的全局 file/socket state（§4.1–§4.2）。
  - **可能失效场景**：persistent socket、kernel-bypass device、shared memory 或外部 mutable object 会把 continuation重新绑定到原 machine/process。
- **观察 3：最常见的 continuation 是一次性 callback，不需要复制。** `call_cc` 采用 functional-but-in-place：value 唯一时直接转移 ownership，保留在内存中恢复，成本不随 process footprint 增长（§5.2、图 3）。
  - **依赖假设**：大多数 continuation 不需要复制到 disk、另一台 machine 或多个 speculative branch；真正 copy 时成本仍随 bytes 线性增长。
- **观察 4：移动计算而非移动数据只在二者大小差异明显时划算。** thumbnail 案例的 image 是 12 MiB，压缩 continuation 只有 32 KiB（图 6）。
  - **可能失效场景**：heap 很大、data 本来就在本地、network bandwidth 高或 target machine 缺 CPU 时，迁移 continuation 可能没有收益。
- **假设 1：provider 提供的 effect handlers 正确、安全且可恢复。** application 不能直接 I/O，所有 side effect 都由 kernel 或 API adapter 解释（§3.2、§4.3）。
  - **证据强度**：弱到中。prototype展示 I/O 路径性能，却没有定义 crash/retry 下的 exactly-once 或 at-least-once effect semantics。
- **假设 2：舍弃 mutable shared-memory threads 是可接受的兼容边界。** Arca 不支持 `mmap`、`shm_open`、`clone` 式共享状态（§3.3、§4.4）。
  - **证据强度**：中。WASI/FFmpeg说明一类单线程程序可移植，但没有大型多线程应用数据。

## 核心方法

### logical function、funclet 与 effect

Arca 是 procedure-oriented OS：process 不通过 file/socket IPC积累状态，而是像函数一样接收 values、运行计算、返回 values。一个 funclet 若要读文件，会捕获“读完以后继续做什么”的 continuation，然后返回描述 `read` 的 effect 和 callback。effect handler完成 read 后，把结果作为参数调用 callback；从应用角度，控制流仍回到原来的 `read()` 之后（§3.2–§4、图 1）。

每个 process 有 page table、register file 和 value descriptor table。descriptor 不指向 kernel file，而是指向内核里的通用 immutable values，例如 word、blob、tuple、page、page table 和 funclet。system calls 可创建、复制、消费这些 values，也能调用 child process、返回结果和执行 `call_cc`。默认 linear ownership 让唯一 value 原地更新，共享 value 才 copy；`call_cc` 把 capture 与 callback creation合成一次 syscall，避免无用 memory copy（§4.1–§5.2、表 3）。

### 兼容层与 effect handler

对 WebAssembly/WASI，toolchain 用 `wasm2c` 把 binary 转成 C，再链接改造后的 musl/WASI shim。对一部分 POSIX source，Arca 的 musl port直接把 `open/read/write/socket` 等调用翻成 effect。application之上的 API Adapter 是另一个 Arca process：它把 POSIX-like effect 转成 provider-native 的 `get blob`、`query database` 等请求；kernel root handler再经 VirtIO/Vsock交给 Linux host monitor（§3.1–§3.3、图 2）。

兼容不是完整 POSIX。普通 file I/O 可模拟；低层 network I/O需要 provider显式支持，而且 socket state 不能干净 capture，所以 continuation只能回原 machine。pipe/fork可用 continuation模拟，但 mutable shared memory原则上不支持。prototype最复杂 port是 FFmpeg 5.1 的现成 WASI binary；一个 developer为所需 WASI shim投入约两周 part-time，只验证多种 audio transcoding成功，没有给 FFmpeg性能（§3.3、§6.5、表 2）。

### 隔离与当前实现

Arca process 用硬件 page protection隔离，kernel用 Rust，实现 SMEP/SMAP，并不给 process直接 side effect或 x86 timestamp counter。作者认为没有高精度 timer、shared-memory helper和未审查 I/O，可降低 timing side channel；但允许哪些 effect、是否提供 arbitrary network由 provider决定（§4.3）。

prototype是 x86-64 Rust research kernel，运行在 [[KVM]] 中。Linux userspace monitor提供 file/network/debug；kernel通过 VirtIO Vsock和 hypercall访问 host TCP stack，用 9P filesystem承载文件。论文没有实现完整 serverless scheduler、placement、billing、access control、production debugger/metrics或 multi-tenant control plane（§5.1、§9）。

## 设计取舍

- **内核原生 continuation 换新 OS**：capture path可以做到微秒级；部署不能直接复用 Linux container生态。
- **procedure-oriented state 换 POSIX 兼容性**：page/register/value state容易序列化；file descriptor、socket、shared mapping的普通语义被削弱或取消。
- **不复制 callback 换位置自由**：本机一次性 resume是常数时间；migration、replication和swap必须 copy整个 reachable state。
- **I/O 变 effect 换 provider可控性**：provider能在依赖出现时 placement；effect handler成为新的 I/O语义、权限和故障恢复中心。
- **每次 I/O capture 换自动 CPS**：source code无需手拆 DAG；极高 I/O rate、`io_uring` 或 kernel bypass会付出大量 boundary cost，且后两者难以支持。
- **无 shared-memory threads 换独立 snapshot**：每个 process可单独迁移；thread-pool程序只能单线程直移植，或改用 provider级并行 primitive。
- **限制 timer/I/O 换 side-channel缩减**：攻击面更小；论文没有证明共享 cache、branch predictor、KVM/VirtIO等微架构/host channel都被消除。

## 实验与结果

- **continuation microbenchmark**：在双 AMD EPYC 7702（128 physical cores、160 GiB RAM）上，Arca VM分配32 GiB；single-thread loop warm up 1 s，再跑10 s，重复10次。continuation不复制时 snapshot+resume恒定为2.55 µs；copy path随 footprint线性增长，虽仍比 tmpfs上的 Linux CRIU和 Firecracker约快一个数量级，却不是五个数量级。表 1 的 283,000/217,000 µs 对比 2.55 µs，只代表 Arca最有利的 resident、no-copy callback路径（§6.1、图 3）。
- **sandbox创建与并发**：另一台双 EPYC 7702、512 GiB机器上跑60 s noop。128-way的表 1 数字为 Arca 32.2 µs、Wasmtime 110 µs、Linux process 540,000 µs、MicroVM 742,000 µs。Figure 4更完整：single-thread Arca约5 µs、Wasmtime 1.5 µs；4-way起 Arca反超，256-way约30 µs对200 µs。SHAREDOBJECT约100 ns但完全无 isolation；PROC尚未加 namespace，所以Linux sandbox baseline甚至偏乐观（§6.2.1、图 4）。
- **有计算的稳定吞吐**：AMD Ryzen 9 7950X、32-way、128×128 int32 matrix multiply open-loop test中，系统在120 s内若后60 s slowdown超过10%就视为不稳定。SHAREDOBJECT稳定到18K requests/s，Arca 17K，Wasmtime 15K，reset已有VM的 DKVM 10K，新建 Linux process的 PROC只有1K；FCKVM只有200 requests/s且 p95 42 ms（§6.2.2、图 5）。旧页把 Arca写成18K、把 Linux process写成约10.5K，混淆了 no-isolation与 DKVM baseline。
- **跨机 locality案例**：两台 AWS c6a.metal上，TRADITIONAL把12 MiB image搬到 compute node，98%时间等网络，吞吐9.42 requests/s；CCC压缩并传32 KiB continuation到 data node，data-transfer占9%，吞吐557.3 requests/s，约59.2倍。单次图示估算为106 ms对2.82 ms。若一半请求已有 local data，CCC/传统吞吐仍为889.62/18.21 requests/s（§6.3、图 6）。两者都用 Arca isolation，所以差异只反映 placement；这是刻意选择“大数据、小 continuation”的理想案例。
- **I/O路径**：Ryzen 7950X、ApacheBench 65,536 requests、concurrency 32下，pooled Arca与 Apache 2.4.66相近：p50 1.642/1.737 ms，p99 2.217/2.067 ms。每请求新 process的 individual模式中，Arca p50/p99为3.665/5.390 ms，Apache CGI为16.53/19.36 ms，p99约快3.6倍（§6.4、表 4）。这只是返回静态 `hello, world`，不代表真实 web stack或 TLS/database workload。
- **功能与安全边界**：FFmpeg compatibility是qualitative success，没有 benchmark。实验没有测恶意 tenant、side channel、continuation validation、effect crash/retry、remote resume p99、persistent storage、资源计费或真实 FaaS trace；论文也承认完整 runtime/control plane尚不存在（§4.3、§6.5、§8–§9）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| continuation可以是微秒级 OS primitive | no-copy `call_cc` snapshot+resume为2.55 µs（图 3） | resident本机callback；copy/migrate成本随footprint线性增长 | 强（该路径） |
| Arca能兼顾硬件隔离与轻量sandbox | matrix test稳定吞吐17K，接近无隔离18K并高于Wasmtime15K（图 5） | 单机research OS、单计算kernel；安全未做攻击评测 | 中到强 |
| continuation placement可显著减少data movement | 32 KiB continuation替代12 MiB image，吞吐557.3对9.42 requests/s（图 6） | 两节点、单thumbnail workload，尺寸比极有利 | 强（案例内） |
| 自动在I/O处capture不必明显拖慢server | pooled Arca与Apache p50/p99相近；individual p99低约3.6倍（表 4） | 静态短响应、无TLS/backend state | 中 |
| 传统程序可机械进入continuation模型 | WASI→C→musl toolchain成功运行FFmpeg audio transcode（§6.5） | shim开发约两周；只覆盖部分WASI/POSIX，无性能或广泛兼容测试 | 中 |

## 批判性分析

### 论证链条

论文从“手工拆 serverless DAG很难”出发，把CPS transform下沉为 `call_cc`，再通过舍弃ambient Unix state得到便宜capture，逻辑清楚。microbenchmark证明no-copy continuation很轻，thumbnail则证明它有机会改变placement。关键外推是把“有用的primitive”称为“computing paradigm”：完整scheduler、durability、retry、billing和production运维都未实现；59倍也只证明一个continuation远小于remote data的案例，不证明普通FaaS普遍获益。

### 假设压力测试

若 continuation heap从32 KiB变成数百MiB，或应用持有socket、device queue与共享state，capture要么线性copy，要么不能迁移。若I/O非常频繁，每次libc call都capture/return/resume，2.55 µs也会累积。若任务以长compute phase为主，只有I/O boundary提供调度点，provider仍无法及时抢占或重分资源。若effect已执行但callback恢复前crash，缺少幂等key/transaction的外部服务可能重复side effect。

### 实验可信度

论文分别测capture、create/delete、open-loop compute、跨机data locality、I/O tail和FFmpeg compatibility，问题覆盖完整，也明确区分DKVM reset与FCKVM cold creation。最需谨慎的是baseline口径：Arca在KVM内，其他系统直接跑Linux；Table 1把128-way effective create time与no-copy snapshot headline并列；CRIU/Firecracker必须产出可移植snapshot，而2.55 µs路径没有copy。thumbnail图片/continuation尺寸极悬殊，且没有sweep size ratio、network congestion或remote failure。没有真实multi-tenant trace和cost数据。

### 系统性缺陷

Arca的compatibility tension是抽象本身带来的，不全是engineering backlog。mutable shared memory无法让每条continuation独立；TCP/device state也不随page/register自然迁移。effect handler/API Adapter相当于重建一层I/O kernel，需要权限、backpressure、cancellation、timeout、idempotence和observability。kernel不保留logical call stack，使跨funclet debugging更难。安全论证主要基于少暴露timer与memory-safe Rust，没有multi-tenant isolation、speculative-execution、malformed value/continuation或host-channel test。最后，单个research kernel、partial libc与paravirtualized host依赖使升级、driver和部署成本都未量化。

## 局限与后续工作

- 对每种effect定义crash点、retry和idempotence，注入“side effect已发生但callback未恢复”等故障，验证exactly-once或明确at-least-once语义。
- sweep continuation从KiB到GiB、local-data ratio、network bandwidth和target load，找出“移动计算优于移动数据”的break-even curve。
- 在真实FaaS trace上测capture frequency、remote resume p50/p99、continuation storage、memory pressure、billing与end-to-end cost。
- 为thread pool、socket、`io_uring`、kernel bypass和long-lived daemon给出明确替代抽象，并量化porting LoC与性能损失。
- 构建scheduler/control plane，测试preemption、placement、backpressure、quota、multi-tenant fairness与host failure recovery。
- 对恶意continuation、effect payload、VirtIO/9P边界和timing/cache side channel做security audit与fuzzing。
- 记录跨funclettrace、logical stack和effect lineage，验证debugger/profiler能定位跨machine失败。

## 相关

- **相关概念**：[[Serverless-Computing]]、[[Continuation]]、[[Process-Checkpointing]]、[[WebAssembly]]
- **同会议**：[[OSDI-2026]]
