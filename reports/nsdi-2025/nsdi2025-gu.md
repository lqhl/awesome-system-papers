# HA/TCP: A Reliable and Scalable Framework for TCP Network Functions

**作者**：Haoyu Gu, Ali José Mashtizadeh, Bernard Wong（University of Waterloo）
**会议**：NSDI 2025（22nd USENIX Symposium on Networked Systems Design and Implementation）
**链接**：https://www.usenix.org/conference/nsdi25/presentation/gu
**源文件**：[[nsdi2025-gu.pdf]]

---

## 一、背景

Layer 7 网络功能（Network Functions, NFs）是现代网络基础设施的关键组成部分，包括缓存代理、TLS 终止、TCP 拼接器和 WAN 加速器等。这些 NF 在网络中的关键位置处理和转换流量，例如 Cloudflare 使用 L7 代理改善 Web 服务的性能和安全性。任何 NF 宕机都会直接导致服务中断，造成财务和声誉损失。

与 L2-L3 NF 不同，L7 NF 包含完整的 TCP 协议栈，终止 TCP 连接并对流量进行复杂的读-修改-写操作。这使得 L7 NF 的可靠性和可扩展性面临独特挑战。Microsoft 的研究表明，NF 故障占严重事故的 42%，部分故障持续超过一天。由于 L7 NF 执行流量转换（如加密、压缩、封装），无法像 L2-L3 NF 那样使用 fail-to-wire 机制绕过故障。

---

## 二、要解决的问题

1. **L7 NF 状态复杂**：L7 NF 拥有完整的 TCP 协议栈和应用层状态，单个数据包的状态更新量比数据包本身还大，现有的 L2-L3 NF 状态复制框架（S6、Stateless-NF、FTC）假设 NF 只修改少量状态变量，无法适用于 L7 NF。

2. **状态更新频繁且流水线化**：L7 NF 在处理流水线中多次读写状态变量（TCP、TLS、应用状态），尝试批量化状态更新会导致正确性或性能问题。

3. **延迟 ACK 的性能问题**：一种直觉方案是延迟 TCP ACK 直到 NF 应用处理完成后再发送，但这会增加感知 RTT，导致 TCP 窗口缩小和拥塞控制误判，严重影响性能。

4. **现有 TCP failover 系统的不足**：已有的 TCP failover 方案（FT-TCP、Snoeren 等）不透明（需修改客户端 TCP 栈）、不支持常见 TCP 扩展、开销高（30% 以上），且多数已停止维护超过 20 年。

---

## 三、洞察与设计

**关键洞察**：大多数 NF 的应用状态都源自 TCP 流本身（most NF state derives from the TCP flow）。因此，只要保证 TCP 协议栈在 primary 和 replica 上的行为完全一致（输出确定性），NF 应用就能在两端产生相同的输出，从而实现透明的故障切换和迁移。

基于这一洞察，HA/TCP 的核心设计如下：

- **Active Replication**：primary 拦截所有来自客户端的 TCP 数据包，在 TCP 协议栈处理之前通过 replication channel 转发给 replica。replica 确认收到后，两端同时进行 TCP 处理。
- **Replicated Sockets**：提供与标准 socket 兼容的 API，封装复制细节，消除 primary 和 replica 之间的非确定性。NF 开发者只需确保应用逻辑不产生外部可见的非确定性。
- **IP-based Replication Channel**：使用自定义 IP 协议而非 TCP 作为复制通道，避免 TCP-over-TCP 导致的 meltdown 问题，同时消除锁竞争和拥塞控制开销。
- **IP Clustering**：基于分布式 LACP 协议，允许多个节点共享同一 IP 地址，实现水平扩展和连接级别负载均衡。
- **CARP 故障检测**：使用 CARP 协议进行故障检测和 leader election，默认 300ms 检测时间。

---

## 四、实现细节

HA/TCP 基于 FreeBSD 13.1 网络栈实现，运行在 DPDK 上（通过 F-Stack）。

**代码规模**：
| 组件 | 代码行数 |
|------|---------|
| HA/TCP 内核代码 | 10K SLOC |
| IP Clustering | 1.4K SLOC |
| SOCKS Proxy | 3.3K SLOC |
| WAN Accelerator | 8.7K SLOC |
| Distributed Load-balancer | 1.2K SLOC |

**关键实现细节**：

- **Primary 处理流程（5 步）**：(1) 在 TCP checksum 验证和控制块查找后拦截数据包；(2) 将原始数据包入队并记录 TCP 控制块引用；(3) 复制数据包并通过 replication channel 发送给 replica；(4) 等待 replica 确认；(5) 收到确认后释放队列中的数据包恢复 TCP 处理。
- **Replica 处理流程（5 步）**：(1) 接收并立即确认（在 NIC 线程中，避免 jitter）；(2) 入队等待 TCP 状态就绪；(3) 同步时间相关状态；(4) 按条件交付数据包给 TCP 栈；(5) 丢弃出站数据包（仅保留在 socket buffer 中用于重传）。

**关键优化（性能提升 10×+）**：

| 优化 | 效果 |
|------|------|
| TCP LRO | 将小包合并为 64KiB 大包，减少 PPS 40×，吞吐提升 6.2× |
| Shallow Copy (m_copypacket) | 避免 deep copy，仅复制 mbuf header 并引用计数 payload |
| IP-based Replication Channel | 替换 TCP 通道，消除锁和拥塞控制开销，避免 TCP meltdown |
| 统一 IP 分片与包复制 | 合并两个操作为一次拷贝，吞吐额外提升 67% |

**TCP 选项支持**：支持 SO_REUSEPORT、SYN Cache 随机状态同步、Syncookie/TFO、SACK、PAWS 时钟同步、多种拥塞控制算法（NewReno、DCTCP、H-TCP 等）。

---

## 五、实验结果

**实验平台**：双路 Intel Xeon Gold 6342，双端口 100Gbps Mellanox ConnectX-6 NIC，100Gbps Mellanox 交换机。Client-Primary MTU 1500 bytes，节点间 MTU 9000 bytes。

### 微基准测试

| 指标 | 结果 |
|------|------|
| 最大吞吐（iPerf3, receive-bound） | 90.5 Gbps（仅 3.4% 下降） |
| 最大吞吐（iPerf3, transmit-bound） | 仅 0.3% 下降 |
| 延迟增加 | 平均 11µs |
| 迁移时间 | 38µs（含网络延迟），TCP 操作仅 16µs |
| 迁移速度 vs. Prism | 2.4× 更快 |
| 迁移速度 vs. Capybara | 1.7× 更快 |
| 多节点扩展（6 节点） | 线性扩展，仅 2% 低于理想值 |
| 复制通道内存开销 | 峰值 ~875 KiB |

### NF 应用测试

| NF 应用 | 吞吐下降 | Primary CPU 增加 | 总 CPU 增加（含 Replica） | Failover 时间 |
|---------|---------|-----------------|------------------------|--------------|
| WAN Accelerator | 无统计显著变化 | 6.4% | 106% | 132µs（检测后） |
| SOCKS Proxy | 2% | 29% | 102% | 84ms（检测后） |
| Load Balancer | 迁移后双节点聚合 181.2 Gbps | — | — | — |

---

## 六、批判性分析

1. **CPU 开销被低估**：论文强调吞吐下降仅 0.2%-3.4%，但 replica 的 CPU 使用实际上是 100% 的额外资源消耗。对于 WAN Accelerator，总 CPU 开销增加 106%，意味着需要翻倍的计算资源。论文将这一成本以"包含 replica 的总 CPU 使用"轻描淡写。

2. **实验环境过于理想**：所有测试在 LAN 环境下进行（primary-replica 延迟极低），论文声称这是"worst-case"（因为 WAN 场景下复制延迟相对更小），但真实部署中 primary-replica 可能跨机架甚至跨数据中心，延迟和丢包特性完全不同。

3. **SOCKS Proxy failover 时间高达 84ms**：这远超论文宣称的"毫秒级"failover。原因是 replica 队列积压了约 44 个请求。论文将此归因于"1MiB response size"的特殊性，但在实际负载下，大响应是常见场景，这暴露了队列机制在高吞吐场景下的根本限制。

4. **IP Clustering 不支持复制**：论文承认 IP Clustering 目前不支持与复制同时使用，需要额外的应用编排来管理 primary-replica 对的放置。这意味着论文展示的扩展性测试和可靠性测试实际上是在不同配置下运行的，无法同时获得两者。

5. **多 replica 支持的实用性存疑**：论文声称支持多 replica，但实际测试全部使用单 replica。多 replica 需要额外的专用网络接口或尚未实现的 multicast 支持，实际可行性未验证。

6. **NF 开发者的负担被低估**：论文声称开发者只需"确保不产生外部可见的非确定性"，类似游戏引擎的编程纪律。但 WAN Accelerator 的例子说明，当 replica cache miss 时需要从 peer 获取值——这意味着开发者仍需处理复杂的状态同步逻辑，而非简单地"使用 replicated socket"。

7. **缺乏与现代系统的对比**：迁移时间的比较对象 Prism (NSDI'21) 和 Capybara (APSys'23 workshop paper) 代表性有限。论文未与任何商用 L7 NF 高可用方案（如 Envoy + xDS、HAProxy seamless reload）做对比。

---

## 七、总结

HA/TCP 是首个为 TCP-based L7 NF 提供迁移和故障切换支持的框架。通过 active replication、replicated socket 接口和多项针对 100Gbps 网络的优化，实现了低开销的透明故障切换（38µs 迁移，300ms 故障检测 + 13µs 切换）。系统基于 FreeBSD/DPDK 实现，适用于 WAN 加速器、SOCKS 代理、负载均衡器等 L7 NF 场景。主要局限在于：需要翻倍的 CPU/NIC 资源用于 replica，IP Clustering 与复制尚不能同时使用，以及在高吞吐大响应场景下 failover 时间可能显著增长。
