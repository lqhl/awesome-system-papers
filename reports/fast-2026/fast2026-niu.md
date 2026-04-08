# DRBoost: Boosting Degraded Read Performance in MSR-Coded Storage Clusters

**作者**：Xiao Niu, Guangyan Zhang*, Zhiyue Li, Sijie Cai（清华大学）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/niu
**源文件**：[[fast2026-niu.pdf]]

---

## 一、背景

纠删码（Erasure Coding）是对象存储系统中广泛使用的容错技术，相比副本方式大幅降低存储开销。然而，当存储节点不可用时（永久故障、临时不可用、计划维护等），需要通过降级读（Degraded Read）从其他节点重建数据，这涉及额外的读放大和解码计算开销。

Minimum Storage Regenerating（MSR）码是一类理论最优的向量纠删码，在相同存储开销下实现最优修复带宽，是构建高效可靠存储系统的理想选择。当前最先进的 MSR 码实现是 Clay（Coupled-Layer）码。然而，MSR 码的向量化结构导致 sub-packetization level 随条带宽度指数增长，加上大 sub-chunk 对存储设备带宽利用的需求，最终导致 chunk 尺寸极大（如 (20,16) Clay 码推荐 chunk 大小为 16MB–256MB）。

---

## 二、要解决的问题

MSR 码的大 chunk 尺寸与实际对象尺寸严重不匹配——阿里云 90% 以上对象小于 10MB，IBM 和 Facebook 的分布类似。现有 MSR 编码系统仅支持全 chunk 重建，导致降级读时严重的 I/O 放大。具体而言：

1. **交织 codeword 布局**：MSR 码的 hop-and-couple 方法使对象分散到条带内所有 codeword，无法像标量码那样隔离单个 codeword 进行部分重建。
2. **非对称修复模式**：修复不同节点所需的 helper sub-chunk 位置不同，难以设计对所有失败场景都友好的对象布局。
3. **碎片化访问模式**：每个 chunk 内只有部分 sub-chunk 参与修复，导致不可避免的碎片化随机 I/O。

实验表明，降级读延迟可比正常读高出 1–2 个数量级，严重影响服务质量。

---

## 三、洞察与设计

**关键洞察**：MSR 码的 sub-stripe（由一层 uncoupled sub-chunk 构成的标量 MDS 条带）具有独立容错能力，且在部分 chunk 重建过程中存在两种数据重用机会——(a) 同一 sub-stripe 内多个丢失 sub-chunk 可共享 helper 数据（sub-stripe reuse），(b) 被请求对象的健康部分本身可作为 helper 数据（request reuse）。利用这两种重用，可以大幅减少修复带宽。

基于此洞察，DRBoost 将对象布局分离为两层：

- **Coding Layout**（编码布局）：将对象空间映射到编码空间，面向 MSR 码的修复优化。引入 **basic layout unit**（基本布局单元）概念，将同一 sub-stripe 内的 major sub-chunk 分组，使对象天然对齐 sub-stripe 以最大化数据重用。在此之上构建分层结构：balanced layout unit（确保数据均匀分布到各节点）和 reuse-optimal layout unit（确保重建时无需额外 helper 数据）。
- **Storage Layout**（存储布局）：将对象空间映射到存储空间，面向存储系统的顺序访问需求。通过重排 sub-chunk，使同一对象在每个节点上的数据连续存储，消除碎片化。

两层布局通过确定性 mapping table 关联，正常读直接使用 storage layout（无需翻译），仅在降级读时触发 coding-storage 地址转换。

---

## 四、实现细节

- **部分 chunk 重建算法**：三步流程——(1) 统计目标对象在各 sub-stripe 中的丢失 sub-chunk 数；(2) 优先对多个丢失 sub-chunk 所在的 sub-stripe 执行 sub-stripe reuse；(3) 对剩余丢失 sub-chunk 选择 request reuse 度最高的 sub-stripe 重建。优先 sub-stripe reuse 的原因是其确定性更强、计算开销更低。
- **分层布局分配**（Algorithm 1）：通过 digit-wise modulo addition 生成 basic layout unit 的分配序列，确保连续分配的单元自然形成 balanced/reuse-optimal layout unit。
- **碎片消除**：将同一 basic layout unit 的 sub-chunk 在存储设备上连续放置，并按分配序列保持顺序，使对象在每个节点上无碎片存储。
- **Mapping Table**：确定性映射，所有相同 (n,k) 配置的条带共享一张表。(20,16) Clay 码的映射表仅需 128KB 内存。
- **两阶段写入**：先将对象写入副本池，再聚合编码进入纠删码池，避免大条带的写放大。
- **原型实现**：C++ 实现，基于 Intel ISA-L 库进行编解码。集成到 Ceph，修改了 Librados API（支持部分条带读写）、EC Module（支持 sub-chunk 级位置信息）和 EC Backend（基于 slice map 精确读取）。

---

## 五、实验结果

**测试环境**：阿里云 40 台 ecs.g8i.xlarge 实例（4 vCPU, 16GB RAM），30 存储节点（100GB ESSD），10 客户端节点，4Gbps 网络。默认 (20,16) Clay 码，sub-chunk 16KB。

| 指标 | 合成负载 | 真实负载 |
|------|---------|---------|
| 全量读平均延迟降低 | 2.19×–60.7× | 1.28×–20.2× |
| 全量读 P99 延迟降低 | 4.65×–212× | 1.15×–66.1× |
| 降级读平均延迟降低 | 11.7×–213× | 2.45×–89.2× |
| 平均放大比降低 | 16.0×–156.9× | 24.6×–557× |

**真实 trace**：Ali（阿里云）、IBM、FB Photo、FB Video 四种负载。对小对象为主的 FB Photo trace 效果最显著。

**各技术贡献**：
- 部分 chunk 重建：最高 72.3× 加速（小对象）
- Coding Layout：2.95×–4.90× 加速（全尺寸对象）
- Storage Layout：最高 1.28× 加速（消除碎片）
- 正常读性能不受影响（storage layout 消除了 coding layout 引入的碎片）

**与标量码对比**：DRBoost 使 MSR 码降级读延迟比 RS 码低 1.62×–3.12×，比 LRC 低 1.52×–1.80×（除 4KB 极小对象外）。

**参数敏感性**：k 增大时 DRBoost 优势更明显；m 减小时同理；sub-chunk 越小降级读越快但全量恢复越慢，需权衡。HDD 场景下 storage layout 的碎片消除尤为关键。

---

## 六、批判性分析

1. **实验网络带宽偏低**：测试环境使用 4Gbps 网络，远低于生产环境常见的 25–100Gbps。在高带宽网络下，网络不再是瓶颈，I/O 设备性能和计算开销的相对权重会改变，DRBoost 的收益分布可能与论文展示的不同。

2. **降级读占比仅 3%**：论文承认降级读仅占约 3% 的请求，全量读延迟的改善主要来自消除少数降级读的长尾。在实际部署中，若降级读比例更低或更高，整体收益需要重新评估。

3. **EC Module 未完全集成**：部分 chunk 重建逻辑运行在原型系统中而非 Ceph 内部，"Ceph 仅用于数据访问"。这意味着论文测量的延迟可能未完全反映生产环境中 Ceph 内部处理开销，且实际部署需要大量额外工程工作。

4. **两阶段写入的代价被轻描淡写**：聚合对象到大条带需要先写副本池再编码，这引入写放大和额外延迟，论文未量化这一开销。对写密集型负载，这可能是显著的劣势。

5. **4KB 对象场景的退化**：当对象小于 sub-chunk（16KB）时，DRBoost 仍需重建整个 sub-chunk，性能退化到接近 LRC 水平。论文将此归因于"实现简化"，但对阿里云这种 90% 对象小于 10MB 且大量 4KB 小对象的场景，这是一个实质性限制。

6. **确定性布局的局限性**：论文在 Discussion 中承认自适应方法（动态选择对象聚合、定制每条带的 coding layout）未被探索，但确定性策略在对象大小分布不均时可能导致次优的数据重用率。

---

## 七、AI Infra / MLSys 视角

1. **Checkpoint 存储优化**：大规模分布式训练中，checkpoint 是典型的大对象写入 + 偶尔读取场景。MSR 码的低修复带宽特性天然适合 checkpoint 存储，而 DRBoost 的部分 chunk 重建能力在需要恢复单个 tensor shard 时尤为有用——无需重建整个 chunk 即可读取特定模型参数。

2. **KV Cache 离线存储**：推理系统中 KV Cache offloading 到远端存储时，cache block 的大小通常远小于 MSR 码的 chunk 大小。DRBoost 的 basic layout unit 粒度（与标量码的条带大小对齐）可以有效降低 KV Cache 降级读的放大比，值得在 KV Cache 分层存储中探索。

3. **Coding-Storage 分离思想的借鉴**：DRBoost 将编码布局与存储布局解耦的设计哲学，可以迁移到 AI 训练中的 data pipeline。例如在分布式数据加载中，数据的逻辑分片（coding layout）和物理存储位置（storage layout）分离，可以在节点故障时快速进行部分重建而不影响训练吞吐。

4. **可跟进方向**：(a) 将 DRBoost 的部分重建思想应用于 AI 训练的纠删码 checkpoint 系统（如 CheckFreq、DeepFreeze）；(b) 探索自适应 coding layout 在非均匀对象分布（如混合 embedding table + dense tensor）下的优化空间。

---

## 八、总结

DRBoost 针对 MSR 编码存储系统中降级读 I/O 放大严重的问题，提出了部分 chunk 重建算法、重建友好的编码布局和无碎片存储布局三项技术。通过利用 sub-stripe 内的数据重用和编码-存储地址分离，DRBoost 将降级读延迟降低 1–2 个数量级，同时不影响正常读性能。该方案适用于采用 MSR 码的大规模对象存储系统，使 MSR 码从冷存储扩展到延迟敏感的温数据场景。主要局限在于对极小对象（< sub-chunk 大小）的优化不足，以及确定性布局策略在异构对象分布下的次优性。
