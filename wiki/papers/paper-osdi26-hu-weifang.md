---
type: paper
name: Tessera
full_title: Tessera: A Holistic Pipeline Parallelism Framework for Trillion-Parameter Heterogeneous MoE Training (Operational Systems)
authors: [Weifang Hu, Langshi Chen, Man Yuan, Youyang Yao, Xiulong Yuan, et al.]
venue: OSDI
year: 2026
tags: [pipeline-parallelism, moe-training, communication-overlap, heterogeneous-models, dynamic-scheduling]
source_pdf: "[[osdi26-hu-weifang.pdf]]"
source_md: "[[osdi26-hu-weifang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-13
---

# 面向异构 MoE 训练的整体流水线并行框架（OSDI 2026）

> **原题**：Tessera: A Holistic Pipeline Parallelism Framework for Trillion-Parameter Heterogeneous MoE Training (Operational Systems)

> **一句话总结**：异构注意力与稀疏 MoE 让不同流水线分块的通信隐藏效率相差可达 3 倍，Tessera 用硬件 profiling 得到的 overlap 后成本联合决定分块与细粒度调度，再用运行时动态气泡填充吸收路由波动，在 4,096–12,288 GPU 的生产训练中将吞吐提高 20%–33%，万亿参数模型 MFU 达到 39%。

## 问题与动机

传统流水线并行通常先按串行层成本切分，再套用固定的通信-计算重叠模板。这依赖 Transformer 层结构相近。Qwen3-Next 将 Gated DeltaNet 与 softmax attention 交错使用，每层后接稀疏 MoE；长序列下相邻注意力操作的计算时间最多相差 10 倍。不同分块组合的通信和计算时间线因此不同，固定模板会留下暴露的 All-to-All（A2A）延迟。

分块边界又决定了哪些操作能够重叠，重叠效率反过来决定最优分块。单独优化两者会把串行时间看似均衡的阶段变成 pipeline straggler。即使静态计划正确，MoE token routing 的随机性仍会改变各 expert 的计算时长，制造静态计划无法预见的短暂空闲槽。

## 关键观察 / 隐含假设

- **观察 1：重叠效率取决于具体分块组合。** Qwen3-Next-80B 的 profiling 中，C-C 组合延迟下降 41.6%，D-D 仅下降 14.0%；串行均衡分区的瓶颈 overlap 后成本比 overlap-aware 分区高 1.14 倍（图 4）。
  - **依赖假设**：任务时长和资源冲突在相同硬件拓扑上具有可复用性。
  - **可能失效场景**：GPU 型号、EP/TP 拓扑、通信拥塞或 kernel 实现变化后，离线 profile 可能不再代表生产执行。
- **观察 2：路由波动造成的空闲槽可以被非关键路径任务填充。** Wgrad 和部分梯度归约不定义 stage 的 backbone 完成时间，却能在 MoE 负载不均时填入局部间隙（图 5、图 8）。
  - **依赖假设**：运行时能在目标槽出现前取得 token counts，并且 movable task 有足够 deadline slack 和内存余量。
- **观察 3：计算密度决定 A2A 隐藏上限。** Qwen3-Next-L 中 73% 的 EP 通信被隐藏；计算更短的 Qwen3-Next-M 只有 26% 被隐藏（§6.2、图 10）。
  - **证据强度**：强；同一框架下的生产工作负载对比直接显示了边界。

## 核心方法

Tessera 固定高层 pipeline 模板（如 interleaved 1F1B），构建 overlap graph。每个虚拟 stage 在串行均衡分区附近生成一组连续层候选；对候选分块在不同方向上的 overlap pair 拆成任务 DAG，任务标注依赖、资源类型和时长。

事件驱动 scheduler 采用 backbone-first 与 gap-fit 规则，优先安排决定 makespan 的任务；会延迟会拖长 makespan 的 movable task，并在剩余生命周期内回填。它比逐实例用 CBC 求 ILP 快得多，在 EP32/EP8 上距离 ILP 的实测成本分别仅 1.07%/0.76%（图 13、§6.5）。

所有候选 pair 在 reference device group 上实际 profiling，得到 overlap 后成本。MILP 选择每个 stage 的一个候选，目标是最小化所选 overlap edge 的最大成本，同时约束连续、不重叠的层范围、拓扑兼容和显存容量。profile-guided pruning 删除成本超过基线的候选 pair。

运行时 Dynamic Bubble Optimizer（DBO）复用 dispatch 前可得到的 per-expert token counts，预测预标注槽位的大小，并从有 deadline slack 的 movable task pool 中贪心选择最合适任务。若任务接近 deadline 仍未被填入，系统将其恢复到主执行流，优先保证正确性。Plan-Agnostic Execution Engine 以 C++ lock-free FSM 解释计划，避免改写 Megatron-LM 的训练循环；`advance()` 暴露任务边界，`register_task()` 注册可移动任务。

## 设计取舍

- **硬件 profiling 换取准确性**：万亿参数模型的 distinct overlap pair profiling 仍可在约一小时内完成，但新模型、拓扑或 kernel 变动都可能触发重新 profiling。
- **任务延迟换取气泡利用率**：DBO 延迟 Wgrad 会延长 activation 和 gradient 的存活时间。Qwen3-Next-M 上 DBO 使峰值显存增加 2–4 个百分点；pool 上限需按显存余量配置（§6.6）。
- **互 microbatch overlap 换取模块化**：相较沿 sequence 切分的 intra-microbatch 方法，Tessera 保持 GEMM 的计算强度和通信 backend 独立性，但只能利用已有 pipeline 并发窗口。

## 实验与结果

- 生产集群在 4,096–12,288 张 NVIDIA Hopper GPU 上训练 Qwen3/Qwen3-Next，Tessera 相对已包含 interleaved 1F1B 和通信重叠的内部 Megatron 基线提升 20%–33% MFU；万亿参数运行达到 39% MFU（表 2、§6.2）。
- 8,192-GPU Qwen3-XL 热升级中，静态 planner 带来约 13% 吞吐提升；启用 DBO 后 MFU 达到 39.0%，并降低生产吞吐波动（图 9）。
- 256-GPU 控制实验中，相对内部 Megatron 基线，Qwen3-235B、DeepSeek-V3、Nemotron-3 Super 的 MFU 分别为 1.27×、1.24×、1.13×；相对 Megatron-Core MoE，Qwen3-235B 达到 1.24×，其余两者接近（图 11）。
- Qwen3-Next-M 上，DBO 相对静态计划降低迭代时间 4.4%–5.4%；监控路径自身约增加 1%，峰值显存增加 2–4 个百分点（表 3）。
- MILP 的 profile-guided pruning 将问题规模减少约 3–5 倍，测试配置在 64-core server 上均在 5 秒内求解；profile 在 128K sequence length、trillion-scale PP8-C2 下约 3,050 秒（表 4、§6.7）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 联合优化分区与重叠优于串行成本分区 | 图 4、图 12、§6.4 | Qwen3-Next-80B/M；128/256 GPU；mock router | 强 |
| DBO 能吸收路由造成的动态气泡 | 图 9、表 3、§6.6 | Qwen3-Next-M；256 GPU；生产案例 6,144/8,192 GPU | 强 |
| Tessera 可扩展到生产规模 | 表 2、图 10、§6.2 | Alibaba Hopper 集群；4,096–12,288 GPU；Qwen 家族 | 中 |
| overlap 收益受计算通信比限制 | 图 10、§6.2 | Qwen3-Next-L 与 M；不同规模和专家计算量 | 强 |

## 批判性分析

### 论证链条

观察、设计和结果基本闭合：异构 pair 导致固定模板失效，Tessera 以 pair-level profile 和 MILP 处理静态耦合，再以 DBO 处理动态波动。其主要外推是“profile-driven co-optimization 系统性优于手工启发式”；论文只在有限模型、拓扑和内部生产栈上验证，尚不足以证明跨硬件代际的普遍性。

### 假设压力测试

候选空间只在串行均衡分区附近扰动。若真正最优边界远离该邻域，MILP 即使求得最优也只是局部搜索结果。DBO 依赖 per-expert counts 的提前可见性和可用显存；高负载或更短迭代时间下，预测窗口可能不足。网络 jitter 的历史预测只被讨论，尚未系统验证（§5）。

### 实验可信度

生产基线较强，能隔离 Tessera 的增量收益；控制实验覆盖三种结构不同的 MoE。另一方面，部分数据集和内部 baseline 不公开，且与 Megatron-Core 的比较使用 256 GPU 和公开 recipe，不能直接等同于生产部署优势。bitwise equivalence 只在 deterministic mode 的一个万亿规模工作负载上核验（§6.2）。

### 系统性缺陷

系统包含约 11,000 行 Python 和 2,000 行 C++，并引入后台线程、FSM、显存生命周期管理和硬件 profile cache。论文未量化故障恢复、profile 失效检测、可观测性和计划版本管理成本。粗粒度 task 仍可能发生 SM contention 或隐式串行化，理论成本与硬件测量平均相差约 5%，尾部 primitive-level profile 误差可达 15%（§5）。

## 局限与后续工作

- **局限 1**：Qwen3-Next-M 的计算强度不足时，只有 26% EP 通信被隐藏，仍有 38.9% iteration time 的 exposed EP（§6.2）。框架无法消除缺少可重叠计算这一物理边界。
- **局限 2**：DBO 的延迟策略会增加显存压力，激进配置可能 OOM；offloading 和 recomputation 被作为可移动任务的方向，但未给出完整评估。
- **后续工作 1**：在受控网络拥塞和跨代 GPU 上测量历史 jitter predictor 的预测误差、吞吐收益和错误注入代价。
- **后续工作 2**：扩大候选分区搜索范围，并以 profile 成本误差对最终分区选择的敏感性作为独立指标。

## 相关

- **相关概念**：[[Pipeline Parallelism]]、[[Mixture-of-Experts]]、[[Communication-Computation Overlap]]
- **同类系统**：[[Megatron-LM]]、[[Megatron-Core]]、[[Comet]]、[[DualPipe]]
- **同会议**：[[OSDI-2026]]
