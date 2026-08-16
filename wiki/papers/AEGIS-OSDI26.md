---
type: paper
name: AEGIS
full_title: "Safeguarding LLM Training at Scale: Online SDC Detection and Insights from 35 Million GPU Hours"
authors: [Kinman Lei, Liyan Zheng, Xiang Li, Hongmin Chen, Yun Zhang, Gaohong Liu, Zuquan Song, Zixuan Ma, Zhiyu Xue, Minghui Yu, Shuguang Wang, Wencong Xiao, Haibin Lin, Yuyang Jin, Jidong Zhai, Bo Liu, Xin Liu]
venue: OSDI
year: 2026
tags: [distributed-training, silent-data-corruption, gpu-reliability, fault-detection, operational-systems]
source_pdf: "[[osdi26-lei.pdf]]"
source_md: "[[osdi26-lei]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# AEGIS：大规模 LLM 训练中的在线静默错误检测

> **原题**：Safeguarding LLM Training at Scale: Online SDC Detection and Insights from 35 Million GPU Hours

> **一句话总结**：AEGIS 把“在线发现可疑计算”和“离线确认错误”拆成 cSensor 与 cVerifier，并组合高精度代数校验和训练中已有的重复计算；它在 3,500 万 GPU-hours 的生产部署中以平均 0.86% 开销发现 18 起 SDC，但这个开销来自采样策略，不能理解为每个算子都被完整检查。

## 问题与动机

静默数据损坏（silent data corruption，SDC）不会触发普通异常、ECC 报警或进程退出，却会让 GPU 返回错误数值。大规模 [[LLM]] 训练中，一个错误可以进入激活、梯度和 collective，最后污染许多设备，甚至让长时间训练得到不可用模型。

离线诊断不能解决全部问题。论文观察到，同一块故障 GPU、同一工作负载重复运行时，错误可能只偶尔出现；错误还依赖具体输入数值和算子。对一块已经发生过 SDC 的 GPU 连续运行 nanoGPT 50 次，只有 1 次 loss 分叉。另一次 Matmul 重放 9.2×10^5 次，只看到 3 种错误结果（§3.1）。因此，设备“通过压力测试”不代表它在真实训练输入上安全。

在线方案也有冲突：每一步做完整重复计算太贵，只看 loss 或数值 outlier 又容易误报。AEGIS 的目标是让轻量检测留在训练关键路径，把昂贵确认移出关键路径，并允许多种检测机制共用一套调度与确认框架。

## 关键观察 / 隐含假设

- **SDC 很少、非确定且依赖输入。** 同一故障可能隔几秒，也可能隔几天才再次出现；调节 Matmul 输入的缩放因子后，只有部分数值区间会触发错误（图 2、§3.1）。在线检测必须看到真实训练输入。
- **不同故障没有统一信号。** 生产事件出现在不同算子、矩阵单元和 HBM 路径中。单一 checksum 或离线诊断无法覆盖全部错误，所以系统需要互补传感器（表 2）。
- **低精度输出会淹没小错误。** 直接对 bfloat16 输出求 checksum 时，正常舍入误差可能比故障扰动更大；现代 [[Tensor-Core]] 内部已有 float32 accumulator，可以在截断前生成更干净的校验信号（图 5–6）。
- **训练本身包含重复计算。** 激活重计算和 [[Flash-Attention]] backward 内部重计算为“同一确定性计算应逐位相同”提供了近乎免费的参考（§5.1.2）。
- **传感与确认可以解耦。** 大部分 inline 信号只需保存少量行、列、输出或 fingerprint；确认任务可以排队，在 pipeline bubble 或 step 末尾的小时间片执行（§5.2–§5.3）。
- **核心前提是确定性。** 相同输入和执行配置必须产生相同结果，否则 bitwise replay 会把正常非确定性当成错误。采样还假设未被抽中的计算风险可以接受。

## 核心方法

### 1. cSensor–vTask–cVerifier 两阶段流水线

cSensor 在受保护算子之后运行轻量校验，记录紧凑证据。若差值超过阈值，它把证据和最小重放上下文封装为 vTask，放入 cVerifier 队列。cVerifier 不阻塞当前算子，而是在 GPU 自然空闲期或每个 step 末尾的受限时间片执行重放，再给出确认结果（图 3、§4–§5.3）。

确认后，平台可以隔离故障 GPU，并从较早 checkpoint 重启。这个架构把“高召回的可疑信号”和“低误报的最终结论”分开，也让新传感器只需实现统一 vTask 接口。

### 2. 利用 float32 accumulator 的 Matmul 校验

经典矩阵校验比较 `(AB)1` 与 `A(B1)`，其中 `1` 是全 1 向量。两条等价路径差异过大时，说明 Matmul 可能出错。问题是最终 bfloat16 输出已经被截断，正常数值噪声会掩盖较小故障。

AEGIS 在 GPU kernel 内直接从 float32 accumulator 累积 checksum，再输出 bfloat16 结果。这样不改变训练精度，却显著降低校验噪声。对 forward/dgrad，vTask 只需保存输入 A 的一行及对应输出；对 wgrad，需要 A 的行、B 的列和对应结果，因此 row+column 配置内存复制更多，但覆盖更完整（图 4–6、§5.1.1、§5.2）。

### 3. 用 Attention 不变量覆盖一条计算链

在 [[Attention|注意力]] 算子的 [[Flash-Attention]] backward 中，`dV = P^T dO`，而 softmax 的每一行和为 1，因此应满足 `1^T dV = 1^T dO`。AEGIS 从 float32 accumulator 求两边的列和，差异超过阈值时生成 vTask（图 7）。

这个不变量不只检查最后一步 `dV`。P 在 backward 中由 QK、softmax 和 forward 保存的 LSE 重建；这些上游计算若破坏“每行和为 1”，最终不变量也会失败。因此，一个很小的 checksum 可以间接覆盖一段算子链。不过，能保持该不变量的错误仍可能逃逸。

### 4. 复用确定性重计算做逐位比较

训练框架常为节省显存而重算 activation。AEGIS 对原始结果和重算结果各做 xorsum fingerprint；cVerifier 比较二者，任何 bit 不同都视为已确认异常。相同办法也用于 FlashAttention 内部已有的 backward 重计算，并可覆盖 RMSNorm、GeLU 等不适合代数 checksum 的算子（图 8、§5.1.2）。

为了扩大覆盖，论文建议把 fingerprint 放在一段确定性重计算图的末端：若上游错误传播到最终输出，一次比较就能覆盖整段图。代价是 xorsum 属于压缩摘要，论文没有分析碰撞概率。

### 5. 控制阈值、采样和补充告警

数值尺度会随训练变化。AEGIS 的阈值在出现大差值时暂时翻倍，之后逐步减半回到较敏感水平，以避免正常分布漂移制造大量 vTask。算法检测还可以按算子动态采样，把总开销限制在预算内（§5.1.3、§6）。

此外，系统在 [[Data-Parallelism|数据并行]] rank 间 all-gather 紧凑差值，以 P90 作为基线。某个 rank 高出基线极大倍数时，例如 10^6 倍，会发出离群告警（outlier warning）。这种告警只是排查线索，不是 cVerifier 已确认的 SDC（§5.4）。

## 设计取舍

- **采样开销换覆盖率。** 生产平均 0.86% 开销来自稀疏启用算法检测；采样越少，越可能漏过只出现一次的间歇错误。
- **异步确认换检测延迟。** vTask 不阻塞算子，但队列积压时，错误可能在确认前继续传播。论文没有报告确认延迟分布或最大 backlog。
- **确定性换适用范围。** bitwise replay 很强，但非确定 kernel、随机控制流或执行配置变化会破坏参考。
- **高精度 checksum 换 kernel 改造。** 从 accumulator 取 checksum 比直接读输出准确，却需要修改核心 Matmul/Attention kernel，移植到新算子和新硬件并非免费。
- **阈值适应换敏感度。** 自动抬高阈值能抑制正常噪声，也可能在小幅真实故障连续出现时降低敏感度。
- **统一框架换算子专用工作。** vTask 接口统一了系统部分，但每类算子仍要设计不变量、最小重放上下文和精度策略。

## 实验设计

评测全部运行在生产 GPU 集群，每个节点通常 8 块 GPU。受控开销实验使用 70B 和 268B 模型，序列长度 8,192、global batch 768，规模为 128–1,024 GPUs；每个结果取 10 个稳定 iteration 平均。row 配置不完整覆盖 wgrad，row+column 配置覆盖所有 Matmul 类别，两者都启用确定性检测（§7.1、§7.4）。

检测能力有三类证据：3,500 万 GPU-hours 的线上部署；8 台曾经发生 SDC、但已通过生产入场筛查的机器，每台重复训练 10 次；以及在健康机器上做的受控 fault injection。注入实验先收集 500 iteration 的正常差值，再以每个算子的 float32 中位差值为尺度，按 0.02% 概率扰动随机元素，每个设置重复 100 次（§7.2–§7.5）。

## 实验与结果

- **生产部署说明问题真实，但不提供完整 ground truth。** 3.5×10^7 GPU-hours 中，AEGIS 发现 18 起 SDC，涉及 13 块故障 GPU，平均训练开销 0.86%。只有 3 起表现为 NaN 等可见训练失败，其余 15 起原本是静默的。确定性检测发现 12 起，算法检测及其 outlier 发现 6 起，说明两类机制互补；但算法检测在生产中只做采样（图 13、§7.2）。
- **真实故障机器比离线诊断更能支持检测能力。** 对 8 台历史故障机器，每台训练 10 次，AEGIS 最终识别 8/8，vendor offline diagnostics 识别 2/8，而且没有单个传感器覆盖全部机器。这个结果不能直接解释为一般性的 100% 对 25% recall：这 8 台机器都先通过过离线筛查，样本本来就偏向“离线难检”的故障（表 2、§7.3）。
- **完整配置开销应与生产采样开销分开看。** row-only 配置平均 slowdown 少于 1.61%，最大 2.1%；row+column 配置平均 2.35%，最大 2.6%。后者覆盖 wgrad，但需要额外保存 B 的列。动态采样率与开销近似线性，生产才把目标调到 0.86%。实验测到 1,024 GPUs，且没有新增训练通信，但不能据此证明更大规模仍完全不变（图 14–15、§7.4）。
- **高精度 accumulator 是算法检测成立的关键。** 500 iteration 正常运行中，float32 checksum 差值明显小于 bfloat16。按算子自身中位差值注入扰动时，float32 在 `r=1` 已接近 100% 检出；bfloat16 在这个尺度几乎无响应，约需 10^4 倍扰动才接近相同检测率。这是校准后的数值扰动，不等同真实随机 bit flip 分布（图 16、§7.5）。
- **案例能定位到计算与内存两类错误。** 一个故障只在 execution unit 94 的 matrix core 执行特定 MMA 指令时出现，输出错误位置呈周期模式；另一个 HBM 事件让 forward 保存的 float32 中间值翻转 1 bit，却没有触发 ECC，最终由重计算 fingerprint 发现。生产中所有可确认事件都能在原 GPU 上再次出现，但间隔从秒到天；重启可能暂时让诊断通过，一个月后错误仍复发（图 17、§7.6、§8）。

## 论断—证据表

| 论断 | 论文证据 | 证据边界 | 置信度 |
|---|---|---|---|
| 在线 sense-then-verify 能发现普通离线筛查漏掉的真实 SDC | 3,500 万 GPU-hours 发现 18 起；8 台历史故障机识别 8/8 | 没有全量故障 ground truth；8 台机器存在预筛选偏差 | 强 |
| 多种传感器必须互补 | 生产中确定性方法发现 12 起，算法方法及 outlier 发现 6 起；表 2 无单一方法全覆盖 | 当前实现主要覆盖 Transformer backbone | 强 |
| float32 accumulator 让低精度训练的代数校验更敏感 | 图 16：中位尺度扰动接近 100% 检出，bfloat16 约需大 10^4 倍 | 人工校准扰动，不代表真实硬件错误分布 | 强 |
| 可在低开销下扩大到千卡训练 | 完整 row+column 平均 2.35%、最大 2.6%；生产采样平均 0.86%；测到 1,024 GPUs | 两个模型配置，受控结果只平均 10 iterations | 中强 |
| AEGIS 能避免所有训练污染 | 找到 1 块保护区外的额外故障 GPU；作者明确不能排除未知漏检 | 未覆盖轻量算子、通信和全部软件路径 | 弱 |

## 批判性分析

### 论证链条

论文从三个生产事实出发：错误非确定、依赖输入、模式多样；然后分别推出在线感知、互补传感器和异步确认三个需求。float32 accumulator 消融解释了算法校验为什么在低精度下可用，8 台真实故障机器和 3,500 万 GPU-hours 又补足了合成注入无法说明的真实性，链条较完整。

必须保持三个结论边界。第一，0.86% 是生产采样策略，不是 full coverage 成本。第二，8/8 是经过离线预筛选的历史故障样本，不是对全部 GPU 故障的无偏 recall。第三，18 起是“AEGIS 观察到的 incident”，不能直接除以 GPU-hours 当成普适硬件故障率，因为设备被移除、检测配置变化，同一故障还可能反复触发。

### 假设压力测试

AEGIS 要求受保护计算确定。实际训练可能使用非确定性归约、不同 kernel autotune 选择、随机稀疏路由或动态 shape；这些变化会使 bitwise replay 不再是可靠参考。一次生产告警来自越界写的软件 bug，说明系统能发现更广的错误，但也说明“fingerprint 不同”不能自动归因于硬件。

算法 checksum 只观察低维投影。某些错误可能正好抵消或保持 `1^T dV = 1^T dO`；xorsum 也存在理论碰撞。更重要的是，间歇故障在 cSensor 与 cVerifier 的两次执行中可能恰好产生相同错误或不再出现。论文没有给出这些漏检概率的上界。

动态阈值遇到大差值会翻倍。如果真实错误先以小幅、持续方式出现，阈值可能向错误分布适应。DP-rank outlier 用 P90 和极大倍率比较，也会在 warm-up 的分布外数值上误报；生产 21 次 warning 中至少 3 次来自 warm-up，另有部分长期可疑但无法离线复现（§8）。

### 实验可信度

3,500 万 GPU-hours 是强生产证据，真实 matrix unit 与 HBM 案例也比单纯 bit injection 更有价值。作者报告一个保护区外的漏检、warning 误报和软件 bug，而不是只展示成功案例，这使边界更清楚。

但生产环境没有可观测的“所有真实 SDC”标签。周期性 deterministic cluster replay 只找到一块额外故障 GPU，能增加信心，不能证明没有更安静的漏检。受控开销只取 10 个稳定 iteration；模型、GPU 代际和 kernel 细节没有充分展开，外部团队也难复现生产故障。注入按 checksum 差值尺度构造，适合比较精度，不适合估计真实硬件 recall。

### 系统性缺陷

当前保护重点是 Transformer backbone 的 Matmul、FlashAttention、normalization 等路径。独立 element-wise、optimizer state、控制流、通信和 backbone 外计算仍可能逃逸；论文确实找到一块在保护区外出错的 GPU。没有观察到通信 SDC 只说明该部署中未发现，不能证明链路端到端完整性已经解决。

检测后的系统动作也不完整。AEGIS 依赖 checkpoint rollback，但没有测从错误发生到确认的延迟、这段时间污染传播范围、可证明干净的 checkpoint 如何选择、回滚浪费或 vTask backlog。大规模训练真正关心的是“最终模型是否未被污染”，而论文主要证明“若被传感器看到，能定位并确认一部分计算错误”。

## 局限与后续工作

- 扩展到 optimizer、独立 element-wise、通信、HBM 读写和 Transformer backbone 外部路径，报告每类算子的实际 coverage。
- 记录 vTask 排队、确认延迟、最大 backlog 和错误传播步数，并把 checkpoint provenance 与检测事件关联起来。
- 用真实 bit flip、不同 GPU 代际和公开故障 corpus 补充“按 checksum 尺度注入”的实验。
- 对非确定 kernel 建立容忍模型，区分硬件 SDC、合法非确定性和软件内存破坏。
- 分析 checksum/xorsum 碰撞、两次重放同时出错和动态阈值被错误抬高时的漏检上界。
- 长期报告按算子与采样率分层的 incident 数，避免把部署观察误解为硬件总体故障率。

## 相关

- **相关概念**：静默数据损坏、算法型故障容错、故障检测、[[Tensor-Core]]、[[Flash-Attention]]、[[Data-Parallelism]]
- **相关系统**：[[PyTorch]]、checkpoint/restart
- **同会议**：[[OSDI-2026]]
