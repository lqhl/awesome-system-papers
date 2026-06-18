---
type: paper
name: ZK-APEX
full_title: "ZK-APEX: Zero-Knowledge Approximate Personalized Unlearning with Executable Proofs"
authors: [Mohammad M Maheri, Sunil Cotterill, Alex Davidson, Hamed Haddadi]
venue: MLSys
year: 2026
tags: [machine-unlearning, zero-knowledge, edge, personalization, privacy]
source_pdf: "[[735b90b4568125ed6c3f678819b6e058.pdf]]"
source_md: "[[735b90b4568125ed6c3f678819b6e058]]"
---

# ZK-APEX: Zero-Knowledge Approximate Personalized Unlearning with Executable Proofs (MLSys 2026)

> **一句话总结**：provider 发 public sparse mask、client 用 Group-OBS + block Fisher 补偿个性化模型，Halo2 ZK-SNARK 证明执行正确；ViT 恢复 ~99% Top-1、证明 ~2h（比 retrain 验证快 10⁷×），峰值内存 < 0.7 GB。

## 问题

边缘个性化模型需按 GDPR 删除指定类数据，但 provider 不能看 θ_p，client 不能交模型；全量 retrain+ZK 证明在 edge 不可行。

## 核心方法

**Unlearning**：provider 在 θ_0 上算 saliency mask m*；client 在 θ_p 上 Group-OBS 二次补偿（block damped Fisher），(θ_u)_M=0。

**ZK**：电路只验证 mask 置零 + 补偿按式 (13)–(14) 计算；无 SGD 随机性，防 forging。

**零-shot**：确定性算子，适合 SNARK 稀疏 matvec。

## 关键结果

- ViT：~**99%** 个性化 Top-1，有效遗忘
- OPT-125M CodeParrot：~**70%** 精度恢复
- Halo2 证明：≈**2 小时**，peak **< 0.7 GB**，proof ~400 MB；比 retrain-based 验证 **>10⁷×** 快

## 相关

- **相关概念**：[[LoRA]]（个性化 adapter）
- **同类系统**：SISA、OBS pruning、ZK proof-of-training
- **同会议**：[[MLSys-2026]]