# GPREEMPT: GPU Preemptive Scheduling Made General and Efficient

**作者**：Ruwen Fan, Tingxu Ren (Tsinghua University); Minhui Xie (Renmin University of China); Shiwei Gao, Jiwu Shu, Youyou Lu (Tsinghua University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/fan
**源文件**：[[atc2025-fan.pdf]]

---

## 一、背景

GPU 已成为计算机视觉、机器学习、图形渲染和科学计算等领域的核心计算资源。在数据中心场景中，GPU 工作负载通常具有波动性——高峰和低谷交替出现。为提高资源利用率，业界普遍将不同 SLA 需求的任务共置（co-locate）在同一 GPU 上：延迟敏感型（LC）任务（如实时推荐、自动驾驶推理）与尽力而为型（BE）任务（如离线推理、数据分析）混合运行。

然而，当 LC 任务到达时，BE 任务可能仍占用 GPU 资源，导致 LC 任务的 SLA 被违反。因此，GPU 上的抢占调度机制成为关键需求。

---

## 二、要解决的问题

现有 GPU 抢占策略分为两类，各有根本性缺陷：

1. **Wait-based 抢占**（如 EffiSha、block-level preemption）：等待 BE 任务的线程块执行完毕后再释放资源。通用性好，但抢占延迟高（block-level 可达 5ms），且受最慢 BE 任务影响。
2. **Reset-based 抢占**（如 REEF、Chimera）：直接终止正在运行的 kernel，利用 DNN kernel 的幂等性重新计算。延迟低，但**只适用于幂等 kernel**——科学计算、图计算等非幂等负载无法使用，CUDA Graph 也增加了重置复杂度。

核心矛盾：**通用性（generality）与低延迟抢占（efficiency）不可兼得**。

---

## 三、洞察与设计

**关键洞察**：NVIDIA 开源 GPU 驱动中存在一个未公开文档化的硬件时间片分配机制（timeslice allocation）——当多个独立任务在同一 GPU 上运行时，硬件会按预设时间片轮转执行各任务。通过缩短 BE 任务的时间片至极短（如 200µs），可以迫使 BE 任务在短时间内让出 GPU 资源，从而间接实现 GPU 上的 yield 原语和 context-switch 抢占。

基于这一洞察，GPREEMPT 的设计包含两个核心机制：

### 1. Timeslice-based General Preemption

- 将 BE 任务的时间片设为极短（~200µs），LC 任务的时间片设为远超其生命周期的值
- 当 LC 任务到达时，BE 任务在消耗完当前时间片后被动让出 GPU（平均等待 t₁/2，最大 t₁ ≈ 160µs）
- LC 任务执行完毕后自动释放剩余时间片，GPU 立即切换回 BE 任务
- 当只有 BE 任务运行时，GPU 不会在同组任务间强制切换，不引入额外开销

### 2. Hint-based Pre-preemption

GPU 任务执行前必须经历数据准备阶段（数据预处理 + CPU→GPU 数据传输，通常数百µs）。GPREEMPT 利用这个阶段作为抢占提示信号：

- **Overlap with Data Preparation**：在 LC 任务的数据准备阶段就注入 preemption kernel，消耗 BE 任务的时间片，使 context-switch 与数据准备并行执行，隐藏切换开销
- **Scheduled Pre-preemption**：用户指定预期 GPU 需求时间，GPREEMPT 通过后台线程在调度时间点启动 preemption kernel，避免过早抢占导致 GPU 空闲浪费
- 使用 GDRCopy 实现 CPU→GPU 直接内存访问，通知 preemption kernel 完成（延迟约 1µs）

---

## 四、实现细节

GPREEMPT 由两部分组成：

1. **GPU 驱动修改**：修改 NVIDIA 开源驱动代码，暴露时间片重配置接口。在 NVIDIA 平台上利用驱动内部的时间片分配机制；在 AMD 平台上，RDNA3+ 使用 MES（Micro Engine Scheduler）硬件调度器实现类似功能，早期 AMD GPU 通过修改 ROCm 驱动的调试机制手动切换上下文。

2. **用户态 API**：提供即用 API，可直接集成到用户程序中，无需修改计算 kernel 代码。

**关键数字**：
- NVIDIA A100 GPU：每个 SM 有 164KB 共享内存 + 64K 个 32-bit 寄存器，单 SM 上下文 420KB，108 个 SM 共约 44.3MB 上下文
- 内存带宽 1.1TB/s 下，context-save 约 40µs 完成
- 总 context-switch 开销约 100µs

---

## 五、实验结果

**实验平台**：Intel Xeon Gold 5420+ CPU, 256GB DRAM, NVIDIA A100-40GB GPU / AMD Instinct MI100 GPU

**工作负载**：7 种负载，涵盖 DNN 推理（VGG, ResNet, DenseNet, BERT, Inception）、科学计算（miniWeather）和图计算（BFS, SSSP, PageRank, CC）

| 指标 | NVIDIA A100 | AMD MI100 |
|------|-------------|-----------|
| LC 任务平均延迟增加（vs LC-only） | 2.4% | 10% |
| 总吞吐量（vs NP 基线） | 88.6% | 82.2% |

**与各基线对比（NVIDIA 平台，LC 延迟增加 vs LC-only）**：

| 方法 | 平均延迟增加 |
|------|-------------|
| No Preemption (NP) | 58.4% |
| Sequential (SEQ) | 96.3% |
| Block-level Wait (WB) | 15.3% |
| **GPREEMPT** | **2.4%** |

**关键结果**：
- 单 LC 任务负载下，GPREEMPT 平均抢占延迟 < 40µs
- 多任务共置场景（10 个并发任务），GPREEMPT 引入的额外延迟仅约 500µs
- Hint-based pre-preemption 平均减少 160µs 延迟
- 数据准备时间超过 100µs 时，额外延迟稳定在 40µs 以下
- BE 任务吞吐量比 block-level wait-based 提高 17%-26%
- 非幂等负载（科学计算 Y、图计算 Z）上，GPREEMPT 正常工作，而 reset-based 方法完全不适用

---

## 六、批判性分析

1. **硬件依赖性风险**：核心机制依赖 NVIDIA 开源驱动中未文档化的时间片分配接口。这个接口可能在未来驱动版本中被修改或移除，且 NVIDIA 可能不会对此提供兼容性保证。论文未讨论这一风险。

2. **实验规模有限**：仅在单 GPU（A100 / MI100）上评估，未涉及多 GPU 或生产级集群场景。现代数据中心的 GPU 共享通常涉及 MIG、vGPU 等虚拟化技术，GPREEMPT 与这些技术的兼容性未被讨论。

3. **工作负载代表性不足**：LC 任务仅涵盖经典 CNN（VGG、ResNet）和少量模型，缺少 LLM 推理（自回归解码、prefill/decode 混合）等当前最重要的 GPU 推理负载。论文引用了 MuxServe 等 LLM serving 工作，却未在实验中覆盖。

4. **context-switch 开销的乐观估计**："随着 GPU 内存带宽提升，开销会继续减小" 的论述忽略了 GPU SM 数量和寄存器文件同样在增长——H100 有 144 个 SM，B200/GB200 更多，上下文总量也在增加，净效果并不确定。

5. **对 CUDA Graph 的讨论不充分**：论文指出 reset-based 方法难以处理 CUDA Graph，暗示 GPREEMPT 能处理，但未明确展示 CUDA Graph 场景下的实验结果。

6. **scheduled pre-preemption 需要用户预估时间**：这要求用户对数据准备时间有准确预估，论文未讨论预估不准确时的性能退化。

---

## 七、AI Infra / MLSys 视角

1. **LLM Serving 的直接应用价值**：LLM serving 中 prefill（LC）和 decode（BE）的混合调度是当前热点问题。GPREEMPT 的 timeslice-based 抢占可以作为 prefill 优先调度的底层机制，避免长 decode 批次阻塞新到的 prefill 请求，且不需要 kernel 幂等性假设。

2. **与 MIG/MPS 的互补性**：NVIDIA MPS 允许多进程共享 GPU 但缺乏优先级抢占能力，GPREEMPT 的时间片机制可以为 MPS 环境提供优先级调度支持。这是一个值得探索的集成方向。

3. **推理与训练混合调度**：数据中心中训练和推理任务混部是趋势（如 DeepBoot），GPREEMPT 提供了一种透明的、不需要修改 kernel 的抢占机制，可以作为 elastic scheduling 的基础设施。

4. **可跟进的研究方向**：
   - 将 GPREEMPT 扩展到 LLM serving 场景（prefill/decode 调度、投机解码中的 draft/verify 优先级）
   - 探索与 GPU 虚拟化（MIG, vGPU）的集成
   - 研究在多租户 GPU 集群中的公平性和 QoS 保证
   - 结合 attention kernel 的分块特性（FlashAttention 的 tile-based 执行），设计更细粒度的推理抢占策略

---

## 八、总结

GPREEMPT 通过发掘 GPU 驱动中未公开的时间片分配机制，首次在商用 GPU 上实现了通用的 context-switch 抢占调度，打破了 wait-based（通用但慢）和 reset-based（快但受限于幂等性）之间的权衡。在 NVIDIA A100 上实现了 < 40µs 的抢占延迟，同时保持 88.6% 的总吞吐量。其主要局限在于依赖未文档化的驱动接口、实验规模有限，以及缺少对 LLM 等当代 AI 负载的验证。
