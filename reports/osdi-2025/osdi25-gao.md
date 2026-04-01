# Stripeless Data Placement for Erasure-Coded In-Memory Storage

**作者**：Jian Gao, Jiwu Shu (通讯作者), Bin Yan, Yuhao Zhang (清华大学); Keji Huang (华为)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/gao
**源文件**：[osdi25-gao.pdf](../../papers/osdi-2025/osdi25-gao.pdf)

---

## 一、背景

分布式内存存储系统构建在高速 RDMA 网络之上，为大量延迟敏感的热数据提供数量级快于磁盘的访问性能。这类系统需要容错机制来保障部分节点故障时的可用性和性能。数据冗余有两种主要方式：复制（replication）和纠删码（erasure coding）。复制简单但存储开销大；纠删码存储开销低但带来额外计算成本。由于内存远比磁盘昂贵，纠删码在内存存储系统中尤其有吸引力——可以容纳比复制多得多的对象。

然而，现有纠删码方案的核心概念——stripe（条带）——在高速内存存储场景下暴露出严重的性能问题。所有现有纠删码方案都要求每个数据块必须被分配到恰好一个 stripe 中，而无论采用 intra-object 还是 inter-object 的分配方式，都会引入显著的性能或存储开销。

---

## 二、要解决的问题

Stripe 导致数据放置受限，现有方案存在以下不足：

1. **Intra-object 方案**（如 Ceph, EC-Cache, Hydra）：每个对象被切分为 k 个 chunk 放在不同节点上，读写一个对象需要联系 k 或 (k+p) 个节点，I/O fanout 极高。对于真实负载中占 80% 的小于 1KB 的对象，这种开销不可接受。

2. **Inter-object 静态分配**（如 Cocytus 静态策略）：基于 hash 等静态策略将对象分配到 stripe，无法适应运行时的放置约束（如节点临时变慢），且 stripe 中可能出现空 chunk 造成内存浪费。

3. **Inter-object 动态分配**（如通过 MDS 动态分组）：每次访问都要先查询元数据服务（MDS），引入额外网络往返延迟，MDS 成为集中式瓶颈和单点故障。

总结：stripe 强迫系统在高 I/O fanout、内存浪费和 MDS 瓶颈之间三选一，在高速内存存储场景下均不理想。

---

## 三、洞察与设计

**关键洞察**：如果采用合适的数据放置策略（基于组合数学中的 SBIBD 结构来决定主备节点的亲和关系），可以在完全不使用 stripe 的情况下，仅用 XOR 编码就实现多节点故障容错——从而绕过 stripe 带来的所有性能缺陷。

基于此洞察，论文提出 **Nos**（"no-stripe"），一种无条带的纠删码数据放置方案：

- **编码方式**：每个节点独立地将主对象复制到 (p+1) 个备份节点；备份节点独立地将收到的 k 个不同源节点的数据副本 XOR 编码为 parity。无需中心化协调，写路径极简。

- **SBIBD 亲和矩阵**：使用 symmetric balanced incomplete block design (v,k,1)-SBIBD 来决定主节点到备份节点的映射关系。SBIBD 保证任意两行之间最多只有一个公共列值为 1，从而确保不同主节点的对象不会被复制到完全相同的备份节点集合，避免了 Figure 2 中的数据丢失风险。

- **故障恢复**：对于 p 个节点同时故障，论文证明任何丢失的对象都可以在至多两步递归中恢复——先恢复 parity 中编码的其他丢失对象，再恢复目标对象。平摊恢复成本不超过读取 k 个 chunk，与 Reed-Solomon 码相同。

- **参数关系**：集群大小 v = k² - k + 1，k 为每个 parity 编码的对象数，p 为容错阈值（要求 k > p）。

在 Nos 之上构建了 **Nostor**，一个分布式内存 KV 存储原型（Rust 实现，约 16K 行代码），采用前台线程处理读写 RPC、后台线程异步编码 parity 的架构，并通过版本号机制（SN/CSN）保证写入一致性。

---

## 四、实现细节

**Nostor 架构**：
- C/S 架构，服务端使用 DRAM 驻留的分片哈希表（DashMap）存储对象和 parity
- 通信基于全用户态 RDMA 之上的 RPC
- 集群按 subcluster（大小为 v）组织，subcluster 之间可重叠但不交叉编码

**写路径（PUT）**：
1. 在对象的版本队列中追加新版本并获取 SN
2. 计算新值与前一版本的 delta
3. 将 delta 复制到 (p+1) 个备份节点的 replication queue
4. 复制完成后更新 CSN，清除过期版本

**后台编码**：
- BGT（后台线程）轮询各 replication queue，每轮从每个源收集一个 delta，XOR 合成 parity
- 超时机制（10μs）避免阻塞：若某源无数据则跳过，生成 partial parity
- Partial parity 通过 parity queue 管理，后续积极转换为 full parity
- 并发 PUT 通过 hashmap 中的 placeholder 机制协调

**故障恢复**：
- Fail-stop 模型，不处理拜占庭故障
- 故障一致性：备份节点交换 SN 信息，确定 CSN，丢弃未提交 delta
- Degraded read：查找编码最少故障对象的 parity，递归深度不超过两层
- 节点修复：并行恢复主数据和 parity

---

## 五、实验结果

**实验环境**：CloudLab 16 台 c6525-100g 节点（AMD 7402P 24 核，128GB RAM，ConnectX-5 100Gb NIC），每节点运行 2 个 server，支持最大 k=6 (v=31)。

**基线系统**：Cocytus（inter-object, Reed-Solomon）、PQ（inter-object, P+Q/XOR）、Split（intra-object）、Repl（纯复制）。

| 实验 | 主要结果 |
|------|---------|
| 100%-GET（小对象 ≤256B） | Nostor 吞吐是 Split 的 3.92×(k=4) 和 6.06×(k=6) |
| 100%-PUT | Nostor 比 Cocytus/PQ 高 37.3%–56.6%；大对象(4KB)时 Split 因低带宽消耗反超 |
| YCSB-A（写密集） | Nostor 与 Repl 相当，显著优于其他纠删码方案 |
| 真实负载（Twitter Twemcache） | Nostor 比其他纠删码系统吞吐高 1.61×–2.60× |
| 节点修复时间 | Nostor 比 Split 快 16.4%，比 Cocytus 快 88.2% |
| Degraded read 延迟 | (k,p)=(6,3) 最坏情况下比 Cocytus 高 35.0%，比 Split 高 62.4% |
| 内存消耗 | 比 Repl 节省 18.7%–57.4%，与 Cocytus 相当 |
| 慢节点适应 | Nostor 仅毫秒级尾延迟上升；Cocytus 尾延迟飙升 48.2×，吞吐下降 98.9% |

---

## 六、批判性分析

1. **集群规模刚性约束被轻描淡写**：Nos 要求集群大小 v = k²-k+1，这意味着 k=4 时需要恰好 13 个节点，k=6 时需要 31 个节点。论文用 subcluster 来应对更大集群，但对 subcluster 间的负载均衡、跨 subcluster 故障、subcluster 重叠对性能的影响几乎没有讨论。实际部署中集群规模很少恰好匹配这些数值。

2. **评估规模有限**：仅使用 16 台物理机、每台跑 2 个 server 来模拟最大 31 节点的集群。真实数据中心有数千到数万节点，论文对大规模部署的可行性（如 SBIBD 矩阵计算、subcluster 管理开销）缺乏验证。

3. **Degraded read 延迟恶化在最坏情况下显著**：(6,3) 配置下递归 degraded read 延迟比 Split 高 62.4%。论文以"此类操作应该很少"轻描淡写，但在多节点故障期间，degraded read 可能是所有丢失主数据对象的唯一访问路径，此时的延迟恶化影响范围可能远大于论文暗示的。

4. **不支持 degraded write**：节点故障期间写操作被阻塞。对于写密集型工作负载，这意味着故障期间部分数据的写可用性降为零，这是一个严重的限制但论文仅一句话带过。

5. **基线比较的公平性存疑**：Cocytus 是论文作者从原始 Memcached+TCP/IP 实现中提取核心逻辑移植到自己的 RDMA 框架中的。虽然作者声称移植后性能更好，但这种"line-by-line porting"是否完整保留了原系统的所有优化（特别是内存分配策略）难以验证。

6. **k 值选择范围受限**：SBIBD 仅在 k = q+1（q 为素数幂）时存在，论文列出 k 可取 3,4,5,6,8,10,12,14，但不能取 7,9,11,13 等值。这限制了存储效率的调优粒度。

---

## 七、AI Infra / MLSys 视角

1. **KV Cache 存储的启发**：LLM 推理中的 KV cache 管理面临类似问题——需要在多个 GPU/节点间提供容错的高速内存存储。Nos 的无条带 XOR 编码 + 后台异步 parity 生成的思路，可以借鉴到分布式 KV cache（如 vLLM 的分布式 prefill/decode 架构）中，在几乎不增加关键路径延迟的情况下提供 GPU 故障容错。

2. **Checkpoint 加速**：分布式训练的 checkpoint 保存本质上也是将内存数据持久化并提供冗余。Nos 的去中心化编码方式（无需 MDS 协调）可以减少 checkpoint 写入的同步开销，特别适合大规模训练集群中节点频繁变动的场景。

3. **SBIBD 结构在通信拓扑中的应用**：SBIBD 的"任意两行最多一个公共列"性质，本质上定义了一种低冲突的通信模式。这可能对 AllReduce 等集合通信操作的调度有参考价值——在 k² 量级的节点中设计低冲突的 reduce 拓扑。

4. **可跟进的方向**：
   - 将 Nos 的思想应用到 GPU 显存的纠删码保护（参数服务器场景）
   - 探索 SBIBD 约束下的弹性扩缩容方案（节点增减时如何动态调整亲和矩阵）
   - 研究 partial parity 在 checkpoint 场景中的应用——允许不完整的 parity 来换取更快的 checkpoint 速度

---

## 八、总结

Nos 提出了一种大胆的思路——彻底抛弃纠删码中的 stripe 概念，转而使用 SBIBD 组合数学结构来指导数据放置，实现去中心化的 XOR 编码。基于 Nos 构建的 Nostor 在真实负载下取得了 1.61×–2.60× 的吞吐提升，同时保持与复制方案相当的延迟和显著更低的内存消耗。其主要局限在于集群规模的刚性约束（v=k²-k+1）、degraded read/write 性能恶化、以及对大 k 值的不兼容。适用于中等规模、以小对象为主的高速内存 KV 存储场景。
