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
last_reviewed: 2026-08-14
---

# 精确追踪内存对象的框架（OSDI 2026）

> **原题**：Ichnaea: A Framework for Precise Tracking of Memory Objects

> **一句话总结**：Ichnaea 不再检查程序执行的每条 load/store，而是用内存保护键（Memory Protection Keys，MPK）让目标对象所在页在被访问时触发 SIGSEGV，再在当前线程中模拟指令并记录对象、调用栈、线程、时间和写前/写后值；它在九个 SPECInt workload 上把运行时间控制在 native 的 1.07–4.88 倍，但论文的“完整、无遗漏”只在已注册且实现已覆盖的用户态访问上接近成立，内核读、绕过 libc 的 syscall 和共享断点 slow path 都留下明确缺口。

## 问题与动机

调试内存破坏、并发错误或由数据驱动的控制流时，只知道“程序崩在什么地方”通常不够。开发者真正想知道的是：哪个线程、哪条指令、经过哪条调用链，在什么时间读写了哪个具体对象，写入前后又发生了什么变化。函数指针、别名、指针算术和动态分配会让这些访问位置很难提前找全；即使静态分析给出候选，它也容易因为路径爆炸而过度近似，或因间接控制流而漏掉真实访问（§1、图 1）。

传统动态二进制插桩会检查大量 load/store，因此 Pin、Valgrind 一类工具在这种“逐对象、逐访问、带完整上下文”的任务上常带来 10–100 倍 slowdown。硬件 watchpoint 又只有很少的 debug register，x86 通常只能同时监视 4 个很小的区域。另一条路线是把对象所在页设为不可访问，让 page fault 成为事件通知；但传统 `mprotect` 修改的是整个进程共享的页权限，还会修改页表、触发 TLB shootdown。一个线程临时解锁页面时，其他线程可以悄悄访问目标对象，syscall 和 atomic operation 尤其容易在这个全局读写窗口中丢事件（§2.1）。

Ichnaea 面向的是 C/C++ 中一组事先选定的 global 或 heap object。它接受少量源码标注，不修改 kernel，也不要求给整个程序和所有动态库加 compiler pass。核心目标不是做通用 memory sanitizer，而是在离线测试、benchmark、fuzzing 或 forensic run 中，以比全量插桩低得多的成本，获得少量关键对象的细粒度访问轨迹。

## 关键观察 / 隐含假设

- **观察 1：传统页保护真正导致漏报的不是“页太大”，而是临时解锁对所有线程可见。** MPK 把页面与 protection key 关联，而读写权限放在每个线程自己的 PKRU 中；`pkey_set` 的实测中位成本是 0.05 μs，一个线程解锁后，其他线程仍会 fault（§2.2、§4.1、表 5）。
  - **依赖假设**：目标机器支持 MPK，应用还能让出一个 key，而且程序自身不会任意改写相同 PKRU 权限。
  - **可能失效场景**：不支持 MPK 的平台、key 已被其他隔离 runtime 占满，或被测程序主动执行 WRPKRU/pkey API。
- **观察 2：如果只关心少量对象，成本可以与这些对象的实际访问次数相关，而不是与程序的全部指令数相关。** 对象未被访问时无需逐指令检查，访问发生时才支付 fault、解码、日志和 stack unwind 成本（§3.1）。
  - **依赖假设**：目标对象数量有限，且不是每条热路径都会反复访问它们。
  - **可能失效场景**：追踪所有对象、追踪极热 global，或目标对象与大量非目标数据共页时，SIGSEGV 数量会迅速上升。
- **观察 3：在 handler 中直接模拟 faulting instruction，可以把临时解锁限制在一次 signal handling 内。** 快路径不必修改共享 `.text`，也不必再执行一次 INT3；signal 返回时恢复原 PKRU，使页面重新锁定（§4.1、图 3）。
  - **依赖假设**：decoder 和 emulator 能正确覆盖 workload 使用的 x86 memory instruction，包括 operand size、addressing mode 和 side effect。
  - **可能失效场景**：atomic、SIMD、floating-point store 等未实现指令会进入 breakpoint slow path，正确性边界随之改变。
- **观察 4：触发粒度可以是 page，记录粒度仍可以是 object。** 同页的非目标访问也会 fault，但 handler 可按精确地址判断是否写日志；heap object 再通过独立页减少这种 collateral fault（§4.1、§4.5）。
  - **依赖假设**：额外 fault 或独立页的成本可接受。
  - **可能失效场景**：hot global 与普通数据共页会放大时间，成千上万个小 heap object 则会放大内存和分配成本。
- **假设 1：用户能正确指出要追踪的对象。** 注册 API 的 address、size、name、type 是可信输入；论文明确说错误 size 会产生错误 trace。
  - **证据强度**：这是使用前提，没有自动检查 annotation 与真实 C object layout 是否一致。
- **假设 2：测试运行已经执行了需要分析的路径。** Ichnaea 能记录一次运行中发生的访问，却不能证明未执行路径没有访问目标对象。
  - **证据强度**：基本的动态分析限制；论文用 test suite 和 AFL++ 扩大覆盖，但不提供路径完备性。

## 核心方法

开发者用 `ichnaea_register_obj(addr, size, name, type)` 注册目标对象，并用轻量 compiler directive 防止关键 store 被优化掉。程序正常编译，运行时通过 `LD_PRELOAD=libIchnaea.so` 加载不足 2K 行 C 的 runtime。注册时，runtime 建立对象地址到 backing page 的 metadata，用 `pkey_mprotect` 给这些页标上同一个 MPK key，再让当前线程禁止对该 key 的读写。以后还可以在运行中继续注册对象（§3.2、§4.4）。

用户态快路径分为五步（§4.1、图 3）：

1. 访问目标页触发 SIGSEGV，runtime 的 signal handler 先判断 fault address 是否落在已注册对象内。
2. handler 只修改当前线程的 PKRU，暂时开放所有使用该 tracer key 的页面；其他线程的权限不变。
3. handler 从寄存器和指令 operand 计算地址、大小和值，在 handler 内模拟这次 read/write；这样不必让原指令在正常控制流中重跑。
4. 只有精确命中目标对象时，才把 PID、TID、RIP、调用栈、时间戳、访问类型以及 write 的 before/after data 写入内存池；同页非目标访问只承担 fault 和模拟成本。
5. handler 把 RIP 移到下一条指令。signal 返回会恢复进入 handler 前的 PKRU，目标页再次不可访问；进程退出时再把内存池序列化为 JSON。

未被 emulator 支持的指令走 slow path（附录 A.9、A.11）。handler 在 faulting instruction 后一字节临时写入 INT3，开放页面后让原指令在 CPU 上执行；随后的 SIGTRAP 再锁页、恢复被替换的字节并记录访问。这避免了为所有 x86 指令一次性实现 emulator，却修改了所有线程共享的代码页：另一个线程若同时走到同一位置，即使操作完全不同的数据，也会撞上临时断点。论文承认这可能破坏执行，而且不能排除，只把它归为发生概率较低的工程限制。

内核访问不能依靠用户态 SIGSEGV 捕获。Ichnaea 因而 interpose 常用 libc 调用：wrapper 在 syscall 前为当前线程开放目标页，解析 pointer 或 iovec，调用结束后检查地址或比较对象 hash、写日志并恢复权限（§4.3、附录 A.6）。这个办法能覆盖论文 workload 使用的 `read`、`write`、`recv*`、`getcwd`、`getdents64` 等路径，也能通过状态变化发现部分 kernel write；但 inline syscall、VDSO 和未实现 wrapper 会绕过它。对于无法解析 read target 的 `ioctl`、`readv` 等调用，kernel read 会直接漏掉；没有实际读取数据的“空 read”也无法区分。

global object 可用专门 section macro 与普通 global 分开。对 heap object，用户注册保存 allocation 返回值的 pointer handle；被 interpose 的 `malloc/calloc/realloc` 查看 caller 中保存返回值的指令，判断这次 allocation 是否属于目标 handle。若属于，就返回 page-aligned、page-isolated slab；普通 allocation 仍交给原 allocator。论文在 gcc 和 clang 上验证了这个识别方法，并给 custom allocator 提供额外 macro（§4.5、附录 A.5/A.12）。stack object 因为与活跃调用栈共页，当前实现不支持。

## 设计取舍

- **事件触发换单次访问成本**：不访问目标对象时几乎没有逐指令成本；每次快路径 write 的端到端中位数仍是 9.0 μs，比普通几十纳秒的内存访问高两个数量级以上。
- **线程局部权限换硬件依赖**：一个 thread 的 unlock 不再暴露给其他 thread，但实现依赖 MPK 和 x86 instruction handling；“MPK 也存在于 ARM”不等于当前 prototype 已跨架构验证。
- **对象级日志换页面级 fault**：记录内容精确到对象，触发仍以 4 KiB page 为单位。global 共页会制造非目标 fault；heap 隔离又把空间问题转成每个对象接近两个 page 的实际开销。
- **源码标注换部署简单**：不改 build system、不重编动态库，也不用 kernel module；代价是必须有源码、人工选择对象并保证 annotation 正确。
- **用户态 wrapper 换 kernel 覆盖**：不需要特权和内核版本维护，但 syscall surface 很大，inline/VDSO/复杂参数让“完整内核访问轨迹”在 prototype 中并不成立。
- **小实现换未覆盖语义**：不足 2K C LOC 容易部署，却把 instruction emulation、async-signal safety、nested signal、allocator interaction 和 wrapper completeness 留成高风险工程面。
- **离线日志换崩溃耐久性**：先写内存池降低正常运行 I/O；论文没有量化 buffer 满、进程异常退出或 crash 前尚未 flush 时能保留多少 forensic data。

## 实验与结果

- 平台是 Intel Xeon Silver 4316 2.30 GHz、64 GiB、Ubuntu 24.04.2、Linux 6.14。作者从九个 C/C++ SPEC CPU 2017 integer workload 中各选 global 或 heap handle，运行 5 份副本；基线是自制 Pin pintool 和把 `pkey_set` 换成 `mprotect` 的同构 tracer。图 4 中 Ichnaea 是 native 的 1.07–4.88 倍，Pin 是 12.90–86.54 倍；逐项相除后，Ichnaea 在八项上约快 12–64 倍，但 xalan 只快约 3.7 倍，所以摘要“10–60 倍”没有覆盖两个边缘值。Pin 还不追踪 syscall，功能并非完全相同（§5.1–§5.3.1）。
- 与同代码的 `mprotect` 版本相比，Ichnaea 在 SPECInt 快 1.3–7 倍。PostgreSQL 的 real/user/sys time 分别为 native 17/4.9/4.3 s、Ichnaea 35/15.1/11.2 s、Pin 944/38.7/10.4 s；Ichnaea 的 wall time 是 native 的约 2.06 倍、比 Pin 快约 27 倍，同时更高的 system time 反映了 page fault 路径（§5.3.2–§5.4、表 3）。
- 快路径 microbenchmark 共记录 240 万次 write。handler launch 的 median/p99/top-1%-mean 是 2.2/3.0/6.0 μs，SIGSEGV handler 是 6.1/16.4/18.2 μs，端到端是 9.0/19.5/21.9 μs；作为机制对照，一次 `mprotect` 为 2.0/4.5/5.9 μs，传统 unlock window 为 4.0/8.8/11.2 μs，而 `pkey_set` 只有 0.05/0.08/0.10 μs。该表只测 emulator 快路径和 write，不覆盖 breakpoint slow path 或 read（§5.6.2、表 5）。
- 100 个 8-byte 对象（50 global、50 heap）的 worst-case workload 中，从 2 个追踪对象增加到 100 个，normalized runtime 约增至 1.7 倍；每增加 20 个约增 8%–10%，各 object-count 的 pooled access median 约 15 μs。50 个 global 共同放在一页，所以增加它们主要增加日志而不新增 fault；page-isolated heap 才是主要增量。正文说“所有对象各访问 10,000 次”，图 5 caption 却写“每次运行 10K accesses”，实验口径没有完全对齐（§5.5、图 5）。
- 10,000 个偏小随机 heap object、100 次迭代中，普通 packed allocation 的 RSS 是 4.2 MiB，page isolation 是 80.3 MiB，即 19 倍；每个对象实际占用从 0.42 KiB 增到 8.03 KiB。median allocation time 从 728 ns 增至 5.5 μs，即 7.6 倍；Ichnaea allocator interposer 还会再加约 500–600 ns。论文提出共享 isolated-region suballocator，但 prototype 未实现（§5.5、表 4、附录 A.7）。
- AFL++ 实验是一个合成的 memory-access-intensive target，其中 17 条路径会访问目标对象。原生 fuzzer 4 分钟覆盖 17/17、记录 0/17；加 Ichnaea 后 25 分钟覆盖并记录 17/17；经 AFLpin 接入 Pin 后超过 12 小时仍覆盖 0/17。它证明 Ichnaea 能让这个合成 tracing campaign 跑完，不足以证明真实大型程序上的 fuzzing 优势或普遍 trace completeness（§5.7、表 6）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| MPK 比全局 `mprotect` 更适合多线程按访问追踪 | 表 5：`pkey_set` median 0.05 μs，对比 `mprotect` 2.0 μs；权限只对当前线程开放 | 单台 Intel MPK 机器；只测 prototype 快路径 | 强 |
| 对少量已选对象，Ichnaea 明显快于逐 store 的 Pin tracer | 图 4、表 3：SPECInt 为 1.07–4.88 对 12.90–86.54 倍 native；PostgreSQL 为 35 对 944 s | 作者选择的对象；Pin 不含 syscall tracing，功能并非完全相同 | 强 |
| 快路径能给出细粒度上下文且端到端中位成本约 9 μs | 表 5：240 万 writes；日志包含 TID、RIP、stack、时间和 before/after | 只测可模拟的 write；未测 slow path、复杂 syscall 和 trace buffer 压力 | 强 |
| page-isolated heap object 有明显资源代价 | 表 4：10K object 的 RSS 4.2→80.3 MiB，allocation 728 ns→5.5 μs | 小对象随机分布、THP 关闭、未计 tracer 本体 | 强 |
| “完整、无遗漏”适用于所有应用/库/内核访问 | §4.3、§6、附录 A.9：kernel read 会漏，inline syscall 可绕过，slow path 有共享断点 race | 论文自己给出的限制直接反驳无条件版本 | 弱 |

## 批判性分析

### 论证链条

论文最扎实的部分是从 `mprotect` 的全线程解锁窗口推导 thread-local MPK，再用同一份 tracer 只替换权限机制进行对照。这个 observation 与 design 之间几乎没有跳步；表 5 也把 `pkey_set`、fault launch、handler 和总时延拆开，让 1.3–7 倍的机制收益有可解释来源。相较之下，标题中的“precise”与正文中的“complete/lossless”混在了一起：精确记录命中对象的含义比较清楚，是否覆盖每种访问来源则依赖 wrapper 和 emulator 的工程完整度，两者不能由 MPK 本身保证。

### 假设压力测试

系统最脆弱的假设是“目标少且不热”。图 4 已给出反例：xalan 因 hot global 和同页数据，Ichnaea 自身达到 4.88 倍 native，相对 Pin 的优势缩到约 3.7 倍。若追踪对象覆盖大量 heap、所有 global 或 allocator metadata，fault storm、stack unwind 和日志带宽会压过省下的插桩成本。若应用自己使用 MPK，单一 tracer key 还会带来 key ownership 与 permission composition 问题；论文没有实验这类 coexistence。

快路径的正确性还依赖完整 instruction semantics。读取 register 并手工执行 memory operand 不只是“把值拷过去”：atomicity、flags、fault ordering、partial write、vector lane、lock prefix 和 restart semantics 都可能影响被测程序。未覆盖指令进入 shared `.text` breakpoint slow path，论文明确承认另一个线程可能误入 SIGTRAP 并破坏执行。只要这个路径会在真实 workload 出现，“所有访问无遗漏且不改变程序行为”就不能作为无条件系统属性。

### 实验可信度

SPECInt、PostgreSQL、同构 `mprotect` baseline、event breakdown、object scaling、heap memory 和 fuzzing 让性能论证覆盖面很好。作者还故意不对 xalan 做 global placement 优化，能看到 page sharing 的坏情况。不过对象由作者挑选，访问频率和数量没有系统扫描；Pin 的实现需要额外 static-address discovery、逐 store filter 和手工 heap hook，且不做 syscall tracing，功能与工程成熟度并不完全等价。论文没有用 ground-truth trace 对比 event 数，也没有把所有受支持/不支持指令、syscall、动态库访问做 coverage matrix，因此 R2 的 completeness 主要是架构论证，不是端到端测量。

报告本身也有两处应保留的数字边界。第一，图 4 的逐项比例包含约 3.7 倍和约 64 倍，不能严格概括成摘要的 10–60 倍。第二，object-scaling 正文与图注对“10,000 accesses”的分母描述不同。这些不推翻总体性能趋势，但会影响精确复算和 workload intensity 的判断。

### 系统性缺陷

libc wrapper 无法覆盖 direct syscall、VDSO 和所有复杂 pointer argument；对于无法解析的 read target，论文明确说会漏 trace。kernel write 的 post-state hash 只能说明对象变了，未必能重建 kernel 在一次调用中做过的每个中间访问。stack object 不能追踪，程序异常退出前的内存日志是否落盘也没有保证。与此同时，signal handler 内还要完成 instruction decode、libunwind、clock、logging 和 allocator-safe 操作；作者称其 async-signal-safe，但没有用 nested signal、fork/exec、dlopen、alternate signal stack、buffer exhaustion 或 adversarial reentrancy 做系统验证。

因此，Ichnaea 更准确的定位是“低开销、选择性的用户态对象访问 tracer framework”，而不是已经覆盖任意 C/C++ 程序所有 memory access source 的完整观察层。这个较窄定位仍然很有价值，也更符合论文真正展示的证据。

## 局限与后续工作

- **局限 1**：只能追踪预先注册且 annotation 正确的 global/heap object，不支持普通 stack object，也不保证测试未执行路径的覆盖。
- **局限 2**：当前 emulator 不覆盖所有 x86 instruction；atomic、SIMD 等 slow path 会修改共享代码并存在跨线程误触断点的正确性风险。
- **局限 3**：kernel read coverage 不完整；inline syscall、VDSO、未包装 libc API 和解析不了的复杂参数都可能漏报。
- **局限 4**：page granularity 会让同页非目标数据产生 collateral fault；逐对象 heap isolation 则带来约 19 倍 RSS 和 7.6 倍分配时间。
- **局限 5**：只在一台 Intel Xeon、一个 Linux 版本上评测，没有跨 CPU、不同 MPK 实现、[[NUMA|NUMA]] 和高线程数压力测试。
- **局限 6**：没有用独立 ground-truth oracle 测 trace precision/recall，也没有量化 signal/reentrancy 对程序语义的扰动。
- **后续工作 1**：建立 instruction/syscall conformance suite，把每种 opcode、atomic interleaving、libc/direct syscall 的预期事件与实际 trace 逐项比对。
- **后续工作 2**：实现不修改共享 `.text` 的 slow path，或用受控 single-step/hardware facility 消除跨线程 breakpoint race，并报告 slow-path 命中率。
- **后续工作 3**：实现共享的 isolated-object suballocator，在对象数量、大小、访问热度和 page density 上画出 latency–RSS Pareto frontier。
- **后续工作 4**：用真实 CVE、并发 bug 和 nginx/PostgreSQL 故障案例，测“从 trace 到 root cause”的时间，而不只测 benchmark runtime。
- **后续工作 5**：让 kernel/[[eBPF|eBPF]] 或 seccomp 辅助记录绕过 libc 的 access，并以 ground truth 量化新增覆盖和额外权限成本。

## 相关

- **相关概念**：Memory Protection Keys、动态二进制插桩、page fault、object-level tracing、fuzzing
- **同类工具**：Intel Pin、DynamoRIO、Valgrind、基于 `mprotect` 的 tracer
- **同会议**：[[OSDI-2026]]
