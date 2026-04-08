# Getting the MOST out of your Storage Hierarchy with Mirror-Optimized Storage Tiering

**作者**：Kaiwei Tu, Kan Wu†, Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau（University of Wisconsin–Madison, †Google）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/tu
**源文件**：[[fast2026-tu.pdf]]

---

## 一、背景

存储层级结构一直是计算机系统设计的核心。传统上，快速小容量设备（如 SSD）作为缓存层叠加在慢速大容量设备（如 HDD）之上，两者性能差距巨大，层级关系清晰。然而，随着 Intel Optane NVM、低延迟 NVMe SSD、SATA SSD、NVMe over Fabrics 远程存储等新型设备的出现，"性能层"和"容量层"之间的性能差距大幅缩小且高度依赖工作负载。例如，16KB 读带宽下 Optane 与 PCIe 3.0 NVMe 的比值仅为 1.5:1，本地与远程 PCIe 4.0 NVMe 的比值仅为 1.25:1。在这种"扁平化"的存储层级中，传统的严格分层管理方法无法充分发挥设备潜力。

---

## 二、要解决的问题

现有多设备存储管理方案在现代异构存储层级中存在系统性不足：

1. **单副本方案（Striping、Tiering）的局限**：Striping 静态分配数据，受限于最慢设备；经典 Tiering（如 HeMem）将热数据放在性能层但不利用容量层带宽；即使是 state-of-the-art 的 Colloid，也完全依赖数据迁移来调整负载分布，导致在动态工作负载下收敛慢、写放大严重、设备寿命缩短。
2. **多副本方案（Mirroring、Caching）的局限**：完全 Mirroring 浪费一半容量；包含式 Caching（如 Orthus）虽能路由读请求，但同样浪费性能层容量，且无法有效处理写密集型工作负载（write-through 受限于慢设备写带宽，write-back 导致脏页无法路由）。
3. **存储层级特有挑战**：相比内存层级，存储设备容量更大（迁移数据量大、收敛时间长）、写带宽有限、存在读写干扰（后台活动影响前台性能）、设备耐久性受频繁迁移威胁。

核心矛盾：如何在最小化空间开销的同时，最大化异构存储设备的总带宽利用率，并快速适应动态工作负载？

---

## 三、洞察与设计

**关键洞察**：在经典 Tiering 系统中，只需对少量热数据进行跨设备镜像复制（而非全量镜像），就能获得 Mirroring 的负载均衡优势（通过路由而非迁移来调整负载分布），同时保持接近 Tiering 的空间效率。路由调整是即时的（改变概率即可），而数据迁移是昂贵且缓慢的。

基于此洞察，MOST 采用混合数据布局，将数据分为两类：

- **Mirrored class**：最热的数据，在两个设备上各存一份副本。读请求以概率 `offloadRatio` 路由到容量设备，其余路由到性能设备。写请求通过 subpage 粒度的 invalidation tracking 实现单副本更新，从而也能负载均衡。
- **Tiered class**：其余数据，单副本存储。温数据在性能设备，冷数据在容量设备。

**Optimizer 算法**：核心是一个简单的反馈控制循环——每 200ms 测量两个设备的端到端延迟，当性能设备延迟高于容量设备时增大 `offloadRatio`（向容量设备分流），反之减小，相等时停止迁移。这个机制不需要预知工作负载特征或设备性能参数。

**动态写分配**：新写入的数据以 `offloadRatio` 概率分配到容量设备，避免性能设备饱和时仍不断向其写入。

**Mirror-Class 迁移**：从 Tiered class 的性能设备上选最热 segment 复制到容量设备以加入 Mirrored class；当 Mirrored class 已满时与最冷 segment 交换。迁移方向由延迟差异动态控制，避免两个设备同时承受迁移写入。

---

## 四、实现细节

MOST 实现为 **Cerberus**，集成在 Meta 的 CacheLib 闪存缓存库中，作为存储管理层位于 Flash Cache Engine（SOC/LOC）和物理设备之间。

- **Segment 粒度**：2MB，每个 segment 维护 76 字节元数据（ID、双设备地址、invalid/location bitmap 指针、时钟、读写计数器、rewrite distance 计数器、标志位、存储类别、互斥锁）。
- **Subpage 管理**：Mirrored class 中每个 4KB subpage 跟踪 2 位元数据（invalid bit + location bit），三种状态：clean（双副本有效）、性能设备无效、容量设备无效。这使得 4KB 对齐的写请求可以像读一样进行路由负载均衡，无需更新整个 2MB segment。
- **选择性清理**：后台线程根据 rewrite distance（两次写入之间的平均读次数）选择性地清理脏副本。rewrite distance 小的 block 很快会被再次写入，清理无效。
- **尾延迟保护**：支持设置最大 `offloadRatio`，限制向容量设备分流的比例，防止容量设备的高尾延迟影响热数据访问。
- **参数设置**：θ=0.05（延迟相等判定阈值），ratioStep=0.02，tuning interval=200ms，Mirrored class 最大容量为总容量的 20%（实验表明通常只需镜像 1.8%–7% 的数据）。
- **代码规模**：Cerberus 在 CacheLib 基础上新增约 1.5k LOC，复用并扩展了 HeMem 的核心 Tiering 逻辑。同时在 CacheLib 中实现了 Orthus（6k LOC）、HeMem（7k LOC）、BATMAN（4k LOC）、Colloid（4k LOC）作为对比基线。

---

## 五、实验结果

**硬件平台**：40 核 Intel Xeon Gold 5218R，64GB DRAM，Ubuntu 20.04。两种存储层级配置：
- Optane（750GB）/ NVMe（1TB Samsung 960）
- NVMe / SATA（1TB Samsung 870）

### 静态工作负载（微基准测试）

| 工作负载 | Cerberus vs 最佳基线 |
|---------|---------------------|
| 随机只读 | 高负载下吞吐量显著优于所有方案，迁移量仅 50GB vs Colloid 134GB |
| 随机只写 | 大幅领先，Orthus 无法均衡写流量，Colloid 受迁移开销拖累 |
| 顺序写 | 动态分配新写入到容量设备，避免性能设备饱和 |
| Read Latest | 高效均衡，Colloid 迁移无效（迁移的 block 很快变冷） |

### 动态突发工作负载

| 指标 | Cerberus | Colloid++ |
|------|----------|-----------|
| 负载变化适应时间 | <10 秒 | >800 秒（100MB/s 迁移限制下） |
| 突发期吞吐提升 | 比 HeMem 高 1.53× | 比 HeMem 差（迁移干扰） |
| 迁移写入量（只读） | 87GB（镜像到容量层） | 282GB + 262GB（双向迁移） |
| 设备寿命影响 | 性能层 5.0 年 | Colloid 降至 4.1 年（-18%）；容量层从 3.0 年降至 129 天（-88%） |

### 生产缓存工作负载（Meta CacheBench）

| 层级 | 平均吞吐提升 vs Colloid | P99 延迟降低 |
|------|------------------------|-------------|
| Optane/NVMe | 1.24× | 平均 20%，P99 26% |
| NVMe/SATA | 1.17× | 平均 6.6%，P99 12% |

最突出的是 Workload D（kvcache-wc，大 value 写密集），Cerberus P99 GET 延迟 27.76ms vs Colloid++ 86.32ms（Optane/NVMe），降低 68%。

### YCSB

Cerberus 在多种 YCSB 工作负载下吞吐量最高提升 1.43×，P99 延迟降低 30%。

---

## 六、批判性分析

1. **Mirrored class 大小的自适应性存疑**：论文声称 20% 最大镜像容量"对所有工作负载足够"，但实验中工作负载的热点集中度都较高（20% hot set 占 90% 访问）。对于热点更分散的工作负载（如均匀分布），20% 镜像是否足够？论文未探讨这一边界条件。

2. **写密集场景下的 subpage 元数据一致性**：Subpage 级别的 invalid/location tracking 在高并发写下的正确性和性能开销未充分讨论。76 字节 segment 元数据中包含 SharedMutex，在 256 线程写密集场景下锁竞争如何？论文仅提到 CPU 开销增加 0–1.5%，但未分析锁争用对尾延迟的影响。

3. **实验层级配置有限**：只测试了两种两层配置（Optane/NVMe 和 NVMe/SATA），且都是本地设备。论文在 Table 1 中列出了 RDMA 远程设备，但未在实际实验中使用。Multi-tier 扩展（§5 Discussion）也仅作为 future work 提及。

4. **与 Colloid 的比较公平性**：论文为 Colloid 实现了三个版本（原版、Colloid+、Colloid++），其中 Colloid++ 修改了关键参数（θ=0.2, α=0.01）。这种"帮竞争对手调参"虽然看起来公平，但也意味着 Colloid 的参数敏感性可能被放大了——如果 Colloid 原始作者针对存储场景调参，结果可能不同。

5. **CacheLib 集成的代表性**：Cerberus 深度集成在 CacheLib 的 lookaside cache 模式中，所有实验都通过 CacheBench 运行。这意味着评估局限于缓存场景，对文件系统、数据库等通用存储场景的适用性未验证。

6. **Consistency 和 Crash Recovery 缺失**：论文坦承一致性保证留作 future work，但对于一个声称面向"现代存储层级"的系统，缺乏崩溃恢复机制是一个显著的实用性缺陷。

---

## 七、AI Infra / MLSys 视角

1. **KV Cache 分层管理的启发**：LLM 推理中的 KV Cache 面临类似的异构存储管理问题——GPU HBM（性能层）和 CPU DRAM/SSD（容量层）之间需要高效的数据放置和迁移。MOST 的"少量镜像 + 概率路由"思路可以迁移：对最热的 KV Cache 条目（高频访问的 attention head 或 sequence prefix）在 GPU 和 CPU 上各保留一份，根据 GPU 负载动态路由请求，而非昂贵的 page migration。

2. **Checkpoint 和模型参数分发**：分布式训练中的 checkpoint 写入和模型参数加载涉及大量顺序写和突发读。MOST 的动态写分配策略（根据设备负载概率性分配写入）可用于优化 checkpoint 到多层存储（NVMe SSD + 远程存储）的写入路径。

3. **Prefill/Decode 分离推理的存储优化**：在 prefill-decode disaggregation 架构中，prefill 阶段产生的 KV Cache 需要快速传输到 decode 节点。MOST 的 subpage 级脏页追踪和选择性清理可用于高效管理 KV Cache 在不同推理阶段之间的一致性。

4. **值得跟进的方向**：
   - 将 MOST 的反馈控制路由机制应用于 GPU 多级显存管理（HBM → DRAM → SSD），特别是在 vLLM 等系统中管理 paged KV Cache 的放置
   - 探索 MOST 在 CXL 异构内存池中的应用，CXL 内存的性能特征（延迟接近但带宽有差异）恰好是 MOST 设计目标的场景

---

## 八、总结

MOST 提出了一种将少量镜像与经典 Tiering 结合的存储管理方法，通过概率路由（而非数据迁移）实现跨设备负载均衡。其核心优势在于：适应动态工作负载的速度极快（<10 秒 vs 迁移方案的数百秒），显著减少设备写入量（降低 84%），且在各类静态和动态工作负载下均优于 Striping、Caching、Tiering 等方案。主要局限在于仅验证了两层两设备的缓存场景，一致性保证和多租户隔离尚未解决，且对非缓存存储场景的适用性有待验证。
