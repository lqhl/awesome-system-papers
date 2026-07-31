---
type: paper
name: Ichnaea
full_title: "Ichnaea: A Framework for Precise Tracking of Memory Objects"
authors: [Samad Haque, Sibin Mohan, Aaron Paulos, Partha Pal]
venue: OSDI
year: 2026
tags: [memory-tracing, debugging, mpk, dynamic-analysis, security]
source_pdf: "[[osdi26-haque.pdf]]"
source_md: "[[osdi26-haque]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 精确追踪内存对象的框架（OSDI 2026）

> **原题**：Ichnaea: A Framework for Precise Tracking of Memory Objects

> **一句话总结**：全 load/store instrumentation 太慢，传统 page protection 又因全线程 permission window 丢事件；Ichnaea 用 Intel MPK 的 per-thread page permission、SIGSEGV instruction emulation 和 syscall wrapper，只在目标对象被访问时记录 caller/thread/time/before-after，在 SPECInt 上相对 Intel Pin 快 12–60×，单次 fast-path access median 约 9 μs。

## 问题与动机

调试 control-flow object、forensics 和 memory bug 常需要回答“谁在何时读写了哪个 object、改了什么”。static analysis 会因 pointer alias、function pointer 和 path explosion 漏报/过近似；Pin/Valgrind/DynamoRIO 动态检查大量 instruction，常慢 10–100×；watchpoint 只有少数几个；`mprotect` 以 page 为粒度且 permission 对所有 thread 全局生效，handler 临时解锁会让其他 thread 的并发 access 漏过。

Ichnaea 的范围是 C/C++ 中少量预选 global/heap object。开发者加一条 registration annotation，runtime 对 backing page 禁止访问；真正 access 才触发 fault、模拟 instruction 并记录上下文。目标不是通用 memory sanitizer，而是以较低应用 slowdown 获得 precise per-access trace。

## 关键观察 / 隐含假设

- **观察 1**：MPK 通过 thread-local PKRU 改 permission，`pkey_set` 约 50 ns，不改 PTE/TLB；因此 handler 可以只为当前 thread 暂时 unlock，其他 thread 继续 fault，消除 `mprotect` 的 global read/write window（§2.1.3、§4.1）。
  - **依赖假设**：运行在支持 Intel MPK 的 x86，且可用 protection key 未被应用/其他 runtime 占用。
  - **可能失效场景**：无 MPK CPU、pkey exhaustion 或 application 自己改 PKRU 时，性能/正确性需另行处理。
- **观察 2**：只 trace 少数 object 时，fault frequency 与目标 access frequency相关，而不是总 instruction 数；这使 event-driven tracing 比全 binary instrumentation 更便宜（图 4）。
  - **依赖假设**：目标集合小且多数不在极热路径。
  - **可能失效场景**：trace all objects 或 hot global 与大量 unrelated data 共页时，fault storm 可超过 instrumentation。
- **观察 3**：faulting instruction 若在 handler 内直接 emulate，返回时 PKRU 自动恢复 locked state，就不需 INT3/second fault，缩短并发暴露窗口（图 3）。
  - **依赖假设**：decoder/emulator覆盖 workload instruction；复杂/floating-point instruction 走更慢 fallback。
- **假设 1**：source annotation 给出的 address/size/type 正确且测试/benchmark 能执行相关 path。
  - **证据强度**：使用前提；dynamic trace 不证明未执行路径安全，错误 annotation 会产生错误 trace。

## 核心方法

`ichnaea_register_obj(addr,size,name,type)` 建立 object/page metadata，并用 `pkey_mprotect` 给 page 标同一 key、当前 thread 禁止 R/W。`LD_PRELOAD=libIchnaea.so` 安装 SIGSEGV handler；fault 后判断 address 是否目标，thread-local unlock，解析 register/operand 模拟 read/write，记录 PID/TID、RIP/call stack、timestamp、before/after data，再跳过 faulting instruction返回（§3–§4.1）。

MPK 仍以 page 为粒度，page 上 unrelated access 也 fault，但 handler 只为真正 target 记录。global 可用 section macro 集中；heap allocator wrapper 自动识别已标 pointer 指向的 allocation，并以 page-isolated slab 隔离，避免 unrelated malloc object 造成 collateral fault（§4.5）。

kernel-mode copy 不触发 userspace SIGSEGV，只会返回 `EFAULT`。Ichnaea 因而 wrapper 常见 libc syscall，在进入 kernel 前临时 unlock、检查 argument 与 traced region、返回后按 hash/data变化记录并恢复。无法解析 target 的 inline/VDSO/复杂 `ioctl/readv` 仍可能漏 kernel read，故“complete”只限 user-space access（§4.3、§6）。

trace 先写 memory pool，程序退出后序列化 JSON，避免每 event file I/O。实现少于 2K C LOC、无 kernel modification；libunwind 是 handler 的主要可优化成本。

## 设计取舍

- **精确选择换 annotation**：不改 build system/不需 compiler pass，但用户必须知道要追踪什么，且 source 可修改。
- **per-access 完整上下文换 fault 成本**：fast path median 9 μs，仍比 native load/store 高多个数量级，只适合稀疏目标。
- **heap isolation 换内存**：10k small objects page isolation RSS 80.3 MiB，对 packed 4.2 MiB 是 19×；allocation 5.5 μs 对 728 ns 是 7.6×（表 4）。
- **userspace deployability 换 syscall coverage**：无需 privilege/kernel patch，但 inline syscall、未 wrapper interface 和 kernel read 可能缺失。
- **边界条件**：stack object 因共用活跃 stack page 不适合，trace all objects 也不是目标（§6）。

## 实验与结果

- Xeon Silver 4316、64 GiB、Ubuntu 24.04/kernel 6.14；SPECInt 与 PostgreSQL regression suite，对比 Intel Pin 和把同一实现改为 `mprotect` 的 tracer（§5.1）。
- SPECInt 中 Ichnaea 多数为 native 的 1–3× runtime，最差 xalan 4.8×；相对 Intel Pin 快 12–60×，Pin 自身 slowdown 12–86×（图 4）。
- 相对 `mprotect` tracer 快 1.3–7×；PostgreSQL suite native/Ichnaea/Pin real time 为 17/35/944 s，Ichnaea 比 Pin 快约 26×（表 3）。
- 2→100 traced objects、固定每轮 10k accesses 的 worst-case synthetic 中，每新增 20 objects runtime 增约 8%–10%；pooled per-object median access latency 约 15 μs且随 object count 差异少于 1%（图 5）。
- fast path 240 万 writes 中，从 attempted access 到 resume median/p99/top-1%-mean 为 9.0/19.5/21.9 μs；其中 handler launch median 2.2 μs，handler 6.1 μs，`pkey_set` 0.05 μs（表 5）。
- AFL++ synthetic target 的 17 个目标 path：native 4 min 全覆盖但不 trace；Ichnaea 25 min 覆盖并记录 17/17；Pin 超过 12 h 仍 0/17（表 6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| selective MPK tracing 显著快于 Pin | 图 4、表 3 | SPECInt、PostgreSQL、单 Xeon MPK platform | 强 |
| MPK 比全局 `mprotect` 更适合多线程对象追踪 | 图 4、§5.3.2 | 同一 tracer implementation 替换 permission mechanism | 强 |
| 单 event 延迟约 9 μs 且 tail 有界 | 表 5 | 240万 synthetic writes、fast path、global+heap | 强 |
| object count 本身不是主要 per-event cost | 图 5 | 100 个 8-byte objects、hot worst-case microbenchmark | 中 |
| 可用于 fuzzing-assisted trace | 表 6 | 单 synthetic AFL++ target、17 sites | 中 |

## 批判性分析

### 论证链条

论文从传统 page protection 的 global window 推出 per-thread MPK，是直接且有力的 observation→design；用同代码切 `mprotect` 的 baseline 也较好隔离机制收益。标题的“precise”基本成立于已注册 userspace object，“complete/lossless”则必须带上 syscall wrapper coverage、instruction emulator 和执行路径限定，论文正文也承认这些边界。

### 假设压力测试

最危险前提是目标少且不热。gcc/xalan hot global 已使 runtime 到 4.8×，trace all objects 可能比 Pin 更差。page sharing 会让 unrelated access 也触发 handler；隔离能缓解却带 19× small-object RSS。多 runtime 共享 MPK、signal nesting、application SIGSEGV handler 与 PKRU manipulation 的组合未充分测试。

### 实验可信度

真实 SPECInt/Postgres、mechanism baseline、micro breakdown、scaling 与 fuzzing 覆盖多个问题。Intel Pin adaptation 需要 static address 和手工 heap hooks，可能不是最优化实现；只在单 CPU/OS 上评测，缺少 nginx 端到端 case、多 socket、高 thread count 与生产 bug diagnosis。所有 object 由作者挑选，选择偏差会影响 overhead。

### 系统性缺陷

signal handler 内 instruction decoding、emulation、libunwind、custom allocator 与 logging 都必须 async-signal-safe；未覆盖 instruction 走 slow path，复杂 race 容易改变程序行为。syscall wrapper 不能拦 inline/VDSO，hash-based postcheck 也不能还原每次 kernel read。trace buffer overflow、recursive fault、fork/exec、dlopen 和 crash 时未 flush 的 forensic reliability 未量化。

## 局限与后续工作

- **局限 1**：stack object、全部 object 和极热 object 不适用；只声称 userspace complete（§6）。
- **局限 2**：instruction emulation 与 libc syscall wrapper 尚不完整，kernel read 可能漏报。
- **局限 3**：page-per-object heap isolation 对大量 small object 有明显内存/分配放大。
- **后续工作 1**：用真实 CVE/并发 bug 基准量化 root-cause time、trace completeness 与 semantic perturbation，而非只测 runtime。
- **后续工作 2**：实现 shared isolated suballocator，扫描 object density/access frequency 对 RSS、false fault 与 latency 的 Pareto frontier。
- **后续工作 3**：系统 fuzz instruction emulator、nested signal 与 syscall wrapper，并用 kernel/[[eBPF|eBPF]]辅助验证漏失率。

## 相关

- **相关概念**：[[Memory-Protection-Keys]]、[[Dynamic-Binary-Instrumentation]]、[[Memory-Safety]]、[[Watchpoint]]、[[Fuzzing]]
- **同类系统**：[[Intel-Pin]]、[[DynamoRIO]]、[[Valgrind]]、[[Dthreads]]
- **同会议**：[[OSDI-2026]]
