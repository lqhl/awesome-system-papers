---
type: paper
name: Toppings
full_title: "Toppings: CPU-Assisted, Rank-Aware Adapter Serving for LLM Inference"
authors: [Suyi Li, Hanfeng Lu, Tianyuan Wu, Minchen Yu, Qizhen Weng, Xusheng Chen, Yizhou Shan, Binhang Yuan, Wei Wang]
venue: ATC
year: 2025
tags: [llm-serving, lora, cpu-offload, multi-tenant, scheduling]
source_pdf: "[[atc2025-li-suyi-toppings.pdf]]"
source_md: "[[atc2025-li-suyi-toppings]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Toppings: CPU-Assisted, Rank-Aware Adapter Serving for LLM Inference (ATC 2025)

> **一句话总结**：观察到 [[Continuous-Batching]] 下按需 GPU load [[LoRA]] adapter 会累积打断 inflight decoding（RPS=9 时占服务时间 29%），而 LoRA 计算仅 ~1 GFLOPs 且集群 CPU 大量闲置；Toppings 用 CPU 并行 prefill 掩盖 loading 冷启动，并以 rank-aware 调度避免异构 batch 拖慢 decoding，相对 S-LoRA/dLoRA 平均延迟降 1.7×、SLO 满足率 99%、距理想全-cache baseline 仅 7% 开销。

## 问题与动机

多租户 [[LoRA]] serving 的主流范式是：base LLM pin 在 GPU，成百上千个 adapter 放在 host memory，按需 load 到 GPU 后与 base model 做 on-the-fly 的 xAB 计算并 batch 在一起（Punica、S-LoRA）。这在 [[Continuous-Batching]] 下能复用单份 base model 提升吞吐，但论文指出两个被现有系统低估的根本瓶颈。

第一，**adapter loading 不是一次性开销，而是累积的 decoding-interruption 税**。新请求到达时，系统必须暂停当前 batch 的 decoding，先完成 load + prefill，再恢复 decoding。在 Poisson 到达、512 个 adapter、rank=64 的设置下，RPS=3/6/9 时单请求 decoding 被打断的中位数分别为 4/10/25 次，累积 interruption 占整次服务时间的 13%/22%/29%。rank=64 单 adapter 约 100MiB（≈ 200 token 的 [[KV-Cache]]），load 可达数十 ms，往往超过 90% 真实 prompt 的 prefill 时间。

第二，**集群调度 rank-agnostic 会在异构 LoRA batch 上系统性违反 SLO**。BGMV（Punica）按 batch 内最大 rank padding，MBGMV（S-LoRA）按 rank 之和计费；同 batch size 下 rank 组合不同可导致 decoding latency 相差 28%。现有 Punica、S-LoRA、dLoRA 的集群调度都不建模这一异构性。

全量预 cache LoRA 到 GPU 虽能消除 loading，但 production trace 显示 50% 命中率需缓存 200+ adapter（Llama2-7B 上 >20GiB），挤占 [[KV-Cache]] 空间、降低吞吐，且 dLoRA 在 512 adapter 时直接 GPU OOM。dLoRA 的 dynamic merge/unmerge 则把 loading 换成计算税：TPT 比理想 baseline 高 29%–86%。Toppings 的目标是在不预 cache 全部 adapter 的前提下，把 loading 对 inflight 请求的损害压到接近 CACHED 理想上界。

## 关键观察 / 隐含假设

- **观察 1**：在 [[Continuous-Batching]] + on-demand loading 下，decoding-interruption 是主导延迟来源，且随 RPS 和 adapter 数量超线性累积。
  - **依赖假设**：请求到达服从 Poisson/长尾分布；adapter 不在 GPU 上 cache 或 cache hit 率较低；每个新请求大概率触发 load+prefill 抢占。
  - **可能失效场景**：高 cache hit（热门 adapter 常驻 GPU）、极低 RPS、或采用不抢占 decoding 的调度策略时，CPU-assisted 的收益大幅缩水。

- **观察 2**：LoRA 的 xAB 计算量级约 1 GFLOPs/层，远小于 base LLM 的 xW；Llama2-7B prefill 每层触发 32 次 LoRA invocation，原生 IPC/sync 开销可使延迟涨 79.4%，但计算本身 CPU 可扛。
  - **依赖假设**：LoRA 仅作用于 attention 投影矩阵（WQ/WK/WV）；rank 在 8–256 范围；prompt 长度以 LMSYS 分布为主（绝大多数 <1k token）。
  - **可能失效场景**：极长 prompt（2k–30k token，QMSum 场景）时单核 CPU 成为新瓶颈，需依赖多 CPU 并行；rank 极大或 LoRA 扩展到 MLP 层时 GFLOPs 假设不再成立。

- **观察 3**：LLM 集群 CPU 利用率极低（75% 节点 <10% GPU 利用率 99%），为 CPU-assisted prefill 提供「免费」算力而不与 GPU 争资源。
  - **依赖假设**：每台 inference server 有足够物理核（论文用 Intel Platinum 8369B，LoRA 进程绑核）；CPU 不被其他 co-located 服务占满。
  - **可能失效场景**：CPU 被 embedding、数据预处理、或 [[Disaggregation]] 的 prefill worker 占满时，Toppings 的 46% CPU 利用率可能与其他服务冲突。

- **观察 4**：异构 LoRA batch 的 decoding latency 可由简单线性模型准确预测——BGMV：latency ∝ |S| × max(rank)；MBGMV：latency ∝ Σ rank；R²=0.96。
  - **依赖假设**：kernel 性能受 GPU memory bandwidth 主导（adapter weight 进 L2）；batch size ≤64、rank 种类有限；硬件与 base model 固定后 α/β 只需分钟级 reprofile。
  - **可能失效场景**：新 GPU 代际、新 kernel 实现、或 batch 内 adapter 数量/分布超出 profile 空间时，线性模型可能失准。

- **假设 1**：layer-wise CPU-GPU 同步 + shared memory IPC 可将 per-layer invocation 开销压到 <1ms，不抵消 CPU prefill 收益。
  - **证据强度**：**强**——microbenchmark 显示 domain socket 随 receiver 数线性增长，shared memory 近常数；sync-free fused kernel 比 native PyTorch 快 10%–15%。

- **假设 2**：pipelined adapter loading（按 layer group 重叠 CPU compute 与 GPU load）在 rank≥64 时有效，且 load 未完成时动态选择 CPU/GPU 执行路径可保持鲁棒性。
  - **证据强度**：**中**——rank=128/64 时 prefill 加速 1.2×/1.1×；CPU 资源减 4× 时仍靠 pipeline 保持优势，但极端 load/compute 抖动下的切换策略论文未充分 ablate。

## 核心方法

Toppings 在 LightLLM 上实现，架构分三层：集群 rank-aware scheduler、全局 LoRA registry（SQLite）、以及 per-server 的 CPU-assisted inference。

**CPU-assisted LoRA serving** 回应观察 1 和 2。新请求到达且 adapter 不在 GPU 时，不再让 inflight decoding 空等 load 完成；而是立即用已在 host memory 的权重在 CPU 上启动 prefill 的 xAB 计算，同时 GPU 后台 pipelined load adapter（按 layer group 切分，profile 对齐 CPU compute 与 PCIe transfer 时间）。load 完成的层切到 GPU BGMV kernel 继续；未完成的层留在 CPU。这直接针对 [[Continuous-Batching]] 的抢占问题：prefill 不再阻塞在 load 上，inflight decoding 恢复更快。

协调 CPU/GPU 的三项系统优化回应假设 1：（1）**sync-free fused CUDA operator**——把 async MemCpy 与 host semaphore signaling 融合进单 kernel，避免 PyTorch 显式 `cudaSynchronize` 阻塞后续 base model kernel launch；（2）**shared memory IPC**——base LLM process 与多个隔离 CPU LoRA process 通过 DRAM shared memory + semaphore polling 交换 x 和 xAB，消除拷贝/序列化；（3）**profiling-guided 多 CPU 并行**——按 token 数切分 x，每核一个绑核进程，比 PyTorch multithreading 在 16 核下快 1.4×。GPU 侧沿用 Punica 的 BGMV，与 [[vLLM]]/LightLLM 的 [[PagedAttention]] 式内存管理兼容；支持 [[Tensor-Parallelism]] 下按 base model 同样策略切分 LoRA 权重 B。

**Rank-aware scheduling** 回应观察 4。scheduler 维护 per-server 的 running batch 与 queue 状态，对新请求在所有持有该 adapter 的 candidate server 上计算 cost：`Δprefill/avg_resp_len + Δdecode`，若加入后 decoding 超 SLO 则加无穷 penalty；最终选 `cost × (running+queued)` 最小的 server。性能模型只需一次轻量 profile（7618 条请求、batch 4/8/16/32、rank 8/16/32/64），推理开销 0.001ms。这与 Punica 的 FIRSTFIT、dLoRA 的 reactive migration、RANDOM 等 rank-agnostic 策略形成对比。

## 设计取舍

- **取舍 1：CPU-assisted prefill vs 纯 GPU load+prefill vs 全量 GPU cache**
  - 收益：相对 S-LoRA 在 512 adapter MAF trace 上 TPT/E2E 加速 1.28×–1.29×；相对 CACHED 理想仅 +7% 开销（S3 合成负载）。
  - 代价：CPU 利用率从 4% 升到 46%，每请求平均 27ms CPU LoRA 计算；实现复杂度显著（自定义 CUDA op、多进程 IPC、pipeline loading）。
  - **边界条件**：adapter 数少、RPS 低时收益接近 CACHED，CPU-assisted 的固定工程成本可能不值；全 cache 在 adapter 规模小时更简单。

- **取舍 2：decoding 仍被 prefill 抢占 vs strawman 异步 load 不中断 decoding**
  - strawman 不中断 decoding 但让新请求 TTFT 涨最高 4×、TPT 涨 1.4×；Toppings 选择缩短 prefill 窗口而非消除抢占，优先保护 inflight 请求的 TPT。
  - **边界条件**：TTFT 敏感型 workload（聊天首 token）仍可能受损；论文用 CPU early-start 缓解但未量化 TTFT P99。

- **取舍 3：隔离 CPU LoRA 进程 vs in-process 多线程**
  - 进程隔离带来 fault tolerance 和绑核确定性，但引入 layer-wise sync 需求；shared memory 将 IPC 压到 <1ms 后净收益为正。
  - **边界条件**：进程数随并行度增长，OS 调度与 NUMA 效应论文仅在单节点验证。

- **取舍 4：rank-aware 调度 vs 简单负载均衡**
  - 8 节点 testbed RPS=40/50 时 SLO attainment 比 dLoRA 高 21%/26%；60 节点仿真 avg TPT 比 FIRSTFIT 快 57%。
  - 代价：scheduler 需实时 batch 状态、依赖 kernel-specific 性能模型；换 MBGMV 需重建模型；未显式处理 fairness（可与 VTC 等正交叠加）。

- **边界条件**：BGMV 在 batch 内存在大 rank adapter 时小 rank 请求被 padding 拖累——调度器缓解集群级问题但不改变单 batch kernel 效率上限；dLoRA 的 merge/unmerge 路径在 adapter 多时 OOM，Toppings 明确不走此路。

## 实验与结果

- **vs S-LoRA / dLoRA（Llama2-7B/70B）**：平均请求服务延迟最高降 **1.7×**；S3（rank=64, RPS=9, 200 adapter）相对 CACHED 理想 TTFT/TPT/E2E 仅 +6%/+6%/+7%，S-LoRA 则 +82%/+80%/+81%。
- **vs CACHED 理想 baseline**：全 GPU cache、零 loading——不可扩展但作上界；Toppings 平均仅 **7%** 额外开销；512 adapter MAF trace 上加速 S-LoRA 1.25×–1.29×。
- **长 prompt**：QMSum 2k–30k token、rank=256（S4）优势保持；dLoRA 慢 LoRA GEMM 问题更突出。
- **Llama2-70B TP=4**（S5/S6）：S6 上相对 S-LoRA TTFT/TPT/E2E 加速 1.6×/1.5×/1.4×；dLoRA S6 GPU OOM。
- **Rank-aware 调度**：8 节点 testbed SLO attainment 最高 **99%**；60 节点 MAF 仿真 avg TPT 比 dLoRA/RANDOM/FIRSTFIT 快 22%/23%/57%。
- **Microbenchmark**：sync-free kernel prefill -10%–15%；pipelined loading rank=128/64 加速 1.2×/1.1×；shared memory IPC <1ms；16 CPU 并行 1.4× vs PyTorch threading。
- **资源**：S3 下 GPU 利用率 S-LoRA/dLoRA/Toppings = 46%/81%/56%；CPU = 4%/4%/46%。

## Critical Analysis

### 论证链条

论文的 observation → design → result 链条在 **单节点 loading 问题** 上闭合较好：Fig. 4 量化 interruption 比例 → CPU-assisted + pipeline 直接缩短 prefill 窗口 → Fig. 13/14 显示接近 CACHED。薄弱环节在于把 **7% vs CACHED 的差距** 外推为「生产可部署」：CACHED 在 512 adapter 时不可行，但部分热点 cache（论文自己也说 50% hit 需 200 adapter）的混合策略未被 baseline 化。

Rank-aware 调度链条也较完整：Fig. 5/6 展示异构 batch 的 latency 差异 → 线性模型 R²=0.96 → testbed + 60 节点仿真 SLO 99%。但仿真复用 LightLLM 逻辑、latency 来自 profile 而非在线 serving，高负载下模型漂移、queueing 非线性未验证。

未覆盖的跳步：**TTFT vs TPT 的 Pareto 权衡**——Toppings 仍抢占 decoding，只缩短抢占窗口；对首 token 延迟敏感场景是否最优未与 chunked prefill / prefill-decode disaggregation 对比。

### 假设压力测试

- **Workload 变化**：MAF/serverless trace 长尾 adapter 分布是核心 motivator；若 tenant 集中在少量热门 LoRA（高 GPU cache hit），CPU-assisted 收益可能降至个位数百分比——论文在 128 adapter 低 RPS 时已显示「impact negligible」。
- **硬件变化**：profile 导向的 pipeline group 大小和 α/β 参数绑定 A100 + PCIe 带宽；HBM 更大、PCIe Gen5、或 CXL 扩展内存改变 load/compute 平衡点时需重调。
- **规模外推**：60 节点仿真 RPS≈340、40000 function；scheduler 全局状态收集、SQLite registry 延迟、跨 AZ 路由开销论文未讨论。
- **模型演进**：仅 attention 投影 LoRA；若扩展到 full-layer 或 MoE adapter，1 GFLOPs 假设失效。
- **已证明 vs 推断**：interruption 占 29% 是实测；「CPU 不影响集群其他服务」主要基于他人 cluster characterization [23]，非 Toppings 负载下的 co-tenancy 实验——**推断** 在 CPU 紧张环境可能不成立。

### 实验可信度

- **Benchmark 代表性**：LMSYS-CHAT-1M + MAF trace + QMSum 长 prompt 覆盖较广；合成负载 S1–S3 每请求 distinct adapter（最坏 loading 情况），可能高估相对生产 hit-rate 场景的增益。
- **Baseline 公平性**：CACHED/Toppings/S-LoRA 同基于 LightLLM + BGMV，dLoRA 基于 vLLM——作者承认 backend 差异，70B 上对 S-LoRA/dLoRA 做了 reimplement；但 dLoRA 的 OOM 使其在大 adapter 数场景缺席，对比略不对称。
- **Ablation**：§7.3 对 sync-free、shared memory、pipeline、multi-CPU 有 microbenchmark；缺「去掉 rank-aware 调度仅保留 CPU-assisted」的端到端分解。
- **Metric 覆盖**：TTFT/TPT/E2E + SLO attainment 齐全；**尾延迟 P99/P999、公平性、故障恢复** 论文未报。

### 系统性缺陷

- **尾延迟与隔离**：CPU LoRA 进程绑核，但多请求并发时 shared memory 竞争、semaphore polling 的 tail 行为未测量。
- **故障恢复**：提到 redundant CPU process 可增强容错，但无 failover 实验；CPU process crash 对 inflight GPU batch 的影响论文未讨论。
- **可观测性 / 运维**：多进程 + 自定义 CUDA op + pipeline 切换增加 debug 难度；论文未讨论。
- **兼容性**：声称可移植到 [[vLLM]] 等框架，但实现仅在 LightLLM；与 [[Chunked-Prefill]]、[[Disaggregation]]、[[Speculative-Decoding]] 的组合论文只说「compatible」无实验。
- **公平性**：rank-aware 目标是最小化 SLO violation，高 rank 请求可能被路由到已负载 instance；未与 VTC 等 fairness 机制集成验证。

## 局限与 Future Work

- **局限 1**：仍依赖 [[Continuous-Batching]] 的 iteration-level 抢占模型；无法消除 prefill 对 decoding 的结构性中断，只缩短单次抢占时长。strawman 与 Toppings 的 TTFT/TPT 权衡未给出操作指南。
- **局限 2**：性能模型和 pipeline 参数绑定特定 GPU/kernel（BGMV/MBGMV），硬件或 kernel 升级需 reprofile；scheduler 未考虑 network RTT、跨节点 adapter 副本一致性。
- **局限 3**：CPU-assisted 在极长 prompt + 高 rank 时依赖多核扩展，CPU 成为新瓶颈时仅比 CACHED 高 10%–17%（4× CPU 约束实验），优势收窄。
- **Future work 1**：**量化混合 cache 策略**——对 top-K 热门 adapter 做 GPU pin + 冷门走 CPU-assisted，测量 hit-rate vs memory 的 knee point，可能优于纯 on-demand 或纯 CACHED 二分法。
- **Future work 2**：**与 prefill-decode [[Disaggregation]] 结合**——将 CPU LoRA prefill 卸载到 dedicated prefill worker，彻底解除与 decoding 的 GPU 抢占耦合；需测量跨节点 weight 传输是否抵消收益。
- **Future work 3**：**tail latency + fairness 的系统测量**——在 rank-aware cost 中加入 P99 惩罚或集成 VTC，验证 SLO 99% 是否以牺牲低 rank tenant 为代价。
- **Future work 4**：**在线模型校准**——当 batch 组成漂移时动态更新 α/β，而非离线一次性 profile，应对新 adapter rank 分布或新 kernel 版本。

## 相关

- **相关概念**：[[LoRA]]、[[KV-Cache]]、[[Continuous-Batching]]、[[Tensor-Parallelism]]、[[PagedAttention]]、[[Chunked-Prefill]]、[[Disaggregation]]
- **同类系统**：[[vLLM]]（dLoRA 后端）、Punica（BGMV multi-tenant LoRA）、S-LoRA（MBGMV + unified memory pool）、dLoRA（dynamic merge/unmerge）
- **同会议**：[[ATC-2025]]
- **对比**：Toppings 用 CPU 算力换 GPU loading 等待；dLoRA 用 GPU 内存换 loading；S-LoRA/Punica 接受 loading 打断——三者代表 multi-tenant LoRA 的不同资源权衡轴
