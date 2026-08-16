---
type: concept
aliases: [Speculative Decoding, speculative decoding, SpecDec, Spec-Dec]
parent: "[[LLM-Inference]]"
last_updated: 2026-08-14
tags: [llm-inference, decoding, latency-optimization]
---

# 推测解码（Speculative Decoding）

> 推测解码先用较便宜的草稿路径一次提出多个候选 token，再让目标模型并行验证。它减少的是目标模型必须串行执行的解码轮数，不是目标模型的参数量。

## 它到底做了什么

普通自回归解码每轮只确定一个 token：目标模型读一遍权重和 [[KV-Cache]]，采样后才能开始下一轮。推测解码把一轮拆成三步：

1. **草拟（draft）**：草稿模型、目标模型的早退层、n-gram 表或其他便宜路径提出一段候选。
2. **验证（verify）**：目标模型用一次并行前向计算候选各位置的分布。
3. **提交（commit）**：接受一段前缀；在第一个拒绝位置停止，并用目标分布决定后续 token。

对于 greedy decoding，候选只有与目标模型逐位选择一致时才能提交。对于随机采样，必须使用正确的接受概率和拒绝后的校正分布，才可保持目标模型原有的输出分布。论文所说的“无损”通常只指这个**分布语义**，不代表浮点结果逐位一致，也不代表系统实现没有 nondeterministic kernel、状态同步或取消请求方面的错误。[[ReSpec-MLSys26]] 就观察到，理论无损的方案在 RL 训练环中仍可能因实现非确定性、草稿模型过时和采样方差而影响 reward。

树形或多分支草稿只是一次验证更多路径；它仍须遵守同一条原则：未被目标模型接受的候选不能进入已提交输出，也不能污染后续可见的 KV 状态。

## 为什么可能更快，也为什么经常不快

一次验证平均接受的 token 越多，节省的串行轮数越多；但系统同时增加了草拟、验证更大 token batch、维护草稿 KV、同步和回滚的成本。能否加速主要由下面几项共同决定：

- **平均接受长度**：领域、温度、草稿质量、候选深度和训练阶段都会改变它。
- **草拟成本**：大草稿模型通常更准，却可能先把收益吃掉；小模型、n-gram 和 self-speculation 各有不同成本。
- **验证效率**：一次验证多 token 能提高并行度，但 batch 已很大时，验证可能从带宽受限转为计算受限。
- **请求批次**：低 batch 的目标模型更容易从多 token 验证受益；高 batch 本来就有足够并行度，额外候选可能变慢。
- **内存与通信**：草稿和目标模型可能需要两套权重或 KV；多节点方案还会增加同步和候选传输。
- **调度与工作负载**：输出长度、请求优先级、RL policy 漂移和前台应用争用都会改变最佳策略。

因此，接受率高不等于端到端吞吐高。[[SHIP-MLSys26]] 在 Llama-3.3-70B 上发现 1B/3B 草稿模型能明显加速，而 8B 草稿即使接受率更高也难胜过不启用推测解码。[[ReSpec-MLSys26]] 的一个配置在 batch 32 时则从低 batch 的 1.46 倍加速降到 0.76 倍，也就是反而更慢。

## 经验规律与证据

### 验证往往才是主要成本

[[SpecDecodeBench-MLSys26]] 把草拟、验证和 KV 开销拆开后发现，验证可占总时间的 42%–95%。随 batch 增大，n-gram 草拟成本通常低于 2%，EAGLE 类草拟成本占比可从 12%–20% 降到 3%–7%，但整体收益仍会因验证变得计算受限而下降。该论文还报告：固定候选长度 5 的最佳点约为 2.1 倍，自适应长度约为 2.3 倍，而知道未来结果的 oracle 可到 2.75 倍；这些数字说明“选多少候选”本身就是调度问题。其 4.9 倍多方法 oracle 没计入在线切换和额外 KV 成本，不能当成可部署结果。

[[DataflowIsAllYouNeed-MLSys26]] 从另一侧说明草拟也可能成为主导：在其 8B 草稿、70B 目标、候选深度 9 的 GPU 配置中，草拟占推测解码时间 72%。论文在 SN40 数据流硬件上通过常驻参数和流水化得到超过 6 倍加速，但部分 H100 对比来自外推；结果依赖特定草稿、接受率和硬件映射，不能直接代表通用 GPU 服务。

[[FlashInfer-Bench-MLSys26]] 把推测验证纳入可复现 kernel/workload 评测，提醒比较时同时固定 batch、序列形状、接受模式和后端。只报某个 verify kernel 的 microbenchmark，不能回答在线服务的 TTFT、TPOT 或吞吐是否改善。

### 草稿容量与单步成本可以解耦

[[PRISM-MLSys26]] 观察到越靠后的候选越难被接受，于是把不同 draft step 映射到不同参数模块：总草稿容量可以增加，每步仍只激活一个模块。它在集成 [[SGLang]] 的 batch 1 评测中，相对优化后的推理栈把解码吞吐提高到 2.6 倍以上，并显示数据规模继续增加时接受长度仍能上升。边界也很明确：实验没有覆盖高并发 continuous batching，总参数增加仍占存储，且“每步激活量恒定”只在草稿保持带宽受限时近似等于“延迟恒定”。

[[SpecDiff-2-MLSys26]] 用 diffusion drafter、streak distillation 和候选自选择提高并行候选质量；在其模型和任务上，相对 EAGLE-2 的 tokens/s 提高 55%，相对普通自回归生成最高 5.5 倍。这里的“无损”仍依赖正确拒绝采样，且实验采用固定窗口和特定任务。

[[TiDAR-MLSys26]] 不再维护独立小模型，而让同一模型在一次前向中并行做 diffusion draft 与自回归验证，利用带宽受限前向中的空闲计算槽。论文在 batch 1 的 H100 上对 1.5B/8B 模型报告 4.71/5.91 倍加速；它需要训练这种专用架构，不是可直接套到任意现有模型上的 serving 插件。

[[HELIOS-MLSys26]] 走的是 early-exit/self-draft 路线，以同一模型的浅层生成候选，避免独立草稿权重。它给出的一个能耗对照中，OPT 的独立草稿加目标模型方案耗能是其双早退方案的 1.49 倍；论文没有给出现代 EAGLE 类方法的完整端到端同条件比较。

### 非参数草稿适合可复用上下文

n-gram、suffix tree 和历史 token 草稿不执行神经网络，成本很低，但要求请求之间或同一请求内部有可复用片段。[[Seer-OSDI26]] 在 GRPO 同 prompt 的一组 responses 中维护压缩后缀树，并根据 batch 与在线接受统计最多分配 8 个候选；相对普通推测解码最高再提高 1.3 倍吞吐，平均接受长度增加 0.22。它的完整系统收益还包含 rollout 切块、KV 迁移和长请求优先调度，不能全归因于推测解码。

[[DAS-MLSys26]] 同样利用 RL rollout 最近生成的后缀树，并按候选长度分配预算；论文报告 rollout 时间降低超过 50%、整体训练时间约降低 25%，同时保持 reward 曲线。收益依赖 rollout 轨迹重复、短期历史仍能代表持续更新的 policy，以及后缀树查找低于目标验证所省时间。

[[Sereno-OSDI26]] 用 n-gram 在移动端补回被抢占草拟造成的吞吐损失。它更重要的贡献不是提高接受率，而是把候选当成**可以安全丢弃的工作**：前台应用争用内存带宽时，可在草稿子图边界快速让出 NPU；目标验证则改用预编译的不同 batch 并插入短暂停顿。四个应用的消融中，n-gram 把受限配置的吞吐从 14.42 提到 18.06 token/s；候选接受率从面向吞吐方案的 30.4% 降到 18.9%，说明系统主动用更低吞吐换前台 QoS。

### 稀疏执行只有在索引成本也受控时才有用

[[SparseSpec-MLSys26]] 用稀疏注意力做 self-speculation，复用精确验证阶段得到的 attention score 来指导下一轮草拟，并加入统一调度、延迟验证和 KV offload。它相对 [[vLLM]] 最高达到 2.13 倍，相对 MagicDec 和 TriForce 的最高加速分别为 1.36 和 1.76 倍。设计依赖 attention pattern 在相邻轮次具有局部稳定性；选择、元数据和不规则 kernel 过贵时，稀疏率不会自动变成端到端收益。

[[KAIROX-OSDI26]] 把 GPU–CPU 神经元稀疏执行与固定 5 个候选的推测解码结合。论文的推测配置收益低于普通生成配置，而且只测 batch 1；其结果说明更大的 verify batch 会改变稀疏与 dense kernel 的盈亏点，部署前应同时扫描 batch、候选长度和稀疏阈值。

[[AttributionSparseActivation-MLSys26]]、[[GeneralSparse-ATC25]]、[[BLASST-MLSys26]] 和 [[SkipKV-MLSys26]] 都把稀疏激活、稀疏注意力或 KV 优化列为可与推测解码组合的方向，但各自的 headline 结果不是推测解码实验。不能把这些论文的独立稀疏加速与推测解码加速直接相乘。

## 在线服务、RL 与移动端需要不同控制器

### 普通在线服务

在线服务关心 TTFT、TPOT、吞吐和尾延迟。固定候选长度在请求长度、batch 和缓存命中不断变化时很脆弱。[[Pie-SOSP25]] 提供可编程 inferlet，让应用能表达自定义 speculative loop、KV 生命周期和外部工具调用；它证明的是编程接口与调度底座，论文的主要性能数字来自 agent/deliberate workflow，并非一种新草稿算法。[[SGLang-NeurIPS24]] 的主要贡献是 RadixAttention、压缩状态机和运行时调度；它支持推测路线的集成，但不能用其整体吞吐数字证明推测解码本身的收益。

[[SHIP-MLSys26]] 把草稿放成额外的 pipeline stage，展示低延迟 SRAM 硬件同样需要在草稿大小和接受率之间找平衡。[[QFactory-ATC25]]、[[Toppings-ATC25]]、[[Kitty-MLSys26]]、[[Libra-ICLR26]]、[[LocalityAwareBeamScheduling-MLSys26]] 和 [[WaferLLM-OSDI25]] 主要研究量化、服务框架、beam 调度或硬件映射；它们只讨论与推测解码的兼容或后续组合，没有给出足以归因到推测解码的端到端证据。

### 强化学习 rollout

RL 的 policy 每轮都在变化，草稿模型会迅速过时；同一 prompt 又会生成一组相关 responses，提供普通在线请求没有的共享信息。[[ReSpec-MLSys26]] 用离线 profile 按 active batch 动态开关和选择参数，并用 reward 加权的在线知识蒸馏持续更新 EAGLE-3 草稿。Qwen2.5 3B/7B/14B、GRPO、2×8 H100 的实验中，平均端到端加速为约 1.84/1.69/1.50 倍，峰值 4.53/2.41/2.60 倍，validation/reward 曲线接近无推测基线。证据限于数学任务、GRPO 和这组硬件；reward 很噪或 batch 长期饱和时收益会变窄。

[[Seer-OSDI26]] 则不训练神经草稿，而利用同组 responses 的重复片段和低 batch 长尾。其完整系统相对同步 veRL 把 rollout throughput 提高 44%–104%，其中加入 grouped speculative decoding 后，在前两项调度机制之上再贡献 26%–48%。三个工作负载都来自内部 GRPO 类训练，并依赖大容量全局 KV 池和高速 RDMA。

[[DAS-MLSys26]] 与 Seer 都利用 rollout 历史，但前者强调近期后缀树和长度预算，后者把组级上下文、优先级与分布式 KV 调度放进同一控制面。两者共同说明：RL 推测解码的关键不是固定选一种 drafter，而是处理 policy 漂移、组内相关性和 active batch 的变化。

### 移动端后台推理

[[Sereno-OSDI26]] 的目标是保护与 LLM 共用 SoC 内存带宽的前台应用。相对 PowerServe，它在 30 个应用上把 jank 平均降低 58.5%，同时将后台 LLM 吞吐平均提高 26.4%；相对不受控推测解码则会主动牺牲吞吐，例如 Social 场景从 19.84 降到 16.00 token/s，以换取 jank 从 15.38% 降到 8.14%。这些结果只覆盖两代 Snapdragon 和一组 W4A16 Llama 目标/草稿模型，不是所有移动 NPU 的硬保证。

## 系统接口与可观测性

- **KV 生命周期**：验证需要临时候选 KV，拒绝、取消和切换模式时必须准确回收。[[SpecDecodeBench-MLSys26]] 测到草稿加目标 KV 的内存可达到单目标方案的 1.77 倍。
- **运行时切换**：[[ReSpec-MLSys26]] 根据 active batch 在普通解码与推测解码间切换；[[Sereno-OSDI26]] 只能选择预先导出的 NPU 子图和 verify batch 档位。
- **性能建模**：[[DCP-OSDI26]] 的 SLO 预测器需要把 speculative kernel、候选数和接受率变化当作 workload 变化；DCP 本身没有评测推测解码。
- **跨节点 KV**：[[DirectKV-OSDI26]] 将推测解码列为未来集成方向，没有实验；[[EcoServe-OSDI26]] 也未把推测解码纳入其能耗/资源调度主结果。
- **诊断**：[[StriaTrace-OSDI26]] 在生产 trace 中找到被额外送去验证的 “ghost token”，说明 token 数、候选数和接受率必须进入 latency roofline；其 tracing 成果不是推测加速结果。
- **边缘 profiler**：[[ProfInfer-MLSys26]] 指出长上下文、推测解码和 dynamic batching 会改变其 batch 1 decode 模型，但没有实际测这些组合。

## 设计选择

| 草稿来源 | 优点 | 主要代价 | 代表证据 |
|---|---|---|---|
| 独立神经草稿 | 接受率通常较高，可单独训练 | 多一份权重/KV，可能过时 | [[PRISM-MLSys26]]、[[ReSpec-MLSys26]] |
| 目标模型早退或自推测 | 复用参数，减少额外模型 | 层间状态与调度更复杂 | [[HELIOS-MLSys26]]、[[SparseSpec-MLSys26]] |
| n-gram / suffix tree | 草拟便宜、容易在线更新 | 依赖文本或组内重复 | [[DAS-MLSys26]]、[[Seer-OSDI26]]、[[Sereno-OSDI26]] |
| diffusion / 专用并行架构 | 一次生成更多候选 | 需要专门训练，非即插即用 | [[SpecDiff-2-MLSys26]]、[[TiDAR-MLSys26]] |
| 固定长度 | 实现与图编译简单 | workload 一变就可能越过盈亏点 | [[SHIP-MLSys26]]、[[KAIROX-OSDI26]] |
| 在线自适应长度/开关 | 能跟随 batch、接受率和争用 | 要 profile、观测和稳定控制 | [[ReSpec-MLSys26]]、[[Seer-OSDI26]]、[[Sereno-OSDI26]] |

## 容易混淆的边界

- [[Belfast-OSDI25]] 里的 “speculative shared log” 是分布式日志的乐观执行，与 LLM 推测解码不是同一概念；它的链接只表示词义辨析。
- [[Transformer-NeurIPS17]] 建立了自回归生成的串行瓶颈，但没有实现推测解码。
- [[CDLM-MLSys26]] 可以作为未来草稿模型，论文主结果是 diffusion language model 的 block-causal 蒸馏，不是 draft-and-verify serving 评测。
- [[Prism-OSDI26]] 研究多模型服务的显存气球，与同名的 [[PRISM-MLSys26]] 草稿模型无关；前者没有把推测解码作为核心机制。
- “可组合”不等于“已验证”。相关压缩、稀疏、KV 或编译论文只有在实际报告联合配置时，才可作为组合收益证据。

## 评价一篇推测解码论文时应看什么

1. 是否说明 greedy 或 sampling 的正确性协议，并验证拒绝、取消和 KV 回滚。
2. 是否同时报告平均接受长度、草拟时间、验证时间、KV 占用和端到端 TTFT/TPOT/吞吐。
3. 是否扫描 batch、候选长度、温度、输入领域和输出长度，而不是只选一个最佳点。
4. 是否与“关闭推测解码的同一优化引擎”比较，避免把 runtime 或 kernel 改进算给算法。
5. 若是 RL，是否报告 reward/time-to-quality、多 seed 和草稿更新成本；若是在线服务，是否报告 P95/P99 与取消请求；若是移动端，是否同时报告前台 QoS、能耗和热约束。
6. oracle 是否计入模式切换、额外模型、KV、通信和控制器开销。

## 仍未解决的问题

- 在 continuous batching 中，用稳定控制器联合选择草稿来源、候选长度、树宽和是否关闭推测，而不产生振荡。
- 在 domain drift、RL policy 更新和多租户混合请求下在线估计接受率，并给出预测误差的安全回退。
- 统一管理草稿/目标 KV、prefix cache、取消、迁移和故障恢复，证明未提交状态不会泄漏或被复用。
- 把能耗、GPU/CPU/NPU/网络资源和尾延迟纳入同一成本模型，而不是只追求 tokens/s。
- 建立覆盖多模型、多任务、多 batch 与真实到达 trace 的公共 benchmark，并区分算法上限、kernel 上限和完整系统收益。
