---
type: paper
name: SakuraONE
full_title: "SakuraONE: An Open Ethernet-Based AI HPC System and Its Observed Workload Dynamics in a Single-Tenant LLM Development Environment"
authors: [Fumikazu Konishi, Yuuki Tsubouchi, Hirofumi Tsuruta]
venue: MLSys
year: 2026
tags: [hpc, llm-training, open-networking, sonic, workload-telemetry]
source_pdf: "[[ad61ab143223efbc24c7d2583be69251.pdf]]"
source_md: "[[ad61ab143223efbc24c7d2583be69251]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# SakuraONE：基于开放以太网的 AI HPC 系统及其在单租户 LLM 开发环境中观察到的工作负载动态（MLSys 2026）

> **原题**：SakuraONE: An Open Ethernet-Based AI HPC System and Its Observed Workload Dynamics in a Single-Tenant LLM Development Environment

> **一句话总结**：SAKURAONE 为 800 GPU（100×8 H100）+ 2PB Lustre + **800GbE RoCEv2 SONiC** 开放网络栈的 TOP500 #49 集群；单租户 LLM 续训/微调项目 telemetry 显示作业数上小作业主导、GPU-hours 上大作业主导，且随项目阶段从大规模训练转向中规模迭代——填补中日等 **数百卡级** 生产负载公开数据空白。

## 问题与动机

公开运维数据多来自万卡 hyperscale；许多运营商实际主力是数百卡续训/微调平台。SAKURAONE 用开放以太网证明 vendor-neutral AI fabric 可扩展，并报告单项目 workload 演化。

## 关键观察 / 隐含假设

- **观察 1：作业数量 small-scale 主导，GPU-time 少数 large job 主导——与经典 HPC 一致，但 LLM 开发期会向 mid-scale 漂移。**
  - **依赖假设**：单租户单项目减少跨租户调度噪声。
  - **可能失效场景**：多租户混部时分布不同；外推需谨慎（论文明确限定）。

- **观察 2：70B/300B token 四月目标反推需 ~800 H100 Hopper 量级；rail-optimized 800GbE + GPUDirect RDMA 可支撑 hybrid parallel collectives。**
  - **依赖假设**：2–3× per-GPU LLM 吞吐 vs A100；网络 ECN/PFC 调优足够 lossless。
  - **可能失效场景**：极大 MoE EP 时网络模式不同未测。

- **观察 3：存储网与训练网物理分离，~100GB/s 聚合带宽支撑 hourly multi-TB checkpoint + 并行数据生成。**
  - **依赖假设**：双 400GbE/节点到 Lustre 无训练 collective 干扰。
  - **可能失效场景**：checkpoint 风暴与训练同峰仍可能争用 OPS。

## 核心方法

**架构**：100 节点 8×H100 SXM、NVLink；8×400GbE GPU fabric（PIX 亲和 NIC 映射）+ 独立 storage bond；SONiC + RoCEv2；2PB all-flash Lustre。

**性能**：HPL **33.95 PFLOP/s** Rmax；HPCG **396 TFLOP/s**；HPL-MxP FP8 **339.86 PFLOP/s**；TOP500 #49，top100 唯一全开放网络栈。

**Telemetry**：Slurm/作业日志分析 job size vs GPU-hours 随时间演化。

## 设计取舍

- **开放以太网 vs InfiniBand**：成本/供应链弹性，需 PFC/ECN 工程。
- **单租户独占 vs 多租户**：可观测性高，利用率可能低于混部云。
- **空气冷却 8U vs 液冷**：部署简单，功率密度受限。
- **边界条件**：日本商业 HPC；LLM 开发非单次极限 pretrain。

## 实验与结果

**指标、基线与边界**：HPL throughput (Rmax)、validated HPCG、time-to-train；vs H100 single-GPU GEMM peak 或 MLPerf quality target；784-GPU benchmark workload 或单一医疗 LLM 项目（§6–8）。

- HPL-NVIDIA25.4.0：784 GPUs、Rmax **33.95 PFLOP/s**、43.31 TF/GPU、约 **78.3%** per-GPU efficiency、**389.23 s**（§6.2，Table 5）。
- HPCG3.1：784 processes、validated **396.295 TFLOP/s**；39.96 TB footprint、16 threads/process（§6.3，Table 6）。
- 非官方 MLPerf-following GPT-3 175B：64/96 nodes 为 **58.30/41.86 min**；Llama2 70B LoRA 96 nodes 为 **1.26 min**（§6.6–6.7）。
- 单租户医疗 LLM 项目中，**77%** jobs 为 single-node，但 >17-node jobs 占 GPU time >**70%**；不代表 multi-tenant cluster（§7.1，§8.3–8.4）。

## 论断—证据表

| 论断 | 证据 | 指标 / 基线 / 评测边界 | 定位 | 置信度 |
|---|---|---|---|---|
| HPL 结果是 784 GPU 的 dense benchmark | 33.95 PFLOP/s、78.3%、389.23 s | H100 single-GPU GEMM peak 55.34 TF/GPU；非 LLM training throughput | §6.2，Table 5 | high |
| HPCG 覆盖 sparse/memory/communication benchmark | validated 396.295 TFLOP/s | 784 processes、39.96 TB、16 threads/process | §6.3，Table 6 | high |
| time-to-train 结果非官方 | 58.30/41.86 min、1.26 min | MLPerf spec-following but unverified/non-official | §6.6–6.7 | high |
| Eos 比较不是受控等价实验 | within 2%–17%；96-node Eos 为 linear extrapolation | node hardware/interconnect/software/tuning differ | §6.6，Table 12 | high |
| telemetry 仅反映一个单租户项目 | 77% jobs single-node、>70% GPU time for >17 nodes | Japanese medical LLM project、指定时间段 | §7.1，§8.3–8.4 | high |

## 批判性分析

### 论证链条

容量规划→开放网络实现→benchmark+telemetry，experience report 逻辑自洽。Workload claim 样本=单项目，泛化有限但诚实。

### 假设压力测试

SONiC 社区升级风险；800GbE 大规模 collective 尾延迟未深拆；与 ABCI 等共享系统对比缺失。

### 实验可信度

Benchmark 可验证；telemetry 方法标准。缺 anonymized 多项目对比。

### 系统性缺陷

论文非优化系统研究；故障/网络拥塞案例浅；开源软件栈细节有限。

## 局限与后续工作

- **局限**：单租户单项目 telemetry；开放网络长期可靠性数据短。
- **Future work**：多租户混部轨迹；与 disaggregated training 网络流量表征；公开 anonymized job trace。

## 相关

- **相关概念**：[[RoCE]]、[[Collective-Communication]]
- **同会议**：[[MLSys-2026]]
