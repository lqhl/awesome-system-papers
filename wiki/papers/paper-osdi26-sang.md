---
type: paper
name: SANI
full_title: "Unleash All Cores: Scalable Asymmetry-aware DNN Inference on Mobile CPUs"
authors: [Qianlong Sang, Puyi He, Huanghuang Liang, Yili Gong, Chuang Hu, Xiaobo Zhou, Dazhao Cheng]
venue: OSDI
year: 2026
tags: [mobile-inference, asymmetric-cpu, dnn-inference, task-scheduling, kernel-affinity]
source_pdf: "[[osdi26-sang.pdf]]"
source_md: "[[osdi26-sang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-02-06
---

# 让移动 CPU 用满所有核心：面向非对称性的可扩展 DNN 推理

> **原题**：Unleash All Cores: Scalable Asymmetry-aware DNN Inference on Mobile CPUs

> **一句话总结**：移动 AMP CPU 中加入 LITTLE 核可能因同步等待使延迟增加最多 37%；SANI 用按簇选择 kernel、按运行时速度合并/拆分任务、迁移时转换 kernel 三个机制，在五种 SoC 上将延迟降低 17.6%–23.7%，并将能耗最多降低 39%。

## 问题与动机

移动 SoC 常同时包含高性能 big 核和高能效 LITTLE 核。DNN 推理若把一个算子的输出平均切分给线程，big 核会先完成工作，在同步屏障处等待 LITTLE 核。论文在 Pixel 9 上观察到，加入 LITTLE 核后端到端延迟反而最多增加 37%。等待延迟约从总时间的 5% 上升到 30%（图 4）。

现有方案各有缺口。Arm-CL 通常只使用同类 big 核，避免失衡却浪费 LITTLE 核；MNN 按固定性能比例静态分配，无法适应移动设备上的抢占和背景负载；AsyMo 使用细粒度动态任务，适应性更强，但频繁取任务会增加开销。另一个被忽略的问题是 core–kernel affinity：不同 CPU 簇对算子 kernel 的偏好不同，统一使用一个 kernel 会让至少一类核心执行非最优实现。

## 关键观察 / 隐含假设

- **观察 1：固定任务大小无法同时控制执行和等待延迟。** 大任务减少取任务次数，却让被干扰的线程长时间拖住屏障；小任务降低单次拖尾，却增加 dequeue 开销。图 5 展示了这个折中。
  - **依赖假设**：算子能够沿输出张量维度切分，并且线程级并行收益足以抵消调度成本。
  - **可能失效场景**：输出维度很小、算子不可有效切分，或每个任务的共享内存访问远超计算成本时，拆分和合并都可能收益有限。
- **观察 2：核心类型与 kernel 存在稳定但不同的亲和性。** 表 1 中 GEMM 在 big 核上的最佳 kernel 比替代实现快 9.1%；DepthWise convolution 使用非亲和 kernel 时性能下降超过 34%。
  - **依赖假设**：离线测得的微架构、SIMD 和 cache 特征足以预测在线 kernel 排名。
  - **可能失效场景**：频率变化、温控降频、系统负载或新的 SoC 改变 kernel 排名时，静态代价模型可能过时。
- **假设 3：应用层可以控制线程绑核和算子任务。** SANI 覆盖 Arm-CL 的 `schedule_common()`，用 pthread 绑定线程，并将调度粒度置于 OS 线程之上。该假设在 Android/Linux 上较强，但依赖运行时允许这种绑定且不会频繁迁移线程。

## 核心方法

SANI（Scalable Asymmetry-aware Neural Inference）在 Arm-CL 上实现，由三个相互配合的组件组成。

首先，亲和性感知 kernel issuer 为每个算子和 CPU 簇选择不同的 kernel。代价模型结合计算量、内存访问量和指令与微架构的兼容性，使用离线延迟测量拟合 big/LITTLE 簇的权重。若两簇的最佳实现不同，系统异步准备双 kernel，包括权重预转置、内存分配和索引映射。

其次，issuer 将不同 kernel 的原生 tile 统一为 block。block 尺寸取候选 tile 各维度的最小公倍数，并固定 height-first 遍历顺序。big 和 LITTLE 簇使用分离队列：这样可保持私有 cache 局部性，也避免所有线程争用一个全局队列。这个设计回应了观察 2，同时为迁移建立统一坐标。

第三，自适应粒度调度器以轮次运行，记录每个线程完成 block 的时间。较快线程下一轮合并更多连续 block，较慢线程将下一个 block 拆成更小任务。计数器控制每个线程下一轮合并或拆分的程度；拆分时优先选择仍有足够迭代空间的最小维度。它用运行时速度反馈吸收 core asymmetry 和背景干扰，直接回应观察 1。

当某一簇队列耗尽时，调度器允许跨簇迁移。按源 kernel 的布局创建的任务不能直接交给目标簇，因此 on-demand kernel switcher 用预计算索引表把同一输出区域映射到目标 kernel 的任务索引。小任务低于阈值时跳过转换；合并任务采用列式范围转换，以减少逐 block 查表成本。

## 设计取舍

- **动态性换取调度状态和测量开销**：合并/拆分避免固定比例失衡，但需要每轮记录完成时间、排序线程并维护队列。
- **双 kernel 换取内存与准备时间**：权重预转置和索引表增加模型加载工作；实测峰值额外内存低于 2 MB，复杂 ShuffleNet 的相关运行时开销低于 3 ms（表 3）。
- **分离队列换取迁移复杂度**：分离队列减少 dequeue 竞争并保留 cache 局部性，但队列耗尽时必须执行 kernel 转换，且转换策略依赖预计算布局映射。
- **应用层调度换取通用性边界**：SANI 能理解算子形状，却不能像 OS 调度器一样直接处理任意应用；它也没有解决大型移动端 LLM 的主要 NPU/内存瓶颈。

## 实验与结果

- 在 Pixel 9、OPPO Find X3 Pro、Redmi K60、OnePlus Ace 5 Ultra 和 Odroid XU4 上，用六个模型（MobileNetV2、ResNet-50、SqueezeNet、ShuffleNet、Inception-V3、GPT-2）进行 FP32/NEON 测试。相对 Native，平均延迟降低 17.6%–23.7%；相对 AsyMo 和 MNN 也分别降低约 9.8%–15.7% 和 12.0%–16.7%（图 10）。
- 按模型看，Inception-V3 相对 Native 降低 29.5%，GPT-2 降低 16.1%。Inception-V3 的 Permute kernel 并行维度仅为 7，SANI 的 block 统一和粒度调度在避免 AsyMo 过细任务的同时保留了并行度（图 12）。
- 在 Pixel 9 的 ShuffleNet、4 big + 1 LITTLE 配置中，SANI 相对 Native 降低 19.3%，相对 AsyMo 降低 15.3%；在 Find X3 的 ResNet-50 全核心配置中相对 Native 降低 19.4%（图 13）。基线加入 LITTLE 核后出现收益递减或退化，SANI 仍能扩展。
- MobileNetV2 在 CPU 空闲、50%/100% 压力和 YouTube 播放场景下，SANI 的等待时间比基线低 20%–40%，执行时间低 7%–10%（图 14）。
- Find X3 上 ResNet-50 和 Inception-V3 的能耗相对 Native 降低 34.1%–35.3%，相对 AsyMo 降低 32.5%–39.0%（图 15）。
- 消融实验显示，在 4B+4L 配置下，issuer、调度器和 switcher 对 SqueezeNet 的增量收益分别为 9.5%、10.5% 和 7.1%，对 ShuffleNet 分别为 9.6%、13.5% 和 8.0%（图 16）。在 4B 对称配置中，switcher 几乎无收益，说明其收益确实来自异构迁移。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| LITTLE 核可能让朴素 AMP 推理变慢 | Pixel 9 的线程扩展与等待分解，图 3–4 | 四个 CNN、最大频率、无并发应用的初始测量 | 强 |
| 自适应粒度能缓解真实运行时干扰 | MobileNetV2 的压力和 YouTube 场景，图 14 | Pixel 9，四种干扰配置 | 中 |
| 三组件组合能跨 SoC 扩展 | 五设备端到端延迟，图 10、13 | Arm-CL、FP32，五种移动平台和有限模型集 | 中 |
| 能效收益并非单纯来自降低延迟 | Find X3 功耗测量，图 15 | 仅 OPPO Find X3 使用 Monsoon 精确测功耗 | 中 |

## 批判性分析

### 论证链条

论文的链条基本闭合：测量先把性能崩溃归因于屏障等待，再将静态粒度和统一 kernel 分别对应到两个观察，最后用消融拆分三组件收益。图 16 支持组件的独立贡献。需要保留的跳步是：作者把小规模手机实验中的可扩展性外推到更广泛 SoC；五台设备虽覆盖不同厂商，但并不等于 production 设备和动态频率环境的全面覆盖。

### 假设压力测试

自适应调度按最近一轮完成时间给线程加减任务计数，隐含了线程速度在相邻轮次具有一定相关性。若负载周期性变化或频繁温控降频，历史排名可能产生振荡。分离队列也假设簇内 cache 热度值得保留；若迁移频繁，转换和数据局部性收益可能被抵消。GPT-2 只使用随机固定长度 20-token prompt，不能代表长上下文、连续 batching 或 KV cache 受限的 LLM 服务。

### 实验可信度

基线均移植到 Arm-CL，避免不同框架 kernel 优化造成不公平，这一点有利于隔离调度策略。模型覆盖 CNN 和一个 transformer，仍偏向 operator-level、FP32 工作负载。能耗只在一台设备上精确测量；论文没有报告温度、频率随时间变化、模型加载成本、P99 延迟或多租户隔离。因此能耗和服务级 SLO 结论应限于当前测试设置。

### 系统性缺陷

论文未评估错误恢复、线程绑核失败、Android 调度策略变化和长期温控行为。双 kernel 的权重布局和 map 需要按 operator-shape 管理，模型动态 shape 或算子覆盖不足时会增加工程复杂度。论文还未讨论迁移过程中 cache/内存带宽竞争，以及多个推理请求并发时队列和反馈是否仍能独立工作。

## 局限与后续工作

- **局限 1**：主要证据来自五个 SoC、六个模型和 Arm-CL/Arm NN；对量化模型、动态 shape、并发请求和长上下文 transformer 的覆盖有限。
- **局限 2**：代价模型在离线 profiling 中拟合，尚未证明跨频率、温控状态和系统版本长期稳定。
- **后续工作 1**：在频率动态变化和可控周期性干扰下记录任务完成时间序列，测量调度器是否振荡，并比较不同反馈窗口和阻尼策略的 P99 延迟。
- **后续工作 2**：在 INT8、动态 batch、长序列 transformer 及真实多请求 trace 上评估双 kernel 和迁移 map 的内存、吞吐与能耗成本。
- **后续工作 3**：将 SANI 的 block/affinity 抽象扩展到 CPU-GPU-NPU 协同执行，明确 kernel 转换与跨加速器数据布局转换的边界。

## 相关

- **相关概念**：[[Asymmetric Multiprocessing]]、[[DNN Inference]]、[[Kernel Selection]]、[[Work Stealing]]
- **同类系统**：[[Arm-CL]]、[[MNN]]、[[AsyMo]]
- **同会议**：[[OSDI-2026]]
