---
type: paper
name: G-HEMP
full_title: "G-HEMP: FAST MULTI-GPU PRIVATE INFERENCE FOR LARGE-SCALE GCNS WITH HOMOMORPHIC ENCRYPTION"
authors: [Ran Ran, Zhaoting Gong, Zhaowei Li, Xianting Lu, Jiajia Li, Wujie Wen]
venue: MLSys
year: 2026
tags: [homomorphic-encryption, gcn, privacy, multi-gpu, graph-learning]
source_pdf: "[[d09bf41544a3365a46c9077ebb5e35c3.pdf]]"
source_md: "[[d09bf41544a3365a46c9077ebb5e35c3]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-16
---

# G-HEMP: FAST MULTI-GPU PRIVATE INFERENCE FOR LARGE-SCALE GCNS WITH HOMOMORPHIC ENCRYPTION (MLSys 2026)

> **一句话总结**：HE-GCN 在 GPU 上因 Penguin 式 packing 导致加密邻接矩阵 **f 倍**复制爆内存，且 limb-level 多卡分区触发 KSO 跨卡传输反而更慢；G-HEMP 用 block-diagonal parallel packing 消 duplication（单卡 **4.41×**）+ Graph Partition 多卡策略（4 卡 **3.88×**、峰值显存减半），相对 Cinnamon 最高 **3.13×**。

## 问题与动机

[[GCN]] 云端推理需保护图拓扑与节点特征；[[Homomorphic-Encryption]]（CKKS）可在密文上计算。CPU 上 SIMD packing（Penguin 等）可行，但 GPU 显存（~80GB）远小于大图加密 **A** 的占用（PubMed 单层 **A** ~59GB+）。朴素多卡 limb 切分 ciphertext 使 CMult/Rotation 的 key-switching 产生大量 P2P，**2 卡可比单卡慢 50%+**。

G-HEMP 目标：GPU/多 GPU 上可扩展的 HE-GCN，同时降 rotation 次数与内存。

## 关键观察 / 隐含假设

- **观察 1**：特征维 packing 迫使加密邻接矩阵按 `f` 复制，是内存主导项。Penguin `(128,64)` 的复制示例是参数配置相关的 demonstration，而非所有图的结论。
  - **依赖假设**：威胁模型为半诚实云 + 客户端解密；无 bootstrapping，电路深度可控。
  - **可能失效场景**：更深 GCN 层数/更大 F 使 rotation 与噪声预算成为新瓶颈。

- **观察 2**：Block-diagonal packing 按图划分和对角抽取，可降低邻接矩阵存储与 rotation 复杂度，并解析分区。
  - **依赖假设**：图可划分且 block-diagonal 结构保持 AXW 语义正确。
  - **可能失效场景**：极高连通度、难划分图使 partition 损失负载均衡或精度。

- **观察 3**：Graph Partition 按密文子块分布多卡、单次聚合。4 卡实验中 GP-X 为单卡 G-HEMP 的 3.63–3.88×，LLP 为 0.3×（§4.2，Table 6）。
  - **依赖假设**：子矩阵乘可并行且最终聚合 rotation 可摊销。
  - **可能失效场景**：PCIe/NVLink 带宽成为跨卡聚合瓶颈时增益缩小。

- **假设 1：CKKS 近似误差在 GCN 推理可接受，无需 bootstrapping。**
  - **证据强度**：**中**——link prediction 任务验证；未覆盖对抗密文攻击面。

## 核心方法

**Block-diagonal parallel packing**：特征图 **X** 按 tunable block **f** 抽对角打包进 ciphertext 3D 张量；避免 **f** 倍 **A** 复制；Algorithm 1 迭代 slice 加密。

**Graph Partition**：多 GPU 分配 packed data + **A** 子块，最小化跨卡 KSO 与内存；单次跨 GPU 聚合结果。

Workflow：客户端上传加密 **X,A**；云上用明文 **W** 做 HE-GCN 层；客户端解密。

## 设计取舍

- **Block size f**：大 **f** 降 ciphertext 数但增 rotation；解析最优 vs 启发式。
- **多卡 vs 单卡简单性**：Graph Partition 工程复杂，相对 plaintext GCN 仍慢 orders of magnitude。
- **无 bootstrapping**：省开销但限制层深/精度。
- **边界条件**：Amazon-Photo/Computers、PubMed link prediction；与 DGL 14× 8GPU 对比的是 plaintext 非 HE。

## 实验与结果

- 单 GPU vs Penguin SOTA：**4.41×** inference speedup。
- 4 GPU G-HEMP vs 单 GPU G-HEMP：**3.88×** latency，per-GPU 峰值显存约 **减半**。
- vs Cinnamon 多卡：**最高 3.13×**。
- Profiling：Rotation/CMult 比 Add 慢 **~69×**；朴素 2-GPU partition 慢于单卡。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| BDPP lowers single-GPU AXW latency | medium AXW .301 s，27.5× vs FWP、1.17× vs Penguin（§4.1，Table2） | synthetic one-layer microbenchmark，非 full GAE E2E | high |
| BDPP lowers rotation/memory in that microbenchmark | 189 rotation/1.69GB vs FWP4064/Penguin7.55GB（§4.1，Table2） | same config，非 all graph workload | high |
| BDPP improves measured encrypted GCN | up to 16.8× latency、lowest memory（§4.1，Table4） | three graph link-prediction、modified baselines to fit memory | high |
| GP-X scales measured HE-GCN on four GPU | 3.63–3.88× vs single GPU；LLP .3×（§4.2，Table6） | 4 A100 server、fixed HE-GCN | high |
| GPU implementation favors two representative benchmark | 11.1× AXW、10.5× Amazon-Computers lower latency（§4.1，Table3） | different CPU/GPU hardware，非 general HE throughput | medium |

## Critical Analysis

### 论证链条

内存爆炸根因（**A** 复制）+ KSO 跨卡依赖 → 新 packing + 图划分 → 单卡/多卡加速，因果清楚。端到端「实用」仍取决于 HE 绝对延迟是否满足 SLA——论文聚焦相对改进。

### 假设压力测试

更大图、更深 GCN、或异构图时 partition 质量关键。GPU 代际显存增大可能削弱 multi-GPU 必要性。与 TEE/联邦等替代隐私方案的成本对比未做。

### 实验可信度

对比 Penguin、Cinnamon 等同领域 SOTA；数据集规模中等。缺：更大工业图、不同 GCN 变体（GraphSAGE/GAT）泛化。

### 系统性缺陷

论文未讨论密钥管理、侧信道、云运营商合谋。运维复杂度（参数选择、噪声 budget）高。与推荐级 QPS 目标差距未量化。

## 局限与 Future Work

- **局限 1**：评估任务与图规模有限；更深网络噪声累积风险。
- **局限 2**：图划分对极端拓扑的鲁棒性未充分消融。
- **Future work 1**：auto-tune (n,f) 与 GPU 数 given 图统计，可测 latency-memory Pareto。
- **Future work 2**：与压缩/TEE 混合方案在相同 threat model 下测 TCO。

## 相关

- **相关概念**：[[Homomorphic-Encryption]]、[[GCN]]、[[Privacy-Preserving-ML]]
- **同类工作**：Penguin、Cinnamon
- **同会议**：[[MLSys-2026]]
