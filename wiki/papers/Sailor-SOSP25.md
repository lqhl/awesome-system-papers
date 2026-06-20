---
type: paper
name: Sailor
full_title: "Sailor: Automating Distributed Training over Dynamic, Heterogeneous, and Geo-distributed Clusters"
authors: [Foteini Strati, Zhendong Zhang, George Manos, Ixeia Sánchez Périz, Qinghao Hu, et al.]
venue: SOSP
year: 2025
tags: [distributed-training, heterogeneous-gpu, geo-distributed, planner, autotuning]
source_pdf: "[[3731569.3764839.pdf]]"
source_md: "[[3731569.3764839]]"
---

# Sailor: Automating Distributed Training over Dynamic, Heterogeneous, and Geo-distributed Clusters (SOSP 2025)

> **一句话总结**：联合优化资源分配与 [[Data-Parallelism]]/[[Pipeline-Parallelism]]/[[Tensor-Parallelism]] 计划，配合准确 memory/iteration time simulator，在异构/跨 zone 场景下比 Metis/FlashFlex 等 planner 吞吐高 **1.1–2.87×**，128 A100 搜索 **<1s**，并支持弹性重配置。

## 问题与动机

同质高端 GPU 集群稀缺（GCP 上 8 张 A100 可能等 7 小时才凑齐）。利用异构 GPU（A100+V100）或跨 availability zone 可提升吞吐（论文示例 c3/c4 分别 **1.15×/1.87×**），但配置空间爆炸：资源拓扑 × 并行度 × microbatch × 跨区数据传输费。

现有 planner（Aceso、Galvatron、Metis、FlashFlex、Atlas、DTFM）要么固定资源分配只搜并行度，要么搜索需数小时（Metis 16 GPU 需数小时），要么 simulator 低估 memory（Varuna OOM）或 runtime（FlashFlex 不准），且训练框架（Megatron/DeepSpeed）不支持 per-stage 异构并行度。

## 关键观察 / 隐含假设

- **观察 1**：异构环境下 iteration time 由 straggler 和 per-GPU OOM 约束共同决定，memory footprint 估算误差可达 25–95%（OPT-350M on Grace-Hopper）。
  - **依赖假设**：单层 profiling + 解析模型可外推到多节点异构拓扑。
  - **可能失效场景**：[[MoE]] 等层负载动态变化（论文明确 leave for future work）；新 GPU 类型未 profile。
  - **证据强度**：强——Fig. 3 直接对比多 baseline memory 估算 vs 实测。
- **观察 2**：云资源可用性在小时级波动，planner 必须在秒级重算配置。
  - **依赖假设**：资源变化频率低于 planner 重算频率；spot/preempt 可映射为配额变化。
  - **可能失效场景**：秒级大规模 preemption 风暴；跨 region 带宽计费模型突变。
  - **证据强度**：中——8 小时 GCP trace 展示波动，但单一云单一模型。
- **假设 1**：TP 限制在单节点内、DP 通信限制在单 region（启发式 H1/H5）不损失最优解太多。
  - **证据强度**：中——与 Megatron 实践一致，但极端 geo 场景可能次优。

## 核心方法

Sailor 三组件：**Profiler**（单节点 per GPU type 层 profile + 跨节点带宽多项式拟合）、**Planner**（DP 剪枝 + per-stage DP 动态规划选 replica 放置）、**Training framework**（Megatron-DeepSpeed 扩展，支持 per-stage 异构 TP/PP/DP、弹性重配置）。

Planner 启发式：OOM 早剪、吞吐最大化时 DP 递减搜索、成本最小化时 DP 递增搜索、同 region 多 zone 合并为单 zone。

## 设计取舍

- **取舍 1**：联合搜索资源+并行度，复杂度靠剪枝和 DP 控制，可能错过全局最优。
- **取舍 2**：不改 global batch size，保证训练动力学一致，但限制某些成本优化空间。
- **边界条件**：dense transformer 类模型效果好；MoE、RLHF 等多变 workload 需额外工作。

## 实验与结果

- vs Metis/FlashFlex/AMP：异构吞吐 **1.1–2.87×**，搜索 10s 级 vs 分钟/小时
- vs DTFM：geo 场景吞吐 **5.9×**、成本 **9.8×**
- 成本约束下比次优 baseline 省 **40%**
- 128 A100 + OPT-350M：搜索 **<1s**（Table 1）

## Critical Analysis

### 论证链条

「simulator 不准 → 错误 plan」和「搜索慢 → 无法适应动态资源」两条动机清晰，Sailor 的三组件分别回应。Table 1 系统对比全面，但部分 baseline 实现/调参是否公平需读者自行判断。

### 假设压力测试

- MoE expert 负载不均时 memory model 可能失效（作者承认）。
- 跨 region 计费、latency 波动大时 H6「多 zone 合并」可能过于激进。
- 仅 OPT-350M 等中小模型详测，千亿参数 planner 延迟外推未验证。

### 实验可信度

首次横向对比 major open-source planners，价值高。GCP 真实 availability trace 增强说服力。缺少 production 长周期训练 job 的端到端 case study。

### 系统性缺陷

论文未讨论 planner 错误导致 OOM 的 runtime 保护；框架弹性重配置时的 checkpoint/resume 开销；与 cloud API 集成的工程复杂度。

## 局限与 Future Work

- **局限 1**：MoE profiling 未支持。
- **局限 2**：依赖 upfront profiling，新模型首次提交有分钟级开销。
- **Future work 1**：在线 profiling 修正 simulator，应对 drift 和 straggler 非静态假设。

## 相关

- **相关概念**：[[Data-Parallelism]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[MoE]]
- **同类系统**：Metis、FlashFlex、Galvatron、DeepSpeed、Megatron-LM
- **同会议**：[[SOSP-2025]]