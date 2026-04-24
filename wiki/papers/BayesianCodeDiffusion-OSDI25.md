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
---

# Bayesian Code Diffusion for Efficient Automatic Deep Learning Program Optimization (OSDI 2025)

> **一句话总结**：给 [[Ansor]] 式 auto-tuning 装上贝叶斯先验——先把相似 subgraph 聚成 cluster 找一个 prior 参数充分优化，再用 "code diffusion" 把它扩散到 posterior subgraph 初始化，把 DL 编译时间最多缩短 3.31×、不牺牲延迟。

## 问题

TVM/Ansor 类 DL 编译器的 auto-tuning 把模型切成 subgraph，每个 subgraph 独立生成 sketch、随机初始化参数、evolutionary search 微调，挑 cost model 预测低延迟的候选上机测。这个流程有三个浪费：(1) 相似 subgraph（比如 ResNet 里重复的 conv+bn+relu 块）被独立搜索，最优参数不共享；(2) fine-tuning 起点完全随机，大量迭代用在无效区域；(3) cost model 按 round-robin/gradient 顺序拿样本训练，数据太多样反而收敛慢、预测不准。已有改进（SelectiveTuning、ETO、DietCode、TransferTuning、FamilySeer）各取一角但都有短板：要么需要预编译的参考模型，要么硬件/算子支持受限，要么一次性迁移不足细调。

## 核心方法

论文把 DL 程序优化重述为贝叶斯推断问题：给定 prior subgraph $\mathcal{G}_p$ 的最优参数 $\theta_p^*$，posterior subgraph $\mathcal{G}_s$ 的最优 $\theta_s^*$ 大概率在 $\theta_p^*$ 附近——即假设 $f(\theta_s) = \mathcal{N}(\theta_p^*, \sigma_s^2)$。经验支撑是：BERT 里 8 个 subgraph 有 5 个共享同一 sketch $S_0$，且同 sketch cluster 内的最优参数 cosine 相似度远高于跨 sketch。

整套流程三步：

(1) **Sketch-based clustering**：按 Ansor 生成的 sketch 聚类（比 SelectiveTuning 的 operator-based 聚类更精确，因 tensor dim 差异会造成同 operator 但不同 sketch）。

(2) **Prior selection + optimization**：cluster 内用 cosine similarity of tensor dims 选最 "中心" 的 subgraph 当 $\mathcal{G}_p$，充分搜索得 $\theta_p^*$，同时做 cost model **pre-training**（用所有 cluster 的 prior 数据混合训练以泛化）。

(3) **Code diffusion**：用 $\theta_p^*$ 作为 posterior 的初始候选 $\theta_s^{(0)}$，再按 $\theta_s^{(t)} = \sqrt{1-\sigma^2}\theta_p^* + \sqrt{\sigma^2}\varepsilon$ 迭代加噪扩散（仿 diffusion model 思路）。针对 Ansor 的 InitFillTileSize 等参数化规则，实现了三种具体 diffusion 机制：相同 extent 直接复用 length；不同 extent 时选 divisor 最接近的 length；或按 $e_s/e_p$ 比例缩放后取最近 divisor。同时按 cluster 顺序做 cost model **fine-tuning**，学同构数据提升单 cluster 预测准确度。

整个系统植入 Ansor (tvm@a340dbe)，改动很小。

## 关键结果

- 端到端编译 speedup：CPU 上 10 个模型平均 2.52×、最大 3.31×（MobileNet）；GPU 上平均 2.00×、最大 2.79×
- 在同等编译时间内，生成程序的执行延迟比 Ansor 最多低 1.13×（VGG-19 on GPU）
- 覆盖 ResNet-18/VGG-16/19/BERT/MobileNet/MobileNetV2/SqueezeNet/InceptionV3/MXNet/EfficientNet，CPU+GPU 两种硬件
- 优于所有 baseline（Ansor、FamilySeer、DietCode、ETO、SelectiveTuning），且适用性最广（DietCode 只支持 GPU+BERT，ETO/SelectiveTuning 不支持 CPU）
- Pearson 分析：CPU 上 sketch sparsity 与 speedup 相关性最强（prior propagation 主导），GPU 上 operator sparsity 更相关（cost model 策略主导）

## 相关

- **相关概念**：[[Auto-Tuning]]、[[Cost-Model]]、[[Ansor]]
- **同类系统**：Ansor、FamilySeer、DietCode、SelectiveTuning、TransferTuning、ETO
- **同会议**：[[OSDI-2025]]
