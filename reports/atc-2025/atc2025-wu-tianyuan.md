# GREYHOUND: Hunting Fail-Slows in Hybrid-Parallel Training at Scale

**作者**：Tianyuan Wu, Wei Wang (Hong Kong University of Science and Technology); Yinghao Yu, Siran Yang, Wenchao Wu, Guodong Yang, Jiamang Wang, Lin Qu, Liping Zhang (Alibaba Group); Qinkai Duan (HKUST)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/wu-tianyuan
**源文件**：[[atc2025-wu-tianyuan.pdf]]

---

## 一、背景

大规模模型训练通常需要数万块 GPU 运行数周甚至数月。在这样的规模下，硬件和网络故障成为常态。现有研究主要关注 fail-stop 类故障（如 GPU 挂起、运行时崩溃），已有成熟的 checkpoint-and-restart 机制来应对。然而，fail-slow（即组件仍在工作但性能退化）是一个被广泛忽视但同样严重的问题。Fail-slow 不会导致训练崩溃，但由于同步训练的特性，一个慢组件会拖累整个训练集群的性能。

---

## 二、要解决的问题

1. **Fail-slow 缺乏系统性理解**：尽管 Meta、ByteDance 等公司在报告中简要提及 fail-slow，但其整体特征（频率、持续时间、根因分布、对训练的影响）尚不明确。
2. **检测困难**：由于同步训练的特性，一个 straggler 会导致所有 GPU 的利用率同时下降，仅靠 GPU SM utilization 或 RNIC CNP 等遥测指标无法定位到具体的慢组件。使用 SuperBench 等基准测试工具需要停止整个训练作业，代价过高。
3. **缺乏有效的缓解机制**：当前实践是将 fail-slow 当作 fail-stop 处理（checkpoint-and-restart），但 fail-slow 通常是暂态的（平均持续 10-72 分钟），而大模型的 checkpoint dump 本身就需要近 100 分钟，用 C/R 来应对得不偿失。
4. **多种并行策略下的复杂性**：hybrid parallelism（TP+DP+PP）使得 fail-slow 的定位更加困难，需要区分计算和通信层面的性能退化。

---

## 三、洞察与设计

**关键洞察**：在 hybrid-parallel 训练中，不同并行维度（TP、DP、PP）的通信流量差异巨大——DP 的 gradient 同步流量远超 PP 的 activation 传输（数十 GB vs 数百 MB），因此可以通过在并行拓扑中交换角色（将拥塞链路从重流量 DP 组移至轻流量 PP 组）来缓解通信 fail-slow；同时，fail-slow 的暂态特性意味着最优缓解策略取决于持续时间（无法预知），这与经典的 ski-rental 问题同构，可以用渐进升级的策略来平衡缓解效果与干预成本。

GREYHOUND 由两个子系统组成：

**GREYHOUND-DETECT**（检测）：三阶段流水线
- **Tracking**：通过 `LD_PRELOAD` hook NCCL 函数调用，透明地追踪每个 worker 的 iteration time。使用 ACF（自相关函数）从通信调用序列中识别周期模式，推算 iteration time。再用 BOCD（Bayesian Online Change-point Detection）+ 验证（过滤 <10% 的抖动）检测慢迭代。
- **Profiling**：检测到慢迭代后，注入 CUDA events 到 NCCL 调用中，测量每个通信组的执行时间。通过"可比较集群"内的交叉对比（同一 comparable cluster 内通信量相同的组，执行时间应一致），缩小可疑范围。
- **Validation**：短暂挂起训练（通过 trap NCCL 调用进入 wait loop），在可疑组内运行轻量级基准测试。计算验证用 GEMM，通信验证用 O(1) 的 ring/tree 拓扑分解（将集合通信分解为不重叠的 P2P 操作）。

**GREYHOUND-MITIGATE**（缓解）：四级自适应策略
- **S1: Do nothing**：等待自愈，零成本。
- **S2: 调整 micro-batch 分配**：将更少的 micro-batch 分给慢 DP 组，建模为二次规划问题（最小化各 DP 组处理时间方差），用 cvxpy 求解。
- **S3: 调整并行拓扑**：将拥塞链路从 DP 组移至 PP 组（角色交换）；多个 straggler 时合并到最少的 PP stage 中（straggler consolidation）。通过内存中 RDMA 交换参数实现，约 1 分钟完成。
- **S4: Checkpoint-and-restart**：最后手段。

策略升级遵循 ski-rental 启发式：从 S1 开始，当累计性能损失达到下一策略的干预成本时升级。

---

## 四、实现细节

- **GREYHOUND-DETECT**：约 5.5k LOC（C++ + Python）。Monitor 通过 Linux `LD_PRELOAD` hook NCCL 函数，使用共享内存（节点内）和 Redis（节点间）通信。验证时复用训练进程的 CUDA context 和 NCCL communicator，避免初始化开销。计算基准依次运行 FP8/FP16/FP32 GEMM kernel；通信基准使用 16/32/64 MB 消息的 send/receive，各重复 3 次。
- **GREYHOUND-MITIGATE**：约 1.5k LOC Python，作为 Megatron-LM 插件实现。planner 从 Redis 接收 straggler ID，生成调整策略。micro-batch 调整用 cvxpy 求解（512 DP 组约 36 秒）。拓扑调整四步完成：暂停训练→dump 参数到主存→P2P RDMA 交换→重启训练。
- **Iteration time 推断**：ACF 阈值 M=0.95，BOCD change-point 阈值 0.9，变化幅度验证阈值 10%。
- **通信验证 O(1) 算法**：Ring 拓扑 2-3 pass（偶/奇环分别处理），Tree 拓扑 4 pass。

---

## 五、实验结果

### 特征研究（生产集群：4000+ 节点，10000+ GPU）

| 类别 | 规模 | Fail-slow 比例 | 平均持续时间 | 平均 JCT 延迟 |
|------|------|---------------|-------------|--------------|
| 计算 fail-slow | 单节点 probing（392 jobs） | 1.5%（6/392） | 10 min | 11.79% |
| 通信 fail-slow | 4 节点 probing（107 jobs） | 40%（42/107） | 24 min | 15.45% |
| 大规模（≥512 GPU） | 27 jobs | 59%（16/27） | 72 min | 34.59% |

### 检测准确率

| 算法 | 计算 fail-slow 准确率 | 通信 fail-slow 准确率 |
|------|---------------------|---------------------|
| Sliding Window | 99.5%（FNR 25%） | 93.5%（FNR 12.2%） |
| BOCD | 77.8%（FPR 18.4%） | 69.2%（FPR 34.0%） |
| BOCD+V（本文） | 100%（FPR 0%, FNR 0%） | 99.1%（FPR 0%, FNR 2.3%） |

### 缓解效果

| 策略 | 场景 | 改善 |
|------|------|------|
| S2: micro-batch 调整 | 单 DP 组慢（4DP） | 1.59× |
| S3: 拓扑调整 | 通信拥塞（4PP） | 1.23× |
| S3: straggler consolidation | 2 个拥塞链路（4DP, 4PP） | 1.7× → 1.3× |

### 256 H800 端到端实验

- 注入 12 个 fail-slow 事件（2 通信 + 10 计算）
- 检测准确率 100%，平均反应时间 10.56 秒
- 无 GREYHOUND：吞吐从 37.4 降至 18.9 iter/min
- 有 GREYHOUND：恢复至 29.8 iter/min，**1.58× 端到端改善**

### 开销

| 组件 | 开销 |
|------|------|
| Tracking | 平均 0.39%，最大 1.1% |
| Profiling | 无额外开销（离线分析） |
| Validation（计算+通信） | ~5 秒 |
| S2: micro-batch 调整 | <1 秒（16 DP）至 ~36 秒（512 DP） |
| S3: 拓扑调整 | 比 disk-based C/R 快 2.46×–6.72× |

---

## 六、批判性分析

1. **Fail-slow 注入的代表性**：实验评估中 fail-slow 均为手动注入（nvidia-smi 锁频率、旁路通信制造拥塞），这与真实生产环境中的 fail-slow 模式（如热节流的渐进性、网络拥塞的突发性和多因素叠加）可能存在差异。论文虽然做了生产集群的特征分析，但缓解效果的评估完全基于合成 fail-slow，缺乏在真实生产 fail-slow 上的端到端验证。
2. **S2 策略的局限性被低估**：当多个 DP 组同时变慢时（生产环境中大规模训练更容易出现），micro-batch 重分配的空间急剧缩小。论文承认了这一点但未深入讨论其在大规模场景下的实际影响——特征研究显示大规模训练中 fail-slow 经常是 compound 的。
3. **S3 策略假设 DP 和 PP 可自由交换角色**：这要求模型能适配不同的 pipeline 划分方式，且参数交换后训练语义不变。论文未讨论这对模型架构的约束（如 MoE 模型的 expert parallelism、非均匀 stage 划分等更复杂的并行策略）。
4. **通信验证的 O(1) 声明有隐含前提**：虽然单次验证的 pass 数是常数（2-4），但每个 pass 中所有 rank 同时参与 P2P 通信，总通信量仍然随组大小线性增长，只是时间复杂度为 O(1)。
5. **Ski-rental 启发式的理论保证不清晰**：经典 ski-rental 是两级决策（租或买），本文扩展为四级但未给出竞争比分析。实际的策略切换阈值（累计损失等于下一策略开销）是否在多级场景下仍有理论保证未做讨论。
6. **与 Holmes（concurrent work）的对比缺失**：Holmes 是同期工作，同样解决 LLM 训练中的 straggler 问题，但论文仅在 Related Work 中简要提及，未做直接实验对比。

---

## 七、AI Infra / MLSys 视角

1. **Fail-slow 特征数据的参考价值**：论文提供了阿里巴巴 10000+ GPU 生产集群的 fail-slow 特征数据（频率、持续时间、根因分布），这对 AI Infra 团队设计容错策略具有直接参考价值。特别是"通信 fail-slow 频率 40%、大规模训练中 59% 的 job 受影响"这些数据点，说明 fail-slow 是 AI 训练平台必须正视的问题。

2. **非侵入式监控的工程启发**：通过 `LD_PRELOAD` hook NCCL + ACF 周期检测 + BOCD 变点检测的组合，实现了对训练框架完全透明的性能监控。这种方法可以推广到任何基于 NCCL 的训练框架（DeepSpeed、Megatron-LM、FSDP 等），值得在训练平台中作为标准监控组件部署。

3. **Micro-batch 动态重分配**：S2 策略将负载均衡建模为 QP 问题并证明不影响训练正确性（通过加权梯度聚合），这个思路可以延伸到更广的异构训练场景，如混合精度训练中不同 GPU 的计算能力差异、spot instance 场景中的动态资源变化等。

4. **可跟进的研究方向**：
   - **与弹性训练的融合**：GREYHOUND 的 S3 策略（拓扑调整）与弹性训练框架（如 Oobleck、Parcae）的弹性并行调整有天然的结合点，可以设计一个统一框架同时处理 fail-stop 和 fail-slow。
   - **预测性缓解**：当前系统是反应式的（检测到 fail-slow 后才缓解），如果能结合历史数据预测 fail-slow 的发生（如根据温度趋势预测热节流），可以提前做预防性调整。
   - **Expert Parallelism 下的 fail-slow 处理**：论文未涉及 MoE 模型的 expert parallelism，而 MoE 的 all-to-all 通信模式对网络拥塞更敏感，是一个有价值的扩展方向。

---

## 八、总结

GREYHOUND 是首个系统性研究大规模训练中 fail-slow 问题的工作，贡献了生产集群的特征分析数据，设计了非侵入式的三阶段检测机制（tracking → profiling → validation）和基于 ski-rental 理论的四级自适应缓解策略。系统在阿里巴巴 10000+ GPU 集群上验证了 99%+ 的检测准确率，在 256 H800 GPU 实验中实现了 1.58× 端到端吞吐改善。主要局限在于缓解效果仅在合成 fail-slow 上验证，且对更复杂的并行策略（如 EP、非均匀 PP）的支持尚未讨论。
