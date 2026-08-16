---
type: paper
name: EcoServe
full_title: "Efficient LLM Serving on Commodity GPU Clusters with Data-Reduced Cross-Instance Orchestration"
authors: [Jiangsu Du, Hongbin Zhang, Taosheng Wei, Zhenyi Zheng, Jiazhi Jiang, Kaiyi Wu, Zhiguang Chen, Yutong Lu]
venue: OSDI
year: 2026
tags: [llm-serving, scheduling, gpu-cluster, disaggregation, kv-cache]
source_pdf: "[[osdi26-du.pdf]]"
source_md: "[[osdi26-du]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# EcoServe：在普通 GPU 集群上减少跨实例数据搬运的 LLM 服务（OSDI 2026）

> **原题**：Efficient LLM Serving on Commodity GPU Clusters with Data-Reduced Cross-Instance Orchestration

> **一句话总结**：NoDG 把 prefill/decode 放在一起会互相干扰，FuDG 完全拆开又需要高速网络搬运 [[KV-Cache]]；EcoServe 让每个完整实例在时间上轮流执行较长的 prefill/decode 窗口，再让多个实例错峰提供 prefill，在 32-GPU L20/Ethernet 配置中，相对 vLLM、Sarathi、DistServe、MoonCake 的 goodput 分别提高 1.96×、1.99×、2.51×、2.40×。

## 问题与动机

[[LLM-Inference]] 有两个硬件特征不同的阶段：prefill 一次处理整段输入，矩阵乘法大多是 compute-bound；decode 每次只生成一个 token，需要反复读取模型权重和已有 KV cache，通常是 memory-bandwidth-bound。服务系统既要让首 token 时间（TTFT）达标，又要让每 token 时间（TPOT）达标，还希望提高吞吐。这三个目标互相牵制。

现有 cluster serving 大致有两种路线：

- **非解耦（NoDG）**：同一个模型实例完成 prefill 和 decode。好处是不搬 KV cache；问题是长 prefill 会挡住 decode，decode 又打断 prefill。即使采用 separate batching、hybrid batching 或 [[Chunked-Prefill]]，频繁切换仍会增加 TTFT/TPOT，并阻止 decode 积累足够大的 batch。
- **完全解耦（FuDG）**：独立的 prefill instance 生成 KV cache，再传给 decode instance。这样消除阶段干扰，却把压力放到网络和资源配比。表 3 显示，8×A800 跑 Llama-30B 时每秒生成约 38.96 GB KV 数据，理论上就需要至少 400 Gbps；小 block、复杂拓扑和 collective contention 还会提高实际要求。

很多已有集群只有 [[PCIe|PCIe]] GPU 和 10/25 Gbps inter-node network。论文的主 L20 集群就在为一家大型 super app 提供 LLM 服务，但评测 workload 不是该服务的线上 trace，而是公开数据集加合成到达过程。EcoServe 的核心问题是：能否不依赖 NVLink/InfiniBand，既减少 prefill–decode interference，又避免跨实例搬 KV cache？

## 关键观察 / 隐含假设

- **观察 1：问题不只是“prefill 太长”，还包括 phase switching 破坏 batch。** NoDG 为守住 TPOT 必须频繁回到 decode，decode batch 难以变大；pipeline parallelism 还会因输入长度不同和 decode iteration dependency 产生 bubble（§2.2–§2.4、图 4）。
  - **设计含义**：让每个阶段连续执行更久，可以减少切换并提高 arithmetic intensity。
  - **可能失效场景**：只有一个实例或并发很低时，长窗口只增加等待，PaDG 会退化为 NoDG。
- **观察 2：decode 提前生成的 token 可以形成短期 TPOT slack。** 前端按 typewriter 方式播放 token；若一段时间内生成速度快于 TPOT SLO，运行时可以用积累的 saved TPOT 插入 prefill（§3.1.1、§3.3）。
  - **依赖假设**：短窗口的历史 decode 进度能预测接下来可借用的时间，prefill duration 也能按输入长度准确 profile。
  - **风险**：算法使用所有 existing request 的 **mean saved TPOT**，平均值可能掩盖 slack 最少的单个请求，因此不能直接推出每个请求都达标。
- **观察 3：一个实例不能同时处于两个阶段，但多个实例可以错峰。** 只要 macro-instance 中不同实例轮流进入 prefill，新请求就不必等某个固定实例结束 decode（§3.1.2、图 5）。
  - **依赖假设**：有足够多的完整模型副本和足够请求，让 rolling activation 的额外并行度被利用。
- **观察 4：FuDG 的相对表现由 KV-to-compute ratio 和 network 决定。** Llama-30B 使用 [[Attention|MHA]]，KV 较大；CodeLlama2-34B/Qwen2-72B 使用 GQA，KV 更小。A800 相对 L20 的计算能力增加超过 4×，网络只增加 2.5×，FuDG 反而更容易被网络卡住（§4.2.2–§4.2.3）。
- **假设 1：每个 PaDG instance 能容纳完整模型和 active KV。** EcoServe 省掉传输的办法是复制模型，不是减少模型/KV memory。
  - **可能失效场景**：ultra-large dense/[[MoE|MoE]]、超长 context 或 memory budget 很紧时，完整副本数会成为上限。
- **假设 2：macro scheduler 收到的状态足够新。** Instance 通过 ZeroMQ queue 上传 phase、decode progress 和 memory；调度器据此连续 admission。
  - **证据强度**：弱到中。论文没有测 queue delay、stale-state admission 或 scheduler overload。

## 核心方法

### 1. 时间上的部分解耦

EcoServe 把自己的策略称为部分解耦（partially disaggregated，PaDG）。每个 instance 仍加载完整模型并保留本地 KV cache，但不再频繁混合 prefill/decode：一段较长时间只做 prefill，下一段较长时间只做 decode。与 FuDG 不同，请求不会在两个模型副本间迁移，因而没有显式 KV transfer；与 NoDG 不同，每个阶段可以积累更大 batch（§3.1.1）。

单实例 PaDG 会让新请求等待下一个 prefill window。EcoServe 因此把多个 instance 组成 **macro-instance**，让它们按循环顺序错峰进入 prefill。Macro scheduler 尽量先把连续请求送到同一个仍有余量的 instance；不满足约束时再检查下一个，从而在减少切换的同时维持 prefill availability（§3.1.2）。

### 2. 三层调度架构

- **Instance scheduler** 管单个模型实例内的 prefill/decode、device execution 和上层指令。
- **Macro-instance scheduler** 汇总一组实例的实时状态，运行 admission/routing，并维持 rolling activation。
- **Overall scheduler** 在多个 macro-instance 间选择服务单元；论文主要实现和评测 macro-instance 内部（图 5）。

实现以 [[vLLM]] 0.7.3 为单设备 runtime，用 Ray 控制一个 instance 内的多 GPU，用 ZeroMQ 同步 status。这个层次把大集群拆成多个调度域，但 macro scheduler 仍是每个域的集中控制点。

### 3. 把 phase-switch waiting 算进 TTFT

论文指出，NoDG/PaDG 在 prefill 后可能还要等 phase switch，FuDG 则要等 KV transfer；若只从 prefill kernel 起止计算 TTFT，会漏掉用户真正等的时间。EcoServe 的 TTFT 等于原始 TTFT 加 phase-switch waiting，TPOT 则从真正进入 decode 后开始计（§3.2、图 6）。这比一些只报 runtime phase 的口径更严格，但也意味着跨论文比较时必须确认指标定义一致。

### 4. 三项 admission 检查

对每个新请求，macro scheduler 循环检查候选 instance（算法 1）：

1. 根据输入长度 profile 每个 pending prefill duration，要求总 prefill 时间不超过 TTFT SLO；
2. 对已经 decode 的请求计算 `output_length × TPOT_SLO − elapsed_since_first_token`，取 mean saved TPOT，要求它不小于待插入的 prefill 总时间；
3. 估计新请求需要的 KV cache，要求不超过剩余 GPU memory。

通过后，instance 继续处理当前 decode，收到上层的新 request 后切换到 prefill。Slack 只在短 decode interval 内积累和消费，减少对未知总输出长度的长期预测；不过公式仍使用已经生成的 `output_length` 和请求 KV size，论文没有详细给出未知未来输出的 memory reserve policy。

### 5. Mitosis 式弹性伸缩

若一个 macro-instance 无限制长大，scheduler 会成为瓶颈；若每次按整组 macro-instance 扩容，capacity jump 又太粗。EcoServe 为每组设下界 `N_l` 和上界 `N_u`，先逐个加/减 instance，越过上界时把实例“分裂”为两个 macro-instance，缩容则反向 merge（§3.4、图 7）。

扩容信号是平均 TTFT 超出 SLO，因为 overload 时 admission queue 会先拉高 TTFT；缩容信号是 saved TPOT 高于根据当前实例数计算的上界。被移除的 instance 会先完成已有请求再释放。

InstanceHandler 只保存 entrypoint 与 message queue 等 metadata，可用 Python pickle 在 macro scheduler 进程间传递；目标 scheduler 反序列化后接管原 instance，不重新加载模型。动态扩容实验中，CodeLlama2-34B 从本地盘重新加载一个 L20 instance 约需 3 分钟，所以这种“迁移控制权而不搬运行中模型”的做法很有价值（§3.4.3）。

## 设计取舍

- **少搬 KV 换更多完整副本。** PaDG 适合网络弱但 GPU memory 尚可的集群；FuDG 能独立配 prefill/decode 数量，PaDG 只能以完整实例增减。
- **长 phase 换更好 batching。** 时间解耦提高吞吐，却把 TTFT/TPOT correctness 交给 profile 和 admission；预测错误会集中造成 SLO violation。
- **平均 slack 换简单决策。** Mean saved TPOT 容易计算，但不保护 slack 最小、等待最久的请求，也没有显式 fairness/age priority。
- **层次化调度换状态同步。** Macro-instance 限制单 scheduler 规模，代价是 status queue、跨 scheduler ownership 和 split/merge correctness。
- **Drain 换不中断输出。** 缩容不杀 active request，因此长输出可能让 GPU 很久不能真正释放。
- **“Cost-effective” 主要是架构判断。** 论文报告 throughput/SLO，不报告 GPU-hour、energy、设备价格或 total cost，不能从 goodput 直接推出实际成本最低。

## 实验设计

三套 testbed 为：8 节点 64×L20 48 GB，GPU 走 PCIe、节点间 10 Gbps Ethernet；2 节点 16×A800 80 GB、25 Gbps RoCE；2 节点 16×H100 80 GB，节点内 NVLink、节点间每 GPU 一条 400 Gbps InfiniBand。模型是 BF16 Llama-30B、CodeLlama2-34B 和 Qwen2-72B。

数据集和默认 SLO 为：Alpaca-gpt4 平均输入/输出 20.63/163.80 tokens，TTFT 1 s、TPOT 100 ms；ShareGPT 为 343.76/237.20，5 s/100 ms；LongBench 为 2,686.89/101.78，15 s/100 ms（表 4）。默认到达是 fixed-rate Poisson；burst 实验改用 Gamma 并调 coefficient of variation。

Baseline 包含 NoDG 的 vLLM、Sarathi，以及 FuDG 的 DistServe、MoonCake，统一或对齐 vLLM 0.7.3；MoonCake 扫不同 prefill/decode ratio 取最佳。指标是把 arrival rate 逐步提高，记录仍能达到 P50/P90/P99 TTFT+TPOT SLO 的最大 throughput，即论文所称 goodput。部分 DistServe/MoonCake case 无法满足 SLO，DistServe 也不能在单节点用 TP=8 跑 Qwen2-72B，这些点被省略（§4.1–§4.2）。

## 实验与结果

- **普通网络是主结果。** 在 L20/A800 的全部可运行 case 中，EcoServe 的 P90 goodput 相对 vLLM、Sarathi 平均提高 2.01×、1.87×，相对 DistServe、MoonCake 提高 3.43×、3.41×（§4.2.1、图 8）。摘要在 32-GPU L20 配置报告的四个对应数字为 1.96×、1.99×、2.51×、2.40×。
- **高速网络上优势缩小，也不是每个点都赢。** H100/NVLink+IB 上，P90 goodput 相对 vLLM、Sarathi、DistServe、MoonCake 分别为 1.34×、1.25×、1.75×、1.24×；MoonCake 在 CodeLlama2-34B 上可以超过 EcoServe。作者还明确指出 DistServe prototype 未维护、MoonCake 仍在开发，baseline 工程成熟度是混合变量（§4.2.1）。
- **模型、网络与数据共同决定收益。** 相对 NoDG，Llama-30B/CodeLlama2-34B/Qwen2-72B 平均提高 1.59×/1.83×/1.76×；相对 FuDG 为 4.82×/2.15×/1.79×。P90 下，对 NoDG 的 L20/A800/H100 增益为 1.97×/1.91×/1.29×，对 FuDG 为 2.45×/4.21×/1.50×；按 Alpaca/ShareGPT/LongBench 分组，对 NoDG 为 1.19×/1.26×/2.72×，对 FuDG 为 1.70×/4.00×/2.53×（§4.2.2–§4.2.4）。Llama-30B 的 LongBench 输入被 2,048 context limit 截断，实际 workload 更轻，不能当作公平长上下文结果。
- **严格 SLO 和 burst 都会降低 tail goodput。** CodeLlama2-34B+A800+ShareGPT 从 `(5 s,100 ms)` 收紧到 `(1 s,50 ms)` 时，EcoServe P99 throughput 从 42 降到 18 rps，少 57.1%；vLLM 16→6.4、少 60.0%，Sarathi 28→7.6、少 72.9%，DistServe 和 MoonCake 分别少 26.9% 和 23.9%，但后两者在宽松 SLO 下已经受 KV transfer 和 load imbalance 限制。Gamma CV 从 1.2 增到 2.0 时，P99 throughput 下降 EcoServe 17.3%、vLLM 19.5%、Sarathi 35.7%、DistServe 12.6%、MoonCake 17.1%（§4.3–§4.4、图 10–11）。
- **多实例既增加容量，也减少 interference。** L20 上从 1 个扩到 4 个 instance，CodeLlama2-34B 和 Qwen2-72B throughput 分别达到 4.96×、5.47×；单 instance 时 PaDG 实际退化为 NoDG。动态实验把 arrival 从 20 增到 50 rps，系统从 8 个 instance/32 GPU 扩到 64 GPU，在第 12 个 instance 时按 `N_l=6,N_u=11` 分成两个 macro-instance；图 13 的 split 附近 SLO attainment 短暂降到约 85% 后恢复，并非零扰动（§4.5、图 12–13）。该实验只升载和扩容，没有实测 contraction/merge。
- **机制消融支持 rolling 与 adaptive routing。** A800+ShareGPT 的三模型、P50/P90/P99 下，cyclic activation 全部优于 random；adaptive admission 全部优于按 TTFT 的 `1/4、1/2、3/4、1` 固定间隔路由。L20 上 TP=2/PP=2 相对 TP=4/PP=1 在更紧 TPOT 下保持更高 plateau，说明 PaDG 比 vLLM 更能利用 [[Pipeline-Parallelism]]（§4.6–§4.7、图 14–16）。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| PaDG 在 commodity network 上比 NoDG/FuDG 有更高 SLO goodput | 图 8–9：L20/A800 P90 平均提升 1.87×–3.43× | 30B/34B/72B，公开数据集，Poisson arrival；部分 baseline failure 点省略 | 强 |
| 收益与 compute/network、KV 大小相符 | §4.2.2–§4.2.4：A800 对 FuDG 4.21×，GQA model 的差距更小 | 三种 GPU/network、三个模型；不是逐组件 controlled experiment | 中 |
| Rolling activation 与 adaptive admission 都有独立贡献 | 图 15–16：所有三模型/attainment 下优于 random/fixed interval | A800、ShareGPT；没有调度 overhead 数据 | 强 |
| Mitosis 能平滑扩容 | 图 13：8→16 instances，split 后 SLO 小幅波动 | 单向升载；没有缩容、merge 或 failure | 中 |
| EcoServe 是更“cost-effective”的选择 | 只报告 goodput 和 SLO | 无 GPU-hour、设备价格、energy 或 operator cost | 弱 |

## 批判性分析

### 论证链条

论文的主线很清楚：NoDG 的瓶颈是 phase interference，FuDG 的瓶颈是 KV movement；PaDG 用时间上的解耦保留本地 KV，再用跨实例错峰补回 TTFT。实验也显示网络越弱、KV-to-compute ratio 越高，EcoServe 对 FuDG 的优势通常越大；H100 上差距缩小。这一趋势支持设计动机，而不是只给一个最大 speedup。

但端到端收益混合了调度策略和 baseline 实现质量。作者自己说 DistServe prototype 未维护、MoonCake 仍在开发且会 pause/buffer shortage；部分不能运行或不能达标的 case 被省略。因而 3.4× 以上的 FuDG 差距不能全部归因于“必须搬 KV”。Rolling/adaptive 的消融更能单独支持 EcoServe 的两项机制。

### 假设压力测试

PaDG 的关键资源不是网络，而是模型复制和本地 KV memory。对 7B/13B 或宽松 SLO，NoDG interference 本来就小；对 ultra-large model、严格 TPOT 或超长 context，单个完整 instance 可能装不下或没有足够 slack，论文也承认需要 FuDG/新硬件。MoE、[[Speculative-Decoding|speculative decoding]]、prefix sharing 和多 tenant adapter 都没有实测。

Admission 用 mean saved TPOT，而服务目标通常是 per-request/p99。若某些长输出请求刚好没有 slack，其他快请求的富余会把平均值抬高，算法仍可能接纳 prefill。Status queue 延迟、同时到达的 request 和错误 output/KV estimate 会进一步放大 stale decision。论文报告 aggregate attainment，没有按 request age、output length 或 tenant 分组验证 starvation/fairness。

### 实验可信度

三种 GPU、三种 interconnect、三模型、三数据集、三档 SLO attainment，加上 SLO sensitivity、burst、scaling、parallelism 和消融，覆盖面很好。指标把 phase-switch wait 纳入 TTFT，也避免隐藏 PaDG 自己引入的等待。

外部有效性仍有限。默认是公开数据集上的 Poisson arrival，Gamma 也只是合成 burst；没有 super app 的真实 arrival、prefix reuse、conversation correlation 或 multi-tenant trace。LongBench 在 Llama-30B 上被截断，且某些 baseline 失败点缺失。实验最大模型 72B dense，没有 130B/MoE/ultra-long context。

“Cost-effective” 没有直接证据：L20/A800/H100 的购买或租用价格、GPU utilization、energy、额外完整副本和 operator complexity 都没有转为总成本。Goodput 更高是重要结果，但不是成本模型。

### 系统性缺陷

Macro scheduler、overall scheduler、ZeroMQ status queue 和 pickle proxy 扩大了控制面。论文没有报告 scheduling CPU、queue depth、state staleness、scheduler crash、network partition 或 ownership transfer 中断。Python pickle 还要求严格控制可信输入和版本兼容；它传的是 handle，不是 durable request/KV state。

动态实验只验证扩容和 split。Contraction 要等待 active request drain，长输出可能让 GPU 很久不能释放；merge、反复 scale oscillation 和缩容期间 SLO 均未测。若 instance 在迁移 ownership 时失败，request/KV 由谁接管、是否重复输出 token也没有 fault-injection 证据。

## 局限与后续工作

- **局限 1**：收益依赖多个完整模型副本；单 instance 退化为 NoDG，memory-limited model/context 可能无法形成足够 macro-instance。
- **局限 2**：Mean saved TPOT 不是 per-request tail/fairness 保证，profile 与 status stale 的错误率未测。
- **局限 3**：只用公开 dataset 和合成 arrival，缺少 production multi-tenant trace、MoE 与真正长 context。
- **局限 4**：扩容实验未覆盖 contraction、merge、oscillation 和 long-request drain。
- **局限 5**：没有 GPU-hour、energy、hardware price 或运维成本，无法验证“cost-effective”的总成本结论。
- **后续工作 1**：按 request age/output length 记录 predicted slack、actual slack 和 SLO violation，比较 mean、minimum、quantile admission policy。
- **后续工作 2**：重放真实多 tenant burst/prefix trace，测 status staleness、scheduler CPU、p99.9 TTFT/TPOT、starvation 和 queue buildup。
- **后续工作 3**：在相同 GPU-hour、memory 与 energy budget 下比较 PaDG/NoDG/FuDG，分离 replication 与 scheduling 收益。
- **后续工作 4**：循环执行 expand→split→contract→merge，并注入 instance/scheduler crash，验证 request/KV ownership 和输出不重复。
- **后续工作 5**：扩展到 MoE、100K+ context 和 adapter multi-tenancy，找出 PaDG 无法满足 SLO、必须转 FuDG 的可测阈值。

## 相关

- **相关概念**：[[LLM-Inference]]、[[KV-Cache]]、[[Disaggregation]]、[[Chunked-Prefill]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[RDMA]]
- **同类系统**：[[vLLM]]、Sarathi、DistServe、[[Mooncake]]
- **同会议**：[[OSDI-2026]]
