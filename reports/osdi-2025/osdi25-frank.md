# Picsou: Enabling Replicated State Machines to Communicate Efficiently

## 论文基本信息

| 字段 | 内容 |
|------|------|
| 标题 | Picsou: Enabling Replicated State Machines to Communicate Efficiently |
| 作者 | Reginald Frank, Micah Murray, Chawinphat Tankuranand, Junseo Yoo, Ethan Xu, Natacha Crooks (UC Berkeley); Suyash Gupta (University of Oregon); Manos Kapritsos (University of Michigan) |
| 会议 | OSDI 2025 |
| 链接 | https://www.usenix.org/conference/osdi25/presentation/frank |

## 研究背景与动机

复制状态机（RSM）是现代分布式系统的核心抽象，广泛应用于键值存储（如 Etcd）、集群管理器、微服务等场景。这些 RSM 经常需要跨集群、跨组织进行通信，例如：
- Etcd 到 Etcd 的灾难恢复镜像（经由 Kafka）
- 政府对等机构之间的数据共享
- 区块链互操作性

然而，现有的跨 RSM 通信方案存在严重缺陷：
1. **Ad-hoc 方案**：缺乏正式保证，行为模糊或随时间演变
2. **可信第三方**：引入额外信任假设
3. **全对全广播（All-to-All Broadcast）**：当 RSM 跨地域分布时，WAN 带宽有限且成本高昂

## 核心问题

构建一个高效、健壮的 RSM 间通信协议需要满足四个要求：
1. **强保证**：需要精确且形式化的框架来描述 RSM 间通信
2. **故障健壮性**：恶意或崩溃节点不能影响正确性或系统吞吐量
3. **低开销**：无故障情况下仅需发送单条消息、常量元数据
4. **通用性**：支持异构大小、通信和故障模型的任意 RSM（包括 BFT 和 CFT 协议）

## 主要贡献

1. **提出 Cross-Cluster Consistent Broadcast (C3B) 原语**：为 RSM 间通信提供形式化框架，保证 Eventual Delivery 和 Integrity
2. **实现 PICSOU**：首个实用的 C3B 协议，支持异构 RSM 间的全双工通信
3. **引入 QUACKs（Quorum Acknowledgments）**：累积性仲裁确认，用于精确判断消息是否已可靠接收或可能丢失
4. **支持权益证明 BFT 系统**：通过加权 QUACK 和动态份额调度（DSS）处理 staking 场景

## 研究方法与设计

### C3B 形式化

C3B 定义两个操作：
- **Transmit**：发送方 RSM 中的正确副本调用 C3B 发送消息 m
- **Deliver**：接收方 RSM 中的正确副本输出消息 m

两个正确性属性：
- **Eventual Delivery**：如果 RSM S 发送消息 m，则 RSM R 最终交付 m
- **Integrity**：每个消息 m，RSM R 当且仅当 RSM S 发送了 m 才交付 m

### PICSOU 核心设计

**设计灵感**：TCP 的全双工通信 + 累积 ACK

PICSOU 将 C3B 实现分解为三个设计支柱：

**(P1) 效率**：无故障情况下每条消息仅发送一次，RSM 内最多 O(n) 份副本，元数据为常量大小

**(P2) 通用性**：支持任意大小 RSM，兼容 CFT（如 Raft）和 BFT（如 PBFT、Algorand）协议，支持同步/异步网络

**(P3) 健壮性**：崩溃或恶意副本对性能影响最小；协议在主动重传消息（降低延迟）和防止拜占庭节点触发虚假重传之间取得平衡

### QUACKs 机制

QUACK 是 PICSOU 的核心创新。它是消息 m 的累积性仲裁确认：
- 简洁地传达"所有小于等于 m 的消息已被接收方 RSM 中至少一个正确节点可靠接收"这一信息
- 重复的 QUACK（相同序列号）表明序列号+1 的消息未被接收

**关键性质**：
- 无故障时每条消息仅需一次发送
- 两个额外计数器作为元数据
- 拜占庭节点无法单方面触发虚假重传

### 加权 RSM 支持（Stake-based BFT）

对于权益证明系统（如 Algorand），需要修改 QUACK 和发送策略：
- **加权 QUACK**：权重由节点 stake 决定，当总权重达到 $u_i+1$ 时形成 QUACK
- **动态份额调度（DSS）**：基于 Hamilton  apportionment 方法，确保：
  - 可靠副本在有限时间内发送消息
  - 短期内/长期内公平性
  - 支持任意 stake 值

## 关键实现细节

- 约 4500 行 C++20 代码
- 使用 Google Protobuf 进行序列化，NNG v1.5.2 网络库
- 设计为即插即用库，易于集成到现有 RSM
- φ-list 机制用于垃圾回收（φ-list 大小 200k）
- 支持 Raft（Etcd v3.0）、ResilientDB（PBFT）、Algorand 等多种 RSM

## 实验结果与分析

### 通用性能

在无故障的 File RSM 场景下（8 节点）：
- PICSOU 吞吐量比 Kafka 高 **2×**
- 比传统 All-to-All 广播高 **3.2×**（小网络，4 节点）
- 比传统 All-to-All 广播高 **24×**（大网络，19 节点）

### 真实应用

1. **Etcd 灾难恢复**：PICSOU 比 Kafka 快 2 倍以上
2. **数据协调应用**：PICSOU 性能显著优于 Kafka baseline

### 故障恢复

- 消息重传策略最小化重传次数
- 拜占庭节点无法触发虚假重传

## 潜在问题与局限性

1. **Reconfiguration 假设**：假设重配置罕见，且存在节点成员变更的可靠机制
2. **乐观协议**：领导者故障时回退到全对全广播，最坏情况下延迟较高
3. **Staking 系统的 LCM 缩放**：当两个 RSM 总 stake 差异极大时，需要将 stake 缩放到 LCM，可能导致消息量子很大
4. **不假设时间同步**：不依赖同步或部分同步假设，但这也意味着最坏情况下的活性需要进一步分析

## 未来工作方向

1. 更高效的领导者故障检测机制
2. 与区块链轻客户端的集成
3. 支持更大规模异构 RSM 网络

## 个人评注

**优点**：
- C3B 原语的提出填补了 RSM 间通信缺乏形式化框架的空白
- QUACKs 机制简洁而优雅，将 TCP 的累积 ACK 思想迁移到分布式状态机领域
- 对 BFT 和 CFT 的统一支持设计巧妙
- 实验覆盖面广，从 microbenchmark 到真实应用

**潜在争议**：
- 文章声称 QUACK 机制"metadata-optimal"，但实际实现需要 φ-list 等额外元数据
- 对于 staking 系统的 LCM 缩放方案，在极端不对称场景下（如 total stake 差异 6 个数量级）消息量子的处理可能需要进一步分析
- 与 GeoBFT/OTU 的比较显示 PICSOU 在领导者故障时需要更多重传（u_s × u_r vs u_s），这一点在论文中未充分讨论
- 实际部署中，RSM 需要主动转发已提交消息到 PICSOU 层，这可能引入额外延迟

总体而言，Picsou 是一项扎实的系统工作，其 QUACKs 机制对分布式系统社区具有重要参考价值。
