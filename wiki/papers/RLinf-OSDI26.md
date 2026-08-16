---
type: paper
name: RLinf
full_title: "RLinf: Flexible and Efficient Large-Scale Reinforcement Learning via Macro-to-Micro Flow Transformation"
authors: [Chao Yu, Yuanqing Wang, Zhen Guo, Hao Lin, Si Xu, Hongzhi Zang, Quanlu Zhang, Yongji Wu, Chunyang Zhu, Junhao Hu, Zixiao Huang, Mingjie Wei, Yuqing Xie, Ke Yang, Bo Dai, Zhexuan Xu, Jiakun Du, Xiangyuan Wang, Xu Fu, Letong Shi, Zhihao Liu, Kang Chen, Weilin Liu, Gang Liu, Boxun Li, Jianlei Yang, Zhi Yang, Guohao Dai, Yu Wang]
venue: OSDI
year: 2026
tags: [reinforcement-learning, distributed-training, scheduling, embodied-ai, llm]
source_pdf: "[[osdi26-yu-chao.pdf]]"
source_md: "[[osdi26-yu-chao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用宏观到微观流变换统一大规模强化学习执行

> **原题**：RLinf: Flexible and Efficient Large-Scale Reinforcement Learning via Macro-to-Micro Flow Transformation

> **一句话总结**：现代 RL 的 generation、inference、training、tool 和 simulator 适合的资源划分并不相同；RLinf 用 M2Flow 把一份宏观 workflow 自动变成 temporal、spatial 或 hybrid 微观执行计划，在最多 256 张 H100 的真实训练中相对现有系统取得 1.07×–2.43× 端到端吞吐提升，但其中一部分收益来自实现优化而非调度本身。

## 问题与动机

现代强化学习（reinforcement learning，RL）不再只是“采样后训练”的两阶段循环。推理 RL 可能包含生成、log-prob inference、reward、actor 和 critic；agentic RL 还会调用搜索工具；具身 RL 则同时运行物理模拟、渲染、VLA generation 和训练。这些组件在显存、算力、CPU、并行方式和运行时间波动上差异很大。

已有系统常在两个极端中选择一个。Temporal/collocated 模式让所有组件依次使用全部 GPU，显存可以复用，但必须等待最慢的 rollout；论文在 64 张 H100 上测到，7B 数学 RL 的未完成 response 很快降到少于 5%，剩下的少量长尾仍会阻塞整阶段。Spatial/disaggregated 模式把组件固定到不同 GPU 并流水执行，可以遮住长尾，却可能因静态切分造成某一阶段拥塞、其他 GPU 空闲。具身 workload 还会同时受 GPU 显存和 CPU core 数量限制，因此不存在一种固定模式对所有 RL 都最好。

RLinf 要解决两个相连的问题：开发者能否只写一份容易理解的逻辑流程；系统能否根据 workload 和资源，把它自动变成合适的时空执行计划，而不要求开发者为每种 placement 重写程序和通信代码。

## 关键观察 / 隐含假设

- **观察 1：真正需要选择的是每个组件何时、在哪里运行。** Logical workflow 的数据依赖不变，但 generation、inference、training 和 simulator 可以共享设备、分设备流水，或只对部分组件做流水。把逻辑和执行分开后，同一程序才有机会搜索完整的 temporal–spatial 组合（§3.2–§3.3，图 6–7）。
- **观察 2：最好的执行模式随算法和 workload 改变。** 长序列 GRPO 的 spatial 模式比 veRL 慢 44.3%–68.6%，PPO 的 spatial 模式却能靠阶段重叠取胜；ManiSkill 适合 hybrid，而 CPU-intensive 的 LIBERO 反而适合 temporal。这组反例直接说明“永远 collocate”或“永远 disaggregate”都不成立（§5.1，图 8、10、14–15）。
- **观察 3：少量 profiling 足以给候选计划排序。** 四个 Qwen2.5-GRPO case 中，temporal 估计误差少于 2%，spatial 少于 5%，且没有改变模式排名。离散 GPU placement 也让一段范围内的 profiling 噪声仍映射到同一计划（§5.2，图 16–17）。
- **假设 1：离线样本能代表后续执行。** Profiler 只测少量 data-parallel size，再用多项式外推时间和显存；若 response length、tool latency 或 simulator 行为快速漂移，初始计划可能失效。系统用持续 15% 偏差触发重规划，但没有给出完整的触发、checkpoint 和 redeploy 开销实验（§3.4）。
- **假设 2：组件能正确实现资源切换。** 每个 worker 必须提供 `onload`/`offload`，系统才可安全做 context switch。抽象隐藏了 placement，却没有消除模型状态、optimizer、随机数状态和外部环境被正确保存的实现责任（§3.2–§3.3）。
- **假设 3：受限搜索空间包含好计划。** Scheduler 会把 cycle 合并成一个 node，并把该 node 的计算均匀分给 GPU；所谓“optimal”是对该递归 s–t cut、候选 parallelism 和预测模型而言，不是任意 cyclic workflow 的全局最优（§3.4，算法 1）。

## 核心方法

**一份宏观程序。** 每类 RL 组件封装成 worker，同类进程组成 `WorkerGroup`。远程函数默认异步并返回 handle，开发者用 `wait` 表示必要 barrier，用 data channel 连接 producer 和 consumer。典型 reasoning runner 少于 100 行，但这不包含框架内置 worker 和算法实现；完整系统约 20K 行 Python（§3.2、§4）。

**M2Flow 变换。** Execution Flow Manager 可以把一次宏观调用拆成更小数据块形成弹性流水，也可以合并数据块。若两个依赖 worker 被放在同一设备，data channel 的分布式 device lock 按依赖顺序执行 `onload`、工作、`offload`，实现 temporal multiplexing；若放在不同设备，channel 允许它们并发形成 spatial pipeline；两者混用就是 hybrid 模式（§3.3，图 6–7）。

**Profile-guided scheduler。** Profiler 在少量 data-parallel size 上测每个组件的时间和显存，并捕获 worker 间的数据流图。Scheduler 递归枚举 DAG 的 s–t cuts：两个子图可共享同一组 GPU 顺序执行，也可分到两组 GPU 流水执行；动态规划比较两种成本并选择设备数和 micro-batch 粒度。典型 chain-like graph 的复杂度为 $O(V^3N^2)$，固定 topology 时随设备数为 $O(N^2)$（§3.4，算法 1）。

**运行时适应。** Worker 持续记录实际时间；偏差在滑动窗口中持续超过默认 15% 时，RLinf checkpoint、更新 profile、重新搜索并部署。论文称 reasoning RL 通常数千 iteration 后才需要一次，但没有把这条路径作为端到端实验变量（§3.4）。

**自适应通信。** Worker 和 connection manager 延迟建立连接，并按数据与进程位置选择 [[NCCL]]、同 GPU 的 cudaIPC 或 CPU 的 Gloo。任意 Python object 会先抽出 buffer 直接传输，结构 metadata 随消息发送。FIFO data channel 还可把 GPU 数据 offload 到 CPU，并按 item weight 在多个 consumer 间负载均衡（§3.5）。

## 设计取舍

- **统一 workflow 换取 worker 约束。** 开发者不用为 temporal、spatial、hybrid 各写一套控制流，但必须遵守 worker、channel、`onload`/`offload` 接口；“runner 少于 100 行”不能代表迁移任意新算法只需 100 行。
- **自动搜索换取 profiling 依赖。** 多项式外推和简单 pipeline 模型让搜索可扩到大量 GPU，却忽略动态 batching、通信竞争、tool tail 和一些 cyclic 细节。运行时重规划是补救，而不是预测误差消失。
- **弹性流水换取额外状态管理。** 更小粒度有利于遮住 rollout 长尾，但会增加 channel、同步和切换开销；更大粒度相反。Scheduler 依赖 profile 在两者间选择。
- **自己管理设备换取清楚的租户边界。** [[Ray]] 只负责进程启动和控制，RLinf 在 cluster manager 已分配的固定资源内自行放置；它不解决跨 job 抢占、公平或全局资源调度。
- **停止全作业换取恢复简单。** 任一 worker 失败后，Controller 停止全部组件，由用户从最近 checkpoint 重启；这避免部分组件继续产生不一致数据，但不是透明容错，也会放大单点故障影响（§4）。

## 实验与结果

- **平台与口径**：主实验最多使用 32 个 node、每 node 8 张 H100-80GB、2 个 48-core Xeon 8558、2 TB 内存和 8 张 400 Gbps ConnectX-7 [[RDMA|RoCEv2]] NIC。吞吐结果是 warm-up 后 10 个 iteration 的平均值；论文没有给方差或误差条。Reasoning 基线统一使用 [[SGLang]] rollout 和 [[Megatron|Megatron-LM]] training（§5.1）。
- **Reasoning RL**：Qwen2.5 1.5B/7B/32B、64/128/256 GPU 的 GRPO 中，RLinf-Temporal 比 veRL 快 1.10×–1.58×，但作者明确把收益归因于更大 KV-cache、较好的显存管理和较低同步开销，而不只是 M2Flow。PPO 中，RLinf-Spatial 对 veRL 的提升为：1.5B 上 35.0%–69.6%，7B 上 38.7%–60.7%，14B 上 27.2%–56.5%。Qwen3-30B-A3B 的 spatial 模式在 32/64 GPU 比 Slime-Colocate 快 31.2%/7.2%，到 128 GPU 却因 overlap 不足而落后（§5.1.1，图 8–13）。
- **Agentic 与 embodied RL**：单 node 8 张 H100 上，Search-R1/Qwen2.5-3B 达 67.3 requests/s，官方 veRL 实现为 30.4 requests/s，即 2.2×。ManiSkill 上没有外部分布式基线，Hybrid 仅与 RLinf 自己的模式比较，分别比 Temporal 和 Spatial 高 52.2%–69.1% 与 60.7%–87.2%。LIBERO 上 Temporal 比 SimpleVLA-RL 快 37.8%、42.6%、143.4%（8/16/32 GPU），其中收益也来自去掉重复 environment 初始化和把 action、log-prob 合成一次 forward（§5.1.2–§5.1.3，图 14–15）。
- **搜索器**：四个 Qwen2.5-GRPO case 的 temporal/spatial 时间误差分别少于 2%/5%。三 node 合成 workflow 从 8 扩到 1,024 GPU 时搜索耗时由 $7\times10^{-4}$ s 增至 5.98 s；继续模拟到 4,096 GPU 仍少于 60 s，这不是 4,096 GPU 的实际训练。1.5B GRPO、128 GPU 的噪声实验中，rollout 低估约 29% 或 training 高估约 48% 前仍选择同一最优 placement（§5.2，图 16–17）。
- **训练正确性**：RLinf 不改变 RL 算法。固定 wall-clock/compute budget 下，1.5B 模型在 AIME24/AIME25/GPQA 得 48.44/35.63/38.46，平均 40.84，分别高于 base 的 28.33/24.90/27.45；7B 在 GPQA 得 48.18。ManiSkill 和 LIBERO 的 success rate 也随 RL 提升。这些结果支持训练能正常收敛，但不能单独证明相同 sample 数下的 sample efficiency（§5.3，表 2–4）。

## 论断—证据表

| 论断 | 直接证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 同一宏观 workflow 可以执行为多种时空计划 | 同一 RLinf runner 下比较 Temporal、Spatial、Hybrid；图 7 展示统一机制 | 依赖 worker 正确实现资源切换；没有量化迁移现有自定义算法的工程量 | 中强 |
| 不同 RL workload 的最优模式确实不同 | GRPO spatial 明显退化，PPO spatial 取胜，ManiSkill hybrid 取胜，LIBERO temporal 取胜 | 只覆盖论文选定的模型、batch、sequence 和硬件 | 强 |
| RLinf 提高端到端训练吞吐 | Reasoning 最高 1.70×，agentic 2.2×，embodied 最高 2.43× | 多项收益由显存、同步、初始化和 fused forward 共同贡献 | 强（系统整体）/中（M2Flow 单独贡献） |
| Profiler 与搜索器能找出这些实验中的好计划 | 四 case 排名不变；噪声范围内仍选同一 placement | 搜索扩展性用三 node 合成图；未测实际大规模重规划 | 中强 |
| 系统支持广泛硬件与故障场景 | 接口声称覆盖多 vendor accelerator、robot arm 和 checkpoint restart | 性能实验全部是 NVIDIA H100；失败恢复没有定量实验 | 弱到中 |

## 批判性分析

### 论证链条

论文最扎实的链条是：先用 response 长尾和 embodied component profile 说明固定执行模式会浪费资源，再用 M2Flow 把逻辑与 placement 分离，最后用四类 workload 展示最优模式真的不同。这个证据支持“需要灵活选择”，也支持 RLinf 作为完整系统更快。它没有隔离 M2Flow 的净贡献：GRPO 的 Temporal 与 veRL 结构相近，提升主要来自显存和同步；LIBERO 的提升又包含 environment 初始化与 fused forward 优化。因此不能把全部 1.07×–2.43× 都归给 scheduler。

### 假设压力测试

最重要的压力测试应让 rollout length、tool latency 和 simulator cost 在训练中突然改变，再记录 15% detector 发现延迟、旧计划损失、checkpoint/redeploy 停顿和是否来回振荡。对带循环的 agent workflow，应比较“cycle 合并后均分”与人工非均匀 placement。还应故意让 `onload`/`offload` 很慢或状态不完整，检查 device lock 只保证互斥时，训练语义和吞吐会如何退化。

### 实验可信度

统一 engine、parallelism、公开 baseline 和最多 256 张 H100 的规模让端到端性能结果有较强可信度；论文还主动报告 spatial 失败的 case，而不是只展示赢家。弱点是每项只平均 10 个 iteration、无方差，模式与基线并非每个 workload 都齐全：ManiSkill 没有外部系统，agentic 只测单 node；4,096 GPU 只是 scheduler 计算。训练质量比较使用固定 wall-clock/compute budget，更适合做 correctness sanity check，而不是严格等样本的算法等价实验。

### 系统性缺陷

RLinf 的统一抽象仍把关键正确性责任交给 worker 作者，channel worker、全局 worker/connection manager 和 device lock 的扩展性及故障行为没有测量。Runtime replan 会停全作业并 checkpoint，故障也会停全作业；动态性越强，这个集中式重配置路径越可能成为瓶颈。硬件接口声称支持 NVIDIA、AMD、Intel、Ascend、MUSA 和 robot arm，但所有性能数据来自同构 H100。它也只在 cluster manager 给定的 allocation 内优化，不处理多租户公平、跨 job 弹性、能耗或 GPU-hour 成本。

## 局限与后续工作

- 对 response/tool/simulator 分布突变做在线重规划实验，报告 detection lag、重部署停顿、振荡次数和累计吞吐损失。
- 用正交消融把 scheduler、KV-cache allocation、通信同步、environment 初始化和 fused forward 的收益分开。
- 在 agentic、cyclic 和异构硬件 workflow 上与人工最优、其他自动 placer 比较，不只比较 RLinf 自身模式。
- 注入 worker、node、channel manager 和网络故障，量化 checkpoint 丢失工作量与恢复时间；进一步支持局部恢复。
- 同时报告吞吐、GPU utilization、GPU-hours、能耗和等样本训练曲线，避免“更快 iteration”掩盖资源成本或 sample efficiency。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[KV-Cache]]、Reinforcement Learning、spatio-temporal scheduling
- **运行时与 engine**：[[Ray]]、[[SGLang]]、Megatron-LM、veRL、Slime
- **同会议**：[[OSDI-2026]]
