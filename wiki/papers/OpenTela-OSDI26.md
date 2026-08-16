---
type: paper
name: OpenTela
full_title: "OpenTela: Unifying Decentralized Computing Resources for Heterogeneous LLM Serving (Operational Systems)"
authors: [Xiaozhe Yao, Youhe Jiang, Ilia Badanin, Qinghao Hu, Robert Matthew Smith, Binhang Yuan, Imanol Schlag, Eiko Yoneki, Ana Klimovic]
venue: OSDI
year: 2026
tags: [llm-serving, hpc, orchestration, crdt, heterogeneous-scheduling, sovereign-ai]
source_pdf: "[[osdi26-yao.pdf]]"
source_md: "[[osdi26-yao]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用去中心化覆盖层统一 HPC 上的异构 LLM 服务

> **原题**：OpenTela: Unifying Decentralized Computing Resources for Heterogeneous LLM Serving (Operational Systems)

> **一句话总结**：OpenTela 用普通用户权限把 Slurm/Kubernetes allocation 包成可发现的 LLM endpoint，以 libp2p + CRDT gossip 维护跨集群注册表，再用模拟器和约束规划放置异构模型；它在 Swiss AI 运行超过 22 个月、服务 1,300 万请求和 150 亿 token，但可用性仍是 best effort，生产资源主要来自同一 Alps 超算内的三个子集群。

## 问题与动机

[[vLLM]]、[[SGLang]] 解决单个 engine 内的 batching、[[KV-Cache|KV cache]] 和 kernel 调度，却默认外部有 Kubernetes 提供固定 service name、健康检查、路由和扩缩容。主权 AI（sovereign AI）资源往往是 [[Slurm]] 管理的 HPC：allocation 只有数小时，compute node 没有公网入站地址，训练和推理还要共享 GPU。硬切一块 Kubernetes partition 会让 batch 与 serving 之间难以调剂。

单个 HPC cluster 的空闲 GPU 随训练完成、维护和 scavenger job 快速变化，LLM 请求也高度 bursty。把多个 cluster 资源池合起来有机会平滑两边波动，但不同机构的 scheduler、网络、GPU、CUDA 和数据治理规则都不同，也没有大家共同管理的 privileged coordinator。OpenTela 的目标不是替换推理 engine 或 Slurm，而是在它们上面加一层普通用户可部署的服务控制面。

## 关键观察 / 隐含假设

- **观察 1：HPC 缺的是 service abstraction，不是 inference kernel。** 一个 Slurm job 已能启动 engine，缺少的是 allocation 变化后仍稳定的发现、健康、路由、认证和计量（§2）。
- **观察 2：服务目录适合最终一致，而非强一致。** 节点状态以 JOIN→SERVING→DOWN→LEFT 单调推进，合并操作只需选更高 lifecycle state；早期中央数据库反而成为扩展瓶颈。G-Map [[CRDT]] 让每个 node 持有本地全量副本，partition 时仍可查询（§3.2、§7.1）。
- **观察 3：生产 demand 同时有热门头部、长尾和极端突发。** 16 个月 trace 包含 142 个模型；最 bursty 模型的 peak/active-minute mean 超过 80，最突发的前 15 个模型都超过 13。平均负载不足以指导静态配置（§6.2，图 9–11）。
- **观察 4：GPU memory 容量不足以表示执行性能。** A100、H100、GH200、RTX 3090 对不同模型和并行策略的相对速度不同，因此默认 placer 用 model/hardware simulator 估计 latency，再做离散优化，而不是只按参数量分卡（§3.5）。
- **假设 1：用户可以事先信任 provider。** allowlist 只阻止路由到未授权 provider；签名检查只证明 OpenTela binary 没变，provider 的 root 仍可替换 engine 或读取 loopback prompt，系统没有硬件 attestation（§3.3）。
- **假设 2：model identifier 足以表达服务语义。** [[Quantization|quantization]]、context limit 和精度由 provider 自觉编码进名称，API 不能协商 QoS；错误或模糊命名可能把请求送到不符合预期的实例（§7.1、§7.3）。

## 核心方法

**用户态节点覆盖层。** Provider 取得 Slurm allocation 或 Kubernetes deployment 后，用 `otela start --process ...` 包住原有 vLLM/SGLang 命令。节点通过 libp2p 建立加密 P2P 网络，以 outbound hole punching 或 public circuit relay 穿过 HPC NAT，再用 Kademlia 找 peer。公开 ingress 也是普通 OpenTela node，只是额外提供 OpenAI-compatible API、认证、用量记录和 dashboard（§3.2、§4，图 2）。

**CRDT 注册表与生命周期。** 每个 peer 保存一份 Growth-only Map，key 是 node/session ID，value 包含 lifecycle 和 hardware/model metadata。随机 gossip 传播更新；本地 engine 死亡时标 DOWN，三个独立 probe path 都失败后先 suspected 并停止路由，超过 grace period 才标 LEFT。已驱逐记录默认 24 小时后从应用视图移除，再定期 compact tombstone；恢复节点必须用新 session ID 重新 JOIN（§3.2、§3.4）。

**请求路由与故障处理。** Ingress 从本地 registry 找到目标 model 的 session，先按用户 provider allowlist 过滤，再用 uniform random、round robin 或 hardware-weighted random 选 worker。非 streaming 请求失败时最多重试到另一节点；stream 已经输出后无法在另一个非确定性 engine 上续写，只能由客户端重试。Pick/OnRequestStart/OnRequestEnd 接口允许替换 request policy（§3.4，图 3）。

**异构放置。** 默认 service scheduler 收集每个模型的 arrival rate、输入/输出长度分布，用扩展自 LLM-Viewer 的 roofline simulator 估计每种 GPU、data/tensor parallelism 下的 mean end-to-end latency，再用 constraint programming 同时决定 allocation matrix 与 parallelism。约束包括 GPU 数量、weights+KV memory 和并行度整除关系。当前 simulator 不建模 [[Chunked-Prefill|chunked prefill]]、prefill/decode disaggregation、[[Prefix-Caching|prefix cache]] 等重要优化；而且 placer 只使用新出现的空闲资源，不回收已运行的冷模型，也不在线改变其 parallelism（§3.5）。

## 设计取舍

- **最终一致换 partition availability。** 本地读 registry 没有协调延迟，但 128 节点全量收敛尾部约 10 s，短时间内可能看到陈旧 endpoint。
- **去中心化 registry 不等于全系统无中心。** 生产客户端仍经过公开 API ingress，自动 model placement 也由 centralized service scheduler 完成；论文未评测 ingress 或 scheduler 故障。
- **非侵入换弱资源控制。** 普通用户不用改 Slurm/Kubernetes，但 OpenTela 不能强制回收 allocation、抢占冷模型或保证底层 job 稳定，因此 availability 只能 best effort。
- **统一 API 换模型语义损失。** OpenAI-compatible API 方便接入不同 engine，却隐藏 quantization、context、quality 和运行阶段，复杂优化与 QoS 只能靠命名或未来扩展。

## 实验与结果

- **生产范围与 trace 口径**：OpenTela 运行超过 22 个月，累计服务 1,300 万请求、150 亿 token、142 个模型和超过 1,000 位研究者。公开 trace 不是完整 22 个月，而是 2024 年 7 月至 2025 年 10 月的 16 个月；含 46 个公开模型和 96 个社区自训模型。用户可为合规绕过 tracking，因此 trace 也不是全部请求的无缺失审计（§6、§6.1）。
- **控制面与 gossip**：Qwen3-1.7B、单 GH200、1/4/16 RPS 下，ingress/lookup/forward/return/other 分别约 0.33/0.07/0.50/0.50/0.23 ms，总增量为 1.42–1.69 ms、约占 P50 TTFT 10%。128 节点时 50% peer 在 7–13 ms、75% 在 26 ms 内、95% 在 1 s 内收到更新，最慢约 10 s。idle gossip 的每节点流量从 10 节点的 1 KB/s 增至 50 节点的 8 KB/s；若 10 个节点每 3 s 重注册一次，CRDT 写入会把每节点流量短时推到 40 KB/s。每次请求另有约 450 B 请求头和 120 B 响应头（§5，图 5）。
- **跨集群与故障**：可直接对照的 WAN path 上，OpenTela tunnel 最多增加 15 ms、吞吐最多下降 16%；Frankfurt ingress 到 Switzerland worker 的 TTFT 增量约 3.5 ms，其中网络 RTT 为 3.1 ms。最多 64 张 GH200、随机终止 replica 的 50 分钟实验中，throughput 随 active replica 数近似变化，作者观察到 0 个用户可见 HTTP error；这不覆盖已经开始返回的 streaming 请求（§5，图 4、图 6）。
- **放置策略**：24 张 A100 + 32 张 GH200、13B/34B/70B 合成 Poisson workload 下，OpenTela 的 per-model throughput 为 30.4/43.0/55.3 req/s，memory-proportional `memP` 为 19.9/12.0/40.2 req/s；合计约 128.7 对 72.1 req/s。提升来自把 GH200 分给被 memP 严重低配的 34B，而不是证明全局最优（§5，表 1、图 7）。
- **模拟器验证**：H100 与 RTX 3090、三组 input/output/batch 配置中，绝对 latency 估计最大偏差 10%，H100 相对 RTX 3090 的 speedup 误差低于 6%。验证只覆盖两个 GPU 和三个静态配置，也未包含 simulator 明确遗漏的 engine 优化（§5，图 8）。
- **Reasoning workload 的生产观察与受控对照必须分开。** 生产 trace 中，Qwen3-Next-80B-A3B-Thinking 在大部分生命周期的 reusable-prefix ratio 超过 90%，对应 Instruct variant 多数约 15%；Reasoning 请求 P95 E2E 为 173.58 s，non-reasoning 为 30.77 s，约高 5.6 倍，其 P95 output 为 7,628 对 828 tokens（§6.2，图 14–15）。另在 AIME 1983–2024 受控实验中，Thinking 的 KV cache 运行约 95 分钟且反复接近满载，Instruct 约 40 分钟完成；4 张 A100 的总能耗为 4.84 对 2.03 kWh、每百万 token 为 0.25 对 0.16 kWh，4 张 GH200 则为 4.35 对 2.08 kWh、0.23 对 0.17 kWh。这只是一对模型、一个 benchmark，不能外推为全部 reasoning 模型或生产 workload 的总体规律（§7.2，图 16–17）。

## 论断—证据表

| 论断 | 直接证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 普通用户态 overlay 能把 transient HPC job 变成长期 LLM service | Swiss AI 超过 22 个月、1,300 万请求、三个 Alps 子集群上线 | 主要在同一 CSCS/Alps 环境，未展示多个互不信任机构贡献 GPU 的长期数据 | 强（该部署）/中（广泛联邦） |
| CRDT gossip 能在 churn 下保持服务 | 最多 64 GH200 随机杀 worker 时 0 HTTP error；128 节点 convergence 测量 | 非 streaming、best-effort retry；全量收敛尾部约 10 s | 中强 |
| 用户态路由开销较小 | 单 GH200 下 1.42–1.69 ms；WAN 中纯 OpenTela routing 约 0.4 ms | 1.7B 模型、最高 16 RPS；没有 ingress saturation 与 P99 | 中强 |
| 异构感知放置优于只看内存 | 合成 workload 总吞吐 128.7 对 72.1 req/s | 只对一个 memP heuristic、三模型和一组 GPU budget | 中 |
| 长期 trace 揭示 burst、reasoning tail 与 prefix reuse | 16 个月、142 模型；peak/mean、P95 和 hash-bucket reuse 数据 | tracking 可绕过；部分结论来自单个代表模型 pair | 强（trace 内）/中（泛化） |

## 批判性分析

### 论证链条

论文作为 operational system 最强的证据是长期真实服务：user-space wrapper、registry、routing 和认证确实把 Slurm/Kubernetes 资源变成了统一入口。microbenchmark 也分别验证 overhead、gossip、churn 和 placer。比较容易被标题掩盖的是“decentralized”的范围：注册表和节点网络去中心化，但 ingress、用户服务和默认 placement 仍有中心角色；论文没有证明整个服务在这些角色故障时仍可用。

### 假设压力测试

网络 partition 超过 suspicion/grace period 时，两个区域可能对同一 session 的状态看法不同；需要测 stale route、重复 retry 和恢复后新 session 的收敛。Provider root 恶意修改 serving engine、伪报 model quantization 或返回错误结果时，签名与 allowlist 都无能为力。trace 说明 demand 极其 bursty，但当前 placer 不回收运行中的冷模型；压力测试应比较“保持可预测”与动态 re-placement 在 burst 期间的 queue、load time 和 availability。

### 实验可信度

长期 trace、真实三子集群和公开 artifact 让 workload 真实性很强。系统实验却偏窄：placement 只比一个 memory heuristic，使用合成 Poisson arrival；没有 Kubernetes/central DB control-plane 基线，也没有 cost、GPU utilization 或 P99 SLO。生产三个子集群都属于 Alps/CSCS，内部网络低于 1 ms；这支持异构 Slurm/Kubernetes 互操作，但不足以完全验证跨国家、跨组织和高 WAN latency 的 federation。0 HTTP error 也没有报告 retry 数、重复计算和 streaming failure。

### 系统性缺陷

OpenTela 明确没有强 availability guarantee；stream 中断不能恢复，节点异常多采用 fail-stop 自我驱逐。每个 peer 保存全量 G-Map，idle traffic 已随 mesh 增长，远大于 128 节点时的 registry 与 tombstone 成本未验证。默认 scheduler 的 roofline model 忽略当前 LLM engine 的关键优化，又不在线回收或 reconfigure，和 trace 得出的“必须动态分配”存在张力。安全上，provider root 能读取请求和替换 engine；数据主权最终依赖机构信任关系，而不是系统强制隔离或远程 attestation。

## 局限与后续工作

- 部署冗余 ingress/scheduler，注入其故障并报告 non-streaming retry、streaming 中断、重复 token 和 P99 availability。
- 在多个独立管理机构的长期 WAN federation 中测量 stale route、partition healing、CRDT full-state/tombstone 开销和成本计量。
- 用实际 engine profiling 校准 simulator，并加入 prefix cache、chunked prefill、prefill/decode disaggregation；与更多 placer 在 trace replay 上比较。
- 引入可验证 model configuration 与 confidential-computing attestation，让 client 能验证 provider、engine、quantization 和代码身份。
- 设计带冷却与 load-cost 的动态 model reclamation，对 production burst trace 客观比较 mean/P99 latency 与 GPU-hours。

## 相关

- **相关概念**：[[CRDT]]、[[Service-Discovery]]、[[Heterogeneous-Scheduling]]、[[Sovereign-AI]]、[[LLM-Serving]]
- **同类系统**：[[Slurm]]、[[vLLM]]、[[SGLang]]、[[Helix]]、[[Petals]]
- **同会议**：[[OSDI-2026]]
