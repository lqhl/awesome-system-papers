---
type: paper
name: QFactory
full_title: "QFactory: Accelerating Quantized Large Language Model Serving with Qtile Graphs"
authors: [Qihao Zhang, Mingshu Zhai, Rui Sun, Jidong Zhai]
venue: ATC
year: 2025
tags: [quantization, llm-inference, compiler, gpu-kernel, qtile]
source_pdf: "[[atc2025-zhang-qihao.pdf]]"
source_md: "[[atc2025-zhang-qihao]]"
---

# QFactory: Accelerating Quantized Large Language Model Serving with Qtile Graphs (ATC 2025)

> **一句话总结**：核心观察是 fine-grained asymmetric quantization 下 dequantization 与 quant params 加载会反超 weight 压缩收益，而 eager dequant 又锁死 graph 重写空间；QFactory 用 Qtile/QGraph 延迟 dequant + 分层 memory scheduling + ML auto-tuning 生成量化 kernel，单 kernel 平均比 BitBLAS 快 1.66×，集成 [[vLLM]] 端到端解码加速 1.23×。

## 问题与动机

[[Quantization]] 是降低 [[LLM]] serving 内存压力、加速 decoding 的关键手段：低 batch 下 decoding 本质是 memory-bound，压缩 weight 并 on-the-fly dequantize 能直接减少 DRAM 访问量。但随着 bit-width 降到 4-bit 甚至 2-bit，fine-grained 算法（如 [[GPTQ]]）引入 asymmetric、group-wise 的 scale/zero 等辅助参数，dequantization 本身变成额外计算与访存瓶颈。

现有路径大致两类：手工优化 kernel 库（如 Marlin）和 DL 编译器（如 BitBLAS，基于 TVM/Welder 的 tile 抽象）。它们共同问题是 **eager execution paradigm**——遇到量化张量立即按算法定义 dequantize，导致两方面损失：一是无法探索 dequant 操作在计算图上的等价重写（例如把 bias 从 A 的 quant params 挪到 B）；二是每个 weight 元素独立 dequant，忽略 group 内 quant params 共享，浪费 memory bandwidth。

作者 claim 的边界是：QFactory 是 **weight-only quantization kernel 编译框架**，聚焦 linear/matmul 类算子在 decoding（batch=1）场景下的性能，不覆盖 activation quantization 或端到端 serving 调度。论文用 BitBLAS 作为 SOTA compiler baseline、Marlin 作为手工 kernel baseline，并在 [[vLLM]] 里做端到端验证。

## 关键观察 / 隐含假设

- **观察 1：bit-width 越低，quant params 访存占比越高，eager dequant 劣化越严重。** BitBLAS 编译 asymmetric W4A16 kernel 比 simple type-casting 慢约 30%；H100 上 W8/W4/W2 相对 BitBLAS 平均加速分别为 1.17×、1.52×、1.66×，gap 随 bit-width 下降而扩大（§7.1、§7.2）。
  - **依赖假设**：评测 workload 以 weight-only、group size 128 的 asymmetric quantization 为主；kernel 瓶颈在 DRAM/L2 带宽而非 compute。
  - **可能失效场景**：batch size 增大后 kernel 转向 compute-bound，weight-only 压缩的理论加速会衰减（论文 §9 明确承认）；joint weight-activation quantization 会改变访存比例。

- **观察 2：dequantization 可以延迟并沿 QGraph propagate，代数等价变换能减少实际 dequant 次数。** 例如 matmul 中 $A_{z_1} \cdot B_{z_2}$ 可展开为 $AB + (J_A B)^{z_1} + (A J_B)^{z_2} + (J_{AB})^{z_1 z_2 K}$，利用 $J$ 矩阵全 1 性质把部分 dequant 塌缩为标量或单行 broadcast（§4.3、Table 2）。
  - **依赖假设**：变换保持数学等价；支持的 op 集合（element-wise add、matmul）覆盖 QLLM linear 层主体；group pattern 可通过 gcd 等规则合并。
  - **可能失效场景**：更复杂 op（layernorm、activation、MoE routing）若未纳入 Qtile 规则，优化空间会缩回 linear 局部；非线性 quant 格式或 lookup-table quant 的 mapping function 变换可能爆炸。

- **观察 3：weight tile、activation tile、quant params 应走不同 GPU memory path 才能最大化带宽。** decoding 下 weight 不被跨 thread block 复用，适合 .cs evict-first 绕过 L1/L2；quant params 在 group 内共享，适合 shared memory 复用；H100 高 occupancy 场景可牺牲 activation 的 shared cache 换更多 SM 活跃（schedule a/b/c/d，§5.2）。
  - **依赖假设**：评测硬件为 NVIDIA V100/A100/H100，PTX cache operator 与（可选）TMA/async copy 可用；matrix shape 落在 LLM 实际层尺寸（中等规模，非超大方阵）。
  - **可能失效场景**：QFactory 对超大矩阵的优势会收敛——所有方法都接近 H100 ~90% 峰值带宽（~2TB/s）；V100 上 W8 仅 0.99× BitBLAS；Marlin 依赖 Ampere 异步 copy，V100 无法对比。

- **隐含假设：LLM decoding 长期以 batch=1、prompt 短、generation 为主路径。**
  - **证据强度**：强。端到端实验固定 batch=1、prompt 16、generation 128 tokens；kernel benchmark 也设 activation batch=1。这与 memory-bound weight-only quant 的设计目标一致，但不代表 prefill 或高并发 serving。

## 核心方法

QFactory 的入口是用户提供的 quantized program，先被转成 **Qtile-graph (QGraph)**：把图中量化张量替换为 **Qtile**——带 mapping function（存储格式、压缩/非对称算法、辅助参数）和 group pattern（tensor/channel/block/individual 四级共享粒度）注解的 tensor tile。Qtile 把 weight 与 quant params 绑定，使编译器能推导二者复用关系。

**Qtile Computation Transformation（§4）** 是 graph-level 核心。对每个 op，若输入含 Qtile 且满足规则，则 `ComputeQtile` 直接产出量化注解的输出 Qtile，而非立即 dequant。算法 1 用 BFS 枚举所有等价 QGraph。变换分两类：group pattern 合并（如两 block Qtile 取 stride gcd）和 mapping function 代数重写（Table 1/2 覆盖 add/matmul）。目标是推迟 dequant 插入点、减少重 dequant 次数、甚至在传播中切换到更轻量的 symmetric 格式。

**Differentiated Qtile Scheduling（§5）** 在选定 QGraph 后决定各 tile 的 memory hierarchy 路径。相对 BitBLAS/Welder 只优化 weight tile 的做法，QFactory 显式区分 activation、compressed weight、scale/zero 的加载策略，并结合 .cg/.cs cache operator、shared memory 复用、register-level 复用（极细 group 时）。这与 [[Welder]] 的 tile-graph scheduling 一脉相承，但针对 quant params 做了专门扩展。

**实现层（§6）** 采用 CUTLASS 风格模板生成 CUDA，把 matrix shape 等作为 compile-time constant 消除分支；用 BitBLAS/Marlin 已有的 fast int→fp16 casting 技巧。auto-tuning 搜索空间因 QGraph 候选和 scheduling 组合而膨胀，故用 **MLP 预测 bandwidth utilization**（非直接预测 latency），离线 profile 50 个随机配置训练，在线通常 **≤15 次 trial** 即可接近最优（§7.6）。数学上非等价的变换被排除，论文验证输出 token 与 baseline 一致。

## 设计取舍

- **延迟 dequant 换编译复杂度**：QGraph 搜索、Qtile 代数表、多种 schedule 显著扩大编译与 tuning 时间；全枚举单模型可达数小时，靠 ML selector 和可复用 profile 缓解，但首次部署仍有编译成本。
- **通用编译框架换 peak 手工优化**：H100 4-bit 上比 Marlin 快 1.30×，但 A100 上仅 1.04×；batch≥4 时 Marlin 借助手工 Tensor Core MMA 优化反超 QFactory（Table 3：QFactory 3.18× vs Marlin 2.54× cuBLAS，但 Marlin 在大 batch 更占优）。作者称二者正交、可工程整合，但论文未实现。
- **weight-only 聚焦换适用范围**：当前只支持 weight-only quant，避开 activation quant 的精度与算子耦合；扩展 W4A4 等需重新定义 Qtile 传播规则（§9 future work）。
- **中等矩阵优势换超大矩阵边际**：真实 LLM 最大 weight matrix（如 Llama2-70B gate/up 约 28,672×8,192）仍属 QFactory 甜点区；极大方阵上大家趋近峰值带宽，优势缩小。

## 实验与结果

- **Kernel-level（H100，asymmetric W8/W4/W2，group 128×1）**：相对 BitBLAS 几何平均 1.17× / 1.52× / 1.66×；4-bit 比 Marlin 1.30×。矩阵含 4096–16384 方阵及 Llama2-13B、Qwen2.5-72B 层形状。
- **Kernel-level（A100）**：相对 BitBLAS 1.17× / 1.40× / 1.71×；相对 Marlin 1.04×（4-bit）。**V100**：相对 BitBLAS 0.99× / 1.17× / 1.41×；Marlin 不支持。
- **Bandwidth**：H100 4-bit asymmetric 下 QFactory 在中等 weight matrix 上持续高于 BitBLAS/Marlin；bit-width 从 8→2 时 BitBLAS 利用率显著下滑而 QFactory 更稳（Figure 9–10）。
- **End-to-end（[[vLLM]] 集成，GPTQ group=128，batch=1，prompt 16，gen 128）**：H100 4-bit 相对 llama.cpp / Marlin / BitBLAS 几何平均 1.21× / 1.32× / 1.03×；2-bit 相对 llama.cpp / BitBLAS 1.58× / 1.23×（Marlin 不支持 2-bit）。大模型（Llama2-70B、Qwen2.5-72B）收益更明显。A100 趋势类似，Qwen-72B OOM。
- **Ablation（Figure 13）**：Base 模板在 2-bit 因对齐问题甚至差于 BitBLAS；+TemplateGen 大幅改善；+Transformation 与 +Scheduling 进一步拉开差距。
- **Batch scaling（Table 3，W4A16，H100）**：batch 1/2/4 相对 FP16 cuBLAS，QFactory 为 3.44× / 3.18× / 2.52×，始终优于 BitBLAS，但 batch 4 时被 Marlin 超过。
- **Auto-tuning**：MLP selector 多数 shape 在 15 trials 内达到搜索空间最优带宽（Figure 14）。

## Critical Analysis

### 论证链条

主链条清晰：**fine-grained quant 使 dequant+aux params 成为新瓶颈 → eager dequant 浪费 graph 与 bandwidth 优化空间 → Qtile 延迟 dequant + 分层 scheduling → kernel 与端到端加速**。Ablation 逐步加上 TemplateGen、Transformation、Scheduling，能对应设计分解，逻辑闭合度较好。

薄弱处在于 **端到端增益小于 kernel 增益**（1.66× kernel vs 1.23× e2e）：说明 non-linear 层、kernel launch、框架开销仍占显著比例，论文未量化各层贡献。另一个跳步是 **将 Llama/Qwen + GPTQ + vLLM 结果外推为“广泛 QLLM serving 加速”**——llama.cpp 使用不同 quant 格式（GGUF Q4_0/Q2_K），虽作者努力对齐 workload，但格式差异使对比含混。

### 假设压力测试

**Decoding-only / batch=1** 是最强假设。Table 3 已显示 batch 增大时优势收窄且 Marlin 反超；prefill 阶段 activation 更大、更接近 compute-bound，QFactory 的 memory-path 优化价值可能下降。论文未测 prefill 或 mixed batch。

**Quant 格式泛化**：实验集中在 GPTQ 式 group-128 asymmetric（e2e）与 asymmetric WxA16 kernel。AWQ、[[SmoothQuant]]、lookup-table、2:4 sparse 等格式的 Qtile 规则是否即插即用，论文只在 related work 中讨论，未实验验证。

**硬件代际**：Marlin 在 A100 极强、在 H100 需改源码才跑；QFactory 强调跨 V100/A100/H100 的 compiler 通用性，但 V100 W8 并无优势。若未来 kernel 更依赖 Hopper TMA/WGMMA 等专用指令，template+MLP 路线是否仍能与新一代手工库持平，需要持续验证。

### 实验可信度

**Baseline 选取合理**：BitBLAS 代表 compiler SOTA，Marlin 代表手工 W4 kernel，llama.cpp 代表流行部署路径；kernel 测试 flush L2、200 warmup + 100 measure，方法论扎实。端到端通过 vLLM 统一集成 BitBLAS/Marlin/QFactory，并验证 token 一致性，正确性可信。

**不足**：(1) 端到端仅 decode 短 generation，未覆盖长上下文、连续 batching、[[Continuous-Batching]] 多请求交错；(2) 与 [[vLLM]] 原生 [[PagedAttention]]/[[Quantization]] 路径以外的系统（TensorRT-LLM、[[SGLang]]、ExLlama）未比较；(3) tail latency、编译耗时对冷启动的影响论文未讨论；(4) 2-bit 排除 Llama2-7B（hidden 11008 不满足 128×4 对齐），说明实现对齐约束仍会造成模型覆盖空洞。

### 系统性缺陷

- **编译与部署成本**：尽管 15-trial selector 降低在线 tuning，全搜索仍可达数小时/模型；生产环境多模型、多 shape 时编译缓存策略论文未讨论。
- **尾延迟与隔离**：论文未讨论 auto-tuning 失败回退、kernel 选择错误、或不同 quant 层配置并存时的行为。
- **可观测性**：作为编译框架，如何向 serving runtime 暴露所选 QGraph/schedule、如何 debug 性能回退，论文未涉及。
- **与 serving 栈协同**：仅替换 linear quant kernel；[[KV-Cache]]、[[Speculative-Decoding]]、[[Disaggregation]] 等系统级优化正交但未集成评估。
- **Activation quant 缺失**：在 batch 增大或 W4A4 趋势下，仅优化 weight path 可能不够；论文承认但未给出路线图细节。

## 局限与 Future Work

- **局限 1：仅支持 weight-only quantization。** batch 增大后 kernel 变 compute-bound，理论加速消失（§9）。Future work：扩展 Qtile 传播到 activation-weight joint quant（W4A4 等），并测量是否能在更大 batch 维持加速。
- **局限 2：大 batch 下落后于 Marlin。** Future work：将 Marlin 式手工 Tensor Core MMA 优化与 QFactory 的 QGraph/scheduling 整合，或在 selector 中按 batch shape 切换 backend。
- **局限 3：算子与格式覆盖未知边界。** Future work：对 AWQ、FP6、LUT-based quant 做 Qtile 规则完备性测试；量化 MoE expert linear 的 group pattern 变化对 propagate 的影响。
- **局限 4：端到端评测场景偏窄。** Future work：在 [[Continuous-Batching]]、长 prompt prefill+decode 混合、多租户并发下测量 TTFT/TPOT 分布，而不只 mean tokens/s。
- **局限 5：编译开销未纳入 TCO。** Future work：报告 per-model 首次编译时间、增量 tuning 成本、与预编译 kernel cache（如 Marlin 预置）的 trade-off。

## 相关

- **相关概念**：[[Quantization]]、[[KV-Cache]]、[[Continuous-Batching]]、[[PagedAttention]]
- **同类系统**：[[vLLM]]、BitBLAS、Marlin、llama.cpp、Welder、TVM、CUTLASS
- **相关算法**：[[GPTQ]]、AWQ、SmoothQuant
- **同会议**：[[ATC-2025]]
- **对比**：QFactory 相对 BitBLAS 的核心差异在 **延迟 dequant 的 QGraph** 与 **quant-params-aware scheduling**，相对 Marlin 的核心差异在 **跨 GPU 代际的编译器通用性** 而非单点手工 MMA