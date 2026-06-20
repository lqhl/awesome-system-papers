---
type: paper
name: AdaCheck
full_title: "AdaCheck: An Adaptive Checkpointing System for Efficient LLM Training with Redundancy Utilization"
authors: [Weijie Liu, Shengwei Li, Zhiquan Lai, Keshi Ge, Qiaoling Chen, et al.]
venue: FAST
year: 2026
tags: [llm-training, checkpointing, fault-tolerance, parallelism, redundancy]
source_pdf: "[[fast2026-liu-weijie.pdf]]"
source_md: "[[fast2026-liu-weijie]]"
---

# AdaCheck: An Adaptive Checkpointing System for Efficient LLM Training with Redundancy Utilization (FAST 2026)

> **一句话总结**：观察到 [[LLM-Training]] 在 [[Data-Parallelism|DP]]/[[ZeRO]]/[[Tensor-Parallelism|TP]]/[[Pipeline-Parallelism|PP]]/[[Expert-Parallelism|EP]]/MiCS/auto-planner 等任意并行组合下都会产生大量可精确刻画的 tensor redundancy，且 mixed-precision Adam 相邻 iter 差异主要是 half-precision gradient；AdaCheck 用 hash+ring detector 在 128 worker 上 3 分钟内识别冗余，离线只存非冗余状态、在线只存 gradient，相比 [[GEMINI]] 把 checkpoint size 缩小 6.00–896×、频率提升 1.46–111×，训练吞吐几乎零开销。

## 问题与动机

大规模 [[LLM-Training]] 是长周期、高故障率过程：LLaMA 3.1 在 16K GPU 上训练 54 天遭遇 419 次失败（约每 3 小时一次），约 2M GPU hours 浪费在 checkpoint 与回滚。故障开销可写为 $T_f = t_{\mathrm{ckpt}} + 1/(2f)$，其中 $f$ 为 checkpoint 频率；而 $1/f \geq s_{\mathrm{ckpt}}/b_{\mathrm{save}}$，故要提高 $f$（理想为每 iter 一次，即 1S1C）必须同时压低单次 checkpoint 体积 $s_{\mathrm{ckpt}}$ 或提高保存带宽 $b_{\mathrm{save}}$。

现有 checkpoint 系统几乎都为特定并行或架构定制：异步保存 / I/O 优化（[[CheckFreq]]、MegaScale、DataStates-LLM）主要重叠计算与持久化 I/O，DP 下常只让 rank 0 保存，不适配 [[ZeRO]]、[[Tensor-Parallelism|MP]]、[[Expert-Parallelism|EP]]；in-memory checkpoint（[[GEMINI]]、ECCHECK）利用训练网络高带宽，但仍按 worker 本地全量保存，忽略并行引入的 state redundancy。更麻烦的是，nnScaler 等 auto-planner 会生成**不规则并行**（不同 operator 的 replica/partition 策略各异），手工写 checkpoint 规则不可扩展。

作者从工业模型（Yi 34B、MegaScale 530B、DeepSeek-V3、Kimi K2）测量发现：训练过程中 25%–100% 的 model states 是冗余的，但 SOTA 系统要么存至少一份完整模型副本到慢速持久化存储（<100Gbps），要么在 worker 互联（<400Gbps）上重复传输冗余分片。核心问题是：**如何在未知/多变的并行策略与模型架构下，自动、精确识别并利用 state redundancy，把 checkpoint size 压到可支撑 1S1C 的水平？**

## 关键观察 / 隐含假设

- **观察 1**：并行训练在参数与 optimizer state 上引入的 redundancy **分布不同、且 replica 位置 matters**。Figure 6 的 MoE 案例：EP+ZeRO-1 下 attention 参数 $p_1$ 为 full redundancy，但其 optimizer state $o_1$ 为 no redundancy；若 naive 地按 replica 计数剔除，会得到「只有 optimizer、没有参数」的不可用 checkpoint。ZeRO-1 整体 25% 状态冗余来自「参数全复制、optimizer 分片」这一结构性不对称。
  - **依赖假设**：checkpoint 必须同时包含可恢复的 parameters 与对应 optimizer states；冗余判定必须在 state（多 tensor 组合）粒度而非单 tensor 粒度完成。
  - **可能失效场景**：非 Adam 优化器、无 momentum/variance 的 optimizer-free 训练、或 optimizer state 与 parameter 不再一一对应时，「取交集」规则需重新定义。

- **观察 2**：mixed-precision [[Adam]] 训练中，相邻 iteration 的 checkpoint 差异可近似为 **half-precision gradient**，不必每步存完整 FP32 optimizer state（14M → 2M，约 1/7）。Figure 8 显示 FP16/BF16 参数可由 FP32 master weight 导出，而 iter 间变化主要体现在 gradient 对 optimizer 的更新。
  - **依赖假设**：训练使用标准 mixed-precision + Adam 流程；gradient 在 failure 前已被正确计算并可用于 remote CPU optimizer replay；存在一个 periodic full checkpoint 作为 incremental chain 的 base。
  - **可能失效场景**：梯度累积跨多 iter、optimizer 状态含非确定性项、loss scaling 异常、或 parameter 在 iter 间被 in-place 改写且与 gradient 不同步时，「只存 gradient」的正确性需重新验证。

- **观察 3**：tensor redundancy 可在训练初期的 **communication group** 内高效探测，而不必做 $O(N^2)$ 全互联比对。并行框架为梯度同步已把 replica worker 组织进 DP/TP/EP 等 group；hash packed tensor + ring P2P 可把 128 worker 探测压到 **<3 分钟**（naive tensor 传输在 1000+ worker 上需 >30 天）。
  - **依赖假设**：framework 暴露的 NCCL communication group 与真实 tensor replica 关系一致；训练前两 iter 的 hash 交集可排除 collision 与 accidental equality；并行策略在训练过程中不变。
  - **可能失效场景**：runtime 动态改并行度、expert routing 导致参数值偶发相同但语义不同、或 hash 碰撞在极端规模下需额外 full-tensor verify——论文用两 iter 交集将错误概率压到 $2^{-512}$ 量级，但未在 production 超长训练上实证。

- **观察 4**：仅靠 offline redundancy utilization 仍不足以达到 1S1C。Figure 4 显示在 32×A800 上，即使用 offline 方法，ZeRO-1 / EP 等「为训练性能引入更多 redundancy」的策略反而**提高**了 1S1C 所需带宽；必须叠加 online gradient incremental 才能把 $b_{\mathrm{save}}$ 拉到 <400Gbps 互联可承受范围。
  - **依赖假设**：failure 后可通过 remote CPU optimizer + 周期性 full checkpoint 在可接受时间内恢复；checkpoint group 大小 $k$ 与 failure tolerance 目标匹配。
  - **可能失效场景**：大规模 correlated failure（整 rack、整 AZ）同时打掉同一 checkpoint group 内所有 replica 时，gradient chain 无法恢复——论文用 failure tolerance factor $k$ 与概率模型缓解，但 worst case（$n=32, k=3, f=4$）恢复率可降至 <90%。

- **假设 1**：用户训练脚本、并行拓扑、模型架构对 AdaCheck **完全透明**；detector 在训练开头运行两次即可，结果全程有效。
  - **证据强度**：**中**——在 DeepSpeed/nnScaler/Merak 集成的 6 个模型、ZeRO/MiCS/EP/auto-gen 多种策略上验证；但未覆盖训练中动态 resharding、pipeline flush 改 stage 分配、或 spot 实例频繁扩缩容。

## 核心方法

AdaCheck 分四块：**tensor redundancy 建模**、**redundancy detector**、**offline + online redundancy utilization**、**系统工程与 API**（Figure 5/10）。

### Tensor Redundancy 与 Offline Utilization

每个 worker $w_i$ 的 model state 是 tensor 集合 $T_i$；tensor $t_k$ 的冗余表示为 replica 位置元组列表 $R_i^k$。State redundancy 分三类：**full**（某 tensor 在全部 worker 有副本）、**partial**（副本数 $1 < |R| < |W|$）、**no**（仅一份）。checkpoint 在 state 粒度操作，且 parameter 与 optimizer state 的 redundancy **取交集**决定存取：full∩partial→partial，full∩no→no，partial∩no→no——保证恢复时参数与 optimizer 配对完整。

Offline 阶段只把 **partial/no redundancy** 的状态写入 remote memory；full redundancy 状态假定 failure 后仍可从存活 worker 的 live state 或 peer 恢复。用户还可指定 failure tolerance factor $k$：副本跨 $>k$ 个 node 的 partial state 视为 full，$\leq k$ 个 node 的视为 no，并据此划分 checkpoint group（group 内 worker 互存 incremental checkpoint）。

### Redundancy Detector

三阶段优化（§6, Figure 7）：
1. **Hash-based consistency check**：每 worker 用 blake2s 把本地 tensor 列表打成 packed hash tensor，跨 worker 比对相等 index；**连续两个 training iter** 取交集，抑制 hash collision 与 accidental equality。
2. **Comparison scope reduction**：只在各 parallel strategy 定义的 **non-overlapped communication group** 内比对，去掉被其他 group 包含的子集 group。
3. **Ring-based communication**：仿 [[Ring-AllReduce]]，step 0–1 并发 P2P 传 packed hash 并 intersect；step 2 起改传 comparison result 而非 packed tensor，把每 worker 传输量降到 $C_n \cdot (M_h + M_c)/2$。

Ablation（Figure 17）：naive tensor 传输不可接受；仅 hash 在 16 worker 需 8 分钟、大规模仍 >30 分钟；加 ring + group reduction 后 128 worker **3 分钟**完成。

### Online Redundancy Utilization

**Gradient-based incremental checkpointing**（§7）：对 detector 标记需保存的 state，按类型选择 payload——仅 parameter 则直接存；仅 optimizer 则存关联 parameter 的 gradient（1/6）；两者皆有则存 gradient（1/7）；metadata 直接存。checkpoint 经 **remote memory checkpointing** 写入同 group worker 的 CPU memory，按 [[Model-Parallelism]] 划分 group 以重叠通信与计算（Figure 9）。

**Remote updating**：为避免 recovery 时从 disk 拉 full base 再逐步 apply gradient，在 remote worker CPU 上维护 **modified CPU optimizer** 副本，收到 gradient 即更新 remote FP32 optimizer state；failure 时 affected worker 从 remote 拉最新 optimizer state 并做轻量 dtype 转换即可恢复，开销接近 [[GEMINI]] 式全量 remote memory checkpoint。

**Non-blocking full checkpointing**：后台线程周期性写完整 checkpoint 到持久化存储，应对 catastrophic failure（全员失效），不阻塞训练 critical path。

### 系统集成

基于 PyTorch 2.0，提供非侵入 API；已集成进 [[Merak]] 并开源，兼容 [[DeepSpeed]]、nnScaler、[[Transformers]] 等栈。与 [[CheckFreq]]（异步持久化 I/O）、[[GEMINI]]（in-memory 全量）正交，核心差异是 **adaptive redundancy-aware minimal checkpoint**。

## 设计取舍

- **取舍 1：训练初期 2-iter detector 换全程自适应**——一次性 $O(C_n \cdot M_h)$ 通信换之后每 iter 最小 checkpoint；代价是**假设并行拓扑与 sharding 规则训练期间不变**；动态重配需重跑 detector（论文未实现）。
- **取舍 2：hash 比对换精确 byte compare**——把每 worker 传输从 $M_t$（全 tensor）降到 $M_h \ll M_t$；代价是依赖两 iter 交集的概率论证，极端情况下需 fallback 全量 verify（未讨论）。
- **取舍 3：gradient incremental + remote CPU optimizer 换 1/7 checkpoint size**——使 1S1C 在带宽约束下可行；代价是 recovery 依赖 incremental chain 与 periodic full checkpoint，**同 group 多 worker 同时失败**时恢复率 $<100\%$（$k=2, n=128, f=4$ 时 95.3%）。
- **取舍 4：parameter∩optimizer 交集换 checkpoint 可用性**——避免 ZeRO-1 类「只存 optimizer」陷阱；代价是在 param full + opt no 场景下**必须存 opt 侧**，冗余削减幅度低于 naive replica counting。
- **边界条件**：在 **ZeRO-3 等无 redundancy** 场景，offline 方法退化为存全量，优势主要来自 online gradient incremental；auto-generated irregular parallelism 上 [[CheckFreq]] 需 per-parameter 规则而失效，AdaCheck 仍可适配——这是其最强场景。

## 实验与结果

- **Cluster**：DCN（32×A800, 800Gbps IB, 50Gbps 存储）与 CMD（128×3090, 100Gbps IB, 10Gbps 存储）。
- **Models**：LLaMA-7B/30B、DeepSeek-V2-Lite（64 experts）、GPT-1.4B/7B、GPT-MoE；并行覆盖 ZeRO-1/3、MiCS、EP+ZeRO-1、nnScaler auto-gen。
- **Checkpoint size**：比 CheckFreq/GEMINI 缩小 **6.00–896×**（Figure 11）；offline alone 比 GEMINI 缩小 1.30–240×，叠加 online 后再缩最多 **7.09×**（Figure 18）。
- **Checkpoint frequency**：在 MiCS / EP+ZeRO-1 高效并行下达 **每 iter 一次（1S1C）**；比 CheckFreq 高 **36.2–111×**，比 GEMINI 高 **1.46–3.64×**（Figure 12）。
- **Failure overhead**：sparse 模型上平均每 failure 浪费时间比 CheckFreq 少 **12.1–88.93×**，比 GEMINI 少 **1.73–4.51×**（Figure 13）；高 failure rate 下 end-to-end 吞吐比 GEMINI 最高 **1.12×**（Figure 15）。
- **Training overhead**：启用 AdaCheck 后 iteration time 与无 checkpoint baseline 几乎重合（Figure 14），得益于通信-计算重叠与非阻塞 full checkpoint。
- **Detector overhead**：128 worker **<3 分钟**；相对 LLaMA 3 级数月训练可忽略。
- **Reliability**：按式 (4) 建模 simultaneous failure 恢复概率；引用 OPT-175B 统计（24h 内 1.5% worker failure），认为 4 worker 同时失败极少，**多数配置恢复率 >90%**（Figure 16）。

## Critical Analysis

### 论证链条

动机（大规模训练高故障率 + 大量未利用 redundancy）→ 观察（tensor redundancy 可统一刻画 param/opt 不对称 + iter 间差异主要是 gradient）→ 设计（detector + offline 交集 + online incremental + remote updating）→ 结果（1S1C + 近零训练开销 + 跨并行/架构适配）整体闭合。最强证据是 **Figure 11/12 跨 6 模型×多种并行** 的 size/frequency 矩阵，以及 auto-gen parallelism 上 CheckFreq 失效而 AdaCheck 仍有效的对比。较弱环节是 **可靠性 claim 主要依赖组合概率模型与 OPT 故障率类比**，未在真实 16K GPU 长跑中做 correlated failure 或 checkpoint chain 断裂的 chaos test。

### 假设压力测试

- **并行策略静态**：生产中 spot 回收、节点替换、elastic DP 会改变 sharding；论文假设 detector 一次运行终身有效，**动态场景需重探测或 incremental metadata 失效**——论文未覆盖。
- **Optimizer 与精度路径**：实验聚焦 Adam + mixed-precision；若换 Lion、Muon、或 FP8 training with different master weight layout，gradient-only incremental 是否仍 1/7 且 numerically safe **论文未证明**。
- **MoE / EP 动态路由**：expert 激活随 token 变化，但 checkpoint 的是权重而非 activation；权重 redundancy 仍由 sharding 决定，这点成立。然而 **expert 负载不均 + 部分 expert 长期不更新** 时，hash 在个别 iter 可能 accidental equality——两 iter 交集可缓解，但证据强度中等。
- **GEMINI baseline 公平性**：GEMINI 闭源，作者 **自行 reimplement**；130× overhead reduction 等数字对 reimplementation 质量敏感，需读者谨慎对待。

### 实验可信度

- **Benchmark 代表性**：OpenWebText + BookCorpus 预训练，覆盖 dense/sparse 与工业规模模型名；但未用真实 production trace 的 failure 时间分布，Figure 15 用 **simulated failure rates** 扫 end-to-end 吞吐。
- **Baseline 强度**：CheckFreq 代表慢速持久化 + 异步 I/O；GEMINI 代表 in-memory SOTA。未与 ByteCheckpoint、ECCHECK、MoC-System/MOETION（MoE 专用）、CHECKMATE/FlowCheck（网络梯度捕获）对比——后者在特定拓扑可能有更低 overhead。
- **Ablation**：detector 三优化与 offline/online 分解（Figure 17/18）充分支持设计必要性；**缺少 remote updating vs naive incremental recovery 的定量 tail latency 对比**（仅定性 Figure 9）。
- **Correctness**：声称不损害 convergence accuracy，但实验 **只报 checkpoint 性能，未给 loss 曲线或 eval metric 对照**——对 incremental/remote optimizer 路径，这是明显缺口。

### 系统性缺陷

- **尾延迟与 recovery**：1S1C incremental chain 变长时，failure 后需定位最近 full checkpoint + replay gradients；remote updating 降低开销，但 **P99 recovery time、recovery 期间集群是否全局 barrier** 论文未给出生产级数据。
- **资源隔离**：checkpoint 占用 peer worker CPU memory 与训练网络带宽；与 [[ZeRO]] offload、checkpoint group 内 straggler 的交互未讨论。
- **可观测性 / 运维**：failure tolerance $k$、group 划分、detector 结果如何暴露给 SRE；incremental chain 损坏时如何检测 **论文未讨论**。
- **存储层次**：主要对比 remote CPU memory vs 持久化；未探讨 NVMe、CXL-SSD、对象存储 tiering 与 AdaCheck minimal state 的叠加收益。
- **与 UCP 等正交性**：[[UCP]] 解决并行策略变更时的 checkpoint 格式互转；AdaCheck 解决同策略下的最小保存——可组合，但论文未实验联合部署。

## 局限与 Future Work

- **局限 1**：**恢复概率 <100%**——gradient incremental + group size $k$ 在 multiple simultaneous failures 下存在理论失败组合；依赖 non-blocking full checkpoint 兜底，而 full checkpoint 频率与存储成本未充分量化。
- **局限 2**：**训练期并行静态**——auto-planner、elastic training、fault-triggered resharding 会使 detector 结果过期；论文承认透明 API 但不处理 mid-run 拓扑变化。
- **局限 3**：**正确性证据不足**——声明不影响 convergence，但缺少与无 AdaCheck baseline 的 loss/perf 长期对照；remote CPU optimizer 与 GPU optimizer 数值漂移边界未测。
- **局限 4**：**GEMINI 闭源 reimplement**——关键对比数字对 baseline 保真度敏感；社区难以独立复现 130× 等峰值。
- **Future work 1**：**动态并行下的 incremental detector**——在 resharding 事件触发局部重探测，并定义 checkpoint metadata 版本化与 chain 迁移协议。
- **Future work 2**：**与 strategy-neutral checkpoint（如 UCP atomic format）叠加**——minimal save + 可重配加载，量化 elastic / spot 场景下的 end-to-end MTBF 收益。
- **Future work 3**：**chaos engineering 测量**——在真实 failure trace（非均匀 Poisson、rack-level correlated）下测 recovery latency、checkpoint chain 损坏率、与训练 tail latency 的耦合。
- **Future work 4**：**扩展 optimizer / precision 族**——在 FP8、AdamW variant、multi-stage LR scheduler 下验证 gradient-only incremental 是否仍安全，并给出必要时的 fallback 全量策略。

## 相关

- **相关概念**：[[Checkpointing]]、[[Fault-Tolerance]]、[[ZeRO]]、[[Data-Parallelism]]、[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[Expert-Parallelism]]、[[MoE]]、[[Mixed-Precision-Training]]、[[Ring-AllReduce]]、[[Adam]]
- **同类系统**：[[GEMINI]]、[[CheckFreq]]、[[UCP]]、ByteCheckpoint、ECCHECK、MoC-System、MOETION、FlowCheck、CHECKMATE、JIT Checkpointing
- **训练框架**：[[DeepSpeed]]、[[Merak]]、nnScaler、Megatron-LM、[[Transformers]]
- **同会议**：[[FAST-2026]]
- **对比**：AdaCheck 与 [[GEMINI]] 同属 in-memory checkpoint 路线，但前者利用 redundancy + gradient incremental 追求 1S1C；与 [[UCP]] 解决不同痛点（最小保存 vs 并行重配），可正交组合