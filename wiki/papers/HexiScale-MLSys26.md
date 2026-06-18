---
type: paper
name: HexiScale
full_title: "HexiScale: Accommodating Large Language Model Training over Heterogeneous Environment"
authors: [Ran Yan, Fangcheng Fu, Youhe Jiang, Bin Cui, Xiaonan Nie, Binhang Yuan]
venue: MLSys
year: 2026
tags: [llm-training, heterogeneous-gpu, pipeline-parallelism, tensor-parallelism, scheduling]
source_pdf: "[[9a1158154dfa42caddbd0694a4e9bdc8.pdf]]"
source_md: "[[9a1158154dfa42caddbd0694a4e9bdc8]]"
---

# HexiScale: Accommodating Large Language Model Training over Heterogeneous Environment (MLSys 2026)

> **一句话总结**：首个支持 DP/PP/TP **完全非对称**划分的异构 LLM 训练系统，两阶段 graph partitioning 调度；Llama-2 7B–30B 在异构 GPU 上 MFU 与同质集群差距平均仅 **3.5%**（最低 0.3%），比 Metis 最高 **1.9×** MFU。

## 问题

Megatron/DeepSpeed 要求对称 parallel group，异构 GPU（算力、显存、互联带宽各异）下强 GPU 被弱 GPU 拖累。例：A800+4090+3090 8 卡上 Megatron 最优 plan iteration **41.52s**，bubble 和跨机 TP 通信开销大。

## 核心方法

- **Asymmetric partition**：每条 pipeline 可有不同 batch size、TP degree、layer 数
- **Asymmetric gradient sync**：大 gradient 切 chunk 对齐最小 shard 做 DP AllReduce
- **Hierarchical graph partitioning**：phase-1 分 GPU group 建 pipeline，phase-2 为每 pipeline 找 parallel plan，迭代优化

## 关键结果

- Llama-2 7B/13B/30B：异构 vs 同质（同 peak FLOPS）MFU gap 平均 **3.5%**，最低 **0.3%**
- vs Metis：最高 **1.9×** MFU；case study 13B 异构环境 **1.6×** 快于 Megatron（25.55s vs 41.52s）

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Flash-Attention]]
- **同类系统**：Megatron、DeepSpeed、Metis、Galvatron、FSDP
- **同会议**：[[MLSys-2026]]