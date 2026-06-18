---
type: paper
name: G-HEMP
full_title: "G-HEMP: Fast Multi-GPU Private Inference for Large-Scale GCNs with Homomorphic Encryption"
authors: [Ran Ran, Zhaoting Gong, Zhaowei Li, Xianting Lu, Jiajia Li, Wujie Wen]
venue: MLSys
year: 2026
tags: [homomorphic-encryption, gcn, privacy, multi-gpu, ckks]
source_pdf: "[[d09bf41544a3365a46c9077ebb5e35c3.pdf]]"
source_md: "[[d09bf41544a3365a46c9077ebb5e35c3]]"
---

# G-HEMP: Fast Multi-GPU Private Inference for Large-Scale GCNs with Homomorphic Encryption (MLSys 2026)

> **一句话总结**：G-HEMP 用 block-diagonal parallel packing 消除加密邻接矩阵 f 倍冗余复制，单 GPU 推理快 4.41×、4-GPU 再快 3.88×，而 Cinnamon limb-level 分片在 4 GPU 上反而慢 3×。

## 问题

同态加密 (HE) 可在云端对密文直接做 GCN 推理，保护图拓扑与节点特征隐私。但大规模 HE-GCN 的 AX 矩阵乘在 GPU 上面临两重瓶颈：(1) SOTA packing（Penguin）为匹配 feature ciphertext 需把加密邻接矩阵 A 复制 f 倍，PubMed 单图 A 就占 ~60 GB，远超 A100 80 GB；(2) naive multi-GPU limb-level 分片触发 key-switching 跨卡传输，2 GPU 反而比单卡慢 50%+。

## 核心方法

**G-HEMP** 两大创新：

1. **Block-diagonal Parallel Packing**：把节点×特征矩阵切成 f×f 方块，按对角线索引打包进 ciphertext，消除 A 的 f 倍复制（内存从 O(nf) 降到 O(n)），旋转复杂度与 Penguin 渐近相当。
2. **Graph Partition 多 GPU 策略**：按图节点分区把 packed ciphertext 分到各 GPU 做并行子矩阵乘，只在最后聚合一次，避免 limb-level 分片导致的 KSO 跨卡依赖。

基于 CKKS scheme，聚焦 CMult/Rotation 主导的 HE-MM，不含 bootstrapping。

## 关键结果

- 单 GPU 相对 Penguin 推理加速最高 **4.41×**。
- 4 GPU 相对单 GPU 再加速最高 **3.88×**，峰值内存减半。
- Cinnamon (ASPLOS'25) 同设置仅 **0.3×**（更慢）。
- GPU 上 Rotation/CMult 比 CPU 快 10×+，但需应用级 packing/partition 才能兑现收益。
- 评测 Amazon-Photo、Amazon-Computers、PubMed link prediction。

## 相关

- **相关概念**：homomorphic encryption、CKKS、GCN、privacy-preserving ML
- **同类系统**：Penguin、Cinnamon、Gazelle
- **同会议**：[[MLSys-2026]]