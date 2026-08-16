---
type: paper
name: SANI
full_title: "Unleash All Cores: Asymmetry-aware Scalable DNN Inference on Mobile CPUs"
authors: [Qianlong Sang, Puyi He, Huanghuang Liang, Yili Gong, Chuang Hu, Xiaobo Zhou, Dazhao Cheng]
venue: OSDI
year: 2026
tags: [mobile-inference, asymmetric-multiprocessing, scheduling, arm]
source_pdf: "[[osdi26-sang.pdf]]"
source_md: "[[osdi26-sang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# SANI：释放非对称移动 CPU 的全部核心（OSDI 2026）

> **原题**：Unleash All Cores: Asymmetry-aware Scalable DNN Inference on Mobile CPUs

> **一句话总结**：SANI 不再把 big 和 LITTLE 核当成一样快的线程，而是为两类核分别选择合适的 kernel，再根据每个线程刚刚测到的速度动态合并或拆分任务；当任务跨 cluster 迁移时，它把任务索引转换到目标 kernel 的布局，从而避免“多加慢核，推理反而更慢”。

## 问题与动机

移动 SoC 常把高性能 big cores 和节能 LITTLE cores 放在同一个共享内存、缓存一致的芯片中。理论上，推理可以让全部核心共同计算，不需要显式搬动 tensor；但常见 DNN framework 默认核心近似对称，把相同大小的任务平均分给每个线程。在 Pixel 9 的测量中，加入 LITTLE cores 后，端到端 latency 最多反而增加 37%；big cores 在同步 barrier 前等待慢核，使 wait latency 从约 5% 升到 30%（§2.2、图 3–4）。作者把这个现象称为性能坍缩悖论（performance-collapse paradox）。

已有方案的两种修补仍不够。MNN 按静态算力比例粗分工作；任务太大时，一个受到后台干扰的慢线程会拖住全体。AsyMo 把任务切得很细再动态领取；负载更均衡，却让快核频繁 dequeue，增加 task-acquisition overhead。移动端的前台应用、后台服务、DVFS 和抢占会不断改变实际速度，所以不存在始终合适的固定粒度（§2.2、图 5）。

问题也不只有任务数量。同一个 operator 的不同 kernel implementation 对微架构有不同偏好。测量中，GEMM 在 big core 上的最佳 kernel 比另一个快 9.1%，LITTLE core 的偏好却相反；Depthwise convolution 使用不合适 kernel 时慢 34% 以上（表 1）。如果 framework 初始化时只选一个 kernel，至少一类核心会执行不适合自己的代码，跨 cluster 的任务迁移还会把这种错配带到目标核。

CPU 推理仍有实际位置。论文测得，轻量 MobileNetV3 在部分设备上由 CPU 执行可比 GPU 快 6–11 倍，因为 GPU 有 launch 和 data-transfer 成本；NPU 又可能不支持某些 operator，例如 Pixel 9 上 SqueezeNet 回退 CPU 后是 46.5 ms，而可用 NPU 路径是 4.4 ms，OnePlus 12 上若干模型则直接执行失败（§2.1、图 2）。这些结果说明 CPU 是重要的通用或 fallback backend，但不说明 CPU 对所有模型都优于 accelerator。

## 关键观察 / 隐含假设

- **观察 1：任务粒度必须同时控制等待和领取开销。** 大任务减少 dequeue，却放大 slow straggler；小任务方便其他线程分担，却增加快核的 queue 操作（§2.2）。
  - **设计回应**：根据每轮完成时间，让快线程 Merge 更多连续 block，让慢线程 Split 下一项工作，而不是固定比例。
- **观察 2：调度“多少工作”和选择“哪段代码”不能分开。** 即使任务数量完全均衡，把为 big core 准备的 kernel 交给 LITTLE core，仍可能损失 30% 以上（表 1）。
  - **设计回应**：加载模型时准备 cluster-specific kernels，迁移时同步转换 workload index 和 kernel pointer。
- **观察 3：不同 kernel 可以共享一个更高层的空间坐标。** 两个 kernel 的 tile shape 不同，但都覆盖同一 output tensor；用 tile dimensions 的最小公倍数定义统一 block，就能表达相同计算区域（§3.2）。
  - **设计回应**：scheduler 只操作 block，switcher 再将 block 映射回目标 kernel 的原生 workload indices。
- **假设 1：operator 输出能拆成相互独立的连续区域。** SANI 面向可做 operator-level parallelism 的 Conv、Depthwise、GEMM、Permute 等 kernel（§1、§5.5）。
  - **失效边界**：强顺序依赖、很小的 operator、不可分的 vendor kernel 或跨任务共享状态，都可能没有足够 block 可调度。
- **假设 2：最近一轮 completion time 能代表下一轮速度。** scheduler 用轻量在线反馈适应干扰（§3.3）。
  - **失效边界**：若抢占、频率或温度变化比调度轮次更快，上一轮的快线程可能正好在下一轮变慢。
- **假设 3：每种 cluster 的 cost model 可以离线拟合并保持有效。** 计算量、访存量和指令兼容性的权重由该 cluster 上的 latency 样本做线性回归得到（§3.2）。
  - **证据强度**：中。五种 SoC 的结果说明方法可移植，但论文没有报告 profiling 样本数、拟合误差和新设备的 tuning 时间。

## 核心方法

### 亲和性感知的 kernel 分发器

SANI 在模型加载时遍历每个 operator 和候选 kernel。对 operator `O`、kernel `K` 与硬件 cluster `H`，cost model 综合三项：由 tensor shape 与 kernel logic 推算的计算成本、由数据访问模式推算的内存成本，以及 kernel instruction mix 与目标微架构的兼容程度。三个权重按 cluster 离线线性回归；如果 big 和 LITTLE 的最佳项不同，分发器就准备一对 kernel，而不是强迫全部核心共享一个实现（§3.2、图 7）。

双 kernel 的 native tile shape 可能不同。SANI 用各维 tile size 的最小公倍数（least common multiple，LCM）建立统一 block，并固定 height-first 遍历。例如 big kernel 输出 tile 为 `2×4`、LITTLE kernel 为 `2×2`，统一 block 就是 `2×4`。block 只描述 output tensor 中的逻辑区域，具体 kernel 再把它展开为自己的 workload indices。初始 block 按 cluster 相对算力分到 big/LITTLE 两个 queue；分队列也减少全局 queue 争用，并尽量保留各 cluster 私有 cache 中的数据（§3.1–§3.2、图 6）。

准备双 kernel 需要 memory allocation、两份 weight pre-transpose 和 index-map construction。SANI 把不同 kernel 的单线程准备任务并发提交给 thread pool，全部完成后才进入在线推理。这是一次 model-load cost，不会在每次 inference 重复；它能并行隐藏一部分时间，却没有消除 cold-start（§3.2）。

### 自适应粒度调度器

每个 workload `W` 保存 split dimension、各维 start/end 与 kernel pointer。`Merge` 将同一 queue 中连续的小 workload 合成更大的连续区域；`Split` 沿仍有足够迭代次数的最小维度，把一个大 workload 切成多个子任务。两种操作都不改变结果 tensor 的覆盖范围（§3.3、图 8）。

scheduler 按 round 执行。每个线程有 counter `Cᵢ`：`Cᵢ` 至少为 1 时，一次取出并合并 `Cᵢ` 个 workload；小于 1 时，取一个 workload 再按线程数拆分。round 结束后，系统按完成时间排序；最快的 `k` 个线程增加 counter，下一轮拿更多工作，最慢的 `k` 个线程减少 counter，下一轮任务变小。这样，速度较快的核少做 queue operation，速度较慢或受干扰的核不再独占最后一个大任务（算法 1）。

论文把 `N` 个 workload 的调度成本写为 `O(N)`：每项 dequeue 一次，全部 merge 的数量也是线性，split 每次最多产生线程数 `T` 个子项。但它同时把每轮对 `T` 个完成时间排序视为 `O(1)`；这个说法只在移动设备线程数被当作很小常数时成立，一般渐近分析应包含 `T` 的排序成本（§3.3）。

### 按需 kernel 切换器

一个 cluster 的 queue 耗尽时，scheduler 会从另一个 cluster 迁移 workload。直接保留原 kernel 会破坏 core–kernel affinity。SANI 因而预先建立 direct-mapped index table，把统一 block 映射到两种 native layout；迁移发生时查表，替换 workload indices 与 kernel pointer，让目标核用自己的最佳 kernel 计算**同一片 output region**（§3.4、图 9）。

切换器还有两个节流机制。小于阈值的 workload 不转换，因为转换成本可能高于收益；对 Merge 后的大范围 workload，则利用 height-first 顺序一次取得连续目标 indices，而不是逐个查表。这里转换的是工作描述和索引，不是复制整个 tensor；big/LITTLE clusters 共享地址空间且 cache coherent（§2.1、§3.4）。

### 实现

prototype 在 Arm Compute Library（Arm-CL）v52.3 上增加约 11.6K LoC，用自定义 scheduler 覆盖 `schedule_common()`，不要求用户改模型代码。它为两个 cluster 维护独立 queue，用 `pthread` 绑定线程；对可双发的 operator 准备两种 kernel，并保存 per operator-shape 的 index map。重复 layer shape 可以复用 map，所以额外内存取决于不同 shape 的数量，而不是简单随网络深度线性增长（§4、§5.4）。

## 设计取舍

- **统一 block 换跨 kernel 可调度性**：scheduler 不必理解每种 tile layout；LCM 过大时可能产生较粗 block，减少小 tensor 的并行度。
- **双 kernel 换亲和性**：两类核都运行更合适的实现；model load 要多做 allocation、weight transpose 和 map construction。
- **分 cluster queue 换 locality 与低争用**：正常路径更少抢同一 queue；一侧先耗尽时必须 work migration 和 kernel switching。
- **在线 Merge/Split 换干扰鲁棒性**：不依赖固定速度比例；round barrier、排序和反馈本身带来控制成本，也可能追赶不上快速波动。
- **阈值式 switching 换实际收益**：大任务保留 affinity，小任务避免转换开销；固定 threshold 不一定适合所有 operator、频率和干扰状态。
- **all-core latency 换更广能耗选择**：混合 big/LITTLE 可兼顾速度和能耗；如果 workload 完全是后台任务，论文承认 LITTLE-only 仍可能最省电（§5.2）。
- **CPU 通用性换 accelerator 性能**：SANI 改善 CPU 主路径和 fallback；大规模 mobile [[LLM|LLM]] 仍更适合 NPU，不能把这里的结论外推成 CPU 优于 NPU（§5.5）。

## 实验与结果

- **平台、workload 与 baseline**：实验覆盖 Google Pixel 9（Tensor G4，1+3+4 cores）、OPPO Find X3 Pro（Snapdragon 888）、Redmi K60（Snapdragon 8+ Gen 1）、OnePlus Ace 5 Ultra（Dimensity 9400+）和 Odroid XU4（Exynos 5422，4+4 cores）。模型为 MobileNetV2、ResNet-50、SqueezeNet、ShuffleNet、Inception-V3 和 GPT-2，使用 FP32/NEON；GPT-2 经 ArmNN 接入，并用固定随机 20-token prompts。Native 是 Arm-CL 默认调度；AsyMo 采用 latency-first mode，MNN 只移植其调度策略。三者都放在同一 Arm-CL 上，减少 framework implementation 差异，但结果不代表原版 MNN 或其他 backend 的绝对性能（§5.1、表 2）。
- **端到端 latency**：相对 Native，SANI 在 Pixel 9、Find X3 Pro、Redmi K60、OnePlus Ace 5 Ultra、Odroid XU4 上平均降低 17.6%、23.7%、19.9%、21.4%、19.0%；相对 AsyMo 分别降低 9.8%、14.4%、13.7%、15.7%、15.5%，相对 MNN 为 12.0%、15.0%、15.0%、16.7%、16.6%。按模型汇总，相对 Native 的改善为 MobileNetV2 15.7%、SqueezeNet 17.7%、ShuffleNet 21.0%、ResNet-50 19.3%、Inception-V3 29.5%、GPT-2 16.1%（§5.2、图 10）。这些是各设备/模型的平均 latency reduction，不是所有单点都达到 29.5%。
- **扩核与动态干扰**：测试设备的 single-thread asymmetry ratio 为 2.6:1–3.4:1，差异越大，SANI 相对静态 baseline 的空间通常越大。Pixel 9 上 ShuffleNet 用 4 big + 1 LITTLE 时，相对 Native/AsyMo latency 降低 19.3%/15.3%；Find X3 Pro 的 ResNet-50 用全部核心时相对 Native 降低 19.4%（图 13）。Pixel 9 上给 MobileNetV2 注入 4-thread 50% stress、8-thread 100% stress 和 YouTube 后，SANI 的 **wait latency** 比 baseline 低 20%–40%，execution latency 低 7%–10%（§5.2、图 14）；20%–40% 不是端到端总 latency 降幅。
- **能耗边界**：能耗只在改装、接入 Monsoon Power Monitor 的 Find X3 Pro 上测量。用全部核心时，ResNet-50/Inception-V3 相对 Native、AsyMo、MNN 分别省 34.1%–35.3%、32.5%–39.0%、37.1%–37.3%；轻量模型的改善为 5.5%–30.5%（§5.2、图 15）。这是单设备、单电源测量设置的 energy per inference，不能直接外推到其余四个 SoC 或持续温控场景。
- **消融实验**：在 4 big 对称配置上，issuer/block unification 对 SqueezeNet/ShuffleNet 分别贡献 4.0%/6.7%，scheduler 再贡献 5.2%/8.6%，switcher 只有 0–0.2%，符合没有跨 cluster kernel conversion 的预期。在 4 big + 4 LITTLE 配置上，三阶段依次贡献 9.5%/9.6%、额外 10.5%/13.5%、额外 7.1%/8.0%（§5.3、图 16）。这是逐步开启组件后的增量改善，不能把三个百分比直接当成互相独立的效果。
- **控制与内存开销**：表 3 中一次性 asynchronous preparation 为 MobileNetV2/SqueezeNet/ShuffleNet 的 3.8/3.2/11 ms；在线 Merge/Split 为 2.2/1.1/2.2 ms，kernel transform 为 0.08/0.25/0.18 ms，所以在线两项合计都少于 3 ms，但 cold model load 另有最高 11 ms。额外 peak memory 少于 2 MB，而被测模型执行通常用 60–100 MB（§5.4）。论文只给三种模型的 overhead，并未报告 p95/p99 或每个 operator 的尾延迟。

## 论断—证据表

| 论断 | 机制与证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 加入 LITTLE cores 不必造成 performance collapse | cluster-specific kernel、Merge/Split 与 migration switching；五种 SoC 相对 Native 平均 latency 降低 17.6%–23.7%（图 10） | 六个模型、FP32 CPU；没有长时间 thermal test | 强（被测范围内） |
| kernel affinity 与 workload balance 都不可少 | 4B+4L 消融中 issuer、scheduler、switcher 都有 7.1%–13.5% 的额外贡献（图 16） | 只对 SqueezeNet/ShuffleNet 做完整消融 | 中到强 |
| scheduler 能适应运行时干扰 | completion feedback 动态改粒度；stress/YouTube 下 wait latency 低 20%–40%（图 14） | 单设备、单模型、预设四种 load；不是 total latency 降幅 | 中 |
| mixed big/LITTLE 可降低推理能耗 | Find X3 Pro 上重模型相对 baseline 最多省 39%（图 15） | 只测一台设备；未给温度、持续运行与 battery-level 结果 | 中 |
| SANI 本身在线成本较小 | Merge/Split + transform 少于 3 ms，额外 peak memory 少于 2 MB（表 3、§5.4） | 只列三种模型；另有一次性 preparation 最高 11 ms | 中到强 |

## 批判性分析

### 论证链条

论文先用“加入核心反而变慢”建立反例，再把根因分成 workload-granularity mismatch 和 core–kernel mismatch，最后分别用 adaptive scheduler、affinity issuer/switcher回应，问题与机制对应清楚。消融也显示：对称核主要受 block unification 和调度帮助，非对称核才明显受双 kernel 与 switcher 帮助。最容易被误读的外推有两处：动态干扰下 20%–40% 是 wait latency，不是 total latency；39% energy saving 只来自 Find X3 Pro，并非五种 SoC 的统一结论。

### 假设压力测试

第一个压力点是反馈稳定性。若 OS 抢占、DVFS 和 thermal throttling 在相邻 round 间剧烈改变，奖励上一轮快线程可能使下一轮负载更不均。第二个是统一 block：两个 kernel tile shape 的 LCM 若很大，或 output dimension 很小，可用 block 数会下降；Inception-V3 的 awkward dimension 恰好从多维 partition 获益，但论文未给系统性的最坏 shape 分析。第三个是 cluster 抽象：Pixel 9 把 Cortex-X4 与 A720 都归为“big”，cluster 内部也可能不对称；只为 big/LITTLE 各选一个 kernel 会忽略这种层次。

### 实验可信度

五个 SoC、六个模型、三个统一实现的 baseline，加上扩核、干扰、energy、消融和 overhead，覆盖面好。作者把 AsyMo/MNN scheduling port 到 Arm-CL，能更公平地隔离 scheduler 差异，但也意味着比较对象不是原 framework 的完整最佳实现。实验没有报告重复次数、误差条、显著性、p95/p99、长时间温度与默认 DVFS 轨迹；20-token GPT-2 case 也不足以代表现代 mobile LLM。NPU/GPU 的兼容性结果依赖特定设备、driver 和 MNN 版本，应理解为 CPU fallback 的案例，而不是 accelerator 的普遍能力上限。

### 系统性缺陷

SANI 跨越 kernel selection、task partition 和 runtime migration 三层，约 11.6K LoC 且需要候选 kernel、离线 profiling 和每种 cluster 的回归权重。论文声称可跨 SoC 扩展，却没有量化新 ISA/SoC 的 porting、profiling 和 correctness-validation 成本。两套 weight layout 与 index map 还会增加 cold start，online 小于 3 ms 不能掩盖一次性 11 ms preparation。scheduler 以 round/barrier为中心，不能消除 operator 自身的串行段；多模型并发时，不同 inference request 对 cache、memory bandwidth 和 queue 的竞争也没有建模。最后，它只调 CPU 内部资源，真实移动 runtime 若要在 CPU/GPU/NPU 之间选择，仍需要更高一层的 admission、placement 和 fallback policy。

## 局限与后续工作

- 在数分钟到数小时的持续推理中同时记录 temperature、frequency、power、p50/p95/p99，检验 feedback 能否跟上 DVFS 与 thermal throttling。
- 系统扫描 kernel tile shape、output dimension 和 LCM，找出 block unification 失去并行度或 index map 过大的边界。
- 报告新 SoC 的候选 kernel 数、profiling 样本、模型误差、tuning 时间与代码改动，并尝试在线或自动校准 cost weights。
- 对 tri-cluster 和 cluster 内异构设计选择每个 microarchitecture 的 kernel，而不是只分 big/LITTLE 两类。
- 评测多个 inference request 与前台 app 共存时的 admission、cache/memory contention、fairness 和 tail latency。
- 把 CPU scheduler 与 GPU/NPU capability detection、fallback 和跨 backend placement 联合起来，报告完整 app latency 与 energy。
- 对较新的 transformer/LLM 做不同 prompt/prefill/decode length 的 CPU fallback 实验；按 latency/token、energy/token 和 memory 分开报告。

## 相关

- **相关概念**：[[Mobile-Inference]]、[[big.LITTLE]]、[[Arm-Compute-Library]]、[[Heterogeneous-Scheduling]]
- **同会议**：[[OSDI-2026]]
