# Scalio: Scaling up DPU-based JBOF Key-value Store with NVMe-oF Target Offload

## 论文基本信息

- **标题**: Scalio: Scaling up DPU-based JBOF Key-value Store with NVMe-oF Target Offload
- **作者**: Xun Sun, Mingxing Zhang, Yingdi Shan, Kang Chen, Jinlei Jiang (清华大学), Yongwei Wu (清华大学, 全程实验室)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/sun

## 研究背景与动机

随着数据密集型应用的快速增长，高密度存储系统的需求急剧增加。DPU-based Just a Bunch of Flash (JBOF) 架构作为一种节能且成本效益高的方案引起了学术界和工业界的广泛关注。然而，现有 JBOF 解决方案在处理大量附加 SSD 时面临严重的扩展性问题，根本原因在于它们严重依赖 DPU 的 CPU 来执行 SSD I/O 操作。

DPU 的 Arm CPU 核心相比通用 CPU 提供了更好的能效（BlueField-3 仅消耗 75-150W，而 Xeon CPU 消耗 300-500W），但缺乏处理多块 SSD 聚合 IOPS 的计算能力。更关键的是，作者发现网络资源在这些 IOPS 密集型场景中严重未被利用——网络 IOPS 利用率不到 1%（ConnectX-6 具备 200M IOPS 能力，但实际只用了不到 600K）。

## 要解决的核心问题

1. **CPU 扩展瓶颈**: 在高密度 SSD 配置下（>4 块 SSD），DPU 的 CPU 成为性能瓶颈，导致系统吞吐量无法随 SSD 数量扩展
2. **网络资源浪费: 网络 IOPS 利用率极低（<1%），与 SSD I/O 能力和 RDMA 读写能力之间存在三个数量级的差距
3. **缓存一致性问题: 使用 NVMe-oF Target Offload 时，客户端直接读取 SSD 数据，绕过了 DPU 的 CPU 和 DRAM 缓存，导致缓存与 SSD 之间的一致性问题
4. **写入放大: 传统方案中每次写入需要两次 SSD 写操作，造成写入密集型工作负载下的严重瓶颈

## 主要贡献

1. **首个利用 NVMe-oF Target Offload 的可扩展分解式键值存储**: 充分利用网络 IOPS 资源，绕过 DPU CPU 处理 SSD 读操作
2. **两层内存数据结构**: 结合 DRAM 热点缓存和 NVMe-oF Target Offload SSD 直读，并通过批量写入的 group commit 机制处理突发写入
3. **RDMA 驱动的缓存一致性协议**: 基于 occupied 和 complete 两个标志位的状态机设计，保证线性化（linearizability）一致性
4. **显著的实验验证**: 在 7 块 SSD 配置下，相比 LEED+Ditto 达到 1.8×-3.3× 加速，相比 LEED 达到 2.5×-17× 加速

## 研究方法与设计

### 读操作工作流（完全单边）
1. **内存查询阶段**: 客户端使用 RDMA Read 获取哈希块，在块内线性搜索目标 key。如果命中缓存（State C），直接返回；如果缓存未命中，选择 victim slot 并用 RDMA CAS 加锁
2. **双重读取验证**: 避免两个客户端同时填充同一 slot 导致的 key 冲突
3. **SSD 访问与缓存更新阶段**: 缓存未命中时，客户端直接通过 NVMe-oF Target Offload 从 SSD 读取数据，然后通过 RDMA Write 更新 victim slot

### 写操作工作流（混合模式）
1. **追加**: 客户端通过 RDMA 将写请求追加到 DPU 的内存环形缓冲区
2. **批量刷新**: DPU CPU 轮询环形缓冲区，积累批量后一次性写入 SSD
3. **Group Commit**: 定义提交点为 next_offset 字段更新时刻，保证写入的原子性
4. **缓存失效**: 写成功后通知所有客户端失效过时的缓存条目

### 缓存一致性协议
定义了四种 slot 状态：
- **State A (空)**: occupied=0, complete=1，可安全回收
- **State B (填充中)**: occupied=1, complete=0，值尚未完全写入
- **State C (有效)**: occupied=1, complete=1，值已完全写入且与 SSD 一致
- **State D (失效中)**: occupied=0, complete=0，在更新过程中被另一客户端失效

**线性化点的定义**:
- 读命中: RDMA Read 到达缓存获取哈希块的时刻
- 读未命中: victim slot 被锁定并通过双重读取验证的时刻
- 写: SSD 上更新已应用且缓存中不存在同 key 的 State B/C slot 的最早时刻

## 关键实现细节

### 索引结构
- 哈希表将 key 映射到固定大小的哈希块（默认 1KB，最多容纳 10 个 100 字节的键值对）
- 每个 slot 包含: key, value, occupied 标志, complete 标志, last_ts (LRU 时间戳)
- 通过 last_ts 实现客户端中心的 LRU 驱逐策略

### 批量写入机制
- 环形缓冲区存储带 client ID 的写请求
- 批量大小小于 SSD 块粒度（4KB）时，一次性确定性写入所有块
- 客户端写操作持有到对应的 next_offset 更新后才被确认为已提交

### 故障处理
- **服务器故障**: 与 RAID 或双 DPU 设置正交集成
- **客户端故障**: 基于 lease 的超时机制，超时后其他客户端可回收锁定的 slot

## 实验结果与分析

### 测试环境
- 1 存储节点 + 5 客户端节点，通过 RDMA 网络互连
- 存储节点: 7 块 Samsung 970 PRO SSD + ConnectX-6 HCA
- 模拟 DPU 配置: 8 核 Intel Xeon Gold CPU + 8GB 内存
- 使用 YCSB 基准测试（A/B/C/D/F 工作负载）

### 关键结果
- **可扩展性**: LEED 吞吐量在 4 块 SSD 时达到上限，而 Scalio 随 SSD 数量线性扩展
- **读写加速比**: 读密集型工作负载达到 3× 加速；写密集型工作负载达到 2× 加速
- **消融实验**: Offloaded Read 提供 1.5×-3.2× 加速；Inline Cache 在只读/读密集型场景提供 2.7×-6.7× 加速；Batched Write 提供最高 1.96× 加速
- **延迟-吞吐量权衡**: Batched Write 引入约 2× 的延迟增加，但吞吐量提升 2.1×，整体收益明显
- **灵敏度分析**: Scalio 对 Zipfian 偏度、数据集大小和 CPU 核心数变化均表现出鲁棒性

## 潜在问题与局限性

1. **评估环境为模拟 DPU 而非真实 DPU**: 作者使用限制的 CPU 核数（8 核）和内存（8GB）模拟 DPU 配置，承认这是保守估算，但可能无法完全反映真实 DPU 环境的性能特征
2. **仅支持小键值对**: Scalio 专注于小键值对（key ≤ 16B, value ≤ 64B），对大值场景的适用性有限
3. **客户端数量规模**: 实验最多使用 160 个客户端线程，未在更大规模下验证
4. **公平性**: 对照系统使用相同 ARM 核分配策略和 SSD 绑定策略，但未与更广泛的 KV store 系统（如 FaRM、DrTM）进行比较
5. **NVMe-oF Target Offload 硬件依赖**: 该技术需要特定硬件支持（ConnectX 系列 HCA），可能限制其通用性

## 未来工作方向

1. 支持更大键值对的工作负载
2. 与更广泛的分布式键值存储系统集成
3. 探索 NVMe-oF Target Offload 在其他存储场景的应用

## 个人评注

### 优点
1. **问题定位精准**: 将 DPU-JBOF 系统的性能瓶颈准确归因于"CPU 资源"与"网络资源未利用"之间的错配，提供了令人信服的量化分析
2. **设计正交性好**: NVMe-oF Target Offload + 两层缓存 + 批量写入 + 缓存一致性协议，各层机制职责清晰，便于独立理解和验证
3. **一致性证明扎实**: 缓存一致性协议提供了形式化的线性化点定义，并从两部分证明了所有读写操作在线性化点处满足一致性
4. **实验全面**: 涵盖消融实验、灵敏度分析、延迟-吞吐量权衡分析

### 潜在问题
1. **实验对照组的规模**: 仅有 LEED 和 LEED+Ditto 两个 baseline，未与其他分布式 KV 存储（如 FaRM、HERD、DrTM）对比，可能无法充分说明其相对于传统 RDMA 优化方案的优劣
2. **NVMe-oF Target Offload 的硬件依赖**: 该方案严重依赖特定的硬件功能，可能限制其普适性，但在 DPU 场景下是合理的技术选择
3. **"3.3×"加速比与"1.8×-3.3×"范围的差异**: 论文标题和摘要中声称最高 3.3× 加速，但在论文中多处给出"1.8×-3.3×"（vs LEED+Ditto）和"2.5×-17×"（vs LEED）的范围，说明具体提升高度依赖于工作负载和 SSD 数量——这一差异本身不是问题，但阅读时需注意区分
4. **租约机制的简洁性**: Lease 机制使用简单的 timestamp + duration，理论上可行，但未讨论时钟同步问题对 lease 正确性的影响
