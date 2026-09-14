---
type: paper
name: AEGIS
full_title: "Safeguarding LLM Training at Scale: Online SDC Detection and Insights from 35 Million GPU Hours"
authors: [Kinman Lei, Liyan Zheng, Xiang Li, Hongmin Chen, Yun Zhang, Gaohong Liu, Zuquan Song, Zixuan Ma, Zhiyu Xue, et al.]
venue: OSDI
year: 2026
tags: [llm-training, silent-data-corruption, gpu-reliability, fault-detection, mixed-precision]
source_pdf: "[[osdi26-lei.pdf]]"
source_md: "[[osdi26-lei]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-13
---

# 面向大规模 LLM 训练的 SDC 在线防护（OSDI 2026）

> **原题**：Safeguarding LLM Training at Scale: Online SDC Detection and Insights from 35 Million GPU Hours

> **一句话总结**：LLM 训练中的静默数据损坏（SDC）具有非确定性和输入敏感性，离线诊断难以覆盖；AEGIS 用临界路径上的轻量传感器（cSensor）筛选可疑计算，再利用空闲期执行延迟验证（cVerifier），在 3.5×10^7 GPU-hours 中发现 18 起 SDC、13 张故障 GPU，生产开销为 0.86%。

## 问题与动机

SDC 是硬件产生错误结果但不触发报警的故障。大规模 LLM 训练持续数周甚至数月，单个错误值可能经集合通信传播到整个集群，导致 loss/gradient 异常、模型质量下降或昂贵的回滚。训练框架已有 NaN/inf 监控，但论文观测到 18 起生产事件中只有 3 起表现为可见训练失败。

离线诊断需要中断训练，且测试 workload 有限；论文引用的生产经验显示其 recall 约为 70%，而单次测试可能耗时超过 8 小时。重放能提供更强确认，但在千卡级训练中会复制大量计算。传统算法式校验在 bfloat16 下又容易把正常舍入误差当成故障。

## 关键观察 / 隐含假设

- **观察 1：SDC 非确定且输入敏感。** 同一故障 GPU 上重复执行 nanoGPT 50 次只有 1 次出现 loss 分歧；一次 Matmul 重放 9.2×10^5 次仅得到 3 类错误结果，估计触发率约 2×10^-9。改变 Matmul 输入缩放范围后，故障概率也随之改变（§3.1，图 2）。
  - **依赖假设**：真实训练会遇到离线测试未覆盖的输入和数值区间。
  - **可能失效场景**：故障是确定性的、或离线测试 workload 与生产计算完全一致时，在线检测的相对优势会降低。
- **观察 2：没有单一校验器能覆盖所有故障。** 八张已知故障 GPU 的测试中，确定性检测、算法检测和 outlier warning 的覆盖互补；确定性方法发现的事件数约为算法方法及其 warning 的两倍（§7.2–§7.3）。
  - **依赖假设**：训练中存在可复用的重复计算，且受保护计算在相同输入与执行配置下是确定的。
- **观察 3：现代 GPU 的高精度累加可降低校验噪声。** 直接从 bfloat16 输出累加会放大舍入误差；从 Matmul 内部 float32 accumulator 累加后，注入误差在中位尺度附近接近 100% 被检测，而 bfloat16 校验需要约 10^4 倍更大的扰动（图 5、图 16）。
  - **证据强度**：强，来自故障注入和 500 次无故障训练迭代的分布比较。

## 核心方法

AEGIS 将检测拆成 cSensor-cVerifier 两阶段。cSensor 内联执行轻量感知，保存后续确认所需的最小证据，并把可疑事件封装为统一的 vTask；cVerifier 在流水线气泡等自然空闲期执行确认，无法消化的任务在每个训练 step 末尾占用固定时间片。只有确认阶段成立后才报告 SDC。

第一类传感器是混合精度感知的算法检测。对 Matmul，AEGIS 使用行校验或行列校验比较等价的 checksum 路径，并在 GPU 的 float32 累加器上完成校验。对 FlashAttention，利用 softmax 注意力矩阵行和为 1 的性质，检查 `1^T dV = 1^T dO`；该不变量可间接覆盖部分 QK、Softmax 与 LSE 计算。可疑事件保存必要的输入行、列、输出和重放元数据，cVerifier 再重放并比较结果（§5.1.1、§6）。

第二类传感器利用训练本身已有的自等价计算。激活重计算会在 forward/backward 中生成同一结果，FlashAttention 也会重算中间量。AEGIS 对输出计算 xorsum fingerprint，在两次确定性执行间做 bitwise 比较。为减少任务数量，它只给确定性重计算链末端的算子加检测；上游故障会传播到末端 fingerprint（§5.1.2）。

sensing control 包括自适应阈值、选择性算子插桩和动态采样。算法校验的阈值根据近期 checksum 差值分布增减，以容忍正常数值波动；生产环境则调节算法检测采样率，将开销控制在目标预算内。outlier warning 是独立的启发式通道：跨 DP rank 计算 P90，若某 rank 的差值超过基线约 10^6 倍则报警，但该信号不等于已确认的 SDC（§5.4）。

## 设计取舍

- **延迟确认换取训练吞吐。** replay 被移出关键路径并利用 pipeline bubble，但 backlog 仍可能积累；论文仅以固定 step 尾部时间片兜底，未给出高故障率下的队列稳定性界限。
- **高覆盖依赖确定性。** fingerprint 比较能检测极小差异，但随机算子、非确定性 kernel 或软件版本变化会制造误报或使确认失效。
- **选择性检测换取低开销。** 动态采样让生产开销降至 0.86%，同时牺牲了算法检测的时空覆盖；确定性检测覆盖更广，但依赖激活重计算等已有冗余。
- **算子专用设计换取检测精度。** Matmul 和 attention 获得了强校验，但独立 element-wise 算子和 Transformer backbone 之外的计算仍可能漏检。

## 实验与结果

- 生产部署覆盖 3.5×10^7 GPU-hours、约 10,000 GPU 的训练任务，发现 18 起 SDC、13 张故障 GPU；性能开销 0.86%，仅 3 起表现为 NaN 等可见训练失败（§7.2）。
- 在 8 张真实故障 GPU 上，AEGIS recall 为 8/8；厂商离线诊断仅发现 2/8（25%）。作者指出样本已先通过严格离线筛选，因此不能直接与其他环境的 70% recall 数字等同（§7.3，表 2）。
- 在 70B 和 268B 模型、最多 1,024 GPU 的测试中，启用行校验时平均开销低于 1.61%、最大 2.1%；启用行列校验时平均 2.35%、最大 2.6%（图 14）。
- 动态采样开销近似随采样率线性增长，生产中据此将目标开销设为 0.86%（图 15）。
- 论文部署后通过重放、异常任务失败和 NaN/inf 检查又发现 1 张故障 GPU；该故障位于 AEGIS 未覆盖的 backbone 外部区域（§8）。
- 两个案例分别定位到触发 `mma` 的特定 matrix EU，以及未触发 ECC 的 HBM 单 bit 翻转（§7.6，图 17）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 在线检测能发现离线诊断漏掉的生产 SDC | 8/8 对比 2/8；3.5×10^7 GPU-hours 发现 18 起 | ByteDance 集群、8 张已知故障 GPU | 强 |
| cSensor-cVerifier 可将确认开销移出关键路径 | 生产开销 0.86%；1,024 GPU 最大 2.6% | Megatron-LM、70B/268B、特定训练配置 | 强 |
| float32 accumulator 比 bfloat16 输出校验更敏感 | 同尺度注入近 100% 检出；bfloat16 需约 10^4 倍扰动 | 注入故障、Matmul/相关算子 | 强 |
| 多种检测机制必须互补 | 确定性检测发现 12 起，算法检测及 warning 发现 6 起；另有 1 起保护区外漏检 | 生产事件分类依赖当前插桩范围 | 中 |

## 批判性分析

### 论证链条

论文从非确定性、输入敏感性和故障多样性推出“在线感知 + 延迟确认 + 多传感器”。这条链条对生产部署是闭合的。实验也证明了高精度 checksum 的局部收益和低运行开销。但“只要受保护计算确定，fingerprint mismatch 就是 SDC”这一点在软件 bug 案例中被重新解释为更宽的 correctness alarm；AEGIS 能报告错误，却不能仅凭自身区分硬件故障、HBM 故障与训练框架 bug。

### 假设压力测试

方法依赖 deterministic execution。更换非确定性 CUDA kernel、通信顺序、编译器或并行调度后，bitwise fingerprint 可能不再是可靠参照。方法还依赖 activation recomputation 和 pipeline bubble；没有重计算、采用不同 pipeline schedule 或 GPU 利用率接近满载时，确定性检测覆盖和 verifier 容量都可能下降。生产数据来自单一内部平台，不能直接外推到不同 GPU 代际、AMD/ROCm、云端虚拟化或通信主导型 SDC。

### 实验可信度

论文同时报告真实故障、故障注入、端到端开销和动态采样消融，覆盖了核心机制。八张故障 GPU 的 recall 样本量较小，且是经预筛选后的条件样本；对 false negative 的估计依赖有限次数的 task replay，无法给出严格漏检率。通信诱发 SDC 未被观察到，不能据此证明通信路径不需要检测。

### 系统性缺陷

当前插桩集中在 Matmul、FlashAttention 和可重计算片段；论文明确承认 standalone element-wise 与 backbone 外计算的覆盖缺口。outlier warning 在 warm-up 阶段产生误报，21 个 warning 中只有部分被复现为故障 GPU。论文未系统报告 vTask 队列峰值、额外显存、故障风暴下的调度退化、跨版本确定性维护成本和多租户隔离。

## 局限与后续工作

- **局限 1**：保护区外仍可能漏检，部署后另有 1 起 SDC 未被 AEGIS 捕获。
- **局限 2**：动态采样降低了算法检测概率；论文没有给出采样率与漏检概率之间的统计保证。
- **局限 3**：bitwise 验证要求确定性执行，难以直接覆盖非确定性算子和通信错误。
- **后续工作 1**：为每类算子建立覆盖矩阵，并在固定 GPU-hours 预算下测量采样率、故障触发率和漏检率的关系。
- **后续工作 2**：设计能容忍合法数值非确定性的 verifier，同时保留对 HBM、matrix unit 和软件越界写的定位能力。
- **后续工作 3**：在高 vTask 到达率和无 pipeline bubble 的训练配置下测量队列稳定性、尾延迟和显存压力。

## 相关

- **相关概念**：[[Silent Data Corruption]]、[[Mixed Precision]]、[[FlashAttention]]、[[Activation Recomputation]]
- **同类系统**：[[Megatron-LM]]、[[ATTNChecker]]、[[ByteRobust]]
- **同会议**：[[OSDI-2026]]
