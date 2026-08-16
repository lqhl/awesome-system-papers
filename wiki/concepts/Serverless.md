---
type: concept
aliases: [Function-as-a-Service, FaaS-Platform]
last_updated: 2026-08-14
tags: [cloud, faas, isolation, scheduling]
---

# Serverless

> 无服务器计算（serverless computing）把机器供给、扩缩容和执行环境管理交给平台，用户按 invocation、任务或实际资源使用付费。“无服务器”不是没有服务器，也不必然无状态；它描述的是资源与运营抽象。

## 一个请求实际经历什么

平台收到请求后，通常要完成：

1. 选择 region、worker、CPU/GPU 与隔离环境；
2. 拉取代码、container image、模型和依赖；
3. 创建或恢复 process、container、MicroVM 或专用 runtime；
4. 装载应用状态，建立网络与存储连接；
5. 执行并保存外部 effect；
6. 缓存、暂停、快照或回收环境，并进行计费。

“冷启动”可能发生在每一层。只优化 process restore，不代表完整平台从收到请求到返回结果都变快；只保留 warm container，也不代表模型已经在 GPU、连接已经恢复或数据已经本地可用。

## 核心矛盾

Serverless 通过细粒度按需分配减少 idle capacity，却把启动、状态、隔离、控制面和尾延迟推到关键路径。平台必须证明：回收的 CPU、GPU 和内存价值大于反复 provision、迁移状态与远端通信的成本。

不同论文中的“serverless”粒度也不同：普通 FaaS 按函数 invocation；Burst Computing 按协作 worker group；Quark 按 Spark task；Torpor/Aegaeon 按 token 或模型驻留；RollArt 只把 reward 阶段外包给 FaaS。比较时必须先确认调度和计费单位。

## 冷启动不是一个数字

### 执行状态恢复

[[Spice-OSDI26]] 发现 process snapshot 同时需要“按预计访问顺序存盘”和“按原虚拟地址恢复”，普通 ELF/快照格式很难兼顾。它用 SHELF、`spliceVMA`、`reexec()` 和 Junction 元数据批量恢复，在 13 个函数中让冷调用只比热调用多 0.6–18 ms，平均比所测 process/VM snapshot 方案快 7.5/9.5 倍。

证据边界很重要：评测排除了请求调度、placement、network setup、container/cgroup/namespace 配置，并预先准备 LibOS pool。它证明的是**已有隔离环境内的函数状态恢复**接近 warm start，不是完整云平台的端到端 cold start。

[[PhoenixOS-SOSP25]] 处理 GPU process checkpoint/restore：通过 kernel 参数推测读写集，再用 instrumentation 验证，实现 soft copy-on-write 与 on-demand restore。Llama2-13B 迁移 downtime 从 9.8 秒降到 2.3 秒，冷启动 622 ms。它依赖 GPU kernel 可分析、验证路径覆盖和额外 runtime，不等同于 CPU FaaS snapshot。

### Container image 供给

[[Poby-ATC25]] 测到 cold start 的 image provisioning 中，extraction 至少占 68.8%。它把下载、解压、传输和 unpack 分给 RNIC、SmartNIC accelerator、PCIe/host memory 与 CPU，平均相对 containerd/iSulad 加速 11.5/7.1 倍并减少 host CPU。其分布式 cache hit rate 是实验参数，testbed 只有 2 个 BlueField worker、扩展实验 5 节点；真实生产 image locality 与 churn 未验证。

### 从根本上缩小 sandbox

[[Dandelion-SOSP25]] 认为保留 POSIX-like guest OS 是 cold start 的根因之一，因而把函数限制为 pure compute + HTTP communication DAG，并使用约 100 微秒 sandbox。Azure trace replay 中 committed memory 降低 96%，尾延迟波动下降 2–3 个数量级。代价是放弃完整 POSIX、任意本地状态和传统网络语义；它不是对现有 MicroVM 的无缝替换。

[[Quilt-SOSP25]] 从程序层消除 invocation tax：在 LLVM IR 合并资源兼容的函数，9/11 个短 workflow 中 median completion latency 降低 45.63%–70.95%。它适合短、可合并函数；长函数、外部服务等待、不同语言/runtime 与 provider 限额会缩小收益。

## 从单函数走向协作任务

[[BurstComputing-ATC25]] 指出，大规模短并行 job 需要 worker 同时启动、彼此通信和共享数据，不能被当成 1,000 个无关 invocation。它用 flare group invocation 和 worker packing，把 960-worker all-ready latency 提高 11.5 倍、启动跨度从 18.8 秒降到 0.44 秒；PageRank 远端流量降 98.5%、快 13 倍。

这里牺牲了普通 FaaS 简单的单 invocation 隔离、失败和计费边界。一个 pack 内 worker 共享环境，跨 pack 仍依赖 Redis、DragonflyDB、RabbitMQ 或 S3；message matching、deadlock 与 job-level retry 都回到用户或上层 runtime。

[[Quark-OSDI26]] 把同一原则用于 Spark。Ant Group 测到 executor 已分配资源中只有 67% 真正在计算，Quark 改为 task 级安全 container，配合 quota、干扰感知 placement 和快速 fork。双集群 replay 中资源消耗降 26.5%；真实迁移前后每 job 降 37.37%，但 workload 同时变化，后一个数字的因果性较弱。标题中的 serverless 是 task-level provisioning；Spark driver、quota manager、模板、shuffle 和 object storage 都仍常驻。

## 有状态 Serverless

FaaS 并不天然适合事务状态。每个 invocation 都去远端 datastore 做 lock 或 OCC validation，会让网络往返主导执行。

[[RTSFaaS-ATC25]] 为每个 KV 对象维护全局唯一 cache lease，用 transaction precedence graph 预序列化 workflow，再用单边 [[RDMA]] 转移 lease。相对 Boki/Beldi 吞吐最高 5/20 倍；即使把对手协议移植到同一 RDMA 环境仍快 1.7/2.1 倍。它获得 serializable execution，但依赖 driver 批处理、单副本 lease、TiKV 远端持久层和稳定 affinity；500 ms batch commit 使低负载延迟近似固定。

Stateful serverless 的关键不是简单“加一个 cache”，而是明确 cache 所有权、事务顺序、失败时 lease 恢复、重复 invocation 的 effect 语义以及远端 durable state。

## GPU 与模型 Serverless

### 长尾模型与 late binding

[[Torpor-ATC25]] 从 Alibaba trace 发现 85% GPU inference functions 平均每分钟调用不超过 1 次，early binding 会让模型长期占 GPU。Torpor 把模型放 host memory，请求到达后才 late-bind 到 4×V100 GPU pool，并流水化 swap；单节点服务 480 个函数，试点报告用户/平台 GPU 成本降低 70%/65%。数字依赖 V100 NVLink/PCIe 拓扑、host memory 容量和模型地址稳定；production isolation 模式还会增加数百毫秒到 1.5 秒 runtime restore。

[[Aegaeon-SOSP25]] 进一步在 decode token 边界抢占模型，把 70 个模型放进 10-GPU decoding pool；ShareGPT 0.1 RPS/model 时 goodput 为 ServerlessLLM 2 倍。Alibaba beta deployment 把 H20 provisioning 从 1,192 降到 213，但“7 models/GPU”只适用于 decode pool，不包括 prefill 和完整服务资源。

[[Alibaba-ASI-OSDI26]] 的 15.5 万 GPU trace 说明，serverless 平台也不能只看函数数：GPU 型号、8 卡节点碎片、CPU 配比、网络拓扑和在线预留共同决定可调度性。论文的 93% allocation ratio 不是 93% GPU compute utilization。

### 只把适合的阶段按需化

[[RollArt-OSDI26]] 发现 agentic RL 的 reward 计算短、突发、相对无状态，于是把 reward worker 变成内部 FaaS，同时把空出的 GPU 给 rollout。所测 16×H800 三个 math jobs 中，GPU utilization 从约 6% 升到 88%，rollout time 从 158 秒降到 77 秒。这个结果同时包含资源重分配与 remote reward；论文没有公开 FaaS cold start、GPU 计费、queue limit、failure 或数据隔离。

[[Murakkab-OSDI26]] 采用 serverless 式“声明做什么、平台决定怎么部署”来优化多模型 workflow，但核心系统仍是离线 profile、联合配置搜索、路由与资源规划。其 24 小时 trace 是构造 replay；相对手工 LangGraph 的 GPU、能耗和成本收益不能自动外推到未知 workflow 或 profile drift。

## 毫秒级实时 Serverless

[[Cosmic-ATC25]] 的 3D printing controller 每约 50 ms 必须完成一次矩阵计算，而 warm AWS Lambda invocation 中位就有 10.2 ms。Cosmic 用 cell grouping、约 85% 命中的投机预调度和配置搜索，在 30 个打印任务中全部满足时序，相对 VM 中位省 2.8 倍成本。它依赖特定 LPBF 状态演化、平台 warm retention 和近似预测；serverless provider 没有把 cold-start 概率当作硬实时 SLA。

这个案例说明：对严格 deadline，平均 cold start 没有意义。系统必须用预启动、冗余、投机或常驻 fallback，把 P99 与失效概率纳入正确性。

## 数据加载仍会限制函数

[[Umap-OSDI26]] 在 serverless LLM weight loading 中，用用户态请求聚合和可扩展 cache 重做 file-backed mmap；大 I/O、1–8 线程下相对 mmap 加速 2.3 倍。它只优化 weight 从 DFS 进入内存的路径，不包含容器创建、GPU mapping、模型初始化或完整 inference cold start。

## 设计取舍

| 设计选择 | 得到什么 | 失去或新增什么 |
|---|---|---|
| warm pool | 很低启动延迟 | 持续占内存/GPU，残留状态与预测失误 |
| snapshot restore | 保留初始化结果 | snapshot validity、外部 connection、格式与工作集预测 |
| 极小 sandbox | 微秒级创建 | POSIX、兼容性和本地可变状态 |
| function merge / worker packing | 少 invocation、共享数据、低 skew | 故障域、计费和隔离边界变大 |
| task/token-level allocation | 精细回收 idle resource | control-plane QPS、迁移与调度复杂度 |
| late-bound GPU model | 长尾模型共享 GPU | host DRAM、swap bandwidth与排队 |
| remote state / reward | compute 易弹性扩展 | 一致性、network tail、重试与数据治理 |

## 批判性分析

Serverless 不是一种固定 runtime，而是一种把“长期预留”改为“按实际需求绑定”的设计原则。OSDI 2026 的 Quark、RollArt、Murakkab、Spice 和 Umap 分别把它用于 batch task、RL reward、workflow configuration、process restore 和模型加载，粒度差异很大。

论文常见的最大风险是只计算被优化的局部路径。Snapshot 论文可能排除 placement 和网络，GPU pooling 论文可能只算 decode pool，task-level 论文可能保留大量 control plane，FaaS 成本论文可能假设 warm retention。可靠比较应从请求到达开始，把 image、sandbox、state、network、storage、GPU、retry 和 billing 全部计入。

第二个风险是把“资源利用率提高”当成业务价值。更高 allocation、GPU busy time 或更低 CU 只有在 P99、正确性、故障恢复和总成本不恶化时才成立；异构硬件和动态价格还会改变 break-even point。

## 开放问题

- 如何统一定义并测量完整 cold start，而不是各论文选择不同起止点？
- Socket、timer、device、multi-process 与 mutable shared state 的 snapshot/restore 语义是什么？
- Task、function 与 continuation retry 如何实现 exactly-once external effect，或明确提供 at-least-once？
- Burst arrival 下，control plane、registry、image cache、model swap 和 remote state 怎样共同做 capacity protection？
- 多租户共享 warm state、host memory 和 GPU 时，怎样防止数据残留、侧信道和 noisy neighbor？
- 计费应按 invocation、CPU/GPU time、memory residency、state transfer 还是 reserved SLO capacity？

## 相关论文

- **启动与执行环境**：[[Spice-OSDI26]]、[[PhoenixOS-SOSP25]]、[[Poby-ATC25]]、[[Dandelion-SOSP25]]、[[Quilt-SOSP25]]。
- **协作与 batch task**：[[BurstComputing-ATC25]]、[[Quark-OSDI26]]。
- **状态与实时性**：[[RTSFaaS-ATC25]]、[[Cosmic-ATC25]]。
- **GPU、模型与 AI workflow**：[[Torpor-ATC25]]、[[Aegaeon-SOSP25]]、[[Alibaba-ASI-OSDI26]]、[[RollArt-OSDI26]]、[[Murakkab-OSDI26]]、[[Umap-OSDI26]]。

## 相关概念

- FaaS、cold start、snapshot/restore、MicroVM、warm pool、late binding、autoscaling、stateful workflow
