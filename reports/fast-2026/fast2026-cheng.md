# LESS is More for I/O-Efficient Repairs in Erasure-Coded Storage

**作者**：Keyun Cheng (The Chinese University of Hong Kong), Guodong Li (Shandong University), Xiaolu Li (Huazhong University of Science and Technology), Sihuang Hu (Shandong University), Patrick P. C. Lee (The Chinese University of Hong Kong)
**会议**：USENIX FAST 2026
**链接**：https://www.usenix.org/conference/fast26/presentation/cheng
**源文件**：[[fast2026-cheng.pdf]]

---

## 一、背景

Erasure coding 在现代分布式存储系统（HDFS、Ceph、Azure、Facebook f4 等）中广泛部署，以远低于副本的存储开销实现容错。然而，纠删码的核心痛点是修复代价高——修复单个失效块需要读取远超块本身大小的数据，带来显著的带宽和 I/O 开销。

近年来，网络技术飞速发展（InfiniBand、RDMA、CXL），网络带宽不再是主要瓶颈，I/O 效率成为修复性能的决定性因素。这促使研究者构建以 I/O 效率为"一等公民"的修复友好型纠删码。

---

## 二、要解决的问题

现有修复友好型纠删码存在多方面不足：

1. **Clay codes**（state-of-the-art I/O-optimal MSR codes）虽然最小化修复数据访问量，但需要指数级 sub-packetization（α = (n−k)^⌈n/(n−k)⌉），产生大量非连续 I/O seek，在 I/O 受限环境下性能反而退化。例如 (14,10) 配置下 Clay 的 α=256，平均 I/O seek 达 286 次。
2. **LRC**（如 Azure-LRC）减少修复 I/O，但牺牲了 MDS 性质，存储冗余更高。
3. **小 sub-packetization 的 MDS codes**（Hitchhiker、HashTag、ET）各有限制：Hitchhiker 仅改善数据块修复；HashTag 要求 α≥4 且为 n−k 的倍数；ET 限制了编码灵活性。
4. 所有现有方案都未能**同时**兼顾：减少修复 I/O、减少 I/O seek、在数据块和校验块间**均衡**地降低修复开销。

---

## 三、洞察与设计

**关键洞察**：修复性能同时取决于修复 I/O 量和 I/O seek 数，最小化修复 I/O 需要指数级 sub-packetization，由此引入的大量 I/O seek 会抵消数据访问量的减少。因此，用小而可配置的 sub-packetization 实现**接近最优**的修复 I/O，比追求理论最优但 seek 爆炸更有实际价值。

基于此洞察，LESS（Layered Extended Sub-Stripes）的核心设计：

- **分层扩展子条带（Layered Extended Sub-stripes）**：将 n 个块分为 α+1 个块组，每个块有 α 个 sub-block，共 nα 个 sub-block 被组织为 α+1 个扩展子条带 X_z。每个 X_z 是一个更长的 Vandermonde-based RS 编码条带，可容忍任意 n−k 个 sub-block 失效。
- **重叠结构**：每个 sub-block 恰好属于两个扩展子条带，最后一个子条带 X_{α+1} 由前 α 个子条带自动推导，无需显式编码。
- **单块修复**：失效块的所有 sub-block 必定在同一个扩展子条带内，因此只需从该子条带内读取部分 sub-block 即可修复，修复 I/O 严格低于传统 RS 的 kα。
- **可配置 α**：α 从 2 到 n−k 可配，平衡修复 I/O 与 I/O seek 的 trade-off。
- **MDS 性质保持**：通过精心选择 Galois Field 上的编码系数（基于 Vandermonde 矩阵），保证 LESS 的 MDS、general (n,k)、systematic 三大实用属性。

---

## 四、实现细节

- **编码系数选择**：使用 GF(2^w) 上的 primitive element p 的乘法生成 nα 个不同编码系数 v_{i,j} = p^{(h_i(α+1)+g_i)α+j}。通过暴力搜索验证可行的 primitive element（一次性离线操作）。对常用参数（n−k≤4, 2≤α≤4），GF(2^8) 或 GF(2^16) 即可满足。
- **编码流程**：依次编码前 α 个扩展子条带，计算 n−k 个校验块的 sub-block；X_{α+1} 自动满足 RS parity-check equation，无需额外编码。
- **单块修复**：从失效块所在扩展子条带 X_z 中，优先读取同组块的连续 sub-block（减少 seek），再补充其他块组的单个 sub-block。修复 I/O = k + (α−1)⌈n/(α+1)⌉ 或 k + (α−1)⌊n/(α+1)⌋。I/O seek 数固定为 k+α−1。
- **多块修复**：当 ⌊(n−k)/α⌋ ≥ 2 且失效块在同一块组时，可在一个扩展子条带内修复多块，否则退回传统修复。
- **实现规模**：基于 OpenEC（纠删码中间件）+ Hadoop 3.3.4 HDFS + Jerasure 编码库，新增约 8.7K LoC（C++）。支持 packet 级流水线编码。

---

## 五、实验结果

实验环境：15 台机器集群，quad-core i5-7500 CPU, 16GiB RAM, 7200RPM HDD, 10Gbps 以太网交换机（通过 Wondershaper 配置带宽）。默认配置：(n,k)=(14,10)，64MiB 块，256KiB packet，1Gbps 网络带宽。

### 数值分析

| 比较维度 | RS | Clay (α=256) | Hitchhiker (α=2) | HashTag (α=4) | ET (α=4) | LESS (α=4) |
|---|---|---|---|---|---|---|
| 平均修复 I/O (blocks) | 10.00 | 3.25 | 7.50 | 6.04 | 5.86 | **4.64** |
| 平均 I/O seeks | 10 | 286 | 10.86 | 12.14 | 14.29 | **13** |
| I/O seek Min/Max | 10/10 | 13/832 | 10/13 | 10/13 | 13/15 | **13/13** |

LESS (α=4) 相比 RS、Hitchhiker、HashTag、ET 分别减少修复 I/O 53.6%、38.1%、23.1%、20.7%，同时 I/O seek 仅 13 次（vs Clay 的 286 次）。

### 测试床实验

| 实验 | LESS (α=4) 相比基线的提升 |
|---|---|
| 单块修复时间 | vs RS −50.8%, vs Hitchhiker −35.9%, vs HashTag −21.5%, vs ET −21.5%, vs Clay −33.9% |
| 全节点恢复时间 | vs RS −48.3%, vs Hitchhiker −34.3%, vs HashTag −17.8%, vs ET −19.4%, vs Clay −36.6% |
| 编码吞吐量 (256KiB packet) | RS 2.8 GiB/s, LESS (α=4) 1.6 GiB/s（仍远超 I/O 瓶颈） |

### 配置敏感性

- **高网络带宽 (10Gbps)**：LESS (α=4) vs RS 减少 28.6%，vs Clay 减少 83.3%（Clay 在高带宽下 I/O seek 成为主要瓶颈）。
- **小 packet (128KiB)**：LESS (α=4) vs RS 减少 59.1%，vs Clay 减少 50.4%（Clay 处理大量 sub-block 的 I/O 开销显著）。
- **宽条带 (124,120)**：LESS (α=4) 修复 I/O 比 RS 减少 59.5%。

---

## 六、批判性分析

1. **编码吞吐量下降被低估**：LESS (α=4) 编码吞吐量仅为 RS 的 57%（1.6 vs 2.8 GiB/s），宽条带下降至 42%（1.1 vs 2.6 GiB/s）。论文以"编码开销相对 I/O 瓶颈有限"一笔带过，但在 SSD/NVMe 集群中 I/O 不再是瓶颈时，编码计算开销可能变得显著。论文始终使用 7200RPM HDD 评估，回避了存储介质升级后的性能表现。
2. **多块修复的受限场景**：LESS 的多块修复优势仅在失效块恰好属于同一块组时生效。论文称 (14,10,α=2) 下 28.6% 的两块失效组合可受益，意味着 71.4% 的情况仍退回传统修复。随着 α 增大（块组变多），每组块数更少，多块修复受益概率进一步下降，但论文未讨论这一 trade-off。
3. **均衡性的实际意义存疑**：论文强调 LESS 修复 I/O 在各块间差异至多 α−1 个 sub-block，但竞品 HashTag/ET 的不均衡主要体现在"数据块改善、校验块不改善"上。实际系统中校验块失效频率与数据块相当，但校验块修复通常不在关键路径上（不影响读性能），因此"均衡"的实际收益需要结合具体工作负载评估。
4. **实验基线选择**：Clay codes 在 (14,10) 下 α=256，这是一个极端配置。论文以此凸显 LESS 在 I/O seek 上的优势，但更公平的比较应包含 Clay 在较小 (n,k) 下的表现（如 (6,4) 时 α=4），那时 Clay 的 seek 开销可能并不那么极端。
5. **缺少降级读性能评估**：论文仅评估修复场景，未测试降级读（degraded read）性能，而这在生产系统中是同样重要的性能指标。

---

## 七、总结

LESS 提出了一种基于分层扩展子条带的纠删码构造方法，通过在 Vandermonde-based RS 码之上叠加多个扩展子条带，以小且可配置的 sub-packetization（α 低至 2）同时减少修复 I/O 和 I/O seek，并保证数据块与校验块间的均衡修复开销。LESS 保持了 RS 码的 MDS、general (n,k)、systematic 三大实用属性，适用于 HDD 主导、网络带宽充裕的分布式存储场景。主要局限在于编码吞吐量下降、多块修复受限于特定失效模式，且未在 SSD/NVMe 等低延迟存储介质上验证。
