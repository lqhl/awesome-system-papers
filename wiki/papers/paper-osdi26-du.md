---
type: paper
name: EcoServe
full_title: Efficient LLM Serving on Commodity GPU Clusters with Data-Reduced Cross-Instance Orchestration
authors: [Jiangsu Du, Hongbin Zhang, Taosheng Wei, Zhenyi Zheng, Jiazhi Jiang, Kaiyi Wu, Zhiguang Chen, Yutong Lu]
venue: OSDI
year: 2026
tags: [llm-serving, commodity-gpu, prefill-decode, scheduling, scaling]
source_pdf: "[[osdi26-du.pdf]]"
source_md: "[[osdi26-du]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 面向商用 GPU 集群的低数据搬运 LLM 服务编排（OSDI 2026）

> **原题**：Efficient LLM Serving on Commodity GPU Clusters with Data-Reduced Cross-Instance Orchestration

> **一句话总结**：在 PCIe 加 10 Gbps Ethernet 的商用 GPU 集群上，完全拆分 prefill/decode 会被 KV cache 传输限制、合并执行又会产生阶段干扰，EcoServe 用同一实例的时间拆分和多个实例的滚动激活组成 PaDG，在 L20 集群上相对 vLLM、Sarathi、DistServe、MoonCake 将 P90 goodput 平均提高约 2.01×、3.43×、3.41×。

## 问题与动机

LLM 推理同时包含 prefill 和 decode。前者通常受计算限制，后者需要反复加载 KV cache，受内存带宽限制；两者又分别受 TTFT 和 TPOT 约束。NoDG 将两个阶段放在同一实例中，阶段切换会互相阻塞；FuDG 将阶段放到不同实例，虽然减少干扰，却需要搬运大量 KV cache，并依赖高性能网络。

论文针对仍大量存在的商用 GPU 集群：L20 集群使用 PCIe 连接 GPU，节点间只有 10 Gbps Ethernet。作者认为这类环境不能直接套用依赖 NVLink 或 InfiniBand 的 FuDG。EcoServe 的目标是在不搬运完整 KV cache 的情况下减少阶段干扰，并让容量能够随请求率细粒度变化。

## 关键观察 / 隐含假设

- **观察 1：** FuDG 的 KV cache 传输在普通网络上很容易成为吞吐瓶颈。LLaMA-30B 在 8 卡 A800 节点上生成 KV cache 所需的输出带宽达到 39 GB/s，论文指出这已要求至少 400 Gbps 网络（表 3）。
  - **依赖假设：** 请求的输入长度和模型 KV cache 足以让传输成本超过拆分带来的收益。
  - **可能失效场景：** GQA、短输入，或拥有 NVLink/InfiniBand 的集群会降低这一瓶颈；论文中 H100 上 MoonCake 已在部分 CodeLlama2-34B 场景超过 EcoServe。
- **观察 2：** decode 若比 TPOT SLO 更快，就会积累可借给 prefill 的时间余量（saved TPOT）。论文据此把阶段切换限制在短时间窗口，而不是依赖整个请求生命周期的精确预测（§3.1.1、§3.3）。
  - **依赖假设：** decode 速度具有足够余量，且短期借用不会让尾部请求连续违约。
  - **可能失效场景：** 输出长度极端、请求突发或 KV cache 逼近显存上限时，平均 saved TPOT 可能掩盖少数请求的 TPOT 风险。
- **观察 3：** 单实例长时间执行一个阶段会损害 TTFT，因此多个实例必须错开 prefill 窗口。滚动激活让宏实例中始终有实例可接收新 prefill（§3.1.2）。
  - **证据强度：** 强；A800 上关闭滚动激活的消融在不同模型和较高 SLO attainment 下均降速（图 15）。
- **假设 1：** 通过预 profiling 序列长度可以较准确地预测单请求 prefill 时长。该时长用于 Algorithm 1 的 TTFT 约束检查。
  - **证据强度：** 中；论文说明采用 profiling，但没有系统报告预测误差及其对 SLO 违约的影响。

## 核心方法

EcoServe 的基本调度单位是宏实例（macro instance），每个宏实例包含多个协作的实例。实例内部采用时间拆分：一个时间窗口主要执行 prefill，另一个窗口主要执行 decode。KV cache 始终留在实例内，避免 FuDG 的跨实例搬运。这一设计直接回应了普通网络上的传输瓶颈观察。

多个实例按循环顺序滚动激活。新请求优先路由到当前能提供 prefill 窗口的实例；实例周期性上报 decode 进度、显存和阶段状态，宏实例调度器据此保持 prefill 的连续可用性。它把因时间拆分造成的 TTFT 等待转化为跨实例协调问题。

自适应调度器使用主从式协作。对每个请求，Algorithm 1 依次检查：待处理 prefill 的总时长是否超过 TTFT SLO，已有 decode 的平均 saved TPOT 是否足以覆盖本次 prefill，以及剩余显存是否容纳新增 KV cache。满足约束后才把请求发送到实例的公共消息队列。

扩缩容采用“有丝分裂”（mitosis）策略。实例数先在宏实例内逐个增减；超过上限后拆成两个宏实例，收缩时则合并。可序列化的 InstanceHandler 代理保存入口和消息队列信息，使实例句柄能在调度器之间迁移而不重新初始化模型（§3.4.3）。

## 设计取舍

- **减少网络搬运，保留阶段干扰的局部性：** PaDG 不需要完整 KV cache 传输，但一个实例仍会经历阶段切换；窗口过长伤害 TTFT，窗口过短又回到 NoDG 的干扰。
- **用宏实例换取协调能力：** 多实例滚动激活提升了 TTFT 可用性，也引入状态上报、公共队列和更高层调度器。宏实例过大时，调度器可能成为瓶颈；过小时则滚动激活的收益不足。
- **细粒度扩缩容增加控制复杂度：** mitosis 避免了模型重载，但需要处理正在执行请求的实例退出、句柄序列化和宏实例拆并。论文未给出故障恢复或迁移失败处理。

## 实验与结果

- 在 64 张 L20（8 节点、10 Gbps Ethernet）上，EcoServe 相对 NoDG 的 vLLM 和 Sarathi，P90 goodput 平均分别提高 2.01× 和 1.87×；相对 FuDG 的 DistServe 和 MoonCake，分别提高 3.43× 和 3.41×（§4.2.1）。
- 按模型统计，相对 NoDG，LLaMA-30B、CodeLlama2-34B、Qwen2-72B 的平均吞吐提升分别为 1.59×、1.83×、1.76×；相对 FuDG 分别为 4.82×、2.15×、1.79×（§4.2.2）。GQA 减少 KV cache 后，FuDG 的劣势缩小。
- 在 H100 + NVLink + 400 Gbps InfiniBand 上，EcoServe 相对 vLLM 的 P90 goodput 提升为 1.34×，相对 DistServe 和 MoonCake 为 1.75× 和 1.24×；MoonCake 在部分 CodeLlama2-34B 场景超过 EcoServe（§4.2.1）。
- 在 CodeLlama2-34B、A800、ShareGPT 上，最严格的 1 s TTFT/50 ms TPOT 下，EcoServe 的 P99 throughput 从 42 降至 18 req/s，下降 57.1%；vLLM 从 16 降至 6.4 req/s（§4.3）。
- 动态扩容实验将请求率从 20 提升到 50 req/s，系统从 32 张 GPU 扩到 64 张；第 12 个实例触发 6+6 的宏实例拆分，仅产生轻微波动，而重新加载 CodeLlama2-34B 约需 3 分钟（§4.5.2、图 13）。
- 从 1 到 4 个实例时，CodeLlama2-34B throughput 提升 4.96×，Qwen2-72B 提升 5.47×；继续扩展后收益转为线性或次线性（§4.5.1、图 12）。关闭滚动激活或自适应调度均低于完整 EcoServe（图 15、图 16）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| PaDG 适合普通网络上的大模型服务 | L20 集群 P90 goodput 相对 vLLM/Sarathi 提升 2.01×/1.87×，相对 DistServe/MoonCake 提升 3.43×/3.41×（§4.2.1） | 64×L20、10 Gbps Ethernet，三种模型和三类数据集 | 强 |
| 阶段拆分不会牺牲所有严格 SLO 下的吞吐 | 1 s/50 ms 下 EcoServe 仍有 18 req/s，且相对 NoDG 降幅更小（§4.3） | CodeLlama2-34B、A800、ShareGPT；未覆盖更低 SLO | 中 |
| 滚动激活与自适应调度各自有必要性 | 随机激活和固定间隔路由的消融均低于完整设计（图 15、图 16） | A800、ShareGPT，固定候选间隔有限 | 强 |
| mitosis 能避免扩缩容中的模型重初始化开销 | 32→64 GPU 动态实验中宏实例拆分仅有轻微波动；模型重载约 3 分钟（图 13、§4.5.2） | 单模型、L20、本地存储；未测迁移失败和故障恢复 | 中 |

## 批判性分析

### 论证链条

从“普通网络限制 KV cache 搬运”到“把阶段拆到同一实例的不同时段”，再到“用多实例错峰弥补 TTFT”，主线是闭合的。图 15 和图 16 支持滚动激活、自适应路由分别贡献收益。不过 Algorithm 1 使用已有请求的平均 saved TPOT 检查 TPOT，平均值对长尾请求的保护不足；论文没有报告按请求分位数计算的 slack 或误差。

### 假设压力测试

PaDG 的优势随模型和网络变化明显。GQA 已降低 KV cache 传输，H100 的强算力也减少了 NoDG 干扰。反过来，超大模型、极严 TPOT 或 decode 几乎没有 slack 时，时间拆分可能无法提供足够 prefill 容量。实验使用固定模型、BF16 和合成的 Poisson/Gamma 到达过程，尚未证明在多租户、模型混部或真实长尾输出分布下仍能稳定滚动。

### 实验可信度

基线均对齐 vLLM 0.7.3，且覆盖 L20、A800、H100 三类网络条件；模型和输入输出长度分布也有变化。限制在于部分 DistServe/MoonCake 场景无法满足 SLO 或不支持对应 TP 配置，因此被省略，剩余比较可能偏向 EcoServe。论文还依赖“应用决定、与模型大小无关”的统一 SLO；这使不同硬件上的相对难度并不完全相同。

### 系统性缺陷

论文没有讨论节点或实例故障、调度器故障、公共队列拥塞、状态上报延迟，以及实例迁移期间的可观测性。显存预测依赖未知输出长度，虽然算法检查剩余 KV cache 容量，仍需要保守预留。论文也未报告调度控制面 CPU 开销、跨节点 ZeroMQ 通信开销和扩缩容抖动对 P99 的影响。

## 局限与后续工作

- **局限 1：** 设计依赖 decode 产生可借用的 saved TPOT；超严格 TPOT、超长输出或高突发负载可能令可借用余量消失。
- **局限 2：** 主要结果集中在 30B–72B 模型和固定的三类数据集；小模型、MoE、长上下文及多租户模型混部尚未验证。
- **后续工作 1：** 用逐请求而非平均 saved TPOT 的风险约束，测量 P99 TPOT 违约率与吞吐的关系，并在输出长度未知时验证显存保守量。
- **后续工作 2：** 在真实生产 trace、节点故障和调度器故障注入下评估宏实例拆并、实例句柄迁移和恢复时间。

## 相关

- **相关概念：** [[KV-Cache]]、[[Pipeline-Parallelism]]、[[PagedAttention]]
- **同类系统：** [[vLLM]]、[[Sarathi-Serve]]、[[DistServe]]、[[MoonCake]]
- **同会议：** [[OSDI-2026]]
- **对比：** [[vLLM-vs-SGLang]]
