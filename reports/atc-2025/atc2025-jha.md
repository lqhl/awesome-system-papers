# HyCache: Hybrid Caching for Accelerating DNN Input Preprocessing Pipelines

**作者**：Keshav Vinayak Jha (Independent Researcher), Shweta Pandey (Indian Institute of Science), Murali Annavaram (University of Southern California), Arkaprava Basu (Indian Institute of Science)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/jha
**源文件**：[[atc2025-jha.pdf]]

---

## 一、背景

DNN 训练的端到端性能不仅取决于模型权重的训练时间，还取决于数据加载和预处理的时间。随着 GPU 硬件的快速发展，训练计算速度大幅提升，瓶颈逐渐转移到 CPU 端的输入预处理流水线（input preprocessing pipeline）。该流水线需要对每个训练样本进行一系列转换操作（如 JPEG 解码、颜色空间转换、归一化、数据增强等），将原始数据转化为结构化张量供 GPU 消费。

研究表明，预处理延迟可能占据高达 65% 的 epoch 时间。Google 报告显示 62% 的训练流水线每个 epoch 至少因输入流水线延迟停顿 1ms，16% 停顿超过 100ms。在任意时刻，约 10% 的训练任务在等待预处理完成。

---

## 二、要解决的问题

现有的缓存方案（如 tf.data、MinIO、PRESTO、Cachew）通过缓存中间预处理结果来加速流水线，但存在四个关键限制：

1. **全有或全无（All-or-nothing）**：只有当某个 pipeline stage 的全部输出能完全放入缓存时才缓存，否则完全放弃。这对于解码后数据量膨胀的步骤（如 JPEG 解码）尤其不利。
2. **内存与存储不协调**：要么只用内存缓存，要么只用存储缓存，无法协调使用两者，导致资源利用不充分，且可能在 OS page cache 中产生重复数据。
3. **同一步骤限制**：即使同时使用内存和存储缓存，也只能缓存同一个 pipeline step 的输出，无法根据不同层级的延迟特性分别选择最优步骤。
4. **缺乏工作内存估算**：没有自动估算预处理所需工作内存的机制，用户需手动指定缓存大小，容易导致 OOM 或缓存利用不足。

---

## 三、洞察与设计

**关键洞察**：预处理流水线中不同步骤的输出大小和计算成本差异显著，且内存和存储的访问延迟差异意味着同一步骤在不同存储层的缓存收益可能完全不同——因此应该允许对不同步骤在不同存储层进行部分缓存（partial caching），并通过统一的优化框架协调内存和存储的缓存决策，而非简单地选择一个步骤全量缓存。

基于此洞察，HyCache 的核心设计包括：

- **Partial Caching**：允许缓存任意比例的中间张量，而非要求全部放入缓存。即使在资源紧张的情况下，也能部分复用计算结果。
- **Exclusive Caching**：确保内存和存储中缓存的数据互斥，避免重复，最大化总缓存容量利用。
- **Coordinated Tier-aware Caching**：根据重计算成本、输出大小和访问延迟，通过 ILP（整数线性规划）自动决定哪些步骤缓存在内存、哪些缓存在存储，不同层级可缓存不同步骤。
- **Automatic Working Memory Estimation**：自动估算流水线运行所需的工作内存（考虑 batching、threading、buffer 管理），仅将剩余内存分配给缓存。

---

## 四、实现细节

HyCache 基于 NVIDIA DALI 实现，封装为 hcLib 库，用户只需继承 `BasePipeline` 并创建 `HyCache` 对象即可，代码改动极少。

**Step Filter**：分析流水线中每个步骤的输入/输出维度，当连续步骤产生相同大小的输出时，只保留最后一个步骤作为缓存候选（filter_steps）。

**Profiler**：在第一个 epoch 的前 1% 数据上进行 profiling，对每个 filter_step 计算：
- $C_M^i$：缓存在内存中节省的时间（= 从原始数据预处理的时间 - 从内存获取的时间）
- $C_D^i$：缓存在存储中节省的时间
- $Sz_i$：平均输出张量大小

**Fetcher 调优**：通过二分搜索自动确定最优 fetcher 数量，在预处理吞吐量和工作内存消耗之间取得平衡。

**ILP 求解器**：核心优化问题为：
- 目标：$\text{maximize} \sum N_M^i \cdot C_M^i + \sum N_D^i \cdot C_D^i$
- 约束：内存预算 $\sum N_M^i \cdot Sz_i \leq M$，存储预算 $\sum N_D^i \cdot Sz_i \leq D$，总缓存张量数 $N_{optM} + N_{optD} \leq N$

**工作内存估算**：$\text{working\_mem} = (\max(Sz_i) \times bs \times \text{prefetch\_depth}) + (\text{mem\_per\_fetcher} \times \max(F_i)) + \text{metadata}$

**Pipeline 生成**：根据 ILP 结果自动生成多条流水线，分别从内存缓存、存储缓存或原始数据中获取张量，通过条件执行逻辑跳过已缓存步骤。缓存在第一个 epoch 期间填充。

---

## 五、实验结果

**实验平台**：AMD EPYC 7313 16-Core CPU，512 GB DDR4，2 TB Samsung 980 PRO SSD，Python 3.10，NVIDIA DALI v2.1。

**Workloads**：6 个预处理流水线（Image Recognition×2、CubePP、Segmentation、Object Detection、Voice Recognition），覆盖计算机视觉和语音识别。

**主要结果**：

| 对比维度 | 相对 MinIO | 相对 PRESTO |
|----------|-----------|------------|
| 预处理流水线吞吐量 | 1.11×–5.3× | 1.24×–2.26× |
| 端到端训练加速 | 1.05×–1.67× | 1.05×–1.47× |
| 远程存储场景 | 1.11×–10.1× | 1.19×–9.28× |

- Voice pipeline 受益最大，协调缓存节省了超过 80% 的计算时间
- IR-1/IR-2 分别节省 58%/42% 的重计算时间
- 不同硬件配置下（C1–C5），HyCache 一致优于 baseline
- Profiling 开销仅占一个 epoch 预处理时间的 2.5%–18.2%，在数百个 epoch 的训练中可忽略
- ViT-LoRA 等计算密集型模型端到端加速较小（1.05×），因瓶颈在 GPU 端

---

## 六、批判性分析

1. **端到端加速有限**：预处理吞吐量提升显著（最高 5.3×），但端到端训练加速最高仅 1.67×，多数模型在 1.05×–1.3× 之间。论文承认这是因为 GPU 训练本身是瓶颈，但这也意味着对于现代大模型训练（以 GPU 计算为主导），HyCache 的实际收益可能非常有限。

2. **评估规模偏小**：所有实验在单机单 GPU 或少量 GPU 上完成。分布式场景仅做了定性讨论（Section 7.9），没有实际的多节点实验验证。对于大规模分布式训练（数十到数百节点），ILP 求解的可扩展性、缓存一致性、异构硬件适配等问题未经验证。

3. **Workload 代表性不足**：6 个 pipeline 中大多数是经典 CV 任务（ResNet50、MobileNet、YoloV5），没有涉及当前主流的大语言模型训练或多模态模型训练场景。这些场景的预处理特征（tokenization、数据混合、动态 padding）与图像 pipeline 差异较大。

4. **PRESTO 对比不完全公平**：论文使用了 3× 更快的 SSD（Samsung 980 PRO），而 MinIO 原论文使用较慢的 SSD。作者承认这减少了 MinIO 的提升空间，但同样可能影响 PRESTO 的表现。此外，PRESTO 的重新实现在 DALI 上完成，可能与原始实现存在差异。

5. **ILP 求解依赖静态 profiling**：profiling 仅在第一个 epoch 的 1% 数据上执行，假设整个数据集的特征与此子集一致。对于数据分布不均匀的数据集（如长尾分布），这个假设可能不成立。此外，训练过程中硬件负载的变化（如其他进程竞争 CPU/内存）未被考虑。

6. **仅支持离线步骤缓存**：HyCache 明确排除了 online（随机）步骤的缓存。虽然这是合理的设计选择（保持数据增强的随机性），但论文没有讨论在 offline 步骤占比很小的 pipeline 中 HyCache 的价值会如何退化。

---

## 七、AI Infra / MLSys 视角

1. **预处理瓶颈在 LLM 时代的新形态**：虽然本文聚焦于 CV/语音的预处理 pipeline，但预处理瓶颈在 LLM 训练中同样存在——大规模 tokenization、数据去重、质量过滤等。HyCache 的分层缓存思路可以迁移到文本预处理场景，特别是在 pre-tokenized 数据的内存/存储分层管理上。

2. **ILP 优化框架的通用性**：HyCache 的 ILP 公式化方法可以推广到其他资源分配问题，如 KV cache 的分层管理（GPU HBM + CPU DRAM + SSD）、模型并行中的 activation checkpoint 策略选择等。核心思想是将异构存储的成本-收益建模为整数规划问题。

3. **与推理系统的关联**：在 LLM 推理系统中，prefix caching、KV cache 管理同样面临"缓存什么、缓存在哪里"的决策问题。HyCache 的 partial + exclusive + coordinated 缓存策略对 vLLM/SGLang 等系统的多层 KV cache 管理有参考价值。

4. **值得跟进的方向**：
   - 将 HyCache 的缓存策略扩展到多节点分布式训练，研究跨节点缓存共享和协调
   - 探索在线自适应缓存策略，根据训练过程中的实时反馈动态调整缓存分配
   - 将分层缓存思想应用于 LLM 推理中的 KV cache 管理，结合 ILP 优化 HBM/DRAM/SSD 三级缓存

---

## 八、总结

HyCache 通过引入部分缓存、互斥缓存和协调分层缓存三个核心机制，配合 ILP 自动优化和工作内存自动估算，显著提升了 DNN 训练输入预处理流水线的吞吐量（最高 5.3× over MinIO）。其设计思路——将异构存储的缓存决策建模为统一的优化问题——具有通用性。主要局限在于端到端训练加速有限（GPU 瓶颈时受益不大）、仅在单机小规模场景验证、以及对当前主流 LLM/多模态训练 workload 的适用性尚待验证。
