---
type: paper
name: BayesianCodeDiffusion
full_title: "Bayesian Code Diffusion for Efficient Automatic Deep Learning Program Optimization"
authors: [Isu Jeong, Seulki Lee]
venue: OSDI
year: 2025
tags: [auto-tuning, deep-learning-compiler, tvm, ansor, cost-model]
source_pdf: "[[osdi25-jeong.pdf]]"
source_md: "[[osdi25-jeong]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Bayesian Code Diffusion for Efficient Automatic Deep Learning Program Optimization (OSDI 2025)

> **一句话总结**：在 Ansor 上实现 Bayesian code diffusion：相似 subgraph 聚类后先优化 prior 参数，再 Gaussian 式 code diffusion 初始化 posterior 搜索，配合 cost model 预训练+微调，端到端编译最高 **3.31×** 加速且程序延迟最高再快 **1.13×**（CPU/GPU 多模型）。

## 问题与动机

[[Ansor]]/TVM auto-tuning 为每个 subgraph 独立 sketch+随机初始化+进化搜索，相似子图不共享最优 tile/schedule；cost model 在线从头训练，样本过于多样收敛慢。TransferTuning 需预编译参考模型，DietCode 算子覆盖窄，FamilySeer 分组 cost model 泛化差。

## 关键观察 / 隐含假设

- **观察 1**：同一模型内 subgraph 结构重复（ResNet block、attention 层），最优 schedule 参数在搜索空间中 **邻近**（θ_p* ≈ θ_s*）。
  - **依赖假设**：聚类能找对相似簇；prior 充分搜索后分布可作为 posterior 的 mode。
  - **可能失效场景**：异构 subgraph（罕见算子）聚类失败，diffusion 起点差。
- **观察 2**：随机 fine-tuning 初始化浪费迭代；从 prior 参数加噪声扩散（Eq.5）比纯随机更快命中低延迟区域。
  - **依赖假设**：方差 schedule σ_{s,t} 控制探索半径足够。
  - **证据强度**：强——3.31× 编译加速，多模型一致。
- **假设 3**：cost model 先 heterogeneous prior 预训练、再 per-cluster 微调，比 round-robin 在线学习更准。
  - **证据强度**：中——§6.3 有 ablation，但依赖 Ansor 测量预算是固定 wall-clock。

## 核心方法

1. **Subgraph clustering** → 选 prior，充分搜索得 θ_p*。
2. **Prior propagation**：posterior 初始搜索空间围绕 θ_p*。
3. **Code diffusion**：θ_s^{(t)} = √(1-σ²)θ_p* + σε，迭代扩展 Θ'。
4. **Cost model pre-train + fine-tune**：先跨簇多样样本，再簇内 homogeneous 样本。

实现于 Ansor，改动最小。

## 设计取舍

- **取舍 1**：贝叶斯叙事是启发式（f_min  hypothetical density），非严格概率保证。
- **取舍 2**：绑定 Ansor sketch 空间，换 compiler 需移植。
- **边界条件**：极稀疏/独特 subgraph 收益接近 vanilla Ansor。

## 实验与结果

- ResNet、BERT 等宽模型 CPU/GPU：编译时间最高 **3.31×** 加速。
- 同等编译预算下执行延迟最高 **1.13×** 优于 SOTA auto-tuning。
- 覆盖 Ansor 原支持的硬件；算子覆盖与 Ansor 同。

## Critical Analysis

### 论证链条

子图相似 → 参数可迁移 → diffusion 缩小搜索 → 更好 cost model → 更快到达同等或更优 latency。链条在评测模型集闭合；全新算子/sketch 无 prior 时退化。

### 假设压力测试

- LLM 动态 shape 导致 subgraph 实例变化，聚类稳定性未知。
- 3.31× 加速依赖 wall-clock 预算定义；无限时间最终可能趋同。
- 与 LLM 编译器（torch.compile 等）生态集成未讨论。

### 实验可信度

与 Ansor 对比公平（同框架）；多模型多硬件。缺与 CUDA autotuner（cuDNN benchmark）端到端对比。

### 系统性缺陷

论文未讨论：错误 diffusion 导致劣化 schedule 的检测、生产编译缓存失效、多版本模型并行调优。

## 局限与 Future Work

- **局限 1**：启发式 Bayesian，无最优性证明；绑定 Ansor。
- **局限 2**：独特 subgraph 收益有限。
- **Future work 1**：动态 shape 在线聚类与 prior 更新。
- **Future work 2**：与 [[BayesianCodeDiffusion]]/Mirage 等 superoptimizer 协同。

## 相关

- **相关概念**：[[Quantization]]、Auto-tuning
- **同类系统**：Ansor、AutoTVM、DietCode、FamilySeer、TransferTuning
- **同会议**：[[OSDI-2025]]
