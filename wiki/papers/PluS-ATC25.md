---
type: paper
name: PluS
full_title: "PluS: Highly Efficient and Expandable ML Compiler with Pluggable Graph Schedules"
authors: [Ruofan Wu, Zhen Zheng, Feng Zhang, Chuanjie Liu, Zaifeng Pan, Jidong Zhai, Xiaoyong Du]
venue: ATC
year: 2025
tags: [ml-compiler, graph-optimization, kernel-fusion, gpu, pattern-matching]
source_pdf: "[[atc2025-wu-ruofan.pdf]]"
source_md: "[[atc2025-wu-ruofan]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# PluS：具有可插入图形计划的高效且可扩展的机器学习编译器（ATC 2025）

> **原题**：PluS: Highly Efficient and Expandable ML Compiler with Pluggable Graph Schedules

> **一句话总结**：基于「子图 codegen schedule 主要由 MatMul/Reduce 等 skeleton operator 的 loop 骨架决定、而非精确 operator 组合」这一观察，PluS 用 loop-centric 的 +Graph 抽象 + 专家可插拔的 pattern warehouse 复用专家 kernel（[[CUTLASS]]、[[Flash-Attention]] 等），在 A100 上端到端比 TorchInductor 平均快 4.04×、比 TensorRT 快 1.77×，且用 18+129 LoC 即可支持 AITemplate 需 1701 LoC 的 T5LayerNorm。

## 问题与动机

[[ML-Compiler]]（[[XLA]]、TorchInductor、[[BladeDISC]]、TensorRT）把图变换规则 hard-code 在编译器内部，每出现一类新优化（[[Flash-Attention]]、fused MatMul-LayerNorm-MatMul）就要大改 fusion/codegen 模块，追不上 CUTLASS、ByteTransformer 等手写库。与此同时，模型架构呈「部分收敛、局部演化」趋势：attention backbone 稳定，但 RMSNorm、SwiGLU、T5LayerNorm 等小改动频繁出现。

模板类 pluggable 编译器（AITemplate）允许用户自定义子图，但按 **operator 组合精确匹配** pattern——`gemm_rcr_bias_gelu` 与 `gemm_rcr_gelu` 需两套前后端模板；T5 因缺 T5LayerNorm fused pattern 直接无法支持；且不支持 [[Dynamic-Shape]]。作者 claim 的边界是：不是要替代 [[TVM]]/Ansor 的自动 schedule search，而是让编译器 **快速接入已有专家子图实现**，同时比 operator-level template 更能容忍架构微变。

## 关键观察 / 隐含假设

- **观察 1：高性能子图的 codegen schedule 主要由 skeleton operator（MatmulOp、ReduceOp）的 loop 骨架决定，trivial elementwise 算子（Add/Sub/Exp）不改变 schedule 本质。** 论文以 MatMul+Softmax（被分解为 6 个 basic op）为例：CUTLASS 可将其优化为 3 kernel，但 embedded compiler 因 Softmax 被分解且 fusion 规则僵化而难以匹配；而 Add 换 Sub 不改变 loop 结构。
  - **依赖假设**：DNN 计算可表达为嵌套 loop；决定性能的 fusion/tiling 边界落在 MatMul/Reduce 等带 non-parallelizable axis 的 op 上。
  - **可能失效场景**：性能由 irregular sparse access、control flow、或大量小算子间复杂依赖主导时，loop skeleton 抽象可能过粗，不同 operator 组合仍需不同 schedule。

- **观察 2：子图识别应从 skeleton operator 出发贪心扩展，且需支持 partial match 以继续生长到 warehouse 中的完整 +Graph。** Fig. 6 的 MatMul→Softmax 案例显示，中间态 +Graph0 虽不完全匹配目标 +Graph1，但满足 partial match 条件（parallelism 可降级、嵌套 loop 数可增加、skeleton operation 一致），因此可继续 fuse Exp/ReduceSum/Divide。
  - **依赖假设**：专家在 pattern warehouse 中预定义的 +Graph 覆盖主流优化形态；`allow_prologue`/`allow_epilogue` 标志能正确约束扩展方向。
  - **可能失效场景**：warehouse 缺 pattern 时 greedy 停在「最后成功匹配」的子图，可能不是全局最优切分；多输出 op 的 fusion 优先级（先遇先 fuse）可能漏掉更优组合。

- **观察 3：端到端加速大量来自 vendor 专家 kernel 的按需集成，而非仅 +Graph 匹配本身。** BERT case study 显示 >95% 执行时间集中在 10 类子图，PluS 为不同 shape/batch 动态选 CUTLASS、ByteTransformer、FlashAttention；关掉优化 kernel 源后子图仍比 PyTorch eager 快 4.79×/13.27×，但 headline 4.04× 相对 TorchInductor 的增益叠加了这些外部实现。
  - **依赖假设**：pattern warehouse 持续维护与硬件/模型演进同步的高质量 kernel；专家能为新 +Graph 编写正确 +Code 模板。
  - **可能失效场景**：新模型出现全新 loop skeleton（如非标准 attention variant）时，仍需人工补 pattern；warehouse 质量不均会导致性能方差。

- **假设 1：loop-centric +Graph 足以唯一标识子图，且四种 transformation primitive 合并后表示 deterministic。**
  - **证据强度**：中。Softmax、LayerNorm、T5LayerNorm 等案例展示了一致性，但论文未形式化证明所有合法 fusion 路径下 +Graph 唯一，也未讨论 ambiguous merge 的完备处理。

- **假设 2：推理 workload（固定/弱动态 shape、batch 1/16、seq 128）能代表 compiler 价值。**
  - **证据强度**：弱–中。五类 transformer 覆盖 NLP/CV，但无 LLM 长上下文、training、或 multi-GPU serving；dynamic shape 支持主要在机制层面验证，实验矩阵仍以固定 shape 为主。

## 核心方法

PluS 把图变换从编译器内核解耦为 **pluggable pattern warehouse**，编译流水线为：PyTorch model → TorchDynamo/`torch.fx.GraphModule` → Hidet 解析为 low-level op 图 → +Graph pattern matching → +Code 模板 codegen。

**+Loop / +Graph 抽象**（回应观察 1）：每个 operator 表达为 +Loop 树，属性为 size（int 或 symbolic）、parallelism（parallelizable / non-parallelizable）、operation（仅记录 dot、reduceMax 等决定 schedule 的关键 op）。多 op 融合时通过四种 primitive 变换 +Loop：同 size 同 parallel merge（Primitive 1）、parallel→non-parallel merge（Primitive 2）、non-parallel 后新建 loop（Primitive 3）、嵌套 loop collapse（Primitive 4）。结果 +Graph 作为 pattern identifier，使 Matmul+Bias 与 Matmul（无 Bias）共享 codegen。

**子图识别**（回应观察 2）：从 skeleton op（至少一个 non-parallelizable +Loop）或 root op 出发，`MatchFromSkeletonOp` 按 `allow_prologue`/`allow_epilogue` 贪心扩展 prologue/epilogue；epilogue 融合后还向 producer 回溯（如 Add 的另一输入来自 DivideScalar）。匹配时先查 perfect match，否则用 recursive +Loop tree traversal 判 partial match（warehouse 中 non-parallel loop 可对应 subgraph 中 parallel loop；parallel 必须保持；嵌套数 warehouse ≥ subgraph；声明的 operation 必须精确匹配）。优先级：epilogue 优于 prologue（避免重复 load）；多输出分叉不强制优先级，先遍历到先 fuse。

**+Code 与 codegen**（回应观察 3）：专家为每个 +Graph 提供 `data placeholder / compute / writeback` 模板；编译器保留子图识别期的 tensor 依赖与 addressing，从 +Loop 叶节点向上填充 trivial op 的 load/compute。支持 CUTLASS wrapper 路径。Dynamic shape 用 symbolic dimension 贯穿识别与 codegen，同一 +Graph 可挂多个实现并由模板内 shape routing 选择。

实现上集成 CUTLASS、ByteTransformer、[[Flash-Attention]]、FlashInfer；pattern 可通过提交 `torch.nn.Module` 自动抽 +Graph，或手工定义 +Graph 与 +Code。

深度细节回 [[atc2025-wu-ruofan]] 或 [[atc2025-wu-ruofan.pdf]]。

## 设计取舍

- **用 loop 抽象换 operator 精确匹配**：+Graph 忽略 trivial op 差异，使 T5 无-bias Linear 复用 BERT Matmul+Bias schedule（AITemplate 需 250+ LoC 新模板）。代价是 operation property 仍须专家正确标注，否则错误共享 schedule 会影响正确性或性能。
- **用 greedy 最大子图换编译复杂度**：持续扩展直到 partial match 失败，保留「最后成功匹配」子图。收益是更大 [[Operator-Fusion]] 范围（T5 220 layers vs TensorRT 247）；风险是局部 greedy 非全局最优，且多输出分叉策略可能固化次优切分。
- **用 expert warehouse 换编译器敏捷性**：新优化无需改 PluS 核心，只需加 +Graph/+Code 或 Module。代价是长期维护负担转移到专家社区/厂商；warehouse 不一致时性能依赖「谁写了模板」。
- **用 PyTorch/TorchDynamo 后端换通用性**：当前实现绑定 PyTorch + Hidet 解析路径，论文称可移植到 [[TVM]]/Grappler 但未实现。对其他 framework 或 training graph 的支持尚属 claim。
- **边界条件**：在「主流 transformer 子图 + 已有 vendor kernel + CUDA GPU」上最优雅；新 attention variant、重度 dynamic shape routing、或 CPU/非 NVIDIA 后端时，+Graph warehouse 需重新建设，优势取决于模板库厚度而非编译器核心。

## 实验与结果

- **端到端延迟（A100）**：BERT/ALBERT/GPT2/T5/ViT，batch 1/16，seq 128（ViT 224×224）；平均比 TorchInductor 快 **4.04×**，比 TensorRT（ONNX Runtime provider）快 **1.77×**；RTX 4090 上为 **4.59× / 2.01×**。
- **对比 AITemplate**：A100 平均快 **7.8%**，RTX 4090 快 **7.2%**；AITemplate 无法报告 T5；PluS 支持 dynamic shape，AITemplate 仅 static。
- **Fusion rate**：相对原始 #Ops，PluS 融合后 #Layers 平均比 TorchInductor 少 **2.08×**、比 TensorRT 少 **1.25×**；与 AITemplate 相近（BERT 87 vs 88 layers），但 T5 220 layers（AITemplate N/A）。
- **子图级（BERT, A100）**：占 >95% 时间的 10 类子图，比 TensorRT 平均快 **1.53×**、比 AITemplate 快 **1.07×**；attention 子图 batch 16 用 FlashAttention、batch 1 用 ByteTransformer。
- **Ablation**：关闭 CUTLASS/ByteTransformer/FlashAttention 后，10 子图仍比 PyTorch eager 快 **4.79×**（bs=16）和 **13.27×**（bs=1）；说明 +Graph fusion 本身有价值，但 headline 对比已含专家 kernel。
- **可移植性**：T5LayerNorm——AITemplate 需 **1701 LoC**（前端 453 + 后端 1248），PluS 需 **18 LoC** +Graph + **129 LoC** 模板；T5 无-bias Matmul 零额外 LoC。
- **编译开销**：缓存后 **18–25 s**（NVCC 主导），首次 **1–2 min**；CPU 内存额外 **130–190 MB**。
- **正确性**：相对 PyTorch eager，子图输出最大绝对误差 **1.9e-3**，平均 **3.57e-5**。

## 批判性分析

### 论证链条

论文链条清晰：embedded compiler 僵化 → pluggable 但 operator-exact 的 AITemplate 不适应架构微变 → loop skeleton 可统一不同组合 → +Graph matching + warehouse 快速接专家 kernel → 端到端显著加速 + T5 低 LoC 案例。最强证据是 **T5 可编译性** 与 **子图 vendor 选择** 的对应关系，而不只是平均 speedup 数字。

薄弱环节在于：4.04× vs TorchInductor 混合了 (1) 更广 fusion、(2) 外部专家 kernel、(3) baseline 配置差异（TorchInductor 关闭 dynamic shape；TensorRT 对 T5 用 Nsight 纯 kernel 时间替代端到端）。论证把「pluggable schedule 机制」与「集成了更多已有优化」部分绑在一起，读者需靠 ablation 才能拆分 fusion 本身与 vendor kernel 的贡献。

### 假设压力测试

**workload assumption**：五类经典 encoder 模型、短 seq（128）、小 batch（1/16）、推理 only。LLM 长上下文、decode-heavy serving、多模态新算子、training backward 图未覆盖。T5 案例证明 portability，但不代表所有 normalization/activation 变体都能用少量 LoC 解决——前提是变体仍共享后续 +Loop 结构。

**resource bottleneck assumption**：默认瓶颈在 GPU kernel 效率与 [[Kernel-Fusion]] 范围，而非 CPU dispatch、编译缓存、或 host-device 传输。T5 在 TensorRT 上出现异常长的 H2D 传输，论文用 profiling 特例处理；说明端到端 metric 对 deployment 细节敏感，PluS 在「kernel 已优化」假设下更有利。

**hardware/deployment assumption**：NVIDIA A100/4090、CUDA 11.8、Ubuntu 22.04；warehouse 内核来自 NVIDIA 生态（CUTLASS）和 transformer 专用库。AMD GPU、CPU inference、或集群 multi-GPU 未评估；pattern warehouse 的可移植性依赖目标后端是否有对应专家实现。

**scaling assumption**：模型规模固定在 base 级（BERT-base 等），未测试更大 width/depth 或 shape 外推。Dynamic shape 机制存在，但主实验矩阵未系统扫 seq/batch 范围；TensorRT 引擎允许 batch 1–32、seq 64–256，与 PluS 固定 shape 对比不完全对称。

**correctness/SLO assumption**：数值误差在 fp32 随机输入下很小，但未讨论 fp16/bf16、极端 shape、或错误 +Graph 导致 silent miscompile 的检测机制。尾延迟、编译失败回退、多 tenant 隔离、A/B 切换 pattern 的运维流程论文未讨论。

### 实验可信度

**强项**：baseline 含 TorchInductor、TensorRT、AITemplate 三条代表路线；fusion rate 表（Table 1）与 latency 图交叉验证「更多 fusion + 更好 kernel」叙事；子图级 breakdown（Table 2 + Fig. 11）把 attention/GEMM/LayerNorm 路径说清楚；T5 LoC 对比是可复现的 portability 证据。

**弱项**：TorchInductor 禁用 dynamic shape 可能压低其表现；TensorRT T5 非标准端到端 metric；AITemplate 在 T5 上缺失使部分对比不完整。未与 BladeDISC、TVM+BYOC、FlexAttention 等更新系统对比。7.8% 相对 AITemplate 的提升较小，claim 更应强调 **coverage/flexibility** 而非纯性能碾压。

### 系统性缺陷

**Warehouse 运维**：性能与安全性依赖专家维护的 +Graph/+Code；论文未讨论 pattern 版本管理、冲突检测、自动测试流水线。错误 partial match 停止条件可能产出非直觉子图切分，调试需理解 +Loop 树，可观测性成本高。

**编译与部署**：首次编译 1–2 min、NVCC 绑定，对 serverless 或频繁换模型场景可能是负担；论文未讨论编译缓存失效、多模型共存、或 incremental compile。

**Greedy matching 脆弱性**：多输出 fusion 顺序、prologue/epilogue 优先级是启发式；论文未给 counterexample 实验。与 auto-tuner（Ansor/AutoTVM）结合路径仅停留在 related work 设想。

**范围缺口**：training、分布式、非 CUDA、非 PyTorch 前端论文未讨论；正确性验证仅限数值 diff，未覆盖 numerical stability under mixed precision。

## 局限与后续工作

- **局限 1**：性能增益与外部专家 kernel 库强绑定；关掉后仍有 fusion 收益，但与 TorchInductor/TensorRT 的差距需更系统化分解（论文有 ablation 但仅在 BERT 10 子图上）。
- **局限 2**：baseline 配置不完全对称（dynamic shape、T5 TensorRT metric），可能放大相对收益。
- **局限 3**：greedy + partial match 的正确性与最优性缺乏形式化保证；复杂图结构下的 matching ambiguity 未充分评测。
- **局限 4**：warehouse 长期维护、测试、版本兼容与生产 rollback 机制论文未讨论。
- **Future work 1**：在统一 dynamic shape 设置下，扫 seq/batch/width 网格，测量 +Graph 复用率与 kernel routing 命中率，验证 loop abstraction 的外推边界。
- **Future work 2**：与 TVM BYOC / TorchInductor custom op / FlexAttention 等路径对比，固定同一组 expert kernel，只变融合框架，分离「pluggable matching」的纯贡献。
- **Future work 3**：为 +Graph pattern 建立 differential testing 与 miscompile 检测；评估 wrong operation tag 的失败模式。
- **Future work 4**：将 PluS 接到 training graph 与 multi-GPU serving，测量 compilation amortization、tail latency 与 pattern 热更新成本。

## 相关

- **相关概念**：[[ML-Compiler]]、[[Operator-Fusion]]、[[Kernel-Fusion]]、[[Flash-Attention]]、[[CUTLASS]]、[[Dynamic-Shape]]、[[Attention]]、[[PyTorch]]
- **同类系统**：[[TVM]]、AITemplate、TorchInductor、TensorRT、[[BladeDISC]]、[[XLA]]、DNNFusion、FlexAttention
- **同会议**：[[ATC-2025]]
- **对比**：pluggable template（AITemplate）vs loop-centric pluggable schedule（PluS）；embedded rule-based fusion（TorchInductor/TensorRT）vs expert warehouse
