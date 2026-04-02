# Mowgli: Passively Learned Rate Control for Real-Time Video

**作者**：Neil Agarwal, Rui Pan (Princeton University); Francis Y. Yan (University of Illinois Urbana-Champaign); Ravi Netravali (Princeton University)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/agarwal
**源文件**：[nsdi2025-agarwal.pdf](../../papers/nsdi-2025/nsdi2025-agarwal.pdf)

---

## 一、背景

实时视频会议（如 Microsoft Teams、Google Hangouts、Zoom）已成为日常生活的重要组成部分。码率控制算法（如 Google Congestion Control, GCC）是视频会议平台的核心，负责根据动态网络状况每隔约 50ms 选择目标码率，以在内容质量和延迟/卡顿之间取得平衡。

近年来，基于强化学习（RL）的数据驱动码率控制方案（如 R3Net、OnRL、Loki）展现了显著优于 GCC 等规则启发式算法的潜力。然而，这些方案在生产环境中几乎没有被采纳——其核心障碍在于训练过程中对真实用户 QoE 的严重干扰。

---

## 二、要解决的问题

1. **在线 RL 训练代价过高**：现有数据驱动方案需要将部分训练的 RL 模型部署到真实用户的视频会议中进行探索式学习。实验表明，训练期间 62% 的通话码率下降，43% 的通话出现更高冻结率（最高增加 79%），QoE 严重退化。
2. **模拟器训练不可靠**：在模拟/仿真环境中预训练的模型面临"sim-to-real gap"，部署到生产环境后性能大幅下降。
3. **GCC 调参空间有限**：GCC 的规则启发式本身就是次优的，代码库中有数百个可调参数，且无法利用丰富的网络信号。
4. **核心矛盾**：如何在不干扰生产环境用户体验的前提下，获得数据驱动方案带来的性能提升？

---

## 三、洞察与设计

**关键洞察**：GCC 虽然在动态网络中反应迟缓（带宽下降时过冲、带宽恢复时爬坡过慢），但它最终总会朝正确的方向调整码率。也就是说，GCC 的生产日志中已经包含了正确的决策动作，只是这些动作出现的时机不对、顺序不对。如果将同一组决策重新排列到正确的时间点，就能大幅提升 QoE——仅靠重排 GCC 自身的动作（不引入任何新动作值），就能使码率提升 19%、冻结减少 80%。

基于这一洞察，Mowgli 提出了一种**被动学习**（passive/offline learning）范式：

1. **数据处理**：从生产环境中已有的 GCC 遥测日志（本来就用于调试和监控）中提取 (state, action, reward) 轨迹，state 包含 12 维传输/应用层特征（码率、延迟、抖动、丢包等），action 为目标码率更新，reward 为吞吐量、延迟、丢包的线性组合。
2. **策略生成**：使用 Soft Actor-Critic (SAC) 算法离线训练轻量神经网络。为应对两大挑战：
   - **缺乏反馈（distribution shift）**：采用 Conservative Q-Learning (CQL)，对 critic 的估值加保守惩罚——对日志中未见过的 (state, action) 降低 Q 值估计，对日志中出现过的提升估计，防止 actor 被错误高估值引导。
   - **环境方差**：将 critic 的输出从标量改为分布（Distributional RL + Quantile Huber Loss），显式建模同一决策在不同环境噪声下的多种可能结果。
3. **策略部署**：训练好的轻量模型（79k 参数、316 kB）部署到客户端，通过 Python 进程与 WebRTC 应用通信，推理延迟约 6ms。

---

## 四、实现细节

- **框架**：基于 AlphaRTC（WebRTC 分支），使用 PyTorch 和 d3rlpy 库训练。
- **网络架构**：Actor 和 Critic 各 2 层隐藏层（256 维），前置 GRU（隐藏维度 32）对 1 秒窗口的状态序列提取时序特征。
- **超参数**：CQL α = 0.01，分布 RL 分位数数量 N = 128。
- **状态向量**：12 维特征（Table 1），其中 4 个额外特征（Previous Action、Min RTT、Report Intervals、Timesteps since Last Packet Loss Report）经消融验证对性能有显著贡献。
- **奖励函数**：R = 2·throughput − 1·delay − 1·loss，吞吐量归一化到 (0, 6 Mbps)，延迟归一化到 (0, 1000 ms)。
- **部署方式**：在 sender 端启动 Python 进程，通过 IPC 管道接收遥测数据并输出码率决策。
- **日志量**：1 分钟通话的压缩日志约 117 kB。

---

## 五、实验结果

### 仿真实验

使用 FCC 宽带和 Norway 3G 蜂窝网络轨迹（87 小时），RTT 设置 40/100/160 ms。

| 指标 | GCC → Mowgli 提升 | Mowgli vs Online RL 差距 |
|------|-------------------|------------------------|
| 平均视频码率 | +14.5%–39.2% | 0.5%–13.1% 以内 |
| 视频冻结率 | -59.5%–100% | P75: 0.77% vs 0.66%; P90: 2.87% vs 2.41% |
| 帧率 | +0%–35.3% | — |
| 端到端帧延迟 | < 400ms 交互阈值 | — |

- **高动态网络**中 Mowgli 优势更大：码率 +10.8%–43.8%，冻结 -47.4%–100%。
- **近似 Oracle 对比**：Mowgli 码率达到 Oracle 的 94%（Oracle 拥有完美带宽预知）。
- BC（行为克隆）P90 码率比 GCC 低 14.4%；CRR（Sage 底层算法）在两项指标上均劣于 GCC。

### 真实网络实验

4 个美国城市的 4G/LTE 蜂窝网络，8 小时+ GCC 日志，4 小时+ 评估。

| 场景 | 码率提升 |
|------|---------|
| 场景 A（同城市） | +3.0%–2.1× |
| 场景 B（新城市） | +2.0%–20.8% |

冻结率在统计上与 GCC 无显著差异（样本量有限）。

### 消融实验

| 变体 | P90 冻结率变化 |
|------|---------------|
| 去除 CQL | +11.3× |
| 去除 Distributional RL | +9.9× |
| 去除 Report Intervals | 码率 -8.7% |
| 去除 Min RTT | 冻结 +1.2× |
| 去除 Prev Action | 冻结 +3.1× |

---

## 六、批判性分析

1. **评估环境与生产差距**：论文反复强调要解决"sim-to-real gap"问题，但由于没有生产环境访问权限，所有实验（包括"生产日志"收集）都在自建 testbed 上完成。GCC 日志来自自己的 Mahimahi 仿真而非真正的生产部署，这使得"利用生产日志"的核心卖点在实验层面未被真正验证。

2. **单向视频简化**：实验只评估了单向视频（无音频），且禁用了 WebRTC 的 DegradationPreference。真实视频会议是双向的、包含音频的，codec 的自适应降级行为也是活跃的。这些简化可能使实验结果过于乐观。

3. **真实网络冻结率不置可否**：在最有价值的真实网络实验中，冻结率（最关键的 QoE 指标之一）"统计上不可区分"——这可能意味着 Mowgli 在冻结率上并无实际改善，但论文选择不展示这些数据。

4. **泛化性有限但被轻描淡写**：Fig. 12 显示在不同网络类型上训练的模型跨场景部署时，P50 码率降 45.8%、P75 冻结增加 40.3×。论文承认了这一点但将其描述为"预期行为"——然而这正是生产部署中最常见的场景（网络条件持续变化），此结果实质上削弱了论文的实用性主张。

5. **Online RL 基线不完全公平**：Online RL 的报告结果排除了训练期间的 QoE 退化，只展示收敛后的最佳模型。但 Mowgli 的核心论点之一是"不需要训练期退化"，因此将 Mowgli（全部性能）与 Online RL（仅最佳性能）对比，在某种程度上是 Mowgli 更不利的对比方式。这一选择对 Mowgli 有利也有弊——有利在于缩小了差距，不利在于如果 Online RL 展示完整画面则 Mowgli 的优势更突出。

6. **CRR 基线对比可能不公平**：论文认为 CRR（Sage 的底层算法）表现差是因为只有单一策略的日志覆盖不足。但 Sage 原本就设计为使用多种 CC 算法的日志，这一对比更像是在批评 CRR 被用于非预期场景，而非 Mowgli 的方法优势。

---

## 七、总结

Mowgli 提出了一种务实的视频会议码率控制改进路径：完全利用现有生产环境中 GCC 的遥测日志进行离线学习，避免在线 RL 训练对用户 QoE 的干扰。通过 Conservative Q-Learning 管理分布偏移风险、通过 Distributional RL 处理环境方差，Mowgli 在仿真和真实蜂窝网络上展现了相比 GCC 15%–39% 的码率提升和 60%–100% 的冻结率降低，接近在线 RL 的性能水平。主要局限在于模型泛化性受训练数据分布约束，且在真正的大规模生产环境中尚未得到验证。
