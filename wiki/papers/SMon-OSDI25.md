---
type: paper
name: SMon
full_title: "Understanding Stragglers in Large Model Training Using What-if Analysis"
authors: [Jinkun Lin, Ziheng Jiang, Zuquan Song, Sida Zhao, Menghan Yu, et al.]
venue: OSDI
year: 2025
tags: [llm-training, stragglers, distributed-training, what-if-analysis, bytedance]
source_pdf: "[[osdi25-lin-jinkun.pdf]]"
source_md: "[[osdi25-lin-jinkun]]"
---

# Understanding Stragglers in Large Model Training Using What-if Analysis (OSDI 2025)

> **一句话总结**：用 what-if 模拟重放字节跳动 5 个月、3079 个 LLM 预训练 job 的 trace,发现 42.5% 的 job 因 stragglers 慢 ≥10%、长尾浪费 45% 资源,而罪魁祸首多是 PP 阶段不均、序列长度不均、GC 停顿,而非硬件故障;配套把分析流水线做成生产态监控系统 SMon。

## 问题

LLM 训练使用 DP+[[Pipeline-Parallelism]]+[[Tensor-Parallelism]]+CP 的 hybrid parallelism,每一维都要频繁同步,任一维上有 straggler 都会拖垮整个 job。传统 straggler 应对方法(backup worker、async SGD、drop update)要么破坏 LLM 训练假设,要么改变收敛行为,所以生产里基本不用——真实 LLM 集群里 straggler 到底有多严重?原因是什么?至今缺乏系统性数据。

关键难点是:从 trace 里直接看执行时间不能告诉你「若 straggler 不存在 job 会快多少」,因为有大量重叠执行与同步 barrier。传统 critical path 分析在对称 LLM workload 上会失真(像 Coz 指出的)。

## 核心方法

论文以 ByteDance 5 个月(2024/01–2024/05)在 128+ GPU 上跑的 LLM 预训练 job 为数据源,共 3079 个,覆盖约一半 GPU-hour。

**What-if analysis 模拟器**:
- 把 trace 中的 op 按 `(step, microbatch, PP-rank, DP-rank)` 组织成 OpDuration 四维张量,每类 op(forward/backward-compute、forward/backward-send/recv、params-sync、grads-sync)各一份。
- 通信 op 只存 `transfer-duration` 部分(减去等 peer start 的 `blocking-duration`),与调度相关的部分交给模拟器重算。
- 理想情况:所有同类 op 时长应相等。要「消除」某类 straggler 就把其时长替换为理想值,然后按依赖图 replay 出 alternative timeline,对比 JCT 差异;要分析某台机器 `(p,d)` 的独立影响,只保留它的真实时长、其余机器替换为理想值。

**分析发现(量化结论)**:
- 42.5% job 被 stragglers 拖慢 ≥10%,tail 场景下浪费 45% GPU 资源。
- 同一 job 内各 step 的 slowdown 高度相似——straggler 多是**持久性问题**,不是瞬态环境抖动。
- 计算 op 比通信 op 更常成为 straggler 来源。
- job 规模与 straggler 程度无正相关;瓶颈不在「大」。
- 通过人工+模拟排查,硬件/软件故障只占少数,主因是:PP stage 间的计算不均衡、microbatch 内序列长度不均、Python GC 导致的停顿。

**产品化**:把分析流水线做成 **SMon** 监控系统,已在 ByteDance 训练集群部署,on-call 团队用它定位关键 job 的 stragglers。

## 关键结果

- 42.5% 的大规模 LLM 训练 job 因 stragglers 慢 ≥10%。
- p99 job 浪费 45% GPU-hour。
- 3 大主因:PP 负载不均、sequence-length skew、GC——都是可治理的工程问题,而不是不可抗力的硬件。
- SMon 已在生产集群部署。

## 相关

- **相关概念**:[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、straggler、Megatron-LM、FSDP、ZeRO
- **同类工作**:Coz(因果 profiling)、critical path analysis、Meta MegaScale / Llama3 训练报告中的可靠性分析
- **同会议**:[[OSDI-2025]]
