---
type: paper
name: Osprey
full_title: "Osprey: Transparent and Efficient Virtual Memory for Secure Computation"
authors: [Yicheng Liu, Alice Yeh, Harry Xu, Raluca Ada Popa, Sam Kumar]
venue: OSDI
year: 2026
tags: [secure-computation, virtual-memory, speculative-execution, paging, obliviousness]
source_pdf: "[[osdi26-liu-yicheng.pdf]]"
source_md: "[[osdi26-liu-yicheng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向安全计算的透明高效虚拟内存

> **原题**：Osprey: Transparent and Efficient Virtual Memory for Secure Computation

## 一句话总结

Osprey 利用安全计算的内容无关性（content-obliviousness），以低成本推测执行预知未来访问并驱动异步 SSD paging；应用无需修改、每个密码库少于 200 行适配，性能相比 Linux swapping 最多提高 12 倍，多线程时最多 16 倍。

## 问题与动机

安全计算（Secure Computation, SC）让系统直接处理加密数据，但 ciphertext expansion 会急剧扩大内存：garbled circuit 中每个明文 bit 可占 16 B，即 128 倍。内存耗尽后，通用 OS replacement 不理解 oblivious workload 的未来阶段，随机 page fault 与同步 swap 使中型 analytics 也不可行。

MAGE 等 memory programming 方法预先计算完整 access plan，但要求把应用重写到特定 DSL/runtime，无法按运行时 pressure 调整，计划本身甚至可达 GiB。传统 speculative memory management 则复制执行、丢页并可能 misspeculate，需要复杂 process rollback 和 kernel support。Osprey 希望保留运行时 virtual-memory 灵活性，同时让 speculation 既轻量又永不走错访问路径。

## 关键观察 / 隐含假设

### 关键观察

- SC 不仅 input-oblivious：输入内容不改变访问轨迹；ciphertext 还具有 content-obliviousness（CO），把其内容覆盖为任意 byte 也不改变后续访问轨迹。
- ciphertext 占主导内存且 cryptographic operation 占主导 CPU；推测 pass 可把所有 CO virtual page alias 到一个 physical page，并跳过实际密码计算，只记录 would-be access。
- CO 数据可任意丢弃而不产生访问轨迹 misspeculation，因此无需 checkpoint/refork 式 rollback。
- 实时 future trace 能为 concrete/programmed pass 提供 prefetch/reclaim hint，比 Linux recency 更适合明显 phase behavior。

### 隐含假设

- SC library 的访问模式确实同时满足 input-oblivious 与被标注对象的 content-oblivious；secret-dependent access 会破坏安全与正确性前提。
- library maintainer 能正确区分 CO allocation、pointer-rich metadata 与 side effect，并标注密码操作的 touched range。
- speculative pass 能领先 programmed pass；CPU oversubscription 或复杂 trace 不会让预测过晚。
- SSD 与异步 I/O 提供足够带宽，瓶颈主要是 latency 与错误 eviction，而不是饱和 bandwidth。

## 核心方法

### 双 pass 执行

speculative pass 与真实 programmed pass 并行。前者执行 control flow，但 CO page 从一开始都映射到同一 physical page；`OSPREY_TOUCH` 放在 cryptographic operation 入口，speculation 时触碰声明的 range 后直接返回，programmed pass 中为空操作。page fault trace 经压缩后指导真实执行何时 prefetch、何时 reclaim。

Osprey 隔离或禁止 speculative side effect，仅把内存访问预测交给真实 pass。annotation 不完整不影响 correctness，只会使 speculation 多做计算、占用更多资源。

### CO 内存分配器

普通 `malloc` 会把 allocator pointer metadata 与 ciphertext 放同页，使整页不能安全 alias。Osprey 划出专用 CO virtual region，并把 allocator metadata 放在外部非 CO region；设计控制 metadata footprint，避免 irregular allocation 又复制大量 non-CO state。对 library API 的一次性修改少于 200 LoC，应用代码不变。

### 访问采集与 paging

为了记录重复访问，Osprey 限制同时 mapped 的 speculative page 数，轮换 unmap 让后续访问再次 fault；窗口小则 trace 精确但采集慢，窗口大则反之。系统以 [[eBPF|eBPF]] hook page-fault pre-handler，把 address/metadata 写入 ring buffer，由 user-space thread 异步处理，避免大幅 kernel source 修改。

programmed pass 用 trace 形成 microset，异步 prefetch 后续页，并在 memory high watermark 到达时 swap-out 到 low watermark。策略需要回答何时回收与回收哪些不再近期访问页，调用扩展后的 `madvise` 精确 reclaim 指定 page，并扩展 `userfaultfd` 支持 private anonymous segment。

### 多线程一致轨迹

thread schedule 会让 speculation 与真实执行 fault 顺序不同。Osprey 利用 Memory Protection Keys 为各 thread 独立触发访问保护，使每条线程看到与其逻辑轨迹一致的 page fault，再分别同步 speculative/programmed progress。

## 实验与结果

**证据定位**：§9.4–§9.8、图 6–9；覆盖 8 个 workload、end-to-end application、多线程与 annotation ablation。

Osprey 以 C++ 实现，适配 Microsoft SEAL 的 CKKS homomorphic encryption 与 EMP-Toolkit garbled circuit，评估 8 个 workload，包括 matrix/vector kernel、password reuse detection 与 comorbidity analysis；受限配置通常为 32 GiB，而端到端应用 unbounded footprint 分别约 163 GiB 与 91.9 GiB。

- 所有 workload 均优于 OS virtual memory，SEAL Sum/Stat 最多快 12 倍；多线程下 OS I/O latency 更突出，差距最多 16 倍。
- 7/8 workload 与 MAGE 相当或更快，6 个 workload 的 runtime 距 unbounded-memory 配置不超过 60%。
- EMP workload 与经同样 library 优化的 MAGE 差距少于 10%，可视为在线有限 lookahead/eviction 相比离线 Belady planning 的成本上界。
- MAGE 的 CKKS backend 每次 operation 做 serialization/deserialization；tiled matrix multiply 中约占 40%，Osprey 直接使用 SEAL 因而多数更快。
- 未 tiled matrix multiply 会生成难压缩 trace，Osprey 表现变差；但仍在 tiled case 的 2 倍 runtime 内并优于 MAGE。
- 完整 annotation 最多降低 45% CPU usage；EMP 可在约 30% unbounded memory 下达到超过 90% unbounded performance，且每 application thread CPU 不超过 1 core。

## 论断—证据表

| 论断 | 证据 | 边界 | 置信度 |
|---|---|---|---|
| CO 可让 speculation 无 misspeculation | ciphertext alias、skip-compute 后访问轨迹保持；两类 SC library 正常执行 | 依赖 library/协议的 obliviousness，不适用于普通程序 | 强 |
| Osprey 显著优于 OS swapping | 8 workload 全部更快，单线程最多 12 倍、多线程最多 16 倍 | workload future access 高度可预测，SSD/内存配置特定 | 强 |
| 透明性优于 planner DSL | 应用 0 行修改，每 library 少于 200 LoC | library 维护者仍承担 annotation 与 allocator 集成 | 强 |
| 在线方法可接近离线 MAGE | 7/8 workload 相当或更优；EMP 差距少于 10% | MAGE backend 与直接 library 的实现差异影响公平性 | 强 |
| annotation 可渐进提供资源收益 | recommended integration CPU 最多下降 45% | 不完整标注虽正确但可能让 speculation 无法领先 | 强 |
## 批判性分析

### 论证链条

最强贡献是把密码学 obliviousness 转化为 OS mechanism simplification：CO 不只是安全属性，也是可安全破坏 speculative data value 的许可，从根源消除 rollback。Osprey 没有强迫整个生态迁移 DSL，仅在 library object/operation 层加 annotation，实际部署路径比全程序 memory planning 更可信。单线程、多线程、kernel interface 与端到端 SC application 的评估也较完整。

### 假设压力测试

- 正确性依赖开发者标注和 SC protocol 的 CO 性质，但系统没有静态或动态证明 annotation soundness；误把 control/pointer data 标成 CO 可能崩溃或错算。
- 两个 library、8 个 workload 仍不足以覆盖 MPC/HE/ORAM 生态，特别是 secret-dependent optimization 或 GPU backend。
- `madvise` 与 `userfaultfd` 需要 Linux 扩展，eBPF fault hook 也增加部署、权限和内核版本负担。
- speculative pass 为每 application thread 增加 speculative/programming background thread，CPU 紧张时可能拖慢真实计算。
- trace compression 对 naive matrix multiply 较差，说明性能对代码 locality/tiling 仍敏感，并非完全 application-agnostic。
- 与 MAGE 比较掺杂 backend serialization 与 library optimization 差异，不能把全部优势归因于 memory manager。

### 实验可信度

两种密码协议、8 个 kernel/end-to-end workload 和多线程扩展构成较完整证据；但与 MAGE 的 backend 差异、仅两套 library 以及 kernel prototype 限制了外推。

## 局限与后续工作

- **局限**：系统依赖 library 对 content-oblivious data 的正确标注和 Linux kernel extension。
- **后续工作**：应自动验证 CO annotation、扩展 GPU/remote memory，并做 side-channel 与错误标注测试。

后续可用 type system 或 library API 自动验证 CO allocation；支持 GPU/accelerator memory、remote/far memory 与不同 swap backend；根据 speculation lead 自适应合并线程和 trace window；建立 side-channel 分析确认 tracing/paging 不泄露 secret；并把精确 page reclaim upstream 为通用 Linux API。

## 相关概念

- [[Secure-Computation]]
- [[Virtual-Memory]]
- [[Speculative-Execution]]
- [[Obliviousness]]
- [[Memory-Protection-Keys]]
