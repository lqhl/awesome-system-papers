---
type: paper
name: QiMeng-Xpiler
full_title: "QiMeng-Xpiler: Transcompiling Tensor Programs for Deep Learning Systems with a Neural-Symbolic Approach"
authors: [Shouyang Dong, Yuanbo Wen, Jun Bi, Di Huang, Jiaming Guo, et al.]
venue: OSDI
year: 2025
tags: [transcompiler, tensor-program, llm, gpu, neural-symbolic]
source_pdf: "[[osdi25-dong.pdf]]"
source_md: "[[osdi25-dong]]"
---

# QiMeng-Xpiler: Transcompiling Tensor Programs for Deep Learning Systems with a Neural-Symbolic Approach (OSDI 2025)

> **一句话总结**：QiMeng-Xpiler 把 tensor 程序翻译拆成 11 类 LLM 变换 pass + 小范围 Z3 修补，在 CUDA/HIP/VNNI/BANG 四平台平均 **95%** 计算正确率，性能达 cuDNN/oneDNN 手工库的 **0.78×**，生产力最高 **96×**。

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

- 4 平台：compilation ~95%，computation accuracy ~95%（平均）。
- 性能：0.78× cuDNN/cuBLAS/oneDNN 等手工库（按算子变化）。
- 生产力：GPU 34.3×、MLU 96.0× vs 手工移植（论文定义的开发时间模型）。

## Critical Analysis

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

## 局限与 Future Work

- **局限 1**：性能未全面超越手工库；依赖外部 LLM。
- **局限 2**：新硬件需人工扩展 pass 与手册管线。
- **Future work 1**：开源/local LLM 降成本；更强 equivalence checker。
- **Future work 2**：与 Ansor 联合做 cross-platform auto-tuning。

## 相关

- **相关概念**：[[Quantization]]、[[Tensor-Parallelism]]
- **同类系统**：TVM、Triton、FCUDA、TransCoder
- **同会议**：[[OSDI-2025]]