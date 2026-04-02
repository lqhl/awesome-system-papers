# PoWER Never Corrupts: Tool-Agnostic Verification of Crash Consistency and Corruption Detection

**作者**：Hayley LeBlanc (UT Austin), Jacob R. Lorch (Microsoft Research), Chris Hawblitzel (Microsoft Research), Cheng Huang (Microsoft), Yiheng Tao (Microsoft), Nickolai Zeldovich (MIT CSAIL & Microsoft Research), Vijay Chidambaram (UT Austin)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/leblanc
**源文件**：[[osdi25-leblanc.pdf]]

---

## 一、背景

存储系统必须在掉电和介质错误等罕见事件下保持数据完整性。形式化验证是确保存储系统韧性的一条有前景的路径，但现有方法存在显著障碍：

1. **验证工具的学习曲线陡峭**：验证 crash consistency 需要专门的工具和逻辑框架（如 Crash Hoare Logic、TLA-style state machine refinement），这些都超出了标准 Hoare 逻辑的范畴，绑定在特定验证工具上。
2. **Corruption detection 的限制**：已有工作（VeriBetrKV）对数据布局做了强假设——要求 checksum 与数据存储在一起且原子更新，不适用于所有系统。
3. **性能差距**：已验证的存储系统至今未能达到最先进的性能水平。

持久内存（Persistent Memory, PM）的兴起带来了新挑战：PM 的细粒度原子写（8 字节对齐）使得传统为块设备设计的 crash consistency 技术不再适用，PM 系统容易产生微妙的 crash consistency bug。Azure Storage 等云服务已在生产中使用 PM。

---

## 二、要解决的问题

1. **验证 crash consistency 依赖专用框架**：Crash Hoare Logic (CHL) 只在 Rocq 上实现，性能受限于 Haskell/OCaml extraction；Perennial 的 crash invariant 需要支持 atomic invariant 的工具；VeriBetrKV 的 state machine refinement 需要大量 TLA-style 基础设施和低层次推理。这些方法都无法跨验证工具使用。
2. **Corruption detection 模型过于受限**：VeriBetrKV 要求 checksum 嵌入在数据旁、与数据原子更新，这在 PM 等字节寻址存储上不可行（PM 原子写粒度仅 8 字节，无法原子更新 CRC + 数据）。
3. **验证系统性能不佳**：已有验证存储系统无法与未验证系统竞争。

---

## 三、洞察与设计

**关键洞察**：不需要新的逻辑形式或 TLA-style 推理来处理 crash consistency——只需在存储 API 的 write 方法上添加一个前置条件（precondition），要求调用者证明该写操作引入的所有可能 crash 状态都是合法的。由于写操作之前就能完整描述其所有可能的 crash 状态，因此这完全可以在标准 Hoare 逻辑 + ghost variable + quantifier 的框架内完成。

基于此洞察，论文提出两项核心技术：

### PoWER (Preconditions on Writes Enforcing Recoverability)

PoWER 将 crash consistency 的验证责任编码在 write API 的 precondition 中：调用 `write(addr, bytes, perm)` 时，开发者必须提供一个 ghost permission token，证明该写操作产生的所有新 crash 状态（由 partial write 导致的 chunk 粒度子集持久化）都被允许。

- **Prophecy-based 异步存储模型**：状态仅由 read state（反映所有已发出写操作）和 durable state（反映将最终持久化的 chunk 子集）两个字节序列组成，大大简化推理。
- **四类写操作的证明策略**：tentative write（写入恢复时不可达的地址，无需证明内容）、committing write（单个 crash-atomic 写改变抽象状态）、recovery write（恢复时执行）、in-place write（直接修改已有数据）。
- **Blanket vs. single-use permission**：blanket permission 可反复使用（如恢复等价状态间的转换），single-use permission 用于只应发生一次的变更操作。

### Corruption Detection 模型

- 基于 CRC 的理论属性（可检测 ≤ $h$ 位翻转），不限制数据和 checksum 的存储位置，不要求原子更新。
- **Corruption-Detecting Boolean (CDB)**：一种新原语，用一个 8 字节 boolean（PM 原子写粒度内）实现 crash-atomic 的 CRC 更新。CDB 存储一个 boolean 值及其两种状态对应的 CRC，通过翻转 boolean 来原子切换到新 CRC。

---

## 四、实现细节

### CAPYBARAKV（Verus 实现的 KV Store）

- **数据结构**：main table（key + item/list 地址 + CRC + CDB）、item table（item + CRC）、list-element table（元素 + 下一地址 + CRC）、physical redo journal。
- **事务机制**：commit 时 tentatively append journal CRC，然后通过更新 CDB 进行 commit。恢复时 replay log entries。
- **Volatile 结构**：HashMap 索引（key→main table 地址）+ 每表 free list，启动时重建。
- **pmcopy crate**：trusted Rust crate，通过 `#[derive(PmCopy)]` 宏生成 Verus ghost code，确保 PM 读写的类型安全（PmSafe、PmSized、Clone、PartialEq trait）。利用 Rust 编译器的 static assertion 检查类型布局一致性。
- **并发变体**：reader-writer lock 变体（并发读）和 sharding 变体（并发写），共享 `UntrustedKvStoreImpl` 核心组件。

### CAPYBARANS（Dafny 实现的 Notary Service）

- 抽象状态：当前逻辑时间戳 + last hash。
- Advance 操作用 CDB 原子更新存储状态，Sign 操作用私钥签名 hash-timestamp 绑定。
- Trusted C# wrapper 提供 CRC、密码学和序列化的外部方法。

### 代码规模

| 组件 | Trusted | Spec+Proof | Impl |
|------|---------|------------|------|
| CAPYBARAKV 总计 | 5,244 | 14,255 | 5,531 |
| CAPYBARANS 总计 | 414 | 673 | 278 |

- Proof-to-code ratio：CAPYBARAKV 2.6，CAPYBARANS 2.4。
- 验证时间：CAPYBARAKV 单线程 54s / 8 线程 23s；CAPYBARANS 单线程 12s。

---

## 五、实验结果

### 微基准测试

与三个未验证 PM KV Store（pmem-Redis、pmem-RocksDB、Viper）对比，25M records，64B keys，1KiB values：

| 操作 | CAPYBARAKV vs 对手 |
|------|-------------------|
| Sequential put/get/update/delete | 延迟与 Viper 相当，显著优于 pmem-Redis 和 pmem-RocksDB |
| Random put/get/update/delete | 类似趋势，random get ~2× sequential get（Optane PM 特性） |
| List 操作 | 仅 pmem-Redis 支持 list，CAPYBARAKV 延迟远低于 pmem-Redis |

### YCSB 宏基准测试

- **单线程**：CAPYBARAKV 显著优于 pmem-Redis 和 pmem-RocksDB，与 Viper 相当。
- **16 线程（sharded）**：CAPYBARAKV 在所有工作负载上超越所有对手（包括 Viper），因为 Viper 的 CCEH hash map 使用 per-bucket semaphore 在高线程数下性能下降。
- **可扩展性**：读密集型工作负载（RunB/C/D）扩展良好；写密集型受 lock contention 影响。

### 启动时间与资源利用

| 系统 | 空启动 | 满启动 | 内存 (GiB) | 存储 (GiB) |
|------|--------|--------|-----------|-----------|
| pmem-Redis | 142ms | 失败 | 12.3 | 22 |
| pmem-RocksDB | 9ms | 7ms | 2.0 | 17 |
| Viper | 9s | 75s | 1.1 | 23 |
| CAPYBARAKV | 7s | 53s | 2.8 | 18 |

- CAPYBARAKV 和 Viper 启动慢（需重建内存索引），但存储利用率合理。
- Battery-backed DRAM 环境下操作延迟可再降 2×。

---

## 六、批判性分析

1. **Sharding 并发模型的局限被轻描淡写**：论文承认不支持细粒度并发写同一存储区域，但 sharding 策略（按 key hash 分片）是最粗粒度的并发方案。对于有热点 key 的真实工作负载，单 shard 会成为瓶颈。论文的 workload Y/Z 虽引入 hotspot 分布，但由于 key 均匀分配到 shard，hotspot 效应被分散了——这实际上掩盖了问题。

2. **静态分配的设计过于简化**：CAPYBARAKV 要求预先指定最大 key/item/list 数量和大小，不支持动态扩容。论文将此定位为"面向特定 Azure Storage 使用场景"，但这大幅限制了通用性。与 Viper、pmem-RocksDB 等支持动态增长的系统相比，这是一个根本性的功能差距，不仅仅是"简化设计决策"。

3. **启动时间的代价未充分讨论**：满载时 53s 的启动时间对于需要快速故障恢复的生产系统是严重问题。论文未讨论这对 tail latency 和可用性 SLA 的影响。

4. **Trusted code base 的风险**：5,244 行 trusted code（包括 PM 后端、pmcopy crate）未经验证。pmcopy 的正确性依赖于 Rust 编译器行为（已经发生过 u128 布局变更导致不一致的案例）。论文虽提到 static assertion 检测到了问题，但这仅是事后发现，不能保证捕获所有类似问题。

5. **存储模型过度近似**：论文承认 PM 模型考虑了实际不可能发生的 crash 状态（同一 cache line 内的 8 字节 chunk 重排序），这可能导致开发者需要为不存在的场景写额外证明。论文将此定位为"更安全"，但代价是验证负担增加且可能排除某些合法优化。

6. **CAPYBARANS 评估不足**：CAPYBARANS 仅作为 tool-agnostic 的证据存在，没有任何性能评估。作为 notary service，其实际效用和性能特征完全未知。

---

## 七、总结

本文提出 PoWER，一种仅依赖标准 Hoare 逻辑、ghost variable 和 quantifier 的 crash consistency 验证方法，以及一个灵活的 CRC-based corruption detection 模型和 Corruption-Detecting Boolean 原语。通过在 Verus（CAPYBARAKV）和 Dafny（CAPYBARANS）两种验证框架上实现，证明了方法的工具无关性。CAPYBARAKV 在 PM KV Store 场景下达到与未验证系统竞争的性能，proof-to-code ratio 仅 2.6，验证时间不到一分钟。主要局限在于不支持细粒度并发和动态扩容，且 trusted code base 仍有一定规模。该工作显著降低了形式化验证存储系统的门槛，是将验证技术推向实用的重要一步。
