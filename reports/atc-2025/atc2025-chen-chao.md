# Swift: Fast Performance Tuning with GAN-Generated Configurations

**作者**：Chao Chen, Shixin Huang (Shenzhen Institutes of Advanced Technology, CAS), Xuehai Qian (Tsinghua University), Zhibin Yu (Shenzhen Institutes of Advanced Technology, CAS; Shuhai Lab, Huawei Cloud)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/chen-chao
**源文件**：[atc2025-chen-chao.pdf](../../papers/atc-2025/atc2025-chen-chao.pdf)

---

## 一、背景

大数据框架（如 Apache Spark、Flink）通常提供上百个配置参数（内存分配、并行度、shuffle 行为等），这些参数的取值对程序性能影响巨大——合理调参可带来高达 89× 的性能提升。然而，参数空间庞大（Hadoop 34 个、Spark 41 个关键参数）且参数间存在复杂的非线性交互，使得配置优化极具挑战性。

传统方法中，基于规则和解析模型的方案因过度简化参数交互而效果不佳；基于仿真的方案需要大量耗时模拟；ML-based 方案（如 OPPerTune、SelfTune）需要数百个训练样本，每个样本需在真实集群上执行程序，导致优化时间长达数天乃至数周。Bayesian Optimization (BO) 虽然迭代次数最少，但每次迭代仍需真实执行，且随机生成的候选配置质量参差不齐，导致收敛缓慢、优化时间过长。

---

## 二、要解决的问题

1. **BO 收敛慢**：传统 BO 在每次迭代中从均匀随机生成的配置池中选择候选，质量不可控，可能选到比上一轮慢 2× 的配置，浪费迭代时间
2. **搜索空间偏移缺失**：随机采样无法将搜索空间偏向最优区域，导致 exploitation 和 exploration 的平衡不理想
3. **简单扰动方法（One-Neighbor）失效**：基于 Manhattan 距离对当前最优配置做小幅扰动，生成的配置虽然向量距离相近，但性能差异可能很大（2× 慢），原因在于仅保证了向量距离短而未保证元素值分布的相似性

---

## 三、洞察与设计

**关键洞察**：生成"与目标配置性能相似但不完全相同"的高质量候选配置，不仅需要配置向量间的距离短，还需要两个向量的元素值分布相似。Jensen-Shannon (JS) divergence 是衡量这种分布相似性的理想指标，而 GAN 天然以 JS divergence 作为损失函数来确保生成数据与输入数据的分布相似性。

基于此洞察，Swift 将 GAN 集成到 BO 框架中：

- **GAN-based Configuration Generator (GCG)**：以当前最优配置为目标，加上服从高斯分布的噪声，训练一个简单的三层全连接 GAN，生成分布相似的候选配置。由于配置是一维向量而非高维图像，GAN 训练简单快速（~几秒，固定 20 轮迭代）
- **混合候选池**：每次 BO 迭代中，将 GCG 生成的 150 个高质量配置与 RCG 随机生成的 100,000 个配置混合，由 acquisition function (Expected Improvement) 从中选择
- **Configuration Arbiter**：当 BO 选中的配置已在 Evaluated Set (ES) 中时，允许最多 3 次重新生成；超过阈值后，仅从 GCG 配置中选择，避免浪费迭代
- **动态更新**：每当发现新的"current best"，重新训练 GAN，确保生成配置始终围绕最新最优解

这种设计使搜索空间偏向最优区域（skewing），实现更快、更平滑的收敛。

---

## 四、实现细节

- **GAN 架构**：Generator 为三层全连接网络（输入 → 128 ReLU → 64 ReLU → dim 输出），Discriminator 同为全连接网络（128 ReLU → 1 sigmoid），使用 TensorFlow 实现
- **配置维度**：Flink 27 个参数，Spark 34 个参数，所有参数归一化至 [0.0, 1.0]
- **GAN 训练**：固定 20 轮迭代，使用标准 GAN loss（D_loss 和 G_loss），不追求 prob_conf0 = prob_conf1，而是允许生成配置性能在目标的 ±25% 范围内
- **Surrogate Model**：Gaussian Process，使用 Matérn 5/2 核函数
- **初始化**：随机生成 5 个配置执行评估，取最优作为首个 GAN 训练目标
- **终止条件**：当性能改进 < 5% 且已执行 ≥ 6 轮迭代时终止

---

## 五、实验结果

### 实验平台

| 平台 | 配置 |
|------|------|
| Flink 集群 | 4 节点，Intel Xeon E5-2407 4核，32GB RAM，Flink 1.4.2 |
| Spark 集群 | 8 节点，Intel Xeon E5-2630 v3，64GB RAM，Spark 2.2 |
| 生产集群 | 12 Docker 容器（Kubernetes），Intel Xeon E5-2698 v3 4核，8GB RAM |

### Flink 结果（vs CherryPick）

| 指标 | Swift 提升 | 优化时间 |
|------|-----------|---------|
| 吞吐量 | 平均 1.28×，最高 1.59× | 平均 5.8h |
| 延迟 | 平均 1.31×，最高 1.68× | CherryPick ≥ 12.5h |
| 试验次数 | 总计 89 次 | CherryPick ≥ 200 次 |

### Spark 结果

| 方法 | 平均优化时间 |
|------|------------|
| Swift | 5.1h |
| CherryPick | 5.9h |
| Selecta | 7h |
| DAC | 11.3h |

Swift 在 24 个 Spark 程序上取得比 CherryPick 高达 2.2×（平均 1.2×）的性能提升，且优化时间减少高达 156%（平均 61%）。

### 生产集群

Swift 在 6.8 小时内将人工调优 4 天的 Flink 日志分析程序的吞吐量提升 2.3×，延迟降低 2.8×。

---

## 六、批判性分析

1. **实验环境陈旧**：实验使用 Flink 1.4（2017 年版本）、Spark 2.2（2017 年）、CentOS 7、SUSE 11 等过时软件栈，这些版本的配置参数、默认值和性能特征与现代版本差异很大，结果的实际指导意义存疑

2. **基线选择问题**：论文以 CherryPick（2017 年）为主要基线，声称 OPPerTune 和 SelfTune 因需要过多样本而不纳入比较。但这些方法可能在足够样本下获得更好的最终性能，论文回避了"给够时间后谁更优"的公平比较

3. **随机种子实验不充分**：论文仅对 Flink WordCount 一个程序测试了 5 个随机种子，就声称"不同随机种子影响不大"，然后所有其他实验仅跑一次默认种子。这对于带有随机性的优化方法，统计显著性严重不足

4. **GAN 的必要性未充分论证**：论文的核心论点是 JS divergence 比 Manhattan distance 更好地捕捉配置相似性，但未对比其他能优化 JS divergence 的更简单方法（如直接在 JS divergence 约束下采样），GAN 是否是最简方案存疑

5. **超参数敏感性**：系统有多个需要手动设定的超参数（GCG 生成数量 150、RCG 数量 100,000、GAN 训练轮次 20、容忍阈值 3、初始配置数 5、终止阈值 5%/6 轮），仅对个别超参数做了 sensitivity study，整体鲁棒性不明

6. **单工作负载局限**：论文承认仅测试了单工作负载场景，但大数据集群的常态是多任务并发、资源争用，Swift 在这种场景下的表现完全未知

7. **TPC-DS 实验描述模糊**：论文提到测试了 23 个 TPC-DS 查询，但详细结果仅在附录中展示，正文缺乏对这类更复杂 SQL 负载的深入分析

---

## 七、AI Infra / MLSys 视角

1. **配置调优方法论的迁移**：Swift 的 GAN 辅助 BO 思路可迁移到 AI 训练/推理系统的超参数优化场景，如 DeepSpeed 的 ZeRO 配置、vLLM 的 batch scheduling 参数等。这些系统同样面临大量配置参数和昂贵的试验成本

2. **搜索空间偏移技术**：Swift 通过混合高质量生成样本和随机样本来偏移搜索空间的思路，可应用于 NAS（Neural Architecture Search）、自动并行策略搜索等 MLSys 问题中，加速 BO 类方法的收敛

3. **局限性**：现代 AI 系统（如分布式训练）的配置参数维度可能远超 34 个，且参数间的交互更为复杂（如 tensor parallelism × pipeline parallelism × data parallelism × micro-batch size），GAN 在更高维空间的效果需要验证

4. **潜在研究方向**：将 Swift 的方法与 transfer learning 结合——在一个工作负载上学到的 GAN 模型是否能加速新工作负载的配置优化？这在 AI 系统中尤为重要，因为训练任务往往具有相似的系统行为模式

---

## 八、总结

Swift 提出了一种将 GAN 集成到 Bayesian Optimization 中的配置调优方法，通过生成与当前最优配置分布相似的候选配置来偏移搜索空间，加速 BO 收敛。在 Flink 和 Spark 基准测试中，Swift 以更短的优化时间（平均 5-6 小时）获得了比 CherryPick 等基线更好的性能。该方法的核心价值在于减少了昂贵的真实执行次数，但实验环境较老旧、统计严谨性不足、仅支持单工作负载等局限性削弱了其实际应用价值。
