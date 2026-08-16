---
type: paper
name: SDCHunter
full_title: "SDCs in the Wild: Characterizing and Diagnosing SDC-defective GPUs in Production LLM Training (Operational Systems)"
authors: [Wenxin Zheng, Wenxiao Wang, Yun Zhang, Mingcong Han, Bin Xu, Jinyu Gu, Xingda Wei, Haibo Chen, Zuquan Song, Gaohong Liu, Yucheng Nie, Zhe Nan, Zhuolin Zheng, Huan Yu, Shuguang Wang, Ziming Zhou, Hang Zhu, Wencong Xiao, Xin Liu]
venue: OSDI
year: 2026
tags: [gpu-reliability, silent-data-corruption, llm-training, deterministic-replay, fault-diagnosis]
source_pdf: "[[osdi26-zheng.pdf]]"
source_md: "[[osdi26-zheng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# SDCHunter：诊断生产 LLM 训练中的 GPU 静默数据损坏（OSDI 2026）

> **原题**：SDCs in the Wild: Characterizing and Diagnosing SDC-defective GPUs in Production LLM Training (Operational Systems)

> **一句话总结**：ByteDance 对 23 张真实 SDC-defective GPUs 的分析发现，故障会随硬件老化出现，并且只在特定 kernel、data type 和输入值上触发，ECC、温度和通用 GEMM stress test 因而经常看不见。SDCHunter 保存触发异常的原模型、checkpoint、input shards 和通信顺序，通过 bit-wise deterministic replay 先用 PP-boundary hash 找到可疑 DP group，再离线比较全部 tensor signature 找具体 GPU；生产中识别了 40 张缺陷 GPU，128/512-GPU、50B/150B 评测的在线开销低于 4%，但系统是异常发生后的诊断工具，不是 always-on SDC detector。

## 问题与动机

单张 GPU 的静默数据损坏（Silent Data Corruption，SDC）很少见，但数万张 GPU 连续训练数月后会成为常态性运维问题。SDC 不一定发出 ECC、machine check 或 device error，而可能先破坏一次 token count、modulo 或 floating-point operation，之后才表现为 shape mismatch、out-of-bound crash 或 loss spike。报错位置往往不是故障源，工程师会先排查 software bug 或数值不稳定，耗费数天甚至数周（§1–§2.2、图 2–5）。

生产常用 hardware diagnostics、GPU-Burn 或通用 GEMM loops 扫设备。论文的经验是这些 synthetic tests 会漏掉超过 60% 的缺陷 GPU，因为真实 SDC 与具体 operator sequence、precision 和 input value 强相关。已确认设备在同一 alert-triggering workload 上的可见错误概率横跨 100% 到 0.000001%；若 occurrence rate 只有 0.01%，传统反复重训的 debug compute 乐观估计也相当于约 2.9 次完整模型训练（§2.3、表 1）。

用原训练 workload 回放最有机会重现故障，但分布式 [[LLM|大模型]] 训练本身并不 bit-wise deterministic：atomic reduction 顺序、random operator、[[NCCL|NCCL]] topology/channel 变化，以及缩小 GPU 数后不同 parallel/fusion strategy 都会产生正常数值差异。即使能重放，loss 又会把早期 tensor corruption 掩盖；全 kernel 检查则有 683.9% overhead，还可能改变微架构 timing，使原 SDC 反而不再出现（§4、图 9–14、表 4）。

## 关键观察 / 隐含假设

- **观察 1：SDC 不只来自新卡的制造缺陷。** 23 张真实设备中只有 25% 在上线前 burn-in 阶段发现；25% 在前两个月、10% 在半年内、40% 在约一年后出现。作者结合 vendor analysis 把这一分布解释为长期高负载造成的 circuit resistance drift（§3、图 6）。
  - **证据边界**：样本只有 23 张，来自单一公司 fleet；具体 GPU generation、散热条件和 fleet denominator 没有公开，因此不能据此估算行业 failure rate。
- **观察 2：触发条件具有 operator 和 data affinity。** 首次暴露故障的 kernel 横跨 GEMM、InplaceMoE、[[Flash-Attention|FlashAttention]]、RMSNorm、Scatter 和 fused/internal kernels；GEMM 与 InplaceMoE 各占 17.3%。三张卡的 sweep 中，FP32/FP64 是否出错随 GPU 和数值区间变化；一张卡的 FP64 结果 100% 错且 latency 高 50 倍，另一张低于 1%（§3、表 2–3、图 7）。
  - **依赖假设**：要复现同一故障，必须保留足够完整的 kernel sequence、data type 和输入分布；缩成一个通用小模型可能把触发条件丢掉。
- **观察 3：logic-level corruption 没有可靠 side signal。** 缺陷卡与健康卡的 exception、performance counter、status register、ECC count、clock 和 thermal limit 没有可区分关系；有些 value bias 小于 `10^-3`，会被后续 activation、normalization 或 accumulation 吸收（§3、图 8）。
  - **结果**：系统必须比较计算输出，而不能只看设备 telemetry；loss/grad norm 又太晚且覆盖有限。
- **观察 4：生产训练可以被约束为可重复 trace。** 锁定 RNG、operator implementation、GEMM launch、atomic reduction、[[MoE|MoE]] dispatch、collective algorithm/channel 和通信顺序后，健康 replica 应产生 bit-wise 相同结果。ByteDance 测量的 deterministic step time 与普通训练相差少于 0.01%，normalized debug time 从 1.00 降至 0.30（§5.1）。
  - **依赖假设**：这些约束在异常发生前就已开启；故障后才切换 deterministic kernel 无法保证 replay 仍是原 workload。
- **观察 5：先粗分组、再细定位可把开销移出关键路径。** [[Pipeline-Parallelism|PP]] communication boundary 的 compact hash 只能定位 rank/group，却足以先摘除可疑 machines；昂贵的 layer-wise full-state comparison 可在小 group 上离线执行（§4.2、§5.2–§5.3、表 4）。
- **假设 1：至少一个 replay replica 健康。** 两个 replicas 不一致时可加第三个 spare replica 做多数判断；多个 faulty groups 只要不产生相同 corrupted signature 也能识别。所有 replicas 同时以相同方式损坏时，SDCHunter 无法靠 consensus 判断，只能回退 known-good machines 与 vendor diagnostics（§5.2）。
- **假设 2：外部 alert 已经出现且相关 trace 可取回。** 当前系统从 loss spike、shape error 等异常启动；没有明显高层症状、已写入 checkpoint 的 silent corruption 或未保留 input/communication trace，不在当前在线检测路径内（§5、§8）。

## 核心方法

### 把 deterministic constraints 放进正常训练

SDCHunter 不是在故障后临时“尽量重跑一次”。Production run 本身开启 [[PyTorch|PyTorch]] deterministic switches，关闭 `cudnn.benchmark` 和 GEMM autotuning；对 reduction 固定累加顺序，对 elementwise kernel 固定 SM-to-row mapping，对 MoE routing/scatter 重写 deterministic kernel。Collective communication 固定 Ring/Tree algorithm 和 channel count，并记录不可变 message order（§5.1）。

Replay 必须恢复同一 model、checkpoint、input shards、operator choices、PP/[[Tensor-Parallelism|TP]] configuration 和 communication schedule。系统只重组用于比较的 [[Data-Parallelism|DP]] groups，不改变模型或 diagnostic kernel。这个选择保留了 workload fidelity，也意味着每种训练栈都需要 deterministic implementation 和 framework integration（§5、§5.1）。

### Phase 1：用 boundary signature 找可疑 group

收到异常后，系统沿 Data Parallel（DP）维度组织两个 replay replicas，两边喂完全相同的 batch。Framework 已知 checkpoint、DP groups、Pipeline Parallel（PP）boundaries 和 replay window，因此只在 PP communication tensors 上计算 associative hash，并比较 replica、DP group 和 PP stage 的 signatures（§5.2、图 15）。

若某 group 相对参考发生 divergence，scheduler 先把该 group 的 machines 从后续 placement 排除，job 从最近 verified checkpoint 在其他 machines 上恢复；Phase 1 在生产中重放少于 100 steps，hash comparison 只需数秒。[[Expert-Parallelism|EP]] 内部 communication 常和 MoE compute 融合，framework 取不到内部 signature，所以不能同样沿 Expert Parallel 维度继续细分（§5.2）。

### Phase 2：比较第一处 tensor divergence

在线 job 恢复后，可疑 group 与健康 reference group 离线 deterministic replay 原 problematic iteration。系统按 layer 收集 intermediate tensor signatures，找到第一处不同的 tensor 和 producing kernel，再利用 framework 的 tensor ownership、rank placement 和 operator order 映射到 physical GPU（§5.3）。

这样只在缩小后的 group 中承担细粒度 inspection，而不是让全 cluster 每步 dump tensor。作为对比，论文测得 communication-boundary signature 为 4.3% overhead、只能 cover rank-level 5.65%；layer granularity 为 36.6%；kernel granularity为 683.9%，才有 kernel/tensor localization（§4.2、表 4）。

### 诊断后的确认（Post-diagnostic confirmation）

定位出的 GPU 先跑 vendor hardware tools；若仍通过，就把 alert-triggering trace 反复 replay，逐步提取最小、稳定复现的 kernel error。这个 confirmation 不阻塞已迁走的训练 job，并为 hardware repair 提供 device ID 和 reproducible trace（§5.4）。

## 设计取舍

- **真实 workload replay 换通用性**：能触发 data-dependent SDC；必须保存 checkpoint、input、model code、operator 和 communication trace，跨 framework/版本复现成本高。
- **正常训练 deterministic 换可比较性**：bit-wise mismatch 有明确含义；锁死 autotuning、reduction 和 topology adaptation，可能牺牲故障网络下的性能弹性，论文只报告稳定 production configuration 的 step time。
- **PP-boundary hash 换低在线开销**：低于 4% 且快速摘除 group；无法直接看到 fused EP kernel 内部或第一处 corrupted tensor。
- **离线 full-state comparison 换 job 快速恢复**：昂贵 work 不占在线 critical path；仍需要健康 reference group、spare capacity 和足够多 replay 才能重现极低概率故障。
- **Replica consensus 换无可信单卡 golden result**：健康 peers 可互为 oracle；common-mode software divergence、相同多卡 corruption 或 hash collision 会破坏判断。
- **被动触发换部署成本**：只有出现 alert 才采集和分析，开销可控；没有 visible symptom 的 SDC 仍会静默污染 checkpoint，always-on fused checksum 只是 future work。

## 实验与结果

- **证据来源、规模与 baseline**：Characterization 使用 23 张 ByteDance 生产中已确认的 defective GPUs，其中 10 张由“真实 online workload 的 offline stress”发现，13 张在 active training 中造成中断。System evaluation 使用 128/512 GPUs、50B/150B models；每 host 有 168 CPUs、2 TB memory、8 GPUs，并使用高速 GPU interconnect/[[RDMA|RDMA]]，但论文没有报告 GPU 型号、网络带宽或训练时长。Baseline 包括 hardware tools、GPU-Burn、PEPPA-X、loss/grad norm、He 等人的统计边界、HWSentinel，以及作为 gold standard 的 Full Data Dump（§2.2、§6）。
- **在线 overhead**：SDCHunter 在 150B/128-GPU、150B/512-GPU、50B/128-GPU、50B/512-GPU 上分别增加 3.75%、1.14%、3.90%、2.25%。Full Signature 为 383%、71%、591%、578%；Full Data Dump 至少 162,813%，最高 5,581,815%，主要因 GPU memory 已接近饱和后同步搬 tensor 到 host（§6.2、图 16）。
- **真实设备 detection**：Production deployment 到投稿时识别了 40 张 SDC-defective GPUs，offline debug 从数天降至一小时内。真实 trace 表中 SDCHunter 与 Full Data Dump 对 confirmed set 均为 100% coverage；hardware tools、GPU-Burn、PEPPA-X 分别为 30%、20%、37.5%，loss/grad norm、He 等人方法和 HWSentinel 分别为 25%、50%、17.5%（§6.1、§6.3、表 5）。
- **模拟 fault detection 与 localization**：Fault injection 通过修改 training input/output tensor values 模拟 corruption。SDCHunter coverage 为 91%，平均 3 steps、overhead 3.9%；Full Data Dump 为 100%、0 step、overhead 大于 1000%；loss、grad norm、He 等人方法 coverage 仅 16%/17%/33%，平均晚 127/109/25 steps。Device-level localization 在真实 confirmed cases 和 injection 中均为 100%；这是 tensor corruption 注入与已确认设备上的归因结果，不等同于对所有真实 microarchitectural fault 的 91% 检出保证（§6.3–§6.4、表 6–7）。
- **恢复时间与低概率边界**：Phase 1 的真实 case 少于 100 replay steps，使 job 在隔离可疑 DP group 后一小时内恢复；Phase 2 在不阻塞 online job 的情况下于一小时内给出 device。论文观察到的 replay occurrence rate 最低达 0.000001%，但没有按 rate 给出诊断时间分布或 replay 并行度，因此“所有 case 一小时”如何覆盖最稀有故障仍缺少细节（§2.3、§6.1、§6.3）。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Generic stress test 会漏掉 workload-specific SDC | 23 张实卡展示 kernel/data-type/value affinity；GPU-Burn 对 confirmed set coverage 20%（表 2–3、表 5） | 单一生产 fleet，confirmed-device selection | 强（该 fleet） |
| Hierarchical replay 能以低在线成本定位可疑 group | 四个 50B/150B、128/512-GPU 配置 overhead 为 1.14%–3.90%（图 16） | GPU 型号与训练配置未公开；依赖长期 deterministic training | 强（所测配置） |
| 系统改善了实际事故处理 | 生产识别 40 张 defective GPUs，job recovery 和 offline diagnosis 均报告一小时内（§6.1、§8） | 没有对照部署、时间分布或总 incident denominator | 中到强 |
| Fault injection 下能较早发现 corruption | 91% coverage、平均 3 steps，对 metric baseline 的 16%–33% 和 25–127 steps（表 6） | 注入直接修改 tensor，不模拟真实 unit trigger、intermittence 或 timing | 中 |
| 第一处 tensor divergence 可定位 device | 真实 confirmed set 与 fault injection 均为 100% rank correctness（表 7） | 条件是 fault 已重现、reference 健康且 signature/ownership 正确 | 强（条件内） |

## 批判性分析

### 论证链条

论文先用真实缺陷设备解释 synthetic test 为什么失败，再把结论直接映射到 exact-workload replay；随后用 determinism 消除正常差异，用 coarse-to-fine signatures 解决 observability overhead。Characterization、设计和 deployment 三段逻辑闭合，尤其把“恢复训练”和“查到具体坏卡”拆成在线/离线两阶段，是很实用的 operational choice。

不过论文把 detection、diagnosis 和 confirmation 有时混用。当前入口仍是外部 anomaly signal；SDCHunter 主要回答“这次异常是否来自哪张卡”，并不能发现从未表现为 loss/crash 的 silent error。40 张 production devices 证明诊断有用，不证明 fleet-wide recall。Future-work 的 fused always-on checksum 才接近实时 detector。

### 假设压力测试

若原训练没有 deterministic constraints、checkpoint/input shards 已丢失、NCCL topology 无法恢复或 operator version 已变化，健康 replicas 也会不同。若 fault 只在原大规模拓扑、某次 thermal state 或跨 GPU interaction 中出现，重组 DP replicas 可能改变触发条件。若多个 replicas 同时发生相同 common-mode corruption，多数判断也失效。

最低 `10^-6%` occurrence rate 意味着朴素串行 replay 的期望次数极大。Exact input 可以提高触发概率，但论文没有解释该最低 rate 下如何在一小时内完成 confirmation。Hash 的位宽、碰撞概率、signature reduction 发生 SDC 时怎样保护，以及 reference group 的健康认证也未定量说明。

### 实验可信度

真实的 23 张缺陷卡和 40 张生产定位结果非常稀有，比纯 fault injection 有力；作者还公开了时间分布、kernel 分布、负面 observability 和完整 baseline table。128/512 GPUs 与 50B/150B models 说明实现确实跑在大训练规模，而不是单机 toy workload。

外推边界也很明显：公司、GPU generation、fleet size、failure denominator 和 raw traces 未公开；confirmed set 可能偏向容易出现 alert 或容易复现的 faults。Table 5 的 100% coverage 在已确认集合上测量，不能得到未知 false negative；fault injection 只是直接改 tensor input/output，验证 signature pipeline，却没有模拟 defective ALU、data-dependent trigger、timing 或 instrumentation-induced Heisenbug。结果没有 confidence interval，也没有 corruption magnitude、位置和频率 sweep。

### 系统性缺陷

系统深度绑定训练 framework：deterministic MoE kernels、固定 collective、trace retention、DP/PP ownership、scheduler quarantine 和 checkpoint recovery 都要协同维护。锁定通信 topology 可能在 NIC degradation 时牺牲 runtime adaptation；专用 deterministic kernel 也要跟随新 model/operator 更新。论文只用 step time 说明稳定态代价，没有报告失败网络、mixed framework 或版本升级的运维成本。

Phase 1 需要额外 replica 或 spare healthy machines；Phase 2 需要重复执行和保存大量 signatures。Alert trace 还可能包含训练数据，长期留存带来容量、隐私和访问控制问题，论文未讨论。系统会隔离设备并重启 job，但不提供 in-step correction，也不能撤销在发现前已经写入和下游使用的 corrupted checkpoint。

## 局限与后续工作

- 按 GPU generation、fault unit、occurrence rate 和 alert type 发布匿名化诊断时长分布，解释 `10^-6%` case 的 replay 数量、并行度与一小时目标。
- 用 hardware fault emulation 或已知 defective GPU 做 controlled sweep，对比 tensor-value injection，量化后者高估或低估 coverage 的程度。
- 报告 signature hash 设计、collision bound、signature computation 自身的冗余保护，以及 reference replica 被污染时的 fail-safe 行为。
- 把 communication checksum 融入 Send/Recv kernel，实测 every-step always-on detection 的 overhead、recall 和 checkpoint pollution window。
- 在 topology change、NCCL fallback、operator upgrade、mixed GPU generation 和 multiple simultaneous faults 下验证 bit-wise replay 与 consensus。
- 为 trace/checkpoint retention 定义容量、加密、访问控制和自动删除策略，并测量每 incident 的 GPU-hours 与工程师时间，而不只报告 wall-clock。

## 相关

- **概念**：GPU SDC、deterministic replay、fault diagnosis、distributed training
- **同会议**：[[OSDI-2026]]
