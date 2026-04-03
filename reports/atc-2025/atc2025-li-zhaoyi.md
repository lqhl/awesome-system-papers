# Accelerating Distributed Graph Learning by Using Collaborative In-Network Multicast and Aggregation

**作者**：Zhaoyi Li (Central South University, NTU), Jiawei Huang, Yijun Li, Jingling Liu (Central South University), Junxue Zhang, Kai Chen (HKUST), Hui Li, Xiaojun Zhu, Shengwen Zhou, Jing Shao, Xiaojuan Lu, Qichen Su, Jianxin Wang (Central South University), Chee Wei Tan (NTU), Yong Cui (Tsinghua University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/li-zhaoyi
**源文件**：[[atc2025-li-zhaoyi.pdf]]

---

## 一、背景

图神经网络（GNN）广泛应用于推荐系统、药物发现、公共健康监测、知识图谱等任务。随着真实世界图数据规模急剧增长（如 ByteDance 的图数据达 2 billion 顶点、2 trillion 边、100TB），单 GPU 训练已无法满足内存需求，分布式 GNN 训练成为必然选择。

分布式全图训练（full-graph training）相比 mini-batch 训练具有更高的收敛精度，但在图传播（graph propagation）阶段会产生大量跨 worker 通信。具体来说，每个顶点的特征需要 one-to-many multicast 到其远程邻居，同时需要 many-to-one aggregation 接收邻居特征，这两种模式分别导致大量冗余流量和严重的带宽竞争，通信开销可占 epoch 时间的 80%。

可编程交换机（如 Intel Tofino）提供了将 multicast 和 aggregation 操作卸载到网络设备的可能性，理论上可将通信量从 O(EM²) 降低到 O(EM)。然而，GNN 的图数据存在复杂依赖关系，且交换机内存有限（10-100MB），直接应用 in-network 技术面临严峻挑战。

---

## 二、要解决的问题

1. **Host-based multicast/aggregation 的冗余流量和带宽瓶颈**：在 Reddit 数据集 128 个 worker 的场景下，流量是边界顶点大小的 16 倍，即平均每个顶点需要 1-to-16 复制发送，16-to-1 带宽竞争接收。

2. **Graph-agnostic multicast 顺序导致链路利用率低和队列积压**：Strawman 方案随机发送顶点，部分顶点上传后长时间无法完成聚合（链路空闲），另一些顶点上传后同时触发大量聚合结果（队列爆发）。从 0ms 到 1ms，队列长度从 0 暴增到 1000MB。

3. **图数据的复杂依赖导致 aggregator overflow**：边界顶点间近 99% 存在依赖关系，Reddit 数据集 128 worker 需要约 500MB aggregator 空间，而交换机通常只有 10-100MB 内存。在 100MB 限制下，聚合吞吐量仅为总吞吐量的约 10%，大量流量只能回退到 host 端聚合。

---

## 三、洞察与设计

**关键洞察**：GNN 图传播中顶点的度数分布高度偏斜（skewed）——在 Reddit 数据集 32 worker 下，20% 的顶点占据 80% 的邻居总数。这种偏斜特性意味着：(1) 通过感知图结构调整 multicast 发送顺序，优先发送高度数顶点，可以实现更平滑的聚合流水线、避免突发流量；(2) 大规模连通的边界子图可以通过多级分区拆解为小块，分批进行 in-network aggregation，从而在有限交换机内存约束下避免 aggregator overflow。

基于此洞察，SwitchGNN 的设计包含四个核心组件：

1. **Graph-Aware Multicast Reordering (GAMR)**：使用基于优先级的广度优先搜索（Priority-based BFS），从随机顶点出发，优先发送度数更高的顶点。高度数顶点先发送后，后续小度数顶点逐步完成聚合，避免瞬时大量聚合结果导致的队列积压。形式化分析表明，在星型图中 PB 策略的执行时间为 n，而随机顺序平均为 (3n-1)/2。

2. **Multi-level Graph Partitioning**：在 METIS 对全图分区的基础上，进一步将连通的边界顶点递归分区为多个独立 block，每个 block 大小不超过交换机 aggregator 容量。切断的边产生的新 block 继续递归分区，直到所有 block 都满足内存约束。为保证图传播正确性，cut edge 对应的特征仍会传输。

3. **Reliability and Congestion Control**：使用双 bitmap 跟踪每个顶点的发送确认状态和邻居接收状态；超时机制处理丢包，从其他 worker pull 未聚合的特征并标记为 bypass（不再参与 switch 聚合）；基于 ECN 的拥塞控制（类似 DCQCN）。

4. **Collaborative In-Network Multicast and Aggregation**：Worker 按预定义的 block 顺序和顶点顺序发送特征到交换机，交换机根据顶点 ID 查表确定目标 aggregator，逐一累加后将聚合结果发回对应 worker。所有 worker 完成当前 block 后才进入下一个 block。

---

## 四、实现细节

- **Host 端**：基于 DGL 框架，用 DPDK 替换通信层。自定义包头（IP header 之后）包含 32-bit Src_id、32-bit Dst_id、16-bit Block_id、16-bit Count、1-bit Is_ACK、1-bit Is_Fetch、1-bit ECN、1-bit Resend 字段。
- **Switch 端**：P4 编程实现，使用 Intel Tofino 交换机。每个 aggregator 分配 128 字节。通过 table 存储顶点 ID 到 aggregator index 的映射。由于 Tofino 限制每个 packet 只能访问 register 一次，通过 loopback 到 ingress pipeline 实现对多个 aggregator 的顺序写入。
- **Multi-level aggregation**：支持多交换机场景（如 leaf-spine），level-1 交换机做部分聚合，结果转发到 level-2 交换机做最终聚合。
- **预处理复杂度**：METIS 为 O(|E|+|V|)，multicast reordering 为 O(|E|+|V|log|V|)，支持 Par-METIS 并行化。
- GPU 内通信仍使用 NVLink/PCIe，仅跨 host/rack 通信使用 in-network aggregation。

---

## 五、实验结果

### Testbed 配置

| 项目 | 配置 |
|------|------|
| 拓扑 | Star topology，1 switch + 8 GPU servers |
| 链路 | 100 Gbps |
| 交换机 | Intel Wedge 100BF-32X（10MB memory） |
| GPU | RTX 3090 + CUDA 11.2 |
| NIC | 100GbE Mellanox CX5 |
| 数据集 | Ogbn-products (2.4M vertices, 62M edges), Yelp (0.72M, 7M), Reddit (0.23M, 114M) |

### 主要结果

| 指标 | SwitchGNN vs BNS-GCN | SwitchGNN vs G3 |
|------|------|------|
| Testbed 训练吞吐量提升 | 最高 54% | 最高 24% |
| NS3 Epoch time 降低（Reddit 128 workers） | 最高 74% | 最高 65% |
| 模型精度 | 无损失 | 无损失 |

### NS3 大规模仿真（128 workers）

- 在 Reddit 数据集上，SwitchGNN 相比 strawman 方案减少 epoch time 83%
- 100MB switch memory 下，流量比 full-graph 方案减少 81%（Reddit 128 workers）
- 10MB memory 下流量减少有限（23%），100MB 下效果显著
- GAMR 显著提升聚合吞吐量并降低队列积压
- Leaf-spine 拓扑下同样有效，通过分层聚合减少跨 rack 流量
- 拥塞控制在背景流量负载增大时有效维持低 epoch time

---

## 六、批判性分析

1. **Testbed 规模过小**：核心实验仅 8 个 worker + 1 台交换机（10MB memory），而论文的主要卖点是大规模场景。NS3 仿真补充了 128 worker 实验，但仿真与真实系统之间存在差距，尤其是在 packet processing latency、loopback overhead 等方面未充分验证。

2. **Loopback 开销被低估**：由于 Tofino 的单次 register 访问限制，每个 packet 需要 loopback 多次才能写入所有目标 aggregator。对于高度数顶点（如度数 16），一个 packet 需要 loopback 16 次，这会占用大量交换机 pipeline 带宽，但论文几乎未量化这一开销。

3. **Block 同步的 straggler 问题**：所有 worker 必须完成当前 block 才能进入下一个 block，这是典型的 barrier synchronization。论文承认了吞吐量波动，但未分析在异构计算环境或 worker 负载不均衡时的影响。

4. **基线选择有局限**：仅对比 BNS-GCN 和 G3，均为 2022-2023 年的工作。缺少与 HongTu（2023 SIGMOD）等更新的全图训练系统的对比。G3 本身已是相当强的基线，24% 的提升在 testbed 上并非压倒性优势。

5. **预处理开销未计入**：Multi-level graph partitioning 和 multicast reordering 需要在训练前完成，但论文未报告预处理时间。对于需要频繁重分区的动态图场景，这一开销可能不可忽略。

6. **10MB 真实交换机内存下效果有限**：Testbed 使用的 Wedge 100BF-32X 只有 10MB memory，而论文大量仿真结果基于 100MB 假设。在 10MB 下 Reddit 数据集流量仅减少 23%，说明该方法在当前硬件约束下的实际收益可能远低于论文标题暗示的水平。

---

## 七、AI Infra / MLSys 视角

1. **In-network computing 对 AI 通信的启发**：SwitchGNN 的核心思路——利用可编程交换机卸载 multicast 和 aggregation——与分布式 DNN 训练中的梯度聚合（如 ATP、SwitchML）一脉相承。其图感知的调度策略可以启发 MoE 模型中 all-to-all 通信的优化，MoE 的 expert routing 同样存在 skewed 分布和 many-to-one 瓶颈。

2. **Multi-level partitioning 对 KV Cache 管理的借鉴**：将大规模连通数据拆分为满足内存约束的独立 block 并分批处理的思路，可以迁移到 LLM 推理中的 KV cache 管理，特别是在跨节点 KV cache 共享（如 Mooncake、MemServe）场景下处理内存碎片和依赖关系。

3. **值得关注的局限**：该方法强依赖静态图分区预处理，不适用于动态图或 graph structure 随训练变化的场景。对于 GNN-based recommendation system 的在线推理场景，实时图更新与静态分区之间的矛盾是一个有价值的研究方向。

4. **可能的延伸方向**：
   - 将 graph-aware scheduling 思想应用到 LLM 推理中的 prefill/decode 调度，特别是 chunked prefill 场景下的 attention 计算依赖管理
   - 探索 CXL 互联场景下的 in-network aggregation，CXL switch 具有更大的内存容量，可能缓解 aggregator overflow 问题

---

## 八、总结

SwitchGNN 提出了图感知的 in-network multicast 和 aggregation 方案来加速分布式全图 GNN 训练。通过 priority-based BFS 优化 multicast 发送顺序、multi-level graph partitioning 避免 aggregator overflow，在 NS3 仿真 128 worker 场景下将 epoch time 减少最高 74%，且不损失模型精度。该系统适用于大规模稠密图的全图 GNN 训练场景，主要局限在于强依赖静态图分区预处理、交换机内存约束下收益有限（10MB 下仅 23% 流量减少）、以及 block 同步的 straggler 风险。
