---
type: paper
name: Kareus
full_title: "Joint Reduction of Dynamic and Static Energy in Large Model Training"
authors: [Ruofan Wu, Jae-Won Chung, Mosharaf Chowdhury]
venue: OSDI
year: 2026
tags: [llm-training, energy-optimization, gpu-scheduling, bayesian-optimization, communication-overlap]
source_pdf: "[[osdi26-wu-ruofan.pdf]]"
source_md: "[[osdi26-wu-ruofan]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-12
---

# Kareus：联合降低大模型训练的动态与静态能耗（OSDI 2026）

> **原题**：Joint Reduction of Dynamic and Static Energy in Large Model Training

> **一句话总结**：GPU 频率、通信 kernel 的 SM 分配和启动时机相互影响；Kareus 将 Transformer 执行图拆成可复用分区，用多目标 Bayesian Optimization 搜索时间—能耗前沿，在实机实验中相对既有方法最多降低 28.3% 能耗（同等时间）或 27.5% 时间（同等能耗）。

## 问题与动机

大模型训练的能耗同时来自动态能耗和静态能耗。降低频率通常减少动态能耗，但会延长执行时间；通信—计算重叠可以缩短执行时间，却可能增加 GPU 活动和动态功耗。Perseus 主要优化频率，nanobatching 等工作主要优化 kernel 调度，分别只覆盖了问题的一部分。

论文测量发现，即使总工作量相同，执行计划也会造成最高 3.29× 的时间与能耗差异。简单叠加频率缩放和 nanobatching 也不是最优，因为频率改变了计算 kernel 与通信 kernel 的资源竞争关系。

## 关键观察 / 隐含假设

- **观察 1：SM 分配存在中间最优点。** 通信 kernel 只分到少量 SM 时会留下暴露的通信时间；分到过多 SM 又会拖慢并行计算，增加静态能耗（图 3a–c）。
  - **依赖假设**：通信与计算确实能够在独立 CUDA stream 上重叠，且 SM 配额能被 MSCCL++ 稳定控制。
  - **可能失效场景**：通信量很小、硬件调度器无法提供细粒度隔离，或通信受 NIC/跨节点链路限制时，SM 调度的收益可能有限。
- **观察 2：通信启动位置必须匹配 kernel 类型。** 通信与 memory-bound 的 Norm 同时运行会争用内存带宽；更早启动不一定更快（图 3d）。
- **观察 3：最优调度依赖 GPU 频率。** 降频主要降低计算吞吐而不同比例降低内存带宽，使 kernel 更偏 compute-bound；因此低频下适合避开 Linear 等计算密集 kernel（图 3e–f）。
- **假设 1：GPU 功耗可近似拆成动态功率与常数静态功率。** 该模型支撑以执行时间估计静态能耗、以频率估计动态能耗；论文承认它忽略了对温度和电压敏感的更细粒度泄漏功耗。
- **假设 2：同类分区可以共享 SM 分配和启动时机。** 这让组合搜索可行，但可能牺牲针对不同层、不同通信规模进行个性化调度的收益。

## 核心方法

Kareus 的 partitioned overlap execution model 将一个通信 kernel 与另一 nanobatch 中一段连续计算 kernel 组成分区。分区内没有数据依赖，通信可以与这段计算的不同子序列重叠。Attention–AllReduce、MLP–AllReduce 等重复模式分别优化，再组合为 microbatch 和 iteration 的时间—能耗前沿。

每个候选计划包含三类决策：通信 kernel 的 SM 数量、通信启动位置和 GPU 频率。优化器使用两个 XGBoost surrogate model 分别预测时间与动态能耗，并以 total、dynamic、static energy 的 hypervolume improvement 加上 bootstrap 不确定性构成四轮候选选择。这样既搜索前沿的不同方向，也避免只优化单一目标。

分区前沿组合时，Kareus 在一个 microbatch 内统一 GPU 频率，并让同类分区共享 SM 分配和启动位置。对小工作负载，它还把顺序执行作为候选，避免 nanobatching 因算术强度下降而造成 GPU 空转。

实现基于 Megatron-LM、MSCCL++ 和 Perseus。计算与通信使用不同 CUDA stream，CUDA event 控制启动位置；profiling 每个候选重复运行 5 秒，并冷却 5 秒，以降低 NVML 约 100 ms 采样间隔和温度变化造成的测量误差。

## 设计取舍

- **搜索精度与 profiling 成本**：热稳定测量使单候选约需 13 秒；MBO 平均耗时约 2 小时、32 GPU-hours，仍明显低于穷举搜索估计的 307 小时。
- **统一配置与表达能力**：同类分区共享配置，避免组合空间指数增长，但无法表达每个 Transformer block 的独立最优计划。
- **固定频率与运行时灵活性**：microbatch 内不频繁切频，避开数毫秒级切频开销；代价是不能利用更细粒度的频率变化。
- **模型简化与可解释性**：两部分功耗模型便于优化和分析，但论文未验证更细粒度功耗模型是否会改变前沿。

## 实验与结果

- 在 16 张 NVIDIA A100 40GB、Llama 3.2 3B 和 Qwen 3 1.7B 的实机实验中，Kareus 相对 Megatron-LM 最多降低 14.9% 迭代时间和 22.1% 能耗（表 3）。
- 相对 Megatron-LM + Perseus，在相同时间预算下最多降低 28.3% 能耗，在相同能耗预算下最多降低 27.5% 时间（表 4、图 11）。
- 在 Qwen 3 1.7B、TP=8、microbatch size=8、序列长度 4K 的案例中，Kareus 以 1,350 MHz 的稳定频率获得比 Nanobatching + Perseus 额外 10.7% 的能耗降低（§6.2.1、图 10）。
- 消融实验显示，去掉频率缩放使能耗增加 12.9%，去掉 kernel 调度使能耗增加 10.8%（表 8）。
- MBO 的 profiling 占总优化开销 97%；四种候选选择 pass 均贡献了最终前沿候选（§6.6）。
- 基于较小规模 profiling 的 Llama 3.3 70B 仿真保持了实机实验的时间和能耗趋势，但不等同于 70B 真实集群测量（§6.3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 三类调度因素必须联合优化 | 图 3、表 2；不同计划最高有 3.29× 差异 | 单层案例基于 A100、TP=4 | 强 |
| Kareus 改善端到端时间—能耗前沿 | 表 4、图 11；最多 28.3% iso-time 能耗降低、27.5% iso-energy 时间降低 | 16 张 A100，Llama 3.2 3B/Qwen 3 1.7B | 强 |
| 两个优化维度都不可缺少 | 表 8；去掉频率或调度分别增加 12.9%/10.8% 能耗 | Qwen 3 1.7B、TP=8、固定配置 | 中 |
| profiling 可被 MBO 控制 | §6.6；约 2 小时而非 307 小时 | 分区类型和 A100 环境特定 | 中 |

## 批判性分析

### 论证链条

论文从功耗拆分和 kernel 竞争测量出发，说明调度与频率存在交互，再用分区模型把全局搜索拆开，最后以实机前沿和消融验证设计。链条基本闭合。最明显的跳步是：分区级前沿的组合假设各分区代价可加，而真实 GPU 上跨分区的缓存、温度、调度器状态和频率切换效应可能破坏可加性。

### 假设压力测试

结论主要建立在 NVIDIA A100、16 GPU、Megatron-LM 的 Transformer 训练和特定并行策略上。新 GPU 的频率—功耗曲线、通信库行为和 SM 调度粒度可能不同。跨节点通信若成为主导瓶颈，局部 SM 分配未必能隐藏通信。论文用 Llama 3.3 70B 仿真扩展规模，但该结果依赖 Perseus emulator 的模型，不能替代真实 70B 集群实验。

### 实验可信度

基线包含 Megatron-LM、Perseus 和 Nanobatching + Perseus，且报告了前沿、消融、microbatch size 敏感性和热稳定 profiling。能耗测量专门评估了 5 秒窗口和冷却时间。限制在于真实模型规模和硬件代际较窄，且没有报告多租户干扰、故障恢复、训练重启或长期温度控制下的运行开销。

### 系统性缺陷

优化前需要 profiling，平均 2 小时和 32 GPU-hours 对短作业或频繁变化的 workload 可能不可接受。模型、batch size、并行度或硬件改变后通常需要重新搜索。运行时还依赖 MSCCL++、自定义 autograd 和频率控制器，增加维护与版本兼容风险。论文未讨论调度计划错误、功耗计量异常或部分 GPU 频率失配时的恢复策略。

## 局限与后续工作

- **局限 1**：两部分功耗模型把静态功率视为常数，未覆盖温度相关泄漏和更细粒度硬件功耗。
- **局限 2**：同类分区共享配置，可能错过层间异质性带来的收益。
- **局限 3**：大模型结果主要来自仿真，真实跨节点 70B 训练的测量证据不足。
- **后续工作 1**：在 H100 等新 GPU 和真实 70B 多节点训练上测量分区组合误差，并将误差控制在端到端能耗的 5% 以内。
- **后续工作 2**：允许受限数量的 per-partition 配置，测量搜索开销与前沿收益的拐点。
- **后续工作 3**：将温度、功耗上限和硬件故障纳入在线控制，验证长时间训练中的稳定性。

## 相关

- **相关概念**：[[GPU-Energy]]、[[Communication-Computation Overlap]]、[[Bayesian Optimization]]
- **同类系统**：[[Perseus]]、[[Megatron-LM]]、[[DeepSpeed Domino]]
- **同会议**：[[OSDI-2026]]
