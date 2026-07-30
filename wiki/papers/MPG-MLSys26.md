---
type: paper
name: MPG
full_title: "MACHINE LEARNING FLEET EFFICIENCY: IMPROVING TPU SYSTEMS AT SCALE WITH ML PRODUCTIVITY GOODPUT"
authors: [Arissa Wongpanich, Tayo Oguntebi, Jose Baiocchi Paredes, Yu Emma Wang, Phitchaya Mangpo Phothilimthana, Ritwika Mitra, Zongwei Zhou, Naveen Kumar, Vijay Janapa Reddi]
venue: MLSys
year: 2026
tags: [ml-fleet, tpu, goodput, scheduling, observability]
source_pdf: "[[d1fe173d08e959397adf34b1d77e88d7.pdf]]"
source_md: "[[d1fe173d08e959397adf34b1d77e88d7]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# MPG：机器学习集群效率——以 ML 生产力有效吞吐改进大规模 TPU 系统（MLSys 2026）

> **原题**：MACHINE LEARNING FLEET EFFICIENCY: IMPROVING TPU SYSTEMS AT SCALE WITH ML PRODUCTIVITY GOODPUT

> **一句话总结**：warehouse-scale ML fleet 上「GPU busy」≠ 有效进展，Google 提出 **ML Productivity Goodput (MPG)**，分解为 Scheduling/Runtime/Program Goodput；论文以内部 TPU workload 的生产案例说明如何定位瓶颈，而非公开可复现的跨云基准。

## 问题与动机

ML fleet（数千 [[TPU]]/DSA）同时面临硬件异构、workload 异构、软硬件共演进；传统 TOPs/W、occupancy 无法解释「优化单 job 损害 aggregate efficiency」。作者需要可分解、可解释、可行动的全局效率指标，驱动 compiler/runtime/scheduler/model 协同。

## 关键观察 / 隐含假设

- **观察 1：ML workload 为 bulk-synchronous、强耦合栈，且 job 需全部申请芯片才启动——初始化/checkpoint 等 runtime 空转会直接吞噬 goodput。**
  - **依赖假设**：forward progress 可用「有效训练/推理步」量化，而非 wall-clock 占卡时间。
  - **可能失效场景**：异步/弹性训练、partial allocation 新调度范式下 SG 定义需改写。

- **观察 2：fleet 组成一年内剧变（extra-large job 占比升），segment 分析（accelerator 代际、topology size、framework、phase）是找瓶颈前提。**
  - **依赖假设**：内部 telemetry 可跨层关联同一 job 的 SG/RG/PG。
  - **可能失效场景**：外部云客户无同等可观测性时 MPG 难落地。

- **观察 3：分解 MPG 暴露 hidden 问题：例如 preempt 调优抬 SG、Pathways 迁移抬 RG、compiler comm-compute overlap 抬 PG——aggregate metric 会掩盖。**
  - **依赖假设**：各分量独立可优化且近似可加解释。
  - **可能失效场景**：强耦合优化（如 fusion 影响调度）时分量非独立。

- **假设 1：MPG 改进与真实 fleet 效率改进对齐（非 gaming metric）。**
  - **证据强度**：**中**——生产案例丰富但细节受 Google 内部数据限制。

## 核心方法

**MPG**：类比 iron law，将 fleet 效率拆为 **Scheduling Goodput (SG)**（卡分配/排队有效进展）、**Runtime Goodput (RG)**（framework/runtime 步进）、**Program Goodput (PG)**（compiler 生成代码效率）。

**Anatomy**：自 accelerator → scheduler → runtime/compiler → framework → model/data 分层 segment。

**Optimization lifecycle**：测 baseline → 定位低效层 → 全栈改动 → 再测 MPG 验证。

## 设计取舍

- **Goodput vs utilization**：更可行动，但定义/归一化复杂，跨云厂商难标准化。
- **Google TPU 案例 vs vendor-agnostic**：方法论宣称通用，实证高度绑定 TPU/Pathways/XLA。
- **Aggregate fleet vs per-tenant SLO**：分解可看 workload 特征，但公平性/隔离未深谈。
- **边界条件**：内部 workload 为主；GPU fleet 仅方法论外推。

## 实验与结果

以下的 metric 是 Scheduling/Runtime/Program Goodput 与 throughput/FLOPS utilization；baseline 是同一内部 TPU fleet 的 workload segments、既有 utilization metrics 或引用部署的优化前版本，boundary 是 Google production TPU workloads，不能视为跨云供应商 benchmark。

- 调度：各 job size **SG >95%**（careful preemption tuning）。
- Runtime：framework 现代化、异步 checkpoint 等提升 RG。
- Program：XLA 等 compiler overlap 提升 PG。
- 展示五年 accelerator mix 演变与 extra-large job 增长趋势。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| MPG defines scheduling, runtime, and program goodput separately | SG/RG/PG numerator and denominator definitions（§3.2，Fig. 2、8–10） | Google TPU methodology; not cross-vendor performance | high |
| The reported scheduler goodput exceeds 95% in each job-size segment | SG greater than 95% in Fig. 11（§4.1） | internal TPU workloads and stated preemption/defragmentation policy; no before/after baseline | high |
| Runtime segmentation exposes workload differences | Fig. 12 shows RG speedup normalized to top-N workloads at quarter start（§4.2） | unnamed internal segments; trend, not a transferable numeric gain | high |
| cited overlap deployment reaches 1.38× throughput | 1024 TPU 500B model, 72% FLOPS utilization（§4.3） | Wang et al. 2022 cited instance, not independently remeasured fleet-wide | high |
| CATWILD FDO loop covers much of the stated fleet | about 70% TPU training fleet; PG tracked on top-150 costly workloads（§4.3，Fig. 14） | coverage, not a performance gain | high |

## 批判性分析

### 论证链条

传统 metric 失效 → MPG 三分解 → 生产 TPU 案例验证 targeted 优化有效，偏 methodology 论文，闭环在「能解释能改」而非单一算法。

### 假设压力测试

开源 PyTorch/JAX 栈无 Pathways 级 runtime 时，RG 瓶颈画像不同。多租户 preempt 策略若损害 tail latency，SG 高不一定代表用户满意。

### 实验可信度

生产规模可信但可复现性低；数字多为 aggregate trend，少公开绝对 MPG 值对比前后。

### 系统性缺陷

论文未讨论 MPG gaming（如缩短 step 定义）、隐私分段粒度、与 carbon/$/goodput 关系。故障/straggler（[[Guard]]）对 MPG 分量影响未建模。

## 局限与后续工作

- **局限 1**：实证绑定 Google TPU 软件栈，外推需重标定。
- **局限 2**：per-job fairness、tail SLO 与 MPG 关系未形式化。
- **Future work 1**：开源参考实现 + 合成 workload 上复现 SG/RG/PG 分解流程。
- **Future work 2**：将 straggler/fail-slow 事件映射到 MPG 分量，量化 [[Guard]] 类系统 ROI。

## 相关

- **相关概念**：[[Goodput]]、[[MFU]]、[[FSDP]]、[[Pathways]]、[[XLA]]
- **同类系统**：集群 scheduler、compiler autotuning
- **同会议**：[[MLSys-2026]]
