---
type: paper
name: EMT
full_title: "EMT: An OS Framework for New Memory Translation Architectures"
authors: [Siyuan Chai, Jiyuan Zhang, Jongyul Kim, Alan Wang, Fan Chung, et al.]
venue: OSDI
year: 2025
tags: [operating-systems, memory-management, page-tables, linux, mmu]
source_pdf: "[[osdi25-chai-siyuan.pdf]]"
source_md: "[[osdi25-chai-siyuan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# EMT：新内存翻译架构的操作系统框架（OSDI 2025）

> **原题**：EMT: An OS Framework for New Memory Translation Architectures

> **一句话总结**：EMT 在 Linux 5.15 上抽象 translation object/database/service 三层 API，使 ECPT/FPT 等新 MMU 只需写 MMU driver，框架开销平均 <0.5%，LTP 1208 项测试全通过，并暴露 OS 在哈希/扁平页表上的真实性能差异。

## 问题与动机

TB 级内存、CXL expander、ML/graph 等 weak-locality 负载使 TLB miss 与 page walk 成为瓶颈；ECPT（并行 cuckoo 查表）、FPT（合并中间级）等新硬件方案难以在 Linux 上实验——内核架构无关代码**硬编码** radix tree（指针递增、PMD 语义 overload、加 L5 需改 23 文件）。现有评估用固定 OS 开销模型或 trace replay，**低估 OS-architecture 交互**。

EMT 类比 VFS：抽象 translation 操作，MMU 差异下沉到 driver，保留 Linux 直接操纵 PTE 的优化能力（批量锁、原地更新、偏移取 entry）。

## 关键观察 / 隐含假设

- **观察 1**：Linux 27.8% 的 mm 性能 patch 依赖直接操作页表 entry；纯 pmap 式「map」接口表达不了这些优化。
  - **依赖假设**：新框架必须暴露 tobj/tdb 级 API 与可定制 fast path。
  - **可能失效场景**：极简 MMU 若无需 batch/lock 优化，EMT 抽象可能显冗余。
- **观察 2**：OS 对 ECPT 的管理成本（kECPT 自引用悖论、sparse scan、locking）在硬件论文里常被忽略。
  - **依赖假设**：硬件-软件 codesign 需要可运行 OS + 仿真 MMU（QEMU）。
  - **证据强度**：强——论文用 EMT 反思 ECPT 设计并给出 kECPT 原子切换等方案。
- **假设 1**：抽象层开销可压到接近零，才能作为新架构的公平 baseline。
  - **证据强度**：强——LEBench 平均 99.9%，macro <0.1%，Redis/Memcached/PostgreSQL 差异 <0.2%。

## 核心方法

**EMT API**：translation object（属性读写）、translation database（find/update/remove）、translation service（switch_tdb 等）。基础函数由 MMU driver 实现；可定制函数有默认实现并可 override。

**EMT-Linux**：模块化 Linux mm，保留 THP、swap、DAX 等特性。

**工具链**：QEMU 仿真 MMU + 可选 cycle-accurate 模拟；在 ECPT/FPT 上跑 macro benchmark 与 Redis/Memcached/PostgreSQL。

**ECPT 经验**：kECPT 自引用 paradox（搬 entry 时缺 translation）、需硬件原子切换多组 kECPT 寄存器；稀疏地址空间扫描比 radix 贵。

## 设计取舍

- **取舍 1**：先聚焦 kernel 内 MMU translation，不暴露给用户态（降低范围换可落地）。
- **取舍 2**：ECPT driver 用粗粒度锁换正确性，牺牲部分可扩展性。
- **边界条件**：非 tree 结构的 page migration、huge page 管理需重新设计 OS 算法。

## 实验与结果

- LTP：1208/1208 通过（Radix/ECPT/FPT driver）。
- vs vanilla Linux：micro 平均 99.9%，macro <0.1%，三类 DB 吞吐/延迟/P99 差异 ≤0.2%。
- ECPT vs x86 radix（仿真）：揭示 OS 侧 locking、scan、metadata 开销；GraphBIG/GUPS 等 macro 有架构相关差异（详见 source_md 图）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| EMT supports broad LTP functional coverage | Radix/ECPT/FPT each pass all 1208 applicable LTP test、376 syscall（§8.2） | Ubuntu 20.04 generic 5.15 config，不是 formal proof/production deployment | high |
| EMT interface overhead is near vanilla Linux | LEBench 99.9% normalized、macro <0.1%、DB p99 within 0.2%（§8.3，Fig. 14–15） | Xeon Gold 6346/256 GB、HT disabled；largest epoll-big 4.2% slow | high |
| ECPT has emulated OS page-fault overhead | instruction 1.74× 4KB、2.59× THP（§8.4，Fig. 16） | QEMU-emulated ECPT vs x86-64，非 silicon | high |
| Driver customization can lower GraphBIG work | THP iterator saves 49.0% total kernel work、52.5% page-fault work（§8.4，Fig. 17） | ECPT emulation、该 workload，非 general result | high |
| Hardware+OS simulation has mixed app effects | PT walk +23.1%、IPC +7.0%、cycles −2.3%；GUPS/Memcached −11.5/−12.9%（§8.5.1，Fig. 18） | DynamoRIO simulation，非 hardware measurement | high |

## 批判性分析

### 论证链条

硬件创新缺 OS → Linux 硬编码阻碍 → EMT 抽象+可定制 → 低开销 baseline → ECPT/FPT 案例验证。链条在「Linux 5.15 + 仿真 MMU」闭合；真实硅未测。

### 假设压力测试

- 生产内核版本漂移使 port 成本持续。
- FPT/ECPT 若大规模部署，EMT 粗锁与 sparse scan 可能成为真瓶颈。
- 仅 CXL/大内存场景外推需警惕 workload 覆盖。

### 实验可信度

LTP + 多 benchmark + 真实 DB 负载；开销对比严谨。ECPT 性能数字依赖仿真，与硅片可能有 gap。

### 系统性缺陷

论文未讨论：upstream Linux 合并路径、driver 认证与安全、与 IOMMU/nested virt 交互。

## 局限与后续工作

- **局限 1**：ECPT kECPT 需额外硬件原子切换支持。
- **局限 2**：哈希页表上 Linux sparse range 优化尚未完全解决。
- **Future work 1**：细粒度 ECPT locking；special state entry 加速 sparse scan。
- **Future work 2**：更多 MMU（range table、hybrid）driver 与上游合并策略。

## 相关

- **相关概念**：Virtual Memory、TLB、Huge Pages
- **同类系统**：Mach/BSD pmap、FBMM、Linux mm
- **同会议**：[[OSDI-2025]]
