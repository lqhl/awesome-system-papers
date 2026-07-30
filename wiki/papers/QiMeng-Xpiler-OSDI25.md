---
type: paper
name: QiMeng-Xpiler
full_title: "QiMeng-Xpiler: Transcompiling Tensor Programs for Deep Learning Systems with a Neural-Symbolic Approach"
authors: [Shouyang Dong, Yuanbo Wen, Jun Bi, Di Huang, Jiaming Guo, Jianxing Xu, Ruibai Xu, Xinkai Song, Yifan Hao, Ling Li, Xuehai Zhou, Tianshi Chen, Qi Guo, Yunji Chen]
venue: OSDI
year: 2025
tags: [transcompiler, tensor-program, llm, gpu, neural-symbolic]
source_pdf: "[[osdi25-dong.pdf]]"
source_md: "[[osdi25-dong]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# QiMeng-Xpiler：使用神经符号方法转编译深度学习系统的张量程序（OSDI 2025）

> **原题**：QiMeng-Xpiler: Transcompiling Tensor Programs for Deep Learning Systems with a Neural-Symbolic Approach

> **一句话总结**：QiMeng-Xpiler 将 tensor 程序翻译拆成 11 类 LLM pass 与小范围 SMT 修补。其 unit-test computation accuracy 跨方向为 **86.9%–100%**，不是语义保证；正确案例的平均性能为手工优化对应实现的 **0.78×**。

## 问题与动机

数据中心部署 NVIDIA/AMD/Intel/Cambricon 等多类 DLS，需为每平台手写 tensor 程序。规则翻译、符号合成、纯 LLM 三条路分别困于人工规则、搜索空间爆炸、GPT-4 单步 **92.3%** 计算错误率（并行/内存/intrinsic 三类错误）。

目标：**Write Once, Run Anywhere** 且保证语义正确，并尽量接近 vendor 优化库性能。

## 关键观察 / 隐含假设

- **观察 1**：LLM 擅长大纲（控制流、intrinsic 选型），SMT 擅长 loop bound/index；单步 LLM 在 parallelism/memory/instruction 上几乎全失败。
  - **依赖假设**：分 pass 后每步错误局部化，SMT 可在有限窗口修复。
  - **证据强度**：强——错误分类表 + 95% 平均正确率。
- **观察 2**：DLS 差异集中在 parallelism、memory hierarchy、specialized intrinsics 三类，可用 11 个变换 pass 覆盖。
  - **依赖假设**：新平台可通过扩展 pass + 编程手册 BM25 检索接入。
  - **可能失效场景**：全新编程模型（非 SIMT/SIMD/task 并行）需新 pass 类。
- **假设 1**：MCTS 搜 pass 序列 + brute-force 搜 tile 参数可逼近专家性能。
  - **证据强度**：中——0.78× vendor 库，但未全面超越。

## 核心方法

**Neural-symbolic pipeline**：annotation（LLM 语义 + BM25 手册）→ meta-prompt 变换 → unit test → 失败则 SMT 修补。

**三类 pass**：(de)sequentialization/parallelization、memory conversion、(de)tensorization。

**Hierarchical auto-tuning**：intra-pass 暴力搜参数；inter-pass MCTS 搜 pass 顺序。

## 设计取舍

- **取舍 1**：依赖 GPT-4 API 成本与延迟，换开发效率。
- **取舍 2**：SMT 仅小范围，放弃全局最优证明。
- **边界条件**：新 DLS 扩展需手册质量与 pass 设计人力。

## 实验与结果

**指标、基线与边界**：unit-test computation accuracy、execution performance、translation/tuning time；QiMeng-Xpiler vs GPT-4/o1/PPCG/HIPIFY 或 vendor library；4 个 DLS、21 operators×8 shapes（§7–8）。

- 四个 DLS 的 168 cases 中，按方向 computation accuracy 为 **86.9%–100%**（§8.1，Table 8）。CUDA→BANG 完整系统为 **100%** compilation、**91.7%** computation；去 SMT 为 **82.7%/54.2%**（§8.2）。
- 所有功能正确案例中，平均执行性能为对应 cuDNN/cuBLAS/CNNL/rocBLAS/oneDNN 手工实现的 **0.78×**（§8.3，Fig.7）。
- CUDA→BANG 六个典型算子的编译/调优为 **1.2–7.8 h**（平均 **3.7 h**）（§8.4，Fig.8）。
- Deformable Attention 的单一生产力试验中，junior VNNI→CUDA 为 **34.3×**，junior CUDA→BANG 为约 **96.0×**，后者含 3 h debug 且性能为手工实现的 **65.17%**（§8.5，Table 10）。

## 论断—证据表

| 论断 | 证据 | 指标 / 基线 / 评测边界 | 定位 | 置信度 |
|---|---|---|---|---|
| 翻译正确率受方向与测试集限制 | 86.9%–100% unit-test accuracy | 4 DLS、21 operators×8 shapes；非形式化语义验证 | §7–8.1，Table 8 | high |
| SMT 促进特定 SIMT→SIMD 翻译，但不能保证全正确 | CUDA→BANG 91.7% vs 去 SMT 54.2% computation | CUDA→BANG direction；vs w/o SMT | §8.1–8.2，Table 8 | high |
| 性能结论只涵盖 functionally correct operators | 平均 0.78× | 4 common directions、对应 vendor libraries | §8.3，Fig.7 | high |
| 自动化有小时级调优成本 | 1.2–7.8 h、平均 3.7 h | CUDA→BANG、6 operators；无 compilation-speed competitor | §8.4，Fig.8 | high |
| 生产力案例是小样本/单算子测量 | 34.3×、96.0×及其 debug/性能条件 | 2 junior 与 2 senior、Deformable Attention | §8.5，Table 10 | high |

## 批判性分析

### 论证链条

DLS 异构 → 单步 LLM 不够 → pass 分解+SMT 修补 → MCTS 调优 → 高正确率与可接受性能。链条在评测算子集闭合；全模型端到端 serving 未claim。

### 假设压力测试

- LLM 版本/训练数据漂移导致 pass 质量下降。
- 极长 kernel SMT 窗口仍可能爆炸。
- 0.78× vendor 库对 latency-critical 生产是否足够需 workload 定义。

### 实验可信度

四平台多样性好；vendor 库是强 baseline。生产力倍数依赖方法论假设，需独立验证。

### 系统性缺陷

论文未讨论：CI 集成、编译失败 fallback、安全审计生成代码、与 TVM/Ansor 生态分工。

## 局限与后续工作

- **局限 1**：性能未全面超越手工库；依赖外部 LLM。
- **局限 2**：新硬件需人工扩展 pass 与手册管线。
- **Future work 1**：开源/local LLM 降成本；更强 equivalence checker。
- **Future work 2**：与 Ansor 联合做 cross-platform auto-tuning。

## 相关

- **相关概念**：[[Quantization]]、[[Tensor-Parallelism]]
- **同类系统**：TVM、Triton、FCUDA、TransCoder
- **同会议**：[[OSDI-2025]]
