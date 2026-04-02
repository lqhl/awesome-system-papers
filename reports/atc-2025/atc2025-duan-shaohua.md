# Crash Consistency in Block-Level Caching Systems: An Open CAS Case Study

**作者**：Shaohua Duan (Washington State University), Youmin Chen (Shanghai Jiao Tong University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/duan-shaohua
**源文件**：[[atc2025-duan-shaohua.pdf]]

---

## 一、背景

字节可寻址非易失性内存（NVM）为文件系统带来了新的机遇：在传统后端存储设备之上增加一层持久化缓存层（persistent caching layer），既能提升 I/O 性能，又能利用 NVM 的持久性特性在系统崩溃后恢复缓存数据。Open CAS（Open Cache Acceleration Software）是 Intel 开发的代表性块级缓存系统，广泛应用于工业界和学术界，支持将 NVM、SSD 等高性能设备作为 Linux 文件系统的缓存层。

然而，随着缓存系统变得越来越复杂——多种缓存模式、异步数据移动机制、复杂的缓存替换策略——系统的可靠性也面临着更大的挑战。传统文件系统的崩溃一致性研究假设缓存层（page cache）的数据在崩溃后完全丢失，但持久化缓存层打破了这一假设，带来了新的一致性和兼容性问题。

---

## 二、要解决的问题

1. **持久化缓存层的崩溃一致性未知**：Open CAS 声称保证数据完整性，但其在各种崩溃场景下的实际行为缺乏第三方系统性验证。开发者自己也注意到某些缓存模式下存在数据持久性风险，但原因不明。

2. **隐式缓存操作难以测试**：eviction 和 cleaning 等操作由内部缓存策略（如 LRU）在重负载下隐式触发，无法通过用户 API 显式调用，传统的 fuzzing 和黑盒测试方法难以覆盖这些操作的崩溃场景。

3. **与文件系统可靠性特性的兼容性未知**：现有文件系统的 journaling、copy-on-write 等可靠性机制是基于"崩溃后缓存数据全部丢失"这一模型设计的。引入持久化缓存层后，崩溃后恢复过程中缓存数据与文件系统数据可能不一致，可靠性设计的前提被打破。

---

## 三、洞察与设计

**关键洞察**：隐式缓存操作（eviction、cleaning）在执行时会导致明显的 I/O 吞吐量下降（performance degradation），这种性能退化可以作为"隐式信息"（implicit information），用来识别隐式缓存操作的运行状态，从而精确注入崩溃点进行测试。

基于这一洞察，作者提出了 Workload-Oriented Test（WLOT）框架：

- **Trace 模式**：生成特定工作负载，监控缓存层 I/O 性能（通过 `casctl stat`），当检测到性能退化时标记崩溃点，同时 flush 所有缓存数据生成 oracle（正确答案）。
- **Test 模式**：回放工作负载 trace，在预设崩溃点注入合成崩溃，触发缓存系统和文件系统的恢复过程，最后将恢复后的数据与 oracle 对比验证正确性。

测试覆盖两大方面：
1. **缓存层崩溃一致性测试**：在缓存层单独注入崩溃，测试 6 种缓存模式 × 7 种缓存操作的所有组合
2. **与文件系统的兼容性测试**：同时在缓存层和后端文件系统注入崩溃，测试 5 种文件系统（ext-2/3/4、xfs、btrfs）在不同可靠性配置下与 Open CAS 的兼容性

---

## 四、实现细节

**测试平台**：HPE ProLiant DL380 Gen10 Plus 服务器，1×Intel Xeon Silver 4314 处理器，1×4GB Optane PMem（缓存设备），1×256GB Samsung SATA SSD PM9A3（后端存储），Red Hat Enterprise Server 7.9，Linux kernel 5.4.0-144-generic，Open CAS version 22.03.2，ext-4 作为默认后端文件系统。

**WLOT 性能退化检测**：
- 使用 FIO（version 3.34-13）16 线程作为工作负载，4KB cache line size
- 实验表明：工作负载越密集、cache line size 越小，eviction 和 cleaning 操作的吞吐量退化越显著
- 为验证 WLOT 准确性，作者额外实现了 `casctl cleaning` 和 `casctl eviction` 用户 API 作为测试驱动，显式触发后观察到相同的性能退化模式

**工作负载设计**：
- Sequential Write (SW)、Sequential Read (SR)、Repeat Write (RW)、Update-After-Read (UR)
- 缓存设备 4GB，文件大小 6GB（oversized），强制触发 eviction
- 每种缓存模式 × 每种缓存操作执行多次崩溃注入

**崩溃注入方式**：
- 缓存层崩溃：`unmount` + `casctl stop`
- 恢复：`mount` + `casctl start`（启用 fast recovery，复用缓存数据）
- 兼容性测试：同时在缓存层和后端文件系统注入崩溃（clean power fault）

---

## 五、实验结果

### 缓存层崩溃一致性测试（Table 2）

| 场景 | 结果 |
|------|------|
| 所有缓存模式，ACK 返回后崩溃 | 全部成功恢复（R） |
| Cache miss / eviction 期间崩溃 | 维持一致性但数据未持久化（C） |
| Write cache hit 期间崩溃（除 WA 模式） | **返回错误数据（B）** |
| WA 模式 read cache hit 期间崩溃 | **返回错误数据（B）** |
| WB/WO 模式 cleaning 期间崩溃 | 维持一致性但数据未持久化（C） |

关键发现：
- **Observation 3**：除 Write-Around 模式外，write cache hit 期间崩溃会导致 Open CAS 返回错误数据给用户（因为更新操作不会重置 valid bit 为 invalid）
- **Observation 4**：Write-Around 模式下写请求期间崩溃，旧的 stale 数据可能返回给用户
- 冷数据比频繁更新的热数据能容忍更严重的崩溃

### 文件系统兼容性测试（Table 3）

| 文件系统 | 结果 |
|----------|------|
| ext-2（所有配置）、ext-3（默认） | 成功但恢复慢（SR） |
| ext-3/ext-4（journaling 相关配置）、xfs、btrfs | flush dirty data 触发 I/O 错误（FE） |
| ext-3/ext-4（journal 配置）、xfs | **持久性丢失 + I/O 错误（LE）** |
| btrfs | **静默持久性丢失（LS）**——最严重 |

关键发现：
- Journaling 文件系统在不完整 journal 事务时切换为 read-only，Open CAS flush dirty data 失败
- Open CAS 以 cache line 粒度保证事务性，而 journal 文件系统要求完整的 journal 事务（通常 > 4KB），粒度不匹配导致数据被丢弃
- btrfs 的 copy-on-write 机制会丢弃不完整数据且不报错，造成**静默数据丢失**

### NVCache 验证

更简单的缓存系统 NVCache 同样在 cleaning 操作期间崩溃时返回错误数据，证明隐式缓存操作是缓存系统崩溃一致性的通用瓶颈。

---

## 六、批判性分析

1. **崩溃注入方式的代表性存疑**：作者使用 `unmount` + `casctl stop` 模拟崩溃，这是一种"干净关闭"而非真正的电源故障或内核 panic。真实崩溃可能在 NVM 上留下部分写入的数据（partial writes），而 unmount 可能会完成正在进行的 I/O 操作，导致测试结果偏乐观。

2. **只测试了单一硬件配置**：所有实验仅在一台服务器、一种 Optane PMem、一种 SSD 上完成。不同硬件的 I/O 行为（如 NVMe SSD vs SATA SSD、不同容量的 PMem）可能影响崩溃一致性行为。

3. **WLOT 依赖性能退化信号**：如果某些隐式操作的性能退化不够显著（如在高端 NVMe 设备上），WLOT 可能无法准确识别操作的运行状态。作者仅验证了一种硬件配置下的有效性。

4. **缺少修复方案的实验验证**：论文在讨论部分提出了三种改进方向（checksums、data synchronization、reliability-feature-aware recovery），但都只是概念性建议，没有原型实现或性能评估。对于一篇系统论文，仅指出问题而不提供可行的解决方案，贡献深度有限。

5. **NVCache 测试过于简略**：NVCache 的测试结果仅占半页，只测试了一种缓存模式，缺乏与 Open CAS 同等深度的分析，难以支撑"隐式缓存操作是通用瓶颈"这一结论的普遍性。

6. **未讨论实际影响的严重程度**：论文发现了"返回错误数据"的问题，但未量化错误数据的范围（多少 cache line 受影响？）和发生概率（在真实工作负载下触发的可能性有多大？），这对于系统管理员评估风险至关重要。

---

## 七、总结

本文首次系统性地分析了块级缓存系统 Open CAS 的崩溃一致性行为，提出了基于性能退化隐式信息的 WLOT 测试框架来覆盖传统方法难以测试的隐式缓存操作。研究发现 Open CAS 在 write cache hit 和部分隐式操作期间崩溃时无法维持一致性，且与 journaling 和 copy-on-write 文件系统存在严重兼容性问题（最坏情况下导致静默数据丢失）。论文的核心贡献在于揭示了持久化缓存层引入后，传统崩溃模型失效带来的一系列可靠性问题，但缺少具体的修复方案和更广泛的系统验证。
