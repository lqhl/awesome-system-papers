# mTuner: Accelerating Parameter-Efficient Fine-Tuning on Multi-GPU Servers with Elastic Tensor

**作者**：Kezhao Huang, Siqi Zhu, Mingshu Zhai, Liyan Zheng, Kinman Lei, Jiaao He, Yuyang Jin, Jidong Zhai（清华大学）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/huang-kezhao
**源文件**：[atc2025-huang-kezhao.pdf](../../papers/atc-2025/atc2025-huang-kezhao.pdf)

---

## 一、背景

大语言模型（LLM）的个性化微调需求日益增长，参数高效微调（PEFT）通过只更新少量 adapter 参数成为主流方法。PEFT 相比全参微调大幅降低了计算和存储开销，但在多 GPU 分布式场景下，内存效率仍是关键瓶颈。现有训练框架（DeepSpeed、Megatron、Torch-FSDP）采用静态内存调度策略，无法适应微调过程中 runtime tensor（激活值、梯度等）高度动态的内存使用模式，导致时间维度上的内存利用率低下。

---

## 二、要解决的问题

1. **时间维度内存利用率低（Temporal Memory Under-utilization）**：runtime tensor 遵循先进后出模式，内存使用呈现 peak-valley 波动。Valley 阶段大量内存闲置，而 peak 阶段内存紧张，现有框架无法利用 valley 阶段的空闲内存。

2. **数据依赖导致通信资源浪费（Data Dependence Waste）**：Tensor Parallelism 中，激活值的通信（all-gather）只能在数据产生后才能开始，导致计算阶段通信资源空闲，而通信阶段又成为瓶颈，无法实现有效的计算-通信重叠。

3. **内存累积策略不灵活导致峰值过高（Inflexible Memory Accumulation）**：现有方法对所有 transformer 层采用统一的内存累积策略，不区分 peak 和 valley 阶段，导致 peak 阶段内存压力过大，限制了 batch size 和吞吐量。

---

## 三、洞察与设计

**关键洞察**：PEFT 中大部分参数是冻结的（frozen），这些冻结参数可以作为"弹性缓冲"——在内存 valley 阶段缓存更多冻结权重以减少后续通信开销，在 peak 阶段则丢弃以释放内存。静态张量（权重）和动态张量（激活值）之间存在可交换性：预取更多权重可以减少激活值的通信范围，从而将原本空闲的通信资源利用起来。

基于这一洞察，论文提出 **Elastic Tensor** 抽象，将所有张量视为可动态调整存储大小的实体，定义四种核心操作：

- **Gather**：通过 all-gather 从远端获取数据，增大本地可用比例（从 1/D 到 100%）
- **Discard**：丢弃已 gather 的数据，释放内存
- **Execute**：执行模型计算，ratio 控制处理的 batch 比例
- **Checkpoint**：保存 runtime tensor 用于梯度计算，ratio 控制保存比例

基于 Elastic Tensor 实现三项优化：

1. **Temporal Memory Adjustment**：在 valley 阶段渐进式（progressive）缓存冻结权重，越接近 valley 缓存比例越高，越接近 peak 则逐步释放。避免一次性缓存 100% 导致快速填满，而是渐进调整实现最优内存利用。

2. **Dependence-relaxed Communication**：在计算 Attention 模块时，插入对后续 MLP 模块权重的预取通信。预取的权重减少了 MLP 阶段激活值通信的范围（如从 8 GPU 降到 4 GPU），从而实现通信资源的高效利用。

3. **Adaptive Data Accumulation**：对深层（靠近 loss 的层）优先执行部分 batch 的前向+反向计算，缩短激活值在内存中的驻留时间，降低 peak 内存消耗。公式为 H_new = (l/L)(b/B)H + (1-l/L)H，通过调整层数 l 和 batch 大小 b 灵活控制峰值。

---

## 四、实现细节

- **系统实现**：基于 PyTorch 和 Torch-FSDP 构建，通过 module wrapping 在 embedding、MLP、attention 等粒度分区权重，使用 pre/post-forward/backward hooks 在运行时执行 Elastic Tensor 操作。无需用户修改模型代码。

- **调度搜索**：采用 profiling-based 方法测量各模块在不同分区策略下的时间和内存开销，然后用 **Dual-memory Dynamic Programming** 搜索最优调度。DP 状态同时追踪 peak memory 和 valley memory，搜索每层的最优实现选择（并行策略 + 权重/激活存储比例）。

- **搜索空间剪枝**：只考虑存储比例为 1/N（N 为整数）的情况，因为通信效率的显著变化只发生在参与设备数变化时。内存消耗离散化为整数值。

- **搜索开销**：7B 模型约 20 秒，70B 模型约 148 秒，相比数小时的微调时间可忽略。

- **开源**：https://github.com/xxcclong/mTuner

---

## 五、实验结果

**实验平台**：
- PCIe 服务器：8× NVIDIA A100-PCIe-40GB
- NVLink 服务器：4 台 × 8× NVIDIA H100-SXM-80GB

**模型**：Llama 2 系列（7B/13B/30B/70B），LoRA 微调，序列长度 1024–8192。

**基线**：Torch-FSDP@2.1.0、DeepSpeed@0.15、Megatron@0.9.0、Flux

| 配置 | 平均加速 | 最大加速 |
|------|---------|---------|
| PCIe 服务器 | 28.3% | 51.2% |
| NVLink 服务器 | 14.5% | 24.8% |

**关键发现**：
- 长序列（≥4096）场景下平均加速 34%，因为 batch size 更小、激活内存占比更大，mTuner 优势更明显
- PCIe 服务器加速更显著（28.3% vs 14.5%），因为通信瓶颈更严重
- 对 Llama 2 13B 在 PCIe 上相比 Torch-FSDP 达到 4.15× 加速
- Progressive valley filling 将 80.2% 权重优化到 25% 弹性比例，通信时间降低 41%
- Adaptive data accumulation 使 70B 模型 batch size 提升，吞吐量提升 12%
- Activation checkpointing 将激活内存降低 10×

---

## 六、批判性分析

1. **NVLink 场景收益有限**：在 NVLink 服务器上平均仅 14.5% 加速，而论文标题和摘要突出了 51.2% 的最大值（PCIe best case）。实际生产环境中高端训练集群多采用 NVLink/NVSwitch 互联，论文的核心优势在这些场景中大打折扣。

2. **仅评估 LoRA 单一 PEFT 方法**：虽然论文声称 Elastic Tensor 适用于各种 PEFT 方法（QLoRA、AdaLoRA、BitFit 等），实验仅使用 LoRA。不同 PEFT 方法的冻结参数比例和计算模式差异显著，泛化性缺乏实证支持。

3. **缺少端到端微调效果验证**：论文仅报告吞吐量指标，未验证 adaptive data accumulation 的 batch splitting 是否在实际任务上与标准训练保持完全一致的收敛行为。虽然理论上梯度累积等价，但实际数值精度和实现细节可能引入差异。

4. **单服务器 PCIe 场景的实用性存疑**：8×A100-PCIe-40GB 的配置在实际中较少见（PCIe 版 A100 多用于推理而非训练），且 40GB 显存对 70B 模型微调本身就不够理想。

5. **DP 搜索的可扩展性**：Dual-memory DP 的状态空间为 O(L × M² × N)，70B 模型搜索需要 148 秒。论文未讨论当模型进一步扩展（如 405B）或多节点场景下搜索时间的增长趋势。

6. **与更新的系统缺少对比**：基线中 Megatron@0.9.0 和 DeepSpeed@0.15 并非最新版本，且缺少与 FSDP2、ColossalAI 等更新系统的对比。

---

## 七、AI Infra / MLSys 视角

1. **冻结参数的"弹性缓冲"思想可迁移到推理场景**：LLM 推理中的 KV cache 同样存在动态增长和 peak-valley 模式。Elastic Tensor 的 progressive caching 策略可以启发 KV cache 的动态管理——在请求少时预缓存更多模型权重或 KV 数据，请求多时释放以容纳更多并发。

2. **Dependence-relaxed communication 对训练通信优化的启发**：用静态数据（权重）的预取来换取动态数据（激活值）通信范围的缩小，本质是一种"空间换时间+带宽"的 trade-off。这一思路可以推广到 MoE 训练中 expert 权重的预取，或 pipeline parallelism 中的跨阶段数据搬运。

3. **Adaptive data accumulation 与 micro-batching 的关系**：论文的分层 batch splitting 策略实质上是对不同层使用不同的 micro-batch size，这与 pipeline parallelism 中的 1F1B 调度思想一脉相承，但在单节点 FSDP 场景下实现。值得探索在 pipeline + tensor + data 混合并行中的联合优化。

4. **值得跟进的方向**：
   - 将 Elastic Tensor 扩展到多节点训练（跨节点通信开销更大，优化空间可能更大）
   - 与 prefix caching / continuous batching 结合，探索推理场景下的 Elastic Tensor
   - 在 MoE 模型上验证：MoE 的 expert 天然是稀疏激活的，冻结的 non-active expert 可以作为弹性缓冲

---

## 八、总结

mTuner 提出 Elastic Tensor 抽象，通过四种操作（Gather/Discard/Execute/Checkpoint）及可调比例，实现对静态和动态张量的统一动态管理。核心贡献在于利用 PEFT 冻结参数的特性，在内存 valley 阶段缓存权重以减少通信，在 peak 阶段释放以扩大 batch size，并通过预取权重放松激活值的数据依赖。在 PCIe 服务器上效果显著（平均 28.3%），NVLink 场景收益偏小（14.5%）。系统适用于通信瓶颈严重、内存受限的 PEFT 微调场景。
