---
type: paper
name: Spice
full_title: "Rethinking Process Snapshots for Near-Warm Serverless Cold Starts"
authors: [Ben Holmes, Baltasar Dinis, Lana Honcharuk, Adam Belay, Joshua Fried]
venue: OSDI
year: 2026
tags: [serverless, snapshot, cold-start, virtual-memory, operating-systems]
source_pdf: "[[osdi26-holmes.pdf]]"
source_md: "[[osdi26-holmes]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 近热启动的 [[Serverless|Serverless]] 进程快照（OSDI 2026）

> **原题**：Rethinking Process Snapshots for Near-Warm Serverless Cold Starts

> **一句话总结**：Spice 发现 disk snapshot restore 的主障碍不是缺少 working-set prediction，而是 Linux 无法同时表达“按访问序排布的磁盘页”和“按虚拟地址连续的 VMA”，且 process metadata 只能逐 syscall 重放；SHELF、spliceVMA 和 bulk metadata restore 将 cold invocation 拉到 warm 的 0.6–18ms 内，平均比 process/VM snapshot 快 7.5/9.5 倍。

## 问题与动机

serverless 的长尾函数无法常驻：Microsoft trace 中 81% application 每分钟最多调用一次。capture 完成初始化后的 snapshot 可避免语言 runtime、library 和 JIT 重做，但 CRIU 从空进程重放成百上千 syscall；VM snapshot 虽保留 kernel metadata，却带入 guest OS working set 和恢复后的 deferred housekeeping storm。

memory restore 还有结构性冲突：prefetch 要把预测 working-set page 按访问时间连续放在磁盘，`mmap` 却只能把连续 file offset 映射到连续 VA。reorder 后恢复要创建数千 tiny VMA；保留 VA-order 又造成随机 I/O 与 page-fault tail。Spice 主张这是缺失 OS abstraction，而非再调 prefetch heuristic 能解决。

## 关键观察 / 隐含假设

- **观察 1：snapshot 是 sparse, reordered overlay，不是传统 ELF 的少数 contiguous segment。** working-set clustering 可提升 I/O，却让 VMA 数最高增 32 倍（图 4、§2.2）。
  - **依赖假设**：profiled access order 对后续 invocation 稳定，未预测页虽可 fault-in但不常见。
  - **可能失效场景**：input-dependent path、高动态 JIT/heap 或 working set 快速漂移。
- **观察 2：process snapshot 的 metadata replay 与 runtime 复杂度一起增长。** bulk restore 将该部分较 CRIU 降低 63%–99%（图 2、12）。
  - **依赖假设**：可安全序列化/恢复 FD、signal、timer、thread 等对象；外部 connection/device state 可重建。
- **观察 3：VM boundary 隐藏了可共享 file-backed page。** 19%–50% working set 可由 process snapshot 借 page cache 共享，VM active memory 高 1.2–3.4 倍（表 2、图 3）。
  - **依赖假设**：host 有相同 library/file version，page cache sharing 不破坏 isolation。
- **假设 1：函数无须把 container/cgroup/namespace setup 放入 invocation critical path。**
  - **证据强度**：中；评测明确排除这些 function-agnostic 成本，生产平台能否完全预建取决于调度与安全模型。

## 核心方法

Snapshot Hybrid ELF（SHELF）保留 ELF 风格 program header，但每个 segment 带 page-granular interval tree，可把 VA range 中的 hole/page 指向 SHELF private page、原 file-backed page 或 anonymous zero page。working-set private pages 按预测访问序连续存放在 header 后，loader 可先发大 sequential read（图 6–7）。

kernel 的 spliceVMA 将一个紧凑 VMA 绑定到该 interval tree，fault 时按 VA 查实际 backing source，从而 decouple on-disk order 与 virtual layout；不必 per-page `mmap` 或 copy。新 `reexec()` syscall 批量建 VMA，并行 prefetch、预装 PTE 后尽早恢复 execution，missed page 仍可按 snapshot exact bytes fault-in（图 8–9）。

非 memory state 由 Junction LibOS 从 compact description bulk reconstruct threads、FD state、signal handler 与 timer，避免 CRIU 的 userspace morphing 和 syscall replay。Spice 仍以 process 为 snapshot boundary，可放在 VM sandbox 内执行，不把 isolation choice 与 snapshot boundary 绑定。

## 设计取舍

- **kernel/format co-design 换部署侵入性**：spliceVMA、reexec 和 SHELF 需内核与 toolchain 支持，不是 stock Linux drop-in。
- **profiled prefetch 换 path sensitivity**：常见路径接近 warm，偏离预测仍正确但会暴露 page fault/I/O tail。
- **process compactness 换外部对象复杂性**：比 VM 少恢复 OS state，但 socket、device、distributed session 需专门策略。
- **LibOS bulk restore 换兼容面**：Junction 便于原型，完整 Linux syscall/application compatibility 未由 FunctionBench 证明。
- **边界条件**：runtime initialization 重、snapshot working set 稳定且 [[NVMe|NVMe]]/page cache 带宽足时最好；storage saturation 或网络 state 多时收益下降。

## 实验与结果

- Xeon Gold 5420+、128GB、[[PCIe|PCIe]] 5.0 Crucial T705 NVMe、Java/Python/Node.js FunctionBench，cold page cache 下 Spice 较 FaaSnap*/REAP*/CRIU* latency 分别低 17%–96%、18%–95%、14%–96%，平均对应 process/VM baseline 快 7.5/9.5 倍（图 10）。
- Spice 为 warm invocation 的 1.01–6.34 倍，绝对只多 0.6–18ms；现有系统多 3.6–1,197ms。短函数收益最大，剩余主要串行成本是 VMA creation（§5.1）。
- RNN baseline 要建 3,212 VMAs并多 21ms（2.5× warm）；spliceVMA、batch VMA、PTE install 与 async prefetch 后只多 2ms（23%）（图 11）。
- bulk metadata restore 较 CRIU replay 降 63%–99%（图 12）。25 concurrent restores 下，page-cache sharing 少用 20% I/O bandwidth、throughput 高 30%（图 14）。
- Azure-trace-derived mixed workload 在 25 concurrent restore 达 ideal throughput 的 76%（图 15）；慢盘单读 latency 高 2.8 倍、bandwidth 低 25 倍时，只要未饱和，async prefetch 隐藏大部分差异（图 16）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| OS layout abstraction 是 restore 关键瓶颈 | 图 11：3,212 VMA baseline 多21ms，完整设计多2ms | 单 RNN function 与同机 ablation | 强 |
| process snapshot 可接近 warm invocation | 图 10：仅多0.6–18ms，平均快7.5/9.5倍 | FunctionBench、三 runtime、cold page cache、快速NVMe | 强 |
| bulk metadata 优于 syscall replay | 图 12：restore cost 低63%–99% | Junction 对 CRIU*，对象类型限于 benchmark | 中 |
| page sharing 改善并发 restore capacity | 图 14–15：I/O -20%、throughput +30%、25并发达76% ideal | 单机NVMe、Azure-derived mix | 中 |

## 批判性分析

### 论证链条

论文先把 process-vs-VM、disk-layout-vs-VA-layout 两组 tradeoff 分离，再以 format+kernel primitive 逐一解除，机制与 ablation 对应紧密。使用 `*` baseline 是为共同 working-set/lazy 技术做适配，仍需注意它们不是完全原生默认配置。结论是“function state restore 接近 warm”，不包含完整 sandbox placement/setup。

### 假设压力测试

若 access trace 随 input 分叉，按旧顺序 prefetch 会抢占有用 I/O；大量 dirty heap/JIT code 会扩大 private SHELF。FD 指向 remote socket、pipe peer、GPU/device 或 credential 时，bulk serialization 不一定能恢复外部世界。shared library version mismatch 会使 file-backed reuse 错误，必须用 content identity 固定。

### 实验可信度

三 runtime、多个 function、cold cache、process/VM baseline、memory/metadata ablation、concurrency 与快慢 SSD sensitivity，系统评测完整。限制是单机、最多 25 concurrent、快速 NVMe，working set 来自已知 FunctionBench；未报告 snapshot capture/storage cost、version churn、multi-tenant security 或 production tail trace。

### 系统性缺陷

新 kernel interface 增加 untrusted snapshot parser、interval-tree lookup 与 bulk state import 攻击面。SHELF compatibility/versioning、crash consistency、snapshot encryption/signing、[[Garbage-Collection|GC]]/dedup 和 rolling runtime upgrade 未展开。Junction 与 Linux 语义差异可能让部分 application 无法透明迁移。

## 局限与后续工作

- **局限 1**：排除 container/namespace/cgroup 与 placement cost，端到端 platform cold start 仍可能高于报告值。
- **局限 2**：外部 socket/device state、dynamic working set 和多进程 function 未充分覆盖。
- **后续工作 1**：在真实 serverless arrival/input trace 上测 working-set prediction miss、P99 latency 与 wasted prefetch bytes。
- **后续工作 2**：扩展 bulk metadata 到 socket/epoll/multi-process，并用 fault injection 验证 peer disconnect、timer drift 与 partial restore rollback。
- **后续工作 3**：对 SHELF parser/reexec 做 fuzz、signature/version validation，并量化 stock-kernel upstreamable API 的最小 trusted code base。

## 相关

- **相关概念**：[[Serverless-Cold-Start]]、[[Process-Snapshot]]、[[Virtual-Memory-Area]]、[[Working-Set-Prefetching]]
- **同类系统**：[[CRIU]]、[[FaaSnap]]、[[REAP]]、[[Junction]]
- **同会议**：[[OSDI-2026]]
