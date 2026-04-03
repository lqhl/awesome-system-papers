# Colocating ML Inference and Training with Fast GPU Memory Handover

**作者**：Jiali Wang, Yankui Wang, Mingcong Han, Rong Chen（上海交通大学并行与分布式系统研究所）
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/wang-jiali
**源文件**：[[atc2025-wang-jiali.pdf]]

---

## 一、背景

GPU 是 MLaaS 平台的核心加速器，但在服务推理任务时利用率极低（常低于 15%）。推理工作负载具有动态性和突发性（峰值可达平均的 50 倍），为满足严格的延迟 SLO（如 100ms），平台通常为推理任务过度配置 GPU 资源，导致计算资源和显存的严重浪费。

将推理与训练任务混部（colocation）是提升 GPU 利用率的常见策略，Google Kubernetes Engine 和腾讯云 qGPU 等产品已在实践。然而，推理和训练都是显存密集型任务：推理需要存储模型和 KV cache，训练需要存储模型参数、优化器状态和中间结果。GPU 显存有限（通常数十 GB），如何在两者之间高效共享显存是核心挑战。

---

## 二、要解决的问题

现有混部方案均存在显著不足：

1. **时间分片（Temporal Sharing）**：如 PipeSwitch，推理与训练交替使用 GPU，但上下文切换开销巨大——推理模型重新加载可达数秒，违反 SLO；训练任务被频繁抢占导致饥饿甚至失败；推理服务期间 GPU 空闲资源被浪费。

2. **静态显存分区（Static Partition）**：固定划分显存给推理和训练，但推理工作负载动态波动，静态分配无法匹配：低负载时显存浪费，高负载时显存不足导致模型换入换出（cold start），SLO 合规率低至 25%。

3. **动态显存换出（Dynamic Swapping / Unified Memory）**：通过 GPU 与主机内存之间的数据搬移提供"无限"显存，但 PCIe 带宽有限（比 GPU 显存慢 60 倍），即使在低负载下 UM 方案也导致推理 SLO 降级 93%。

核心矛盾：推理需要毫秒级响应且显存需求动态波动，训练占用大量显存且中断代价高——如何在毫秒级时间尺度内完成显存从训练到推理的移交（handover），同时不破坏训练状态？

---

## 三、洞察与设计

**关键洞察**：训练 batch 的执行可以清晰地分为两个阶段——梯度计算（Gradient Computation, GC）和模型更新（Model Updating, MU）。GC 阶段占训练时间的 95% 以上但不修改模型参数，MU 阶段需要原子执行但通常不到 10ms。因此，在 GC 阶段可以安全地丢弃当前 batch 来立即释放显存，而 MU 阶段即使需要等待也只是短暂延迟。结合训练任务的弹性特性（通过调整 batch size + gradient accumulation 可以在不改变有效 batch size 的前提下动态控制显存消耗），GPU 显存可以在推理和训练之间毫秒级动态共享。

基于此洞察，SIRIUS 系统的设计围绕三个关键技术展开：

### 1. Instant Memory Adjustment（§4.1）

SIRIUS 利用软件 GPU kernel 队列管理技术，将训练 operator 放入软件队列而非直接提交给 GPU 硬件。当需要调整显存时：
- 禁止新 operator 入队
- 等待 GPU 上少量正在执行的 kernel 完成（训练 kernel 通常很短）
- 丢弃软件队列中的 operator，从而完整丢弃当前训练 batch
- 遍历计算图释放中间结果对应的显存
- 重新配置 batch size 后恢复训练（被丢弃 batch 的数据会被重新处理）

对于多 GPU 数据并行训练，SIRIUS 额外处理 NCCL AllReduce 死锁问题：不同 GPU 上训练进度可能不一致，导致 NCCL kernel 数量不匹配。SIRIUS 通过设置 NCCL abort flag 终止 in-flight NCCL kernel，并在下一轮迭代前重置 NCCL counter，避免连接重建的巨大开销。

### 2. Safe Memory Handover（§4.2）

SIRIUS 维护推理和训练共享的显存池，使用 GPU Virtual Memory Management (VMM) 实现灵活的内存页映射。关键设计：
- 绕过 PyTorch 的显存缓存机制和低效的 cudaMalloc/cudaFree
- 维护显存所有权机制：训练释放的显存仍属于训练任务，只有在显存调整发生时才显式移交给推理任务，避免异步执行导致的数据污染（训练 operator 尚在 GPU 上执行但显存已被推理任务分配）
- 移交的显存先填零再分配给推理任务，保护数据隐私

### 3. SLO-aware Memory Reallocation（§4.3）

为避免频繁的显存抖动（thrashing），SIRIUS 采用粗粒度的显存再分配策略：
- **Liveness time (T_idle)**：空闲模型超过 T_idle 未被请求才释放显存
- **Watermark (W)**：控制最小再分配粒度，累积释放的模型显存达到 2W 阈值才真正移交给训练任务，同时保留 W 大小的显存作为推理缓冲
- 使用 M/G/1 排队模型对推理 SLO 合规率建模，离线搜索 T_idle 和 W 的最优配置
- 当训练已达调整极限时（batch size 为零），回退到模型换入换出策略

---

## 四、实现细节

- **推理引擎**：从零构建，约 6,000 行 C++ 代码，后端使用 TVM 处理 DNN 模型，vLLM 处理 LLM
- **训练插件**：扩展 PyTorch，约 5,000 行 Python + C++ 代码
- **公共组件**：GPU 显存和计算资源管理，约 6,000 行 C++ 代码
- **显存管理**：使用 CUDA VMM API 维护共享显存池，推理任务通过直接切割连续内存区域分配，训练任务通过映射可能不连续的内存页形成独立连续内存区域，避免碎片化。调整时仅更新页所有权，延迟实际 unmap 操作
- **SM 动态共享**：使用 SM mask 机制为推理和训练动态分配 Streaming Multiprocessors，推理优先使用所有 SM，训练使用剩余 SM
- **Batch 分配**：多 GPU 场景下通过在线 profiling 动态分配数据样本到各 GPU，平衡训练时间

---

## 五、实验结果

**实验平台**：2× Intel Xeon Gold 6138 (80 cores)，503GB DRAM，4× NVIDIA Tesla V100 (16GB)，NVLink 互联，PCIe 3.0 x16；Ubuntu 20.04，CUDA 11.6，PyTorch 2.1.2

**对比方案**：TaskSwitch（类 PipeSwitch 时间分片）、SP-50/SP-75（静态分区）、UM+MPS（Unified Memory + 多进程服务）、Infer-Only（仅推理基线）

### 单 GPU 总体性能

| 指标 | SIRIUS vs TaskSwitch | SIRIUS vs SP-50 | SIRIUS vs SP-75 | SIRIUS vs UM+MPS |
|------|---------------------|-----------------|-----------------|-------------------|
| 推理 P99 延迟 | 平均 12.6× 改善 | 平均 261.9× 改善 | 平均 64.3× 改善 | 平均 3,100× 改善 |
| 推理 SLO 合规率 | 平均 +72.6% | 平均 +54.6% | 平均 +8.2% | 平均 +92.6% |
| 训练吞吐量 | 平均 4.6× | — | — | — |

- SIRIUS 达到 Infer-Only 方案 95.3%（最高 98%）的推理 SLO 合规率
- 丢弃 batch 导致的训练计算浪费仅 1.4%
- 动态 batch size 不影响训练收敛：Swin-T 在 CIFAR-100 上达到 75% 准确率，平均 210.6 epoch vs 标准训练 206.2 epoch

### 多 GPU（4 GPU）性能

推理 P99 延迟和 SLO 合规率分别平均改善 558.4× 和 43.0%，训练吞吐量平均改善 6.1×

### 显存移交分解

| 组件 | Naive 方案 | SIRIUS |
|------|-----------|--------|
| 训练调整时间 | >250ms（单 GPU），>1s（多 GPU） | <5ms（121× 加速） |
| 显存分配时间 | ~34ms | ~0.8ms（89.2× 加速） |
| 模型加载等待 | 基线 | 降低 3.7× |
| 总体显存再分配 | 基线 | 148× 加速 |

### LLM 实验（NVIDIA A100 80GB）

使用 Llama2-13B 推理 + Qwen2-0.5B 训练，BurstGPT trace：
- vs SP-50：TTFT SLO 合规率 +40%，TBT SLO 合规率 +7%
- vs SP-75：训练吞吐量 1.5×
- 达到 Infer-Only 的 89%（TTFT）和 91%（TBT）SLO 合规率

---

## 六、批判性分析

1. **实验硬件老旧且规模小**：主要实验在 V100 16GB 上进行，这是 2017 年的 GPU。现代 MLaaS 平台普遍使用 A100/H100（80GB+），显存压力和混部场景的特征可能显著不同。唯一的 A100 实验仅覆盖 LLM 场景的单 GPU 配置，缺乏说服力。

2. **推理模型规模偏小**：实验中的 DNN 推理模型（ResNet-152 的 319MB、DistilGPT2 的 317MB）远小于当前主流部署模型。56 个模型实例通过 round-robin 复制 6 个基础模型生成，这种设置是否反映真实生产环境的模型多样性值得质疑。

3. **训练任务设置简单**：仅使用单一训练任务（Swin-T 或 Qwen2-0.5B），且仅支持数据并行。论文在 Discussion 中承认不支持 pipeline/tensor parallelism，但这恰恰是大模型训练的标准配置。对于需要混合并行的训练任务，SIRIUS 的核心机制（丢弃 batch + 调整 batch size）的可行性未被验证。

4. **SLO 定义宽松**：SLO 设为模型独立执行时间的 4 倍，这对于毫秒级推理模型来说相当宽松（如 EfficientViT 的 SLO 为 14.8ms）。在更严格的 SLO 约束下，SIRIUS 的 5ms 训练调整时间 + 模型加载时间是否仍然可接受？

5. **排队模型假设过强**：M/G/1 排队模型假设推理模型同质且相互独立，但实际生产环境中模型大小、执行时间差异巨大。SKEWED 工作负载虽然使用了 Zipfian 分布，但模型异构性仍未被充分考虑。

6. **Gradient Accumulation 的隐含代价**：论文强调通过 gradient accumulation 保持有效 batch size 不变来保证收敛，但频繁调整 batch size 意味着更多的小 batch 迭代和更多的 gradient accumulation 步骤，这会增加训练的 wall-clock time。论文仅报告了 epoch 数相近，但未明确报告实际训练时间的影响。

---

## 七、AI Infra / MLSys 视角

### 启发与借鉴价值

1. **训练任务的两阶段特性**是一个重要的系统观察：GC 阶段占 95%+ 时间但不修改状态，MU 阶段短暂但需原子执行。这个特性不仅适用于混部场景，对训练容错（checkpoint 时机选择）、弹性训练（资源调整时机）等问题同样有指导意义。

2. **软件 kernel 队列 + 即时丢弃**的思路为 GPU 任务的细粒度抢占提供了新范式。与 Reef/XSched 等 preemption 工作互补，区别在于 SIRIUS 是应用层面的协作式抢占，而非 runtime 层面的强制抢占。

3. **显存所有权机制**解决了共享显存池中异步执行导致的数据污染问题，这个问题在任何需要多个 workload 共享 GPU 显存的场景中都可能出现。

### 可迁移的技术

- **NCCL abort + counter reset** 机制：对于任何需要中断分布式训练通信的场景（如弹性训练的节点加入/退出、故障恢复）都有参考价值，避免了代价高昂的 NCCL 连接重建。
- **VMM-based 显存池**：使用 CUDA VMM API 实现灵活的显存管理，绕过 PyTorch 缓存和 cudaMalloc，这种思路可用于 LLM 推理中 KV cache 与模型权重的动态显存分配。

### 值得跟进的研究方向

1. **混合并行训练的弹性显存调整**：当前仅支持数据并行，扩展到 pipeline/tensor parallelism 需要解决 reshard 和 reshape 问题，这与 Oobleck、Tenplex 等工作的方向一致。
2. **Prefill-Decode 分离架构下的混部**：现代 LLM 推理趋向 disaggregated architecture（如 Mooncake），prefill 和 decode 阶段的显存特征不同，混部策略需要重新设计。
3. **多租户推理 + 训练的集群级调度**：当前 SIRIUS 聚焦单节点多 GPU，如何在集群层面协调多个推理服务和多个训练任务的显存共享是自然的扩展方向。

---

## 八、总结

SIRIUS 通过利用训练任务的弹性特性（GC/MU 两阶段 + batch size 动态调整 + gradient accumulation），实现了推理与训练之间毫秒级的 GPU 显存移交，在优先保障推理 SLO 的同时利用剩余资源提升训练吞吐量。其核心创新在于即时训练 batch 丢弃（5ms vs 250ms+）、安全显存移交（所有权机制防数据污染）和 SLO 感知的粗粒度再分配（排队模型驱动配置）。系统在多种工作负载下显著优于现有方案，但实验规模偏小、仅支持数据并行、模型规模与现代生产环境存在差距，向大规模混合并行训练和更大模型的扩展仍待验证。
