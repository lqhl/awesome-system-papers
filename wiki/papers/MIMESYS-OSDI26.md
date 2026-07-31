---
type: paper
name: MIMESYS
full_title: "MIMESYS: Generating Realistic Executable Testing Environments from Resource Usage Traces"
authors: [Donghyun Kim, Zichao Hu, Joydeep Biswas, Aditya Akella, Daehyeok Kim]
venue: OSDI
year: 2026
tags: [workload-generation, resource-contention, diffusion-model, testing, performance]
source_pdf: "[[osdi26-kim-donghyun.pdf]]"
source_md: "[[osdi26-kim-donghyun]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 从 Resource Trace 合成可执行测试环境（OSDI 2026）

> **原题**：MIMESYS: Generating Realistic Executable Testing Environments from Resource Usage Traces

> **一句话总结**：production app 难共享但 aggregate trace 可得；MIMESYS 用 diffusion model 将 CPU/memory/cache/I/O time series 反演为 stressor composition，以 prior-state conditioning 和 execution-feedback alignment 捕获历史/真实分布，相对 baseline trace similarity 最多提升 5.5×，contention performance degradation 误差平均 8.3 percentage points、准确性提升 2.6×。

## 问题与动机

测试 noisy neighbor 需要真实 co-located workload，但 privacy/proprietary/dependency 阻止共享 production app。benchmark 覆盖有限，简单 stress-ng 常以固定最大强度运行，缺少 temporal dynamics 与 cross-resource interaction；application clone 又需逐应用 exhaustive profiling。

运营方已有 resource trace。MIMESYS 不恢复业务逻辑，只要求生成的 executable 在相似 hardware 上制造相似 contention。核心难题是 resource metric 到 stressor parameter 的逆映射非线性、多解且有历史状态：8-thread memory stressor 可比单线程多 1800× bandwidth，同一 composition 在 prior cache/memory state 下表现不同。

## 关键观察 / 隐含假设

- **观察 1**：对测试 contention，复现 aggregate resource pattern 可不恢复 application logic（§3）。
  - **依赖假设**：target app degradation主要由已测 CPU/memory/LLC/disk aggregate interference决定。
  - **可能失效场景**：[[NUMA|NUMA]] placement、lock/scheduler、request burst、network/GPU 或 microarchitectural access pattern主导 tail。
- **观察 2**：stressor composition→metric 非线性/多模态，diffusion 比线性 interpolation适合逆映射（§3–4）。
  - **依赖假设**：固定 stressor library 的 convex-like coverage 足以逼近 real trace。
  - **可能失效场景**：trace 落在 library不可达区域；新增 stressor 必须重 profile/retrain。
- **观察 3**：previous window 改变 cache/controller state；同 composition 的 LLC/memory 90th-percentile change 可达 135.7%/95.0%（§7.3）。
  - **依赖假设**：一个 prior composition/state window 足以捕获相关 history。
- **假设 1**：trace 发布与 executable synthesis 比原 workload 更 privacy-safe；论文未形式化 membership/inversion leakage。
  - **证据强度**：弱至中。

## 核心方法

每个 1-second window 的 executable 表示为 `M stressors × K threads` 的 activation fraction；Fleetbench/stress-ng primitive 覆盖 CPU、memory、cache、disk。U-Net diffusion（8.9M parameters）以 target trace 为 condition，逐步生成每 window composition。

state-aware conditioning 额外输入上一个 composition 与执行所得 resource state，使下一 window 不只独立匹配 target point，而能补偿 warm cache、memory controller 等残留。novelty-guided collection 用 100-tree Random Forest 的 uncertainty+metric-space rarity 每轮选 128 compositions、100 轮，共约 12K sample，提高 reachable space coverage。

synthetic composition 没有 real app 的 ground-truth label。execution-driven alignment 用模型生成 candidate、实际运行、按 trace DTW reward 做 DDPO-style update；无需知道正确 stressor composition，只优化执行结果。pretrain/align 各约 2 h，后者在 8 machines 获取 feedback。

## 设计取舍

- **aggregate fidelity 换 logic fidelity**：可共享、可执行，不复现 request/data/control semantics。
- **hardware-specific profiling**：同机准确，跨 architecture cache/memory topology 会退化。
- **1 s window**：小 window metric noise 大，长 window掩盖 dynamics；选择并非所有 workload 最优。
- **generative training**：覆盖多解，需 8 h/8 machines data collection 与 GPU training。

## 实验与结果

- trace metric 为 per-core CPU、memory bandwidth、LLC traffic、disk I/O，1 s granularity；12K training samples 收集约 8 h/8 machines，A100 pretrain 2 h、alignment 2 h（§6）。
- across workload mixes，DTW distance 相对 stressor/interpolation baseline 最多改善 5.5×（§7.2、图 9）。
- target app degradation error 平均 8.3 percentage points，next-best interpolation 19.4 points，即约 2.6×更准；DaCapo P90仍有15 points error（§7.1）。
- TPC-C+Spark/web case 中真实 throughput 最多降37%，MIMESYS 平均 throughput deviation 4%、resource DTW 8%；interpolation 9%、simple stressor 30%（§7.1、图 8）。
- novelty collection 降平均 DTW error 2.5×；去 state 平均仅差7%但tail case超过2×；去 alignment DTW平均高59%（§7.3、图 10–11）。
- 随机 drop 20%/80% trace 时 DTW退化1.4×/3.7×；drop单 metric 后其他 metric退化少于1.7×（§7.4、图 12）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| trace→executable 可复现 multi-resource pattern | §7.2、图 9：DTW 最多好 5.5× | CPU/memory/LLC/disk、同类 hardware | 强 |
| 合成 workload 能复现 target app contention | §7.1：8.3 vs 19.4 points degradation error | database/FIO/DaCapo 等 benchmark mix | 强 |
| alignment 是主要 fidelity 来源 | §7.3：移除后 DTW 高59% | 所测 real app traces | 强 |
| aggregate trace 难复现 tail latency | §7.1：Redis P99 degradation 可差9× | request-level detail缺失 | 强 |

## 批判性分析

### 论证链条

论文合理缩小目标到“环境-level contention”，diffusion、state condition、execution alignment分别解决多解、history和sim-to-real gap，ablation闭合。性能误差比trace DTW更重要，而8.3 points虽优于baseline，仍可能改变SLO结论；不应把5.5× similarity误读为production-equivalent workload。

### 假设压力测试

相同 aggregate CPU/bandwidth可由不同 cache line sharing、NUMA、branch与I/O queue depth产生，对target app影响不同。Redis P99 9×差异正说明request-level dynamics缺失。hardware变化会改变stressor transfer function，论文承认需加入hardware descriptor；在不同CPU上直接复用 executable不可靠。

### 实验可信度

既测trace又测受害app、包含time-varying case、ablation和missing-trace sensitivity，证据全面。real production trace规模/来源与privacy未充分展示，training/test app覆盖有限；diffusion与 simpler supervised inverse model在等profiling budget下比较不够。

### 系统性缺陷

合成stress workload本身可能触发thermal/power/failure，需sandbox和resource cap。模型/trace可能泄露tenant activity；生成 executable更容易被滥用做DoS。fixed stressor library/version与hardware metadata必须可追溯，否则同名artifact跨机器不可复现。

## 局限与后续工作

- **局限 1**：不生成application logic/request pattern，tail latency fidelity较弱。
- **局限 2**：hardware-specific，新增stressor需重profile/retrain。
- **局限 3**：只覆盖CPU/memory/LLC/disk，不含network/GPU/power。
- **后续工作 1**：加入NUMA/IPC/branch/queue-depth与request burst metric，测是否降低Redis/DaCapo tail error。
- **后续工作 2**：condition on CPU/cache/NUMA descriptor并做跨三代hardware leave-one-out，报告迁移DTW/degradation error。
- **后续工作 3**：对trace→model→executable做privacy audit与membership inference，建立可发布的noise/utility boundary。

## 相关

- **相关概念**：[[Workload-Synthesis]]、[[Resource-Contention]]、[[Diffusion-Model]]、[[Performance-Testing]]
- **同类系统**：[[stress-ng]]、[[Fleetbench]]、[[SPEC]]
- **同会议**：[[OSDI-2026]]
