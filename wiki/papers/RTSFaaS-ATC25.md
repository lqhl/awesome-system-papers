---
type: paper
name: RTSFaaS
full_title: "Towards High-Performance Transactional Stateful Serverless Workflows with Affinity-Aware Leasing"
authors: [Jianjun Zhao, Haikun Liu, Shuhao Zhang, Haodi Lu, Yancan Mao, et al.]
venue: ATC
year: 2025
tags: [serverless, faas, rdma, transactional, concurrency-control]
source_pdf: "[[atc2025-zhao-jianjun.pdf]]"
source_md: "[[atc2025-zhao-jianjun]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# RTSFaaS：通过亲和力感知租赁实现高性能事务性有状态无服务器工作流程（ATC 2025）

> **原题**：Towards High-Performance Transactional Stateful Serverless Workflows with Affinity-Aware Leasing

> **一句话总结**：关键观察是事务性 stateful [[FaaS]] 在 [[RDMA]] 网络上仍被远端 lock/validation 主导（banking workload 中 CC 占执行时间大头）；RTSFaaS 用 affinity-aware lease 让每个 KV 对象全局仅一个独占 cache 副本，并以 TPG 序列化执行 + 单边 RDMA 动态租约转移替代分布式锁，相比 [[Boki]] / [[Beldi]] 吞吐最高 5× / 20×，即便把对手 CC 协议移植到 RDMA 仍快 1.7× / 2.1×。

## 问题与动机

[[Serverless]] / [[FaaS]] 主流范式是无状态函数，但支付转账（withdraw ⇒ deposit）、库存、旅行预订等应用需要多函数 workflow 共享状态并保证 **serializable** 事务一致性。现有 stateful FaaS 平台（[[Beldi]] 的 [[2PL]]、[[Boki]] 的 [[OCC]]、T-Statefun）普遍依赖远端 datastore（DynamoDB、S3 等）做 lock 管理与冲突验证。

这带来两个结构性痛点：

1. **CC 通信开销主导**：即便把 lock/validation 优化到单边 [[RDMA]] verb，banking service 的 function 执行时间 breakdown 显示 CC 仍是主要瓶颈（Figure 1）。高 contention 下远端 lock 获取/释放与 OCC validation 的 RMA 开销不可忽视。
2. **强一致性削弱 cache 收益**：[[2PL]] 要求即使本地 cache 有效也必须远端取锁；[[OCC]] 虽可乐观读写本地 cache，但 commit 前 validation 失败会 abort/retry，频繁更新还会 invalidate cache。

作者 claim 的边界：不是重新发明 FaaS 编程模型，而是在 **compute-storage disaggregated** 架构下，为 **transactional stateful serverless workflows** 提供 serializable 一致性且显著降低 CC 通信开销。与 Apiary/Styx 等紧耦合 storage-compute 方案不同，RTSFaaS 保持 FaaS 常见的两层数据组织（worker 本地 cache + 远端 [[TiKV]]）。

## 关键观察 / 隐含假设

- **观察 1：在 RDMA 网络上，传统 2PL/OCC 的 lock/validation 通信仍是 stateful FaaS 的首要瓶颈，而非单纯「网络不够快」。** Figure 1 对 banking workload 的分解显示，即便 Boki OCC+cache 和 Beldi 2PL 都已用单边 RDMA 优化，CC 相关开销仍占 function 执行时间的大头；Figure 13 的 factor analysis 进一步表明「给现有协议加 RDMA」不能根治远端 storage 交互开销。
  - **依赖假设**：workload 是 **高 contention、多函数共享 KV state** 的事务性 microservice workflow，且一致性要求是 serializable 而非 TCC/causal。
  - **可能失效场景**：只读为主、极低 contention、或弱一致性可接受的场景下，OCC+cache 的乐观路径可能足够好，lease 序列化的收益会缩小。

- **观察 2：若每个 KV 对象在分布式 cache 中全局只有一个独占副本（leaseholder），大多数事务可以「强亲和」本地执行，从而把 cache 从「需远端协调的副本」变成「带独占访问权的 primary」。** 这与传统多副本 cache（需同步/锁）不同：leaseholder 独占控制对象访问，其他 worker 通过租约转移临时获得访问权。
  - **依赖假设**：对象的读写模式在 batch 内可通过统计表预测；且 **每个 function 只访问一个 key**（多 key function 被分解成单 key 子函数序列）。
  - **可能失效场景**：access pattern 剧烈漂移、热点 key 极高并发、或 function 无法预先分解为单 key 访问时，affinity 分配和 TPG 构造成本会上升。

- **观察 3：把 consistency guarantee 与 function execution 解耦为 planning / execution 两阶段，可用 TPG（temporal + parametric dependency）在 execution 前确定全局序列化顺序，从而避免执行期的分布式 lock 与 concurrency abort。** Lemma 1 证明按 TPG 调度可保证 conflict-serializable。
  - **依赖假设**：请求可被 batch 处理；driver 为每个 request 分配全局 timestamp；batch 内所有 worker 在 transition-flag 后看到一致的 global lease table。
  - **可能失效场景**：极低延迟 SLO 无法接受 batch 等待；跨 batch 的依赖若处理不当可能引入额外延迟或一致性窗口问题。

- **假设 1：部署环境提供低延迟 RDMA 互联（实验 RTT 7µs），且 worker 间可直接建立 one-sided RDMA 连接访问彼此注册的 memory region。**
  - **证据强度**：强（论文在 5 节点 Mellanox ConnectX-3 集群上实现并开源）。但未覆盖跨 AZ、无 RDMA 的云 VM 场景。

- **假设 2：事务的 read/write set 在执行前可知（或可通过 early read 确定），以支持 affinity 分配与 lease 表构建。**
  - **证据强度**：中。论文 Section 4.3 承认 dependent read 需要额外 round-trip 和悲观广播，是已知弱点。

## 核心方法

RTSFaaS 采用 driver + workers + [[TiKV]] 三层架构（Figure 3）。Driver 负责请求路由、统计表维护、lease 表更新与 batch 切换；每个 worker 含 scheduler、executors 和共享 local data cache；所有 worker cache 构成全局 shared memory pool，与 TiKV 形成两层存储。

### Affinity-aware Lease Assignment（关联感知租赁分配）

Driver 维护 per-worker 统计表：已分配 function 数 $N_i$，以及对每个 KV object $j$ 的访问计数 $N_i(j)$。新请求到达时，根据其 read-write set $K$ 计算 affinity score $A_i = \sum_{k_j \in K} N_i(k_j)$，再与 load balancing score $S_i = 1 - (N_i - min)/(max - min)$ 加权求和，选最高分 worker 接收请求。

一个 batch 的请求分发完毕后，按统计表为每个 object 指定 **访问频次最高** 的 worker 为 leaseholder（同分取最小 worker ID）。这使后续 function 更可能在本 worker cache 命中，减少跨节点访问。该设计直接回应观察 2：把 data-function affinity 从「事后 cache 命中」提升为「事前 lease 归属」。

### Planning：Global TPG 构造

RTSFaaS 将 consistency 与 execution 解耦：

- **Planning phase**：各 worker 识别 batch 内函数的 **temporal dependency**（不同 workflow、同 key、timestamp 有序）和 **parametric dependency**（同 workflow 内函数输出依赖），构建 local TPG；再通过 lease table 把跨 worker 的 remote function 元数据交换为 virtual vertex，拼成 global TPG。
- **Execution phase**：按 global TPG 的 breadth-first 顺序调度 function；leaseholder prefetch 对象、执行本地函数，遇到 remote function 时用单边 RDMA 读远端 cache 并检查 16-bit lease flag，执行完后按 TPG 把 lease 转回目标 worker。

Chandy-Lamport 风格的 **transition-flag** + driver 广播 global lease table 保证 batch 边界上所有 worker 对 lease 归属达成一致。该设计回应观察 3：用预先确定的 TPG 序列化替代执行期 lock contention。

### RDMA 数据通路与 Fault Tolerance

- 采用 **push-based RDMA write** + circular buffer（非 RDMA read），减少 round-trip 和 CPU 参与。
- 每个 cached value 前置 lease flag；leaseholder 更新 flag 完成租约转移（Figure 6）。
- 存储层依赖 TiKV 复制做 k-fault tolerance；计算层用 **snapshot + lightweight log**：batch 完成后 snapshot local cache，再 write-back TiKV；失败时从 snapshot 或 TiKV 重放 batch。完整数据丢失恢复约 729ms，snapshot 重试约 233ms；Docker 冷启动仍是主要恢复开销（~20s）。

### Transaction Abort 处理

RTSFaaS 在 planning 阶段消解 concurrency conflict，因此 **无 concurrency-related abort**；但业务约束（如余额非负）仍可能 abort。借鉴 Yao et al.，每个 workflow 以 condition-variable check 为首个函数，失败时向依赖函数传播 disabled signal，避免 cascading abort。

深度实现细节回 [[atc2025-zhao-jianjun]] 或 [[atc2025-zhao-jianjun.pdf]]。

## 设计取舍

- **单副本 lease vs 多副本 cache**：全局每对象仅一个 in-memory 副本，省去 replica 同步成本并强化独占语义；代价是热点 key 的 leaseholder 可能成为单点瓶颈（论文 Section 4.3 承认，建议未来借鉴 PolarDB 的 primary + read-only replica 模型）。
- **Batch 处理 vs 低延迟**：batch interval 默认 500ms，吞吐随 batch size 增至 n=25600 饱和，但中位延迟在低吞吐时也固定 ~500ms，p99 随 batch 增大显著恶化。这是为 TPG 构造和 affinity 统计付出的结构性延迟税。
- **Planning 开销 vs 执行期零 lock**：TPG 构造与 BFS 探索占用可观时间（Figure 13），但换来执行期无远端 lock/validation。短 workflow、低 contention 时 planning 相对收益可能变小。
- **Serializable 强保证 vs 弹性**：TPG 全局序列化限制了同 key 的并行度；比 OCC 的乐观并行更保守，但避免了 abort/retry 开销。
- **边界条件**：最优雅场景是 RDMA 互联数据中心、中高 contention 事务 workflow、access pattern 相对稳定、可接受百 ms 级 batch 延迟；脆弱场景是跨 region 无 RDMA、极端热点 key、dependent read 密集、或需要 sub-10ms SLO 的在线事务。

## 实验与结果

- **vs 完整系统（Boki/Beldi）**：Movie Review / Travel Reservation / Banking 三个 benchmark 上，median latency 700ms 时吞吐相比 Boki 提升 2.0× / 4.0× / 5.0×，相比 Beldi 提升 6.0× / 20× / 17×（Figure 9）。RTSFaaS 随吞吐上升延迟增长更平缓；低吞吐时因 500ms batch commit 呈现近似恒定延迟。
- **vs RDMA 移植 CC 协议**：将 Beldi 的 remote lock（RDMA CAS/FAA）和 Boki 的 remote OCC+local cache 移植到 RTSFaaS 的 RDMA 环境，RTSFaaS 仍快 1.7× / 2.1×。Skew 升高时 OCC 因 abort 急剧退化（θ=1 从 23k 降到 16k txn/s），remote lock 始终最差；RTSFaaS 在各 skew、read-only 比例、workflow 长度下最稳定。
- **Factor analysis**：remote lock/OCC 的主要时间在 lock/validation/storage 交互；RTSFaaS 虽花时间在 TPG 构造与探索，但总执行时间仍更低。
- **Batch size**：吞吐在 n=25600 饱和（计算资源用尽），p99 latency 随 batch 增大显著上升，因早到请求需等 batch 凑齐且 TPG 构造更慢。
- **Testbed**：5 物理机（1 driver + 4 worker），Xeon Gold 6230，Mellanox ConnectX-3，RDMA RTT 7µs；每 worker 8 CPU / 32GB / 2GB local cache；TiKV 三 PD + 三 TiKV 节点。Boki/Beldi baseline 在 c5d.2xlarge VM 上跑（VM 间 RTT 100–120µs）。

## 批判性分析

### 论证链条

论文链条较闭合：measurement 证明 CC 是瓶颈（即使 RDMA 优化）→ 单副本 lease + affinity 提升 cache 有效命中 → TPG 预序列化消除执行期 lock/validation → 端到端 benchmark 与 RDMA 公平 CC 对比验证收益。核心贡献是把「事务并发控制」从 datastore-centric lock/OCC 重构为 **compute-layer lease + dependency scheduling**，这与 FaRM/DrTM 等 monolithic RDMA transaction 系统的问题设定不同，更贴近 disaggregated FaaS。

需留意的跳步：端到端对比 Boki/Beldi 时，RTSFaaS 跑在专用 RDMA 集群（7µs RTT），baseline 跑在 AWS VM（100–120µs RTT），网络与部署条件并不对等。论文用 Section 5.3 的 RDMA 环境 CC 协议对比部分弥补了这一 gap，但「5×/20×」的 headline number 应视为 **不同部署栈下的系统级对比**，而非纯算法优势。

### 假设压力测试

**workload assumption**：benchmark 来自 DeathStarBench 风格 microservice（movie review、travel reservation、banking），transaction 长度较短，且函数已被分解为单 key 访问。真实 FaaS workflow 可能含多 key 函数、非确定性分支、长 DAG；decomposition 与 early read 成本可能被低估。

**resource bottleneck assumption**：默认瓶颈是跨节点 CC 通信与 cache 一致性协调，而非 function 计算本身或 TiKV write-back。若 function 逻辑很重或 write-back 成为主导，lease 机制的收益会下降。

**hardware/deployment assumption**：强依赖 RDMA one-sided 访问 worker 间注册的 cache memory。Serverless 公有云（Lambda、Azure Durable Functions）通常无此能力；结论主要适用于 **自建 RDMA 数据中心内的 stateful FaaS**。

**scaling assumption**：affinity 统计表随运行时间累积，在 access pattern 稳定时有效；突发 drift 或 multi-tenant 干扰可能导致 lease 归属滞后，需若干 batch 才能重新收敛。热点 key 上 single leaseholder 模型的扩展性未在大规模集群上验证。

**correctness/SLO assumption**：论文证明了 conflict-serializability（基于 TPG），并处理业务 abort；但未深入讨论 partial failure 下 lease flag 与 cache 的一致性边界、跨 batch 交互、或可线性化的 client 语义。固定 500ms batch 对 tail latency SLO 不友好，论文有测量但未给出 adaptive batch 策略。

### 实验可信度

**强项**：开源实现；三类代表性 workload；除完整系统对比外还有 RDMA 环境下的 CC 协议隔离实验（Section 5.3）；ablation 覆盖 skew、read-only 比例、workflow 长度、batch size、execution breakdown。

**弱项**：Boki/Beldi 端到端对比的硬件/网络不对等；baseline 节点数（8 workers）与 RTSFaaS（4 workers）不完全一致，虽作者尝试匹配 CPU/内存；未与 Apiary、Styx、Calvin 类方案对比；microbenchmark 与 end-to-end 的 worker 配置（20 core vs 8 core）不一致。

### 系统性缺陷

- **尾延迟**：batch 等待 + TPG 构造使 p99 随负载和 batch size 恶化；论文未提供 adaptive punctuation 或优先级 batch。
- **热点与扩展性**：单 leaseholder per key 在极端热点下可能成为串行化瓶颈；论文提出 replica 扩展方向但未实现。
- **Dependent read**：需 early read 和向所有 worker 广播元数据，通信成本可观；论文承认是非确定性函数的固有难点。
- **运维与可观测性**：lease 转移、TPG 构造、batch 边界切换的状态对调试者不透明；论文未讨论 tracing/metrics 接口。
- **故障恢复**：batch 级重放简单但粗粒度；Docker 重启 20s 级开销表明生产环境仍需 MITOSIS 类 RDMA 冷启动优化。TiKV write-back 与 snapshot 之间的窗口行为论文仅简略描述。

## 局限与后续工作

- **局限 1（论文自述）**：dependent read 使完整 read/write set 难以预先获知，early read + 悲观全局广播增加通信开销。
- **局限 2（论文自述）**：单 leaseholder 模型在热点 key 高并发下可能成为瓶颈；需 replicated-state（primary + read-only replica）扩展。
- **局限 3（实验边界）**：batch 处理引入最低 ~500ms 延迟 floor，不适合延迟敏感型在线事务；需测量 adaptive batch interval 对吞吐-延迟 Pareto 的影响。
- **局限 4**：函数单 key 分解约束简化了 TPG 构造，但增加了 programming/runtime 负担；需评估 decomposition 对真实 workflow 语义与性能的影响。
- **Future work 1**：在 Zipf hotspot（θ→1）与 tenant 混合漂移 trace 下，测量 lease 重分配收敛速度、跨节点 RDMA 流量与 p99 延迟。
- **Future work 2**：实现 primary/replica lease 扩展，对比单 leaseholder 在高 read 比例下的吞吐与一致性代价。
- **Future work 3**：与 [[BurstComputing-ATC25|BurstComputing]]、[[AFaaS-OSDI25|AFaaS]] 等 FaaS 调度/冷启动优化结合，评估 RDMA lease 机制在弹性扩缩容时的 lease 表重建成本。

## 相关

- **相关概念**：[[RDMA]]、[[Serverless]]、[[FaaS]]、[[Disaggregation]]、[[Concurrency-Control]]、[[2PL]]、[[OCC]]
- **同类系统**：[[Boki]]、[[Beldi]]、T-Statefun、Apiary、Styx、rFaaS、MITOSIS、RMMAP、FaRM、Calvin
- **同会议**：[[ATC-2025]]
- **对比**：RTSFaaS 代表「compute-layer lease + TPG」路线；Boki 代表 log-based OCC；Beldi 代表 remote 2PL——三者一致性均为 serializable，但 CC 所在层与通信模式根本不同。
