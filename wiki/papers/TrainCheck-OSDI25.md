---
type: paper
name: TrainCheck
full_title: "Training with Confidence: Catching Silent Errors in Deep Learning Training with Automated Proactive Checks"
authors: [Yuxuan Jiang, Ziming Zhou, Boyu Xu, Beijie Liu, Runhui Xu, Peng Huang]
venue: OSDI
year: 2025
tags: [ml-systems, silent-errors, invariant-inference, training-reliability, pytorch]
source_pdf: "[[osdi25-jiang.pdf]]"
source_md: "[[osdi25-jiang]]"
---

# Training with Confidence: Catching Silent Errors in Deep Learning Training with Automated Proactive Checks (OSDI 2025)

> **一句话总结**：TRAINCHECK 从示例训练流水线中自动推断带前置条件的「训练不变量」,在训练时持续校验,在 20 个真实 silent error 中 18 个在一个 iteration 内被检出,同时又在主流训练库中挖出 6 个新 bug。

## 问题

深度学习训练跨越用户代码、框架、编译器、算子库、驱动和分布式栈,极易出现 silent error——不抛异常、loss/accuracy 仍然「看起来正常」,但模型实际已悄悄跑偏。论文中 BLOOM-176B 的例子(DeepSpeed BF16Optimizer 的梯度裁剪 bug 导致未切分的 LayerNorm 权重在各 [[Tensor-Parallelism]] rank 间悄悄发散)整整 10 天才被发现,再花 9 天恢复。

现有手段要么依赖 loss/accuracy 这类高层噪声信号(误报+延迟),要么是针对特定错误类型(如张量 shape 不匹配)的静态检查,覆盖面窄。经典的 Daikon 等不变量推断工具只能捕获 `var1 > var2` 这种低层变量关系,无法表达「跨 TP rank 权重一致」这类 DL 训练语义。

## 核心方法

关键洞察:只要在**合适的抽象层**上观察行为,训练不变量可以是确定性的、无需概率谓词——DL 训练的不确定性往往是因为观察层级过高。TRAINCHECK 把不变量定义在 API 调用和可训练状态层,而非 loss/accuracy 或单一变量层。

流水线三步:
1. **Instrumentation**:用 monkey-patching 注入框架 API hook,用 proxy 对象拦截状态更新,对用户代码零侵入。传统 `sys.settrace` 方案被测出 200×–550× 减速,不可用。
2. **Invariant Inference**:预定义一组通用 relation 模板(如 API 调用序列关系、状态传递关系);把变量抽象为 `(type, attribute, value-constraint)` 三元组 descriptor,避免按实例枚举组合爆炸。针对每条候选不变量,算法从训练 trace 中搜索 precondition(在什么上下文下该不变量成立),把统计显著度高的条件逐步加入直到 precondition「安全」,否则丢弃为 superficial。
3. **Verifier**:把推断出的不变量挂到目标训练任务上,只选择性 instrument 与不变量相关的信息,在线校验,违例时给出触发的不变量和相关 trace 作为调试线索。

关键设计:有 precondition 的不变量**可跨训练程序迁移**——可以用 PyTorch 教程或 HuggingFace 示例作为「invariant 源」推出不变量,再应用到完全不同的生产训练任务。

## 关键结果

- 在 20 个真实 silent error(覆盖 user code、framework、数学算子、硬件、编译器各层)上,18 个在**单个 training iteration 内**被检出并附带调试提示。
- 额外挖出 6 个主流训练库中未知的 silent bug,3 个已修复。
- 8000+ PyTorch 相关不变量中 23% 可迁移到 16 个以上的训练流水线;选择性 instrument 模式下 overhead 通常 <2%,最差 1.6×(发生在仅 2 层 CNN 这种极轻量 toy 任务)。
- 跨 model class 的 false positive 率大多 <2%,仅小规模 CNN 类提高到 2.62%。

## 相关

- **相关概念**:[[Tensor-Parallelism]]、[[MoE]]、[[Pipeline-Parallelism]]
- **同类工作(概念邻居)**:Daikon(通用不变量推断)、HuggingFace / DeepSpeed 的训练健康监控
- **同会议**:[[OSDI-2025]]、[[T2C-OSDI25]]（test 转 runtime checker,思想相近但目标是分布式系统 silent failure）
