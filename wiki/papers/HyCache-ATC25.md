---
type: paper
name: HyCache
full_title: "HyCache: Hybrid Caching for Accelerating DNN Input Preprocessing Pipelines"
authors: [Keshav Vinayak Jha, Shweta Pandey, Murali Annavaram, Arkaprava Basu]
venue: ATC
year: 2025
tags: [dnn-training, input-pipeline, caching, ilp, preprocessing]
source_pdf: "[[atc2025-jha.pdf]]"
source_md: "[[atc2025-jha]]"
---

# HyCache: Hybrid Caching for Accelerating DNN Input Preprocessing Pipelines (ATC 2025)

> **一句话总结**：跨内存与 SSD 的混合缓存运行时，用 ILP 自动选择缓存哪些预处理步骤、缓存到哪一层，对 6 个 DNN pipeline 实现 1.11×-10.1× pipeline 加速、最高 1.67× 端到端训练加速。

## 问题

GPU 训练越来越快，CPU 端 input preprocessing pipeline（fetch → decode → resize → normalize → augment）成为瓶颈，谷歌报告 16% 训练 pipeline 每 epoch stall ≥100ms，最多 65% epoch 时间花在预处理上。已有缓存方案（tf.data、PRESTO、Cachew）有四个局限：1) all-or-nothing——某 step 输出装不下就完全不缓存，但部分缓存仍能减少重计算；2) 内存与存储分离不协同；3) 即便两层都用，也只缓存同一 step 输出，忽略两层延迟差异；4) 不估算 working memory，要么超提交 OOM 要么浪费空间。

## 核心方法

提出 **HyCache**：混合、互斥、协同的多层缓存：

- **Partial caching**：允许任意比例缓存某 step 输出，不再 all-or-nothing
- **Exclusive memory + storage**：同一 tensor 只在一层，避免重复，最大化总容量
- **Tier-aware coordinated caching**：内存与存储可缓存不同的 pipeline step（基于延迟差异和重计算成本）
- **Working memory 自动估算**：考虑 batch_size、prefetch_depth、fetcher 数量、fetcher per-process 开销与 Python metadata，自动留预算

工作流程：

1. **Annotator + Step Filter**：profile 每个 step 的输入输出维度，对连续输出大小相同的 step 序列只保留最后一个作为候选
2. **Profiler**：1% 数据集上测算 $C_{M_i}$（缓存到内存节省时间）、$C_{D_i}$（缓存到存储节省时间）、tensor size $Sz_i$；二分搜索最优 fetcher 数
3. **ILP solver**：在内存预算 M 和存储预算 D 约束下最大化 $\sum N_{M_i} C_{M_i} + \sum N_{D_i} C_{D_i}$，决定哪些 step 缓存到哪层、缓存多少 tensor
4. **Pipeline 生成**：自动构造多分支 pipeline 用 if-then-else 从 memory/SSD/raw 不同源接入 tensor，向用户暴露单一 iterator

只缓存 offline（确定性）step；online 增强（random crop/flip）保留随机性。基于 [[Nvidia-DALI|NVIDIA DALI]] 实现 hcLib 库，用户只需继承 BasePipeline 并实例化 HyCache。深度细节回 [[atc2025-jha]]。

## 关键结果

- Pipeline 吞吐：vs MinIO 1.11×-5.3×（Voice 5.3×），vs PRESTO 1.24×-2.26×
- 不同硬件配置（C1-C5）下 Voice pipeline 提速 3.14×-7.10×（vs MinIO）、1.2×-3.5×（vs PRESTO）
- 端到端训练：1.05×-1.67×（vs MinIO）、1.05×-1.47×（vs PRESTO），ViT-LoRA 因 GPU 计算重提升仅 1.05×
- Profiling 开销 2.5%-18.2% 单 epoch 时间（一次性）
- 案例：Voice pipeline 同时在内存缓存 step 3、存储缓存 step 1 + step 3，多层多 step 协同；Detection pipeline 在内存缓存 6 个 step、存储缓存 5 个 step

## 相关

- **相关概念**：[[Data-Pipeline]]、Caching、ILP、[[DNN-Training]]、Activation Checkpointing 类比
- **同类系统**：MinIO、PRESTO、Cachew、tf.data
- **同会议**：[[ATC-2025]]
