# Tigon: A Distributed Database for a CXL Pod

## 论文基本信息

| 字段 | 内容 |
|------|------|
| 标题 | Tigon: A Distributed Database for a CXL Pod |
| 作者 | Yibo Huang, Haowei Chen, Newton Ni（UT Austin）；Yan Sun（UIUC）；Vijay Chidambaram, Dixin Tang, Emmett Witchel（UT Austin） |
| 会议 | OSDI 2025 |
| 链接 | https://www.usenix.org/conference/osdi25/presentation/huang-yibo |

## 研究背景与动机

构建高效的**分布式事务性数据库**在数十年研究后仍是挑战。现有分布式数据库通过**网络**同步跨主机数据访问，引入大量消息交换和网络延迟开销。

**共享内存架构的问题**：
- 传统 shared-nothing 数据库：分区事务代价高，需要 2PC
- RDMA 方案：内存访问延迟仍比本地 DRAM 高 1-2 个数量级

**CXL 内存的出现**：
- CXL 3.0/3.2 支持跨主机硬件缓存一致性
- 延迟（214-394ns）比 RDMA（微秒级）低很多
- 可以在多主机间共享内存模块（CXL pod，8-16 台主机）

**CXL pod 的局限**：
1. 延迟仍比本地 DRAM 高（214-394ns vs 111-117ns）
2. 带宽比本地 DRAM 低（18-52 GB/s vs 218-246 GB/s）
3. **硬件缓存一致性内存容量有限**（仅几十到几百 MB）

## 核心问题

如何构建一个**利用 CXL 内存加速跨主机事务处理**的分布式内存数据库，同时：
1. 克服 CXL 的更高延迟和更低带宽
2. 处理有限的硬件缓存一致性容量
3. 避免 2PC 的高开销

## 主要贡献

1. **首个 CXL Pod 分布式内存数据库**：通过 CXL 内存中的原子操作同步跨主机并发数据访问
2. **软件缓存一致性协议**：扩展可缓存的 CXL 内存区域（将元数据放入 HWcc 区域，数据放入 SWcc 区域）
3. **高效的跨主机 CAT 访问**：利用数据库锁和索引在数据移动时高效访问
4. **无 2PC 的事务语义**：增强 2PL +  epoch-based logging，避免跨主机两阶段提交
5. 开源：https://github.com/ut-datasys/tigon

## 研究方法与设计

### 核心洞察

**关键观察**：虽然数据库可能很大，但**并发运行的事务所访问的元组集合很小**（Cross-host Active Tuples，CAT）。
- TPC-C 每事务平均访问 39 个元组，约 7KB
- 1000 核 × 每核 1 事务 = 最多 39K 活跃元组 ≈ 7MB

### Tigon 架构（基于 Pasha）

**数据分区**：初始分区到各主机 DRAM
**CAT 维护**：维护在共享 CXL 内存中
**跨主机同步**：使用 HWcc 区域中的锁和原子操作
**消息传递**：使用 CXL 内存作为传输（类似 HydraRPC）

### 数据组织

**本地 DRAM**：
- 分区数据存储在本地 DRAM
- `LocalRow`：包含 latch、2PL 锁、shortcut pointer、is-valid、epoch-version、tuple

**CXL 内存**：
- **HWcc 区域**（小但硬件缓存一致）：HWcc Record（8B）：excl latch + 2PL lock + has-next-key + is-dirty + clock-bit + SWcc bitmap + SWcc-row-ptr
- **SWcc 区域**（大但软件缓存一致）：SWcc Row：is-valid + epoch-version + tuple

### 软件缓存一致性协议

**设计原理**：硬件支持仅需对**频繁跨主机访问的元数据**（锁、latch）提供缓存一致性；数据本身可以不用硬件一致性保护。

**SWcc-bitmap**：每主机 1 位，追踪可缓存读取的主机集合
- 缓存读取时置位自己的位
- 写入时清除其他所有位
- 避免跨主机缓存一致性开销

### 事务执行

**避免 2PC 的关键洞察**：
1. 通过在 CXL 内存中维护 CAT，单个主机可以完成事务的所有修改
2. 索引修改可以重建，无需日志
3. 只需记录元组修改日志以保证原子性和持久性

**Epoch-based Group Commit**（基于 SiloR）：
- 事务在 epoch 内执行
- 小 epoch 号的事务先于大 epoch 提交

### NEXT-KEY Locking

增强 NEXT-KEY Locking 以避免幻读问题：
- 每个 SWcc Row 包含 has-next-key 标志
- 范围扫描时对下一条记录加锁

## 关键实现细节

- 基于 Pasha 架构
- 在 AMD EPYC 处理器 + CXL 内存模拟器上评估
- 使用 epoch-based logging 到本地 SSD
- 支持最多 16 台主机

## 实验结果与分析

### TPC-C 性能

**与 Sundial+（优化后的 Sundial）和 DS2PL+ 比较**：
- Tigon 在 60/90 多分区事务比例下比 Sundial+ 快 **2.5×**
- 比 DS2PL+ 快 **2.0×**

### YCSB（95% 读，5% 写）

- Tigon 在高多分区事务比例下显著优于 Sundial+ 和 DS2PL+
- 原因：CXL 内存使跨分区访问更高效

### 可扩展性

- 8 主机时 TPC-C 吞吐量提升 **5.7×**，YCSB 提升 **3.5×**
- Sundial+/DS2PL+ 的可扩展性明显更差（仅 2.4×/2.1×）

### 有限的 HWcc 内存

- 50MB HWcc 内存：性能仅比无限制 HWcc 低 5.8%
- 10MB HWcc 内存：因频繁数据移动性能下降

### 软件缓存一致性

- Tigon 比 NonTemporal（非临时访问）高 11%-20%
- 比 NoSWcc（无 SWcc）高 11%-20%（高多分区比例场景）

### 优化效果

- Shortcut pointer：TPC-C 吞吐量提升 16%
- 脏读优化（is-dirty flag）：YCSB 读吞吐量提升 60%

## 潜在问题与局限性

1. **CXL 硬件限制**：CXL 3.0/3.2 硬件缓存一致性内存容量"几十到几百 MB"——这在实际 CXL 设备上有多大？论文承认"具体数字未知"，依赖供应商
2. **Emulation 评估**：部分评估（CXL 延迟、带宽、跨主机一致性）基于 emulated 测试床，而非真实 CXL 3.0 硬件
3. **与 RDMA 数据库的比较**：仅与 Motor（基于 RDMA 的数据库）比较，但 Motor 是一个较老的系统，可能不公平
4. **故障模型**：假设 fail-stop 模型，failure 发生时整个系统失败，缺乏更细粒度的容错分析
5. **CXL Pod 规模**：仅支持 8-16 台主机构成的 pod，无法直接扩展到大规模集群
6. **调试难度**：CXL + 数据库 + 分布式系统的组合极其复杂，生产环境调试将是巨大挑战

## 未来工作方向

1. 在真实 CXL 3.0 硬件上评估
2. 处理无硬件缓存一致性的 CXL 内存配置
3. 更大规模的 pod 支持

## 个人评注

**优点**：
- **洞察深刻**：CAT（Cross-host Active Tuples）概念非常精准——正是这个"活跃数据"才是跨主机事务处理的关键
- **SWcc/HWcc 分离的设计**优雅地将数据库一致性机制和 CXL 缓存一致性结合起来
- **避免 2PC** 的设计非常巧妙，通过 epoch-based logging + 单主机执行所有操作 + 索引重建实现
- 实验覆盖面广，从 microbenchmark 到 TPC-C 和 YCSB

**潜在争议**：
- **"首个"CXL Pod 数据库**的声称：Pasha 论文（CIDR 2025）描述了一个数据库架构，Tigon 是其实现。但 Pasha 的架构设计与 Tigon 几乎完全相同，CIDR 2025 和 OSDI 2025 同时接受，Tigon 是否真正解决了"首个"问题存疑
- **Emulation 评估的局限性**：CXL 3.0 硬件尚未广泛可用，论文的评估大量依赖 emulation。这意味着实验结果的实际可重复性和在真实硬件上的表现存疑
- **与 Motor 的比较**：Motor 是一个较老的设计（假设 RDMA 硬件），Tigon 的优势可能部分来自与较弱 baseline 的比较
- **10 亿级数据支持**：论文未讨论数据规模扩展，当 CAT 超过 CXL 内存容量时系统行为

总体而言，Tigon 是一项扎实的系统工作，为 CXL Pod 上的数据库设计提供了重要的系统化思路。
