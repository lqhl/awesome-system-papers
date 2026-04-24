---
type: paper
name: QiMeng-Xpiler
full_title: "QiMeng-Xpiler: Transcompiling Tensor Programs for Deep Learning Systems with a Neural-Symbolic Approach"
authors: [Shouyang Dong, Yuanbo Wen, Jun Bi, Di Huang, Jiaming Guo, et al.]
venue: OSDI
year: 2025
tags: [transcompiler, tensor-program, llm, program-synthesis, compiler, heterogeneous-hardware]
source_pdf: "[[osdi25-dong.pdf]]"
source_md: "[[osdi25-dong]]"
---

# QiMeng-Xpiler: Transcompiling Tensor Programs for Deep Learning Systems with a Neural-Symbolic Approach (OSDI 2025)

> **一句话总结**：把张量程序在 CUDA / HIP / BANG / VNNI 四类深度学习系统间自动源到源翻译：LLM 生成高层 sketch，小尺度 SMT 修 bug，层级 auto-tuning 优化性能，平均正确率 95%，可达 vendor 手调库 0.78× 性能。

## 问题

数据中心部署了 NVIDIA GPU、AMD MI、Intel DL Boost、Cambricon MLU 等异构深度学习系统（DLS），每种都要手写一份高性能张量算子。"Write Once, Run Anywhere"难在架构差异巨大（SIMT vs SIMD、独特内存层次 NRAM/WRAM/shared、专用 intrinsic）。三类现有 transcompilation 方案都不适用：

- **规则驱动**（HIPIFY、FCUDA）：要专家手写大量规则，不同 DLS 之间架构落差无法覆盖
- **符号合成**（Tenspiler 等）：基于 SMT 求解器，搜索空间随程序规模爆炸，难以扩展到通用程序，还要人工写规约
- **LLM 驱动**（GPT-4、TransCoder、OpenAI o1）：GPT-4 zero-shot 的 CUDA→BANG 编译正确率 0%、few-shot 计算正确率 7.7%，在并行语义、内存层次、专用指令三类错误上都高频失败

## 核心方法

QiMeng-Xpiler 是 neural-symbolic 转译器：把翻译拆成一系列"LLM-assisted transformation passes"，每个 pass 先用 LLM 生成，再单元测试验证，失败则用**小尺度 SMT 修复**——把符号合成的问题规模限制到求解器能搞定的范围。

11 个 pass 分三类，分别对应 DLS 三大特征：
1. **Sequentialization / Parallelization**：loop recovery、loop bind、loop split/fuse/reorder、loop expansion/contraction，把 `blockIdx.x/threadIdx.x` 这类并行变量与 `clusterId/coreId` 或标量循环之间互转
2. **Memory Conversion**：cache、pipeline——桥接 NVIDIA shared memory ↔ Cambricon NRAM/WRAM 等异构内存层次
3. **(De)Tensorization**：tensorize / detensorize——识别 GEMM / 卷积，替换为平台专用 intrinsic（`__bang_mlp`、`wmma::mma_sync`、`__builtin_amdgcn_mfma`）

每个 pass 内部 pipeline：程序标注（LLM + BM25 检索平台手册）→ meta-prompt 驱动的 transformation → bug localization（AST 遍历 + binary search 定位错 buffer，CFG 分类 index-error 还是 tensor-instruction-error）→ SMT 修复。性能上用**层级 auto-tuning**：intra-pass 用 brute-force 找 tiling 等参数；inter-pass 用 MCTS 搜索最优 pass 序列，以实际 kernel 执行时间作为 reward 回传。

## 关键结果

- 4 个 DLS（Intel DL Boost / NVIDIA / AMD MI / Cambricon MLU）之间互相翻译，算子正确率平均 **95%**
- 生成代码性能平均达 vendor 手调库（cuDNN / cuBLAS / oneDNN）的 **0.78×**
- CUDA C → BANG C 对比：OpenAI o1 few-shot 计算正确率仅 7.7%，QiMeng-Xpiler w/o SMT 54.2%，加 SMT 后 **91.7%**
- 编程生产力：相较 senior coder 手写 Deformable Attention，GPU 方向节省 **34.3×** 时间，MLU 方向节省 **96.0×**
- Case study on FlashAttention / FlashAttention-2：跨平台翻译后性能达原生实现的 0.61-0.81×

## 相关

- **相关概念**：[[Program-Synthesis]]、[[LLM-Code-Generation]]、[[Monte-Carlo-Tree-Search]]、[[Auto-Tuning]]、[[Flash-Attention]]
- **相关工作**：HIPIFY、C2Rust、PPCG（rule-based）、Tenspiler、MetaLift、C2TACO（symbolic）、TransCoder、StarCoder、GPT-4、OpenAI o1（data-driven）
- **同会议**：[[OSDI-2025]]
