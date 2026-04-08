# Preparation Meets Opportunity: Enhancing Data Preprocessing for ML Training With Seneca

**作者**：Omkar Desai (Syracuse University), Ziyang Jiao (Huaibei Normal University), Shuyi Pei (Samsung Semiconductor), Janki Bhimani (Florida International University), Bryan S. Kim (Syracuse University)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/desai
**源文件**：[[fast2026-desai.pdf]]

---

## 一、背景

随着 GPU 算力的快速增长（2011–2023 年 GPU TFLOPS 增速远超 CPU），ML 训练中的数据存储与摄入（Data Storage and Ingestion, DSI）管线已成为瓶颈。对于图像、视频、音频和推荐模型等多媒体 ML 训练任务，DSI 管线需要从远程存储读取数据、解码为张量、进行随机增强变换，最后加载到 GPU。CPU 与 GPU 之间的性能鸿沟不断扩大——以 SwinT 模型为例，DSI 吞吐量与 GPU 训练吞吐量的差距在 RTX 5000 服务器上为 4.63×，在 A100 服务器上扩大到 7.66×。

当多个训练任务并发执行以最大化 GPU 利用率时，DSI 管线的瓶颈更加严重：每个任务独立进行数据预处理，导致大量重复计算。例如，4 个并发 PyTorch 任务在 170 万样本的数据集上产生了 716 万次预处理操作。

---

## 二、要解决的问题

1. **缓存数据形式选择困难**：DSI 管线中数据存在三种形式——编码态（encoded，体积小但需要完整预处理）、解码态（decoded，中间状态）和增强态（augmented，训练就绪但体积膨胀高达 15×）。在有限缓存容量下，缓存哪种形式涉及复杂的空间-时间权衡，最优选择取决于硬件配置、缓存大小和数据集特征，现有工作均未考虑这一问题。

2. **随机采样导致缓存命中率低**：ML 训练要求每个 epoch 随机采样数据，这使得传统 LRU 等缓存策略失效。并发训练任务各自独立采样，无法从彼此的缓存活动中获益。SHADE 的重要性采样不兼容并发训练，Quiver 的替换采样存在过采样开销。

---

## 三、洞察与设计

**关键洞察**：（1）由于随机采样的统计特性，缓存命中率可以被精确估算（命中概率 = 缓存样本数 / 数据集总样本数），这使得构建 DSI 管线的解析性能模型成为可能；（2）训练任务的采样顺序不必严格遵循预定的伪随机序列——只要保证每个样本在一个 epoch 内恰好被使用一次且顺序是随机的，就可以用缓存中已有的样本替代未缓存的样本，从而在不影响训练精度的前提下提高缓存命中率。

基于以上洞察，Seneca 设计了两个核心机制：

### Model-Driven Partitioning (MDP)

构建 DSI 管线的高级性能模型，将管线建模为四种数据访问场景的加权组合：
- 访问增强态缓存（DSI_A）：受限于缓存带宽、网络、PCIe 和 GPU 吞吐量
- 访问解码态缓存（DSI_D）：额外受限于 CPU 增强吞吐量
- 访问编码态缓存（DSI_E）：额外受限于 CPU 解码+增强吞吐量
- 访问远程存储（DSI_S）：额外受限于存储带宽

整体 DSI 吞吐量为四种场景按概率加权求和。通过暴力搜索（1% 粒度枚举所有 encoded/decoded/augmented 分配比例），找到使 DSI 吞吐量最大化的缓存分区方案。

### Opportunistic Data Sampling (ODS)

维护两个轻量元数据结构：
- **per-job seen bit vector**：追踪每个任务在当前 epoch 中已使用的样本
- **per-dataset status + reference count**：追踪每个样本的缓存状态和引用计数

当 batch 请求到达时，ODS 将缓存未命中的样本替换为缓存中已有但当前任务尚未使用的样本。引用计数达到并发任务数时触发驱逐，确保增强态数据不会跨 epoch 重用。元数据开销极小（ImageNet-1K 上 8 个并发任务仅需 2.6 MB）。

---

## 四、实现细节

- 基于 PyTorch v1.12.0 修改 DataLoader，约 4200 行代码改动
- 使用 Redis 作为缓存后端（可替换为其他高性能 KV 存储）
- MDP 在训练启动时执行一次缓存分区计算（< 1 秒）
- ODS 在运行时执行，每次 batch 请求仅需 4 次常数时间的元数据操作（纳秒级）
- 支持数据并行分布式训练，性能模型考虑了 ring-reduce 梯度通信开销和 NVLink 互联
- 提供 Docker 容器和开源代码：https://github.com/swiftomkar/seneca-fast26-pytorch

---

## 五、实验结果

**实验平台**：5 种硬件配置（in-house 2×RTX 5000、AWS 4×V100、Azure 4×A100，以及各自的双节点分布式配置）

**数据集**：ImageNet-1K (142 GB)、OpenImages V7 (517 GB)、ImageNet-22K (1.4 TB)

**模型**：7 个模型（ResNet-18/50、VGG-19、DenseNet-169、AlexNet、ViT、SwinT），参数量 3.4M–633.4M

| 指标 | 结果 |
|------|------|
| 多任务 makespan 降低 | 45.23%（vs PyTorch） |
| DSI 吞吐量提升 | 最高 3.45×（vs 次优 dataloader） |
| 单任务训练加速（vs PyTorch） | 38.09%–49.16% |
| 单任务训练加速（vs DALI） | 60.70%–70.00% |
| 缓存命中率（20% 数据缓存） | 54%（比 Quiver 高 11%） |
| GPU 利用率 | 98%（4 并发任务） |
| 训练精度影响 | < 2.83% 误差 |

**模型验证**：性能模型在 24 种配置组合上 Pearson 相关系数均 ≥ 0.90。

**分布式扩展**：Azure 80 Gbps 网络下双节点扩展比为 1.89×；in-house 10 Gbps 网络下为 1.62×（受网络瓶颈限制）。

**MDP 分区结果**（部分）：

| 数据集 | Azure 1×NC96ads_v4 | AWS p3.8xlarge |
|--------|---------------------|----------------|
| ImageNet-1K | 0-48-52 | 0-81-19 |
| OpenImages V7 | 5-95-0 | 52-48-0 |
| ImageNet-22K | 100-0-0 | 100-0-0 |

---

## 六、批判性分析

1. **评估仅限图像分类**：虽然论文声称核心概念可推广到所有预处理密集型 ML 训练（音频、视频、推荐模型），但实验完全基于图像分类模型。Table 1 列出了多种模型类型的预处理流程，却没有任何非图像实验验证。推荐模型（DLRM）和音频/视频模型的数据管线特征差异很大，泛化性存疑。

2. **基线比较的公平性问题**：SHADE 被标注为单线程设计，Seneca 在吞吐量上超过 SHADE 13.18×。这个对比的意义有限——如果 SHADE 的核心瓶颈是单线程实现而非算法设计，那么多线程化的 SHADE 可能表现大不相同。Quiver 未开源，由作者自行实现，实现质量难以验证。

3. **ODS 对训练收敛的理论分析不足**：论文通过实验展示精度差异 < 2.83%，但缺乏对 ODS 采样偏差的理论分析。ODS 偏好缓存中的样本，实际上引入了依赖于缓存内容的采样偏差。论文仅在 250 epoch 内验证了 4 个模型，对更长训练、更大模型、不同学习率调度下的影响缺乏探讨。

4. **性能模型假设较强**：模型假设硬件参数（CPU/GPU 吞吐量、带宽等）可以被精确 profiling 且在训练过程中保持稳定。实际环境中，共享集群的网络带宽波动、OS 干扰、其他进程的资源竞争等因素可能导致模型预测偏差。论文在受控环境下验证了 ≥ 0.90 的相关系数，但未讨论生产环境中的鲁棒性。

5. **缓存容量假设的局限性**：实验中缓存大小为 64–400 GB，数据集最大 1.4 TB。在实际大规模训练场景中（数据集 10+ TB），缓存占比会更低，MDP 可能退化为全部缓存编码态（如 ImageNet-22K 结果所示，全部 100-0-0），此时 MDP 的价值有限，主要收益来自 ODS。

---

## 七、AI Infra / MLSys 视角

1. **DSI 管线建模方法论可迁移**：Seneca 的性能模型将 DSI 管线分解为缓存/网络/PCIe/CPU/GPU 多个瓶颈点的 min 函数组合，这种建模思路可直接应用于 LLM 推理系统中的 prefill/decode 管线分析，特别是在 disaggregated inference（分离式推理）架构下分析数据搬运瓶颈。

2. **对 LLM 训练数据管线的启发**：虽然 LLM 训练的数据预处理（tokenization）相对轻量，但多模态大模型（如 vision-language model）的图像/视频预处理同样面临 DSI 瓶颈。Seneca 的缓存分区策略可直接应用于多模态训练场景。

3. **ODS 的思想可扩展到 KV Cache 管理**：ODS "用已有的替代缺失的"这一核心思想，与 LLM 推理中的 prefix caching / KV cache 复用有类比关系——在 batch scheduling 层面，优先调度能复用已有 KV cache 的请求，类似于 ODS 优先采样缓存中的数据。

4. **可操作的研究方向**：将 MDP 的思想扩展到异构缓存层级（GPU HBM → CPU DRAM → NVMe SSD → 远程存储）的自动分区，结合实时 profiling 动态调整，适用于 vLLM 等推理系统的多层 KV cache 管理。

---

## 八、总结

Seneca 通过两个互补的技术——基于性能模型的缓存分区（MDP）和机会主义数据采样（ODS）——有效缓解了并发 ML 训练中的数据预处理瓶颈。MDP 根据硬件配置和数据集特征自动确定编码态/解码态/增强态数据在缓存中的最优分配比例，ODS 在不影响训练精度的前提下通过替换采样提高缓存命中率。系统在多种硬件和数据集上验证了有效性，最高将 DSI 吞吐量提升 3.45×，makespan 减少 45.23%。主要局限在于实验仅覆盖图像分类场景，且对大规模数据集（缓存占比极低时）MDP 的增益递减。
