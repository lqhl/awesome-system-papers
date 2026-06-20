---
type: paper
name: PoWER
full_title: "PoWER Never Corrupts: Tool-Agnostic Verification of Crash Consistency and Corruption Detection"
authors: [Hayley LeBlanc, Jacob R. Lorch, Chris Hawblitzel, Cheng Huang, Yiheng Tao, et al.]
venue: OSDI
year: 2025
tags: [formal-verification, storage, crash-consistency, persistent-memory, key-value-store]
source_pdf: "[[osdi25-leblanc.pdf]]"
source_md: "[[osdi25-leblanc]]"
---

# PoWER Never Corrupts: Tool-Agnostic Verification of Crash Consistency and Corruption Detection (OSDI 2025)

> **一句话总结**：PoWER 把 crash consistency 编码为 durable write 的 precondition（标准 Hoare logic + 量词即可），配合灵活 CRC 腐败模型与 CDB 原语，在 Verus/Dafny 上分别验证 CAPYBARAKV/CAPYBARANS，验证 <1min，CAPYBARAKV 性能与未验证 PM KV 持平或更快。

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

- CAPYBARAKV 验证：54s（1 线程）/ 23s（8 线程）；CAPYBARANS 12s。
- vs pmem-Redis/RocksDB/Viper：microbenchmark 延迟相当或更低；16-shard YCSB 多 workload 显著领先 Viper（CCEH semaphore 扩展性问题）。
- 启动：满实例 CAPYBARAKV 53s vs Viper 75s；内存 2.8 GiB vs Viper 1.1 GiB（CAPYBARAKV 存全 key）。
- proof:code ≈ 2.6（CAPYBARAKV）、2.4（CAPYBARANS）；开发 CAPYBARAKV ~1.5 年。

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