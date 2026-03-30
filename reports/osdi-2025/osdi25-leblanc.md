# osdi25-leblanc: PoWER Never Corrupts

## 论文基本信息

- **标题**: PoWER Never Corrupts: Tool-Agnostic Verification of Crash Consistency and Corruption Detection
- **作者**: Hayley LeBlanc（UT Austin）、Jacob R. Lorch、Chris Hawblitzel（Microsoft Research）、Cheng Huang、Yiheng Tao（Microsoft）、Nickolai Zeldovich（MIT CSAIL & Microsoft Research）、Vijay Chidambaram（UT Austin）
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/leblanc

---

## 研究背景与动机

存储系统即使在罕见且难以测试的条件（如掉电和介质错误）下也必须保持数据的完整性。**形式化验证**为确保存储系统的弹性提供了有前景的途径——使用机器检查的证明来保证弹性和正确性。然而，当前的验证方法存在三个关键问题：

1. **专用工具带来陡峭的学习曲线**：现有的崩溃一致性验证方法（如 Crash Hoare Logic、Perennial）需要额外的语言特性或证明基础设施，大多数验证器不支持
2. **已有支持 CRC 的验证系统假设过强**：VeriBetrKV 要求 CRC 必须与数据内嵌并原子更新，这对于许多真实系统（特别是字节可寻址内存）并不成立
3. **性能差距**：经过验证的存储系统迄今未能达到最先进的性能

---

## 要解决的核心问题

1. 如何仅使用标准验证器特性（Hoare 逻辑、ghost 变量、量词）来验证崩溃一致性？
2. 如何提供一种灵活、无限制的媒体损坏模型，支持任意数据布局下的可证明损坏检测？
3. 如何构建一个经过验证的 PM K/V 存储，在不牺牲性能的前提下实现这些保证？

---

## 主要贡献

1. **PoWER（Preconditions on Writes Enforcing Recoverability）**：一种仅依赖标准 Hoare 逻辑的工具无关崩溃一致性验证方法
2. **一组基于存储系统领域知识的证明策略库**：简化崩溃一致性证明
3. **灵活的数据损坏模型**：允许 CRC 与数据分开存储，不要求原子更新
4. **Corruption-Detecting Boolean（CDB）**：持久内存上 CRC 原子更新的新原语
5. **CAPYBARAKV 和 CAPYBARANS**：两个用不同验证框架（Verus 和 Dafny）实现并验证的新系统

---

## 研究方法与设计

### 核心洞察

PoWER 的核心洞察是：**不需要新的逻辑形式或 TLA 风格推理来推断崩溃**。相反，可以在执行持久写入的方法上添加前置条件，声明所有结果崩溃状态必须合法。这可以直接用 Hoare 逻辑和量词表述，而大多数验证器都支持这些特性。

在 PoWER 中，当开发者调用写入 API 时，需要提供一个满足前置条件的证明——即写入总是将存储系统置于崩溃一致状态。

### PoWER API

关键创新是在 write 方法上添加前置条件，要求所有新引入的可能崩溃状态都被允许。在 Verus 中的简化签名：
```rust
requires addr + bytes.len() <= old(self).len(),
forall |s| can_result_from_partial_write(s, old(self).durable_state, addr as int, bytes@)
    ==> perm@.permits(s)
ensures self@.can_result_from_write(old(self)@, addr as int, bytes@)
```

### 存储模型

基于 prophecy 的异步磁盘模型（Perennial 中使用）：状态由两个字节序列组成：
- `read_state`：反映所有已执行的写入（包括可能丢失的未决更新）
- `durable_state`：反映最终将持久化的状态

### 损坏检测模型

新模型基于 CRC 的理论属性：
- 设备有一个损坏位掩码，每存储位对应一位
- 当位为 0 时读取返回正确数据；为 1 时返回任意位（不一定是同一位每次读取）
- CRC 位掩码中 1 的数量有上限 c（代码对该上限透明）

关键属性：假设损坏位少于 c，则对缓冲区的 CRC 检查可以明确证明缓冲区是否损坏。

### Corruption-Detecting Boolean（CDB）

一种新的 8 字节原语，只有两个特定值（CRC(0) 和 CRC(1)），可用于原子方式更新 PM 数据结构和 CRC。

---

## 关键实现细节

### CAPYBARAKV（Verus 实现）

- 嵌入式 PM K/V 存储，验证了功能正确性、崩溃一致性和损坏检测
- 支持 key-item 对的标准 CRUD 操作及列表操作
- 使用物理重做日志，提交时附加单个 CRC，然后通过 CDB 更新提交
- `pmcopy` crate 生成 Verus ghost 代码，利用 Rust 编译器检查类型布局属性
- 证明/代码比：2.6（较低）

### CAPYBARANS（Dafny 实现）

- 持久公证服务，在线和离线验证
- 使用 CDB 算法原子更新计数器和新哈希

### 验证工作量

| 系统 | 验证时间（8 线程） | 证明/代码比 |
|------|------|------|
| CAPYBARAKV | 23 秒 | 2.6 |
| CAPYBARANS | 12 秒 | 2.4 |

---

## 实验结果与分析

### 性能对比（与未验证 PM K/V 存储对比）

**单线程平均延迟**：
- pmem-Redis：最高延迟（受通信开销影响）
- pmem-RocksDB：较高延迟（后台压缩、内存索引开销）
- Viper 和 CAPYBARAKV：类似且最优（使用内存哈希索引和简单持久数据结构）

**YCSB 吞吐量（1 线程）**：
- CAPYBARAKV 显著优于 pmem-Redis 和 pmem-RocksDB
- 与 Viper 性能相当

**分片性能（16 线程）**：
- CAPYBARAKV 在所有工作负载上均优于其他系统
- 即使与 Viper 相比也表现出色（使用更粗粒度的并发控制）

---

## 潜在问题与局限性

1. **PoWER 与某些自动化工具不兼容**：Yggdrasil 和 TPot 等高度自动化工具对量词支持有限，无法与 PoWER 一起使用
2. **不支持任意细粒度并发**：PoWER 无法推断与同一存储区域上的并发读写相关的任意细粒度并发
3. **CAPYBARAKV 的一些设计决策**：
   - 静态分配存储空间，不支持动态调整大小
   - 使用易失性哈希索引，内存占用较大
   - 存储开销可能高于未优化的系统
4. **验证正确性依赖**：
   - 验证系统的正确性依赖于其规范和验证器/编译器本身的正确性
   - pmcopy crate 中的 Rust 编译器静态断言虽然有用，但编译器本身未被验证

---

## 未来工作方向

1. 将 PoWER 扩展到更多验证器
2. 提供对 in-place 写入的支持
3. 探索更自动化的不变量推理方法
4. 扩展 CDB 到更多用例

---

## 个人评注

**优点**：
- 这是一篇非常扎实的系统论文。工具无关性（tool-agnostic）是核心贡献，使得更多开发者可以使用形式化验证而不被陡峭的学习曲线阻挡
- 通过实际构建两个经过验证的系统并与真实未验证系统对比，证明了方法的可实用性
- 崩溃一致性和损坏检测的统一处理是一个优雅的设计
- 证明/代码比 2.6 是相当低的，说明方法在实际工程中的可行性

**技术细节值得注意**：

1. **VeriBetrKV 的局限性被正确识别**：VeriBetrKV 要求 CRC 与数据内嵌并原子更新，这在字节可寻址内存上不可行。作者的新 CRC 模型更加灵活，适合 PM 用例。

2. **Prophecy 模型 vs 自然模型**：论文提到从自然模型切换到 prophecy 模型使崩溃一致性证明"简化很多"。这是一个重要的工程经验，观察到模型选择对验证难度的影响。

3. **CDB 的实现依赖于精心选择的 CRC 值**：使用 CRC(0) 和 CRC(1) 作为 CDB 的两个值，但理论上这些值在介质损坏时也可能被翻转。作者假设 8 字节足够大使得这种情况概率可忽略，这是一个合理的工程权衡但值得注意。

4. **性能结果需要关注具体设置**：CAPYBARAKV 的最优性能在特定配置下（如分片版本、独占 NVDIMM）取得，在共享或 NUMA 交错设置下的表现未详细评估。

5. **Azure Storage 集成声明**：论文提到 CAPYBARAKV 被集成到 Azure Storage 的原型 Rust 版本中，但具体集成深度和规模未说明。
