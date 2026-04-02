# ShiftLock: Mitigate One-sided RDMA Lock Contention via Handover

**作者**：Jian Gao, Qing Wang, Jiwu Shu（清华大学）
**会议**：FAST 2025（23rd USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast25/presentation/gao
**源文件**：[[fast2025-gao.pdf]]

---

## 一、背景

RDMA 网络在分布式存储系统中被广泛部署，提供超低延迟（≤2µs RTT）和高吞吐量（如 NVIDIA ConnectX-7 达 370M pkts/s）。基于 RDMA 的分布式锁（RDMA lock）利用 one-sided verbs 直接操作锁服务器上的锁条目，绕过服务端 CPU，在低竞争场景下仅需一次网络往返即可完成锁的获取和释放，性能优越。

然而，随着系统规模和并发度的增长，高竞争场景下 RDMA 锁面临严重的性能瓶颈：所有客户端的网络流量都指向锁服务器（N-to-1 通信模式），失败的锁获取必须重试，重试消耗 RNIC 的 inbound IOPS 资源，导致 goodput 急剧下降。实验表明，240 个客户端竞争同一把 CAS 锁时，94.4% 的 CAS verbs 是重试，goodput 从理想的 278.3K ops/s 降至 15.5K ops/s。即使使用最先进的 truncated exponential backoff（SMART），仍有 87.1% 的 CAS verbs 是重试，goodput 比理想情况低 49.2%。

---

## 二、要解决的问题

1. **重试开销巨大**：现有 RDMA 锁在高竞争下客户端反复重试，每次重试消耗一次 RDMA 往返，浪费服务器 RNIC IOPS 并增加延迟。Backoff 策略只能缓解而非根本解决。

2. **客户端间直接通信的挑战**：MCS lock 的 handover 思想在单机环境成熟，但在分布式环境面临三个难题：
   - RPC 通信是阻塞且 CPU 密集的
   - 维护全连接（RC QP）不可扩展
   - 客户端故障会破坏队列，导致后续客户端永远无法获取锁

3. **缺乏读写语义**：原始 MCS lock 不支持 reader-writer 语义，而其分布式变体需要多次访问锁条目（多次网络往返），延迟过高。

4. **容错问题**：客户端故障时，现有的 one-sided 恢复机制存在 ABA 问题，可能导致锁状态被错误覆盖。

---

## 三、洞察与设计

**关键洞察**：在 RDMA 环境中，客户端的 CPU 是空闲的（不参与锁管理），可以利用这一点让客户端之间直接通过 two-sided RDMA（Send/Recv）进行非阻塞的锁 handover，从而将 N-to-1 的通信模式转变为客户端间的点对点协调，根本上消除重试。

基于此洞察，ShiftLock 的核心设计包括：

**1. 高效的客户端间通信机制（§3.2）**
- 使用 Send/Recv 而非 Write，避免额外 96 bits 元数据开销
- 消息是非阻塞通知，接收方可延迟处理（释放锁时再检查），无需专用 CPU 轮询
- 采用 RDMA Dynamic Connection (DC) 实现可扩展通信，DCI 连接新 DCT 仅需 <1µs
- 将路由信息从 168 bits（GID+LID+QPN）压缩到 40 bits（16-bit NodeID + 24-bit DCT QPN）

**2. 分布式 MCS Lock 实现（§3.3）**
- 使用 ExtCAS（extended atomic CAS，compare mask 设为零）模拟 FetchAndStore 语义，确定性地只需一次网络往返入队
- 入队后通过 Send 通知前驱，释放时通过 Send 将锁 handover 给后继

**3. Reader-Writer 语义（§3.4）**
- 在锁条目中嵌入 23-bit RdrCnt（支持 8M 并发 reader）
- 使用 ExtFAA（extended FetchAndAdd）独立修改 RdrCnt 而不影响 TailPtr
- 引入 64-bit RelCnt 计数释放次数，让 queue head writer 知道所有前驱 reader 何时离开
- 锁条目扩展到 128 bits，利用 extended atomics 支持 128-bit 操作数

**4. Starvation Avoidance（§3.5）**
- 写优先设计：writer 入队后立即阻止新 reader
- 引入 1-bit Epoch 字段实现 writer→reader 的锁转移，writer 翻转 Epoch 即可让等待的 reader 进入临界区
- 使用连续 writer 计数阈值 N=16 决定何时转移锁给 reader

**5. 容错机制（§3.6）**
- 基于 lease（T_lease = 10ms），客户端周期性检查 RelCnt
- 3×T_lease 超时后向 server 发 RPC 请求恢复，server 维护 era 计数器防止 ABA 问题
- 恢复时 RelCnt 增加 2^63，其他客户端识别到跳变后重启锁获取

---

## 四、实现细节

**锁条目格式**（128 bits 对齐）：
| 字段 | 位宽 | 用途 |
|------|------|------|
| Epoch | 1 bit | 读写模式切换信号 |
| RdrCnt | 23 bits | 活跃 reader 计数 |
| NodeId | 16 bits | 节点标识（支持 65535 节点） |
| DctQpNum | 24 bits | DC Target QP 号 |
| RelCnt | 64 bits | 释放计数（含故障恢复标记） |

**关键 RDMA 原语使用**：
- ExtCAS（compare mask = 0）：模拟 FetchAndStore，writer 入队
- ExtCAS（指定 compare/swap mask）：writer 释放时原子清零 TailPtr + 更新 RelCnt + 翻转 Epoch
- ExtFAA（带 field mask）：reader 原子增减 RdrCnt / RelCnt

**实现规模**：7.2K 行 Rust 代码。

**消息类型**：
- Successor：新 writer 通知其前驱自己的路由信息
- Handover：writer 释放时将锁转交后继 writer
- ModeChanged：writer 决定转移锁给 reader 时发送

---

## 五、实验结果

**实验平台**：6 台机器（1 server + 5 clients），Intel Xeon E5-2650 v4（48 核/机），128GB DDR4，Mellanox ConnectX-5 100Gbps RNIC，InfiniBand 交换机。总客户端数 240。

### 微基准测试（Zipfian-0.99 workload）

| 指标 | ShiftLock vs 最佳基线 |
|------|----------------------|
| Goodput (WI) | 最高可达 3.62× |
| Goodput (RI) | 最高可达 1.26× |
| P99 延迟降低 | 最高达 76.6% |
| 平均 RDMA verbs/cycle | 2.01 atomics + 0.36 Reads (WI) |

### 分布式事务

| 工作负载 | ShiftLock 提升 |
|---------|---------------|
| TATP | goodput 提升 1.25×–2.85×，GSD/UL 中位延迟降低 19.6%/16.8% |
| TPC-C | goodput 提升 1.09×–2.14×，延迟相当或更低 |

### Banking 应用（SmallBank）
- RedLock: 5.56K ops/s → ShiftLock: 36.55K ops/s（~6.6×）
- 中位延迟降低 62.9%，P99 延迟降低 95.2%

### 容错
- 在 10^-5 到 10^-2 故障率下，ShiftLock 均能恢复，goodput 与 DSLR 同一数量级，但因超时值更大（3×T_lease vs 2×T_lease）略低于 DSLR。

---

## 六、批判性分析

1. **硬件依赖性强**：ShiftLock 依赖 RDMA extended atomics（ExtCAS、ExtFAA），这是 Mellanox/NVIDIA mlx5 系列 RNIC 的特性，并非所有 RDMA 设备支持。论文未讨论在不支持 extended atomics 的硬件上的 fallback 方案或可移植性问题。

2. **容错性能明显劣于 DSLR**：ShiftLock 的恢复超时为 3×T_lease（30ms），而 DSLR 为 2×T_lease（20ms）。更关键的是，当客户端向已故障节点发送消息时会触发 RNR 错误导致 DCI QP 进入 error state，需要重置。在高故障率下（如 10^-2），ShiftLock goodput 低于 DSLR 约一个数量级。论文将此轻描淡写为"同一数量级"，但在 failure-prone 场景（如云环境中的抢占式实例）这是实际问题。

3. **写优先设计的局限性**：ShiftLock 是 write-preferring 的，writer 入队后立即阻止新 reader。虽然 N=16 的阈值避免了 reader starvation，但在读密集场景下，writer 到来时所有新 reader 都必须等待，可能导致 reader 延迟抖动。论文承认 "when RdrCnt is zero, the lock may continue to be handed over among writers" 但将此优化留作 future work。

4. **评估硬件较旧**：实验使用 ConnectX-5（2017 年）和 Xeon E5-2650 v4（2016 年），已落后主流数据中心硬件两代以上。ConnectX-7 的 IOPS 更高，backoff 方案在新硬件上的相对劣势可能缩小，ShiftLock 的优势幅度存疑。

5. **锁规模固定 10M 的合理性存疑**：10M 锁在 Zipfian-0.99 分布下热点锁的竞争程度有限。论文虽有不同锁数量的实验（Figure 7），但事务负载（TATP/TPC-C）的锁数量远小于 10M，且 TATP 中 ShiftLock 对 CAS/MCS 的优势仅 6.9%，说明在中低竞争场景下优势不显著。

6. **DC 的实际开销未充分评估**：Dynamic Connection 的连接切换在高频 handover 场景下可能引入额外延迟，论文提到 <1µs 但未在高负载下系统性测量。

---

## 七、总结

ShiftLock 将单机 MCS lock 的 handover 思想成功迁移到分布式 RDMA 环境，通过客户端间 two-sided RDMA 直接传递锁所有权，根本性地减少了高竞争下的重试流量。其设计巧妙地利用了 RDMA extended atomics 实现紧凑的 128-bit 锁条目和高效的读写语义。在高竞争场景下，ShiftLock 相比现有 RDMA 锁提升 goodput 最高 3.62× 并降低尾延迟最高 76.6%。主要局限在于对 extended atomics 硬件特性的依赖、容错性能不及纯 one-sided 方案、以及在低竞争场景下优势有限。适用于高竞争、读写混合的分布式存储系统锁管理场景。
