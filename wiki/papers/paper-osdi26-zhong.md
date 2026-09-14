---
type: paper
name: SPEX
full_title: "Breaking the Reward Barrier: Accelerating Tree-of-Thought Reasoning via Speculative Exploration"
authors: [Shuzhang Zhong, Haochen Huang, Shengxuan Qiu, Pengfei Zuo, Runsheng Wang, Meng Li]
venue: OSDI
year: 2026
tags: [llm-inference, tree-of-thought, speculative-exploration, reasoning, scheduling]
source_pdf: "[[osdi26-zhong.pdf]]"
source_md: "[[osdi26-zhong]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-14
---

# 用推测探索加速 Tree-of-Thought 推理（OSDI 2026）

> **原题**：Breaking the Reward Barrier: Accelerating Tree-of-Thought Reasoning via Speculative Exploration

> **一句话总结**：ToT 的 DFS 受奖励反馈串行依赖、BFS 受层间同步和 straggler 拖慢，SPEX 在奖励返回前预测并扩展可能被访问的分支，再用跨查询预算分配和自适应提前终止控制浪费；在四类 ToT 算法和四个模型上取得 DFS 最高 3×、BFS 最高 1.7× 加速，与 MTP 组合最高 4.1×，但收益依赖短期奖励稳定性和 memory-bound 工作负载。

## 问题与动机

Tree-of-Thought（ToT）把 LLM 推理组织成搜索树，每个节点是一段 thought，奖励模型或模型自身的置信信号决定下一步扩展、回溯和投票。它比单路径的 Chain-of-Thought 能探索更多解，但也把推理变成大量不规则的短序列生成与奖励评估。

论文将主要瓶颈定义为 reward dependency barrier。DFS 每次 rollout 必须等结果和树统计更新后才能决定下一次 traversal；BFS 虽能并行扩展同一层，却要等待所有分支的奖励，且短分支完成后会被最长分支阻塞（§3.1，图 3–5）。批次逐渐缩小后，权重和 KV cache 被反复读取，算术强度下降，推理转入 memory-bound 区域。

SPEX 的目标是把本来用于等待奖励的空闲时间转化为有效生成：系统先扩展高概率的未来分支，等控制逻辑确认后再复用其结果。论文关注查询吞吐，而不是保证每个输出 token 的延迟都下降。

## 关键观察 / 隐含假设

- **观察 1：DFS 的短期树值相对稳定。** MCTS 节点的 value 在后续 rollout 中变化缓慢，图 6(a)用跨迭代曲线展示了这一点。SPEX 因此可以在临时树状态上模拟未来 k 次 UCB 选择。
  - **依赖假设**：短预测窗口内，新增 rollout 不会大幅改变节点排序。
  - **可能失效场景**：奖励噪声大、早期访问次数很少、搜索树存在强烈的 delayed reward，或 k 取值过大时，命中率会下降；图 14(a)也显示 DFS 预测距离越远命中率越低。
- **观察 2：BFS 的同层节点生成长度有长尾。** 图 4(d)显示同一深度的 node length 方差较大，快分支只能等待 straggler；这些空档可用于扩展已完成节点。
  - **依赖假设**：提前扩展的节点仍可能位于真实 frontier，且错误分支能低成本停止。
  - **可能失效场景**：分支长度较均匀、奖励控制非常快，或 frontier 迅速变化时，speculation 可提供的空闲槽减少。
- **假设 1：ToT 服务处于低并发、偏 memory-bound 的区间。** SPEX 依赖增加并行分支来摊薄模型权重访问并复用共享前缀 KV cache。批次足够大而已进入 compute-bound 后，收益下降（§6.2）。证据强度：强，图 5(b)和不同 batch size 的结果直接支持这一边界。
- **假设 2：浅层答案更常见且更可靠。** 在偏斜深树中，图 7(b)显示多数答案来自浅层，且正确率更高。SPEX 用 top-1/top-2 答案奖励差距触发提前终止。证据强度：中，论文只在给定任务、模型和 majority vote 设定下测量这一规律。

## 核心方法

SPEX 建立在 [[SGLang]] 之上，把分支扩展和搜索控制拆成 producer–consumer。多个 producer 并行生成主分支或 speculative 分支；consumer 从完成队列接收结果，确认主分支后更新搜索树，并在有空闲 producer 时继续派发高效用的 speculative 节点（§4.5，图 8）。SGLang 前端被改为支持异步、独立返回的请求。

对 DFS，SPEX 在当前树上复制底层算法的 UCB 选择过程，连续模拟 k 次选择，并在每次模拟后更新访问次数和 UCB。已在 speculation 中或已完成的节点会被跳过，后者的奖励会并入树统计（算法 1，图 9(a)）。DFS 不做显式错误回收，因为未被本轮选中的预测节点仍可在未来 rollout 中使用。

对 BFS，系统把已完成的短节点产生的空闲容量作为 speculative budget，并沿用原 BFS 算法的扩展策略。例如 REBASE 仍按奖励 softmax 给高分节点分配更多子节点（图 9(b)）。consumer 将预测节点与真实 frontier 对照；未被选中的分支立即终止，避免继续消耗生成资源。

跨查询调度先用 roofline 分析确定全局 speculative budget，再为每个查询估计效用。效用同时考虑可发出的并行分支数、预测命中率、参数复用和可复用的 KV cache 大小。系统用带温度参数 τ 的 softmax 分配容量，避免把预算集中到已经没有可并行空间的查询（§4.3）。

面对偏斜树，提前终止监控已生成答案数和 top-1、top-2 假设的累计奖励；当答案数达到阈值 t 且置信差距超过由 α 和第二名平均权重确定的条件时，终止真实搜索（§4.4）。这一步会改变搜索空间，因此它不是纯调度优化，理论上可能影响准确率。

## 设计取舍

- **投机计算换取批次密度**：错误分支消耗额外生成和 KV cache 空间；收益来自更高的权重摊销和前缀复用。论文报告 reasoning model 的 TPOT 开销控制在 15% 内，但没有给出所有配置下的显存峰值和容量压力。
- **预测精度与预测距离冲突**：DFS 预测越远越容易失准；BFS 深层节点分数更接近，命中率也更难维持（图 14）。SPEX 采用短窗口、浅层优先等启发式，牺牲了对远期树结构的覆盖。
- **提前终止牺牲穷举性**：它适合答案分布偏向浅层且 majority vote 可靠的任务；若正确答案只在深分支出现，置信度条件可能提前剪掉必要搜索。
- **系统通用性依赖底层算法接口**：producer–consumer 外壳可以包住多种 ToT 算法，但每种算法仍需提供可模拟的选择规则、奖励更新和 frontier 验证逻辑。

## 实验与结果

- SPEX 评估了 REST-MCTS、RSTAR-MCTS、REBASE 和 ETS，覆盖 Llemma-7B/34B、DeepSeek-R1-Distill-Qwen-8B、Qwen3-30B-A3B；硬件为 A6000 或 A100，数据集包括 GSM8K、MATH-500、AIME 2024/2025、BRUMO 和 HMMT-Feb25（§6.1）。
- 端到端查询吞吐方面，DFS 平均加速 1.8–3×，BFS 平均加速 1.2–1.9×；小 batch 收益最大，DFS 最高 3×，BFS 最高约 1.7×（图 10，§6.2）。batch size 越大，系统越接近 compute-bound，收益下降。
- 在 pass@1 上，SPEX 保留 ToT 相比纯 CoT 的准确率提升；多数配置与 ToT baseline 接近或略高（表 2）。提升可能来自提前剪去低质量深分支，而不只是调度。
- 消融显示，T1（单查询分支选择）对小 batch 最重要，T2（跨查询预算分配）在 batch 增大时更重要，T3（提前终止）在各配置约带来 1.2× 稳定加速（图 11）。
- SPEX 与 token-level 的 MTP speculative decoding 互补。DeepSeek-R1-8B、RSTAR-10、BS=1 时，MTP 约 2.0×、SPEX 约 3.1×，组合达到约 4.1×（图 12，§6.5）。
- 额外并行分支使 reasoning model TPOT 最多增加约 15%，奖励模型平均延迟增加少于 0.1 秒（图 13，§6.6）。REBASE speculative 分支到达 critical path 的概率约为 40%–60%，每个深度平均提前生成约 20 tokens（图 15）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| reward dependency barrier 是 ToT 吞吐的主要系统瓶颈 | §3.1、§3.2，图 3–5 | Llemma-7B/DeepSeek-R1-8B，MATH-500/AIME，A6000 等 | 中 |
| speculative branch selection 能提高 ToT 查询吞吐 | §6.2，图 10；§6.4，图 11 | 四类算法、四个模型、A6000/A100，最高 DFS 3×、BFS 1.7× | 强 |
| 提前终止没有破坏总体准确率 | §6.3，表 2 | 给定数学数据集、pass@1、majority vote 配置 | 中 |
| SPEX 与 token-level speculation 可叠加 | §6.5，图 12 | DeepSeek-R1-8B、MTP、RSTAR-10/REBASE-8 | 强 |

## 批判性分析

### 论证链条

论文的链条在系统层面基本闭合：奖励等待造成低并行度，低并行度造成 batch attrition 和较差 KV/权重摊销，分支投机填充空闲槽后吞吐上升。DFS 和 BFS 分开处理，避免把两种依赖模式混为一谈。局部结果外推仍有一步跳跃：roofline 解释了内存访问压力，却没有给出端到端时间中权重读取、KV 读取、奖励计算和 Python 调度各自的比例；因此“reward barrier 是 principal bottleneck”更像由相关性和对照实验支持的工程判断，而非完整的因果分解。

### 假设压力测试

预测依赖奖励稳定性。若奖励模型对早期 thought 的判断经常翻转，DFS 的模拟选择会产生更多无效生成；BFS 的严格验证虽能停止错分支，但已支付的 token 和 KV cache 成本不会回收。调度效用还假定前缀驻留在 cache 中，cache 淘汰、跨租户竞争或更长上下文可能改变复用收益。论文主要使用数学题，未验证代码执行、工具调用、检索或具有高分支不确定性的 ToT 工作负载。

### 实验可信度

实验覆盖算法、模型、硬件和难度不同的数据集，且报告了吞吐、速度、准确率、TPOT、奖励延迟和预测命中率。基线配置沿用各 ToT 算法设定，这有助于可比性。限制在于：没有 production trace，没有不同 GPU 拓扑和显存容量的系统性扫描，也没有与更强的异步 batching、专用 reward batching 或其他 speculative tree search 实现做全面对照。表 2 的图像解析未保留完整数值矩阵，结论主要依赖论文给出的汇总描述。

### 系统性缺陷

实现将核心组件放在 Python coroutine 中，论文未报告在高并发下的调度 CPU 开销、队列拥塞、故障恢复和取消请求成本。BFS 错误分支的“立即终止”需要 serving 层支持细粒度取消；已生成的 KV cache 如何回收、是否造成碎片，文中没有展开。跨租户隔离、SLO 保护和 speculative budget 的在线自适应也未讨论。提前终止改变了搜索策略，虽在所测任务上保持准确率，但尚不能视作一般性的无损优化。

## 局限与后续工作

- **局限 1**：核心 workload 是数学推理，奖励稳定性、浅层答案偏置和 majority vote 假设未在代码、检索或工具型 agent 上验证。
- **局限 2**：预测错误的浪费只以吞吐和 TPOT 间接体现，缺少显存峰值、KV cache 回收、能耗和美元成本测量。
- **后续工作 1**：在包含工具调用和不均匀奖励噪声的真实 trace 上，按预测命中率、无效 token 比例、P99 延迟和准确率画出 speculative budget 的 Pareto 曲线。
- **后续工作 2**：将取消、回收和多租户 SLO 纳入调度器，测量不同 KV cache 容量与淘汰策略下的收益。

## 相关

- **相关概念**：[[Tree-of-Thought]]、[[Speculative Decoding]]、[[KV-Cache]]、[[MCTS]]
- **同类系统**：[[SGLang]]
- **同会议**：[[OSDI-2026]]
