# How Soon is Now? Preloading Images for Virtual Disks with ThinkAhead

**作者**：Xinqi Chen (上海交通大学), Yu Zhang (阿里巴巴), Erci Xu* (上海交通大学), Changhong Wang, Jifei Yi, Qiuping Wang, Shizhuo Sun, Zhongyu Wang (阿里巴巴), Haonan Wu (上海交通大学), Junping Wu, Hailin Peng, Rong Liu, Yinhu Wang, Jiaji Zhu, Jiesheng Wu (阿里巴巴), Guangtao Xue (上海交通大学), Patrick P. C. Lee (香港中文大学)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/chen
**源文件**：[[fast2026-chen.pdf]]

---

## 一、背景

Elastic Block Storage (EBS) 是现代云计算的基石，为虚拟机和容器提供高性能、可扩展的块存储虚拟磁盘 (VD)。在 EBS 中，用户可以将 VD 的快照保存为镜像 (image)，并从镜像创建新的 VD。由于镜像通常存储在远端对象存储服务 (OSS) 中，VD 创建需要从 OSS 拉取数据块。

当前业界普遍采用 lazy loading 方式——按需拉取数据块，以实现近乎即时的 VD 启动。然而，首次访问尚未加载的数据块时会产生显著的等待延迟（尾延迟可达数秒），这在容器化环境中（VD 频繁创建和销毁）尤为严重。在阿里巴巴 EBS 的生产环境中，每天有数百万次 VD 创建事件和约 70 万次 slow I/O 事件。

---

## 二、要解决的问题

1. **Lazy loading 导致的 slow I/O 占比极高**：对阿里巴巴 EBS 约 16 万次 VD 创建事件的 trace 分析表明，lazy loading 贡献了 39.35% 的 slow I/O（端到端延迟超过 1s），是 EBS 软件栈中最主要的 slow I/O 来源，P99 尾延迟高达 7s。

2. **现有替代方案各有局限**：
   - **缓存方案**：超过 80% 的系统 VD 来自用户自定义镜像，数据异构性高导致缓存命中率低；VD 分布在数十个集群中，缓存部署困难。
   - **P2P 协作**：依赖镜像热度，时空动态性使 P2P 不可靠；对等节点缺乏信任，存在安全风险。
   - **新镜像抽象 (FlacIO)**：大幅修改 I/O 路径和镜像格式，不适合大规模生产部署；且针对容器层级镜像设计，不适用于二进制 VD 镜像。

3. **Preloading 面临的技术挑战**：
   - I/O trace 因网络不稳定和内核 I/O 重排而存在不一致性和不完整性
   - OSS 网络带宽因共享服务（如 LLM 训练）而剧烈波动（2MB/s ~ 700MB/s）
   - Zero-shot 场景——56.9% 的用户仅用单一镜像创建一个 VD，缺少历史 trace

---

## 三、洞察与设计

**关键洞察**：从同一镜像创建的 VD 在启动阶段展现出极高的访问模式相似性（84.8% 的公共镜像和 72.7% 的用户自定义镜像 cosine similarity > 0.9），且初始加载阶段仅访问 VD 中很小比例的 LBA 空间（公共镜像 2.67%，用户自定义镜像 4.55%），加上阿里巴巴大规模生产环境提供了丰富的历史 trace，这使得基于数据驱动的预加载策略成为可能。

基于此洞察，ThinkAhead 采用三个核心组件：

1. **数据集预处理**（应对 trace 变异性）：
   - 分析每个镜像所有 trace sequence 中数据块访问计数的概率密度分布，识别 spike 并据此划分 category
   - 截断 PDF 两端各 2.5% 的异常数据，过滤 outlier
   - 在每个 category 内，使用 Pearson 相关系数 (PCC) 计算 trace 间的相似度，聚类形成 group，为每个 group 选取 centroid

2. **基于评分的数据块选择**（应对动态带宽）：
   - 为每个数据块计算综合评分 S(b_i) = α × ac_i + β × (t_max - t_avg,i)/t_max + (1-α-β) × (t_max - t_min,i)/t_max，综合考虑访问次数、平均访问时间和最早访问时间
   - 使用遗传算法离线搜索不同带宽区间下的最优权重 α 和 β
   - 运行时通过 centroid feature switching 模块监测实际访问模式，在检测到 I/O 重排时动态切换到匹配的 group 参数

3. **Zero-shot 预测**（应对无历史数据场景）：
   - 基于 Jaccard Index 计算镜像间相似度
   - 三层选择策略：同镜像族 → 同用户 → 相同元数据配置
   - 复用相似镜像的预训练参数以节省计算开销

---

## 四、实现细节

- 总代码量约 7,000 行：预加载策略约 1,000 行 Python，完整预加载系统约 6,000 行 C++
- **中央系统**（部署在每个 EBS 集群）：
  - 在每个 block server 部署 tracing 模块，收集 VD 创建前 6 分钟的 I/O trace（95% 的 slow I/O 发生在此时段）
  - 三级优先队列管理数据块下载：missed block queue（最高优先级，用户请求但未预加载的块）→ preload block queue（预测即将访问的块）→ left block queue（剩余块）
- **分析系统**：执行数据预处理、score-based block selection 和 zero-shot prediction
- 固定 2 MiB 数据块大小（cross-block read rate 仅 2.1%，平衡了网络效率和访问粒度）
- 遗传算法训练以天为粒度执行，训练参数可跨集群复用
- 推理延迟在 5ms 以内，运行时开销可忽略

---

## 五、实验结果

**实验设置**：
- 高保真模拟器：64 核 Intel Xeon E5-2682 2.5GHz CPU + 128 GiB DRAM，重放生产 trace
- 生产集群：20 个 block node（Intel Xeon Silver 4114 2.2GHz, 128 GiB DRAM, 25Gbps NIC），完整阿里巴巴 EBS 栈 + 远端 OSS

**核心结果**：

| 指标 | ThinkAhead vs. Lazyload | ThinkAhead vs. History-based |
|------|------------------------|------------------------------|
| Hit rate（公共镜像） | 最高提升 7.27× | 最高提升 3.40× |
| Hit rate（用户自定义镜像） | 最高提升 2.64× | 最高提升 1.25× |
| P50 等待延迟 | 5MB/s 时即可达到 0 | HB 在 5MB/s 时仍有 4.6s |
| P99 等待延迟 | 低带宽下改善最高 79.8% | 高带宽下持平 |

**充足训练数据场景**（≥20 条历史 trace）：hit rate 最高提升 3.83×（vs. Lazyload）、1.89×（vs. HB）；P50 等待延迟比 HB 低 65.3%。

**Zero-shot 场景**：hit rate 仅比 HB 低 0.8%；P50 等待延迟比 HB 优 20.2%；P99 等待延迟比 Lazyload 改善 98.7%。

**真实网络条件模拟**：两个生产集群上 hit rate 分别提升 4.27× 和 3.44×（vs. Lazyload）。

**端到端集群实验**：

| 指标 | Lazyload | ThinkAhead | 改善 |
|------|----------|------------|------|
| P50 等待延迟 | 204ms | — | 3.20× |
| P99 等待延迟 | 269ms | — | 1.35× |
| 最大等待延迟 | 279ms | — | 1.46× |
| 冷启动延迟 | 23.4s | — | 1.46× |
| Slow I/O 数量 | 396 | — | 5.35× |

**开销**：训练约 2 小时（天级粒度，参数可跨集群复用）；推理 < 5ms。

---

## 六、批判性分析

1. **端到端改善幅度与微基准差距较大**：模拟器中 hit rate 提升可达 7.27×，但端到端集群实验中 P50 等待延迟仅改善 3.20×，P99 仅 1.35×，最大延迟仅 1.46×。论文将此归因于"有限带宽约束下仍可能遇到长 I/O"，但对此未做深入分析。端到端实验的规模（仅 20 个 block node）也远小于生产环境（数百个集群），外推能力存疑。

2. **训练开销被轻描淡写**：遗传算法训练需 2+ 小时，是所有基线中最高的（其他基线最多 26s）。论文以"天级粒度训练、参数可跨集群复用"辩护，但未讨论新镜像上线时的冷启动训练延迟，以及镜像更新频繁时的参数陈旧问题。

3. **Accuracy 指标的反直觉表现**：ThinkAhead 平均 accuracy 为 44.1%，低于 HB 13%，意味着超过一半的预加载块未被实际访问。论文声称"高 accuracy 不一定意味着低延迟"，这在定义上是正确的，但也说明 ThinkAhead 在带宽利用效率上存在浪费，在带宽极度紧张的场景下可能适得其反。

4. **评分公式设计缺乏理论基础**：S(b_i) 的三个权重项（访问计数、平均时间、最小时间）的组合形式是线性加权，遗传算法仅搜索权重空间。论文未讨论为何选择线性组合而非其他形式，也未验证评分函数的 sensitivity。

5. **Zero-shot 场景评估不够严格**：zero-shot 的三层选择策略依赖元数据相似性，但论文仅在 Meta3（相同元数据配置）上展示了高 Jaccard Index (0.87)，实际 zero-shot 场景中镜像可能缺乏足够相似的参照镜像。当三层筛选后不足 5 条 trace 时"逐步放松选择条件"，这种退化行为的性能未被量化。

6. **基线选择公平性**：与 Lazyload 对比的改善幅度虽大，但 Lazyload 本质上没有预加载能力，不是一个公平的 preloading 基线。与更合理的基线（如 IOCnt2T）相比，改善幅度小得多（约 9-15%），论文在叙述中主要强调 vs. Lazyload 的数字。

---

## 七、AI Infra / MLSys 视角

1. **LLM 推理服务的冷启动优化**：ThinkAhead 的数据驱动预加载思路可以迁移到 serverless LLM 推理场景。模型权重加载面临类似的冷启动问题——从远端存储加载大模型权重时，可以基于历史请求模式预加载 layer/shard，而非等待首次推理请求触发加载。

2. **Checkpoint 恢复加速**：分布式训练中的 checkpoint 恢复与 VD 镜像加载有结构性相似——都是从远端存储拉取大量数据到本地。ThinkAhead 的 score-based block selection 可以启发 checkpoint 的分层预加载（优先加载 optimizer state 中即将用到的 partition）。

3. **带宽感知的数据加载调度**：ThinkAhead 将网络带宽分 bin 并为不同带宽条件训练不同参数的方法，可以应用于 LLM 训练中的数据预取。特别是在共享集群中，训练 job 和推理 job 竞争存储带宽时，动态感知带宽并调整预取策略具有实际价值。

4. **值得跟进的方向**：
   - 将 ThinkAhead 扩展到 GPU 集群的模型权重 prefetch，特别是 MoE 模型中 expert 权重的按需加载
   - 探索用轻量级 ML 模型（而非遗传算法）替代评分权重搜索，降低训练开销并支持在线学习
   - 研究多租户场景下预加载带宽的公平分配问题

---

## 八、总结

ThinkAhead 是一个面向 EBS 虚拟磁盘的数据驱动预加载系统，通过数据预处理、score-based block selection 和 zero-shot prediction 三个组件，利用同一镜像 VD 创建间的高度访问模式相似性，主动预加载数据块以缓解 lazy loading 导致的 slow I/O。在阿里巴巴 EBS 生产 trace 驱动的评估中，ThinkAhead 将 hit rate 提升最高 7.27×，尾延迟降低最高 98.7%，推理开销仅毫秒级。其主要局限在于训练开销较高（遗传算法需数小时）、预加载 accuracy 不到一半存在带宽浪费、以及端到端改善幅度远小于微基准数字。目前 ThinkAhead 作为实验特性部署在阿里巴巴 EBS 中，生产化推进中。
