# AdaCheck: An Adaptive Checkpointing System for Efficient LLM Training with Redundancy Utilization

**作者**：Weijie Liu*, Shengwei Li*, Zhiquan Lai, Keshi Ge (National University of Defense Technology); Qiaoling Chen (Nanyang Technological University); Peng Sun (Shanghai AI Laboratory); Dongsheng Li, Kai Lu (National University of Defense Technology)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/liu-weijie
**源文件**：[[fast2026-liu-weijie.pdf]]

---

## 一、背景

大语言模型（LLM）训练依赖复杂的并行训练技术（数据并行、模型并行、专家并行等），需要在数千 GPU 上进行长时间训练。例如 LLaMA 3.1 在 16K GPU 上训练 54 天，期间遭遇 419 次故障，平均每 3 小时失败一次。Checkpointing 是故障恢复的核心机制，定期保存模型状态以便从最近的检查点恢复训练。

现有 checkpointing 系统主要分为：异步存储方案（CheckFreq）、远程持久存储优化（ByteCheckpoint、FastPersist）、分布式内存 checkpointing（GEMINI）等。这些系统都是针对特定并行策略或模型架构的离线方案，无法适应多样化的并行策略组合，也未能识别和利用大部分模型状态的冗余性，导致 checkpoint 体积过大、保存频率过低、故障恢复代价高。

---

## 二、要解决的问题

1. **状态冗余复杂且难以建模**：不同并行策略（ZeRO-1/3、MiCS、EP、自动并行等）和模型架构（dense、MoE、MLA）组合产生的状态冗余模式各不相同。参数和 optimizer 状态的冗余类型可能不一致（如 ZeRO-1 下参数全冗余但 optimizer 状态无冗余），朴素方法会生成不可用的 checkpoint。

2. **细粒度冗余识别开销大**：LLM 参数量巨大，每个 worker 不知道其他 worker 的状态。朴素的逐 tensor 比较方案在 1000+ worker 规模下需要超过 30 天。

3. **离线冗余利用不足以实现 1S1C（每步一 checkpoint）**：即使去除冗余状态，在 ZeRO-1 或 EP 等策略下，所需的保存带宽仍远超持久存储（<100 Gbps）和训练网络互联（<400 Gbps）的能力。

---

## 三、洞察与设计

**关键洞察**：并行训练中大量模型状态存在冗余（如 Yi-34B 训练中 25%、MegaScale-530B 中 100% 的状态冗余），且混合精度训练中相邻迭代间 checkpoint 的差异仅为半精度梯度（大小为 2M vs 完整状态 14M），因此可以同时从"空间维度"（跨 worker 的 tensor 冗余）和"时间维度"（跨迭代的状态冗余）两个方向大幅压缩 checkpoint 体积。

基于此洞察，AdaCheck 设计了两层冗余利用机制：

### 离线冗余利用（Offline Redundancy Utilization）
- 引入 **tensor redundancy** 抽象，用元组列表描述每个 tensor 的副本分布位置
- 将状态冗余分为三类：全冗余（所有 worker 持有副本）、部分冗余（部分 worker 持有）、无冗余（仅单个 worker 持有）
- 计算参数与 optimizer 状态冗余类型的交集，确保生成的 checkpoint 可用
- 仅保存无冗余和部分冗余的状态

### 在线冗余利用（Online Redundancy Utilization）
- **基于梯度的增量 checkpointing**：利用混合精度训练的参数更新模式，仅保存半精度梯度（2M）替代完整 optimizer 状态（12M）+ 参数（2M），压缩比达 1/7
- **远程更新机制**：在远程 worker CPU 内存中维护备份 optimizer，接收梯度后自行更新状态，故障恢复时直接获取最新 optimizer 状态，避免逐步重放梯度

---

## 四、实现细节

### 冗余检测器（Redundancy Detector）
采用三阶段通信优化：
1. **Hash-based 一致性检查**：将 tensor 映射为 blake2s hash（256-bit），传输 hash 值而非原始 tensor 进行比较。两次迭代取交集避免 hash 碰撞和偶然相等
2. **通信组范围缩减**：利用并行训练中 worker 组织为通信组的特性，只在通信组内比较，去除重叠子集
3. **Ring-based 通信算法**：借鉴 ring-allreduce，将顺序比较转为并行执行，并在最终阶段传输比较结果而非完整 packed tensor

检测器可在 128 worker 规模下 3 分钟内完成冗余识别，仅在训练开始时执行一次。

### 系统设计
- 支持容错因子 k，将部分冗余进一步细分：副本跨越 k 个以上节点视为全冗余，否则视为无冗余
- Checkpoint group 按模型并行分组，确保组内 worker 计算图相似，便于重叠通信与计算
- 非阻塞全量 checkpointing：后台线程定期保存完整 checkpoint 到持久存储，应对灾难性故障
- 非侵入式 API，不假设用户训练脚本、并行策略或模型架构
- 基于 PyTorch 2.0 实现，已集成到 Merak 框架并开源

---

## 五、实验结果

### 实验环境

| 集群 | GPU | 规模 | 训练带宽 | 存储带宽 |
|------|-----|------|----------|----------|
| DCN | 8×A800 80G/node | 32 GPU | 800 Gbps | 50 Gbps |
| CMD | 4×3090 24G/node | 128 GPU | 100 Gbps | 10 Gbps |

### 模型

| 模型 | 类型 | 参数量 |
|------|------|--------|
| LLaMA-7B / LLaMA-30B | Dense | 7B / 30B |
| GPT-1.4B / GPT-7B | Dense | 1.4B / 7B |
| DeepSeek-V2-Lite | Sparse (MoE, 64 experts) | — |
| GPT-MoE | Sparse (MoE, 64 experts) | — |

### 关键结果

| 指标 | 对比 CheckFreq | 对比 GEMINI |
|------|---------------|-------------|
| Checkpoint 体积缩减 | 6.00–896× | — |
| Checkpoint 频率提升 | 36.2–111× | 1.46–3.64× |
| 故障浪费时间缩减 | 12.1–88.93× | 1.73–4.51× |
| 端到端吞吐提升 | — | 最高 1.12× |
| 训练吞吐开销 | 几乎为零 | — |

- AdaCheck 适配所有并行策略（ZeRO-1/3、MiCS、EP+MP、自动并行），包括 nnScaler 生成的不规则并行
- 容错因子 k=2、n=32 时，4 worker 同时故障的恢复概率仍 >90%

---

## 六、批判性分析

1. **GEMINI 基线为自行复现**：论文承认 GEMINI 是闭源的，只能"to the best of our abilities"复现。这意味着与 GEMINI 的所有对比数据的可靠性存疑——复现版本的性能可能低于原始实现，导致 AdaCheck 的优势被高估。

2. **梯度增量 checkpointing 的数值精度风险被低估**：用半精度梯度重放 optimizer 更新来恢复 FP32 optimizer 状态，涉及浮点累积误差。论文声称"不影响收敛精度"但未提供任何收敛实验或数值误差分析，仅一句"we focus on comparing checkpointing performance"带过。对于长时间训练（如 LLaMA 3.1 的 54 天），累积误差是否可控是一个关键问题。

3. **容错可靠性分析基于均匀故障假设**：论文假设故障均匀分布在 worker 间，但实际数据中心故障往往具有空间相关性（同一机架、同一交换机下的节点更容易同时故障）。k=2 在 32 worker 规模下 4 worker 同时故障恢复概率 >90% 看似不错，但如果这 4 个故障 worker 恰好在同一 checkpoint group 内，恢复概率为 0。

4. **实验规模偏小**：最大规模仅 128 GPU（CMD 集群），而论文 motivation 中反复提到的 LLaMA 3.1 使用 16K GPU。冗余检测器的 3 分钟/128 worker 结果能否线性外推到数千 worker 规模不确定，通信组的重叠和检测开销可能非线性增长。

5. **远程更新机制的 CPU optimizer 开销未量化**：在远程 worker CPU 上持续运行 optimizer 更新会消耗 CPU 计算资源和内存带宽，论文未报告这部分开销对训练流水线的影响。

---

## 七、AI Infra / MLSys 视角

1. **冗余利用思路的普适性**：tensor redundancy 抽象不仅适用于 checkpointing，还可以应用于通信优化（如减少冗余的 allreduce）、弹性训练（故障后重新分配冗余状态而非重启）、以及 checkpoint 感知的并行策略搜索（将 checkpoint 开销纳入自动并行优化目标）。

2. **与 MoE 训练的深度结合**：随着 DeepSeek-V3、Kimi K2 等超大 MoE 模型的流行，EP+ZeRO 组合下的 checkpointing 效率成为痛点。AdaCheck 对 MoE 的细粒度冗余分析（dense layer 全冗余 vs expert 无冗余）提供了有价值的分析框架。

3. **值得跟进的方向**：
   - **Checkpoint 感知的自动并行**：将 checkpoint 体积/频率作为自动并行搜索的优化目标之一，在训练性能和 checkpointing 效率间取得更好的 Pareto 最优
   - **异构存储分层 checkpointing**：结合 CXL 内存、NVMe、远程 DRAM 等多级存储，根据状态冗余类型选择不同存储层
   - **大规模验证**：在千卡以上规模验证冗余检测和梯度增量 checkpointing 的可扩展性和数值稳定性

---

## 八、总结

AdaCheck 提出了一种自适应 checkpointing 系统，通过 tensor redundancy 抽象统一建模并行训练中的状态冗余，结合离线冗余利用（去除冗余状态）和在线冗余利用（基于梯度的增量 checkpointing），将 checkpoint 体积缩减 6–896×，实现每步一 checkpoint 的目标。系统设计对并行策略和模型架构透明，已适配 dense 和 MoE 模型的多种并行组合。主要局限在于实验规模有限（最大 128 GPU）、GEMINI 基线为自行复现、以及梯度增量方案的数值精度缺乏严格验证。
