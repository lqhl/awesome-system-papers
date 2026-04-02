# Obscura: Concealing Recomputation Overhead in Training of Large Language Models with Bubble-filling Pipeline Transformation

**作者**：Yuzhou Huang, Yapeng Jiang (Sun Yat-sen University), Zicong Hong (HKUST), Wuhui Chen* (Sun Yat-sen University), Bin Wang, Weixi Zhu (Huawei Technologies), Yue Yu (Peng Cheng Laboratory), Zibin Zheng (Sun Yat-sen University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/huang-yuzhou
**源文件**：[[atc2025-huang-yuzhou.pdf]]

---

## 一、背景

大语言模型（LLM）的训练需要巨大的 GPU 显存。例如，fine-tune Llama-2 13B 需要约 400GB 显存，远超单张 A100 80GB 的容量。Pipeline parallelism（流水线并行）是分布式训练的核心策略之一，通过将模型层分配到多个 GPU 上实现跨节点高效扩展。

1F1B（one-forward, one-backward）是最常用的 pipeline schedule，但存在严重的**显存不均衡**问题：早期 stage 需要缓存更多 micro-batch 的 activation，导致显存用量远高于后期 stage。以 8-way pipeline 训练 Llama-2 13B 为例，stage 0 比 stage 7 多消耗约 35GB 显存。

Recomputation（重计算）是缓解 activation 显存压力的标准手段：在 forward pass 丢弃 activation，backward pass 时重新计算。但这引入了显著的计算开销，延长了训练时间。

---

## 二、要解决的问题

1. **全 stage 重计算效率低下**：现有方案（如 DAPPLE+）对所有 stage 统一应用 recomputation，但实际上只有前几个 stage 存在显存瓶颈，后期 stage 显存充裕。All-Stage Recomputation 增加了约 33% 的执行时间。

2. **On-Demand Recomputation 虽然更优但受限**：仅对超出显存限制的 stage 应用 recomputation（On-Demand）比全 stage 方案更快，但 pipeline 中的 bubble 利用率不足——forward bubble 完全未被利用，backward bubble 只能隐藏部分重计算开销。

3. **Stage 间紧耦合的数据依赖限制了 bubble 利用**：micro-batch 的前向/后向传播在 stage 间严格顺序执行，backward bubble 只能隐藏其前一个 backward pass 的 recomputation，无法充分利用所有空闲 bubble。

4. **Pipeline 变换带来额外显存压力**：将 forward pass 前移会增加 warmup 阶段的 activation 积累，可能导致 OOM。

5. **Adjusted stage 与 non-adjusted stage 间的计算不均衡**：only 对部分 stage 应用 recomputation 导致工作负载不平衡，non-adjusted stage 出现额外空闲 bubble。

---

## 三、洞察与设计

**关键洞察**：在 1F1B pipeline 中，backward pass 之间的 bubble（backward bubble）可以有效隐藏 recomputation 开销，而 forward pass 之前的 bubble（forward bubble）却完全未被利用。通过 pipeline 变换，可以将 forward bubble 转化为 backward bubble，从而在不增加总执行时间的前提下"隐藏"更多的 recomputation 开销。

基于此洞察，Obscura 提出了一种 **pipeline transformation** 方法：

### Strawman Pipeline

首先构建一个基础方案：对超出显存限制的 stage（adjusted stage）应用 recomputation，然后将 adjusted stage 中 steady phase 的 forward pass 迁移到 warmup phase 的 forward bubble 位置。这样 forward bubble 被 forward pass 填充，原来的 forward bubble 变为 backward bubble，可用于隐藏 recomputation 开销。

### 三大核心组件

1. **Dependency Relaxation（依赖松弛）**：将 adjusted stage 中剩余的 forward pass 左移，与 backward pass 交替排列（类似 1F1B 的 interleaving），打破 stage 间的紧耦合数据依赖。这样 backward bubble 不再受限于只能隐藏紧邻的 recomputation，可以更充分地利用所有空闲 bubble。同时通过 Migration Refinement 减少不必要的 forward pass 迁移，降低 warmup 阶段的 activation 积累。

2. **Swapping-Aware Recomputation（感知 swapping 的重计算策略）**：引入 activation swapping scheme，在 warmup 阶段将 activation 以 micro-batch 粒度（activation block）逐步 evict 到 CPU 内存，在 steady/ending 阶段 reload。建模 recomputation 与 communication 的 trade-off，形式化为优化问题：给定 swapping 配置，最小化总执行时间。通过枚举 swapping 相关变量，求解对应的最优 recomputation strategy。

3. **Partition Adjustment（分区调整）**：通过将 transformer layer 从 adjusted stage 转移到 non-adjusted stage，均衡各 stage 的计算负载。以 attention layer 和 MLP layer 为粒度进行细粒度调整。

### CMB-Identifying 增强

引入 CMB（Cost-effective Memory-saving with low-overhead）recomputation strategy：对于临近显存限制的 stage，先尝试只 recompute cost-effective operator（如 RMSNorm、SiLU、Mul），可减少约 40% activation 且仅增加 2-3% 开销，从而减少需要标记为 adjusted stage 的数量，提升 bubble 隐藏能力。

---

## 四、实现细节

- **基于 DeepSpeed 实现**，替换原生 scheduler 为自定义 Obscura scheduler
- 将 NCCL 同步通信改为异步，并引入同步机制保证执行正确性
- Swapping 操作作为 execution step 集成到 pipeline schedule 中，使用独立 CUDA stream 和手动内存管理实现 swapping 与计算的并行
- Obscura Planner 离线运行：先跑几个 iteration 收集 profiling 数据（operator 的计算时间和显存开销），然后求解优化问题生成配置
- Obscura Runtime 在线执行：根据配置管理分布式部署和模型训练
- 优化问题为整数规划（IP），通过枚举 swapping 变量（λ_k, β）配合 recomputation strategy 求解
- Recomputation strategy 表示为二进制数组 R^{0-1}_{op}，每个 operator 独立决定是否 recompute

---

## 五、实验结果

**平台**：8× NVIDIA A100-SXM-80GB（NVLink 互连，600 GB/s），2× Intel Xeon Platinum 8352S，2.0TB DRAM；附加验证使用 4× A800（无 NVLink，PCIe 4.0）

**模型**：Llama-2 和 GPT-3，参数量 13B/18B/23B/28B；序列长度 4096，micro-batch size 1

**基线**：DAPPLE（1F1B 无 recomputation）、DAPPLE+（全 stage Full recomputation）、OHP-CMB（cost-effective operator recomputation）、BPipe（inter-GPU activation balancing）、Strawman

| 配置 | 模型 | Global Batch Size | Obscura vs DAPPLE+ 加速比 |
|------|------|-------------------|--------------------------|
| 8-stage | Llama-2 18B | 16-64 | 1.28×–1.31× |
| 8-stage | Llama-2 23B | 16-64 | 1.22×–1.31× |
| 8-stage | Llama-2 28B | 16-64 | 1.22×–1.28× |
| 8-stage | GPT-3 18B | 16-64 | 1.28×–1.33× |
| 8-stage | GPT-3 23B | 16-64 | 1.10×–1.32× |
| 8-stage | GPT-3 28B | 16-64 | 1.06×–1.32× |
| 4-stage (A800) | Llama-2/GPT-3 | 32 | 1.27×–1.31× |

**关键发现**：
- Obscura 在 23B 模型上 recomputation overhead 几乎完全被 bubble 隐藏，stage 2 仍保留 bubble 余量
- GPT-3 因 GELU 比 SiLU 更 cost-effective，Obscura 加速比更高（最高 1.33×）
- 在无 NVLink 的低带宽平台上，Obscura 一致获得 27-31% 加速，而 BPipe 因 inter-stage transfer 开销反而比 DAPPLE 慢 11-17%
- 显存利用率方面，Obscura adjusted stage 的显存接近 80GB 上限，实现了高效利用；而 DAPPLE+ 每个 stage 约有 20GB 未使用

---

## 六、批判性分析

1. **实验规模局限于单节点**：所有实验在单节点 8 GPU 上完成。论文声称 "Obscura introduces no communication overhead between stages, it can seamlessly scale to multiple nodes"，但实际多节点环境中跨节点通信延迟、带宽限制、以及与 tensor parallelism 的交互可能带来新问题，未经验证。

2. **模型覆盖面有限**：仅测试了 Llama-2 和 GPT-3 两种架构。MoE（Mixture of Experts）模型的 activation 特征和计算模式显著不同，Obscura 的适用性未知。同样，对于使用 GQA（Grouped Query Attention）等新架构的模型，attention 与 MLP 的计算/显存比例变化可能影响效果。

3. **与其他并行策略的组合未讨论**：实际大模型训练通常使用 3D parallelism（DP + TP + PP）。Obscura 与 tensor parallelism 和 data parallelism 的交互、特别是 TP 引入的 all-reduce 通信与 swapping 的带宽竞争，论文未涉及。

4. **Offline Planner 的适应性**：Obscura Planner 需要先运行几个 iteration 做 profiling，然后离线求解。如果训练过程中 batch size 变化（如 curriculum learning）或 sequence length 变化（如 variable-length inputs），planner 的配置可能需要重新生成，论文未讨论动态适应机制。

5. **28B 模型 + 大 batch size 时加速比下降**：在极端场景（28B, batch=64）下加速比降至 1.22-1.23×，说明 bubble 容量终究有限。论文虽然提到了这一点，但未深入分析瓶颈在哪里以及是否存在进一步优化空间。

6. **与 ZeroBubble 等最新 schedule 的对比缺失**：论文基线中没有包含 ZeroBubble、Hanayo 等更新的 pipeline schedule 方案，这些方案本身就在减少 bubble，可能削弱 Obscura 利用 bubble 隐藏 recomputation 的前提。

---

## 七、AI Infra / MLSys 视角

1. **"隐藏开销于 bubble"的思路具有普适价值**：Pipeline bubble 是分布式训练中的固有浪费，Obscura 将其转化为有用计算的思路可以推广到其他场景——例如在 bubble 中执行 gradient compression、异步 checkpoint 写入、或 prefetch 下一个 batch 的数据预处理。

2. **Pipeline schedule 变换作为优化手段**：Obscura 的 pipeline transformation（forward bubble → backward bubble 转换）是一种新颖的 schedule-level 优化范式。未来可以探索更通用的 pipeline schedule 自动搜索/变换框架，将 recomputation hiding、swapping、partition adjustment 统一到自动化优化中。

3. **与 activation compression 的结合**：Obscura 目前使用 swapping 和 recomputation 两种手段管理 activation。引入 activation compression（如 quantize activation 到 FP8/INT8）可以进一步减少 swapping 的数据量和 recomputation 的需求，是一个自然的延伸方向。

4. **面向推理的 prefill-decode pipeline 启发**：LLM 推理中的 chunked prefill + decode 调度也面临类似的 bubble 问题。Obscura 的 dependency relaxation 和 bubble-filling 思路可能为 inference pipeline schedule 优化提供借鉴。

5. **值得跟进的具体研究问题**：
   - Obscura + ZeroBubble/1F1B-interleave 等新 schedule 的结合
   - 支持 TP+PP 混合并行下的 swapping-aware recomputation 优化
   - 动态 Planner：根据运行时显存和计算 profiling 自适应调整 recomputation strategy

---

## 八、总结

Obscura 提出了一种新颖的 pipeline 训练优化方法，核心思想是通过 pipeline schedule 变换将 forward bubble 转化为 backward bubble，利用后者隐藏 recomputation 开销。结合 dependency relaxation、swapping-aware recomputation 和 partition adjustment 三个组件，在 Llama-2 和 GPT-3 的 13B-28B 模型上实现了相比全 stage recomputation 最高 1.33× 的吞吐提升。该方法的核心优势在于不引入额外的 stage 间通信开销，适用于低带宽互连场景。主要局限是实验仅覆盖单节点、未与最新 pipeline schedule 方案对比、且在模型/batch size 极端增大时 bubble 容量有限导致加速比下降。
