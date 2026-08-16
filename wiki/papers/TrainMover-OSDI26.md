---
type: paper
name: TrainMover
full_title: "TrainMover: An Interruption-Resilient Runtime for ML Training"
authors: [ChonLam Lao, Jiaqi Gao, Jiamin Cao, Zhipeng Zhang, Pengcheng Zhang, Jiangfei Duan, Zhilong Zheng, Yu Guan, Yichi Xu, Yong Li, Zhengping Qian, Aditya Akella, Minlan Yu, Ennan Zhai, Dennis Cai, Jingren Zhou]
venue: OSDI
year: 2026
tags: [distributed-training, fault-tolerance, live-migration, collective-communication, checkpointing]
source_pdf: "[[osdi26-lao.pdf]]"
source_md: "[[osdi26-lao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# TrainMover：抗中断的机器学习训练运行时（OSDI 2026）

> **原题**：TrainMover: An Interruption-Resilient Runtime for ML Training

> **一句话总结**：TrainMover 观察到替换训练机器时，真正必须暂停全局训练的工作只有最新状态和通信连接切换，冷启动与大部分通信组准备都能提前完成；它用无通信的 shadow iteration、两阶段增量 CCL 和可接替任意角色的 standby，把 1,024-GPU 实验中的计划迁移与意外故障停机分别降到 16.6 秒和 21.1 秒，并外推 64K GPU 每周可少浪费 55% GPU-hours。

## 问题与动机

大模型训练会持续数周甚至数月，又要求数千张 GPU 每轮同步。一个 GPU、CPU、网络设备或后台进程变慢，就会拖慢整个任务；一台机器宕机则可能令训练直接退出。论文引用的生产数据中，Llama 3 训练的 MTTF 只有 2.7 小时，Meta 的 8,192-GPU 任务 ETTR 可降到 0.6。故障之外，驱动更新、硬件维护、资源整理和高优任务抢占也会主动中断训练。

传统办法是停任务、换机器、从 [[Checkpoint-Restart|checkpoint]] 重启。一个 8,192-GPU 生产任务平均要 6.47 分钟，其中不算基础设施的 framework 初始化也要 4.45 分钟：checkpoint loading 占 35.1%，NCCL 创建占 24.5%，冷 warm-up 占 40.4%（表 1）。Oobleck、Parcae 一类弹性系统能先缩容再扩容，但新加入的机器仍要创建通信组、分配显存和 JIT 编译，扩容一步反而可能超过 100 或 200 秒。

直接改变 TP、PP、DP 或 EP 布局也不理想。大规模训练已经按模型、显存和互连仔细调优，少一台机器可能降速、OOM，或让整个 DP 组闲置。因此 TrainMover 不重新规划训练，而是让健康机器一对一接替故障机器的原角色。生产集群本来常保留 backup/elastic GPU；论文列举的比例约为 6%，设计目标是把这些资源变成准备充分的替补，而不是让全任务等待冷启动。

## 关键观察 / 隐含假设

- **观察 1：初始化很慢，但大部分不需要处在全局停机路径上。** GPT-10B 的单次 warm-up 不含 NCCL 就约 150 秒，首轮还因 JIT 和级联初始化慢约 6 倍。只要新机器能独立走过真实执行路径，就能在旧机器继续训练时提前完成这些工作（§4.1）。
  - **依赖假设**：训练路径、kernel 顺序、tensor shape 和 collective 顺序大体确定；运行时数据不会触发完全不同的大块初始化。
- **观察 2：更换整台机器只改变少数 CCL channel。** 组内大部分成员、机内 NVLink 和 topology 不变，没有必要销毁并重建所有通信组。64 张 A100 的 GPT-10B 设置中，完整 NCCL setup 约 50 秒，其中 connection establishment 占 76.45%（表 2）。
  - **依赖假设**：迁移以机器为主要粒度，joiner 的本地拓扑与 leaver 兼容，增量 topology 仍能得到高效 channel。
- **观察 3：训练 rank 高度对称。** [[Tensor-Parallelism|TP]]、[[Data-Parallelism|DP]]、[[Expert-Parallelism|EP]] rank 的参数形状、kernel 和 collective 基本相同；[[Pipeline-Parallelism|PP]] 也通常只有首段、中间段、末段三种角色。一个 standby 依次 warm-up 这三类，就不必为每个 rank 准备一台替补（§6）。
  - **可能失效场景**：异构或多模态模型、动态 layer、数据依赖控制流，以及强烈不均匀的 pipeline stage 会打破这种对称。
- **假设 1：故障已被立即定位并隔离。** 所有 downtime 实验都假设 fault localization/isolation 是瞬时的，所以报告的是训练 runtime 的处理时间，不是告警出现到训练恢复的完整时间。
- **假设 2：最新训练状态有可用来源。** 计划迁移可从 leaver 直接传；意外故障需要 DP 冗余、远端 CPU memory checkpoint，或退回远端存储 checkpoint。不同来源会改变恢复关键路径。

## 核心方法

### 1. 把恢复拆成准备与切换

计划事件到来后，controller 给新 elastic machine 分配将要接替的角色。joiner 在准备阶段完成 sandbox warm-up 和第一阶段 CCL setup，leaver 与其他 stayer 继续正常训练。准备完成后，训练只在 iteration 边界短暂停顿：通信连接从 leaver 切到 joiner，最新模型与 optimizer state 一对一传输，随后 leaver 退出。

意外故障无法提前知道出问题的 rank，因此 TrainMover 在训练开始时部署 general standby，并预先完成同样的准备。故障后只给它绑定具体角色并进入切换阶段。若没有 standby，系统仍能在故障后启动 joiner，并把不同初始化工作尽量重叠，但 downtime 会更长（图 3）。

### 2. 用有效 tensor 回放触发真实 warm-up

简单用全零 tensor 跑假迭代可能产生 NaN、断言失败，或漏掉实际路径。TrainMover 在任务最初一轮，让指定 rank 的 hook 截获 collective 输出并把有效 tensor 存入持久存储；之后移除 hook，不再影响正常训练。joiner 先载入初始状态，再在通信隔离的 sandbox 中跑 shadow iteration：跨 sandbox 的 all-reduce 等调用返回记录值，barrier 和无返回状态的 send 可直接跳过，sandbox 内部通信仍真实执行（图 5）。

只记录可能跨迁移边界的通信，也去掉重复训练角色；GPT-5.12T [[MoE|MoE]] 设置下记录空间少于 300 GB。shadow 结果不承担正确训练状态，切换时会被 leaver 或 checkpoint 的最新状态覆盖。它的作用只是触发 CUDA context、显存分配、JIT、data loader 等隐式初始化。MoE routing 等未覆盖路径仍可能在切换阶段补初始化，论文称所测情况只有毫秒级，但没有给系统性的动态路径覆盖率。

### 3. 两阶段增量修改 [[NCCL]]

第一阶段在训练后台执行。stayer 复用已有 TCP bootstrap，joiner 与相关成员交换 topology 和状态，所有参与者本地计算新旧 topology 的差异；CPU 侧 metadata 和 joiner 本地 channel 可以提前准备。此时原通信组仍工作，stayer 不创建新的跨机 GPU connection，所以不增加训练 GPU 的峰值显存。

第二阶段调用 `CCL_switchover()`，只把受影响的 RDMA queue pair 从 stayer–leaver 改成 stayer–joiner，继承不变 channel，并回收旧 topology。最新训练状态与连接切换并行传输。为避免临时状态通道抬高峰值，leaver 复用即将释放的 gradient buffer；joiner 利用第一、二阶段之间尚未建立跨机连接的显存空档，传完就销毁状态通道（图 6、19）。这里的“zero memory overhead”指迁移不超过原训练显存峰值，不是 standby 本身不消耗 GPU。

### 4. 一个 standby 覆盖多种角色

无 PP 时，各机器角色对称，一次 shadow iteration 即可。启用 PP 时，standby 最多依次跑首段、末段和中间段三轮；JIT artifact 每种角色只多几百 KB，完成后保留最常见的中间段状态。若实际故障发生在首段或末段，再补分配 embedding/output layer 的少量参数和 optimizer state。standby 的 CCL 仍停在第一阶段，具体相邻 stage 的连接等角色确定后再建立（图 7）。

原型约 12 KLoC，修改 [[Megatron]]-LM、[[PyTorch|PyTorch]] c10d 和 NCCL，并有独立 controller。状态源可以是 leaver、DP 副本、远端 CPU memory checkpoint 或存储 checkpoint；后一种仍保留 durability fallback，TrainMover 并没有取代 checkpoint。

## 设计取舍

- **保留原布局换额外机器**：迁移后无需重新调并行策略，代价是需要可兼容的 elastic/standby 机器；空闲 standby 的机会成本在小规模、低故障率时可能高于节省。
- **record/replay 换框架通用性**：不必逐个拆解隐式初始化，却依赖执行路径确定、通信输出可记录，以及一份可能达到数百 GB 的准备数据。
- **增量 channel 换 CCL 改造成本**：只更新 delta 很快，但需要深入修改 PyTorch c10d 和 NCCL；普通未修改的 collective library 不能直接获得收益。
- **一台通用 standby 换相关故障覆盖**：单机故障时经济，机架、交换机或电源导致多机同时失效时，一两台 standby 可能立即耗尽。
- **内存峰值不增加换精细生命周期管理**：复用 gradient buffer 和连接建立空档很节省，但状态通道、旧 group 与新 group 的释放顺序必须严格正确。

## 实验与结果

- **平台与基线**：最大 testbed 为 1,024 GPUs，模型从 GPT-175B 到 GPT-5.12T MoE，覆盖 TP、PP、EP 和 distributed optimizer；32-GPU 细测使用 Wikitext，并与 Megatron-LM restart、Oobleck、Parcae 比较。Oobleck 无法扩到 1,024 GPUs，Parcae 不支持 TP，两者都不支持 distributed optimizer，因此完整 baseline 对比只在其支持的 32-GPU 配置上成立（§8.1、表 3）。
- **随规模的停机时间**：从 32 扩到 1,024 GPUs，计划迁移从 11.5 秒增到 16.6 秒，general-standby 意外恢复从 19.8 秒增到 21.1 秒；同图中的 Megatron-LM framework restart 在 1,024 GPUs 接近 300 秒，而且还排除了 job cleanup 和 rescheduling（图 8）。
- **计划与意外事件**：不同模型/并行配置的计划迁移约为 2.3–7.9 秒，相对 Megatron-LM Save-and-Restart 至少快 15 倍；一次迁移 4%–33% GPU 时，GPT-20B/39.1B downtime 最高仍为 6.15 秒（图 10、12）。32-GPU 意外故障中，有 standby 时所有模型少于 10 秒；无 standby 时也最高比 Megatron-LM 快 3.48 倍，但 Oobleck/Parcae 无法运行 distributed-optimizer 大模型（图 11）。
- **消融、带宽与显存**：GPT-5.12T MoE 上，Megatron-LM 约 221 秒；直接状态迁移降到约 125 秒，两阶段 CCL 再降到约 80 秒，完整 sandbox warm-up 后为 16 秒。CCL 部分从 51 秒降到 7 秒。状态带宽为每 GPU 0.25–2 GB/s 时，TrainMover 保持 6–9 秒；Megatron checkpoint loading 最差到 GPT-20B 的 320 秒和 GPT-39.1B 的 750 秒。图 19 显示迁移显存不超过原峰值（图 15、17–19）。
- **频繁重平衡与 straggler**：每 10 分钟重平衡一次时，128–1,024 GPU 的 ETTR 为 0.98、0.98、0.98、0.97，Megatron-LM 为 0.50、0.49、0.44、0.42；这里的约 3% 损失是高频重平衡场景，不是 TrainMover 常驻运行开销。1,024-GPU、GPT-5.12T MoE 在第 75/100 轮注入单 GPU 20% slowdown 时，TrainMover 训练效率只损失 4.7%（图 13–16）。
- **生产规模是外推，不是实测**：64K 结论使用 1,024-GPU TrainMover downtime、32-GPU Oobleck/Parcae downtime、Meta MTTF、计划/意外事件 1:8.9 比例，并给所有系统加 2 分钟基础设施成本。按该模型，论文报告 TrainMover with standby 比最佳替代少浪费 55%，每周少约 140 万 GPU-hours；在 128K 点，相对 no-standby TrainMover 少 55%，相对 Parcae 少 88%（图 9）。

## 论断—证据表

| 论断 | 论文证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 准备/切换分离能把千卡训练停机压到约 20 秒 | 图 8：1,024 GPUs 下计划 16.6 秒、意外 21.1 秒 | 合成 GPT 配置；不含 fault detection 与 rescheduling | 强 |
| sandbox 与两阶段 CCL 都在关键路径上贡献明显 | 图 15：约 221→125→80→16 秒；CCL 51→7 秒 | GPT-5.12T MoE 单组消融 | 强 |
| delta 与一对一传输让多机迁移近似不随比例增长 | 图 12：迁移 4%–33% 时最高 6.15 秒 | GPT-20B/39.1B，所测网络与拓扑 | 中 |
| 迁移不增加原训练显存峰值 | 图 19 的 leaver/joiner memory timeline | 特定实现与 buffer 生命周期；standby 容量另计 | 中 |
| 64K GPU 可少浪费 55% GPU-hours | 图 9 的成本模型 | 从 1K/32 GPU 测量、外部 MTTF 和单故障假设外推 | 中 |

## 批判性分析

### 论证链条

论文从 restart breakdown 找出两个可提前做的主要成本——warm-up 与 CCL setup，再分别用 sandbox 和两阶段增量连接移出停机路径，图 15 的逐项消融与图 8 的扩展结果能对上设计。general standby 又补上“意外故障没有准备通知”的缺口，整体链条闭合。需要收窄的是经济结论：千卡 downtime 是实测，64K 的 55% 和 140 万 GPU-hours 是按故障模型计算出来的预测。

### 假设压力测试

故障检测并非瞬时，silent data corruption、慢节点定位和网络隔离可能比 20 秒更久。论文主要考虑一台或一批已明确 leaver 的机器；共享交换机、电源或软件 bug 造成相关故障时，standby 数量、状态来源和 delta channel 都可能一起失效。动态 MoE、多模态分支、异构 GPU/driver 或运行时改变 shape 时，预录一轮 tensor 未必触发所有初始化。若 distributed optimizer 没有内存冗余，意外故障还必须从存储恢复最新 checkpoint，优势会依赖 checkpoint 新鲜度和带宽。

### 实验可信度

评测覆盖 32–1,024 GPUs、dense/MoE、不同并行维度、计划/意外事件、多机迁移、带宽、显存和消融，证据较完整。限制是 Oobleck/Parcae 只在 32 GPUs 且功能受限，Megatron 的图 8 还排除了 cleanup/rescheduling；这些 baseline 数字不能直接当成同一生产系统的完整端到端恢复。64K/128K 没有实测，模型把各系统 downtime 固定，并用文献中的 MTTF 和事件比例。论文也没有报告恢复前后 loss/optimizer state 的逐位或收敛验证、反复迁移稳定性与失败中的失败。

### 系统性缺陷

系统要同时改训练框架、c10d、NCCL 和 controller，升级任一层都可能破坏 hook 顺序、group ordering 或显存生命周期。持久化的通信 tensor 可能很大，也需要和模型版本、并行布局严格匹配。所谓 zero memory overhead 依赖精细复用即将释放的 buffer，论文未讨论异常中止时如何回滚半切换 group。standby 仍是昂贵 GPU，只是论文在投影中把它计入浪费；如何按相关故障概率决定数量和跨故障域放置仍是运维问题。

## 局限与后续工作

- **局限 1**：实测最大 1,024 GPUs，64K/128K 成本与故障收益依赖外推。
- **局限 2**：假设故障立即定位，主要验证单机/已知批次迁移，没有覆盖 silent corruption 和恢复过程再次失败。
- **局限 3**：record/replay 依赖静态、对称训练路径；异构、多模态和动态执行只被列为 future work。
- **后续工作 1**：接入真实 detector，报告异常发生、定位、隔离、状态恢复到重新产出有效 step 的端到端 P50/P99。
- **后续工作 2**：注入 rack/switch/power 相关故障和恢复阶段二次故障，测所需 standby 数、放置策略与失败回滚。
- **后续工作 3**：在 64K 生产 trace 上验证 MTTF 外推，并报告 standby GPU-hours、记录存储、controller 运维和 checkpoint durability 的完整成本。

## 相关

- **相关概念**：[[Distributed-Training]]、[[Checkpoint-Restart]]、[[Live-Migration]]、[[NCCL]]、[[RDMA]]
- **相关系统**：[[Megatron]]、[[Parcae]]、[[Oobleck]]
- **同会议**：[[OSDI-2026]]
