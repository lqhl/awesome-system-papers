---
type: paper
name: FLoRIST
full_title: "FLoRIST: Singular Value Thresholding for Efficient and Accurate Federated Fine-Tuning of Large Language Models"
authors: [Hariharan Ramesh, Jyotikrishna Dass]
venue: MLSys
year: 2026
tags: [federated-learning, lora, fine-tuning, svd, communication-efficient]
source_pdf: "[[eccbc87e4b5ce2fe28308fd9f2a7baf3.pdf]]"
source_md: "[[eccbc87e4b5ce2fe28308fd9f2a7baf3]]"
---

# FLoRIST: Singular Value Thresholding for Efficient and Accurate Federated Fine-Tuning of Large Language Models (MLSys 2026)

> **一句话总结**：FLoRIST 在服务器侧对 stacked 的 [[LoRA]] adapter 做独立 SVD + 中间矩阵分解 + 能量阈值截断，产生统一的低秩全局 adapter，相比 FLoRA 通信效率提升最多 58×、相比 full fine-tuning 提升 227×，同时匹配或超过基线精度。

## 问题

[[LoRA]] + 联邦学习（FL）组合支持参数高效、隐私保护的 LLM 微调。但现有方案各有缺陷：

- **FedIT**：对 A、B 独立 FedAvg，产生 cross-term 噪声 $B_i A_j$，且只支持同构 rank
- **FFA-LoRA**：冻结 A 只训 B，无噪声但参数量减半、收敛慢
- **FLoRA**：stacking 聚合数学正确，支持异构 rank，但下载的 stacked adapter 随客户端数线性增长
- **FlexLoRA**：对完整 ΔW = ΣB_k A_k 做 SVD，服务器端内存/算力开销巨大，且按客户端 rank 分发导致低配客户端丢失关键奇异值

核心问题：聚合后的 LoRA 的真实内在维度是多少？能不能只保留最关键成分从而统一压缩？

## 核心方法

**1. 无噪 stacking 聚合**：
- $B_{\text{stack}} = B_1 \oplus \cdots \oplus B_K \in \mathbb{R}^{m \times r}$（horizontal）
- $A_{\text{stack}} = (n_1/N) A_1 \oplus \cdots \oplus (n_K/N) A_K \in \mathbb{R}^{r \times n}$（vertical）
- $\Delta W = B_{\text{stack}} A_{\text{stack}}$ 数学等价但**避免显式构造**

**2. 高效 SVD via 中间矩阵分解**：
- 分别对 $B_{\text{stack}}$ 和 $A_{\text{stack}}$ 做 SVD，得 $U_B, S_B, V_B, U_A, S_A, V_A$
- 构造中间矩阵 $P = S_B (V_B^T U_A) S_A \in \mathbb{R}^{r \times r}$（远小于 $\Delta W$）
- 对 $P$ 做 SVD 得 $U_P, S_P, V_P$，$S_P$ 即 $\Delta W$ 的奇异值
- 全局 adapter：$B_g = U_B U_P S_P$，$A_g = V_P^T V_A^T$

**3. 能量阈值截断**：
- 保留 top-p 使 $\sum_{i=1}^p (S_P)_{ii}^2 / \sum_i (S_P)_{ii}^2 \geq \tau$
- 两个变体：FLoRIST-O（τ 取高，最大化精度）；FLoRIST-E（τ 取低，最大化通信效率）

**关键观察**：实测 q_proj 层大部分奇异值在前 8–10 个后迅速衰减；即使客户端最大 rank=64，全局 p 只需 2–10。中间层比首尾层需要更高 rank；v_proj 一贯比 q_proj 低秩。

## 关键结果

- 8 客户端同构设置下 FLoRIST-E 相比 FFA-LoRA **3× 通信减少**、相比 FLoRA **39×**、相比 full FT **227×**
- 跨数据集 FLoRIST-E 相比 FLoRA 最多 **58.11× 高效率**，相比 FFA-LoRA **11.8×**
- TinyLLaMA + Wizard 上 FLoRIST-O MMLU 43.63%，超过 FedIT (41.42%)、FLoRA (41.99%)、FlexLoRA (42.53%)、FFA-LoRA (26.31%)
- 低阈值 τ ≤ 0.99 引入的截断噪声还起到 regularization 作用

## 相关

- **相关概念**：[[LoRA]]、SVD、Federated-Learning、Parameter-Efficient-Fine-Tuning
- **同类系统**：FedIT、FFA-LoRA、FLoRA、FlexLoRA、HetLoRA
- **同会议**：[[MLSys-2026]]
