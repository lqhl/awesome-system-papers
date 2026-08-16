---
type: paper
name: jwmalloc
full_title: "jwmalloc: A Verified Memory Allocator for Mobile Devices"
authors: [Jiawei Wang, Ming Fu, Ruixian Wang, Chao Xu, Jonas Oberhauser, Haibo Chen]
venue: OSDI
year: 2026
tags: [memory-allocator, mobile-system, memory-reclamation, non-blocking, verification]
source_pdf: "[[osdi26-wang-jiawei.pdf]]"
source_md: "[[osdi26-wang-jiawei]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# jwmalloc：面向移动设备的已验证内存分配器（OSDI 2026）

> **原题**：jwmalloc: A Verified Memory Allocator for Mobile Devices

> **一句话总结**：手机上的内存分配既频繁改换对象尺寸，又有剧烈的前后台内存峰谷、激进回收和数百线程超额订阅；jwmalloc 用单页统一 slab、只保存合法 size class 的 closed sibling tree、两缓冲生命周期回收和 non-blocking fallback 联合处理这些问题，并在 Mate 70 Pro 的两小时真实 workload 中让 jemalloc 的全机指令数高出 10%、用户态分配相关指令高出 3.84×，同时保持相近内存占用。

## 问题与动机

动态内存分配不是手机上的小开销。论文测得，使用 jemalloc 时，allocator 指令约占 Android 实际 workload 总指令的 8.2%，在 HarmonyOS 上约占 12.4%（图 1）。手机又只有少量有效 CPU core 和有限 DRAM；多做一次 split、coalesce、系统调用或锁等待，都会和前台应用争 CPU、电量与内存，并可能直接表现为卡顿。

作者从手机 trace 中归纳出四个不同于典型服务器 workload 的压力：

1. 不同时刻由不同 object size class 主导，但在用内存总量可以大致稳定，说明同一批内存会频繁被重新格式化；系统 graphics service 的瞬时分配率可到约 300 万次/秒（图 2–3）。
2. 前后台切换造成大峰谷，graphics 的峰值内存超过 steady state 的 5×（§2.3）。
3. 手机常把回收延迟设为 1 秒或更短；streaming workload 中 90% 的 page 在 33.55 ms 内变空，但仍有超过 1% 活过 3.22 s，生命周期明显分层（图 5）。
4. 8-core 设备在 app installation 场景中出现最多 742 个线程，且 cross-thread free 在部分时间片接近 100%；持锁线程被抢占会把延迟传给 UI 等高优先级线程（图 4、图 6）。

jemalloc、tcmalloc 和 mimalloc 各自优化了吞吐或内存，但没有同时适配这四点：异构 slab 会在 size demand 改变时推动 backend 反复拆合；固定 granularity 会留下不能直接服务请求的 intermediate range；metadata 常随历史峰值增长而不缩；按时间或速率回收不知道邻接 range 是短寿还是长寿；共享 backend 的锁在超额订阅时会放大 tail latency。

论文因此不是只替换某个 freelist，而是重新设计 frontend、midend、backend、回收和并发接口。它仍属于 performance-oriented allocator；use-after-free quarantine、checksum 等安全加固不在本文范围内。

## 关键观察 / 隐含假设

- **观察 1：小对象 slab 的主要浪费不只是尾部碎片，还包括跨 size class 重格式化时的 backend churn。** jemalloc 为不同 size class 选择不同 slab 大小，空 slab 很难直接改作另一类；一页大小的统一 slab 则可放进同一个 thread-local pool（§3.1、图 7）。
  - **依赖假设**：为每个小对象 size class 微调实际 class 大小后，4 KB slab 的 tail waste 仍可接受；应用也能容忍请求被 round up 到略有变化的 size class。
  - **可能失效场景**：请求大量集中在接近 2 KB 的尺寸时，一页 slab 里对象太少，统一设计的性能和空间收益都会变弱；论文在 8 B–4 KB、10N-thread 的 rptest/xmalloc 中确实看到少量退化。
- **观察 2：backend 若只维护真正可分配的 size class，就能避免 intermediate range 的查找与反复拆合。** 一个 resolution-`R` size-class set 的最大 round-up 碎片有界；closed sibling tree 让任意连续 sibling 的和仍落在这个集合里，因此可以只做 size-class-exact split/coalesce（§3.2、表 1、图 8–9）。
  - **依赖假设**：生产配置采用 `R=3`，即最坏 round-up internal fragmentation 为 25%，足以兼顾尺寸密度与跨尺寸复用。
- **观察 3：页生命周期有明显“很快释放”与“长期存活”两群。** 只要让刚释放或刚合并的 range 多等一个 buffer epoch，就更可能先和即将释放的短寿邻居合并；不需要为每个 range 保存 timestamp（§2.3、§3.3、图 5）。
  - **证据强度**：中。graphics 与 streaming trace 支持分层，但论文没有给所有应用、不同回收周期和 phase transition 下的误判率。
- **观察 4：极端 tail 来自锁持有者被抢占，而不是常见路径本身慢。** 因而系统可以把罕见的锁等待改成短暂额外内存：allocation 改取更大 range，free 先放 deferred list（§3.4）。
  - **代价**：non-blocking fallback 保住调用路径，却可能在 contention 最高时增加临时 footprint 和后续整理工作。
- **假设 1：“Verified”指有界验证，而不是完整 allocator 的无限状态证明。** VSync 穷举小型 client 在 weak memory model 下的执行；bitmap 从 64 项缩到 2 项，系统 allocator 与 OS 交互也会被抽象掉（§5）。
  - **证据强度**：强于 stress test，但只对所选 client 和界限内的状态完整。

## 核心方法

### 1. 按尺寸分成三层

整体架构见图 10。少于 2 KB 的对象进入 per-thread frontend；2–16 KB 若直接放进 4 KB 粒度的 frontend/backend 都容易产生尾部碎片，因此由 per-process slab midend 处理；16 KB–4 MB 进入 backend；大于 4 MB 直接走系统调用。这些阈值来自手机 workload，也允许按系统调整。

### 2. 单页 slab 与跨 size-class pool

Frontend 的所有小对象 slab 都是一页，即 4 KB。它不是保持旧 size class 再扩大 slab，而是反过来微调 size class，使一页扣除 metadata 后的尾部浪费受控。例如 4 KB slab、128 B metadata 下，512 B class 留 384 B，改为 560 B class 只留 48 B（§3.1）。

每个 thread-local storage（TLS）为每个 class 保存 partial/empty list，并用按 8 B 对齐请求索引的 direct map 指向当前 slab。变空的 slab 还能进入所有 class 共享的 pool；pool 超过按总 slab 数计算的 watermark 时，least-recently-used slab 才交回 backend。Cross-thread free 使用独立的 cross list，head offset 与 object count 可一次原子更新；周期检查只读 count，真正缺对象时才批量把整条 list 转到 local list（§4.1）。

### 3. 只保存合法尺寸的 closed sibling tree

Backend 分为 Nest、Knit 和 Thrift：Nest 按 size class 找 range，Knit 管连续虚拟地址的 split/join，Thrift 管 cache watermark 与 reclaim（图 10–11）。Mapped Nest 保存仍有物理页的 range，unmapped Nest 保存已 `madvise` 的 range；两者都先查 bounded bitmap，必要时才查 unbounded list。

Knit 的每个 4 MB root 下是一棵 closed sibling tree。若要从 256 KB 取 8 KB，系统不会留下非法的 248 KB remainder，而是先拆成 32+224 KB，再把 32 KB 拆成 8+24 KB；每一步结果都属于 resolution-3 size class（图 9）。Free 时也只合并同一 parent 下、合并后仍合法的连续 sibling，避免“刚合并成 248 KB、下一次又拆回 224+24 KB”的 churn。

不规则 tree 通常需要大量 pointer。jwmalloc 把二维 tree 映射到一维 per-granule array，把 internal node 编进 leaf metadata，并从 range size、depth 和 sibling index 计算 offset。结果是每 4 KB 只需 12 B metadata；当一个 root 管理的 range 全部释放时，这些 metadata 也能回收，不会永久停在历史 peak（§3.2.3）。

### 4. 两缓冲生命周期回收

Mapped Nest 的每个 size class 有 active 与 standby 两个同构 buffer。新释放或刚合并的 range 总进 active；allocation 先查 active，再查 standby。后台线程交换两个 buffer、等待间隔 `Δ`，随后对 standby 中仍未复用的 range 执行 `madvise` 并移到 unmapped Nest；论文实现把这段 futex 等待设为 500 ms，也可被同步回收提前唤醒（§3.3、§4.2.4）。

直觉是：若空闲 range 的 sibling 很快也释放，两者会合并并重新进入 active，相当于重置倒计时；若邻居长期存活，它会在 standby 中等满一个周期后优先被回收。系统不扫描全体 range，也没有 per-range timestamp。若 cached range 超过 watermark，freeing thread 会同步回收新 range，并唤醒后台线程提前换 buffer，避免后台线程在超额订阅下迟迟得不到 CPU。

### 5. Non-blocking ownership transfer 与有界验证

每个 size class 的 bitmap 是主路径，unbounded doubly linked list 只作 fallback。拿不到 list lock 时，allocation 改从更大的 class 取 range 再拆，free 则把 range 推到 concurrent deferred list 后立即返回。Backend 中 range 同时受 Nest 的“可搜索所有权”和 Knit 的“地址树所有权”约束；两者不能原子取得时，协议用分阶段 acquire、CAS、rollback 和 bounded retry，失败后扩大搜索或延期处理（§3.4、§4.2.3）。

作者用 VSync 对 frontend、midend、backend 分别及组合后的 bounded multi-thread client 做 weak-memory model checking，检查 assertion、memory safety、data-race freedom 与 loop termination。每个 client 控制在 10 分钟内。验证发现过一个真实 bug：root 没有 sibling，但 metadata shifting 的一条路径仍访问 sibling state，特定数据值下会越界读；backend client 约 10 秒即可暴露它（§5）。

## 设计取舍

- **统一 slab 换更简单的跨 class 复用。** 它减少 backend churn，却要改变 size-class layout，并在接近 4 KB 的请求上牺牲部分性能。
- **Size-class-exact tree 换实现复杂度。** Closed sibling property 消除 intermediate range，但 split 路径、metadata shifting 和 sibling state 比普通 buddy 更难实现与审计。
- **粗粒度 lifetime 换低 CPU 成本。** 两个 buffer 避免 timestamp 和全量 scan，却只能给出“至少经历一个 epoch”的粗分类；`Δ`、watermark 与 workload phase 不匹配时仍会过早回收或多占内存。
- **临时内存换无阻塞调用。** Try-lock 失败时多取 range 或延期 free，可避开 priority inversion，但没有给出 adversarial contention 下的额外内存上界、公平性或单线程完成时间界。
- **性能优先换 memory hardening。** 论文没有集成 quarantine、checksum、MTE/HWASAN 的完整成本与正确性实验，不能把实现层验证理解为能防住客户端 use-after-free。
- **自动 bounded checking 换 proof coverage。** 缩小常量和拆分 client 让所有 weak-memory execution 可穷举，但未覆盖的 API 序列、真实规模、syscall failure 和 OS interaction 仍靠测试与生产运行兜底。

## 实验设计

Microbenchmark 在 Intel Xeon Platinum 8260 服务器上限制使用 4 个 core，再用不同 thread count 模拟手机并发；它比较 jwmalloc、jemalloc 5.3.0、mimalloc 2.1.8 和 gperftools tcmalloc 2.16，四个 workload 分别覆盖 thread-local allocate/free、cross-thread free、多生命周期和频繁 thread creation/destruction。所有 allocator 用默认配置并关闭 profiling（§6.1）。

真实设备是 8-core、12 GB RAM 的 Huawei Mate 70 Pro，运行 HarmonyOS 5.1。作者把系统默认 jemalloc 替换成 jwmalloc 或 mimalloc，执行约两小时、覆盖系统交互与常用应用的 benchmark；每项跑 5 次并报告 mean 与 standard error。tcmalloc 因 C++ runtime/toolchain 不兼容而没有进入手机比较（§6.2、图 17）。

## 实验与结果

- **最短路径的指令确实减少。** x86 in-slab `alloc/local_free/cross-thread_free` 分别为 `16/22/29` 条指令；jemalloc 为 `27/38/>100`，尤其 cross-thread free 少超过 70%（表 2）。这只衡量 slab 内路径，不含 page fault 和 backend 慢路径。
- **Microbenchmark 的平均性能与指令结果支持 frontend/backend 联合设计。** 相对 jemalloc，jwmalloc 平均性能提高 74%，allocator-side instructions 约少 82%；仅换 frontend 的 `jw+jemalloc` 在 rptest-8B-128B-1 快 24%，在 xmalloc-8B-128B-N 快 4.1×。完整 jwmalloc 在 rptest-8B-128B-1 相对 jemalloc/mimalloc/tcmalloc 分别快 25%/24%/10%（§6.1.1、图 12）。
- **峰谷 workload 下，backend 回收了 steady-state 内存。** 插入 2 秒 sleep 的 mstress-10N 中，jwmalloc peak/steady footprint 为 906/29 MB，jemalloc 为 968/376 MB；`jw+jemalloc` 为 1002/385 MB，说明低 steady state 主要来自新 backend 与 lifetime reclaim，而不只是 uniform frontend（§6.1.2、图 13）。
- **Non-blocking 设计改善了极端尾延迟。** mstress-10N 的 P99.99 allocation/free latency 为 1.5 µs，最佳竞争 allocator 为 5.9 µs；论文没有把这个 5.9 µs 明确归因于 jemalloc（§6.1.3、图 14）。
- **真实手机上指令、功耗和内存方向一致。** 图 15 以 jwmalloc 为 1：jemalloc/mimalloc 的全机指令平均高 10%/13%，用户态分配相关指令高 3.84×/4.79×，内核态分配相关指令高 14%/12%。相对 jemalloc，article reading 与 video playing 的总 CPU instructions 少 21.0%/6.7%，各 CPU cluster 功耗少 4.7%–11.0%，LPDDR 功耗少 2.2%–2.8%（表 3）；六个高内存 system service 的 PSS 多数相近或更低（图 16）。
- **部署证明了可运行规模，但不是可复现的可靠性统计。** 论文称 jwmalloc 已用于 1200 万台手机、平板和手表，累计稳定运行超过 300 亿 user-hours（§1、§7）；没有披露 crash rate、版本分布、回滚次数或与 jemalloc 的线上对照组。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 统一 slab 与新 backend 能显著减少 allocator 指令 | 表 2、图 12：cross-thread free 少超过 70%，micro 平均 instructions 少约 82% | 4-core x86 server、四个合成 benchmark；手机 ISA 与慢路径另测 | 强 |
| Lifetime-aware backend 能压低峰谷后的常驻 footprint | 图 13：mstress-10N steady 29 MB，对 jemalloc 376 MB | 人工插入 2 秒 sleep；不等于任意应用的最坏 bound | 强 |
| Non-blocking fallback 能缓解超额订阅 tail | 图 14：10N-thread P99.99 为 1.5 µs，对最佳竞争者 5.9 µs | 单一 mstress 分布、4-core server；未测 priority mix | 强 |
| 系统收益能传到真实手机的 CPU 与功耗 | 图 15–16、表 3：全机指令、CPU/LPDDR power 同向下降 | 一款 Mate 70 Pro、HarmonyOS 5.1、约两小时 workload、每项 5 次 | 强 |
| 并发实现经过 weak-memory 检查 | §5：bounded clients 穷举并发现 root sibling 越界读 | 缩小配置、有限线程/API 次数、抽象系统 allocator | 中 |

## 批判性分析

### 论证链条

论文最强之处是把四项 trace observation 分别映射到四类机制：size-class churn→uniform slab，峰谷与非法 fragment→closed sibling tree/可回收 metadata，生命周期分层→两 buffer，超额订阅→non-blocking fallback。`jw+jemalloc`、完整 jwmalloc、memory sleep variant、operation latency 和手机 whole-system counter 又从不同角度拆开验证，主线比只报 malloc throughput 完整。

仍要避免把结果全归给某一个新结构。图 12 的 74%/82% 是 frontend、backend、size-class tuning、reclaim 和 concurrency protocol 的组合；论文没有逐个关闭 closed sibling tree、metadata shifting 和 lifetime tracker 的完整消融。手机 power 只测两个较稳定步骤，不能证明所有 workload 都按指令比例节能。

### 假设压力测试

Uniform slab 依赖小对象分布与 4 KB page；使用 16/64 KB page、对象集中在 2 KB 边界、huge page 或不同 alignment 时，重新选 class 后的 tail waste 和 cache locality 可能改变。Closed sibling tree 依赖固定 resolution set；若 allocator 为某类对象使用非规则 class 或 guard page，它的 closure 优势会下降。

两 buffer 把“活过一个 epoch”当成长寿近似。Phase 快速反转、周期性 burst 恰好跨越 swap、邻接 range 的 lifetime 不相关时，分类可能失效。论文用两个 service 的 lifetime CDF 支持假设，却没有报告误判率、`Δ` sweep 或 memory-pressure trace 下的 reclaim/syscall 数。

Non-blocking 只说明调用不因 fallback lock 持续等待。更大 range、deferred free、CAS retry 和 cache-line bouncing 都可能在 adversarial cross-thread pattern 下形成额外工作或内存；论文没有给形式化 progress class、fairness 或 footprint bound。

### 实验可信度

实验同时覆盖 instruction、throughput、peak/steady memory、P99.99、全机 counter、CPU/DRAM power 和商业部署，baseline 也包含三种成熟 allocator，证据维度很强。作者明确承认 microbenchmark 不能代表真实系统，并用实际手机补足，这比单纯 server allocator test 更可信。

外部有效性仍受限制。手机端只公开一款 Huawei flagship 和 HarmonyOS；Android 数据只用于动机，没做 drop-in A/B。真实场景约两小时、5 次，图 16 只画 top memory-consuming services；没有 foreground jank/frame deadline、background kill/OOM、thermal state、长时间 fragmentation 或低端设备结果。tcmalloc 由于兼容性被排除也使真实设备 baseline 少一个。

### 系统性缺陷

“Verified”容易让读者误以为整个实现已被证明。实际方法是以 assertions 作为 specification 的 bounded model checking；client 之外的语义、真实 bitmap 规模、OS/syscall failure、TLS teardown 与 sanitizer/MTE 组合不在完整证明内。论文也未给 LOC、验证 client 数、explored state 数或每项 property 的 coverage 表。

Allocator 是几乎所有进程的公共故障面。Closed sibling tree、metadata shifting、Nest/Knit 双所有权、deferred list 和同步/异步混合回收增加了实现复杂度。虽然 300 亿 user-hours 是很强的运行信号，但缺少 crash、corruption、rollback、memory-pressure incident 和旧/新 allocator 对照统计，无法据此量化 residual risk。

## 局限与后续工作

- **局限 1**：真实设备只覆盖 Mate 70 Pro/HarmonyOS 5.1；Android、低端 SoC、不同 page size 与 server workload 的收益未验证。
- **局限 2**：没有逐项关闭 closed sibling tree、metadata shifting 和 lifetime tracker 的完整消融，组合收益难精确归因。
- **局限 3**：两缓冲回收没有 `Δ`/watermark sensitivity、误判率、`madvise` 次数或长期 fragmentation 曲线。
- **局限 4**：有界验证缺少 client/state-space 清单，且不覆盖无限执行、完整 OS 交互和 memory-hardening 组合。
- **局限 5**：生产部署只给设备数与 user-hours，没有可靠性分母、故障分类和 rollout/rollback 过程。
- **后续工作 1**：在 4/16/64 KB page、低中高端 SoC 和 Android 上扫描 size class，报告 CPU、PSS、page fault、frame miss 与 background kill。
- **后续工作 2**：记录每次 buffer swap 的 range age、coalesce、`madvise` 和 reuse，比较固定 `Δ`、自适应 `Δ` 与 jemalloc epoch 的 footprint/CPU Pareto frontier。
- **后续工作 3**：建立 adversarial cross-thread free、thread death、memory pressure 与 syscall failure campaign，报告 progress、最大 deferred bytes 和 P99.999。
- **后续工作 4**：公开 verification client/property/界限矩阵，并逐步纳入真实配置、frontend–midend–backend composition 与 MTE/HWASAN。

## 相关

- **相关概念**：[[Garbage-Collection]]、weak memory model、non-blocking allocator、slab allocation
- **同类系统**：jemalloc、mimalloc、tcmalloc、Scudo
- **同会议**：[[OSDI-2026]]
