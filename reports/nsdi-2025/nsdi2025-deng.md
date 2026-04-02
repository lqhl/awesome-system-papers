# Minder: Faulty Machine Detection for Large-scale Distributed Model Training

**作者**：Yangtao Deng (Tsinghua University), Xiang Shi, Zhuo Jiang, Lei Zhang, Zhang Zhang, Bo Li, Zuquan Song, Hang Zhu, Gaohong Liu, Shuguang Wang, Haibin Lin, Jianxi Ye (ByteDance), Xingjian Zhang (Tsinghua University), Fuliang Li (Northeastern University), Minlan Yu (Harvard University)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/deng
**源文件**：[nsdi2025-deng.pdf](../../papers/nsdi-2025/nsdi2025-deng.pdf)

---

## 一、背景

大规模分布式模型训练需要同时使用数千台机器和上万块 GPU。随着模型参数规模从数百亿到超过万亿（如 GPT-4 的 1.8T 参数），训练集群的规模和复杂性持续增长。在 ByteDance 的生产环境中，硬件或软件故障平均每天发生两次，单次故障可能导致任务中断数小时甚至数天。以一个 128 机训练任务为例，40 分钟的 PCIe 降级故障就造成了超过 $1700 的经济损失。当前依赖人工排查的诊断方式效率低下，平均耗时超过半小时，最长可达数天。

---

## 二、要解决的问题

1. **故障通知不及时**：当前系统仅在任务完全停止后才报警，无法检测训练性能退化（如 PCIe 降级导致的速度下降），任务会在劣化状态下持续运行。
2. **排查内容不完整/冗余**：日志内容有限，不包含 GPU power、温度、NVLink 带宽等关键监控指标；同时日志中存在大量冗余信息（环境参数、warnings 等），增加排查难度。
3. **人工诊断流程复杂耗时**：需要训练、物理网络、存储、硬件等多个团队协作排查，流程可持续数小时到数天。
4. **故障类型多样、监控指标与故障关系复杂**：机器可能在任意组件出错（GPU、CPU、PCIe、NVLink、RNIC、内存、磁盘），没有单一指标能覆盖所有故障类型，且同一指标的正常范围随任务 workload 变化。

---

## 三、洞察与设计

**关键洞察**：在 3D 并行（DP/PP/TP）分布式训练中，所有机器的计算、通信、存储负载在秒级粒度上是均衡的，因此各机器的监控指标时序数据呈现高度相似的波动模式。当某台机器发生故障时，其监控数据会偏离群体，呈现出持续一段时间的异常离群模式——这种"相似性中的异常"和"异常的持续性"可以被自动检测。

基于此洞察，Minder 的核心设计包含四个要素：

1. **机器级相似性检测（Similarity）**：利用分布式训练中机器间指标的天然相似性，将故障检测转化为离群点检测问题，无需标注数据或预设正常阈值。
2. **持续性验证（Continuity）**：真正的故障导致的异常会持续数分钟，而噪声/抖动是短暂的。通过要求异常持续超过阈值（4 分钟）来过滤误报。
3. **逐指标独立模型（Per-metric Model）**：为每个监控指标训练独立的 LSTM-VAE 模型进行去噪和重建，避免多指标融合导致的相互干扰。因为不同指标对不同故障的敏感度差异很大，融合会稀释有效信号。
4. **指标优先级排序（Metric Prioritization）**：使用决策树对指标按故障敏感度排序（PFC > CPU > GPU > NVLink），优先用最敏感的指标检测，加速响应。

---

## 四、实现细节

**LSTM-VAE 模型**：编码器和解码器都使用 LSTM 网络，输入为单台机器在时间窗口 w（如 8 秒）内的单指标时序数据（1×w 向量）。模型参数包括 hidden_size=4、latent_size=8、lstm_layer=1。模型将输入重建为去噪后的嵌入向量，正常数据重建后保持相似，异常数据则产生明显偏差。MSE 低于 0.0001。

**在线检测流程**：
- Minder 每 8 分钟被调用一次，拉取过去 15 分钟的秒级监控数据
- 按指标优先级顺序，将每台机器的数据输入对应 LSTM-VAE 模型获取重建嵌入
- 计算所有机器间嵌入的两两欧氏距离，对每台机器求距离总和并归一化为 normal score
- 最大 normal score 超过相似性阈值的机器被标记为候选
- 如果同一台机器在连续时间窗口中被检测为候选超过 4 分钟（持续性阈值），则判定为故障机器

**指标优先级**：通过 Z-score 计算指标在故障时的离散程度，用决策树学习最优排序。结果显示 PFC Tx Packet Rate、CPU Usage、GPU 相关指标（Duty Cycle、Power Draw、Graphics Engine Activity、Tensor Activity）和 NVLink Bandwidth 为最敏感的 top-7 指标。

**部署**：运行在独立机器上（128 核 CPU、512G 内存、双端口 ConnectX-6 25G RNIC），作为后端服务不干扰在线训练。检测到故障后通知驱动程序通过 Kubernetes 驱逐故障机器并替换新机器，从 checkpoint 恢复训练。

---

## 五、实验结果

**数据集**：150 个运行时故障实例，覆盖 9 个月，任务规模 4 到 1500+ 机器（最多 10,000 GPU），覆盖 Table 1 中所有故障类型。

| 指标 | Minder | Mahalanobis Distance (MD) 基线 |
|------|--------|-------------------------------|
| Precision | 0.904 | 0.788 |
| Recall | 0.883 | 0.767 |
| F1-score | 0.893 | 0.777 |

**检测速度**：平均 3.6 秒完成一次检测调用（含数据拉取和处理），相比人工排查（平均 30+ 分钟）减少 99% 时间（快 500×）。

**各故障类型表现**：ECC error、CUDA execution error、GPU card drop、NVLink error、HDFS error、NIC hardware error、machine unreachable 表现良好。GPU execution error 和 PCIe downgrading 的 recall 较低（因同机多 GPU/PCIe 同时故障导致快速传播的 group effect）。AOC error 由于缺乏光缆相关计数器，部分被遗漏。

**消融实验**：
| 对比维度 | 结论 |
|---------|------|
| 指标数量 | 更多指标提高 recall 但降低 precision（相互干扰），更少指标 precision 和 recall 都下降 |
| 模型选择 | RAW（无去噪）recall 最差；CON（拼接嵌入）和 INT（统一模型）均不如逐指标独立模型 |
| 持续性检测 | 去掉 continuity 后 precision 明显下降（更多误报） |
| 距离度量 | 欧氏距离、曼哈顿距离、切比雪夫距离表现接近，说明 LSTM-VAE 嵌入质量好 |

---

## 六、批判性分析

1. **数据集规模偏小**：仅 150 个故障实例覆盖 9 个月，对于一个声称适用于"所有分布式训练任务"的系统来说，评估规模不够。论文提到生产环境平均每天 2 次故障，9 个月应有远超 150 个实例，说明大部分实例未被包含（可能因无法人工确认标签），这引发了对实际部署效果的疑问。

2. **并发故障处理几乎无效**：论文坦言 Minder 在处理交换机重启等并发故障场景时"hardly distinguishes the faulty outliers"，且当前秒级监控粒度不足。虽然通过注入实验展示了毫秒级监控下的可行性，但毫秒级监控在生产环境并未部署，实际能力存疑。

3. **对 3D 并行的强假设**：Minder 的相似性前提建立在 3D 并行训练的负载均衡之上。对于非对称并行策略（如异构 pipeline、不均匀的 expert parallelism in MoE）或推理、微调等工作负载，这一前提可能不成立。论文仅在讨论中提及"future work will explore"，未给出任何验证。

4. **基线对比薄弱**：仅与 Mahalanobis Distance 一个统计方法对比。没有与其他时序异常检测方法（如 Transformer-based、GNN-based）对比，也未与 SuperBench 等同领域系统做端到端比较。

5. **根因分析缺失**：Minder 只能定位到故障机器，无法识别具体故障类型或根因。检测后仍需人工介入做进一步诊断，这限制了自动化闭环的实现。

6. **连续性阈值的选择**：4 分钟的 continuity threshold 是经验性选择。论文未充分分析该参数对不同类型故障的影响——对于传播极快的故障（如 NVLink error），4 分钟可能导致检测延迟过长。

---

## 七、AI Infra / MLSys 视角

1. **对大规模训练运维的直接价值**：Minder 解决了 LLM 训练中最痛的运维问题之一——故障机器定位。对于任何运营千卡以上训练集群的团队，这是一个高度实用的参考。其"相似性+持续性"的方法论简洁且适用性广。

2. **可迁移的设计思路**：
   - **逐指标独立模型**的设计值得在其他监控场景借鉴。多指标融合是直觉上更"自然"的方案，但 Minder 通过消融实验证明了在异构指标场景下独立模型更优。
   - **指标优先级排序**的思路可以迁移到推理系统的 SLO 监控，根据不同异常类型动态调整监控指标的检查顺序。

3. **值得跟进的方向**：
   - **从机器级到组件级定位**：结合 in-band profiling（如 TorchProfiler、CUDA event timer）实现从"哪台机器出了问题"到"哪个组件、哪种故障"的精细化诊断，形成自动化闭环。
   - **MoE 和异构并行场景的适配**：MoE 模型的 expert parallelism 打破了机器间负载均衡的假设，需要新的相似性定义（如同 expert group 内的相似性）。
   - **推理服务的故障检测**：推理场景中请求分布不均匀、负载波动更大，直接应用 Minder 的相似性假设不成立，需要探索请求级或 batch 级的异常检测方法。
   - **毫秒级监控的工程化**：论文的注入实验表明毫秒级监控可大幅提升并发故障检测能力，如何低开销地在生产环境部署毫秒级监控是一个有价值的工程问题。

---

## 八、总结

Minder 是 ByteDance 部署的自动故障机器检测系统，利用分布式训练中机器间监控指标的天然相似性，通过 LSTM-VAE 去噪、逐指标独立模型、相似性距离检测和持续性验证来定位故障机器。系统在生产环境部署超过一年，平均 3.6 秒完成检测（比人工快 500 倍），精度 0.904、F1 0.893。主要局限在于无法处理并发故障、缺乏根因分析能力、对非 3D 并行场景未验证，且评估数据集规模有限。
