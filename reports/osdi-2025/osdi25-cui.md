# F2FSJ: Decentralized, Epoch-based F2FS Journaling with Fine-grained Crash Recovery

## 论文基本信息

- **标题**: Decentralized, Epoch-based F2FS Journaling with Fine-grained Crash Recovery
- **作者**: Yaotian Cui, Zhiqi Wang（香港中文大学）; Renhai Chen（天津大学）; Zili Shao（香港中文大学）
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/cui

---

## 研究背景与动机

### F2FS 概述

F2FS（Flash-Friendly File System）专为闪存设计，采用追加写入和冷热数据分离策略，被广泛用于 Android 系统。F2FS 将空间划分为：
- **原地更新区（Random Writes Area）**：存储文件系统元数据（SIT、NAT、SSA），采用原地更新
- **顺序写入区（Sequential Writes Area）**：存储文件元数据和数据，采用追加写入（out-of-place update）

### 现有 F2FS 崩溃恢复的问题

**F2FS 依赖粗粒度检查点（checkpointing）进行崩溃恢复**：
- 检查点由 dirty 内存元数据阈值或超时（默认 60 秒）触发
- 检查点触发时，所有写操作被阻塞直到完成
- 最坏情况延迟：mkdir 26ms、rmdir 233ms、create-4KB 247ms、unlink-4KB 293ms

**三大核心问题**：

**问题 1：时间开销巨大**
- 在 mkdir、rmdir、create-4KB、unlink-4KB 基准测试中，检查点时间占总执行时间的 37.2%、17.2%、47.3%、44.2%
- 即使缩短检查点间隔（60s→1s），平均执行时间反而增加 11%-21%

**问题 2：数据和元数据丢失**
- 检查点间隔期间修改的文件数据/元数据在崩溃时丢失
- 实验显示 F2FS 默认配置下数据/元数据丢失率高达 9.1%（相比之下 F2FSJ 可恢复 99.9%）

**问题 3：Roll-forward 恢复不一致**
- F2FS 的 roll-forward 恢复机制依赖 inode/dnode 标签
- 在无 barrier 和 fsync 模式下，文件数据与其 inode/dnode 标签的持久化顺序无保证，可能导致恢复状态不一致

### 现有日志方案不适用于 F2FS

日志技术在内核文件系统（如 EXT4 的 JBD2）中已有充分研究，但直接应用于 F2FS（out-of-place-update 文件系统）不能产生类似效果：

**EXT4 的 in-place-update**：on-disk inode 位置固定，in-memory inode 可先写入日志再正确应用到 on-disk inode。

**F2FS 的 out-of-place-update**：inode 位置不固定（每次更新到新 LBA），仅日志 in-memory inode 无法正确恢复（因为 on-disk 文件系统元数据可能是过时的）。

**若同时日志 in-memory 文件系统元数据和 inode**：开销过大（元数据和 inode 需写两次）。

---

## 要解决的核心问题

如何为 F2FS 设计一种新的日志机制，利用其 out-of-place-update 特性实现细粒度崩溃恢复，同时避免现有方案的开销、锁竞争和等待时间问题？

---

## 主要贡献

1. **首个针对 F2FS ordered journal 模式的日志技术**：利用 out-of-place-update 特性而非绕过它
2. **去中心化日志设计**：将日志嵌入 inode，大幅减少锁竞争和 inode 间干扰
3. **Epoch-based 数据/控制平面解耦机制**：消除日志周期切换时的等待时间
4. **Fast-forward-to-latest 策略**：将多个小更新合并为一个更新，减少 journal apply 期间的小写入
5. **完全可用的 Linux 原型**：基于 F2FS Linux（Kernel 5.15），仅 3,000 行 C 代码改动

---

## 研究方法与设计

### 核心设计原则

1. **仅日志变更（Change-only Journaling）**：不日志整个元数据页，仅日志元数据变更
2. **Ordered Journal Mode**：数据先刷盘，之后才提交元数据日志（每个数据刷盘及其对应元数据变更构成一个 journal period）
3. **利用 out-of-place-update 特性**：旧信息不被修改仅保留，因此 roll-forward 恢复天然具有一致性保证

### 设计一：去中心化 Per-inode 日志

**问题**：EXT4 的 JBD2 使用集中式 journal transaction 和全局日志列表，导致：
- 大量锁竞争（每次文件操作需获取全局 journal ticket）
- inode 间干扰（等待同一 journal period 的操作互相阻塞）

**解决方案**：每个 inode 有自己的 per-inode log list，日志内容包括：
- inode 本身的元数据变更
- 相关 SIT、NAT、SSA 条目变更

**优势**：锁竞争大幅减少，不同 inode 的日志操作完全独立。

### 设计二：Epoch-based 数据/控制平面解耦

**Ordered Journal 的 journal period 切换问题**：
- 每个数据刷盘（及其对应元数据变更）= 一个 journal period
- 新 journal period 只能在当前 period 所有文件操作完成后才能开始
- JBD2 中新 running transaction 必须等待当前 transaction 所有相关操作完成

**解决方案**：将数据平面（per-inode log list 中的元数据变更）和控制平面（在 epoch 中注册 inode 信息）解耦：
1. **数据平面**：每个 journal period 内，先将 inode 的元数据变更存入 per-inode log list
2. **控制平面**：epoch 仅注册哪些 inode 在本 period 有变更

**效果**：当日志刷新触发当前 epoch 提交时，可立即生成新 journal period 和新 epoch 来容纳新元数据变更，几乎无等待时间。

### 设计三：Fast-forward-to-latest

**问题**：Journal apply 阶段，跨 epoch 的多个小更新操作同一元数据会产生大量小写入。

**解决方案**：采用新的页面标志机制，当 apply 某 log record 时：
1. 若对应 in-memory 元数据存在：直接刷新该 in-memory 元数据并标记为"clean"（避免不必要的 flush 和支持可能的 eviction）
2. 遵循 epoch 顺序应用（确保一致性）
3. 多个操作同一元数据的小更新合并为一个最终状态写入

---

## 关键实现细节

- **基于**：F2FS with Linux Kernel 5.15
- **代码改动**：约 3,000 行 C 代码
- **与 F2FS 原生特性的兼容性**：支持原地更新区的文件元数据管理、无缝集成 F2FS 的冷热分离策略
- **兼容性保证**：per-inode log list 仅在需要时创建，不影响现有代码路径

---

## 实验结果与分析

### 实验配置

- **Intel 桌面系统**：Intel Core i7-9700, 32GB RAM, 512GB SSD
- **ARM 嵌入式开发板**：ARM Cortex-A72, 4GB RAM
- **基准测试**：filebench（mkdir、rmdir、create-4KB、unlink-4KB）
- **对比基线**：原生 F2FS（不同检查点间隔）

### 检查点时间

- **F2FSJ 将检查点时间缩短最多 4.9 倍**
- 4 个基准测试中检查点时间占总执行时间的比例均显著降低

### 整体执行延迟

- **平均执行时间减少最多 35%**（相比原生 F2FS）
- 即使将 F2FS 检查点间隔缩短到 1 秒，F2FSJ 仍比它快

### 恢复比例

- **F2FSJ 可恢复 99.9% 的文件/元数据**（create-4KB: 99.9%, mkdir: 99.9%）
- F2FS 默认 60 秒检查点：mkdir 90.9%, create-4KB 90.9%（丢失约 9.1%）
- F2FS 1 秒检查点：可恢复约 98.9%，但平均执行时间反而增加 12-21%

### 平台间效果

- ARM 嵌入式平台上 F2FSJ 同样显著优于原生 F2FS
- 证明了方案的通用性

---

## 潜在问题与局限性

1. **未与 JBD2 之外的其他日志文件系统直接对比**：如 Btrfs 的日志机制、XFS 的 journaling，未作为对比基准
2. **长顺序写入工作负载**：F2FSJ 优化主要针对元数据密集型操作，对纯顺序数据写入的效果未充分评估
3. **per-inode log list 的内存开销**：每个 inode 维护独立的日志列表，在大文件系统中可能带来显著的内存开销
4. **Epoch 切换的开销**：虽然解耦了数据/控制平面，但 epoch 切换仍需要额外的协调机制
5. **生产环境验证**：论文没有展示在真实 Android 设备或大规模生产环境中的长期运行数据

---

## 未来工作方向

- 与 F2FS 压缩、去重等特性的结合
- 进一步减少 per-inode log list 的内存开销
- 支持 writeback journal 模式
- 在真实 Android 设备上的长期评估

---

## 个人评注

### 优势

1. **问题定义精准**：明确指出 F2FS 依赖粗粒度检查点这一核心问题，并量化了其对性能和可靠性的影响（检查点占总时间 47%、丢失率 9.1%）
2. **去中心化设计的洞察**：per-inode log list 避免了 JBD2 的集中式锁竞争，这是一个简单但深刻的观察——既然 F2FS 已经将 inode 分布管理，日志也应该如此
3. **Epoch 解耦的优雅性**：数据/控制平面解耦让 journal period 切换几乎无等待，这是对 ordered journal 模式本质的深刻理解
4. **最小化改动的工程原则**：3,000 行代码改动即可在生产级文件系统中实现，这是对现有系统最友善的研究方案

### 潜在问题

1. **"4.9 倍检查点时间缩短"的适用范围**：这一数字可能主要来自元数据密集型基准测试，对数据密集型工作负载（F2FS 的主要设计目标）的效果有待验证
2. **per-inode log list 的元数据一致性边界**：当同一个 inode 的元数据在多个 journal period 中被频繁更新时，日志回放的正确性需要仔细验证
3. **与 F2FS 其他特性的交互**：F2FS 有垃圾回收、TRIM、压缩等功能，F2FSJ 对这些特性的影响未评估
4. **恢复时间的对比缺失**：论文强调了恢复比例，但没有对比 F2FSJ 和原生 F2FS 在实际崩溃恢复场景中的总恢复时间
