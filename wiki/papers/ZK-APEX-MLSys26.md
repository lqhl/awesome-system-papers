---
type: paper
name: ZK-APEX
full_title: "ZK-APEX: Zero-Knowledge Approximate Personalized Unlearning with Executable Proofs"
authors: [Mohammad M Maheri, Sunil Cotterill, Alex Davidson, Hamed Haddadi]
venue: MLSys
year: 2026
tags: [machine-unlearning, zero-knowledge, privacy, edge, halo2]
source_pdf: "[[735b90b4568125ed6c3f678819b6e058.pdf]]"
source_md: "[[735b90b4568125ed6c3f678819b6e058]]"
---

# ZK-APEX: Zero-Knowledge Approximate Personalized Unlearning with Executable Proofs (MLSys 2026)

> **一句话总结**：首个面向边缘个性化模型的可验证近似 unlearning 框架，用 provider 发公共 sparse mask + client 做 Group-OBS second-order 补偿，Halo2 ZK-SNARK 证明 ~2 小时（ViT）比重训验证快 10^7×，peak mem < 0.7 GB。

## 问题

模型 provider 把预训练模型下发到 edge 设备后各客户端用私有数据本地个性化。GDPR/CPRA "被遗忘权"要求按 provider 指令删除指定样本影响，但：
1. Provider 不能访问 client 个性化参数（涉隐私）。
2. Client 可能忽略或伪造删除请求——需要密码学可验证。
3. 完整重训 + ZK-SNARK 证明 proof-of-training 成本高到 edge 设备跑不动。
4. 裸转发 forget-set 给 client 暴露敏感数据。
5. SGD 的随机性在 proof of learning 里可被攻击者用于伪造。

## 核心方法

**Threat model**：CVM + GPU-CC 之外的可验证 unlearning；client 是 prover，provider 是 verifier。公共输入仅 mask Ψ 和 Commit(θ_p)、Commit(θ_u)；不暴露 θ_p 和 D_p。

**算法**：
1. **Saliency mask (provider-side)**：用 forget-set 的 gradient + 曲率（diag Hessian 或 empirical Fisher）对每参数算 `S_i = -g_{f,i} θ_{p,i} + 0.5 C_{f,ii} θ_{p,i}^2`，选 top-k 作为 mask m*，provider 只公开 m* 不发 forget-set。
2. **Group-OBS compensation (client-side)**：受 Optimal Brain Surgeon 启发，client 在个性化集上计算 block-wise empirical Fisher F_p，解 KKT 形式二次规划 `min 0.5 δw^T (F_p + λI) δw s.t. E_M^T δw + w_{p,M} = 0`，闭式解只需 sparse matrix-vector 运算，恢复个性化效用。
3. **Halo2 ZK-SNARK 电路**：证明 (i) mask 正确 zero 目标参数，(ii) 补偿权重按承诺的 Fisher 和公共 mask 算出。全是线性 + 稀疏运算，没有 non-linear 激活、没有 training-in-circuit 的 SGD 随机性，因此消灭 forging 攻击面。

**ZK-friendly 关键**：zero-shot（不做 iterative 训练）→ 无 SGD 随机性 → prover adaptivity 为零。

## 关键结果

- **ViT 分类**：~99% Top-1 个性化准确率同时有效 forgetting。
- **OPT-125M 自回归 LM on CodeParrot**：~70% 原始 accuracy 恢复。
- **ZK-SNARK 证明（ViT 场景）**：~2 小时生成，**比重训验证快 10^7×**。
- Peak memory < **0.7 GB**，proof size ~**400 MB**（支持 mobile）。
- 开源 https://github.com/mammadmaheri7/ZK-APEX。

## 相关

- **相关概念**：[[Quantization]]、[[LoRA]]
- **同会议**：[[MLSys-2026]]
