---
type: theme
topic: Operating-Systems
paper_count: 9
first_generated: 2026-08-17
last_updated: 2026-08-17
tags: [topic-overview, operating-systems, runtime, virtualization]
---

# 操作系统与运行时综述

> 9 篇论文覆盖移动 OS service、内存分配、firmware/eBPF 隔离、CXL microkernel、serverless 与 managed runtime；共同方法是把应用层反复出现的 workaround 上移为明确的调度、状态或隔离抽象。

## 论文列表

### OS Service 与内存运行时（3 篇）

- [[Spars-OSDI25|Spars]] — 将 rendering service 分成按序准备、乱序执行和按序提交，释放多核并行度。
- [[Copier-SOSP25|Copier]] — 把 memory copy 提升为 first-class OS service，协调 SIMD、DMA 与 copy-use overlap。
- [[jwmalloc-OSDI26|jwmalloc]] — 用统一 slab、closed sibling tree、两缓冲回收和 non-blocking fallback 适配手机 workload。

### 隔离、虚拟化与新硬件 OS（3 篇）

- [[uEFI-ATC25|µEFI]] — 以 microkernel-style address space 隔离 UEFI module，并保持 protocol transparency。
- [[vBPF-OSDI26|vBPF]] — 用 namespace 和 late binding 虚拟化 eBPF hook、program 与 state view。
- [[StarfishOS-SOSP26|StarfishOS]] — 在 [[CXL]] 上用 state-partitioned microkernel 重访 single-system image；当前仅有公开 metadata。

### Serverless、Batch 与 Managed Runtime（3 篇）

- [[AFaaS-OSDI25|AFaaS]] — 从生产 cold-start trace 出发，用 fork、资源池和 tree seed 优化 serverless startup。
- [[Quark-OSDI26|Quark]] — 将 co-located batch 的长寿 executor 改成 task-level serverless instance。
- [[DGC-OSDI26|DGC]] — 把 concurrent GC marking 解聚到共享服务，并对多个 runtime 的 burst 做全局错峰。

## 主题综述

[[Spars-OSDI25]] 与 [[Copier-SOSP25]] 都从“已有 API 隐藏了并行机会”出发：前者在 stateful rendering API 下引入 prepare/execute/commit，后者利用 copy-use window 把同步 memcpy 改成 OS 调度对象。[[jwmalloc-OSDI26]] 同样不是只优化 fast path，而是联合调整 slab、backend tree、回收和锁等待。

隔离路线强调绑定时机和状态所有权。[[uEFI-ATC25]] 把 signed module 从共享地址空间移走，[[vBPF-OSDI26]] 把 program 从 physical hook 延迟绑定到 tenant namespace，[[StarfishOS-SOSP26]] 的公开题名则把 CXL single-system image 建立在 state partitioning 上。三者都试图在兼容现有接口的同时缩小共享状态。

[[AFaaS-OSDI25]]、[[Quark-OSDI26]] 与 [[DGC-OSDI26]] 共同挑战固定 provision：函数启动、batch executor 和 GC marker 都表现为 bursty resource consumer。它们通过按需实例、共享池或跨 runtime 协调提高利用率，但也扩大了 control plane 与共享故障域。

## 设计空间矩阵

| 论文 | 工作负载 | 瓶颈 | 机制 | 主要资源 | 正确性 / SLO 边界 |
|---|---|---|---|---|---|
| [[Spars-OSDI25]] | mobile rendering | 单线程 render service | OOO execute/in-order commit | CPU/GPU | 保持绘制顺序；限 2D UI |
| [[Copier-SOSP25]] | copy-heavy service | 同步 memcpy | async copy service | SIMD/DMA/CPU | 需识别 copy-use dependency |
| [[jwmalloc-OSDI26]] | mobile allocator | reformat/reclaim/lock | slab+closed tree+fallback | CPU/DRAM | bounded verification |
| [[uEFI-ATC25]] | firmware module | 共享 privilege | address-space isolation | CPU/MMU | 依赖完整 protocol metadata |
| [[vBPF-OSDI26]] | multi-tenant eBPF | global hook/state | namespace+late binding | kernel/eBPF | 信任 kernel/verifier/toolchain |
| [[StarfishOS-SOSP26]] | CXL SSI | 未公开 | state-partitioned microkernel | CXL | metadata-only |
| [[AFaaS-OSDI25]] | production FaaS | cold start | fork+pool+tree seed | CPU/memory | Ant production functions |
| [[Quark-OSDI26]] | co-located batch | idle allocation | task-level serverless | CPU/memory | Spark production workload |
| [[DGC-OSDI26]] | managed runtime | GC burst | disaggregated marking | CPU/RDMA | 高 load 与 NIC saturation 边界 |

## 共同观察

- **共享状态会把局部工作变成全局串行点。** Rendering state、copy engine、allocator backend、eBPF hook 和 GC marker 均出现这一问题。
- **异步化需要显式 commit/validation。** [[Spars-OSDI25]] 保序提交，[[Copier-SOSP25]] 追踪 copy-use，[[DGC-OSDI26]] 需要 remote heap snapshot 与全局调度；只把工作移到后台不能保证正确性或 tail latency。
- **生产 workload 呈 burst、phase 和 over-subscription。** [[AFaaS-OSDI25]]、[[Quark-OSDI26]]、[[jwmalloc-OSDI26]] 的设计均依赖真实 trace，而非 steady-state microbenchmark。

## 假设冲突与脆弱点

- 把服务池化可平滑 burst，但 [[DGC-OSDI26]] 的共享 marker 与 [[Quark-OSDI26]] 的 task instance 都扩大了网络、调度和 shared-failure dependency。
- 透明兼容减少部署改动，却要求系统理解隐含语义：[[uEFI-ATC25]] 依赖 protocol metadata，[[Copier-SOSP25]] 依赖 copy-use boundary，[[vBPF-OSDI26]] 依赖 event→namespace mapping。
- [[StarfishOS-SOSP26]] 目前只有 metadata，不能从题名推断 CXL coherence、failure 和 state migration 已被解决。

## 值得关注的方向

- **异步 OS service 的统一 dependency API**：比较 rendering、copy、I/O 和 accelerator command 的 prepare/execute/commit 共性。
- **Shared service fault injection**：对 DGC、serverless pool 和 eBPF multiplexer 注入 crash、partition 与 stale state，测量最坏恢复时间。
- **CXL state ownership**：等 StarfishOS 全文公开后，与 [[CXL]] 现有 memory-placement/system work 做同一 failure model 下的比较。
