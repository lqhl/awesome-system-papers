# D2FS: Device-Driven Filesystem Garbage Collection

**作者**：Juwon Kim, Seungjae Lee (KAIST); Joontaek Oh (University of Wisconsin–Madison); Dongkun Shin (Sungkyunkwan University); Youjip Won (KAIST)
**会议**：FAST 2025 (23rd USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast25/presentation/kim-juwon
**源文件**：[[fast2025-kim-juwon.pdf]]

---

## 一、背景

Log-structured filesystem（日志结构文件系统）是一种 append-only 的文件系统设计，最初为 HDD 开发以减少随机寻址开销。在 Flash、SMR 等存储介质上，顺序写入远快于随机写入，log-structured 方式天然适配。F2FS 是当前最主流的面向 Flash 的 log-structured filesystem。

然而，log-structured filesystem 面临一个根本性问题：**垃圾回收（Garbage Collection, GC）开销**。当文件系统用完空闲 section 时，需要合并有效 block、回收无效空间。GC 过程需要获取排他锁、暂停所有写操作、执行 checkpoint，导致严重的性能下降和尾延迟飙升。

与此同时，Flash 存储设备（SSD）内部的 FTL 也有自己的 device-level GC 来回收无效 flash page。当 log-structured filesystem 运行在 SSD 之上时，文件系统级 GC 和设备级 GC **各自独立运行**，造成双重 write amplification，严重降低系统性能。

---

## 二、要解决的问题

1. **文件系统级 GC 代价高昂**：F2FS 的 GC 需要获取排他锁暂停所有写操作、分配 page cache、遍历 filemap block、执行 checkpoint，实验表明其开销是 device-level GC 的 3×–10×。这是 log-structured filesystem 无法广泛应用于生产环境的主要障碍。

2. **双重 GC 问题**：文件系统和 SSD 各自运行 GC，互不协调，增加 write amplification。

3. **现有方案的局限性**：
   - **Host 管理 L2P 映射**（如 ZNS SSD）：消除了 device-level GC，但文件系统级 GC 开销依然存在，且需要设备暴露内部几何结构。
   - **IPLFS**：使用 8 ZByte 超大文件系统分区消除文件系统 GC，但导致 FTL 需处理天文数字大小的 LBA 空间，L2P 映射内存开销极大（256 GB SSD 需 392 MB FTL 内存）。
   - **空闲时段 GC / 可抢占 GC**：预测空闲时段容易出错，完全可抢占的 GC 实际不可行。

---

## 三、洞察与设计

**关键洞察**：Flash 存储设备本身已有成熟的 GC 机制来回收无效 flash page，且 device-level GC 的开销远小于 filesystem-level GC（仅 20% 性能下降 vs. 80% 性能下降）。如果能让设备的 GC 同时回收文件系统级的空闲 section——即在 FTL 迁移 valid flash page 时**同步更新 LBA 映射**，就可以彻底消除文件系统级 GC，将 GC 职责完全下放到存储设备。

基于此洞察，D2FS 提出三个核心技术组件：

### 1. Coupled Garbage Collection (CGC)
设备级 GC 在迁移 valid flash page 时，不仅更新 L2P 映射（物理地址），还**同时更新 LBA**（逻辑地址），使得迁移后的 page 不仅物理上集中在同一 flash block，**逻辑上也集中在同一个文件系统 section**。核心操作是 **remap**：将 victim flash page 的 LBA 从旧值更新为新值。CGC 采用 **Block Associative Mapping**，允许 flash page 在目标 block 内任意偏移放置。

### 2. Migration Upcall
设备通过 NVMe queue pair 将 migration record `<old LBA, new LBA>` 异步发送给 host。采用 **Upcall Piggybacking**：将 upcall 通知搭载在正常 IO completion signal 上，不需要额外中断或轮询。Host 端的 upcall handler 更新 filemap、block bitmap 和 reverse mapping。

### 3. Virtual Overprovisioning
将文件系统分区大小设为物理存储容量的 ρ_v 倍（实验中 ρ_v = 2.4），使得存储设备先于文件系统耗尽空闲 block，从而保证 CGC 总能在文件系统需要空闲 section 之前及时回收。文件系统分区分为 regular region（文件系统使用）和 GC region（仅供 CGC 分配 LBA）。

---

## 四、实现细节

- **基于 F2FS 实现**，总代码量约 5.4K LoC（Linux 内核 + 存储固件）
- **Block Associative Mapping**：使用 block 粒度 L2P 映射，但允许 page 在 block 内偏移变化（类比 CPU set-associative cache）
- **Remap 操作**：CGC 迁移 victim page 后，在 GC region 分配新 LBA，更新 mapping table entry
- **Read-redirect / Discard-redirect**：当 host 访问已被 remap 的旧 LBA（mapping entry 为 NULL）时，FTL 查找 outstanding migration record 并重定向到新 LBA
- **Immediate Discard**：D2FS 在 invalidate 文件系统 block 后立即发送 discard 命令（而非 F2FS 的批量延迟策略），防止 free section fault
- **Stream Interface**：写命令通过 NVMe stream 接口标记 data block / filemap block 类型，CGC 按类型聚簇
- **Crash Recovery**：基于 redo 语义，checkpoint pack 记录最近处理的 (record id, upcall id)，恢复时重放未完成的 migration record
- **单个 migration upcall 可携带最多 256 条 migration record**
- **Migration record buffer 约 2 MB 足够**

---

## 五、实验结果

**实验平台**：Intel Xeon 2.10 GHz 40 核, 512 GB DRAM, SSD 模拟器 NVMeVirt（模拟 Samsung 970 Pro, 256 GB, 8 channel, 16 chips）

**对比系统**：F2FS、Zoned F2FS（ZNS SSD）、IPLFS

| 指标 | D2FS vs F2FS | D2FS vs Zoned F2FS | D2FS vs IPLFS |
|------|-------------|-------------------|---------------|
| FIO 吞吐 | **3×** | **1.7×** | **1.15×** |
| TPC-C 吞吐 | 显著优于 | **1.4×** | 优于 |
| YCSB-F 平均延迟 | 降至 **1/5** | 降至 **1/2** | 降至 **1/2** |
| YCSB-F 99.95th 尾延迟 | 降至 **1/11** | 显著降低 | 降至 **1/8** |
| FIO 99.99th 尾延迟 | 显著降低 | 降至 **1/3** | 优于 |
| FTL 内存开销 (256GB SSD) | 27.2 MB vs 256 MB | 27.2 MB vs 10.4 MB | 27.2 MB vs 392 MB |
| 单 section GC 延迟 | — | **3×–10× 更快** | — |
| WAF | ~1.4 | 相近 (~1.4) | 相近 |

**Virtual Overprovisioning**：ρ_regular ≥ 1.4 时 CGC 总能及时供给空闲 section，实验统一使用 ρ_v = 2.4。

---

## 六、批判性分析

1. **实验全部基于 SSD 模拟器，未在真实 SSD 上验证**。虽然论文做了 NVMeVirt vs Samsung 970 Pro 的 fidelity test（Fig. 9），但仅对比了 zoned F2FS 下的一个 FIO workload。CGC、Migration Upcall 等需要修改 FTL 固件的功能无法在真实 SSD 上测试，实际部署可行性存疑。

2. **Virtual Overprovisioning 导致实际可用容量缩水**。ρ_v = 2.4 意味着文件系统分区是物理容量的 2.4 倍，其中 GC region 占用等同于设备容量的 LBA 空间。虽然论文强调这是"virtual"的，但对于 FTL 内存开销（27.2 MB vs zoned F2FS 的 10.4 MB）和 L2P mapping 复杂度仍有实际影响。论文对此轻描淡写。

3. **需要修改 SSD 固件**（FTL 支持 CGC、Block Associative Mapping、Migration Record 管理），同时需要修改 Linux 内核（NVMe 驱动支持 Migration Upcall、F2FS 支持 upcall handler）。这种**跨越 host-device 边界的协同设计**在工程上极难推动落地——SSD 厂商不愿暴露内部机制，host 侧改动需要上游 Linux 社区接受。

4. **Immediate Discard 策略的开销未充分评估**。论文声称"recent SSD products"的 discard 开销变轻，但仅引用文献支撑，未在实验中量化 immediate discard 对前台 IO 延迟的影响。

5. **Workload 覆盖有限**。FIO 是纯随机写，MySQL 上的 TPC-C / YCSB 是数据库场景，Fileserver 涵盖混合操作——但缺少对 read-heavy workload、大文件顺序写、多租户等场景的评估。对于 GC region 的 read-redirect 开销在高并发读场景下的表现未做分析。

6. **与 IPLFS 的对比可能不完全公平**。IPLFS 的 Interval Mapping FTL 在随机写下内存膨胀是已知问题，论文的对比更多反映了 Interval Mapping 的缺陷而非 D2FS 的优势。

---

## 七、总结

D2FS 提出了一种将文件系统级 GC 完全下放到存储设备的方案，通过 Coupled Garbage Collection（设备 GC 同时回收文件系统 section）、Migration Upcall（异步通知 host 更新 filemap）和 Virtual Overprovisioning（确保设备 GC 先于文件系统耗尽空闲空间触发）三个技术组件，消除了 log-structured filesystem 最大的性能瓶颈。在 FIO 上实现 3× 于 F2FS 的吞吐提升，尾延迟大幅降低。主要局限在于需要同时修改 SSD 固件和 Linux 内核，且实验完全基于模拟器，距离实际部署仍有较大距离。
