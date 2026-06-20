---
type: paper
name: DynaFlow
full_title: "DYNAFLOW: TRANSPARENT AND FLEXIBLE INTRA-DEVICE PARALLELISM VIA PROGRAMMABLE OPERATOR SCHEDULING"
authors: [Yi Pan, Yile Gu, Jinbin Luo, Yibo Wu, et al.]
venue: MLSys
year: 2026
tags: [intra-device-parallelism, scheduling, pytorch, overlap, compile]
source_pdf: "[[f7177163c833dff4b38fc8d2872f1ec6.pdf]]"
source_md: "[[f7177163c833dff4b38fc8d2872f1ec6]]"
---

# DYNAFLOW: TRANSPARENT AND FLEXIBLE INTRA-DEVICE PARALLELISM VIA PROGRAMMABLE OPERATOR SCHEDULING (MLSys 2026)

> **一句话总结**：intra-device overlap/fusion/split 与 [[vLLM]]/[[SGLang]] 顺序执行模型冲突，单模型集成 dual-batch 需 **1.3K LOC/2 月**；DynaFlow 用注解分区图 + 可编程 schedule + 异步后端（预分配 tensor、子图 [[CUDA-Graph]]），在 6 个 ML 系统上 **≤1.29×** 吞吐且可匹配/超专用实现 **1.1×**。

## 问题与动机

[[LLM]] 推理/训练算子交替 compute/memory/network-bound，顺序执行浪费 **~15%**（Fig.3）。overlap、fusion、batch-split 有效但依赖 invasive 全局重排；且最优策略随 batch/硬件而变（A100 partial overlap 优于 full，H100 相反）。

DynaFlow 将 **logical model** 与 **physical schedule** 解耦，作 `torch.compile` backend 透明注入。

## 关键观察 / 隐含假设

- **观察 1：无单一 intra-device 策略普适；Llama-3-70B TP 上策略排名随 batch/硬件变化（Fig.2）。**
  - **依赖假设**：runtime 可编程 schedule 比静态融合更重要。
  - **可能失效场景**：若 compiler 已自动 overlap 足够好，增量有限。

- **观察 2：SGLang dual-batch 单模型集成 **>1.3K lines/2 months**——可复制成本 prohibitive。**
  - **依赖假设**：注解+Python schedule API 可将集成降到「minimal code changes」。
  - **可能失效场景**：极复杂 MoE 路由 schedule 表达力边界。

- **观察 3：6 个 SOTA ML 系统上 representative 策略集成 **1.29×** peak，匹配专用实现并 **1.1×** 超之案例。**
  - **依赖假设**：子图级 CUDA Graph/TorchInductor 兼容保留低 overhead。
  - **可能失效场景**：动态 shape 频繁时子图 graph 捕获失败。

- **假设 1**：scheduling granularity 在「可表达 overlap」与「dispatch 开销」间用 annotated subgraph 平衡。**
  - **证据强度**：**强**——多系统多策略实证。

## 核心方法

**Frontend**：用户注解划分子图；Python-native 定义非顺序执行序。

**Backend**：异步控制/数据流；预分配中间 tensor 消 copy；子图级 CUDA Graph/Inductor。

**Integration**：`torch.compile` backend 嵌入 [[PyTorch]] 系系统。

## 设计取舍

- **透明性 vs 极致性能**：略低于手工 CUDA fusion kernel（个别 case 赢 **1.1×**）。
- **Expressive schedule vs 用户负担**：需学习 schedule API。
- **vs [[TokenWeave]]**：TokenWeave 是特定 AR+RMSNorm 融合；DynaFlow 是通用 substrate，可承载类似策略。
- **边界条件**：Llama/DeepSeek 等；batch 512 seq 1024 等 profile 场景。

## 实验与结果

- 6 ML systems：**up to 1.29×** throughput vs original。
- vs specialized implementations：match or **up to 1.1×** better。
- 代表策略：comm-compute overlap、fusion、micro-batch split 三类 Fig.1。

## Critical Analysis

### 论证链条

编程模型不匹配是 adoption Barrier → 解耦 schedule → 多系统验证，系统论文论点扎实。1.29× 平均感知可能因 peak 案例拉高，需看 median。

### 假设压力测试

与 [[DynaFlow]] 名冲突无；与全局 compiler auto-schedule 长期竞争。多租户 serving 动态 batch 使 schedule 选择需 online policy——DynaFlow 提供机制非 policy。

### 实验可信度

6 系统覆盖面广；对比含专用实现。缺：months-long 维护成本量化（vs 2月1.3K行）。

### 系统性缺陷

论文未讨论 schedule 错误导致 silent race、debug 工具链。与分布式 TP/EP 交界 schedule 未深谈。

## 局限与 Future Work

- **局限 1**：用户需写 schedule，非全自动。
- **局限 2**：极端动态 shape 下 graph 捕获脆弱。
- **Future work 1**：learned schedule selector 用 [[Charon]] 仿真器反馈。
- **Future work 2**：与 [[TokenWeave]] fused kernel 作为子图 plugin 对比维护成本。

## 相关

- **相关概念**：[[CUDA-Graph]]、[[Tensor-Parallel]]、[[torch.compile]]
- **同类系统**：[[vLLM]]、[[SGLang]]、NanoFlow、DualPipe
- **同会议**：[[MLSys-2026]]