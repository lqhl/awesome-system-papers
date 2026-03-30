# Bayesian Code Diffusion for Efficient Automatic Deep Learning Program Optimization

## 论文基本信息

| 字段 | 内容 |
|------|------|
| 标题 | Bayesian Code Diffusion for Efficient Automatic Deep Learning Program Optimization |
| 作者 | Isu Jeong, Seulki Lee（UNIST） |
| 会议 | OSDI 2025 |
| 链接 | https://www.usenix.org/conference/osdi25/presentation/jeong |

## 研究背景与动机

高性能深度学习程序是高效 ML 系统的基础。深度学习编译器（如 TVM、Glow、nGraph、XLA）自动生成硬件优化代码，但面临三个核心问题：

**问题 1：子图相似性被忽略**
- 每个子图独立分配搜索空间
- 相似子图（如 BERT 中的多个 batch_matmul）独立优化，浪费计算

**问题 2：随机初始化的效率低下**
- Ansor 等方法使用随机初始化的候选程序
- 需要大量迭代才能找到最优解

**问题 3：Cost Model 训练无原则**
- 训练数据由 round-robin 或梯度采样生成
- 数据过于多样，模型难以泛化

## 核心问题

如何在深度学习编译器的自动调优（auto-tuning）中：
1. **复用相似子图的优化参数**（Program Sharing）
2. **从更好的初始点开始搜索**（Prior Propagation）
3. **更高效地训练 Cost Model**（Pre-training + Fine-tuning）

## 主要贡献

1. **Bayesian Code Diffusion 框架**：将贝叶斯框架中的 prior/posterior 概念重新表述为代码优化上下文
2. **Prior 传播**：从已充分优化的子图参数向相似子图传播
3. **Code Diffusion**：通过迭代扩散找到最优 posterior 参数
4. **Cost Model 预训练 + 微调策略**：提升学习效率和预测准确性
5. 在 Ansor 上实现，CPU 和 GPU 均有效：**最高 3.31× 编译加速**，程序延迟最高快 1.13×

## 研究方法与设计

### 核心洞察

**Prior-Posterior 类比**：
- **Prior 子图 G_p**：已充分优化（找到最优参数 θ*_p）
- **Posterior 子图 G_s**：待优化的相似子图
- **Code Diffusion**：将 prior 的参数"扩散"到 posterior，在高概率区域搜索

### 理论公式

**条件似然**：
f_min(c(θ)) = 1 如果 c(θ) 是当前探索中的最小延迟，否则 0

**Prior 传播**：
- 取 θ*_p（prior 最优参数）作为 posterior 初始搜索空间的模式
- 假设 θ*_p 和 θ*_s 接近（因为 G_p ≃ G_s）

**Code Diffusion 过程**：
θ_s^(t+1) = √(1-σ²_{s,t})·θ*_p + σ_{s,t}·ε

其中 ε ~ N(0,I)，σ²_{s,t} < 1 是扩散方差，随迭代递减

### Sketch-based 参数对齐

不同子图可能有不同的 sketch（优化规则序列），需要对齐：
- **Extent 对齐**：l_p 为 prior 参数中某规则的出现次数，l_s 为 posterior 中对应规则的出现次数
- **Length 对齐**：对长度进行缩放以匹配子图维度差异

### Cost Model 学习策略

**Pre-training（预训练）**：
- 在所有子图聚类的 diverse prior 子图执行数据上训练
- 学习广泛的泛化能力

**Fine-tuning（微调）**：
- 在 posterior 子图簇内同构数据上进一步训练
- 提升特定子图的预测准确性

## 关键实现细节

- 在 Ansor（TVM）上实现
- 使用 XGBoost 作为 Cost Model
- 评估在 Intel Core i9-11900K（CPU）和 Nvidia A6000（GPU）上进行
- 测试了 ResNet-18、VGG-16/19、BERT、MobileNet、SqueezeNet、Inception-V3、MXNet、EfficientNet 等模型

## 实验结果与分析

### End-to-End 编译加速

**CPU 上**：
- 相比 Ansor 平均 **2.52×** 编译加速
- 最高 **3.31×**（MobileNet on CPU）
- 相比其他方法（FamilySeer、DietCode、ETO、SelectiveTuning）平均 **1.95×** 加速

**GPU 上**：
- 相比 Ansor 平均 **2.00×** 编译加速
- 最高 **2.79×**
- 相比其他方法平均 **1.76×** 加速

### 首次扩散延迟 vs 最后扩散延迟

**首次扩散延迟**（所有子图至少调优一次）：
- MXNet GPU：比 Ansor 快 **1.65×**

**最后扩散延迟**（完整时间预算用尽）：
- VGG-19 GPU：比 Ansor 快 **1.13×**
- 整体上 Bayesian Code Diffusion 在整个编译过程中保持更低的程序延迟

### Cost Model 学习效率

**Pre-training + Fine-tuning 策略**：
- 相比 Ansor 的 round-robin 采样：收敛更快
- 相比 FamilySeer 的分组方法：泛化能力更强

**观察**：
- Sketch sparsity 高（子图相似性低）时，跨簇泛化效果有限
- Operator diversity 高时，cross-cluster generalization 更有效

## 潜在问题与局限性

1. **扩散方差的 σ²_{s,t} 如何确定**：论文未详细说明 σ 的具体设置方法，可能需要调参
2. **子图相似性度量**：基于 sketch 相似性的聚类可能无法捕捉所有有意义的相似性（如数据流相似但结构不同）
3. **扩展到其他编译器**：当前在 Ansor（TVM）上实现，扩展到其他编译器（如 TensorRT、XLA）需要适配其 IR 和搜索空间表示
4. **复杂模型架构**：测试集中在经典 CV/NLP 模型，对 Transformer 变体、MoE 等新架构的适用性未充分验证
5. **超参数敏感性**：扩散过程的收敛性和最终解的质量可能对参数初始值敏感
6. **与学习型 Cost Model 的结合**：论文使用 XGBoost，但未探索更先进的 Cost Model 架构（如神经网络）

## 未来工作方向

1. 将框架扩展到更多深度学习编译器后端
2. 探索更复杂的 prior-posterior 关系建模
3. 结合学习型 Cost Model 架构

## 个人评注

**优点**：
- **贝叶斯框架的重新表述**非常巧妙——将 prior propagation 和 code diffusion 的过程用严格的数学公式表达，为启发式方法提供了理论解释
- **Pre-training + Fine-tuning 策略**实际上是对机器学习中迁移学习的应用，思路清晰
- 实验覆盖面广，在多种模型和硬件上验证了方法的有效性
- **3.31× 编译加速**在实际应用中有显著价值（更快的编译 = 更短的优化周转时间）

**潜在争议**：
- **"Bayesian Code Diffusion"的命名**有一定误导性——真正的贝叶斯推断涉及后验分布的采样和估计，而本文的方法更像是"从好的初始点出发进行局部搜索"。Bayesian 一词可能过于强烈
- **扩散过程（diffusion）**：与 diffusion model 中的 diffusion 过程（逐步加噪声再逐步去噪）完全不同，只是借用了"从 prior 向 posterior 扩散"的概念。读者可能会被名称误导
- **子图聚类质量**对整体效果影响很大，但论文未充分讨论聚类算法选择的影响
- **与 Ansor 的比较**：Bayesian Code Diffusion 是建立在 Ansor 之上的增量改进，Ansor 本身需要大量手动调参的 sketch 生成，这个负担转移到了聚类阶段

总体而言，Bayesian Code Diffusion 是一项有价值的增量改进工作，将 prior propagation 思想系统化并应用于深度学习编译器 auto-tuning。
