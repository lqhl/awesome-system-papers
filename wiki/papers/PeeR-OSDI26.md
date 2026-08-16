---
type: paper
name: PeeR
full_title: "PeeR: First-Class Scheduling for Latency-Critical eBPF Applications"
authors: [Jeremy Carin, Ben Holmes, Weiyang Wang, Ankit Bhardwaj, Manya Ghobadi]
venue: OSDI
year: 2026
tags: [ebpf, scheduling, preemption, tail-latency, kernel]
source_pdf: "[[osdi26-carin.pdf]]"
source_md: "[[osdi26-carin]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 延迟关键 eBPF 应用的一等调度（OSDI 2026）

> **原题**：PeeR: First-Class Scheduling for Latency-Critical eBPF Applications

> **一句话总结**：复杂 [[eBPF]] 程序已不再“短而均匀”，不可抢占的 softirq 会造成队头阻塞并逃过 CPU accounting；PeeR 在 verifier 认定安全的 helper boundary 做协作式抢占，把超预算 invocation 续跑到 per-CPU kernel thread，并交给 `sched_ext` 调度，使短请求 p99 降低 3–19.8 倍，一次完整 yield/resume 的平均成本为 247 ns。

## 问题与动机

XDP 等 latency-critical hook 在 softirq 中执行。这个路径快，是因为程序收到 I/O event 后立刻 run-to-completion，不发生普通 thread context switch；代价是 CPU scheduler 看不见是谁消耗了这些时间，通常把它记到刚好被 interrupt 的 userspace process。`ksoftirqd` 只能把后续一批 request 延后，不能在一个长 eBPF invocation 中间停下，也不能按安装 hook 的应用区分租户（§2）。

这种设计来自早期 packet filter 的 fast-path assumption：每个程序都很短，执行时间也很接近。现代 eBPF 已经承载 key-value store、transaction、load balancer、transport 和 storage logic。论文分析七个应用：Cilium 单个程序有 7,622 条 instruction 和 233 个 helper/kfunc call site；Redis-KFlex 的 p50/p99 是 0.5/248 μs，[[RocksDB|RocksDB]] XRP 是 4/882 μs。静态 verifier 的一百万 instruction 上限并不能保证实际运行时间短（§3.1、表 1）。

直接后果有两个。第一，同一应用中，长 invocation 会挡住后来的短请求；Redis-KFlex 的 99.5% GET、0.5% SCAN workload 中，200 μs SCAN 让 0.2 μs GET 的 p99 相对假想 5 μs 抢占模型恶化最多 7.4 倍。第二，不同应用共机时，Redis-KFlex 即使名义上只分到 50% CPU，仍可在高负载下使用 90%，挤压 colocated job（§3.2、图 1–2）。

## 关键观察 / 隐含假设

- **观察 1：helper/kfunc boundary 提供了 verifier 已知的程序状态。** verifier 在这些位置知道 register、stack、pointer、lock、reference 和 liveness，PeeR 可据此判断是否能保存和恢复（§4–§6）。
  - **依赖假设**：目标程序会频繁调用 helper，并且调用点没有活跃的 RCU pointer、spin lock 或其他未释放资源。
  - **可能失效场景**：XRP 每次 data-block scan 可在没有 helper 的约 100-instruction loop 中运行 2,000 次，即约 20 万条 instruction；纯计算段仍不能被 PeeR 截断（§3.1）。
- **观察 2：只把超预算的长任务移出 softirq，就能保留短任务 fast path。** 常见 invocation 不需要一开始就变成 thread（图 3）。
  - **依赖假设**：存在一个 quantum，能让大多数短任务直接完成，同时足够快地切断长任务。
  - **可能失效场景**：service time 接近单峰、任务都短于 budget 时收益很小；budget 太小则频繁 yield，吞吐和延迟都会变差。
- **假设 1：hook input 可以延长生命周期，最终 verdict 也能晚一些执行。** 这决定了 continuation 是否能离开原调用栈。
  - **证据强度**：中。论文完整实现 native XDP 的 packet retention 和五类 action；tc terminal action、XRP 等只做 design-time audit，未端到端实现（§6.2、表 3）。
- **假设 2：应用允许 invocation interleaving，或会自己同步共享状态。** PeeR 保证 memory safety，不保证原来 run-to-completion 带来的逻辑原子性和 per-core completion order。
  - **证据强度**：弱到中。论文明确说明语义变化，但没有对现有大规模 eBPF 程序做 data-race compatibility study（§6）。

## 核心方法

PeeR 修改 x86 eBPF JIT，在 verifier 认定安全的每个 helper site 前插入很短的 budget check。scheduler 每个 quantum 更新 per-CPU epoch/flag；程序开始时记录 epoch，helper 前比较当前值。没有超时就直接调用 helper，常见路径只增加 1 cycle，scheduler 正在写 flag 时为 2 cycles；超时才跳到该 site 对应的 yield stub（§5.1、图 5）。

yield handler 先保存 11 个 register、512-byte BPF stack、program context、`site_id` 和 task reference，共 600 bytes 的连续 register/stack state。native XDP 的 packet buffer 原本只在当前 NAPI poll 内有效，PeeR 不复制 packet，而是把它重新绑定为 reference-counted `xdp_frame`，返回新的 `XDP_YIELD` verdict，让 driver 视为已经消费并继续 poll。continuation 完成后才归还 frame（§5.1）。

超预算 task 先进入本 CPU 的 continuation buffer，再由同 CPU 的 PeeR-kthread 续跑。worker 的 stack 和 context 地址不同，原寄存器中的 pointer 不能原样恢复。PeeR 在 JIT 前导出 verifier 对每个 site 的 `PTR_TO_STACK` 和 `PTR_TO_CTX` 信息，生成 patch descriptor；resume 时按 old/new base 重定位这些 pointer，scalar 保持不变。多条 control-flow path 对同一位置类型不一致时，只保留所有路径一致的交集（§5.2、图 6）。

worker 需要间接跳回原 helper call，但 CPU 的 Control-Flow Integrity 不允许跳到任意地址。PeeR 为每个 site 生成以 `endbr64` 开头的 trampoline，先满足 indirect-branch tracking，再相对跳转到 helper。yield check 就在 helper 前，所以 resume 后 helper 正好执行一次，不会漏掉或重复 side effect（§5.2）。

PeeR 只在没有活跃 RCU-protected pointer、BPF reference 或 lock 的 site 插入 check。它结合 verifier 的 pointer type 和 liveness，判断 map-value pointer 是否已在最后一次 dereference 后变成 dead。spin lock 区域内 verifier 本来也禁止普通 helper call，PeeR 对少数仍允许的 kfunc 继续检查 `active_locks`。这个限制保护 use-after-free，却使抢占间隔完全取决于程序何时到达下一个安全 helper（§5.3、§6.1）。

调度分两层。外层 macro-scheduler 是 `sched_ext`，把 PeeR-kthread 当普通 kernel thread，决定所有 slow-path eBPF 合计能用多少 CPU；内层 micro-scheduler 在每个 PeeR-kthread 中按 FIFO、SRPT、WRR 等策略排列 continuation。softirq 和 worker 每次执行都写入 per-CPU `runtime_event` ring buffer，userspace daemon 异步汇总到 application/cgroup；scheduler 据此调整 kthread share 和下一轮 budget（§7）。continuation 不跨 CPU 迁移。

正确性还要求逐 hook 审计三个条件：input 能保留、caller 不要求立即拿到结果、caller 没有跨调用持锁。当前实现只覆盖 native single-buffer XDP，并在 resume 后支持 DROP、ABORTED、PASS、TX 和 REDIRECT；multi-buffer 与 tail-call XDP program 在 load time 被拒绝。tc 只适合 terminal action，tracing/LSM 需要同步结果或可能在 caller lock 内执行，因此不兼容当前模型（§6.2、表 3）。

## 设计取舍

- **verifier-safe yield 换抢占粒度**：不会在任意机器指令处打断，因此状态可重建；helper-free loop、长 helper 本身或长期持有 RCU pointer 的区域仍会阻塞。
- **softirq fast path 换双路径复杂度**：短任务开销很小，长任务却需要 frame ownership、state save、pointer patch、CFI trampoline、continuation queue 和 worker lifecycle。
- **短请求 latency 换长请求 deep tail**：短任务可越过长任务；长任务在高负载下会被重复推迟，SRPT 还会把代价集中到最长一类请求。
- **per-CPU ownership 换负载均衡**：task 不迁核简化 packet/context ownership，但热点 RSS queue 的 backlog 不能借用空闲 CPU。
- **memory safety 换旧语义兼容性**：PeeR 保证 pointer 和 hook object 有效，却允许 later invocation 在 earlier invocation 挂起时修改共享 map；旧程序若依赖隐式原子性，必须补显式同步。
- **可配置 policy 换估计和控制成本**：SRPT 需要应用提供 remaining-work hint；accounting 还依赖 userspace daemon 异步消费事件。

## 实验与结果

- **Redis 的短请求 tail 明显下降**：实验使用两台 28-core Xeon Gold 5420+、256 GB 服务器、ConnectX-7 400 Gbps NIC 和修改后的 Linux 6.16，默认 quantum 为 5 μs。99.5% GET/0.5% SCAN 中，PeeR 相对默认 eBPF 将 GET p99 降低 19.8 倍，相对 userspace KeyDB 吞吐高 3.77 倍，相对默认 eBPF 吞吐还高 10.3%。在 1.5 Mrps，cpumap/default/PeeR 的 GET p99 分别为 403/581/31 μs；cpumap 近饱和时 SCAN p99 达 350 ms，PeeR 为 4 ms（§8、§8.1.1、图 8）。
- **Memcached 仍有隔离收益，但吞吐并非总会增加**：50% GET/50% SCAN 中，PeeR 把 GET p99 降低 4.5 倍；KFlex 有无 PeeR 都比 userspace 高 3.46 倍吞吐。由于这个 workload 的请求更短、queue buildup 较轻，PeeR 总吞吐略低于默认 eBPF（§8.1.1、图 8）。
- **policy interface 能表达不同目标，但长请求 deep tail 会付费**：TPC-C transaction profile 驱动的 XDP echo workload 中，FIFO 抢占已优于默认 eBPF；300 krps 时，SRPT 把 mean latency 降低 3 倍，短 Payment 持续受益，长 StockLevel 在高负载下的 p99.9 则高 1.5–1.7 倍。Redis 3.1 Mrps 附近，SCAN p99.9 也从默认 eBPF 的 2,562 μs 增到 5,952 μs，即 2.3 倍。这不是完整 TPC-C 数据库，而是按五类 transaction duration 做 spin 的 synthetic workload；operator 可提高 budget 或 priority，但不能无代价地同时最小化所有 class 的 tail（§8.1.2、图 9–10）。
- **跨应用 accounting 恢复 CPU policy**：50/50 共机时，无 PeeR 的 BMC 让 batch throughput 只剩 fair share 的 30.9%，Memcached 让 batch CPU 降到 7%；PeeR 维持目标份额。Redis-KFlex 实验把 batch target 从 0% 调到 75%，PeeR 的跟踪误差在 6% 内（§8.2、图 11）。
- **单次抢占很便宜**：超过一百万次测量中，preemption 为 77 ns，其中 flag cache miss 17 ns、其余保存路径 60 ns；resume 为 170 ns，其中 batched kthread activation 46 ns、DSQ selection 80 ns、restore 44 ns，总计 247 ns（§8.3.1、图 12）。
- **quantum 存在 U 形取舍**：5 μs echo request 中，500 ns budget 的峰值为 275 krps，10 μs 可匹配 no-preemption 的 330 krps。95% 0.5 μs/5% 100 μs workload 中，2 μs budget 的短请求 p99 最低，为 31 μs；500 ns–1 μs 时是 110–190 μs，200 μs 时因队头阻塞升到 565 μs（§8.3.3、图 13–14）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 现代 latency-critical eBPF 已打破短且均匀的 fast-path assumption | 七个应用的静态分析和 runtime p50/p99；Redis/KFlex 阻塞与共机实验（表 1、图 1–2） | 每个应用只分析最大单个 program；动态反例主要来自 KFlex | 强 |
| helper boundary 能支持低成本、memory-safe continuation | verifier descriptor、RCU/lock 筛选、XDP frame retention；完整 cycle 247 ns（§5–§6、图 12） | x86、native XDP、Linux 6.16；不是任意 hook | 强 |
| PeeR 显著改善 bimodal workload 的短请求 p99 | Redis 19.8 倍、Memcached 4.5 倍；TPC-C-derived workload 3 倍 mean latency（图 8–10） | 两台服务器、合成 mix；长请求 deep tail 会退化 | 强 |
| PeeR 能让 scheduler 执行 eBPF/userspace 的 CPU share | batch fair-share 与 0%–75% weighted target 实验（图 11） | 一个 batch job 与三种 eBPF app；accounting daemon failure 未测 | 强 |
| 一个固定 quantum 能普遍兼顾 throughput 和 latency | 预算扫描呈明显 U 形，最佳点随 workload 改变（图 13–14） | 仅 echo 和 95/5 synthetic mix | 弱 |

## 批判性分析

### 论证链条

论文先用真实程序证明 fast-path assumption 已失效，再分别量化队头阻塞和 scheduler invisibility，随后把 verifier 的既有信息转成 safe point，链条很扎实。它还明确区分了 memory safety、hook safety 与 application semantics，没有把“能正确恢复 register”夸大成“旧程序语义完全不变”。最大的外推是从完整 XDP implementation 推到更广泛的 eBPF runtime；其他 hook 仍要逐一保留 input、延迟 verdict 并审计 caller lock。

### 假设压力测试

协作式抢占的最坏延迟由两个量决定：quantum 到期时间，以及到下一个安全 helper 的时间。论文只系统扫描前者；XRP 的约 20 万 instruction helper-free loop 已经说明后者可能很大。另一个压力点是 per-CPU 固定放置：RSS skew、flow hot spot 或 service-time skew 会让一个 PeeR-kthread 堆积 continuation，即使别的 CPU 空闲。

### 实验可信度

实验覆盖 Redis、Memcached、TPC-C-derived mix、三种 policy、跨应用公平性和细分 nanosecond overhead，并主动报告 SCAN/StockLevel p99.9 退化，证据质量高。不过 TPC-C 只是 echo server 按 duration spin，不含数据库锁、I/O 和共享状态；硬件与 kernel version 都只有一种。400 Gbps NIC 并不等于 workload 实际跑满 400 Gbps，图 8 的峰值只有约 12 Gbps，因此还不能证明极端 packet rate 下 continuation 路径同样稳定。

### 系统性缺陷

约 5,000 LOC kernel/JIT/scheduler modification 扩大了 trusted computing base 和升级维护面。论文未量化 continuation buffer 满、userspace accounting daemon 停止、runtime event 丢失、worker crash 或 overload backpressure。更重要的是，原本依赖单核 run-to-completion 的共享 map 代码可能在 PeeR 下出现新 race；这类兼容性风险可能比 247 ns 的运行时成本更难部署。

## 局限与后续工作

- **局限 1**：当前只实现 native single-buffer XDP；multi-buffer、tail-call XDP 和其他 hook 没有端到端支持（§6.2、表 3）。
- **局限 2**：纯 cooperative preemption 无法限制 helper-free region 或长 helper 的 blocking time。
- **局限 3**：continuation 不跨 CPU 迁移，缺少 work stealing 和热点 queue 的负载均衡。
- **局限 4**：PeeR 改变 invocation interleaving 和 completion order，论文没有给出现有应用的兼容性自动检查。
- **后续工作 1**：对表 1 全部应用测量最长 verifier-safe gap 的 p99/p99.9，并探索 compiler-inserted safe poll 或有严格 safe-point metadata 的 hybrid interrupt。
- **后续工作 2**：在真实 transactional eBPF 程序上做 race detection，比较启用前后 shared-map race、错误结果和同步开销。
- **后续工作 3**：实现 [[NUMA]]-local work stealing，在 RSS/flow skew 和 overload 下同时测 short/long p99.9、cache miss 和公平性。
- **后续工作 4**：加入 continuation queue 限额、event-loss 检测和 daemon failure fallback，验证过载时不会无限占内存或失去 accounting。

## 相关

- **相关概念**：[[eBPF]]、[[NUMA]]
- **相关论文**：[[vBPF-OSDI26]]、[[bpftime-OSDI25]]、[[XSched-OSDI25]]、[[GPreempt-ATC25]]
- **同会议**：[[OSDI-2026]]
