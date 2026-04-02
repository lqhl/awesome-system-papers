# Okapi: Decoupling Data Striping and Redundancy Grouping in Cluster File Systems

**作者**：Sanjith Athlur*, Timothy Kim* (Carnegie Mellon University), Saurabh Kadekodi (Google), Francisco Maturana, Xavier Ramos (Carnegie Mellon University), Arif Merchant (Google), K. V. Rashmi, Gregory R. Ganger (Carnegie Mellon University)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/athlur
**源文件**：[[osdi25-athlur.pdf]]

---

## 一、背景

集群文件系统（如 HDFS、Ceph、Google Colossus）将单个文件的数据分散存储在多块磁盘上以提升 IO 效率，并使用纠删码（Erasure Code, EC）提供容错能力。在 k-of-n EC 方案中，k 个数据块编码生成 r = n-k 个校验块，任意 k 个块即可恢复全部数据。

随着超大规模存储集群的数据量持续增长，数据平均温度不断下降，推动了宽纠删码（n ≥ 20 甚至 50-150）的广泛采用以节省存储空间。同时，HDD 密度增长远快于 IO 性能增长，导致 IO-per-TB 持续恶化，磁盘寻道和带宽成为日益稀缺的资源。此外，EC 方案转换（如数据冷却后从窄码切宽码、磁盘故障率突变时紧急调整冗余度）已成为常态操作——Google 集群每天执行超过 10 万次 EC 转换。

---

## 二、要解决的问题

现有集群文件系统将 **数据条带化（data striping）** 和 **冗余分组（redundancy grouping）** 紧密耦合：文件的 EC 配置（k, r）同时决定了条带宽度和分组宽度，即 stripe width = group width = k。这种耦合造成两个根本性问题：

1. **性能与空间效率的冲突**：宽条带适合大顺序 IO 但对中小读请求 IO 效率差（过多磁盘寻道）；宽分组节省存储空间但增加重建开销。应用被迫在有限选项中做次优折衷——例如视频流服务需要窄条带（低尾延迟）+ 宽分组（高空间效率），但耦合设计不允许。Google 观察到大量文件使用 k > 50 的宽分组以节省空间，但随之承受严重的 IO 低效。

2. **EC 转换代价高昂**：改变分组方案必须连带重新条带化数据（read-re-encode-write, RRW），需要读写文件全部数据。在紧急场景下（如某型号磁盘故障率突增 4 倍，需将 k≈50 降至 k≈15），90K 磁盘的集群需要 784 PB 的转换 IO，即使全集群全速运行也需超过 1 天。

---

## 三、洞察与设计

**关键洞察**：数据条带化（控制 IO 性能）和冗余分组（控制可靠性与空间效率）本质上是两个独立的关注点，它们受不同因素驱动——条带宽度应匹配数据访问模式，而分组宽度应匹配可靠性和空间目标。Google 的生产数据表明，64%-94% 的文件在 150 天内始终使用相同大小的读请求，而同一时间段内 EC 方案可能变化多达 4 次。这意味着条带宽度应保持稳定以匹配固定的访问模式，而分组宽度需要独立灵活调整。

基于此洞察，Okapi 将条带化配置与冗余分组配置解耦，允许每个文件独立指定 stripe width 和 group width (k)。例如，一个文件可以使用 4-wide striping（优化 IO）同时使用 6-of-8 grouping（优化空间效率）。

核心设计方案：

- **元数据推断**：冗余分组由文件的连续数据块组成，通过简单的模运算从已有条带映射推断分组关系（block x 属于 stripe ⌈x/stripe_width⌉ 和 group ⌈x/group_width⌉），无需维护两套独立的元数据结构。
- **部分校验（Partial Parity）**：利用线性运算的结合律，将完整校验计算分解为 k 个独立的部分计算。写入时，每收到一个数据块即计算其部分校验并丢弃数据，仅缓存 r 个部分校验块（而非全部 k 个数据块），从而限制客户端内存开销。
- **降级读缓存**：大顺序读时，缓存已读数据以供后续降级重建使用，避免重复读取。
- **Re-grouping**：EC 转换时只需重新计算校验块，无需移动数据块，将转换 IO 减少约 50%。

---

## 四、实现细节

Okapi 在 HDFS 基础上实现，已开源（https://github.com/Thesys-lab/okapi）。

**元数据结构**：将传统的 Striped Block Group (SBG) 拆分为 data stripe 和 parity group 两个结构，均支持 O(1) 查找。每个块节省 8 bits（去掉 EC policy 指针，复用 replication 字段）。每个文件头用 1 字节记录 stripe width（最大 127）。

**写入路径**：支持任意 stripe width 和 EC 方案组合。部分校验存储在 r-wide 字节缓冲数组中，每个大小为 1 个 block（8 MB）。任意时刻客户端最多缓存 blocksize × r + cellsize × k 的数据。编码时仅乘以编码矩阵的相关子矩阵，计算量与完整编码等价。

**正常读**：与 HDFS 完全一致，仅访问 data stripe 元数据，不涉及 parity group。

**降级读**：推断失败块所属冗余分组，尝试复用已缓存的读数据以减少读放大。

**EC 转换**：计算新的分组映射 → 新校验组加入 BlocksMap → 通过 HDFS 已有的 EC 恢复流水线编码写入新校验 → 原子删除旧校验。转换期间新旧校验共存，保证数据始终受保护。

**代码规模**：修改 HDFS 现有数据结构和流水线，避免从零构建。

---

## 五、实验结果

实验集群：20 节点（1 Namenode + 19 Datanodes），每节点 Quad-Core AMD Opteron + 128 GB RAM + 1 TB 7200 RPM HDD，40 GbE 网络。Block size = 8 MB, cell size = 1 MB。

| 实验 | 关键结果 |
|------|---------|
| 读吞吐（6-of-9 分组） | Okapi 相比耦合 6-of-9 提升最高 80%（12-of-15 时高达 115%） |
| 磁盘寻道 | 减少最高 70%，峰值寻道减少 60% |
| 真实 workload（Google 读大小分布） | 吞吐提升 55%，总寻道减少 65%，端到端完成时间缩短 36% |
| EC 转换 IO | Re-grouping 比 RRW 减少约 50% IO；结合 Morph 可减少 70% |
| 紧急转换（Google 案例） | 427.68 PB vs 784.08 PB（减少 45%），完成时间从 21 天降至 12 天 |
| DARE 模拟（Backblaze 6 年） | 平均磁盘转换 IO 减少 38% |
| Namenode 元数据开销 | 总 Java heap 增加 < 1%（0.74%），每文件 BlocksMap +26%, INodeMap +22%（宽分组时更低） |
| 写吞吐 | 解耦对写性能无明显影响 |
| 客户端写内存 | 部分校验将缓冲从 150 MB（20-of-23 朴素方案）降至 ≤ 25 MB |
| 降级读放大 | 平均仅 3.23% 额外读放大（18-wide stripes），24 MB 中等请求最差约 33% |

---

## 六、批判性分析

1. **实验规模偏小**：20 节点 + 7200 RPM HDD 的学术集群与 Google 描述的数万台机器、百 EB 级集群差距巨大。论文多处引用 Google 生产数据来论证动机，但核心性能实验在小集群完成。宽 EC 方案（k=50+）的真实表现、网络竞争、跨 rack 延迟等在小规模下难以充分体现。

2. **workload 代表性有限**：主要评估读密集型场景，写入、混合读写、追加操作的影响讨论不足。Google 生产 workload 的 trace replay 仅使用了读大小分布，未包含时间相关性、并发模式等关键特征。

3. **stripe width 选择的实际可行性**：论文提出的 benchmark 流程（Sec 4.6）需要为每个应用采样 IO pattern → 生成测试文件 → replay → 选择最优宽度，这个过程本身的运维成本和自动化难度被轻描淡写。对于 IO 模式随时间变化的应用，论文仅简单表示"可回退为耦合模式"。

4. **降级读的 worst-case 被弱化**：论文强调平均读放大很小，但承认中等大小请求（如 24 MB, 3-wide stripes）的降级读性能可差 33%。论文用"降级读发生概率更低"来对冲，但在磁盘故障突增的紧急场景下（正是论文主推的 use case），降级读频率恰恰会大幅上升。

5. **与 SSD/混合存储架构的适用性未讨论**：论文完全聚焦于 HDD 场景，而现代集群越来越多地使用 SSD tier 或 NVMe。SSD 的寻道代价几乎为零，解耦带来的 IO 效率改善是否仍然显著值得探讨。

6. **缺少与 Ceph/Colossus 的真实对比**：论文声称 Okapi 的机制可直接迁移到其他 DFS（附录 A 讨论了 Ceph/Panasas），但未提供任何实际移植或评估。

---

## 七、AI Infra / MLSys 视角

1. **Checkpoint 存储优化**：大规模分布式训练的 checkpoint 是典型的"写一次、偶尔读、逐渐冷却"的数据。解耦设计允许 checkpoint 使用窄条带优化偶发的恢复读性能，同时使用宽分组节省存储空间。随着 checkpoint 冷却，可以低成本地转换到更宽的分组方案。

2. **训练数据读取**：数据并行训练中，每个 worker 读取不同数据分片，读请求大小通常固定（batch size × sample size）。Okapi 的按访问模式定制 stripe width 的思路可以显著提升训练数据的 IO 吞吐，特别是在 HDD 作为大容量数据湖的场景下。

3. **模型权重/KV cache 的分布式存储**：推理场景中模型权重的加载和 KV cache 的 offload 有固定的访问模式，解耦设计可以为这些场景分别优化。

4. **值得跟进的方向**：
   - 将解耦思想扩展到 SSD + HDD 混合存储分层，研究 SSD 上解耦的收益曲线
   - 结合 workload prediction（如训练 pipeline 的可预测性）自动选择最优 stripe width
   - 在 object store（如 S3）层面探索类似解耦，这对 AI 训练数据管理有直接意义

---

## 八、总结

Okapi 揭示并解决了集群文件系统中数据条带化与冗余分组的不必要耦合问题。通过将两者解耦，Okapi 允许独立优化 IO 性能（通过 stripe width 匹配访问模式）和数据可靠性/空间效率（通过 group width），同时大幅降低 EC 转换的 IO 代价。设计上通过元数据推断、部分校验和降级读缓存三个机制控制了解耦引入的额外开销，并在 HDFS 上实现了原型验证。核心局限在于实验规模偏小、仅聚焦 HDD 场景、且 stripe width 的运维选择流程在生产中的可行性有待验证。
