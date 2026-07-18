---
type: paper
name: PoWER
full_title: "PoWER Never Corrupts: Tool-Agnostic Verification of Crash Consistency and Corruption Detection"
authors: [Hayley LeBlanc, Jacob R. Lorch, Chris Hawblitzel, Cheng Huang, Yiheng Tao, Nickolai Zeldovich, Vijay Chidambaram]
venue: OSDI
year: 2025
tags: [formal-verification, storage, crash-consistency, persistent-memory, key-value-store]
source_pdf: "[[osdi25-leblanc.pdf]]"
source_md: "[[osdi25-leblanc]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-17
---

# PoWER Never Corrupts: Tool-Agnostic Verification of Crash Consistency and Corruption Detection (OSDI 2025)

> **一句话总结**：PoWER 将 crash consistency 编码为 durable write 的 precondition，并在 Verus/Dafny 案例中验证 CAPYBARAKV/CAPYBARANS。CAPYBARAKV 的验证时间为 54 s（1 thread）或 23 s（8 threads）；性能比较仅适用于论文的 PM、YCSB 和 shard 配置。

## 问题与动机

验证存储系统 crash consistency 与 corruption detection 长期难落地：CHL/Perennial/TLA refinement 需专用验证器；VeriBetrKV 的 checksum 模型限制 data/checksum 同址原子写，不适配字节寻址 PM；已验证系统性能常落后于未验证对手。

PoWER 核心思想：在 `write()` 的 **precondition** 中要求证明「此次写引入的任何 crash 状态均合法」——无需 Crash Hoare Logic 专用构造，Verus/Dafny/Prusti/Creusot 等标准工具即可。

## 关键观察 / 隐含假设

- **观察 1**：多数 crash-consistency 证明只需关心写的**位置**是否触及 recoverable 状态，而非写内容或具体 crash 轨迹——tentative/committing/recovery 四类写策略库可 discharge 大部分证明。
  - **依赖假设**：开发者能形式化 recovery 函数 `rec` 与合法 crash 状态集合；存储模型（prophecy async disk）与真实 PM 行为足够接近。
  - **可能失效场景**：弱一致性语义（in-place 非原子用户可见写）；依赖具体 flush 指令序的微妙硬件保证。
- **观察 2**：基于 bitmask 的 CRC 腐败模型（Hamming distance ≤ c 则 CRC 不同）比 VeriBetrKV「有效 checksum 即未腐败」更底层，允许 data 与 checksum 分离存放。
  - **依赖假设**：可信 fast CRC 库与 c 的 opaque 上界正确；PM 8-byte 原子写约束。
  - **可能失效场景**：对抗性构造的 CRC 碰撞（Tick-Tock 类算法在 PM 上可被证伪）；短数据 c>1 的精细利用（实现未做）。
- **假设 1**：Azure 类场景——小 key/item、数十 GiB 专用 PM、静态容量预分配——使 CAPYBARAKV 设计可简化验证。
  - **证据强度**：中；有 production prototype 集成，但功能边界窄。

## 核心方法

**PoWER API**：`write` 新增 precondition `forall s. can_result_from_partial_write(s, old, addr, bytes) ==> perm.permits(s)`；permission 分 blanket（recovery-equivalent 转换）与 single-use（状态突变）。

**腐败模型**：`maybe_corrupted` + CRC 验证；**CDB**（CRC(0)/CRC(1) 两有效值）实现 PM 上原子切换双副本 data+CRC。

**CAPYBARAKV**（Verus）：main/item/list-element 表 + redo journal + volatile HashMap 索引；copy-on-write；`pmcopy` 用 Rust 编译器断言对齐 layout。**并发扩展**：reader-writer lock 与 sharding 用 atomic PoWER + durable resource invariant。

**CAPYBARANS**（Dafny）：notary Advance 用 CDB 原子更新 timestamp+hash；port 到 Dafny ~10h 级工作量。

## 设计取舍

- **取舍 1**：prophecy 模型 overapproximate 部分不可能 reordering——简化证明，可能增加 annotation 负担。
- **取舍 2**：PoWER 不支持同 region 上并发 read/write 交错——细粒度并发需其他方法。
- **边界条件**：Yggdrasil/TPot 等弱量词工具不兼容；TCB 含 pmcopy、PMDK、CRC 库。

## 实验与结果

**指标、基线与边界**：verification wall-clock、startup time、YCSB throughput；CAPYBARAKV vs Viper/pmem-Redis/pmem-RocksDB；Linux/i7-11850H 验证机或 128 GiB Optane PM、指定 YCSB/shard 配置（§6）。

- 验证时间：CAPYBARAKV 为 **54 s**（1 thread）/ **23 s**（8 threads），CAPYBARANS 为 **12 s**（§6.1）。
- 证明负担：CAPYBARAKV/CAPYBARANS 的 proof-to-code ratio 为 **2.6/2.4**；分别为 14,255/5,531 与 673/278 LOC（§6.1，Table 2）。
- 128 GiB Optane PM 满实例启动：CAPYBARAKV **53 s** vs Viper **75 s**，但 DRAM 为 **2.8 GiB vs 1.1 GiB**（§6.2，Table 3）。
- 16 threads/16 shards 的被测 YCSB 中作者报告 CAPYBARAKV 优于三种对手；RunE 被跳过，RunA/B 改为 full-value update（§6.2，Fig.3）。

## Claim–Evidence Map

| Claim | Evidence | Baseline / evaluation boundary | Locator | Confidence |
|---|---|---|---|---|
| 两个案例可在分钟内完成验证 | 54 s/23 s/12 s | Linux 6.9.3、i7-11850H、8 physical cores；不同 verifier/thread configuration | §6.1 | high |
| proof burden 由两个案例而非跨系统比较刻画 | proof-to-code 2.6/2.4 与 LOC 明细 | Table 2 的 code-count 定义；trusted components 不等于已证明组件 | §6.1，Table 2 | high |
| 启动较快伴随更高 DRAM 占用 | 53 s vs 75 s；2.8 GiB vs 1.1 GiB | 128 GiB Optane、YCSB LoadA full instance；vs Viper | §6.2，Table 3 | high |
| Azure battery-backed DRAM 可改善该系统的微基准操作延迟 | 最多 2× faster | 仅 CAPYBARAKV；Windows 20 GiB battery-backed DRAM；vs 同系统 Optane PM | §6.2 | high |
| 并发 throughput 结论受 workload 改写限制 | 16 shards/threads 下优于三种对手 | 128 GiB Optane、15M keys；RunE omitted、RunA/B full updates | §6.2，Fig.3 | high |

## Critical Analysis

### 论证链条

「写前证明所有新 crash 状态合法」↔ CHL WPC / Perennial crash invariant 有机器检查对应证明，方法论链条闭合。性能 claim 在 Optane + Azure battery-backed DRAM 上成立，但 CAPYBARAKV 静态容量、无 range query、无 partial update 限制 general KV 叙事。

### 假设压力测试

- **已证明**：PM KV/notary 在 prophecy 模型下可验证且快。
- **可能失效**：block device、复杂文件 system 语义、对抗性腐败；并发同 region 写。
- **论文未覆盖**：specification 错误、编译器/提取链信任边界外的端到端安全。

### 实验可信度

Baseline 为同类 PM KV，公平性较好；YCSB 修改（无 partial update）有利于 hash-map 架构。无与 VeriBetrKV 直接性能对比（不同设备模型）。

### 系统性缺陷

静态预分配与 volatile 全 key 索引限制 scale-out；运维复杂度（验证器版本、trusted code）高；review 后补的并发机制说明 artifact 迭代成本高。

## 局限与 Future Work

- **局限 1**：不支持 arbitrary fine-grained 同址并发写；in-place 弱一致性库支持缺失。
- **局限 2**：CAPYBARAKV 不可动态扩容；大 key 内存 footprint 高。
- **Future work 1**：在 Linux/Dafny 外更多验证器上的 PoWER 案例与 proof strategy 库扩展 measurement。
- **Future work 2**：更紧 PM 硬件模型（clflush、同 cache line 序）是否减少 overapproximation 且保持证明可负担。

## 相关

- **相关概念**：crash consistency、persistent memory、formal verification、CRC
- **同类系统**：VeriBetrKV、FSCQ、GoJournal、Perennial
- **同会议**：[[OSDI-2025]]
