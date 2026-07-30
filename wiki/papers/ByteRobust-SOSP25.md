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
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# ByteRobust：字节跳动的稳健 LLM 训练基础设施（SOSP 2025）

> **原题**：Robust LLM Training Infrastructure at ByteDance

> **一句话总结**：基于三个月 778K incident 的生产观测，ByteRobust 用「快速隔离优于精准定位」+ 分级停机诊断 + 代码热更新/预热 standby + 跨并行组分布式 checkpoint，在 9600 GPU 三月训练上达到 **97% ETTR**，failover 比 baseline 快 **10.87×/11.04×**。

## 问题与动机

大规模 [[LLM]] 预训练（月级、万卡）中故障几乎不可避免：Meta 在 16K GPU 上约每 2.78 小时一次硬件故障。传统 fail-stop → 日志分析 → 人工诊断 → 重调度 → 从远程 FS 拉 TB 级 [[Checkpointing]] 的流程可耗时数小时到数天，严重拉低 ETTR（有效训练时间 / wall-clock）。

字节三个月生产数据（778,135 incidents）显示：36% 为显式 [[CUDA]] Error，但 **>10% 为隐式故障**（job hang、MFU 下降、[[Silent-Data-Corruption]]/NaN loss），无明确错误信号；此外 17.3% 为人工重启（代码/数据调整）。月级训练伴随持续代码演进（kernel fusion、并行策略调整），使「故障根因是 infra 还是 user code」更难区分。万卡规模下即使定位了坏机，也没有足够备机全量替换，**隔离本身成为关键路径**。

## 关键观察 / 隐含假设

- **观察 1**：绝大多数 incident 可用粗粒度手段快速恢复，无需昂贵精准定位。
  - **依赖假设**：故障域与 [[Tensor-Parallelism]]/[[Pipeline-Parallelism]]/[[Data-Parallelism]] 并行组对齐；over-evict 整个 parallel group 的代价小于数千 GPU 空等定位。
  - **可能失效场景**：单卡 SDC 且 dual-phase replay 仍无法复现时；或故障与代码变更强耦合且 rollback 无效。
  - **证据强度**：强——19 个 ≥9600 GPU 任务统计：直接驱逐 32.52%、重试 22.70%、回滚 9.20%，仅 1.23% 需 dual-phase replay。
- **观察 2**：隐式故障的 unproductive time 中，failover（调度、建 pod、拉 checkpoint、重算）往往比 detection/localization 更长。
  - **依赖假设**：checkpoint 间隔较大或存远程 FS；failover 路径未预热。
  - **可能失效场景**：every-step checkpoint + 本地/CPU 备份已消除远程拉取瓶颈时，detection 成为新瓶颈。
  - **证据强度**：中——Fig. 3 以 job hang 为例展示 breakdown，但不同 incident 类型比例不同。
- **假设 1**：LLM 训练故障以「单台坏机」为主，dual-phase replay 的 group testing 可定位 SDC。
  - **证据强度**：中——论文经验称 SDC 通常单卡，但仅 1.23% case 需要 replay，样本偏少。

## 核心方法

ByteRobust 是 control plane + data plane 全生命周期管理系统，贯彻三条哲学：

1. **Prioritize rapid isolation**：轻量实时检测（DCGM、RDMA 流量、loss/gradient/MFU）+ 分级停机诊断（EUD → intra-machine all-to-all → inter-machine all-gather → bitwise alignment test）；不足时用 runtime stack-trace 聚类 over-evict parallel group。
2. **Incorporate human error**：代码回滚与确定性故障合并处理（lazy update）；用户空间错误直接从 log 触发 rollback。
3. **Control variability during recovery**：不换机时 **in-place hot-update**；换机时预热 warm standby + self-check；checkpoint 跨 parallel group 分布式备份到 CPU 内存和本地盘。

关键机制：Dual-Phase Replay（保持 TP/PP，缩 DP 做两次分组 replay 定位 SDC）；Data-driven over-eviction（hang/MFU 下降时聚合 stack-trace）。

## 设计取舍

- **取舍 1**：牺牲精准根因定位，换取 ETTR——可能 over-evict 健康机器，依赖 warm standby 补位。
- **取舍 2**：every-step checkpoint（<0.9% 开销）换快速 failover，但增加存储与网络带宽压力。
- **边界条件**：适合月级、多阶段、频繁重启的 production pretrain；对小规模短训或 research sandbox 可能过度工程化。

## 实验与结果

- **97% ETTR**（9600 GPU，三月）
- Warm standby / hot update：**10.87× / 11.04×** failover 加速（16384 GPU micro-benchmark）
- Every-step checkpointing 开销 **<0.9%**
- 三月内自动处理 38,236 显式 + 5,948 隐式故障
- 与 [[MegaScale]] 等对比：强调 process 级精细管理而非 pod 级

## 批判性分析

### 论证链条

production incident 统计 →「粗粒度隔离足够」→ 自动化框架设计，逻辑闭合较好。97% ETTR 与 micro-benchmark 加速数字支撑 recovery 路径优化；但 ETTR 定义与 baseline 对比细节（是否含人工重启）论文有描述，外推到其他云厂商需警惕 workload 差异。

### 假设压力测试

- 100K GPU 集群（xAI 规模）下 warm standby 池是否足够？论文未讨论备机比例上限。
- MoE/EP 等更复杂并行组的 over-evict 边界未充分展开。
- SDC 非确定性、难复现时 dual-phase replay 的 false negative 率未量化。

### 实验可信度

生产数据体量大、时间跨度长，可信度高。Micro-benchmark 与 macro 三月任务互补。缺少与 MegaScale 等同场 head-to-head ETTR 对比。

### 系统性缺陷

论文未讨论：tracing/可观测性对运维的依赖；checkpoint 存储成本随模型增大（405B+）的 scaling；跨地域训练的网络分区场景。

## 局限与后续工作

- **局限 1**：聚焦字节内部栈，外部框架适配成本未知。
- **局限 2**：SDC 定位仍可能需数小时 offline stress test（论文案例）。
- **Future work 1**：量化 over-evict 率与备机池大小的 tradeoff curve，指导不同规模集群的参数选择。

## 相关

- **相关概念**：[[ETTR]]、[[Fault-Tolerance]]、[[Checkpointing]]、[[Silent-Data-Corruption]]、[[NCCL]]
- **同类系统**：[[MegaScale]]、Meta LLaMA 3 训练栈
- **同会议**：[[SOSP-2025]]
