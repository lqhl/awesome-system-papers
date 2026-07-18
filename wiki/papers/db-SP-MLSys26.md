---
type: paper
name: db-SP
full_title: "ACCELERATING SPARSE ATTENTION FOR VISUAL GENERATIVE MODELS WITH DUAL-BALANCED SEQUENCE PARALLELISM"
authors: [Siqi Chen, Ke Hong, Tianchen Zhao, Ruiqi Xie, et al.]
venue: MLSys
year: 2026
tags: [sequence-parallelism, sparse-attention, dit, video-generation, workload-balance]
source_pdf: "[[d3d9446802a44259755d38e6d163e820.pdf]]"
source_md: "[[d3d9446802a44259755d38e6d163e820]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# ACCELERATING SPARSE ATTENTION FOR VISUAL GENERATIVE MODELS WITH DUAL-BALANCED SEQUENCE PARALLELISM (MLSys 2026)

> **一句话总结**：DiT 推理中 block-wise [[Sparse-Attention]] + [[Ulysses]]/[[Ring-Attention]] 会在 head 级与 block 级产生 **ρ_s>1.5** 负载失衡（8×A800 上 Wan2.1-14B 仅 **6.09×** 理想加速）；db-SP 用双层 greedy 划分 + 运行时 Ulysses×Ring 策略选择，端到端 **1.25×**、attention **1.40×** 于 SOTA SP。

## 问题与动机

视觉 [[DiT]] 视频生成 attention 占 **>50%** 延迟；block sparse attention 单卡仍太慢（Wan2.1-14B + PAROAttention **>15 min**/video A800）。[[Sequence-Parallelism]] 可扩 token，但现有 Ulysses（按 head）、Ring（按 sequence/block）未考虑稀疏 mask 不均：head 间稀疏度不同、mask 内 dense block 分布不规则，导致 straggler GPU。

## 关键观察 / 隐含假设

- 观察 1：稀疏不平衡比 ρ_s = max load / avg load 在 Ulysses 8 GPU 上可达 1.513（Wan2.1-14B SpargeAttn），8→1 GPU 端到端仅 6.09×（Ulysses）/ 5.81×（Ring）。
  - **依赖假设**：workload ≈ 各 head dense block 总数；block size 为 SM 整数倍以复用 dense kernel。
  - **可能失效场景**：动态 online sparse（每步变 mask）使划分缓存失效，需重分区。

- **观察 2：head 级与 block 级失衡耦合，但「每层可近似独立达到近完美 balance」可作为解耦先验。**
  - **依赖假设**：先 head partition 再 block partition 的序贯贪心足够接近联合最优。
  - **可能失效场景**：极强跨 head 相关稀疏模式时序贯次优。

- **观察 3：跨 denoising step/layer 稀疏模式相似，可复用划分降 reorder/通信开销。**
  - **依赖假设**：相邻 step mask 相似度高。
  - **可能失效场景**：SpargeAttn 等动态方法相似度低时需频繁重划。

- **假设 1**：latency predictor 可为每组 attention 选最优 (Ulysses degree, Ring degree)。**
  - **证据强度**：**中**——平均 1.25× E2E；predictor 校准质量决定鲁棒性。

## 核心方法

**ρ_s 形式化**：量化 SP 下稀疏 attention 负载不均。

**Dual-balanced partitioning**：head 级 greedy 均衡各 GPU dense block 数；block 级 biased greedy（reward factor 抑通信）在理想 head balance 假设下再均衡。

**Runtime strategy selection**：预测各 (UxRy) 计划延迟，动态选 Ulysses×Ring 组合（类似 [[USP]]）。

**实现**：github.com/thu-nics/db-SP。

## 设计取舍

- **Reorder/All-to-all 开销 vs balance 收益**：贪心+mask 相似性缓存压低 overhead。
- **序贯双层 vs 联合优化**：实现可扩展，极端 mask 可能次优。
- **vs BurstAttention 均匀切 block**：小块切分毁 kernel 效率（§6.2），不适合视觉质量所需小 block。
- **边界条件**：Wan/CogVideoX 等 DiT；8×A800 为主。

## 实验与结果

- 平均端到端 **1.25×**、attention **1.40×** vs SOTA SP（Ulysses/Ring/USP）。
- ρ_s 表：多模型多 sparse 方法上 db-SP 显著降不平衡。
- 8 GPU scaling：显著优于 baseline 欠理想线性。

## Critical Analysis

### 论证链条

SP+sparse → 双层失衡 measurable → 解耦贪心+策略选择 → E2E 加速，链条完整。Predictor 错误可能导致选错并行策略——论文需依赖校准。

### 假设压力测试

更长视频、更多 GPU、PCIe 机器通信 dominate 时增益可能缩小。与量化/cache（SageAttention 等）正交但未联合测。

### 实验可信度

对比 USP 等强 baseline；多模型。缺：与 [[StreamDiffusionV2]] 级 streaming SLO 场景结合。

### 系统性缺陷

论文未讨论 partition 失败 fallback、多租户并发 DiT serving。动态 sparse  worst-case 重划频率未量化。

## 局限与 Future Work

- **局限 1**：强动态 sparse 时相似性假设变弱。
- **局限 2**：predictor 跨硬件迁移需重训。
- **Future work 1**：联合 predictor + 在线 ρ_s 反馈的自适应重划阈值。
- **Future work 2**：与 [[TokenWeave]]/[[TP]] 异构并行共存 profile。

## 相关

- **相关概念**：[[Sequence-Parallelism]]、[[Sparse-Attention]]、[[DiT]]、[[Ulysses]]、[[Ring-Attention]]
- **同类系统**：xDiT、ParaAttention、DSV
- **同会议**：[[MLSys-2026]]
