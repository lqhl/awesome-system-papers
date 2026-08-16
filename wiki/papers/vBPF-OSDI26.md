---
type: paper
name: vBPF
full_title: "Virtualizing eBPF with Late-Binding"
authors: [Jing Zhang, Xiaguannan Song, Dong Du, Yubin Xia, Binyu Zang, Haibo Chen]
venue: OSDI
year: 2026
tags: [ebpf, virtualization, multi-tenancy, kernel-isolation, late-binding]
source_pdf: "[[osdi26-zhang-jing.pdf]]"
source_md: "[[osdi26-zhang-jing]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# vBPF：用晚绑定虚拟化 eBPF（OSDI 2026）

> **原题**：Virtualizing eBPF with Late-Binding

> **一句话总结**：Linux 把 eBPF program 在加载时固定到全局 physical hook，适合单一信任域，却会让不同租户争 singleton hook、顺序执行无关程序并共享可修改的 kernel state。vBPF 在 hook 前放一个 multiplexer，等事件发生后才判断属于哪个 eBPF namespace，再查找该租户的 program 与 state view；跨租户 lmbench latency 最多改善 3.9×，PostgreSQL throughput 最多提高 29%。它证明 late binding 是可行架构，但“安全隔离”的可信根仍包括修改后的 kernel、verifier/JIT、编译期 analyzer 和人工标注，当前 prototype 对 kfunc 与 RCU reader 的处理还不完整。

## 问题与动机

平台方已经用 [[eBPF]] 实现 Cilium、Falco、observability 等全局服务；越来越多 tenant 也希望为自己的 database、scheduler、network 或 tracing 动态加载 program。Linux eBPF 的原始设计默认这些 program 属于同一管理域：program 在部署时验证、加载并静态绑定到 physical hook，事件发生后 hook 按固定列表执行，program 看到的是共享 execution context 和 kernel objects（§1–§2.2）。

多租户下有三类冲突（§2.3）：

1. **Singleton conflict**：`struct_ops`、`sched_ext`、部分 iterator 等全局 hook 只有一个实现，先注册者独占，其他租户无法使用不同策略。
2. **Functionality conflict**：两个各自正确的 program 顺序修改同一 packet、return value 或 kernel object，组合后可能形成无限 redirect loop，或污染后续 program 的输入。
3. **Performance interference**：无关 program 也会被全局 hook 调用。每个 program 自己检查 PID/cgroup 仍先付一次 invocation cost，program 数增加时成本线性累积；raw tracepoint 还会在所有 syscall 上触发（图 3）。

In-program filter 不可强制且仍执行所有 program；cgroup dispatch 依赖 process context，覆盖不了 XDP 等 interrupt event，也不能切分 singleton hook 或 state；平台 orchestrator 把多份代码合成 monolithic program/tail-call chain，会增加 verifier 压力并使单租户更新变成全局重编译；KrakenGuard 一类 admission control 能拒绝冲突，却不能让冲突策略同时存在（§2.4、表 1）。vBPF 因而把问题定位到绑定时机：physical hook 应只是通用 interposition point，program、tenant 和 state 在事件归属清楚后再绑定（§3）。

## 关键观察 / 隐含假设

- **观察 1：事件属于逻辑 tenant，而不是固定 hook。** 同一个 kprobe、TC 或 `struct_ops` hook 可由多个 namespace 各自拥有逻辑 program；runtime 只执行与当前事件有关的 program，物理 hook 本身不再表达租户身份（§3.1–§3.3）。
  - **依赖假设**：每个需虚拟化的事件都能可靠归属到一个 namespace 或明确的 namespace set；无法归属的 platform interrupt 留在 host namespace。
- **观察 2：interrupt 虽没有可靠 `current`，但通常携带先前建立的资源。** Socket/flow 在 `bind`、`connect` 等 process context 中创建，block I/O 也由某个 tenant 提交；先记录 resource→namespace，interrupt 到来时便可反查（§4.1、图 4）。
  - **困难场景**：一个 `bio/request` 可能合并多个 tenant，Snifer 需传播 namespace set；tunnel、connection migration、resource reuse 和 teardown race 都要求映射生命周期准确。
- **观察 3：租户索引可跳过无关 program。** Native kprobe linked list 或 tracepoint array 必须线性扫；vBPF 先按 namespace hash lookup，再执行该租户的 contiguous program array。论文称租户入口为 `O(1)`，严格说这是 hash table 的平均情况，且同一租户内部 program 数仍会影响执行时间（§4.2）。
- **观察 4：父 namespace 的可见性可在加载时展开。** Tenant event 需要从 child 向 root 传播，使 host audit program 能观察、修改或 veto；vBPF 在 attach/update 时预计算 flattened path，runtime 顺序遍历数组（§3.3、§4.2）。
  - **取舍**：减少每次递归查找，却增加每个 child 的 path memory 和 parent update 成本；“常数 dispatch”不包括真正执行的 ancestor programs。
- **观察 5：eBPF 改 kernel state 必须经过 verifier 可见接口。** Helper 和 kfunc 是天然检查边界；compiler plugin 可拒绝未经审计的 global write，variables library 再把合法写入导向 per-namespace state 或 semantic overlay（§4.3）。
  - **依赖假设**：接口集合与 pointer side effect 分析是完整的，人工 `vbpf_safe` 标注正确。当前实现主要覆盖稳定的 helper API，kfunc 支持仍是讨论中的扩展。
- **假设 1：host 软件栈可信。** Threat model 信任 host kernel、eBPF verifier/JIT、container runtime 和管理员；不处理 compromised host、verifier/JIT bug、hardware fault、microarchitectural side channel 或 resource exhaustion（§2.5）。因此 vBPF 是共享 kernel 内的逻辑隔离，不等同于 MicroVM 的硬件边界。

## 核心方法

### 分层 eBPF namespace 与 virtual hook

vBPF 新增与 process 绑定、可分层的 eBPF namespace。它沿用 Linux namespace 操作：用 `clone`/`unshare` 新建，以 `setns` 加入；因此 container runtime 可把 tenant program 与独立 namespace 绑定，而不必把安全策略和 cgroup resource hierarchy 混在一起。Parent namespace 可以观察 child event，host 仍保留全局 audit 能力（§3.3）。

每个 physical hook 只安装一个 lightweight multiplexer。Tenant program 不直接 attach 到 hook，而是登记在 namespace 下；事件触发时，multiplexer 先取得 namespace，再交给 Dispatcher 选择逻辑 program。这样 singleton hook 对 kernel 仍只有一个 occupant，对租户却可呈现多个独立 virtual hooks（§4.2、图 5）。

### vBPF Snifer：两阶段事件归属

论文把组件名拼作 Snifer。Context-aware phase 在有 process context 的资源建立路径插桩，writer 从高层对象提取 key 并写入 resource registry；context-free phase 从 packet、`xdp_md`、`bio/request` 等 interrupt metadata 中由 reader 提取同一 key，调用 `resolve()` 找 namespace（§4.1、表 2、图 4）。

网络实例用 packet headers 和 5-tuple，并在 setup、bind、accept 不同阶段逐步细化映射；storage 实例跟踪 `bio/request`，合并或拆分时传播 namespace set；task sniffer 在 namespace 销毁前保留稳定 task→namespace mapping，以处理 exit path 的迟到事件。IPI、device hotplug 等没有合理 tenant owner 的 platform event 仍只进入 host（§4.1）。

### Dispatcher：hash lookup 与层级展开

Dispatcher 的 hash map 以 eBPF namespace 为 key，value 指向该租户的 contiguous program array；RCU 让 Snifer resolve 和 namespace lookup 的读路径无锁，insert/remove 负责生命周期并异步回收。可选 Bloom filter 在 key 集合很大且 miss 多时提前拒绝 lookup（§4.2、§5）。

需要 parent audit 时，attach 阶段预计算从 tenant 到 root 的 program chain。事件先跑最具体 tenant，再逐层到 root；child 对 context 的修改对 parent 可见，parent 可覆盖 return code。Parent program 更新时，相关 flattened arrays 原子替换，避免 runtime 读到半更新路径（§4.2）。

### 编译器辅助的 state isolation

Clang frontend plugin 用两个 attribute 审计 kernel 暴露给 eBPF 的接口：`vbpf_helper` 标出完整 API surface，`vbpf_safe` 是 kernel developer 对可修改状态接口的人工批准。Taint analysis 默认把 pointer argument 当不安全，再读取 verifier-visible prototype；只指向 eBPF stack、tenant-local map 或 read-only region 的 pointer 可判为安全。未批准的 global state write 会在编译 vBPF kernel 时失败（§4.3）。

Variables library 对两类状态分别处理：

- **Tenant-private variable**：用 `VBPF_VARS_DEFINE` 声明一组变量，以 `VBPF_FIELD_INIT` 注册初始化，第一次 `VBPF_VARS_GET(ns, ...)` 时 lazy allocate；同组 lock 和 data 来自同一 namespace instance。
- **Shared kernel object**：基于 kernel BTF 预解析 object layout。Helper 执行前建立 overlay context，执行后可 snapshot 比较自动 `capture`，或显式 `update` 某个 field；patch 存进当前 namespace。切换 tenant 时先 restore clean base，再 apply 对方 patches（§4.3、图 6–7、Listing 2）。

### 实现与 hot-path 优化

原型基于 Linux 6.12、LLVM 20，kernel 约 12K LoC，Clang plugin 约 1K LoC。RCU hash table 优化 lookup；`kmem_cache` 和 memory pool 预分配 hot-path objects，避免 critical section allocation failure；tenant state 则第一次访问才 lazy allocate。Dispatcher path 和 BTF field offsets 都在 setup 时预计算，把工作从事件路径移到较少发生的 attach/init 阶段（§5）。

## 设计取舍

- **晚绑定换每个事件的 attribution/lookup**：跳过其他 tenant program，避免线性 noisy-neighbor cost；即使 co-located 也要付 Snifer、namespace 和 program lookup。
- **独立 eBPF namespace 换 kernel 改动**：policy 与 cgroup 解耦、支持 singleton virtualization；需要修改 Linux 与 container integration，不能直接部署在 stock kernel。
- **resource registry 换 interrupt 归属能力**：XDP/storage completion 不依赖错误的 `current`；memory 随 live flows/requests 增长，resource-exhaustion 又明确不在 threat model。
- **flattened path 换 runtime 简单**：child→root audit 快；namespace 层级深或 parent program 常更新时，复制和原子替换的控制面成本增加。
- **default-deny analyzer 换 API 维护工作**：未审计接口不能进入 vBPF kernel，安全边界清楚；kernel developer 必须为新 helper/kfunc 理解 side effect、标注或实现 virtualization。
- **semantic overlay 换细粒度共享**：不做 page-table switch，也不复制整个 kernel；每个被修改 object 需要 capture/update、apply、restore，并面对 object lifetime 与并发 reader。

## 实验与结果

- **平台与评测方法**：单台 x86-64 服务器，Intel Xeon Gold 6330 2.00 GHz、2 sockets×28 cores×2 hardware threads、512 GB DRAM；Ubuntu 24.04、Linux 6.12、LLVM 20，全部 eBPF program 开启 JIT，单线程 microbenchmark 绑核并使用 performance mode。Workload 包括 lmbench、UnixBench、PostgreSQL、Apache、Redis、7z；sysdig、netobserv 和简单 bio monitor 作为真实 eBPF 应用。对比 Vanilla Linux、Native eBPF、vBPF Co-located 和 vBPF Cross-Tenant（§6）。
- **microbenchmark 与分解**：Co-located 相对 Native eBPF 的额外 latency 上限分别为 syscall 4.81%、`select` 5.18%、process creation 3.39%、network 2.51%。Cross-Tenant 因跳过无关 sysdig，NULL call/read/write 为 0.258/0.319/0.288 µs，相对 Native eBPF 的 latency 分别改善 3.7×/3.8×/3.9×；RPC/UDP、RPC/TCP、TCP/IP 为 17.55/21.31/13.89 µs，改善 1.4×/1.4×/1.5×（§6.1、图 8–9）。TCX breakdown 中 native program 本身约 1,135 ns，Snifer resolve 另需 134–136 ns、namespace lookup 32–33 ns、program lookup 60–74 ns（§6.2、图 10）。
- **租户规模与 program contention**：namespace 从 10 增到 100 时，Snifer resolve 保持 131.7–136.6 ns，program lookup 保持 58.3–60.7 ns。向同一 `sys_read` 插入 160 个 kprobe programs 时，Native sequential execution 和手写 in-program filter 的 throughput 线性下降；Cross-Tenant vBPF 曲线基本平坦，最高分别快 54 倍和 11.4 倍（§6.3、图 11）。
- **真实 tracing 与 singleton use case**：PostgreSQL 与 background sysdig 分属不同 tenant 时，vBPF 相对 Native eBPF 最高提高 29% TPS、降低 23.6% latency；Apache 搭配 netobserv 时，throughput 最高为 Native eBPF 的 2.8 倍并接近 vanilla（§6.4、图 12–13）。`sched_ext` 实验把 Redis 与 7z 放在不重叠 CPU cores：Native `scx_central` 让 7z 快约 10%，却让 Redis throughput 低 18%；vBPF 只把该 scheduler 绑定到 7z，保留 10% 收益，Redis 接近 vanilla（§6.5、图 14）。
- **state 与 memory 开销**：只修改一个 field 时，overlay apply/restore 为 42–44 ns，显式 update 为 52–56 ns；capture 随 object size/complexity变化，`file` 和 `sk_buff` 分别 100.9 和 118.8 ns，预计算 layout 相对 naive 最多快 31.4 倍。固定 metadata 很小，但 Snifer registry 随 live resources 增长：PostgreSQL 总峰值 11.6 KiB，Apache 39,370.0 KiB，fio 38,963.5 KiB，其中约 39 MB 几乎都来自 Snifer（§6.6–§6.7、图 15、表 3）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 晚绑定能隔离无关 tenant 的执行成本 | Cross-Tenant lmbench latency 最高改善 3.9×，100 namespaces 时 lookup 仍稳定（图 8、11a） | 收益来自 background program 与 workload 无关的场景 | 强（所测路径） |
| Hash dispatch 比线性 program traversal 更可扩展 | 160 kprobes 时最高比 Native 快 54 倍、比手写 filter 快 11.4 倍（图 11b） | Hash 是平均 `O(1)`；同 tenant 与 ancestor programs 仍需执行 | 强（该 microbenchmark） |
| 隔离 tracing program 可恢复真实应用性能 | PostgreSQL TPS 最高增 29%、latency 降 23.6%；Apache throughput 最高 2.8 倍（图 12–13） | 单机、两个 monitor、cross-tenant placement | 强（覆盖 workload 内） |
| Virtual singleton hook 能给不同 tenant 不同策略 | 7z 保留 `scx_central` 的 10% 收益，Redis 避免 Native 的 18% 退化（图 14） | 两 workload 使用不重叠 cores，未测共享 core 调度公平性 | 中到强 |
| Compiler 与 overlay 可提供低成本 state view | 常见 object apply/restore 42–44 ns，update 52–56 ns（图 15） | 仅改一个 field；没有系统性隔离攻击或并发 correctness 结果 | 中 |

## 批判性分析

### 论证链条

论文没有把多租户问题缩成“再加一个 PID filter”，而是统一解释 singleton、功能干扰和性能干扰：它们都来自 logical tenant program 过早绑定到 global hook 与 state。Snifer 解决“事件是谁的”，Dispatcher 解决“跑哪些 program”，analyzer/library 解决“看到和修改哪份 state”，三个组件和三类冲突对应得很清楚。Lmbench、program-count scaling、真实 tracing 与 `sched_ext` 也分别验证了 hot-path cost、noisy-neighbor 和 singleton virtualization。

不过性能结论主要证明“无关 program 可以不运行”，不是任何 eBPF workload 都会加速。Co-located vBPF 仍比 Native 多几个百分点；真正相关的 monitor 必须执行，租户内 program 和 parent audit chain 的成本不会消失。系统的核心贡献是隔离与可组合性，headline speedup 是避免错误 broadcast 的结果。

### 假设压力测试

Snifer 若漏建、过期或错误复用 resource key，Dispatcher 就会送到错误 namespace；共享 socket、merged I/O、NAT/tunnel、connection migration 和 teardown race 都比简单 5-tuple 更难。论文描述了 namespace set、multi-stage match 与 task teardown，但没有报告 attribution accuracy、registry churn、丢失 mapping 时的 fail-open/fail-closed 行为。

State isolation 依赖“所有写都经过 analyzer 看得到的 helper/kfunc”。手工 `vbpf_safe` 标错、indirect side effect 漏传、kernel 新 API 未覆盖，都会绕过逻辑隔离。当前 prototype 聚焦 helper，kfunc 只是可扩展方向。Semantic overlay 又假定共享 object 有可恢复的 clean base；若多个 CPU 或 RCU reader 同时观察对象，apply/restore 的瞬时 view 是否一致更复杂，论文自己承认当前假设 exclusive access，未显式处理 RCU readers（§8）。

### 实验可信度

评测优点是给出 vanilla、native、co-located、cross-tenant 四种配置，既显示收益，也没有隐藏相关 tenant 的额外成本；真实 PostgreSQL、Apache、sysdig、netobserv 和 `sched_ext` 比只测空 program 更有说服力。状态实验分别测 capture/update/apply/restore，memory table 也揭示 Snifer 而非固定 metadata 是主要容量来源。

局限是只有一台 Intel/Linux 6.12 机器，没有与 cgroup、bpfd/orchestrator、KrakenGuard 或 process-isolation eBPF 系统做端到端比较；安全论断没有 formal proof、adversarial programs、lifecycle race 或 hook-coverage matrix。`sched_ext` 给两 workload 分配不重叠 cores，隔离任务相对容易。状态 overlay 只改一个 field，不能代表 program 连续修改多个大 object 的成本。

还有一个论文内部数字需要谨慎：§6.2 列出的 Snifer、namespace 和 program lookup 合计约 226–243 ns，而 basic TCX execution 为 1,135 ns；按这些数字约是 20%–21%，但正文称“largest vBPF overhead only 2.1%”。原 PDF 也写 2.1%，不是 MinerU 误识别。图 10 的 bar 更接近前一种量级，因此此百分比不能直接采信，需作者或源码澄清。

### 系统性缺陷

vBPF 的可信计算基不小：修改后的 Linux、verifier、JIT、Clang analyzer、人工 safety annotation、namespace lifecycle 和 container runtime 全都可信。约 13K LoC prototype 还需跟随快速变化的 helper、kfunc、hook 和 BTF layout 维护。它比 MicroVM 轻，但隔离保证也明显更弱；resource exhaustion 和 microarchitectural leakage 被直接排除。

Registry 的约 39 MB 峰值已经说明 memory 随 network/I/O resources 线性增长，恶意 tenant 又可主动制造资源，而 threat model 不处理这种攻击。Overlay memory 还会随被修改 object 增长。Flattened hierarchy 则把 parent update 扩散为多个 child path 的替换。系统把 runtime 线性遍历换成了控制面索引、lifecycle 与 state-versioning 复杂度，这些在短 benchmark 中尚未充分暴露。

## 局限与后续工作

- 给出 hook/helper/kfunc 支持矩阵，扩展 analyzer 到 kfunc，并用 kernel update CI 阻止未标注 side effect 的新接口进入 vBPF build。
- 对 network tunnel、NAT、shared socket、merged/split I/O、resource reuse 和 namespace teardown 做 attribution fault injection，明确 lookup miss 的安全默认行为。
- 为 semantic overlay 定义并验证并发语义，覆盖 RCU readers、nested interrupt、preemption、object free/reuse 和 parent-child 同时修改。
- 与 cgroup dispatch、主流 orchestrator、admission control 和 MicroVM 在相同 tenant workload 下比较性能、隔离强度与运维成本。
- 测量 namespace depth、parent update rate、每 tenant program 数、百万 live resources 和恶意 churn 下的 CPU、memory 与 tail latency，并加入 quota/eviction。
- 发布 security test suite：跨 tenant map/state 读取、return-value tampering、helper side effect、singleton attach 与 denial-of-service，而不只用性能恢复间接说明隔离。

## 相关

- **相关概念**：[[eBPF]]、late binding、kernel hook、Linux namespace、multi-tenancy
- **同会议**：[[OSDI-2026]]
