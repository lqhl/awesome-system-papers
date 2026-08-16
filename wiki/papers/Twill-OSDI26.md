---
type: paper
name: Twill
full_title: "Optimal Software Pipelining and Warp Specialization for Tensor Core GPUs"
authors: [Rupanshu Soi, Rohan Yadav, Fredrik Kjolstad, Alex Aiken, Maryam Mehri Dehnavi, Michael Garland, Michael Bauer]
venue: OSDI
year: 2026
tags: [gpu-compiler, software-pipelining, warp-specialization, constraint-solving]
source_pdf: "[[osdi26-soi.pdf]]"
source_md: "[[osdi26-soi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# Twill：联合求解 Tensor Core GPU 的软件流水与 Warp 专门化（OSDI 2026）

> **原题**：Optimal Software Pipelining and Warp Specialization for Tensor Core GPUs

> **一句话总结**：Twill 的关键观察是，最小 initiation interval 的软件流水不一定能被有限寄存器、阻塞同步和跨 warp 通信真正实现，所以必须把软件流水与 warp 分工一起求解；它用整数规划和 SMT 从 Triton tile-level IR 生成给定模型内可证明最优的 schedule，重新发现 [[FlashAttention-3-NeurIPS24|FA3]] 与 [[FlashAttention-4-MLSys26|FA4]] 的专家策略，在长度 16,384 的 forward attention 上，Hopper 的 SWP 变体距 FA3 1% 以内，Blackwell 的联合版本距 FA4 2% 以内。

## 问题与动机

新一代 [[Tensor-Core]] GPU 同时有通用运算单元、矩阵单元和异步搬运单元。它们的相对速度、数据放置方式、发起线程数和同步接口每代都会变化。同一个 tile-level 循环若顺序执行，往往会在 GEMM 等待 softmax，或在数据搬运时让 Tensor Core 空闲；因此编译器需要跨迭代重排操作，让不同单元同时工作。

软件流水（software pipelining, SWP）可以用 modulo scheduling 找到最小 initiation interval `I`，也就是以最高理论速率启动新迭代。但 Hopper 与 Blackwell 上，得到一张时间表还不等于能生成程序：一次 Tensor Core 操作可能要多个 warp 合作，流水会让多次迭代的值同时存活，TMA latency 又大幅波动，而且等待异步单元的 blocking synchronization 会阻止同一 warp 发出本来可并行的指令。

Warp 专门化（warp specialization, WS）能把 loader、GEMM、softmax 等操作放到不同 warp，但它不是免费步骤。分开以后可能发生跨 warp spill、共享内存通信和额外同步；寄存器容量也可能让理论最小 `I` 根本无法实现。现有编译器通常先决定流水，再用架构专属 heuristic 分 warp；Twill 要解决的是更窄但更严格的问题：对单层、无额外控制流的 tile 循环和给定机器模型，联合求出可实现且吞吐最优的 SWP 与 WS。

## 关键观察 / 隐含假设

- **观察 1：传统 modulo scheduling 能表达 Tensor Core tile 程序的吞吐上界。** 简化 attention 中，顺序版本每 3 个抽象 cycle 完成一次迭代，`I=2` 的 modulo schedule 让 GEMM 与 exponential 重叠，正好恢复 FA3 的软件流水（§3.1，图 1）。
  - **依赖假设**：tile operation 的依赖、resource reservation table 与延迟足够准确；抽象 cycle 能代表真实机器的相对成本。
  - **可能失效场景**：cache miss、动态 warp issue、TMA 变化或编译器指令选择让实际成本偏离模型时，理论上界不再等于硬件上界。
- **观察 2：WS 是让 SWP 可生成代码的约束，不应是后处理 heuristic。** 它同时决定 cooperative issue、每 warp 寄存器占用、variable-latency 隔离、blocking sync 和跨 warp 通信；任一项都可能迫使 `I` 变大（§3.2–§4.3）。
  - **直接证据**：Blackwell backward 的纯 modulo schedule 给出最小 `I=15`，完整联合约束却只能在 `I=20` 找到可行解（§6.4，表 1）。
  - **证据强度**：强。存在性反例足以否定“总能先求 SWP、再找 WS”的做法。
- **观察 3：把一次 steady state 展成有限 straight-line program，就能避开复杂循环分析。** Twill 只展开 `ceil(L/I)` 份 schedule，并令 steady state 执行一次；每次稳态执行结构相同，因此这个化简对目标循环既 sound 又 complete（§4，图 3）。
  - **依赖假设**：输入是 singly-nested loop，没有内部控制流，所有跨迭代依赖都已进入图中。
  - **可能失效场景**：动态分支、数据相关退出、嵌套流水或动态 shape 破坏重复稳态时，当前证明不适用。
- **假设 1：离线求解时间与人工机器模型是可以接受的。** Twill 愿意花几十秒到数分钟换取最优性，并把 tile size、variable-latency pipeline depth 和底层 lowering 留给人或外部 auto-tuner（§5.2–§5.4）。
  - **证据强度**：中。对少量长期部署的核心 kernel 合理，但不适合交互式编译或频繁出现的新 shape。

## 核心方法

Twill 从 Triton 的 TTGIR 读取 tile-level、SSA 形式的单层循环。每个 operation 是作用于整个 SM tile 的节点，边给出同迭代或跨迭代依赖；resource reservation table 描述它在各抽象 cycle 占用多少 Tensor Core、SFU 等资源。用户另提供目标 GPU 的 operation latency、memory capacity、blocking behavior 和 cross-warp communication cost（§3、§5）。

第一阶段把普通 modulo scheduling 写成整数线性规划（integer linear programming）。CBC solver 从小到大搜索 initiation interval `I`，在依赖和 functional-unit capacity 下找到吞吐最高的初始 schedule `M`。Twill 将 `M` 的 prologue、一次 steady state 和 epilogue 展成长度 `T` 的直线程序 `Q`，保留原始最优 `I`，作为联合问题的 seed（§4、算法 1）。

第二阶段把“何时执行”和“哪个 warp 执行”一起交给 Yices2 的 QFLIA SMT solver。三维布尔变量 `op[v,i,t]` 表示第 `i` 次迭代的 operation `v` 是否在 `t` 执行；uniqueness、modulo consistency、completion、dependence 与 capacity constraints 保证新程序仍来自合法的最优 modulo schedule（§4.1，图 4）。

为了保证 schedule 放得进芯片，Twill 用 `live[v,i,t]` 在求解器内重新计算 SSA value 的生命周期，并限制共享内存等容量。`opw[v,w]` 决定 warp assignment：variable-latency operation 进入专用 warp，每个 warp 的 live values 不得超过 register limit；跨 warp producer-consumer 加上 spill delay；需要 blocking synchronization 的 operation 不能和同 warp 的其他发射重叠。这些约束显式编码“多分一个 warp 能缓解寄存器压力，但会增加通信与同步”的取舍（§4.2–§4.3，图 5–6）。

若最小 `I` 下不可满足，Twill 先在不增加展开份数的范围内增大 schedule length `L`，仍无解再让 `I` 加一；因此返回的是约束模型中第一个可行、也就是吞吐最优的解。求解复杂度会随原始 cycle count 急升，所以系统另用 SCIP 解一个 cost-normalization 整数规划，在保持延迟比例尽量接近的前提下令总成本上界 `U=300`；论文所有归一化问题在 500 ms 内达到全局最优（§5.1–§5.2）。

对没有输入依赖的 variable-latency streaming operation，例如 TMA input load，Twill 将静态成本记为 0，让它在独立 warp 上提前多轮执行，再把 pipeline depth 暴露给外部 tuner。求解完成后，系统输出带流水位置与 warp annotation 的 TTGIR；理论上可交给 Tawa 或 Cypress 一类后端，论文实验则由作者手工翻译为 CUDA C++，以绕过 Triton 当时的 memory allocation、layout conversion 和 synchronization lowering 问题（§5.3、§6.1）。

## 设计取舍

- **形式最优换取问题范围**：保证覆盖给定 tile、依赖图、归一化成本和机器约束内的全部 schedule；它不保证 tile size、指令选择、register allocation 或真实 GPU runtime 的全局最优。
- **联合求解换取编译时间**：显式建模能发现非直觉 warp 分工和不可满足配置，但每个 kernel 要几十秒至 242 秒，只适合离线优化高价值 kernel。
- **静态模型换取无需 profile 搜索**：相比 [[PipeThreader-OSDI25]] 逐个运行候选，Twill 可用文档和微测成本剪枝并证明模型内最优；动态 cache、TMA 与 warp scheduler 行为则可能被简化。
- **成本归一化换取可求解性**：只尽量保存 cost ratio，而非真实 cycle；求解结果严格最优于归一化模型，但比例误差可能改变两个接近 schedule 的现实排序。
- **专注 schedule 换取手工 lowering**：论文把 Twill 的策略手译成 CUDA，清楚隔离了研究问题，却没有交付从 Triton 输入到高性能二进制的完整自动编译器。

## 实验与结果

- **平台与边界**：实验使用 H100 SXM5 80 GB 与 Blackwell B200 180 GB、CUDA 13.0，search time 在单个 Intel Xeon Platinum 8570 core 上测量；kernel 只有 FP16 non-causal fused multi-head [[Attention]] forward/backward，固定 `BATCH=4`、`NUM_HEADS=32`、`HEAD_DIM=128`，sequence length 为 2,048–16,384（§6.1，图 7–11）。论文 §6.1 明确写 B200，但表 1 行名及 §6.4 个别文字写 B100；本页不把这处内部不一致外推成两块不同 GPU。
- **Hopper forward**：只用 Twill optimal modulo schedule、沿用 Triton WS 的 `Twill-SWP`，在 sequence length 16,384 时距官方 FA3 性能 1% 以内；完整 Twill 又自动恢复 FA3 的 ping-pong warp strategy，但因 TMA multicast 这项正交优化更利于 `Twill-SWP`，最终略慢于它（§6.2.1，图 7）。这支持“能发现专家 schedule”，但不是“联合版本总比任何分步版本快”。
- **Blackwell forward**：Twill 找到与 FA4 完全相同的高层策略：TMA、Tensor Core、两个 softmax warp groups 和独立 accumulator-rescale group 联合流水。sequence length 16,384 时实现距 FA4 2% 以内；把 Triton 的 FA4-like WS heuristic 单独加到非联合 schedule 上没有收益，说明策略必须与流水配套（§6.2.2，图 8–9）。
- **Backward 暴露模型边界**：Hopper 上寄存器容量阻止跨迭代 ILP，Twill 与 FA3 得出同样判断，但长度 16,384 时仍比 FA3 慢 11%，作者归因于 Triton 只能用 2 的幂 tile，无法采用 FA3 的 `80×128` tile。Blackwell 上，最初两组 warp 的解按模型可放入寄存器，`ptxas` 却发生严重 spill；降低模型寄存器预算后，三组 warp 解接近 FA4 并获得小幅提升（§6.3，图 10–11）。
- **搜索时间**：H100 forward、Blackwell forward、H100 backward、Blackwell backward reduced-register、Blackwell backward 的总 search time 分别为 28、18、84、48、242 秒；其中 H100 forward 找到同一策略只需 28 秒，[[PipeThreader-OSDI25]] 报告 315 秒，名义上约快 11.3×。后一个数字来自另一篇论文，并非同一主机、同一搜索空间下的受控比较（§6.4，表 1）。
- **联合约束确实会改变最优吞吐**：Blackwell backward 的纯 modulo scheduling 最小 `I=15, L=32`，完整 WS 约束最终只能在 `I=20, L=33` 成功；减少 warp、禁止 cross-warp communication 或不做 sub-tiling 也会使最小 `I` 的 SMT 问题不可满足（§6.2.2、§6.4，表 1）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| SWP 与 WS 必须联合考虑 | Blackwell backward 从纯 SWP 的 `I=15` 增至可实现的 `I=20`（§6.4，表 1） | 单个 Blackwell attention backward 配置，但已构成反例 | 强 |
| Twill 能自动恢复专家的跨代 forward 策略 | Hopper 恢复 FA3 pipeline/ping-pong；Blackwell 恢复 FA4 分组（§6.2，图 7–9） | H100、B200 的 FP16 non-causal attention | 强 |
| 找到的 schedule 能接近手工库性能 | 长度 16,384 时 Hopper `Twill-SWP` 距 FA3 1% 内，Blackwell Twill 距 FA4 2% 内（§6.2，图 7–8） | 手工翻译 CUDA，固定 batch/head 参数；不是自动 Triton 输出 | 强 |
| 约束求解搜索时间可用于离线 kernel 优化 | 18–242 秒；Hopper forward 28 秒对 PipeThreader 315 秒（§6.4，表 1） | 单核 Xeon 8570、5 个 attention 搜索实例 | 中 |
| 当前机器模型仍不足以预测实际寄存器分配 | Blackwell 两组 warp 解被 `ptxas` spill，收紧 register budget 后才成功（§6.3.2） | 一个 backward 实现与特定 compiler backend | 强 |

## 批判性分析

### 论证链条

论文最扎实的贡献是把一句经验判断变成可检验命题：若先求 SWP 再做 WS，总有可能得到无法实现的最小 `I`；Blackwell backward 的 `15→20` 提供了直接反例。约束从依赖、容量、liveness 一直连到 warp communication 与 blocking sync，FA3/FA4 的独立人工结果又验证求解器能找到有现实意义的点。需要收窄的地方是“guaranteed optimal schedules”：保证只针对当前单层循环、固定 tile 和给定抽象机器模型，不等于最终 CUDA kernel 对真实 GPU 全局最优。

### 假设压力测试

Twill 依赖 operation cost ratio、register limit、spill cost 和 blocking relation 足够准确。真实 TMA latency 可跨一个数量级，cache、动态 warp issue 和 compiler lowering 还会改变执行顺序；把 streaming load 记为 0 只是把不确定性移给外部 pipeline-depth tuner。动态分支、嵌套循环、ragged sequence、稀疏 attention 或 shape 很多的在线编译场景，也超出“一次稳定 steady state”的前提。

### 实验可信度

两代 GPU、forward 与结构不同的 backward，加上与 FA3/FA4 高度一致的结果，足以支持方法可跨架构表达复杂策略。作者还公开了负结果：Triton lowering 失败、joint Hopper 版本略慢、`ptxas` spill，这比只报最好柱状图更可信。但 workload 仍只有 [[Flash-Attention]] 一个算法家族，全部高性能代码由作者手工编译；没有 GEMM、convolution、[[MoE|MoE]]、[[Quantization|quantized]] kernel 或非 NVIDIA GPU，也没有证明“大类迭代程序”都能在合理时间求解。

### 系统性缺陷

完整流程同时依赖 CBC、Yices2、SCIP、人工 machine description、外部 tile/depth tuner 和手工 CUDA lowering。任何一个成本或容量标注错误都可能让最优性证明回答错误问题。Blackwell spill 已经展示 register allocator 与约束模型脱节；自动后端若再引入 layout conversion 或额外 synchronization，schedule 可能不再可执行。论文也没有讨论求解器 timeout、unsat core 诊断、模型版本管理和新 GPU bring-up 的测量工作量，工程上还不是可直接替代专家的 compiler pass。

## 局限与后续工作

- **闭合自动 lowering**：把 Twill annotation 接入一个能正确生成 CUDA 的后端，在不手改代码的条件下复现图 7–11；验收指标应同时包含编译成功率、spill 数和距手工库的性能差。
- **联合 register allocation**：将实际 `ptxas` allocation 反馈成约束，或直接共优化物理寄存器；要求所有模型判定可行的候选都不出现未预测的 local-memory spill。
- **扩大 kernel 集合**：在 GEMM、convolution、MoE、quantized attention 和归约各选择至少 3 个 shape，比较 Triton heuristic、PipeThreader 与 Twill 的吞吐、search time 和人工调参量。
- **扩展控制流**：采用论文提到的 hierarchical reduction 支持嵌套或带分支循环，并为每个新增结构给出 soundness/completeness 测试，而不是只观察性能。
- **做鲁棒成本建模**：把 TMA/cache latency 表成区间或多场景目标，验证输出 schedule 在不同序列长度、频率与并发压力下都不比单点模型最优解差超过预设阈值。

## 相关

- **相关概念**：[[Tensor-Core]]、[[Flash-Attention]]、[[Attention]]
- **相关论文**：[[FlashAttention-3-NeurIPS24]]、[[FlashAttention-4-MLSys26]]、[[PipeThreader-OSDI25]]
- **同会议**：[[OSDI-2026]]
- **原始材料**：[[osdi26-soi]]、[[osdi26-soi.pdf]]
