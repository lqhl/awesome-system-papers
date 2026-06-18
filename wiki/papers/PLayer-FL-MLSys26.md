---
type: paper
name: PLayer-FL
full_title: "PLayer-FL: A Principled Approach to Personalized Layer-wise Cross-Silo Federated Learning"
authors: [Ahmed Elhussein, Gamze Gursoy]
venue: MLSys
year: 2026
tags: [federated-learning, personalization, partial-fl, model-pruning, healthcare]
source_pdf: "[[d2ddea18f00665ce8623e36bd4e3c7c5.pdf]]"
source_md: "[[d2ddea18f00665ce8623e36bd4e3c7c5]]"
---

# PLayer-FL: A Principled Approach to Personalized Layer-wise Cross-Silo Federated Learning (MLSys 2026)

> **一句话总结**：PLayer-FL 借用 model pruning 的 first-order 重要性度量，定义 federation sensitivity 指标，只在训练第一个 epoch 就能决定哪些层该被 federate，在 non-IID 数据上优于 FedAvg / FedPer / FedBABU / FedRep。

## 问题

跨医院等 cross-silo 联邦学习中，非独立同分布 (non-IID) 数据导致 FedAvg 全局模型性能下降。Partial FL 只联邦部分层（通常是早期层）能缓解，但现有方法（FedPer / FedBABU / FedRep）靠「浅层更通用」的经验法则预定义联邦层数，泛化性差且主要面向 CNN。pFedLA 虽动态决定但需 hypernetwork，pFedHR 要共享数据（违反 cross-silo 约束）。

## 核心方法

关键洞察：学习泛化层在 loss landscape 平坦区（对 perturbation 不敏感），联邦聚合本质是一种 perturbation。借用 pruning 的 first-order 参数重要性，定义 layer l 的 **federation sensitivity**：

$$
\mathcal{F}_l(\Theta) = \sum_{k=1}^{l} \frac{1}{n_k} \sum_{p=1}^{n_k} (\theta_p \nabla\theta_p)^2
$$

按层参数数归一化，并累积到第 l 层（partial FL 选第 l 层必须同时选前面所有层）。训练一个 epoch 后计算 $\mathcal{F}_l$，在 FCN/CNN/Transformer 上观察到一致的「末尾陡升」转折点，据此选择联邦层数。

## 关键结果

- 仅 1 epoch 即可确定联邦层数，与 gradient variance / Hessian eigenvalue / CKA 高度相关。
- FashionMNIST / EMNIST / CIFAR-10 / MIMIC-III 等 non-IID 数据集上优于 FedAvg、FedPer、FedBABU、FedRep、pFedLA。
- 各 client 性能更均匀，参与 incentive 更强。
- Code: https://github.com/gaiters-aerials/player_fl

## 相关

- **相关概念**：Federated Learning、Non-IID、Model Pruning、Loss Landscape
- **同类系统**：FedAvg、FedPer、FedBABU、FedRep、pFedLA
- **同会议**：[[MLSys-2026]]