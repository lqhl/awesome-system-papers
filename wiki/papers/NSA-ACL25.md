---
type: paper
name: NSA
full_title: "Native Sparse Attention: Hardware-Aligned and Natively Trainable Sparse Attention"
authors: [Jingyang Yuan, Huazuo Gao, Damai Dai, Junyu Luo, Liang Zhao, Zhengyan Zhang, Zhenda Xie, Y. X. Wei, Lean Wang, Zhiping Xiao, Yuqing Wang, Chong Ruan, Ming Zhang, Wenfeng Liang, Wangding Zeng]
venue: ACL
year: 2025
tags: [sparse-attention, long-context, attention-kernel, hardware-aligned, llm-training]
source_pdf: "[[arxiv25-yuan-nsa.pdf]]"
source_md: "[[arxiv25-yuan-nsa]]"
---

# NSA: Native Sparse Attention (ACL 2025)

> **一句话总结**：ACL 2025 最佳论文。提出原生可训练的硬件对齐稀疏注意力——三条并行分支（压缩/选择/滑动窗口）+ 门控融合，首次在大规模实验上证明稀疏注意力可以超越全注意力质量，64K 解码 11.6× 加速。

## 问题

标准 attention 在 64K context 下占解码总延迟的 70-80%。现有稀疏注意力两大缺陷：
1. **硬件协同不足**：理论 FLOPs 减少但内存访问不规则，实际加速远低于理论值
2. **缺乏训练支持**：绝大多数方法仅推理时稀疏，模型在 full attention 下预训练，引入架构偏差

## 核心方法

NSA 将 Key/Value 组织为时间块，通过三条并行分支处理，门控融合：

**Token Compression（粗粒度全局感知）**：连续 K/V 块通过可学习 MLP 压缩为块级表示（32→1），捕获高层语义。

**Token Selection（细粒度关键保留）**：基于压缩注意力计算中产生的中间注意力分数做块重要性评分（**零额外计算成本**），选 top-n 块保留其中所有 token。

**Sliding Window（局部精确性）**：512 长度滑动窗口，专注局部上下文。

**门控融合**：三路输出通过输入特征动态生成的 MLP 门控权重聚合。

**硬件对齐内核**（Triton 实现）：
- Group-Centric Data Loading：GQA 组内所有 query head 共享稀疏 KV 块索引，一次性加载
- 64 token 选择块大小，与 GPU Tensor Core 粒度对齐
- Outer loop 置于 Triton Grid 调度器，简化优化

## 关键结果

- **通用 benchmark (9 项)**：7/9 超越全注意力基线，平均 +1.3%
- **LongBench**：+3.2%，多跳 QA (HPQ +8.7%, 2Wiki +5.1%)
- **NIAH 64K**：100% 检索成功率
- **AIME 8K**：0.121 vs Full-Attention 0.046 (+163%)；16K 0.146 vs 0.092 (+59%)
- **效率 (64K)**：解码 11.6× / 前向 9.0× / 反向 6.0× / 内存访问 65536→5632 token
- **预训练**：27B MoE, 270B tokens, GQA + MoE 架构

## 相关

- **核心概念**：[[Sparse-Attention]]、[[Attention]]、[[Flash-Attention]]
- **同类方法**：DSA (DeepSeek V3.2)、Twilight (adaptive budget)、BLASST (block sparse)
- **上游**：DeepSeek-V3（backbone 架构）、GQA（共享 KV 设计）
- **下游**：DeepSeek-V4 (CSA+HCA，延续稀疏+压缩思路)、SSA/SubQ (content-dependent sparse)
