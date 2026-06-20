---
type: paper
name: DiffKV
full_title: "DiffKV: Differentiated Memory Management for Large Language Models with Parallel KV Compaction"
authors: [Yanqi Zhang, Yuwei Hu, Runyuan Zhao, John C.S. Lui, Haibo Chen]
venue: SOSP
year: 2025
tags: [kv-cache, llm-serving, compression, gpu-memory, quantization]
source_pdf: "[[3731569.3764810.pdf]]"
source_md: "[[3731569.3764810]]"
---

# DiffKV: Differentiated Memory Management for Large Language Models with Parallel KV Compaction (SOSP 2025)

> **一句话总结**：统一量化/剪枝忽略 K vs V 角色差异、token/head 级动态稀疏；DiffKV 三级差异化压缩使 [[KV-Cache]] **2.7–5.7×** 缩小且近无损，靠 on-GPU parallel compaction 管理碎片化，吞吐 **1.9–5.4×**（含 thinking models）。

## 问题与动机

[[LLM-Inference]] 中 [[KV-Cache]] 可占 **>90%** 内存，随长上下文与 thinking models（长 CoT）恶化。[[PagedAttention]] 减浪费但未压缩；量化/剪枝均匀对待 K/V、各 head、各 request，忽略：① K 对 attention score 更关键；② token 重要性异构；③ 每 head 动态稀疏模式不同——导致内存不规则碎片化，数百 head × 数百请求使 per-step 管理成本爆炸。

## 关键观察 / 隐含假设

- **观察 1**：同一 5-token 请求在两 head 上，DiffKV 可用 20.6% 内存达优于均匀剪枝(80%)/量化(50%)（Figure 1）。
  - **依赖假设**：attention score 在线可分层级区分 token；K 高精度/V 低精度误差可控。
  - **可能失效场景**：对 score 极敏感的 long-tail token 被激进剪枝时质量跌。
- **观察 2**：差异化布局使每 step 数万异构 region——CPU 管理不可行，需 GPU parallel compaction。
  - **依赖假设**：unified pages + circular free list + bidirectional page table 可 O(并行) 回收。
  - **可能失效场景**：极高并发×极长序列下 metadata 本身成为瓶颈——论文称 tens of ms/step 内可完成。
- **假设 1**：near-lossless 可在复杂 reasoning benchmark 上成立（含 QwQ/R1-distill）。
  - **证据强度**：中强；首次 thinking model KV 压缩评测 claim。

## 核心方法

三级差异化：
1. **K vs V** 不同精度
2. **Token** 分档（高精/低精/剪枝）
3. **Per-head per-request** 动态识别关键 token

**On-GPU memory manager**：unified pages（按精度配置页）、circular free page list（prefix sum 分配）、bidirectional page table（高低精度从左右生长）。

基于 [[vLLM]] 实现。

## 设计取舍

- **取舍 1**：在线 score 驱动 → 额外 attention 分析开销 vs 静态 PyramidKV 类启发式。
- **取舍 2**：GPU 内 compaction 复杂度换 batch 放大能力。
- **边界条件**：压缩比随 workload 动态稀疏度变化 **2.7–5.7×**。

## 实验与结果

- [[KV-Cache]]：**2.7–5.7×** 压缩，near-lossless（复杂 reasoning）
- 吞吐：**1.9–5.4×**
- 模型：Llama3-8B、QwQ-32B、R1-Distill-Qwen-14B、R1-Distill-Llama-8B 等
- 称首次在 thinking models + CoT 任务上验证 KV 压缩

## Critical Analysis

### 论证链条

差异化观察 → GPU compaction 数据结构 → 压缩+吞吐双升，逻辑闭合。质量「near-lossless」依赖特定 benchmark 阈值——与 FP16 可感知差异的 task 未 exhaustive；与 [[DiffKV]] 正交的 prefix cache/speculative 叠加未测。

### 假设压力测试

- **多租户**：per-request/head 差异化使 fairness 与内存 accounting 复杂。
- **GQA/MQA**：KV head 共享改变 per-head 稀疏假设。
- **硬件**：compaction kernel 在新 GPU 架构上寄存器压力。

### 实验可信度

华为+港中大+vLLM 集成可信；thinking model 评测是亮点。缺与 uniform quant（Atom/Qserve）同精度下的 iso-quality 对比表需读者细读 appendix。

### 系统性缺陷

实现绑定 vLLM 内存 manager；故障时回退 FP16 路径、在线 tuning 超参对运维的要求论文未讨论。

## 局限与 Future Work

- **局限 1**：管理复杂度随 head×request 积增长，极端 scale 待验证。
- **局限 2**：质量敏感应用需 per-model 校准剪枝阈值。
- **Future work 1**：与 [[Pie]]/[[Aegaeon]] 多模型池共享 GPU 时 DiffKV 页表隔离。
- **Future work 2**：iso-quality 下 vs CPU offload KV 方案的$/token。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[vLLM]]、[[Quantization]]、[[LLM-Inference]]
- **同类系统**：H2O、SnapKV、PyramidKV、Atom、Qserve
- **同会议**：[[SOSP-2025]]