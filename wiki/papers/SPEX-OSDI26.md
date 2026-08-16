---
type: paper
name: SPEX
full_title: "Breaking the Reward Barrier: Accelerating Tree-of-Thought Reasoning via Speculative Exploration"
authors: [Shuzhang Zhong, Haochen Huang, Shengxuan Qiu, Pengfei Zuo, Runsheng Wang, Meng Li]
venue: OSDI
year: 2026
tags: [llm-inference, tree-of-thought, speculative-execution, reasoning, scheduling]
source_pdf: "[[osdi26-zhong.pdf]]"
source_md: "[[osdi26-zhong]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# SPEX：用推测探索加速思维树推理（OSDI 2026）

> **原题**：Breaking the Reward Barrier: Accelerating Tree-of-Thought Reasoning via Speculative Exploration

> **一句话总结**：[[Tree-of-Thought|思维树]]（Tree-of-Thought，ToT）每扩展一步都要等 reward 才能决定下一条分支，SPEX 利用短期 reward 排名较稳定这一特点，在等待时提前生成可能用到的分支，并跨 query 分配空闲 GPU 并行度；在同一 SGLang-based ToT 实现上，它把 DFS query throughput 提高 1.8–3 倍、BFS 提高 1.2–1.9 倍，但约 1.2 倍的稳定收益来自会改变实际搜索空间的 early termination，不能把全部加速理解为“完全相同算法语义下的系统优化”。

## 问题与动机

ToT 不把一次回答当成一条连续 token stream，而是让模型生成许多 reasoning nodes，再由 reward model 或 confidence score 决定保留、回退或扩展哪些节点。这个控制循环给搜索质量带来好处，却形成 reward dependency barrier：下一批 LLM generation 必须等上一批 node 的 reward 和 tree update 完成（§2–§3.1、图 3）。

不同搜索算法以不同方式被这道屏障限制：

- Depth-First Search（DFS）类的 RSTAR-MCTS、REST-MCTS 一次主要沿一条路径前进，收到 reward 后才能计算新的 UCB、决定下一次 rollout。论文测到一个 reasoning node 通常有 50–100 tokens，一次搜索又会串行经过许多 nodes，GPU 长期处于小 batch、memory-bound 状态（图 4–5）。
- Breadth-First Search（BFS）类的 REBASE、ETS 可以同时扩展同一深度的多个 branches，但短分支完成后仍要等最长分支，才能聚合 reward 并分配下一层宽度。Branch length 的长尾让有效 batch 不断缩小，原本 compute-bound 的执行又退回 memory-bound（§3.1–§3.2）。

小 batch 不只降低算力利用率，还会反复读取模型权重；分支没有一起送入 server 时，SGLang 的 [[RadixAttention|RadixAttention]] 也较难复用共同 prefix 的 KV cache。SPEX 的目标因此不是预测最终答案，而是把“将来大概率会做的搜索工作”提前到 reward 等待期，增加可批处理的 requests，并尽量让错误推测仍可回收（§3.2–§3.4）。

## 关键观察 / 隐含假设

- **观察 1：MCTS 的 node value 在短期内变化较慢。** 每个 rollout 只更新一条 ancestor path；多次 reward 的均值不会突然大变，UCB 的短期变化主要来自 visit count。因此可以用当前 value、visit count 和已经完成的 speculative reward，模拟接下来几次选择（§4.1–§4.2、图 6(a)）。
  - **依赖假设**：reward calibration 和 search state 要在短预测窗口内稳定。图 14 显示 DFS hit rate 会随 prediction distance 明显下降，所以这不是可任意向前看的 oracle。
- **观察 2：BFS 的 straggler 等待期里已经有可用工作。** 先完成的短 branches 已有 reward，可以按原 BFS 的 reward-softmax policy 提前扩展；若真正的下一层 frontier 没选中它，再取消该 speculative branch（§4.2、图 9(b)）。
  - **依赖假设**：短分支足够多、取消能及时生效，而且 speculative KV 不会先把 cache 挤满。搜索越深，candidate scores 越接近，图 14(b) 的命中率也越低。
- **观察 3：一次 speculation 能同时摊薄 weight read 并复用 KV。** 同一 batch 中的 primary/speculative branches 共用模型参数，具有共同 prefix 的 branches 还能复用 fork point 之前的 KV state。因此收益不只取决于“猜中率”，也取决于 query 可提供多少 branches 和 prefix 有多长（§4.3）。
  - **依赖假设**：serving cache 能保留 live-node prefixes，且有足够并发 query 填满全局 budget。原本已经 compute-bound 的大 batch 几乎没有同样的空间。
- **观察 4：深度偏斜的搜索树里，大多数答案和正确答案出现在较浅层。** 论文据此在 top-1 answer 已明显领先 top-2 时，直接结束整个 ToT search，而不只是停止 speculative work（§4.4、图 7）。
  - **重要边界**：这会减少原算法本应继续探索的 nodes，改变 majority-vote 样本和最终搜索空间。它是算法/系统共同优化，不是无语义变化的 speculation。
- **观察 5：DFS 的 miss 不一定立即浪费。** 如果一次预测没有成为当前 rollout，节点仍留在 tree 中，可能被后续 rollout 使用；BFS 的下一层 frontier 一旦确定，则可以严格判断 miss 并取消（§4.2）。
  - **依赖假设**：DFS 后续确实还会访问该 node。论文没有报告最终没被消费的 generated tokens、KV occupancy 或 energy，因此“暂时可复用”不等于“没有浪费”。

## 核心方法

### 查询内推测选择（Intra-query speculative selection）

对 DFS，SPEX 在 temporary tree state 上执行接下来 `k` 次 UCB selection simulation。每模拟选一次，就增加对应 visit count 并重算 UCB；已经在生成的 node 会被跳过，已经推测完成的 node 则把真实 speculative reward 纳入临时更新。Simulation 本身不调用 [[LLM|LLM]] 或 reward model，它只用当前 statistics 预测哪些 nodes 最可能在未来 rollout 中被选中，再让空闲 producer 提前生成这些 nodes（§4.2、算法 1、图 9(a)）。

对 BFS，SPEX 不预测很远的 tree state，而是在同一 depth 的短 branch 提前结束后，用空出来的 slots 扩展这些 completed nodes。Speculative width 直接沿用底层算法的 policy；例如 REBASE 对 reward scores 做 softmax，得分高的 node 获得更多 children。真正 frontier 形成后，系统保留命中的 children，并立即停止未选中的 branches（§4.2、图 9(b)）。

这两个路径解决的是同一问题，但正确性边界不同：DFS miss 可以留待以后使用，没有逐轮 strict verification；BFS miss 能对照 actual frontier 检查并取消。SPEX 不保证推测顺序与 baseline 的逐步执行完全相同，只保证 primary search 不必等待 speculative task 才前进（§4.2、§4.5）。

### 查询间推测预算（Inter-query speculative budget）

系统先用 reasoning model 的 roofline profile 找到从 memory-bound 走向 compute-bound 时对应的并发量，把它作为全局 speculative budget `k_total`。对每个 query `q`，score 同时考虑三类信息：当前可发出的非重复 speculative branches 数 `C_q`、预测命中率 `P_q`，以及一次 speculation 可共享的 model weights `S_w` 和 prefix KV `S_KV(q)`。最后用 temperature `τ` 控制的 softmax 把 `k_total` 分给多个 queries，并受每个 query 的 `C_q` 上限约束（§4.3、公式 1–2）。

这个策略追求全局 query throughput，而不是每个 query 平均分配。高命中率、长 prefix、branches 多的 query 会拿到更多 slots；低 score query 是否会被延迟、tail latency 是否恶化，论文没有评测。

### 自适应提前终止（Adaptive early termination）

偏斜 tree 的深 branch 很难提前生成，也会持续占用并行预算。SPEX 统计已经生成的 answer 数 `n`，并把属于 top-1、top-2 hypotheses 的 reward 分别累加为 confidence。当 `n` 至少达到 threshold `t`，且 top-1 相对 top-2 的 margin 足够大时，就返回当前 majority answer。实验固定 scaling factor `α=0.5`（§4.4、公式 3–4）。

这里终止的是 actual ToT search。它可以避免质量较低的 deep tail 干扰 majority vote，也可能错过晚出现的正确答案。Table 2 中的 accuracy 变化正是这种 search-space change 的结果，而不是异步执行的纯 timing noise。

### 生产者—消费者执行框架（Producer–consumer execution）

实现以 [[SGLang|SGLang]] 为 generation backend：作者修改 front-end，使原本成批返回的 requests 能各自异步返回；application side 用 Python coroutines 实现多个 producers 和一个 centralized consumer。Producer 可以扩展 primary node，也可以扩展 scheduler 选择的 speculative node；consumer 把完成结果放入 primary tree 或 speculative subtree，再用空闲 producer 补发工作，并优先选择能复用 prefix 的节点（§4.5–§5、算法 2）。

这套框架把 REST-MCTS、RSTAR-MCTS、REBASE 和 ETS 的 search policy 留在 application side，只要求它们暴露 tree state、node expansion 和 reward。论文没有报告代码改动量、scheduler CPU cost、failure recovery 或取消后 server 侧是否仍会完成一部分 token。

## 设计取舍

- **提前生成换 reward-barrier parallelism**：GPU 可以把多个 branches 一起 decode；miss 会消耗 token compute 和 KV cache，并可能提高每 token latency。
- **短期 reward stability 换无需额外 predictor**：直接模拟原 UCB/policy，设计简单；距离越远、reward 越噪，命中率越低。
- **全局 utility allocation 换平均公平性**：优先做 weight/KV reuse 高的 work，提高总 finished questions/min；没有 per-query SLO 或 starvation bound。
- **early termination 换稳定的约 1.2 倍加速**：少算 deep branches，可能同时提高或降低 pass@1；不能再声称与完整 baseline search 等价。
- **application-side control 换算法适配性**：ToT policy 容易用 Python coroutine 接入；高频 scheduling、cancellation 与 state consistency 跨越 Python front-end 和 GPU server。
- **静态 roofline budget 换低决策成本**：profile 给出清楚的并发上限；model、prompt length、KV pressure 或其他 tenants 变化后，旧 budget 可能不再合适。

## 实验与结果

- **设置、baseline 与复现边界**：论文测试 Llemma-7B、Llemma-34B、DeepSeek-R1-Distill-Qwen-8B、Qwen3-30B-A3B。Llemma 使用专用 reward model，跑 GSM8K/MATH-500；DeepSeek/Qwen 用 intrinsic log probability 当 reward，跑 AIME 2024/2025、BRUMO、HMMT-Feb25。四种 search 分别是 REST-MCTS（DFS+BFS）、RSTAR-MCTS（DFS）、REBASE（BFS）和 ETS（BFS），每种用两档 target-answer configuration：前两者为 5/10，后两者为 8/16。Baseline 是同一 ToT algorithm 在 SGLang 上不启用 SPEX，不是另一套 ToT serving system。7B/8B 跑 NVIDIA A6000，34B/30B 跑 NVIDIA A100；论文没有给 GPU 数量、A100 具体型号、CPU、memory、parallel strategy 或完整 roofline profile（§6.1、表 1）。
- **端到端 query throughput**：主指标是 finished questions per minute。图 10 中 DFS 平均加速 1.8–3 倍，BFS 平均 1.2–1.9 倍；小 query batch 下 DFS 最高 3 倍，BFS-only 最高约 1.7 倍。这里的 batch size 是同时处理的 ToT questions，不是 branch requests；例如一个 REBASE-16 query 本身已有 16 个 requests，`BS=8` 在 speculation 前最多就可暴露 128 个。随着 batch 变大并进入 compute-bound，额外推测的相对收益下降（§6.2）。
- **accuracy 不保证逐项不降**：Table 2 用相同 temperature、top-p 和 token limit 比较 pass@1。多数配置下 SPEX 与原 ToT 接近或略高，说明浅层 majority 常已足够；但并非每项都保持，例如 Qwen3-30B-A3B 在 AIME 2025 的 REST-5 从 70.0% 降到 63.3%，Llemma-34B 在 MATH-500 的 REST-5 从 41.2% 降到 38.2%。AIME 题量小，论文没有多随机种子、方差或置信区间，因此这些升降都不宜解释成稳定质量变化（§6.3、表 2）。
- **组件拆解与命中率**：图 11 显示 T1 intra-query selection 在小 batch 贡献最大，T2 inter-query allocation 随 batch 增大变重要，T3 early termination 在不同配置中稳定提供约 1.2 倍，三者合用最好。图 14 中 DFS 的 hit rate 随预测 rollout 距离变远持续下降，BFS 也随 tree depth 加深而下降；图 15 显示 REBASE speculative work 落到 critical path 的概率随配置/深度变化，典型约 40%–60%，critical path 到来前平均已提前生成约 20 tokens。这些图支持短期/浅层优先，但也说明 miss 并不罕见（§6.4、§6.7）。
- **与 token-level speculation 组合及额外成本**：在 DeepSeek-R1-8B/A6000 上，作者把 SPEX 与 Multi-Token Prediction（MTP）组合。RSTAR-10、`BS=1` 时，MTP 单独约 2.0 倍、SPEX 单独约 3.1 倍、合用约 4.1 倍；MTP token tree 是人工按 workload 调优的，RSTAR 固定 16，REBASE 随 `BS=1/4/8` 使用 16/8/4。SPEX 可能使 reasoning-model TPOT 上升，但图 13 所测 overhead 不超过 15%；reward evaluation 的平均额外 delay 少于 0.1 秒。论文未报告 end-to-end latency、P99、wasted tokens、energy 或峰值 KV memory（§6.5–§6.6、图 12–13）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Reward barrier 是所测 ToT 的重要系统瓶颈 | DFS node 常有 50–100 tokens 且串行；BFS 同层 length variation 产生 straggler，roofline 显示有效 batch 缩小后转向 memory-bound（图 4–5） | Llemma-7B/MATH-500 与 DeepSeek-8B/AIME 的 profile，未给 production trace | 中到强 |
| Speculative exploration 能提高 ToT query throughput | 四种算法、四个模型中，DFS 平均 1.8–3 倍，BFS 平均 1.2–1.9 倍（图 10） | 同一 SGLang baseline；硬件数量、服务负载与 tail latency 未公开 | 强（所测设置） |
| SPEX 可与 token-level speculation 叠加 | RSTAR-10、`BS=1` 中 MTP 约 2.0 倍、SPEX 约 3.1 倍、组合约 4.1 倍（图 12） | 单个 DeepSeek-8B/A6000 setup，MTP tree 人工调参 | 中 |
| Early termination 总体没有破坏 ToT 的 accuracy lift | Table 2 多数配置与 baseline 接近或更高 | 个别项下降 3.0–6.7 个百分点；search space 已改变，AIME 小样本且无方差 | 中 |
| 三个组件解决不同负载区间 | T1 主导小 batch，T2 在大 batch 更重要，T3 约 1.2 倍且组合最好（图 11） | 只展示 RSTAR-10、REBASE-16 的 ablation，T3 同时减少算法工作量 | 中到强 |

## 批判性分析

### 论证链条

论文从 DFS 的串行 reward wait 和 BFS 的 straggler barrier 出发，用 roofline 解释它们为什么导致反复读 weights/KV；接着利用 MCTS value 的短期稳定性和 BFS 已完成短分支，构造可提前执行的 work；最后通过跨 query budget 把 speculation 控制在硬件并发上限内。这条从 workload observation 到 scheduler 的链条很直接，四类算法上的结果也支持“已有潜在并行度没有被 serving system 利用”。

但第三项 early termination 是另一条论证：因为 shallow answers 在 trace 中更多且正确率更高，所以干脆不执行 baseline 的 deep search。Ablation 显示它本身贡献约 1.2 倍，意味着总 speedup 有一部分来自减少工作，而不是更好地调度同一批工作。论文在 accuracy table 中公开了变化，但引言贡献总结里的“without compromising accuracy”容易掩盖个别 3.0–6.7 个百分点下降，也把系统优化和搜索策略变化混在了一起。

### 假设压力测试

如果 reward 很噪、node values 在相邻 rollouts 快速反转，DFS simulation 会在错误 subtree 上连续生成；如果 BFS 深层 candidates 分数接近，softmax 也难预测 actual frontier。图 14 已显示这两个趋势。更强的 process reward model 可能提高 hit rate，reward model/domain shift 也可能让静态 `P_q` 失真。

如果正确答案经常晚出现，或 top-1 的浅层高 reward 是错误的但过度自信，early termination 会系统性剪掉纠错机会。Intrinsic log probability 只是 confidence proxy，不等于 answer correctness。对 proof、code search、agent planning 等深度与正确性关系不同的 workload，图 7 的 shallow-depth bias 需要重新验证。

当 query batch 已经把 GPU 推到 compute-bound，speculation 只会争用 compute 和 KV；当 serving traffic 很稀疏，又没有多个 queries 可供 budget allocator 选择。SPEX 在这两端都可能退化到低收益，论文没有定义自动关闭条件或 worst-case compute amplification bound。

### 实验可信度

评测覆盖两种 tree traversal、四个算法、四个 7B–34B/[[MoE|MoE]] models、两类 reward signal 和六个 math benchmarks，比只测单一 MCTS 更有说服力。Baseline 保持同一 algorithm、model、sampling 和 token limit，有利于隔离 scheduler；组件 ablation、prediction hit、MTP composition 和 TPOT overhead 也补上了机制证据。

可复现性仍有明显缺口：没有 GPU 数量、A100 variant、host 配置、tensor/model parallelism、KV capacity、reward model placement 和 query arrival process。主指标是 throughput，不是单 query latency；没有 P50/P99，也没有公开 speculative token ratio 和 cache eviction。Accuracy 只有一次 pass@1 表，无随机种子和 confidence interval；AIME 2024/2025 的小题量尤其容易产生数个百分点波动。Baseline 只是不启用 SPEX 的同一 SGLang ToT，没有与其他并行/continuous-batching ToT runtime 对比。

### 系统性缺陷

SPEX 把 search policy、global scheduling 和 cancellation 横跨 Python application 与修改后的 SGLang front-end。异步 result 乱序、client disconnect、reward timeout、producer crash 或 speculative branch 已在 GPU batch 中但逻辑上被取消时，tree/KV state 怎样清理，论文没有讨论。DFS miss 不立即取消可以提高未来 reuse，也会让低价值 KV 长期占空间。

Global utility 最大化还可能伤害公平性：长 prefix、高 hit-rate query 持续拿到 slots，低 score query 的 completion time 没有上界。Static roofline `k_total` 没有随 prompt length、KV occupancy、模型切换或 co-tenant 动态校准。对线上服务而言，还需同时约束 throughput、P99、GPU memory、energy 和每题最大 test-time compute；当前结果只证明第一个目标。

## 局限与后续工作

- 分开报告“相同 search budget、关闭 T3”的纯 scheduling speedup，以及 early termination 少生成了多少 nodes/tokens，避免把两类收益合并。
- 报告 speculative hit、最终消费率、取消延迟、wasted tokens、KV peak/eviction、energy 和 cost per solved problem，并给出 compute-amplification 上限。
- 在多随机种子和更大题集上给 pass@1 置信区间，重点测试 shallow confidence 错误、late-correct-answer 和 reward miscalibration。
- 增加 query latency/P99 与公平性实验，给低 utility query 最小份额或 deadline-aware budget，并测试 burst arrival 和多 tenant。
- 公开 GPU 数量、parallel configuration、roofline profiling 和 reward-model placement；比较其他 ToT batching/runtime，而不只比较同一 SGLang 开关。
- 测试 code、proof、agent planning 等非数学 tree search，以及 server failure、timeout、cancellation 和 KV cleanup 的正确性。

## 相关

- **相关概念**：[[Tree-of-Thought]]、[[Speculative-Execution]]、[[Test-Time-Compute]]、[[KV-Cache]]
- **同会议**：[[OSDI-2026]]
