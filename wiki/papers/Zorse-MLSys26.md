---
type: paper
name: Zorse
full_title: "Zorse: Optimizing LLM Training Efficiency on Heterogeneous GPU Clusters"
authors: [Runsheng Benson Guo, Utkarsh Anand, Khuzaima Daudjee, Rathijit Sen]
venue: MLSys
year: 2026
tags: [distributed-training, heterogeneous-gpu, pipeline-parallelism, zero, llm-training]
source_pdf: "[[26657d5ff9020d2abefe558796b99584.pdf]]"
source_md: "[[26657d5ff9020d2abefe558796b99584]]"
---

# Zorse: Optimizing LLM Training Efficiency on Heterogeneous GPU Clusters (MLSys 2026)

> **一句话总结**：异构 LLM 集群上 [[Pipeline-Parallelism|PP]]+ZeRO 存在经典 trade-off（ZeRO-2 通信省但显存爆、ZeRO-3 显存省但每层每 microbatch AllGather）；Zorse 用 **Pipeline-Efficient ZeRO DP**（ministage 顺序 interleaving + CPU offload + interleaved optimizer update）同时逼近 ZeRO-3 显存与 ZeRO-2 通信，planner 自动搜配置，在 128 GPU 三类代表集群上相对 TorchTitan-Het、[[HexiScale-MLSys26]]、Cephalo 吞吐最高 **3×**，HFU 接近同构子集群。

## 问题与动机

组织往往只能凑出 **异构 GPU 集群**（不同代际、跨 region、节点间带宽可差 **35×**），但 Megatron、DeepSpeed、TorchTitan 等 3D 并行框架默认同构：每卡等量 workload、对称 parallel group。现实约束包括：GPU 发布周期快、云上单次难订 >32 卡高端 GPU、只能跨代际拼集群（[[HexiScale-MLSys26]]、Metis、Cephalo 等已有探索）。

异构训练需同时处理三重不对称：**算力**（如 V100 比 T4 快 3×+）、**显存**（H100 TFlops 为 A100 的 3× 但显存仅多 15%）、**网络**（NVLink/NVSwitch vs PCIe、跨 region 慢链路）。现有方案通常只做好算力均衡，难以同时解决网络与显存瓶颈。

在 PP 跨慢链路、DP 组内要快链路的常见布局下，ZeRO 与 PP 组合有尖锐 trade-off：

- **PP+ZeRO-2**：每层一次 AllGather，通信接近最优；但参数全量驻留 GPU，大模型或快卡算力/显存比失衡时 **OOM**（Figure 1，8 V100+8 T4 上随 Llama 规模增大）。
- **PP+ZeRO-3 / FSDP**：参数分片省显存；但 PP 把 batch 切成 M 个 microbatch，**每层每个 microbatch 都要 AllGather**，通信随 M 线性放大。
- **[[Tensor-Parallelism|TP]]**：进一步分片显存，但层间 all-to-all 频繁；Figure 2 显示除 8×A100 NVSwitch 外，多数 AWS VM 上 TP 的 HFU 显著低于 DP+ZeRO-3。

作者 claim：需要一种 **同时通信高效且显存高效** 的 PP+DP 集成，外加自动 planner 在巨大搜索空间里找异构最优配置。Zorse 即为此设计，基于 PyTorch FSDP 实现并开源。

## 关键观察 / 隐含假设

- **观察 1**：PP 与 ZeRO 的冲突本质是 **参数 gather 频率 vs 驻留显存**——ZeRO-2 省通信但 materialize 全 stage 参数；ZeRO-3 省显存但 gather 频率 × microbatch 数（Table 1 对比 Zorse / PP+ZeRO-2 / PP+ZeRO-3）。
  - **依赖假设**：若改变 schedule，使任意时刻 GPU 上只保留 **当前 + 下一个 ministage** 参数，仍可将 AllGather 维持在 **每层一次**（非每层每 microbatch）。
  - **可能失效场景**：ministage 过细导致 pipeline bubble 与 offload 开销主导；或 ministage 过少退化为 PP+ZeRO-2 显存行为。

- **观察 2**：异构集群中 **快 GPU 常被显存而非算力卡住**——H100 算力 3× A100 但显存仅多 15%，HexiScale 等 ZeRO-2 方案无法让 H100 按算力比例承担 layer（Cluster A 分析）。
  - **依赖假设**：通过 ministage 级 CPU offload + 异构 PP 不对称分 stage，可在不引入 TP 的前提下，把 layer 按各 GPU **有效吞吐**（算力×可用显存）重新分配。
  - **可能失效场景**：单层参数超过单卡显存+host offload 上限时，仍需 TP 或更细粒度分片——论文明确 **不支持 TP**（Section 6.2）。

- **观察 3**：在常见云 VM 上，**TP 的 HFU 仅在 NVSwitch 级互联下与 DP 可比**；异构集群大量是 PCIe 或跨 region 链路（Figure 2、Cluster C 跨 region）。
  - **依赖假设**：异构 LLM 预训练的主瓶颈是 **跨组 collective + 显存**，而非层内 TP；Pipeline-Efficient ZeRO DP 优于 PP+TP 即使 Cluster A 这种节点内有 NVLink 的环境（Figure 11）。
  - **可能失效场景**：单层无法放入单卡、或 intra-node 带宽极高且 sequence 极长时，TP+Sequence Parallelism 可能更优——论文仅在 Cluster A 7B/13B 上对比，且承认超大模型 future work 需 DP+TP。

- **观察 4**：异构集群的 **DP 组应沿高带宽子图划分、PP 沿低带宽割边**，且各 DP 组 batch size 可不同以细粒度均衡负载（与对称 3D mesh 假设相反）。
  - **依赖假设**：把集群建模为带宽加权全连接图，用 min-k cut（SPLIT 近似）切 k 个 DP 组，再枚举 ministage/batch 配置，足以覆盖代表场景。
  - **可能失效场景**：动态网络拥塞、多 tenant 干扰、或 GPU 故障导致拓扑变化时，静态 planner 结果过时；论文未讨论在线重规划。

- **假设 1**：Host CPU 内存 ≫ GPU VRAM，且 PCIe **~16 GB/s/GPU** 足以通过 prefetch 隐藏参数与 layer-boundary activation offload。
  - **证据强度**：**中**——最大评估模型需 ~130 GB host memory，8×A100 VM 有 1152 GB；Figure 9 报 offload 开销 <3%，但未测极端 ministage 数或慢 PCIe 机型。

- **假设 2**：训练 workload 为 **decoder-only LLM 预训练**（Llama/GPT，global batch **1M tokens**，FP16 mixed precision，activation checkpointing）。
  - **证据强度**：**强**——三集群、多模型规模一致设定；GPT 变体在 Cluster A 验证趋势类似，但无 MoE、多模态或 RL 训练。

## 核心方法

### Pipeline-Efficient ZeRO DP

Zorse 的核心是对 PP 与 ZeRO-based [[Data-Parallelism|DP]] 的重新 schedule，称 **Pipeline-Efficient ZeRO DP**（Figure 3）：

1. **Interleaved pipelining（非 1F1B）**：每 GPU 挂多个 **ministage**；对某一 ministage **顺序处理完所有 microbatch 的 forward**，再切下一 ministage；backward 逆序同理。与 Megatron interleaved 1F1B 不同——后者在 ministage 间交错，若参数分片会频繁 regather。
2. **两 ministage 驻留**：非活跃 ministage 参数 offload 到 CPU；GPU 上同时只保留当前 ministage 与 **prefetch 的下一个 ministage** 参数，显存随 ministage 数增加趋近 PP+ZeRO-3，通信仍为每层一次 AllGather（类 PP+ZeRO-2）。
3. **Interleaved optimizer update**（Figure 4）：每个 ministage backward 结束立即做 optimizer step 并释放 gradient，而非等整条 pipeline backward 完成——降峰值显存，并让 DP 组内 gradient reduce 与后续 ministage 计算 overlap。
4. **Activation checkpointing + CPU offload**：层内 activation 仍 checkpoint；**层边界 activation** 也 offload，只保留当前与 prefetch microbatch 的边界张量，缓解 sequential forward-all-then-backward 的 O(B×L×S×H) 显存（Section 3.1.3）。

实现上修改 PyTorch FSDP：forward 后 reshard/offload ministage 参数；延迟 resharding 至该 ministage 所有 microbatch backward 完成；per-ministage optimizer；层粒度顺序 gather 以 overlap 通信与计算（Section 4.1、4.3）。

### Heterogeneous Pipeline Parallelism

- Stage 间 **GPU 数量与型号可不对称**；microbatch 按各 GPU 相对 layer runtime **many-to-many** 重分配（完成时间第 i 快的 microbatch 分给剩余算力第 i 大的 GPU）。
- 跨 stage 通信用 **NCCL + GLOO 混合**：NCCL P2P 在异构 PP 的 cyclic dependency 下可能死锁，GLOO nonblocking P2P 打破环；GLOO 不走 NVLink 但主要用于 pipeline warmup，饱和后计算可掩盖（Section 4.2）。

### Planner（两阶段）

1. **Profiling**：并行测节点内/跨节点带宽；各 GPU 上 profile layer runtime 并线性外推 batch size；建模 AllGather/ReduceScatter（ring 假设）。
2. **Phase 1 — Cluster partitioning**：带宽加权图上做 **min-k cut**，SPLIT 贪心近似（O(N⁴)），对 k=1..N 求割，使高带宽边留在 DP 组内。
3. **Phase 2 — Model configuration**：按各组聚合算力比例分 layer → 等长 ministage → round-robin 排 stage 顺序（高 intra-group 带宽组优先，减少 startup AllGather）；枚举 batch × ministage 数（O(B·L)），用 latency + memory 模型选最快且不超显存方案。Planner 全程 **<3 分钟**，latency 模型误差 **<10%**（Figure 10、12）。

## 设计取舍

- **Ministage 顺序 schedule vs 1F1B interleaving**：牺牲传统 interleaved PP 的部分 bubble overlap，换取 ZeRO-3 级显存而不增加 AllGather 次数；ministage 数是可调旋钮（Figure 9：max interleaving 显存降 **40%**、吞吐仅降 **20%**）。
- **CPU offload vs 纯 GPU**：显著扩展可训练模型上界，但依赖 host RAM 与 PCIe；PyTorch 原生 CPU offload 会阻塞 GPU，Zorse 用独立 CUDA stream + GPU 上 optimizer step 规避（Section 4.4）。
- **PP+DP vs PP+TP**：默认不用 TP，避免异构环境下 all-to-all 开销；Cluster A（理想 TP 环境）上 PP+DP 仍优于 PP+TP（Figure 11），因层输入 gather/reduce 的串行依赖难以完全 overlap。
- **精确 min-k cut vs SPLIT 近似**：保证 2−2/k 近似比，可一次 pass 算所有 k；可能错过全局最优分区，但 planner 总时间可控。
- **边界条件**：最适合 **memory 与 cross-group 带宽双受限** 的异构预训练；单层超单卡、需 TP/context parallelism 的场景未覆盖；要求 VM 有足够 CPU RAM 做 offload pool。

## 实验与结果

- **设定**：Llama/GPT 至 **65B**；三集群——A：4 H100+16 A100（小集群高端混搭）；B：8 A100+16 A10G+16 V100+24 T4（中集群三代混搭）；C：**128 GPU** 双 region（16 A10G+48 T4 ‖ 16 V100+48 T4）；global batch 1M tokens，FP16，activation checkpointing；序列长 A/B/C 分别为 4096/1024/512。
- **主结果**（Table 3）：相对 TorchTitan-Het、[[HexiScale-MLSys26]]、Cephalo，Zorse 吞吐最高 **3×**；Cluster B **1.5×–4×**；Cluster C 稳定 **~1.5×**；大模型（65B）在异构集群避免 OOM，基线多 OOM 或需牺牲配置。
- **Cluster A 机理**：TorchTitan-Het ZeRO-2+TP 小模型尚可、大模型 OOM；HexiScale PP+ZeRO-2 显存压 H100；Cephalo 全集群 ZeRO-3 受 **35×** 内外带宽差 AllGather 瓶颈；Zorse 节点内 DP、跨节点 PP + ministage offload 兼顾三者。
- **Cluster scaling**（Figure 7）：向训练组逐步加入更快 GPU，吞吐随集群扩大上升，HFU 多数稳定或提升——异构拼池不必然牺牲效率。
- **vs 同构子集群**（Figure 8）：各 GPU 类型在完整异构集群上的 HFU 与仅用同构子集群训练 **相当**，说明负载均衡有效。
- **Ministage 消融**（Figure 9，同构 16 A100/A10G）：验证 Pipeline-Efficient ZeRO DP 在 ZeRO-2/3 之间的连续 trade-off 曲面；offload 开销 **<3%**。
- **Planner**：最大模型优化 **<3 分钟**，profiling 占主导但随 GPU 数 sublinear；memory 模型亦 **<10%** 误差。

## Critical Analysis

### 论证链条

观察（PP+ZeRO 通信-显存对立 + 异构三重瓶颈）→ Pipeline-Efficient ZeRO DP（ministage schedule 降低 gather 频率同时限制驻留参数）→ 异构 PP + 图分割 planner → 三集群最高 3× 吞吐，链条整体闭合。最强证据是 **Table 3 多基线多集群 + OOM 对比 + Figure 9 机理解释 ministage 旋钮**；较弱环节是「SPLIT 分区 + 启发式枚举 → 全局近最优」——latency 模型准确但未证明分区本身最优。

### 假设压力测试

- **已证明**：Pipeline-Efficient ZeRO DP 在同构集群上相对 PP+ZeRO-2/3 的显存-吞吐权衡（Figure 9）；异构集群相对 SOTA 异构系统的吞吐优势；HFU 与同构子集群可比（Figure 8）。
- **可能失效（推断）**：① **Host RAM 不足** 或 PCIe 远慢于 16 GB/s 时，ministage offload 可能从 <3% 变为主导开销；② **极浅模型**（层数不足以切多个 ministage/stage）时优势缩水，HexiScale 在 33B/40 层已显 coarse；③ **动态集群**（节点增减、网络拥塞）下静态 planner 无重规划；④ **单层大于单卡显存** 时必须 TP——论文承认并列为 future work，当前对 65B decoder 足够但未证泛化到更大 dense 或 MoE。

### 实验可信度

- **强项**：三类有代表性的异构拓扑（含跨 region 128 卡）；基线覆盖 3D 并行（TorchTitan-Het）、异构专用（HexiScale）、ZeRO-3 异构（Cephalo）；含 GPT 架构泛化、cluster scaling、同构对照、planner 精度与耗时。
- **弱点**：Table 3 为 TFlops/HFU 摘要，具体加速比随模型/集群变化大（「最高 3×」为峰值表述）；基线配置由各自系统 planner/手工选最优，**调参公平性**论文未逐项披露；无 MoE、无 fine-tuning、无 fault tolerance 或 straggler 实验；端到端训练收敛/loss 曲线未报告，仅吞吐与利用率。

### 系统性缺陷

- **故障与弹性**：论文未讨论节点失败、planner 重跑、或训练中途集群变化；对比 FlexTrain 等 elastic 场景未覆盖。
- **尾延迟与 straggler**：异构 PP 的 microbatch 重分配启发式在严重 straggler 下是否稳定，未单独评估。
- **多 tenant / 网络干扰**：带宽 profile 为静态测量，生产共享集群下 AllGather 与 offload 争抢带宽的行为未量化。
- **运维复杂度**：ministage、offload stream、NCCL/GLOO 混合、per-ministage optimizer 显著增加 FSDP 状态机复杂度；开源可缓解但论文未报告生产部署经验。
- **TP 缺失**：对超大 layer 或 embedding 表极端情况，系统完整性依赖未来 DP+TP 扩展（Appendix 7 讨论方向）。

## 局限与 Future Work

- **局限 1**：**不支持 [[Tensor-Parallelism|TP]]**；层无法放入单卡时 PP+DP 仍会 OOM，需人工换框架或等扩展。
- **局限 2**：依赖 **充足 host CPU 内存** 与有效 PCIe prefetch；极小内存 VM 或 CPU-starved 配置可能不适用。
- **局限 3**：Planner 基于 **静态 profile + 近似图分割**，无运行时自适应；GLOO PP 通信在 warmup 阶段有额外开销。
- **局限 4**：评估限于 **FP16 预训练** 与特定 global batch/seq len；未覆盖 MoE EP、RL、多模态或 fine-tuning memory 模式。
- **Future work 1**（论文 Section 6.2）：在每组 GPU 内支持 **DP+TP（含 context parallelism）**，应对单层超大无法切 ministage 的场景。
- **Future work 2**：在 **动态/弹性集群** 上测量 planner 重配置频率与 offload 行为，并与静态 plan 比较端到端 job time。
- **Future work 3**：对 **MoE / 超 65B** 模型测量 ministage offload 与跨 region collective 的敏感性，验证「不用 TP」假设的边界。

## 相关

- **相关概念**：[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、ZeRO、FSDP、[[Activation-Checkpointing]]、ministage pipelining、HFU
- **同类系统**：[[HexiScale-MLSys26]]、Metis、Cephalo、Megatron-LM、TorchTitan、Whale、Sailor、[[FlexTrain-MLSys26]]
- **同会议**：[[MLSys-2026]]
- **对比**：HexiScale/Metis 用 ZeRO-2+TP 异构 3D 并行；Cephalo 用 ZeRO-3 但无 PP、靠 gradient accumulation 扩 batch；Zorse 用 Pipeline-Efficient ZeRO DP 同时压低 PP+ZeRO 组合的通信与显存，并显式优化跨 region PP