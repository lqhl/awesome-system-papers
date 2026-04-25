---
type: paper
name: Seneca
full_title: "Preparation Meets Opportunity: Enhancing Data Preprocessing for ML Training With Seneca"
authors: [Omkar Desai, Ziyang Jiao, Shuyi Pei, Janki Bhimani, Bryan S. Kim]
venue: FAST
year: 2026
tags: [ml-training, data-loading, caching, dsi-pipeline, pytorch]
source_pdf: "[[fast2026-desai.pdf]]"
source_md: "[[fast2026-desai]]"
---

# Preparation Meets Opportunity: Enhancing Data Preprocessing for ML Training With Seneca (FAST 2026)

> **一句话总结**：用 DSI 性能模型把 cache 在 encoded/decoded/augmented 三种数据形态之间最优分区（MDP）+ 让并发训练任务机会性优先吃 cache 命中样本（ODS），相比 PyTorch 缩短 makespan **45.23%**，DSI 吞吐相对 next best dataloader 提升至多 **3.45×**。

## 问题

并发训练多媒体 ML 模型时，data storage and ingestion (DSI) pipeline 是瓶颈：CPU 与 GPU FLOPS 差距 4.63–7.66× 且持续扩大；OS page cache 在 random sampling 模式下命中率差。已有 caching 方案（[[MINIO]]、[[SHADE]]、[[Quiver]]、PRESTO、Revamper）忽略两个问题：

1. **Cache 哪种数据形态？** Encoded（密度高但 CPU 要再解码）、decoded（中等）、augmented（最 ready 但体积放大 15× 且重复用易过拟合）—— 三种形态在 cache size、CPU 速度、storage 速度等多变量下没有平凡最优。
2. **并发任务不互助**：random sampling 让多 job 共享 dataset 时，各自独立预处理（4 jobs 跑 1.7M OpenImages 样本做了 7.16M 次 preprocess）。SHADE importance sampling 跨 job 不兼容；Quiver 替换式采样有 oversample 带宽争抢。

## 核心方法

Seneca = **Model-Driven Partitioning (MDP)** + **Opportunistic Data Sampling (ODS)**，在 [[PyTorch]] dataloader 上修改、用 [[Redis]] 做远端 cache。

**MDP**：建立 DSI pipeline 数学模型，分别推导 4 种数据访问情形的吞吐 $DSI_A, DSI_D, DSI_E, DSI_S$（augmented / decoded / encoded in cache，及 storage fetch），各自由 cache bandwidth、NIC、PCIe、GPU ingestion、CPU augment/decode rate 中的 min 决定。给定 hardware/job 参数和 cache 容量比例 $(x_E, x_D, x_A)$，预测 random sampling 下各形态命中概率，求解使 $DSI_{overall}$ 最大的最优分区。

**ODS**：基于「同 dataset 的并发 job 之间可以互相利用对方采样进度」的洞察，维护两个元数据：(i) per-job seen bit vector（保证一个 epoch 每样本恰用一次）+ (ii) per-dataset 状态与引用计数。当当前 batch 的某样本未命中 cache 但另一已命中样本 also unseen，则用后者替换；保持伪随机性同时显著提升 cache 命中率。和 [[Quiver]] 不同的是 ODS 不 oversample，无带宽浪费。

## 关键结果

- 相比 PyTorch makespan 缩 45.23%；DSI 吞吐相对 next best dataloader 至多 3.45×，不损训练精度。
- 5 个模型 (3.4M–633.4M 参数) × 3 数据集 (142GB–1.4TB) × 5 硬件配置上对比 5 个 SOTA 方案。
- 关键观察：450GB cache 时 augmented form 节省 preprocess 69.91%，但 250GB cache 时只节省 11.36% 且 fetch 时间反增 87.2% —— 印证 cache form 选择对 cache size 敏感，必须用 model 决策。
- 开源：https://github.com/swiftomkar/seneca-fast26-pytorch

## 相关

- **相关概念**：[[Data-Loading]]、[[Random-Sampling]]、[[Caching]]、[[DSI-Pipeline]]
- **同类系统**：[[MINIO]]、[[SHADE]]、[[Quiver]]、[[DALI]]、[[Cachew]]、[[Pecan]]、[[FastFlow]]
- **同会议**：[[FAST-2026]]
