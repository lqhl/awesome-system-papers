---
type: paper
name: jwmalloc
full_title: "jwmalloc: A Verified Memory Allocator for Mobile Devices"
authors: [Jiawei Wang, Ming Fu, Ruixian Wang, Chao Xu, Jonas Oberhauser, Haibo Chen]
venue: OSDI
year: 2026
tags: [memory-allocator, mobile-system, verification, lock-free]
source_pdf: "[[osdi26-wang-jiawei.pdf]]"
source_md: "[[osdi26-wang-jiawei]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# jwmalloc：面向移动设备的已验证内存分配器（OSDI 2026）

> **原题**：jwmalloc: A Verified Memory Allocator for Mobile Devices

jwmalloc 以统一 slab、closed sibling tree、两缓冲 lifetime tracker 和 non-blocking interface 联合优化移动设备的 CPU、能耗、内存回收与 tail latency，并对弱内存模型下的核心并发协议做 bounded verification。

## 问题与动机

jemalloc/tcmalloc 主要面向服务器吞吐和及时释放，移动设备却只有少量 oversubscribed cores、数 GB 共享 DRAM、频繁前后台峰谷和软实时交互。HarmonyOS/Android workload 中 allocator 指令分别占总指令约 12.4%/8.2%；异构 slab 重格式化、长期 metadata、锁等待与激进回收都直接影响电池和卡顿。

## 关键观察 / 隐含假设

### 关键观察

- 所有 size classes 使用统一 slab size 后，空 slab 可立即跨 class 重用，避免 backend 反复 split/coalesce。
- range 可用 `n×2^m` 形式组织；closed sibling tree 能以紧凑 metadata 高效查找、拆分和合并非 power-of-two fragments。
- 无需为每个 range 记录 timestamp：类似 generational [[Garbage-Collection|GC]] 的 active/inactive 两个 buffer 可低成本区分短寿/长寿区域并指导回收顺序。

### 隐含假设

- 手机 workload 的 lifetime locality 与峰谷行为稳定，两缓冲启发式能跨 app/service 泛化。
- bounded model checking 覆盖的缩小配置能代表任意规模执行，未建模的 OS interaction 不引入新 race。
- 统一 slab 尾部浪费可由更快跨 class reuse 抵消，最终 footprint 与 jemalloc 可比。

## 核心方法

### Uniform slabs 与 pooling

frontend 的所有 size classes 从同尺寸 slab pool 获取内存；slab 变空后无需重塑即可转给其他 class，减少 backend 操作和 cache metadata。

### 闭合兄弟树（Closed sibling tree）

backend/Nest 用新的 range tree 管理 fragments，支持任意范围 split/join，并让 metadata 随在用 ranges 伸缩、可被回收，不因历史 peak 永久驻留。

### 基于生命周期的回收

两个 buffer 交替记录新/旧 ranges，近似 young/old generation。回收优先选择长寿 range 邻近空闲块，让即将释放的短寿块有机会先合并，减少重复 unmap/remap。

### Non-blocking 与验证

前后端 API 以 packed atomic state、CAS 和 ownership protocol 避免锁等待。作者用支持弱内存模型的 bounded model checker 验证 memory safety、data-race freedom 和关键循环性质，并发现过 uninitialized-memory bug。

## 设计取舍

- uniform slab 简化重用、降低指令，但部分 size class 可能产生更多 internal fragmentation。
- lifetime heuristic 无 per-range timestamps，开销低但错误分类会延迟回收或增加 OS churn。
- non-blocking 保证系统整体进展，不保证每个线程 wait-free；重试在极端 contention 下仍可能长尾。
- bounded verification 强于 stress test，却不是完整 allocator、无限 heap/thread 的形式化证明。

## 实验与结果

- 在 Huawei Mate 70 Pro/HarmonyOS 5.1 的真实 mobile workload 中，jwmalloc 相比默认 jemalloc 将 whole-system instructions 降低约 10%，allocator-side instructions 降低 3.84 倍，同时保持可比 memory footprint（§6.2，图 15）。
- 同一设备上，jwmalloc 相比 jemalloc 将 user-space instruction counts 降低 7%–21%，CPU-cluster power 降低 5%–11%，LPDDR power 降低 2%–3%。
- rptest-8B-128B-1 microbenchmark 中，jwmalloc 相比 jemalloc、mimalloc、tcmalloc throughput 分别提高 25%、24%、10%；另一组合对 jemalloc性能提高 74%、allocator instructions 减少约 82%。
- mstress-10N 的 allocation/free P99.99 latency 为 1.5 µs，而 jemalloc 为 5.9 µs，支持 non-blocking 在 heavy oversubscription 下的尾部优势。
- jwmalloc 已部署到 1200 万台商业设备，稳定运行累计超过 300 亿 user-hours；这是可靠性强证据，但事故、rollback 与版本分布未披露。
- 相比 jemalloc，microbenchmark allocator-side instruction 某些场景降低超过 70%；同时 peak/steady memory 波动通常更小，但论文没有给出所有 workload 的单一最坏 footprint bound。

## 论断—证据表

| 论断 | 机制 | 证据 | 边界 |
|---|---|---|---|
| mobile-first allocator 可显著降低系统成本 | uniform slab 与 compact backend | whole-system instructions 降低约 10% | 单一旗舰设备主要结果 |
| non-blocking 设计控制 oversubscription tail | CAS ownership protocol | P99.99 为 1.5 µs，对 jemalloc 5.9 µs | lock-free 不等于每线程 wait-free |
| lifetime tracking 能兼顾回收与 footprint | two-buffer heuristic | 真实 workload footprint 可比、power 降低 | 无严格 memory bound |
| 并发核心获得弱内存模型验证 | bounded model checker | 找到并修复 uninitialized access | 有界缩小模型，不覆盖完整 OS |
| 系统具备生产成熟度 | 1200 万设备部署 | 超过 300 亿 user-hours | 缺少故障率与 rollback 数据 |

## 批判性分析

### 论证链条

论文从 mobile trace 量化 allocator 成本，将四种 workload 特征逐一映射到 uniform slabs、tree、lifetime 与 non-blocking 机制，再以 microbenchmark、whole-system power 和大规模 deployment 验证。机制—证据对齐很好，且 verification 补足 allocator correctness 风险。

### 假设压力测试

若 app size distribution 让统一 slab 产生大量尾部浪费，CPU 收益可能被 paging 抵消；若生命周期快速交替，两 buffer 会频繁误判。CAS 在高 contention 下也可能造成 cache-line bouncing，non-blocking 不自动等于低能耗。

### 实验可信度

真实旗舰手机、多个 allocator、power counter 和 300 亿 user-hours 极具说服力。弱点是 production 结果主要来自 HarmonyOS/Huawei 硬件，Android 仅用于动机；memory footprint 缺少完整分位/最坏值，验证范围也未明确量化 state-space coverage。

### 系统性缺陷

标题“Verified”容易被理解为全实现功能正确，实际是核心组件的 bounded model checking。allocator 与 OS page policy、MTE/sanitizer、fork 和异常终止的组合 correctness 仍依赖传统测试；商业部署数据无法外部复现。

## 局限与后续工作

- 在 Android、低端/中端 SoC 和 Rust/C++ 多类 app 上验证收益。
- 披露 peak/steady footprint 分位、OOM/background kill 与长期 fragmentation。
- 扩大形式化模型到 frontend–backend composition、MTE 与 OS unmap 交互。
- 分析 CAS contention、公平性和 adversarial allocation pattern 的最坏界。

## 相关

- [[Memory-Allocator]]
- [[jemalloc]]
- [[Lock-Free]]
- [[Weak-Memory-Model]]
