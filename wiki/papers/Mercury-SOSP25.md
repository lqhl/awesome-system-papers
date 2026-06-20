---
type: paper
name: Mercury
full_title: "Mercury: Unlocking Multi-GPU Operator Optimization for LLMs via Remote Memory Scheduling"
authors: [Yue Guan, Xinwei Qiang, Zaifeng Pan, Daniels Johnson, Yuanwei Fang, et al.]
venue: SOSP
year: 2025
tags: [multi-gpu, llm, compiler, distributed-attention, comm-ir]
source_pdf: "[[3731569.3764798.pdf]]"
source_md: "[[3731569.3764798]]"
---

# Mercury: Unlocking Multi-GPU Operator Optimization for LLMs via Remote Memory Scheduling (SOSP 2025)

> **一句话总结**：现有 multi-GPU 编译器默认「数据必须先本地化」的 synchronous schedule，浪费 HBM 且难探索 RingAttention/Ulysses 类异步模式；Mercury 用 CommIR 把 remote GPU memory 提升为可调度内存层，自动复现并超越手工策略，相对 USP/Ulysses 平均 **1.56×**，相对 3D-parallel 最高 **1.62×**。

## 问题与动机

LLM [[Attention]]/GEMM 单卡 HBM 不足（Llama-3 70B [[KV-Cache]] 约 282GB）。过去两年仅 attention/linear 就有 20+ 篇手工 multi-GPU 算子论文（RingAttention、Ulysses、USP 等），但移植到新拓扑/序列长度成本极高。[[torch.compile]]、Alpa、Centauri 等编译器仍偏 local-memory-centric，默认复制共享输入、同步执行，限制 remote memory reuse 与 compute-comm overlap。

## 关键观察 / 隐含假设

- **观察 1**：remote GPU memory 可作为与 local HBM 同级的可调度层；shifted asynchronous schedule 让各 rank 错峰访问共享 KV，降低本地内存压力（Figure 1）。
  - **依赖假设**：NVLink/RoCE 层次带宽已知且 collectives 常优于任意 P2P 模式。
  - **可能失效场景**：跨节点低带宽时 universal shift 仍可能被 inter-node 链路瓶颈（RingAttention 已知问题）。
- **观察 2**：loop-based IR 天然含并行语义；在分布式 coarse grain 扩展 TVM bind 等原语可统一 tile/reorder 与 parallelize/shift/shard/replicate。
  - **依赖假设**：LLM 算子可表达为嵌套 loop + 明确 batch/head/query/context 维。
  - **可能失效场景**：高度融合、动态 shape 或 MoE routing 可能超出 CommIR 表达。
- **假设 1**：结构化变换可自动合成 ring AllGather/ReduceScatter，无需手写 kernel 模板。
  - **证据强度**：中强；Table 1 显示覆盖已知手工策略并探索 hybrid shift。

## 核心方法

**CommIR**：扩展 loop IR，计算原语（tile/join/reorder/patch）+ 通信原语（parallelize/shift/shard/replicate）。shift 引入 `(j+i)%J` 类异步访问；shard 触发 collective  lowering 规则。

**Mercury 流水线**：Python DSL → CommIR → 变换搜索 → lowering 到 P2P/collective kernel + TorchInductor/FlashAttention patch → **auto-tuner** 按硬件 mesh 剖面 latency、静态检查内存。

连接上层图优化与下层 tensor compiler，专注 multi-GPU scheduling 层。

## 设计取舍

- **取舍 1**：专注 operator 级而非端到端 training stack → 需与 Megatron 等 3D parallel 协同边界清晰。
- **取舍 2**：autotune 搜索空间大 → 依赖 structured primitives 约束，否则 profiling 爆炸。
- **边界条件**：B100 NVLink72 等新硬件需重新 tune；极短 sequence 时 comm 开销可能反超手工 kernel。

## 实验与结果

- vs USP、Ulysses 等 SOTA 手工库：平均 **1.56×** speedup
- vs model-level 3D-parallel：最高 **1.62×**（真实 LLM workload）
- 自动复现 RingAttention/Ulysses 等已知策略，部分配置发现更优 schedule
- 开源 https://github.com/ChandlerGuan/mercury_artifact

## Critical Analysis

### 论证链条

「local-centric 假设限制设计空间」+ CommIR 统一表达 → autotune 匹配/超越手工，论证较闭合。弱点：实验是否覆盖**训练**长稳态 vs **推理** burst、以及 multi-node 极端不平衡拓扑的外推需更多 trace。

### 假设压力测试

- **硬件**：NVLink mesh vs RoCE 跨 pod；Mercury 层次 parallelize 依赖 mesh 标注准确。
- **模型**：GQA/MQA head 共享改变 shard 语义；新架构（MLA 等）需新 DSL 模式。
- **编译栈**：与 Inductor/FlashAttention 版本耦合，升级 breakage 风险论文未讨论。

### 实验可信度

Meta 作者参与、多 operator/平台评测可信；与 torch.compile 差距有引用支撑。缺少「同等工程师时间」下 Mercury autotune vs 手工 USP 的 TCO 对比。

### 系统性缺陷

autotune 在线成本、失败 schedule 回退、多租户 GPU 池干扰论文未讨论；CommIR 学习曲线与 debuggability 对普通 ML 工程师可能是 adoption 障碍。

## 局限与 Future Work

- **局限 1**：学术编译器可用性/评估门槛高（§1 自述）。
- **局限 2**：与端到端 parallel 策略（DP/TP/PP）联合最优解未完全自动化。
- **Future work 1**：在 B100/NVLink72 上测量 autotune 收敛时间与 human-tuned 差距随规模缩放规律。
- **Future work 2**：MoE expert parallel 纳入 CommIR，检验 remote memory scheduling 是否仍优于 template。

## 相关

- **相关概念**：[[Attention]]、[[KV-Cache]]、[[RingAttention]]、[[Tensor-Parallelism]]、[[NCCL]]
- **同类系统**：Alpa、Centauri、CoCoNet、USP、Ulysses
- **同会议**：[[SOSP-2025]]