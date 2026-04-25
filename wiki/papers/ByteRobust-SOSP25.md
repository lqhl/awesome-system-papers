---
type: paper
name: ByteRobust
full_title: "Robust LLM Training Infrastructure at ByteDance"
authors: [Borui Wan, Gaohong Liu, Zuquan Song, Jun Wang, Yun Zhang, et al.]
venue: SOSP
year: 2025
tags: [llm-training, fault-tolerance, gpu-infrastructure, checkpointing, sdc]
source_pdf: "[[3731569.3764838.pdf]]"
source_md: "[[3731569.3764838]]"
---

# Robust LLM Training Infrastructure at ByteDance (SOSP 2025)

> **一句话总结**:字节跳动生产级 LLM 训练容错系统,通过"快速隔离优于精准定位"+ 代码热更新 + 预热 standby + 跨并行组分布式 checkpoint,在 9600 GPU 三月训练任务上达到 **97% ETTR**,failover 比 baseline 快 10.87×/11.04×。

## 问题

LLM 训练规模已到 10K+ GPU 量级,Meta 报告 16K GPU 上每 2.78 小时就有一次硬件故障。传统做法是 fail-stop → 日志分析 → 人工诊断 → 重新调度 → 从远程 FS 加载 TB 级 checkpoint → 重算丢失步,整个流程耗时数小时到数天,ETTR(productive 训练时间 / wall clock 时间)难以维持。

字节分析三个月 778,135 个训练 incident 发现:36% CUDA Error 是显式故障,但有 10% 以上是 implicit failures——job hang、MFU 下降、silent data corruption (SDC) 如 NaN loss——没有明确错误信号。MegaScale 用 RDMA 流量骤降来检测,但仍需人工定位根因。此外,月级 pretrain 伴随用户代码持续演进(kernel fusion、并行策略调整),是新的故障来源;大规模下即使定位了故障机器,也没有足够备机全量替换,故障定位本身成为关键路径。

## 核心方法

ByteRobust 是一个 control plane + data plane 架构的全生命周期管理系统,基于三条设计哲学:

1. **Prioritize rapid isolation, not precise localization**:大规模训练中精准定位单台机器可能让数千 GPU 空转。ByteRobust 用轻量实时检测 + 分级停机诊断快速隔离疑似机器,必要时基于 runtime stack-trace 聚类 over-evict 整个 parallel group(TP/PP/DP)。
2. **Incorporate human error in design**:代码演进错误是不可避免的,自动容错框架中集成代码回滚作为"快速验证"步骤,新代码变更采用 lazy update,与确定性故障合并处理。
3. **Control variability during swift recovery**:不改变机器分配时用 **in-place hot-update** 保留运行时环境;需要换机时预热 warm standby,上线前做 self-check;checkpoint 模块跨 parallel group 分布式备份到 CPU 内存和本地盘,消除远程拉取依赖。

关键机制细节:

- **分级停机诊断**:EUD → intra-machine all-to-all → inter-machine all-gather → bitwise alignment test,层层排查
- **Dual-Phase Replay**:针对 SDC 等未知故障,用水平/垂直两次分组 replay 训练(保持 TP/PP 不变,只缩 DP)定位故障机,仅需 2 次 replay
- **Data-driven over-eviction**:job hang / MFU 下降时,聚合所有训练进程的 Python/CUDA stack-trace,基于聚类定位异常 parallel group

## 关键结果

- **97% ETTR** 在 9600 GPU 三月训练任务上
- Warm standby 和 hot update 分别带来 **10.87× / 11.04×** failover 加速(16,384 GPU micro-benchmark)
- Every-step checkpointing 开销 < **0.9%**
- 三月内从 38,236 显式故障 + 5,948 隐式故障中自动恢复
- 基于 19 个 ≥9600 GPU 的大训练任务的经验:直接机器驱逐(32.52%)、重试(22.70%)、代码回滚(9.20%) 就能解决绝大多数故障,只有 1.23% 需要 dual-phase replay

## 相关

- **相关概念**:[[Silent-Data-Corruption]]、[[Checkpointing]]、[[Fault-Tolerance]]、[[ETTR]]、[[Pipeline-Parallelism]]、[[Tensor-Parallelism]]、[[Data-Parallelism]]、[[NCCL]]
- **同类系统**:[[MegaScale]]、Meta 的 LLaMA 3 训练栈、xAI 100K GPU 集群
- **同会议**:[[SOSP-2025]]
