---
type: paper
name: SuperInfer
full_title: "SuperInfer: SLO-Aware Rotary Scheduling and Memory Management for LLM Inference on Superchips"
authors: [Jiahuan Yu, Mingtao Hu, Zichao Lin, Minjia Zhang]
venue: MLSys
year: 2026
tags: [llm-inference, slo, gh200, nvlink-c2c, offloading, scheduling]
source_pdf: "[[8f14e45fceea167a5a36dedd4bea2543.pdf]]"
source_md: "[[8f14e45fceea167a5a36dedd4bea2543]]"
---

# SuperInfer: SLO-Aware Rotary Scheduling and Memory Management for LLM Inference on Superchips (MLSys 2026)

> **一句话总结**：观察到 GH200 上 [[vLLM]] 式 PCIe offload 只用到 NVLink-C2C **<5%** 带宽、静态 WF/SF swap 策略无法兼顾 TTFT/TBT，SuperInfer 用 OS 启发的 **RotaSched**（VLT + LVF 主动 rotation）与 **DuplexKV**（eager block rotation + block-first layout + 全双工 batch transfer）把有效带宽拉到近 DRAM 极限，高负载下 TTFT SLO 达成率比 SOTA 高最多 **74.7%**，TBT 与吞吐持平或略优。

## 问题与动机

[[LLM]] serving 在严格 **TTFT** / **TBT** SLO 与有限 GPU memory 之间拉扯：高请求率下 [[KV-Cache]] 随序列长度线性膨胀，很快耗尽 Hopper HBM，引发 waiting queue 的 **HOL blocking** 与 SLO 违约。既有 SLO-aware scheduler（Sarathi-Serve、SOLA、LTR、LightLLM）通过优先级重排或 chunked prefill 缓解排队，但**默认所有请求驻留 GPU**——KV 装不下时，再好的调度也无法服务 backlog。

另一条路线是 **KV offload** 到 host DRAM（FlexGen、NEO、TokenFlow、Select-N 等），把有效内存扩到数百 GB。但两类硬伤并存：

1. **SLO-unaware**：多数系统被动响应 memory pressure，而非 latency urgency；Waiting-First（WF）压低 TTFT 却牺牲 TBT，Swapped-First（SF）保护 TBT 却几乎退化成 FCFS，swap 空间利用不足（Fig. 1）。
2. **PCIe-bound**：Gen5×16 单向约 32–64GB/s，swap 太慢，无法在高负载下及时清空 waiting backlog 或 rotary queue，尾延迟被 swap 带宽锁死（Fig. 2–3）。

NVIDIA **GH200 Superchip** 通过 **NVLink-C2C**（900GB/s 双向）把 Grace CPU DRAM 与 Hopper GPU 紧耦合，理论上可消除 swap 带宽瓶颈。但直接移植 PCIe offload 栈效果反常：[[vLLM]] 在 GH200 上有效 KV 传输仅 **~10GB/s**（<5% 峰值），而细粒度测量显示 C2C 在 ≥8MB 段可达 **~200GB/s/方向**（Fig. 4–5）。瓶颈在**软件栈**（[[PagedAttention]] 碎片化小段 + 串行 H2D/D2H + 数千次 `cudaMemcpyAsync` launch overhead），而非硬件。

作者 claim：Superchip 要发挥潜力，必须 **scheduling 与 memory movement 协同设计**——主动、SLO-aware 的 request rotation + 能喂满 C2C 的 KV rotation engine。

## 关键观察 / 隐含假设

- **观察 1：静态 offload 调度策略在 TTFT 与 TBT 间存在不可调和的偏置。** WF 抢占 running 请求 favor 新到达，TTFT 改善但 running 请求长时间 pause，TBT 恶化；SF 优先 resume swapped 请求，TBT 稳但 swap 空间 underutilize，TTFT 与 FCFS 相近（§3.1，Qwen2.5-32B + ShareGPT）。
  - **依赖假设**：生产框架（[[vLLM]]、[[SGLang]]）在 memory pressure 下仍主要用这类 SLO-unaware 二选一策略；SLO 违约同时来自 waiting queue 与 swapped queue 两类 HOL。
  - **可能失效场景**：若 baseline 已集成更复杂的 per-request deadline scheduler（FastServe、SHEPHERD）且 GPU 内存足够，offload 调度偏置问题不突出；极低 RPS 时 memory 不饱和，观察 irrelevant。

- **观察 2：offload 的 responsiveness 由 effective swap bandwidth 上限决定；PCIe 带宽是 SLO-aware serving 的根本天花板。** 模拟提高 swap 带宽超过 PCIe 极限后，P99 TTFT 与 TBT 同步下降；低带宽导致（a）waiting backlog 清除慢、（b）swapped queue 上新一轮 HOL blocking（§3.2）。
  - **依赖假设**：KV 传输量与请求长度正相关；高 RPS（论文主实验达 20+）下 GPU memory 必然成为瓶颈，offload 是刚需而非可选优化。
  - **可能失效场景**：短 context、低并发、或 aggressive [[KV-Cache]] 压缩/剪枝（InfiniGen、CacheGen）使 GPU 能装下全部活跃请求时，swap bandwidth 不再是主导瓶颈——但这类方法有损或难泛化。

- **观察 3：GH200 上现有 offload 路径严重 under-utilize NVLink-C2C——可达 ~200GB/s/方向，实测 ~10GB/s。** 根因是 [[PagedAttention]] 把 KV 切成 layer-first 的 64KB **segment**，需数千次独立 `cudaMemcpyAsync`；段 ≤64KB 时 C2C 带宽 <10GB/s，且 launch time 可超过 transfer time（§3.3、§4.3.1，Fig. 5、12）。
  - **依赖假设**：Grace DRAM 带宽（每 NUMA **384GB/s** half-duplex）是双向并发传输的实际上限，而非 C2C 900GB/s 标称值；block-first 合并后单段可达 4MB（Qwen2.5-32B），进入高带宽 regime。
  - **可能失效场景**：更小模型（segment 更小）、不同 page size、或未来硬件 DRAM 带宽提升后，合并收益比例会变；AMD MI300A 等 Superchip 的内存层次需重新 profile。

- **观察 4：并发 H2D/D2H 在 [[PagedAttention]] 共享 block table 下存在 data race，迫使 [[vLLM]]/[[SGLang]] 串行 swap-in/out。** swap-in 目标 HBM block 可能与 swap-out 源 block 重叠（Fig. 13），这是全双工 C2C 未被利用的软件依赖，而非硬件限制。
  - **依赖假设**：KV 按 block 增量写入——已满 block（synced）不再修改，仅最后 dirty block 在 generation 中更新；eager 提前 swap-out synced block 可在 preempt 时直接 discard HBM 副本而不丢数据。
  - **可能失效场景**：若模型或 serving 栈引入 in-place KV 重写、跨 block 原地更新、或 speculative decoding 回滚导致 synced block 失效，eager rotation 的正确性前提需重证。

- **假设 1：LLM serving on GH200 可类比 OS：request≈thread，HBM≈L3，Grace DRAM≈main memory，KV≈thread data；time-slicing 式主动 rotation 比 OOM 时才 passive preempt 更利于 SLO。**
  - **证据强度**：**中**——类比启发 RotaSched 设计，但 LLM rotation 代价是毫秒级 KV 传输而非纳秒级 context switch；论文用 VLT 量化「lag」并证明 LVF 有效，未与 OS scheduler（CFS/EEVDF）做形式化对比。

- **假设 2：Virtual Lag Time (VLT) + Largest-VLT-First (LVF) 能在单次 metric 下联合权衡 TTFT 与 TBT，无需 oracle 生成长度。**
  - **证据强度**：**中强**——α、βB、βF 调参实验（Fig. 18–20）展示可控 trade-off；默认 α=3、βB=0、βF=0.5 在 ShareGPT 上平衡。但参数无自动适配，且未在异构 SLO 混合 workload 上验证。

## 核心方法

SuperInfer 在 [[vLLM]] v0.6.6.post1 上实现，由 **RotaSched** 与 **DuplexKV** 协同组成（Fig. 6）。

### RotaSched：SLO-aware rotary scheduler

**从 passive preempt 到 proactive rotation**：传统系统在 KV 需求超过 HBM 时才 offload/discards 后来的请求；即使 HBM 够装 running 请求，waiting 请求接近 TTFT SLO 违约也不会触发抢占。SuperInfer 引入 **rotary state**——请求暂停 GPU 执行、KV 暂存 Grace DRAM、等待下次 rotation——把 preemption 从 OOM 兜底变为主动 SLO 管理手段。

**Virtual Lag Time (VLT)**：借鉴 OS 中 EEVDF 的 lag 思想，但针对 LLM 双目标 latency（TTFT/TBT）与昂贵 rotation 代价重新设计。对 waiting / rotary / running 三类请求分别用 arrival、last-token、run 起始时间与 SLO 阈值（SB=TTFT、SF=TBT）及容忍系数 βB、βF 计算 VLT；α 控制 TBT 相对 TTFT 的敏感度。VLT>0 表示「落后」，优先执行；VLT<0 表示「超前」，成为 preempt 候选。

**Largest-VLT-First (LVF)**：每 engine iteration——① 若 HBM 够装全部请求则退化为 FCFS；② 按 VLT 降序排序；③ 从头部选 rotary/waiting 请求填满 `BHBM + Bxfer`；④ 从尾部 preempt VLT<0 的 running 请求直至凑够 swap 块。**Bxfer**（默认 2400 blocks）反映每轮可旋转的 KV 块预算，与 swap 带宽直接挂钩：C2C 高带宽才撑得起大 Bxfer，否则 rotation 本身成瓶颈（Fig. 17、21）。

### DuplexKV：全双工 KV rotation engine

针对 §4.3.1 诊断的三类软件瓶颈：

1. **Eager block rotation**：后台提前把 **synced** block swap-out 到 DRAM 并标记 HBM 副本可 discard；preempt 时仅传最后 **dirty** block。配合 CPU 侧 block table 副本，打破 swap-in 与 swap-out 的 HBM block 依赖，允许两路 CUDA stream **并发全双工**传输（Fig. 13）。

2. **Block-first layout + batched transfer**：将 [[PagedAttention]] 的 layer-first KV 重排为 block-first，把同 block 跨 NL 层的 64KB 小段合并为 **4MB** 连续区；用 `cudaMemcpyBatchAsync` 单 kernel 发起单向全部 descriptor，消除 per-segment launch overhead（Fig. 14）。扩展 PagedAttention kernel 支持新 stride。

3. **Cross-iteration pipeline**：iteration-t GPU 执行 t−1 准备的 batch 时，host 侧 scheduler + DuplexKV 并行准备 t+1 batch（两路 transfer stream），把 schedule（~7.6ms）与 transfer（~15.8ms）藏在 model execution（~69.8ms）后；全实验仅 **0.021%** iteration 发生 overlap 不足导致 stall（§5.3.4）。

## 设计取舍

- **主动 rotation vs 被动 preempt**：为 SLO-vulnerable waiting 请求腾出 HBM，必须频繁 preempt 长运行请求并支付 KV 传输；低 RPS memory 充足时退化为 FCFS，无额外开销。高 RPS 下收益巨大，但 rotation 频率与 Bxfer 设置不当会把 transfer 变成新瓶颈（SuperInfer w/o DuplexKV + 大 Bxfer 的 TBT 崩溃，Fig. 17）。

- **全量 KV offload vs 有损压缩**：DuplexKV 保留完整 KV，无 InfiniGen/CacheGen 类精度风险，代价是 Grace DRAM 占用大（实验分配 **400GB/480GB** 给 KV）和传输字节数高——靠 C2C 高带宽与 layout 优化消化。

- **GH200 专用 co-design vs 通用 serving 栈**：深度绑定 NVLink-C2C 全双工、Grace half-duplex DRAM、单 Superchip NUMA affinity（`numactl`）；移植到 PCIe GPU 或 disaggregated PD 架构需重写 transfer engine 与 Bxfer 逻辑。

- **vLLM  fork vs 独立 runtime**：继承 [[PagedAttention]]、[[Chunked-Prefill]] 与 production 生态，但 block-first layout、eager rotation、LVF scheduler 均是非 trivial patch；与 [[SGLang]]、[[TensorRT-LLM]] 原生栈集成成本未评估。

- **VLT 参数暴露 vs 自动调优**：α/βB/βF 给部署方场景化 trade-off（TTFT-sensitive 用 α≤1，平衡 sweet spot α=3），但论文明确**不**根据 query 分布预测调参，而是 online 响应 pressure——运维需人工标定或另建 tuner。

- **边界条件**：在 **单/双 GH200 Superchip、Poisson 到达、TTFT SLO 5s / TBT SLO 100ms、dense+MoE 三模型、ShareGPT/LMSYS trace** 下最优雅；极低 RPS 与 baseline 持平；Unified Memory（附录 D）因 bandwidth cliff 反而严重恶化 TBT，说明 explicit offload 管理不可替代。

## 实验与结果

**设置**：NVIDIA GH200 NVL2（144GB HBM + 480GB DRAM/Superchip）；模型 LLaMA-3-8B、Qwen2.5-32B、Mixtral-8x7B；数据集 ShareGPT、LMSYS-Chat-1M；Poisson 到达；metric 为 TTFT/TBT **SLO attainment rate**（阈值 5s / 100ms）。

**主结果（Fig. 16）**
- SuperInfer **TTFT SLO 达成率显著高于所有 baseline**，高 RPS 下最高 **+74.7%**；**TBT SLO 优于或可比** vLLM、TensorRT-LLM、LightLLM、NEO。
- LTR TTFT 最好但 **严重牺牲 TBT**（静态 deadline 优先级）；LightLLM 高 RPS 下 TBT 稳定因其避免 harmful eviction，但 TTFT 仍弱于 SuperInfer；TensorRT-LLM TBT 强但高 RPS TTFT 因 lazy preempt 退化。

**模块消融（Fig. 17，Qwen2.5-32B + ShareGPT）**
- 仅 RotaSched + vLLM offload（Bxfer=300）：TTFT 明显改善，TBT 持平——证明 **调度 alone 有效**。
- RotaSched + 大 Bxfer + vLLM offload：TBT **崩溃**——证明 **无 DuplexKV 则高 rotation 预算反噬**。
- 完整 SuperInfer：TTFT 进一步跃升且 TBT 保持。

**DuplexKV 带宽（Table 1，16GB 双向 KV）**
- Naive（vLLM 式 64KB segment）：理想带宽 **5.6%**，E2E **37.4×** ideal。
- MS → MS+MK：合并段与 batch kernel 逐步提升单向带宽。
- **DuplexKV**：近理想双向带宽，E2E **1.1×** ideal（eager rotation 解锁全双工）。

**参数与扩展**
- α↑ 改善 TBT、损害 TTFT（Fig. 18）；βF↑ 损害新请求 TTFT（Fig. 19）；βB↑ 损害 rotary 请求 TBT（Fig. 20）。
- Bxfer↑ 显著降低 P99 TTFT/TBT（Fig. 21），验证高 swap bandwidth 必要性。
- **TP=2**（NVLink 900GB/s）：TTFT/TBT SLO 仍全面优于 vLLM（Fig. 22）——RotaSched/DuplexKV 与 [[Tensor-Parallel]] 正交。
- **吞吐**：与 vLLM 相当或略优，高 RPS 最高 **+29.2%**（Fig. 23）——快 rotation 给 [[Chunked-Prefill]] 更多 batching 机会。

## Critical Analysis

### 论证链条

链条：**测量**（WF/SF 偏置、PCIe 带宽天花板、GH200 上 vLLM <5% C2C 利用率）→ **设计**（LVF 主动 rotation 回应 SLO 双目标；DuplexKV 回应碎片化+串行+launch overhead）→ **结果**（TTFT +74.7%、TBT 可比、带宽 1.1× ideal、消融闭合）。

最强支撑是 Fig. 17 三阶消融：把「好调度 + 烂 transfer 会更差」与「调度+引擎协同才成立」拆清楚；Table 1 把 DuplexKV 各优化项与全双工 race 消除一一对应。主结果跨 3 模型 × 2 数据集 × 多 RPS，比只报单点更有说服力。

薄弱环节：将 GH200 profile 结论外推为「Superchip 普遍需要此类 co-design」，仅测 NVIDIA GH200 NVL2；Pie（同平台 KV spill）因无公开代码未对比，最近邻 baseline 仍是 **PCIe 时代思路移植的 vLLM offload**。

### 假设压力测试

**Workload**：ShareGPT / LMSYS 真实对话 trace，但 SLO 统一 5s/100ms；混合 TTFT-sensitive 与 TBT-sensitive tenant、多 SLO 等级（Tempo、SHEPHERD 场景）未测。请求长度分布固定于数据集采样，无 adversarial 超长单请求压测 Grace DRAM。

**硬件**：强依赖 **NVLink-C2C + Grace DRAM 带宽曲线**；H100/H200 PCIe 机器上 DuplexKV 的全双工与 block-first 收益需重新测量，Bxfer=2400 可能完全不适用。实验单机/双卡 TP，无大规模集群、无 [[Disaggregation]] prefill-decode 分离。

**规模**：最高 RPS 约 20（Qwen2.5-32B）；更高并发下 host 侧 scheduler + 双 stream transfer 是否成为新瓶颈，论文仅报 0.021% stall 比例，未给 host CPU 利用率或 P99 scheduler latency。

**模型**：测了 MoE（Mixtral），但 NEO 不支持 MoE 故缺对称 baseline；MTP、MLA、量化 KV 未集成。附录 D 证明 UM 不适合 serving，但未测 FP8/INT8 KV 对 segment 大小与传输路径的影响。

### 实验可信度

**优点**：baseline 覆盖 production（vLLM V1、TensorRT-LLM）与 SLO-aware 代表（LightLLM、LTR）及 offload 代表（NEO）；统一启用 [[PagedAttention]] + [[Chunked-Prefill]]；排除缺代码/缺特性的系统并说明理由；artifact 提供 lite（~5h）与 full（~30h）复现路径。

**限制**：
- 缺 **Pie**、HeteGen、Select-N 等同平台 Superchip 工作对比——「比 PCIe 移植好多少」清楚，「比 GH200 专用竞品好多少」不充分。
- 主 metric 为 **SLO attainment rate**，对 P99 绝对延迟分布、per-request 违约原因分解（waiting vs rotary vs compute）着墨较少（部分在 β 敏感性 Fig. 19–20）。
- VLT 参数 **手工固定**，未展示 production trace 上 auto-tune 或 robustness；α=3 作为 sweet spot 的泛化性靠多模型主结果间接支持，非系统化 sensitivity grid。
- 能耗、Grace CPU 占用、DRAM 带宽争用与 OS 抖动——论文未讨论；对 datacenter TCO 结论有限。

### 系统性缺陷

- **运维复杂度**：block-first PagedAttention、eager rotation block table、双 stream pipeline、LVF 每 iteration 全量排序——比 stock [[vLLM]] 显著复杂；论文未讨论 debug/trace 工具或错误恢复（transfer 失败、DRAM OOM）。
- **多租户公平性**：LVF 按 VLT 全局排序，未讨论 per-tenant 隔离、priority class 或 SLO 违约的 blame attribution；大 Bxfer rotation 是否放大邻居干扰未测。
- **正确性边界**：eager discard HBM synced block 依赖「已满 block 不变」；与 speculative decoding rollback、prefix cache 共享 block、或 dynamic LoRA 组合时的 invariant 论文未验证。
- **故障恢复**：KV 大量在 Grace DRAM，GPU worker 崩溃后重建 block table 与 residency 状态的成本未讨论。
- **可移植性**：深度绑定 CUDA 12.8、`cudaMemcpyBatchAsync`、GH200 NUMA；其他 Superchip（MI300A）或 CXL 附挂内存需重做 characterization（§3.3 方法可复用，结论不能直接搬）。

## 局限与 Future Work

- **局限 1**：评估仅限 **NVIDIA GH200**；其他 tightly-coupled GPU–CPU 架构需重新 profile C2C/DRAM 带宽曲线与 race 模式。
- **局限 2**：基于 **vLLM fork** 实现，未证明可 plug-in 到 [[SGLang]]、TensorRT-LLM 等栈而不重写 memory manager。
- **局限 3**：VLT 参数（α、βB、βF、Bxfer）需 **场景手工调优**；论文不尝试从 workload 分布学习最优参数。
- **局限 4**：Grace DRAM 大额预留（400GB KV）+ 保守 80GB OS margin——边缘或小内存 Superchip 配置下策略需收缩。
- **局限 5**：未与 **有损 KV 压缩**（InfiniGen、CacheGen）或 **跨 GPU NVLink offload**（Aqua）做正交组合或 Pareto 对比。
- **局限 6**：Unified Memory 路径实测 **严重 TBT 退化**（附录 D），说明 hardware-managed migration 不适合当前 LLM attention 访问模式。

- **Future work 1**（论文隐含）：将 RotaSched/DuplexKV 与 **prefill-decode disaggregation**、[[Prefix-Caching]]、speculative decoding 组合，验证 rotation 与 rollback/prefix 共享的交互。
- **Future work 2**：在 **MI300A、未来 C2C 代际** 上复用 §3.3 characterization 方法论，建立 Superchip offload 的 portable performance model。
- **Future work 3**：探索 **VLT 参数在线自适应**（如根据 waiting queue 长度与 SLO 违约率反馈调节 α/Bxfer），减少运维手工标定。
- **Future work 4**（可验证延伸）：在 production 多租户 trace 上测量 **per-tenant SLO fairness** 与 rotation 导致的 neighbor tail latency 放大系数；对比 LVF 与 per-tenant weighted fair queueing。

## 相关

- **相关概念**：[[KV-Cache]]、[[PagedAttention]]、[[Continuous-Batching]]、[[Chunked-Prefill]]、[[Tensor-Parallel]]
- **同类系统**：[[vLLM]]、[[SGLang]]、TensorRT-LLM、Pie、NEO、LightLLM、FlexGen、TokenFlow、Sarathi-Serve
- **同会议**：[[MLSys-2026]]
- **对比**：PCIe offload + passive preempt（vLLM/NEO）vs GH200 KV spill（Pie）vs **SLO-aware active rotation + 全双工 DuplexKV**（SuperInfer）