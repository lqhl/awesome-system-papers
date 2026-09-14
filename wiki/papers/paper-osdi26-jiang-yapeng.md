---
type: paper
name: Kairox
full_title: "Kairox: Adaptive GPU-CPU Hybrid LLM Inference via Online Neuron Balancing"
authors: [Yapeng Jiang, Minghao Gan, Zicong Hong, Wuhui Chen, Junyuan Liang, Yue Yu, Meng Guo, Zibin Zheng]
venue: OSDI
year: 2026
tags: [llm-inference, activation-sparsity, gpu-cpu-hybrid, neuron-balancing, edge-inference]
source_pdf: "[[osdi26-jiang-yapeng.pdf]]"
source_md: "[[osdi26-jiang-yapeng]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-12
---

# 面向 GPU-CPU 混合推理的自适应神经元平衡（OSDI 2026）

> **原题**：Kairox: Adaptive GPU-CPU Hybrid LLM Inference via Online Neuron Balancing

> **一句话总结**：静态 hot/cold 神经元划分在语义漂移和批量推理下会把突发工作压到 CPU；KAIROX 用相邻层预测隐藏搬运延迟，用 Temporal Activation Momentum（TAM）保留持续激活的神经元，再按 CPU/I/O 瓶颈动态调节搬运强度，在两台消费级 PC 上相对 llama.cpp 取得最高 7.57×、几何平均 4.45–5.00× 的标准解码加速。

## 问题与动机

13B 模型的 FP16 权重就需要超过 26 GB，消费级 GPU 往往必须把部分权重放到 DRAM。传统 llama.cpp 按层切分，CPU 执行速度较慢；PowerInfer 等系统利用 FFN 激活稀疏性，把高频神经元放在 GPU、低频神经元放在 CPU，但离线划分假定激活分布稳定。

论文在 RTX 3080 Ti 上观察到，批量从 1 增至 20 时，静态划分的 CPU 延迟从 102.8 ms 增至 551.7 ms；单请求生成中，TPOT 也会在约 50–200 ms 间波动（图 3）。语义漂移会让原本的 cold 神经元成片激活，CPU 成为瓶颈，而 GPU 仍有空余并行能力。在线搬运可以缓解 CPU 压力，但会引入 PCIe 延迟、缓存抖动和新的 I/O 瓶颈。

## 关键观察 / 隐含假设

- **观察 1：静态 hot/cold 划分无法覆盖运行时激活漂移。** OPT-6.7B 的某层 cold 激活数可在相邻 token 间从接近 0 跳到超过 3,000（图 4）。
  - **依赖假设**：GPU 仍有足够显存和计算余量承接部分 cold 神经元。
  - **可能失效场景**：GPU 显存极小、激活稀疏性很低或 PCIe 速度更慢时，搬运收益可能被 I/O 抵消。
- **观察 2：激活具有时间局部性。** 超过 400,000 条激活序列显示，神经元被激活后，未来数步再次激活的概率较高；cold 神经元在偏移超过 2 步后该概率降至 0.2 以下（图 8）。
  - **依赖假设**：短期持续激活比单次突发更能预测未来收益。
  - **可能失效场景**：请求上下文快速切换、长距离依赖主导或批内请求差异很大时，TAM 的历史惯性可能滞后。
- **观察 3：相邻 Transformer 层的隐藏状态具有高相似度。** 相邻层余弦相似度约 98%，两层和四层间分别降至约 85% 和 65%。
  - **依赖假设**：相邻预测器的 false negative 足够少，且预取窗口能覆盖搬运时间。
  - **证据强度**：中等。论文报告了召回率 90–99% 和平均任务精度下降小于 0.5%，但覆盖的模型与硬件有限。

## 核心方法

KAIROX 建立在激活稀疏的 FFN 推理上。离线阶段收集 C4 上超过 400,000 条激活模式，用 METIS 按共激活关系把神经元分组并重排。分组提高 PCIe 顺序传输效率，但也带来 over-fetch：组越大，未激活神经元被一并搬运的比例越高。

**Live Pipeline** 用第 i 层 attention 的输出预测第 i+1 层 FFN 激活，于是第 i 层 FFN 和第 i+1 层 attention 执行期间即可预取下一层神经元。第 0 层则利用相邻 token 的激活局部性，在前一个 token 的采样阶段预取。论文选择单层 lookahead，原因是更远层的相似度下降且预测误差增大（图 7、表 2）。

**TAM** 将神经元或神经元组的分数写成带衰减的递推量。持续激活会累积动量，停止激活后分数指数衰减。系统只保留分数最高的 K 个组，并用阈值过滤只出现一次的“one-hit wonder”，避免 LRU 因一次突发而污染 GPU 缓存。该设计直接回应观察 2。

**Adaptive Neuron Balancer** 把 TAM 的衰减因子 λ 变成反馈控制变量。检测到 I/O-bound 时增大 λ，提高历史惯性并减少搬运；检测到 CPU-bound 时减小 λ，使近期激活更快改变缓存。异步 I/O 执行器使用关键流和 reload 流，关键结果合并可以抢占排队的 reload 任务。

## 设计取舍

- **预取换取延迟隐藏**：相邻预测能覆盖搬运时间，但增加预测器、错误预取和调度复杂度；首层仍需特殊处理。
- **分组换取 PCIe 利用率**：单神经元传输只达到 PCIe 理论带宽的约 18–21%，分组改善顺序访问；代价是 over-fetch 和更粗粒度缓存替换。
- **动量换取稳定性**：TAM 抑制瞬时激活，但 λ 较大时会延迟适应真正的语义切换；λ 较小时又可能增加 I/O 压力。
- **专用实现限制通用性**：实现基于 llama.cpp，增加约 5,700 行 C++/CUDA，并要求 GPU、CPU、PCIe 和 CUDA 环境配合。论文未评估统一内存移动设备。

## 实验与结果

- 两台测试机为 RTX 3080 Ti + PCIe 3.0（PC-Low）和 RTX 4090 + PCIe 4.0（PC-High），CPU 分别限制为 12 和 16 线程；模型覆盖 OPT、Prosparse-LLaMA2、Bamboo、SparseQwen2、ReLUFalcon 等。
- 标准 batch-1 解码中，KAIROX 相对 llama.cpp 的最高加速为 7.53×（PC-Low）和 7.57×（PC-High），跨模型几何平均分别为 4.45× 和 5.00×；相对稀疏基线的几何平均约为 2.08–3.06×（§9.2，图 9）。
- 5-token speculative decoding 中，相对 llama.cpp 的几何平均加速为 2.23×（PC-Low）和 2.91×（PC-High）。在 PC-Low 的 OPT-30B-Q4 上，KAIROX 相对 llama.cpp、PowerInfer、Neuralink、Q-Infer 分别为 5.40×、2.44×、1.34×、2.97×（§9.2）。
- 固定 TAM 使 reload 延迟下降约 1.8–2.2×；反馈调节进一步在 CPU-bound 与 I/O-bound 场景间改变 λ 和搬运量（图 10–11）。
- 消融显示 Live Pipeline 带来 1.91×/1.39× 增益；加入在线平衡后达到 3.32×/2.88×；再加入自适应平衡后达到 3.70×/3.46×（PC-Low/High，图 15）。
- 预测器召回率为 90–99%，端到端有效开销约 1–2%；下游任务平均精度下降小于 0.5%（图 16、表 4）。GPU 利用率最高比基线高 5.35×（PC-Low）和 2.98×（PC-High）（图 12）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 在线神经元平衡能缓解静态划分造成的 CPU 瓶颈 | 图 3、图 10、图 15；在线平衡在消融中带来最大增益 | 两台消费级 PC，特定稀疏模型和 7B–66B 模型集合 | 强 |
| TAM 能减少无效搬运 | 图 8、图 10；reload 延迟下降约 1.8–2.2× | 依赖激活时间局部性；未覆盖所有上下文切换模式 | 中 |
| Live Pipeline 能隐藏预测与搬运开销 | 图 7、图 16；预测器端到端开销 1–2% | 相邻层相似度和 PCIe 拓扑可能因模型/硬件变化 | 中 |
| KAIROX 保持模型质量 | 表 4；下游任务平均下降小于 0.5% | 预测器和模型集合有限，未给出更广泛质量与长文本测试 | 中 |

## 批判性分析

### 论证链条

论文的主链条较完整：激活漂移使静态划分把工作压到 CPU；激活时间局部性支持 TAM；相邻层相似度支持预取；消融显示动态平衡是主要增益来源。图 15 能把 pipeline、在线平衡和反馈控制拆开，避免把所有收益归因于单一组件。

但“适用于多样硬件和工作负载”的外推仍受限于两台 NVIDIA 消费级 PC。论文没有给出 λ 控制器的稳定性分析，也没有说明瓶颈检测误判或反馈振荡时的保护机制。图 11 的微振荡说明系统会在阈值附近反复改变搬运强度，但长期尾延迟与不同请求并发下的行为没有单独量化。

### 假设压力测试

TAM 假定短期重激活意味着未来收益，适合论文收集的 256-token 生成序列。对于多租户批处理，每个请求的语义阶段可能不同，共享 GPU 缓存会使单一动量分数产生污染。分组则假定离线 C4 激活共现关系能代表 ShareGPT 和其他任务；领域迁移可能降低分组命中率。

系统还默认 PCIe 传输是可异步调度且 CPU/GPU 工作可以稳定重叠。PCIe 共享、NUMA 距离、较慢主存或同时运行其他任务时，reload 流可能抢占关键路径。论文报告了量化模型和非 ReLU 模型，但没有把不同量化格式、内存带宽和 PCIe 拓扑作为独立变量系统分析。

### 实验可信度

基线包括 llama.cpp、PowerInfer、Neuralink 和 Q-Infer，并说明了移植或重实现方式；这比只比较未经调整的开源版本更公平。实验覆盖标准解码、speculative decoding、显存预算、TPOT、消融和非 ReLU 模型。局限是绝对吞吐受硬件和模型实现影响较大，且 speculative decoding 的 acceptance rate 会改变批处理收益。论文未报告多用户并发、长上下文、冷启动、功耗和总能耗。

### 系统性缺陷

KAIROX 增加了离线 profiling、图划分、预测器训练、CUDA/AVX 内核和多流抢占，部署成本高于静态 PowerInfer。缓存状态和 λ 的动态变化也增加可观测性与故障排查负担。论文未讨论进程抢占、GPU reset、模型更新后离线统计失效、异常 I/O 或预测器错误时的恢复策略。实现只支持单机 GPU-CPU 混合路径，不能直接覆盖统一内存移动设备或云端多 GPU 服务。

## 局限与后续工作

- **局限 1**：评测硬件仅包含两种 NVIDIA 消费级 PC，结论对 AMD GPU、不同 PCIe/NUMA 拓扑和统一内存设备的适用性未验证。
- **局限 2**：离线共激活图和预测器来自 C4，跨领域、跨语言和长上下文下的漂移未充分测量。
- **局限 3**：论文主要关注吞吐和 TPOT，没有报告能耗、温度、并发隔离、冷启动和在线更新成本。
- **后续工作 1**：在多请求 batch 中按请求维护或分层维护 TAM，测量共享 GPU 缓存污染对 P95/P99 TPOT 的影响。
- **后续工作 2**：把 λ 控制器建模为带约束的在线控制问题，比较当前乘法调节与 PID、模型预测控制在瓶颈切换下的稳定性。
- **后续工作 3**：在不同 PCIe 代际、NUMA 位置、量化格式和 GPU 厂商上建立搬运—计算成本模型，验证分组大小是否能自动选择。

## 相关

- **相关概念**：[[Activation Sparsity]]、[[GPU-CPU Hybrid Inference]]、[[LLM Inference]]、[[Mixture-of-Experts]]
- **同类系统**：[[PowerInfer]]、[[Neuralink]]、[[Q-Infer]]、[[llama.cpp]]
- **同会议**：[[OSDI-2026]]
- **对比**：[[Kairox-vs-PowerInfer]]
