# Boosting File Systems Elegantly: A Transparent NVM Write-ahead Log for Disk File Systems

**作者**：Guoyu Wang, Xilong Che, Haoyang Wei, Shuo Chen, Puyi He, Juncheng Hu (Jilin University)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/wang
**源文件**：[fast2025-wang.pdf](../../papers/fast-2025/fast2025-wang.pdf)

---

## 一、背景

Non-volatile Memory (NVM) 以其字节可寻址和持久化特性，成为存储层次中介于 DRAM 和块设备之间的新层级。业界已提出多种利用 NVM 的方案：NVM 专用文件系统（如 NOVA、DAX）直接在 NVM 上运行，但受限于 NVM 容量远小于块设备；跨介质文件系统（如 Strata、Ziggurat）设计复杂、部署困难；overlay 加速方案（如 SPFS、P2CACHE）试图用 NVM 加速现有磁盘文件系统，但引入了额外开销或性能退化。

当前磁盘文件系统的主要瓶颈在于同步写操作（sync writes），这些操作需要立即持久化到磁盘，延迟高且不可避免。如何在不破坏现有软件栈、不引入数据迁移成本的前提下，利用 NVM 加速磁盘文件系统的同步写，是一个尚未被很好解决的问题。

---

## 二、要解决的问题

1. **NVM 专用文件系统速度不够快**：NOVA 等系统虽然利用了 NVM 的持久性，但因 NVM 速度低于 DRAM page cache，在很多场景下反而比传统磁盘文件系统慢（尤其是读操作和非同步写）。
2. **Overlay 加速方案定位不当**：SPFS 需要预测同步写模式，在首次预测成功前性能很差；且数据被导向 NVM 后，后续读也必须从较慢的 NVM 读取，引入二次索引开销。P2CACHE 将所有写（包括异步写）都重定向到 NVM 以保证一致性，不必要地拖慢了异步写性能；且缺少页面状态管理等关键功能，不具备实际部署条件。
3. **异构设备间一致性难题**：同步写到 NVM、异步写回磁盘，两条路径的时序不确定性会导致崩溃后数据版本不一致。
4. **小写入放大**：fsync 操作只能以页粒度（4KB）持久化数据，即使只修改了几十字节也要写整页到 NVM，造成严重写放大。

---

## 三、洞察与设计

**关键洞察**：

- **I1**：DRAM page cache 在绝大多数场景下已经足够高效，因此将同步数据持久化到 NVM 时，应专注于"高效记录"（append-only log），而非"数据检索"（建立索引）。既然 DRAM cache 始终保有最新数据，NVM 上的日志只需在崩溃恢复时使用，无需支持实时读取。
- **I2**：建立 NVM 写与磁盘 write-back 之间的明确时序关系，是保证崩溃一致性的关键。缺少这种时序，要么需要把所有写都重定向到 NVM（P2CACHE 的做法），要么在恢复时面临版本混乱。

基于这两个洞察，NVLog 设计为 VFS page cache 旁侧的 write-ahead log，而非 overlay 文件系统：

- **仅吸收同步写**：异步读写仍走 DRAM page cache 快速路径，NVM 仅记录同步写的日志条目，不改变 page cache 的 dirty 标记。
- **Log 结构设计**：全局 super log 指向各 inode log，inode log 中包含 OOP（Out-of-Place，整页数据存在独立 NVM 页）和 IP（In-Place，小数据内嵌在 log entry 中）两种条目，利用 NVM 字节寻址能力避免写放大。
- **NVM-Disk 一致性协议**：在 NVM 日志中记录磁盘 write-back 事件（write-back entry），建立全局时钟。恢复时只重放未过期的日志条目到磁盘对应版本上，确保不会回滚或混淆数据。
- **Active Sync 优化**：根据历史写模式，动态将 fsync 模式的文件切换为 O_SYNC 模式，从而以字节粒度而非页粒度记录同步写，减少写放大。

---

## 四、实现细节

- **内核实现**：基于 Linux 5.15 LTS，总共 7.3K 行内核代码 + <1K 行用户空间工具。修改集中在 VFS（0.3K LOC）、内存管理子系统（6.2K LOC）和驱动（0.8K LOC）。
- **Log Entry 结构**：super log entry 含 `s_dev`、`i_ino`、`head_log_page`、`committed_log_tail` 四个字段；inode log entry 含 `flag`、`file_offset`、`data_len`、`page_index`、`last_write`、`tid` 六个字段，每条 64B，按 4KB 页组织并以链表连接。
- **持久化保证**：使用 `clwb` 显式刷回 CPU cache line 到 NVM（支持 eADR 时可省略），每个事务仅需两个 `sfence` 屏障——一个在所有 segment 写完后、committed_log_tail 更新前；一个在 commit 后、下一个事务开始前。
- **崩溃恢复**：多遍扫描 inode log，通过 `last_write` 字段反向链接同一 page offset 的条目，构建索引后按序重放。恢复时间约 10 秒。先运行 fsck 修复底层文件系统，再运行 NVLog 恢复。
- **垃圾回收**：后台内核线程定期扫描 log page，回收已过期（被 write-back 或 OOP 覆盖）的 entry 和 data page，不加锁、不影响前台操作。per-CPU NVM page pool 缓解分配压力。
- **开源**：https://github.com/BugJLU/NVLog

---

## 五、实验结果

**实验平台**：Intel Xeon 5218R (20 cores)、128GB DRAM、256GB Intel Optane PMEM (128GB×2 interleaved)、Samsung PM9A3 1.92TB NVMe SSD、Ubuntu 20.04。

### 微基准测试

| 测试项 | NVLog vs Ext-4 | NVLog vs NOVA | NVLog vs SPFS |
|--------|---------------|---------------|---------------|
| 混合读写（4KB 随机，部分同步） | 最高 4.44x | 最高 3.72x | 最高 324.11x |
| 纯同步写（不同 I/O 大小） | 最高 15.09x（Ext-4）/ 13.54x（XFS） | 小写入最高 4.13x；16KB 大写入 NOVA 更快 | — |
| Active Sync（<4KB fsync） | — | 最高 3.22x（64B） | — |
| 多线程可扩展性（1-16线程） | 最高 3.11x | 最高 1.94x | 最高 28.18x |

- GC 有效：80GB 同步写测试中，NVM 峰值使用 <22GB，最终降至接近 0。
- 容量受限（10GB NVM）：纯同步写性能降 57%，但仍比 Ext-4 快 2.25x。

### 宏基准测试

| 工作负载 | NVLog 表现 |
|----------|-----------|
| Filebench fileserver | 比 NOVA 快 3.55x |
| Filebench webserver | 比 NOVA 快 2.10x |
| Filebench varmail | 比 Ext-4 快 2.84x；比 NOVA 慢约 26% |
| RocksDB fillseq | 比 Ext-4 快 5.23x，接近 SPFS（5.83x） |
| RocksDB readseq | 与 Ext-4 相当，优于 NOVA |
| RocksDB readrandomwriterandom | 比 Ext-4 快 1.38x，比 NOVA 快 1.24x |
| SQLite YCSB (A/B/D/F) | 比 Ext-4 最高 1.91x，比 NOVA 最高 1.33x |

注：SPFS 在 RocksDB 和 SQLite 测试中多次崩溃，稳定性不足。

---

## 六、批判性分析

1. **NVM 硬件已停产，前提存疑**：论文基于 Intel Optane PMEM 实验，但 Intel 已停产 Optane。虽然文中提到 RRAM/MRAM 等替代技术，但这些技术的容量、带宽、延迟特性与 Optane 差异显著，NVLog 的性能优势能否在新介质上复现尚不清楚。

2. **实验平台对 NVLog 有利的偏差**：作者声称实验代表"加速下界"（因 NVM 带宽有限、SSD 速度较高），但这一说法缺乏验证。对于更快的 NVMe SSD（如 Gen5），同步写的磁盘 I/O 开销缩小，NVLog 的加速比可能大幅下降。

3. **Varmail 场景的劣势被轻描淡写**：NVLog 在 varmail 中比 NOVA 慢约 26%，论文将此归因于"双写 DRAM 和 NVM"，但这正是 NVLog 设计的核心代价。对于同步写密集、小文件散布的真实邮件服务器场景，这种性能差距可能更显著。

4. **崩溃恢复时间约 10 秒但缺乏深入分析**：对于生产数据库系统，10 秒恢复时间并不短。论文没有分析恢复时间与日志大小的关系，也没有测试极端情况（如 NVM 接近满载时崩溃）。

5. **SPFS 的 324x 加速比存疑**：SPFS 在随机访问场景中 97% 时间花在索引上，这更像是 SPFS 自身的 bug 或病理性退化，而非 NVLog 的真实优势。用这个数字做标题级宣传有误导性。

6. **缺少与 P2CACHE 的直接对比**：论文以"P2CACHE 开源代码不完整"为由跳过对比，但又在设计分析中大量批评 P2CACHE。没有定量对比的情况下，设计层面的优势声称缺乏说服力。

7. **Active Sync 的 sensitivity 参数调优未充分讨论**：论文称 sensitivity=2 对"大多数日常应用"足够好，但没有分析不同工作负载下的敏感度分布。对于写模式频繁变化的混合工作负载，错误的模式切换可能引入额外开销。

---

## 七、总结

NVLog 提出了一种将 NVM 作为 write-ahead log 旁置于 VFS page cache 的轻量级方案，通过仅吸收同步写、保留 DRAM 快速路径、以及 NVM-Disk 一致性协议，在不修改应用和底层文件系统的前提下加速磁盘文件系统。其核心优势在于"不退化"——在任何场景下都不比原始磁盘文件系统慢。实验在 Ext-4/XFS 上验证了最高 15x 的同步写加速和全面的宏基准优势。主要局限包括：依赖已停产的 Optane 硬件、在同步写密集的小文件场景下不如 NOVA、崩溃恢复时间较长缺乏深入分析。该方案适合以异步读写为主、同步写为瓶颈的生产工作负载（如数据库 WAL 场景）。
