---
type: paper
name: Blink
full_title: "When Sampling Lies: Trustworthy Performance Profiling for Flat Workloads with Blink (Operational Systems)"
authors: [Rishikesh Devsot, ChenXing Yang, Yi Fan Yu, Prabhdeep Singh Soni, Afshin Arefi, Bryan Chan, Reza Azimi, Ding Yuan]
venue: OSDI
year: 2026
tags: [profiling, performance-counter, mobile-systems, instrumentation, compiler]
source_pdf: "[[osdi26-devsot.pdf]]"
source_md: "[[osdi26-devsot]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向 Flat Workload 的可信性能剖析（OSDI 2026）

> **原题**：When Sampling Lies: Trustworthy Performance Profiling for Flat Workloads with Blink (Operational Systems)

> **一句话总结**：HarmonyOS 的 flat profile 含数千个短函数，perf 因 skid、shadow effect 和采样扰动可给出稳定却方向错误的结论；Blink 在 function entry/exit 直接读取 PMU 并以 self-patching 限制 tracing，达到 99.999% instruction-count accuracy、约 1% 用户可见开销和近完整覆盖。

## 问题与动机

移动 compiler optimization 经常只改善 1%，因此 profiler 不仅要低 variance，更不能系统性误判方向。Huawei 团队发现，rendering 等真实 workload 没有单个 dominant function，而是数千个短 routine 均匀贡献时间；perf sampling 在此 flat workload 上只覆盖部分函数，并可能把 PMU event 错归到下游 instruction。

一次 ARM LSE 优化本应减少 atomic instruction，perf 却持续报告目标 library instruction 增加约 6%（9000 万条），工程师为此排查数周。问题并非随机 skid 能靠重复平均消除：long-latency atomic 阻塞 retirement，缩小其后的 skid window，形成 shadow bias，使错误稳定重现。

## 关键观察 / 隐含假设

- **观察 1**：skid 与 long-latency instruction 的 shadow effect 联合作用，会产生有方向的 attribution bias，而非零均值 noise（§2.2）。
  - **依赖假设**：PMU interrupt 的 imprecise delivery 与 out-of-order retirement 在目标 ARM/Linux perf 上具有该机制。
  - **可能失效场景**：支持 precise event-based sampling 的硬件、只需 coarse hotspot 的 workload，或没有明显 latency 差异的 instruction stream。
- **观察 2**：即便把 perf 提至 40 kHz，也只覆盖约 62% function；高频 interrupt 同时把 L1D miss 增加最高 46×并扭曲 scheduler（§2.3）。
  - **依赖假设**：目标 flat profile 的函数生命周期短、贡献均匀，缺失 function 对 optimization attribution 关键。
  - **可能失效场景**：少量长函数主导的传统 hotspot workload，此时 sampling 更便宜且已足够。
- **假设 1**：在选定 program point 同步读取 PMU 的开销可被控制，并且 instrumentation 本身不会改变要测的优化结论。
  - **证据强度**：强。ground-truth microbenchmark 与手机 user metric 有量化验证，但仍有 Heisenberg effect。
- **假设 2**：工程师能预先选择值得 instrument 的 function/code region；Blink 不是无需先验的全系统 discovery profiler。
  - **证据强度**：中。Huawei compiler workflow 有明确 target，general debugging 的 target selection 未解决。

## 核心方法

Blink 通过 binary instrumentation 在 function entry/exit 或用户指定点读取硬件 PMU counter，消除 interrupt delivery skid，并保证被 instrument routine 的覆盖。它区分 inclusive tree metric 与排除 callee 的 self metric，把 entry/exit record 按 thread 配对，计算 dynamic instruction、cycle 与 cache event 差值。

为控制 tracing 开销，Blink 在 trace point 插入可 self-patch 的 branch。启用时跳到 hand-written assembly，保存最少 register、读取 PMU 并写入 per-thread buffer/counter；每个 function/thread 收集到上限 N 后把 branch patch 回 `nop`，因此 disabled path 只留一个 jump/空操作级成本，热点不会无限写 trace。

per-thread buffer 避免 lock 与 cache-coherence，满时批量 flush；系统在 context switch 路径保存/恢复相应 PMU 状态。工程实践中 Blink 被接入 HarmonyOS compiler performance suite，可用一两次 run 替代 perf 为稳定性所需的 50 次以上，并支撑 compiler flag autotuning。

## 设计取舍

- **instrumentation 换 attribution correctness**：避免 sampling bias 与 coverage 缺口，却会改变 binary layout、register/cache 行为。
- **每函数限额 N**：给 overhead 明确上界并扩展覆盖，代价是只观察 execution 早期样本，若 phase 行为变化会有偏差。
- **targeted tracing**：对 compiler A/B 极有效，但不具备 sampling profiler 的低先验全局 hotspot discovery。
- **per-thread state**：降低同步开销，却带来与 thread 数线性增长的 memory，最大案例约 5.7 MB。

## 实验与结果

- 实验平台为 Huawei Mate 60 Pro、KIRIN 9000S（4 big + 4 little core）、OpenHarmony 0324，主要 profiling `render_service`，通常报告 10 次平均（§2.1）。
- 已知 ground truth 的 function instruction count 中，Blink 在所有测量上达到 99.999% accuracy；误差平均只有数条 instruction（§4.1）。
- perf 从 4 kHz 增到 40 kHz 仍只捕获约 62% function，并使 L1 data-cache miss 最高增加 46×；说明提高 sampling rate 不能无代价修复 flat-profile coverage（§2.3）。
- 相比会显著扰动 cache 的 40 kHz perf，Blink 对手机关键 user metric 的 frame drop 增幅少于 1%，论文将整体 profiling overhead 报告为约 1%，worst case 约 1%–2%（§4）。
- Blink 固定 tracing path 开销约 38.7 ns，并在实际 LSE、frame rendering anomaly 与 ML compiler autotuning case 中给出一两次 run 即稳定的反馈（§4–5）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| perf 在 flat workload 可稳定给出错误方向 | §2.2：LSE 后报告 instruction 增 6%/9000 万，静态语义相反 | KIRIN 9000S、Hiperf/perf sampling、单优化 case | 强 |
| 提高 sampling rate 仍覆盖不足且严重扰动 | §2.3：40 kHz 约 62% coverage、L1D miss 最高 46× | HarmonyOS mobile workload | 强 |
| Blink 精确且低开销 | §4.1–4.2：99.999% accuracy、frame drop 少于 1% | instrumented target、Mate 60 Pro test suite | 强 |
| Blink 改善工程迭代速度 | §5：perf 需超过 50 runs，Blink 一两次稳定 | Huawei compiler case studies，缺少统一 time study | 中 |

## 批判性分析

### 论证链条

论文从 operational misdiagnosis 证明 sampling error 不是“多跑几次”能解决，再选择 direct counter instrumentation 从机制上消除 skid，逻辑闭合。它没有宣称替代所有 profiler，而是针对 short-lived、flat、fine-grained A/B attribution，这个边界合理。

### 假设压力测试

若优化改变 control flow、thread scheduling 或 phase length，按 function 前 N 次采样可能偏向早期行为；若 instrument point 周围极短，38.7 ns 本身可能超过 function execution。binary patch 和额外 branch 还会影响 I-cache/branch predictor。论文以 end-user frame drop 说明整体扰动小，但不能证明每个 microarchitectural event 都无偏。

### 实验可信度

已知 instruction ground truth、用户指标、真实误诊与多 use case 组合很有说服力，尤其明确对 perf 的系统性 bias。外部有效性受单一手机 SoC、OpenHarmony/Hiperf 和 ARM 限制；与 Intel PEBS/AMD IBS、eBPF trampoline、XRay 等在相同 workload 的 accuracy-overhead curve 不够完整。

### 系统性缺陷

self-modifying code 需要 executable memory 与 patch synchronization，可能与 CFI、W^X、code signing 和 production security policy 冲突。per-thread buffer 在 thread-heavy process 中膨胀，trace overflow、crash consistency 和 multi-process aggregation 的运维边界较少讨论。Blink 也需要 compiler/binary cooperation，闭源或 JIT code 的 coverage 不清楚。

## 局限与后续工作

- **局限 1**：实验集中于一款 ARM phone 与 compiler workload，跨 architecture 结论有限。
- **局限 2**：需要预先选择 instrumentation target，不能取代 discovery profiling。
- **局限 3**：self-patching 与 PMU virtualization 在 hardened OS/container/VM 中可能不可用。
- **后续工作 1**：在 ARM SPE、Intel PEBS、AMD IBS 上复现 flat workload，比较 direction error、coverage 与 perturbation。
- **后续工作 2**：扫描每函数 budget N 和 function duration，给出误差少于 0.1%、overhead 少于 1% 的可操作边界。
- **后续工作 3**：实现 W^X/CFI-compatible patching 并测试并发 enable/disable、signal、thread exit 与 buffer overflow 的 correctness。

## 相关

- **相关概念**：[[Performance-Profiling]]、[[Hardware-Performance-Counter]]、[[Binary-Instrumentation]]、[[Observer-Effect]]
- **同类系统**：[[perf]]、[[eBPF]]、[[XRay]]
- **同会议**：[[OSDI-2026]]
