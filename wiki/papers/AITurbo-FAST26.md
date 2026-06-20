---
type: paper
name: AITurbo
full_title: "Fast Cloud Storage for AI Jobs via Grouped I/O API with Transparent Read/Write Optimizations"
authors: [Yingyi Hao, Ting Yao, Xingda Wei, Dingyan Zhang, Tianle Sun, et al.]
venue: FAST
year: 2026
tags: [cloud-storage, ai-infra, checkpoint, kv-cache, rdma, disaggregated-storage]
source_pdf: "[[fast2026-hao.pdf]]"
source_md: "[[fast2026-hao]]"
---

# Fast Cloud Storage for AI Jobs via Grouped I/O API with Transparent Read/Write Optimizations (FAST 2026)

> **一句话总结**：观察到 disaggregated 云存储的 frontend S-NIC 带宽与买 backend 带宽的 16× 成本曲线是 AI bulk I/O 的主瓶颈，而 AI 集群 host DRAM 与 [[Compute-Fabric]] 在训练/推理时常空闲，AITurbo 用 grouped read/write API 让存储层透明做 deduplication + load-balanced I/O 规划，checkpoint 写比 SFSTurbo 快 3.9–58.8×、比 Gemini 快 5.9×，KVCache 读比 [[Mooncake]] 快 1.28×，仅需数百行应用改动且已在 HUAWEI 云生产部署。

## 问题与动机

大模型训练与推理已改变云存储带宽画像：在 HUAWEI 云某本地数据中心，AI job 已占存储带宽 **>10%**。三类高带宽场景尤为突出：

- **Checkpoint write**：周期性把 model parameters + optimizer states 写入 [[Disaggregated-Storage]]，单次可达数百 GB。
- **Checkpoint read**：推理 autoscaling 或训练恢复时需快速加载 checkpoint；AzureConv trace 显示 burst 时 job 数可从 1 扩到 3，所有新 job 需 grouped 读同一 checkpoint。
- **[[KV-Cache]] read**：HBM/DRAM 不够时从存储拉预计算 KV；agent workload 中同 task category 共享 system prompt，产生 batched 重复读。

这些 I/O 的共同特征是 **bulk + asynchronous + grouped**：文件多为 GB 级顺序读写，可与 forward/backward 计算重叠，但多个 XPU 同时参与同一逻辑 I/O batch。

现有方案有两条难路：

1. **加存储带宽很贵且 frontend 有硬顶**：backend 从 1.6 → 80 GBps 单 GB 价格涨 **16×**；compute node 的 S-NIC 聚合带宽（如 100 Gbps）与 compute fabric（如 200 Gbps/XPU [[RDMA]]）分离，只加 backend 无法突破 frontend 瓶颈。
2. **应用层优化复杂且难覆盖全 workload**：[[Megatron]] 约 **1/4 codebase** 在做 checkpoint 优化仍因不了解 disaggregated 架构而次优；[[OpenSora]] 等多模态框架几乎无 checkpoint 优化。[[ZeRO]] 1/2/3 + DP 组合使 deduplication 模式多变（Table 1），应用难穷举；即便知道去重，如何 load-balance 写满所有链路也非平凡。

论文提出 **AITurbo**：在现有云存储之上，用极少应用改动（通常数百行 LoC）透明获得可比或优于重度框架优化的 I/O 性能。

## 关键观察 / 隐含假设

- **观察 1**：AI 集群的 **host DRAM 与 compute fabric 在训练/推理时常 underutilized**，可作高速 staging buffer 弥补 storage fabric 不足，且 checkpoint 等写可接受「DRAM 可见即可继续、持久化异步」的 durability trade-off。
  - **依赖假设**：job 独占一组 XPU（无同机 co-located 推理/训练混部）；host DRAM 容量足以 stage 单次 grouped I/O（checkpoint 场景仅需 hold 去重后 payload）；应用可容忍 `future_1` 未 ready 前数据丢失（靠 replication 或周期性 checkpoint 恢复）。
  - **可能失效场景**：推荐 serving 等 DRAM 已满 workload；多 job 共享 compute fabric 且 RoCE QoS 隔离不足时，借道 fabric 可能拖慢训练 collective；要求强 durability 的写必须等 `future_1` 则 staging 收益下降。

- **观察 2**：AI job 的 grouped I/O 语义可被 **极简 API 扩展**（`group_getfile` / `group_putfile` + group id）完整捕获，存储层比应用更了解 disaggregated 拓扑，因而能透明推导 deduplication 与 load-balanced plan，优于应用各自优化。
  - **依赖假设**：应用能显式声明 group（训练=全部进程，autoscaling=同时启动的 inference jobs）；group 内 I/O pattern 在 job 生命周期内相对稳定（支持 plan/checksum metadata 缓存）；bulk I/O 使 metadata 开销可忽略（SFSTurbo 1 MB 读 0.2–1 ms）。
  - **可能失效场景**：推理实例难以同步使用 group API（论文 Mooncake 集成未用 group API 仍有效但可能未达上限）；小文件/随机 I/O；跨 job 的 I/O pattern 剧烈变化导致 plan 缓存失效。

- **观察 3**：Grouped write 中存在 **可预测的跨 XPU 重复 payload**（DP>1 时 parameter 必重复；agent KVCache 共享 prefix），checksum 去重 + compute-fabric broadcast 读可把有效 storage 带宽放大到接近 fabric 上限。
  - **依赖假设**：BLAKE3 chunk checksum 碰撞可忽略；训练前几轮 optimizer state 全零会导致假去重，需若干 iteration 后 pattern 稳定；读侧 deduplication 常可离线或用文件名判定。
  - **可能失效场景**：ZeRO-3 等高度 shard 配置重复度低；KVCache 无共享 prefix 的 workload；checksum 粒度与 tensor 边界不对齐时去重率下降。

- **假设 1**：最小化 storage overhead ≈ 最小化 $I/O\_payload / \min(frontend, backend)$ 带宽，可忽略 metadata 与 seek。
  - **证据强度**：**中**——与 Figure 3 bulk RDMA 测量一致，但未在 metadata-heavy 或小 I/O 场景验证。

## 核心方法

AITurbo 在现有云存储上新增三个组件（Figure 8）：**job controller**（控制面规划）、**staging buffer manager**（跨节点闲置 DRAM）、**communicator**（compute fabric 传输）。

### Grouped API 与异步语义

在 `getfile`/`putfile` 之上增加 **group** 参数，告知存储「一批 client 协同读写」。写路径提供两个 future：

- `future_0`：数据已进 host DRAM staging buffer，XPU 可进入下一训练 iteration。
- `future_1`：数据已 durable 写入 backend；此前失败则标记文件 broken，由应用处理。多节点 DRAM 复制（类似 Gemini）降低丢失概率。

### Grouped write 三阶段（§4.1）

1. **Deduplication**：各 XPU 用 [[BLAKE3]] kernel 算 chunk checksum（V100: **7.8 ms/GB** vs CPU **35.6 ms/GB**），上报 job controller；controller 识别重复并生成 plan。去重 metadata 在 job 生命周期内缓存，用户 hint 可跳过后续 checksum。
2. **Load-balanced staging**：将去重后 payload 写入各节点 DRAM，形式化为 **bilinear programming**（最小化端到端时间 $t$，约束 source/destination 带宽、链路带宽、buffer 容量）；用 branch-and-bound 固定 $t$ 解 LF 子问题。64 XPU、38B trace 上单线程 Python solver **~4 s**；首轮 plan 可缓存复用。
3. **Persist**（可选）：从 DRAM 异步刷到 storage server；仅需 fault tolerance 不需 debug 时可跳过。

OpenSora rank-0 单点写示例（Figure 10）：dup factor=2 时耗时翻倍，因 S0 outbound 成瓶颈；AITurbo plan 并行利用 D0/D1。

### Grouped read 两阶段（§4.2）

1. 从 storage 各 chunk **只拉一份**到 staging node（plan 与 write 对称）。
2. 经 compute fabric **broadcast** 到所有需要该 chunk 的 XPU（沿用 [[BlitzScale]] 串行转发链，对大 bulk 近最优）。两阶段 pipeline；group read 还支持 **distributed cache**——若 peer 节点已有数据则走 fabric  bypass storage。

### 系统机制（§4.3）

- **Tensor-native file type**：metadata 与 data 分离，避免 XPU↔CPU↔storage 序列化开销（对齐 [[Megatron]] DCP / PyTorch DCP 思路）。
- **Communicator**：不用 [[NCCL]] group init（Megatron 上可达数分钟），改为按需建立 **P2P RDMA QP**（~15 ms，可与 storage init overlap）。
- **隔离**：RoCE QoS 将 AITurbo QP 设为最低优先级 best-effort；同 XPU co-located job 的精细隔离留作 future work。
- **Controller 容错**：stateless，plan/cache 可重算或持久化，多副本即可。

## 设计取舍

- **取舍 1：透明存储层优化 vs 框架深度集成**。AITurbo 把 in-memory checkpointing、dedup、broadcast 下沉到存储，Megatron 仅需 **286 LoC**（原 checkpoint 相关 **2228 LoC**），但要求应用改用 grouped API 并声明 group。收益是跨框架复用与全局拓扑感知；代价是 storage provider 需维护 controller/planner 复杂度。
- **取舍 2：DRAM staging 的 durability**。`future_0` 先行使训练不被慢 storage 阻塞，与 Gemini 类似接受非持久窗口。收益是数量级 checkpoint 加速；代价是全副本丢失时需应用回滚到上一 checkpoint。
- **取舍 3：分阶段 bilinear plan vs 联合优化**。write 的 staging 与 persist 分开求解，未做 scatter-then-gather 联合 plan（作者认为 checkpoint 场景 DRAM write 已够）。收益是实现可落地；代价是极端拓扑下可能未用尽所有 S-NIC 并行度。
- **取舍 4：compute fabric 借道 vs 训练 collective 干扰**。硬件 QoS best-effort 而非软件限速（Gemini 有 profile-based 方案）。收益是部署简单；代价是 fabric 满载时 I/O 与 allreduce 可能争抢——论文称生产 case 未观察到问题。
- **边界条件**：仅加速 **bulk transfer**；小 I/O、高度 unique 的 checkpoint（ZeRO-3）、无法声明 group 的在线 inference 收益有限；frontend 非瓶颈且 backend 极快时优势收窄。

## 实验与结果

**Testbed**：最多 64 XPU（Ascend 910B / NVIDIA A800），每 node 8 XPU、192 CPU cores、1.5 TB DRAM；compute fabric 200 Gbps intra-node，S-NIC 100 Gbps/node，backend 最高 30 GBps。

- **Checkpoint write（6 种 TP/PP/ZeRO 配置，1.5B/13B/38B）**：AITurbo 与 Gemini 均大幅快于 Megatron+SFSTurbo（最高 **58.8×**）；有重复写时 AITurbo 比 Gemini 最高 **5.9×**（Gemini 默认无 dedup/write plan）。Factor analysis：+Buffer 最大贡献；+Dedup 在 DP 场景再降 4.3–47.2%；+Write plan 最高再降 **76%**。
- **Wasted XPU time**（最优 checkpoint 频率，failure rate 1 XPU/h）：AITurbo 比 SFSTurbo 最多减少 **6%** wasted XPU hours（绝对值小但长训成本显著）。
- **Checkpoint read（Qwen 72B / QwQ 32B，1–30 GBps）**：缓存命中时 Qwen 72B 部署到 64 XPU 仅 **2.25 s**；冷读仍受 storage 限制（135 GB @ 1 GBps ≈ 173 s）。热数据后 compute-fabric broadcast 使 load time 近乎与 XPU 数无关——ServerlessLLM 经 SFSTurbo 分发同场景需 **1384 s**。
- **KVCache read（Qwen-14B，8 XPU，Qwen-Bailian trace 30 min）**：Mooncake+AITurbo TTFT 比 Mooncake+SFSTurbo 降 **23%**；storage miss 时借 fabric 提升有效 KV 读带宽，Mooncake+AITurbo 比纯 Mooncake 最高 **1.28×**。
- **工程开销**：Megatron +286 LoC vs 原 2228 LoC；Mooncake 改 **44 LoC**（未用 group API）。64 XPU grouped write 的 controller 协调开销最大 **45 ms**，相对 I/O 可忽略。
- **生产部署**：已用于 HUAWEI 云训练 checkpoint；推理扩展进行中。

## Critical Analysis

### 论证链条

观察链较完整：HUAWEI 测量（AI 带宽占比、文件 size 分布、frontend/backend 定价）→ bulk grouped I/O 特征 → 两条 insight（闲置 DRAM+fabric、grouped API）→ 写/读 planner → 多 workload 对比 SOTA。弱环节在于 **把「DRAM 常空闲」推广到所有 AI 集群**：论文用推荐 serving vs 训练 contrast 说明，但缺少多租户混部下的系统测量；论证依赖「job 独占 XPU 组」这一部署假设。

设计到结果的映射清晰：factor analysis 分解 Buffer/Dedup/Write plan 贡献，与 OpenSora rank-0 瓶颈案例互证。读路径上「先 storage 单副本再 fabric broadcast」解释了对 ServerlessLLM 的数量级优势，逻辑闭合。

### 假设压力测试

- **Workload 变化**：ZeRO-3、纯 TP 无 DP 时 dedup 收益下降（实验覆盖但优势收窄）；agent KVCache 无共享 prefix 时 grouped read 退化为普通并行读——论文未量化。
- **硬件/规模**：实验上限 64 XPU、30 GBps backend；更大规模下 bilinear plan 求解（4 s）与 controller 单点是否成瓶颈未测；Ascend/NPU 与 GPU 结论是否一致仅部分验证。
- **部署方式**：Mooncake 未用 group API 仍有收益，说明部分优化可在 API 子集工作，但也暗示 **group 语义对 inference 在线同步困难**，生产 inference 扩展可能打折扣。
- **已证明 vs 推断**：checkpoint 数字有充分 baseline；「16× 成本」来自 HUAWEI 定价曲线——外推到 AWS/GCP 需重新测量。

### 实验可信度

- **Benchmark 代表性**：训练用 Megatron 多规模+ZeRO 矩阵较好；推理用真实 AzureConv、Qwen-Bailian trace 加分。缺 long-running multi-tenant 生产 trace。
- **Baseline 强度**：SFSTurbo（类 [[3FS]]）、自实现 Gemini 技巧、ServerlessLLM、Mooncake 均为合理 SOTA；Gemini 为 reimplementation 而非原版，可能略弱/略强于真实 Gemini。
- **Ablation**：Figure 14/15 factor analysis 支持设计分解；dedup profile（Figure 19）与框架级一致，验证透明 dedup 正确性。
- **Metric**：checkpoint time、wasted XPU hours、TTFT、KV 读吞吐覆盖吞吐与延迟；**未报告** persistence 路径 tail latency、fabric 干扰下训练 step time、failure recovery 端到端时间。

### 系统性缺陷

- **尾延迟与隔离**：仅 RoCE 最低优先级 QoS；同 XPU co-located、fabric 突发占用时的训练 P99 影响 **论文未讨论**。
- **正确性与一致性**：checksum 去重无二次内容比对；BLAKE3 碰撞概率极低但非零。`future_0`/`future_1` 语义下 broken file 检测依赖 flag，跨 controller 故障的 exactly-once 语义未形式化。
- **可观测性与运维**：job controller、staging buffer 全局状态的可观测性、plan 错误时的 debug 路径论文未展开。
- **兼容性**：依赖 tensor-native 文件与 grouped API 改造；legacy checkpoint 格式需适配层。
- **成本模型**：节省 backend 带宽不等于零成本——占用大量 host DRAM 与 fabric 的机会成本在计费模型中如何体现未分析。

## 局限与 Future Work

- **局限 1**（论文明确）：聚焦 **bulk transfer**，小 I/O 不受益；fabric 隔离仅用硬件 QoS，同 XPU 多 job co-location 的精细隔离未做。
- **局限 2**（实验边界）：写 plan 分阶段求解，未探索联合 scatter-gather；推理 group API 同步困难导致部分场景未用满 API 能力。
- **局限 3**（部署）：生产目前以训练 checkpoint 为主，推理 KVCache/autoscaling 仍在扩展；跨云 vendor 存储后端异构性未验证。
- **Future work 1**：在混部集群上 **测量** compute fabric 借道对训练 collective P99 的影响，并对比软件 profile-based 限速（如 Gemini）与硬件 QoS 的 trade-off。
- **Future work 2**：对 **无 group 声明** 的 inference 路径做自动 group 推断或 storage-side trace 预测，量化 Mooncake 场景还能挖多少潜力。
- **Future work 3**：联合 staging+persist 的 I/O plan 与更大规模（>64 XPU）plan 求解 latency 的 scalability 研究。

## 相关

- **相关概念**：[[Checkpoint]]、[[KV-Cache]]、[[RDMA]]、[[Compute-Fabric]]、[[Disaggregated-Storage]]、[[Deduplication]]、[[ZeRO]]、[[Tensor-Parallelism]]
- **同类系统**：Gemini、[[Mooncake]]、[[Megatron]]、[[3FS]]、[[BlitzScale]]、[[ServerlessLLM]]、[[ByteCheckpoint]]、SFSTurbo、[[OpenSora]]
- **同会议**：[[FAST-2026]]
- **对比**：框架级 checkpoint 优化（Megatron/Gemini/ByteCheckpoint）vs 存储层透明优化（AITurbo）；KVCache-centric serving（Mooncake）vs storage+fabric 协同（AITurbo）