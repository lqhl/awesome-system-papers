---
type: paper
name: MIMESYS
full_title: "MIMESYS: Generating Realistic Executable Testing Environments from Resource Usage Traces"
authors: [Donghyun Kim, Zichao Hu, Joydeep Biswas, Aditya Akella, Daehyeok Kim]
venue: OSDI
year: 2026
tags: [workload-generation, resource-contention, diffusion-model, testing, performance]
source_pdf: "[[osdi26-kim-donghyun.pdf]]"
source_md: "[[osdi26-kim-donghyun]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 从资源使用轨迹生成可执行测试环境（OSDI 2026）

> **原题**：MIMESYS: Generating Realistic Executable Testing Environments from Resource Usage Traces

> **一句话总结**：MIMESYS 不试图恢复私有应用的业务逻辑，而把 CPU、内存带宽、LLC 和磁盘 I/O 轨迹反推成每核 stressor 执行计划；在同一 Haswell 平台的 benchmark 混部实验中，它让 DTW 轨迹距离相对基线最多改善 5.5 倍，受害应用的性能下降误差平均为 8.3 个百分点、下一名为 19.4 个百分点，论文摘要另把总体准确性概括为提高 2.6 倍。

## 问题与动机

应用只有在真实资源争用下测试，才能知道上线后是否会被 noisy neighbor 拖慢。硬件配置只是环境的一半；同机运行的其他工作负载会争抢 CPU、内存带宽、last-level cache（LLC）和 I/O。开发者需要这种压力既真实又可重复，才能公平比较配置、判断优化是否有效，并提前发现 SLO 风险。

真实生产应用往往不能共享：它们处理敏感数据，包含私有算法，还依赖内部基础设施。直接去生产环境测试又昂贵、难并行，而且每天的混部情况都在变化，实验无法复现。公开 benchmark 容易运行，但类型有限；stress-ng 之类工具通常只让某个 stressor 以固定最大强度持续运行，不能表达 burst、ramp 和多资源交互；application cloning 则要对每个应用做详细 profiling，主要复现均值等统计量，扩展到大量应用很贵（§1–2）。

云运营方本来就在收集资源使用轨迹。MIMESYS 因此问了一个更窄的问题：能否只根据多变量 time series，生成一个可以执行的 workload，使它在同一或相近硬件上造成类似的资源争用？它不恢复 request、数据结构或业务逻辑，只复现“环境施加给目标应用的资源压力”（§3）。

这个逆问题并不适合手调。一个 memory stressor 在八个线程上运行时，论文测到的内存带宽可以是单线程的 1,800 倍；把 stressor 和 sleep 线性混合，也可能产生相差超过 3 倍的带宽。并发 stressors 会互相影响，前一秒的 cache 和 memory-controller 状态还会改变下一秒。更麻烦的是，多种不同的 stressor 组合可以得到相似轨迹，真实应用轨迹又和随机 stressor 组合的分布不同（§3.1–3.2）。

## 关键观察 / 隐含假设

- **观察 1：复现资源争用不一定要复现应用逻辑。** 如果测试目标只是看 target app 在 noisy neighbor 下的性能，能制造相近的资源轨迹可能已经够用（§3）。
  - **依赖假设**：性能影响主要由已观测的 aggregate CPU、memory bandwidth、LLC traffic 和 disk I/O 决定。
  - **可能失效场景**：tail latency 由请求 burst、锁、cache-line sharing、branch、I/O queue depth、[[NUMA]] locality、网络或 GPU 干扰主导；相同均值轨迹也可能造成完全不同的延迟。
- **观察 2：trace→composition 是一对多且非线性的逆映射。** Diffusion model 可以从噪声逐步生成多个可行组合，比简单线性插值更自然地表示多模态分布（§4.2.1）。
  - **依赖假设**：固定的 14 个 stressors 足以覆盖目标轨迹附近的可达资源空间；模型能在训练点之间可靠插值。
- **观察 3：前一时间窗会改变下一时间窗的 stressor 效果。** 同一 composition 相比“前一窗 idle”的情况，LLC 和内存带宽变化的 P90 分别达到 135.7% 和 95.0%（§7.3）。
  - **依赖假设**：前一个 composition 是系统状态的充分代理。实际模型条件是 `a_(t-1)`，不是直接读取 cache、controller 或 scheduler 的真实状态；更长历史也没有显式输入。
- **观察 4：随机收集 stressor 组合会堆在资源空间的中间。** 极端或不对称模式很少被抽到，增加相似样本不能有效扩展覆盖；应该优先执行“稀有或预测不确定”的候选（§4.2.3、图 4）。
- **观察 5：真实轨迹没有正确 stressor 标签，但执行本身可以当反馈。** 生成 candidate、实际运行、比较结果和目标轨迹，就能用 reinforcement learning 把模型拉向真实应用分布（§4.3）。
- **假设 1：把 trace 变成 stressor executable 足以保护隐私和知识产权。** 它确实不包含原应用代码或数据，但论文没有做 membership inference、属性推断或差分隐私分析，也没有证明 trace 和生成物不会泄露租户活动模式。

## 核心方法

**1. 用每核 stressor 矩阵表示一秒 workload。** 对长度为 `T` 的轨迹，MIMESYS 切成固定大小 `W=1 s` 的窗口。第 `t` 窗的 composition `a_t` 是 `M stressors × K CPU threads` 的矩阵；元素在 0–1 之间，表示该线程在这一秒内运行某个 stressor 的时间比例，每个线程分配的总时长不超过一秒。跨线程同时执行的数量决定总体强度（§4.1）。

**2. 用 diffusion model 生成 composition。** 模型是 8.9M 参数的 U-Net。目标资源向量 `o_t` 经过四层 MLP 编成 256 维 embedding；前一个 composition `a_(t-1)` 经另一组 MLP 编码，两者拼接后注入 U-Net 每一层。模型学习条件分布 `p(a_t | o_t, a_(t-1))`，用 25 步 denoising 从 Gaussian noise 得到一个 composition（§4.2.2、§6、图 3）。

**3. 用“前一个 composition”近似系统状态。** 生成按时间顺序进行：得到 `a_t` 后，它成为下一窗的条件。这样模型能学会在上一窗已经造成高内存负载时降低下一窗 memory stressor，而不是把每个时间点独立拟合。论文称之为状态感知条件（state-aware conditioning），但这里的 state 是上一动作的代理，不是执行后遥测到的完整机器状态（§4.2、图 11）。

**4. 用新颖度指导训练数据收集。** 每轮先在已有 `(composition, trace)` 数据上训练 100-tree Random Forest，预测大量候选 composition 的资源使用。新颖度由两项组成：预测点离现有 trace 的距离，衡量“稀有”；树之间的预测方差，衡量“不确定”。每轮只实际 profile 分数最高的 128 个候选，共 100 轮，得到约 12K 个多样样本。完整收集在 8 台机器上约 8 小时，每个样本会重复测量（§4.2.3、§6）。

**5. 用执行驱动对齐跨过 synthetic-to-real gap。** 预训练数据有 composition 标签，但真实应用只有目标 trace。MIMESYS 把 diffusion model 当 policy，输入真实 trace 生成 composition，和前一个 composition 一起在真实硬件上执行，再用生成 trace 与目标 trace 的加权 L1 距离取负数作为 reward。系统采用 denoising diffusion policy optimization（DDPO），把每一步 denoising 当 action，用 policy gradient 更新模型；实验 reward 对四类资源给相同权重（§4.3、§6）。

**6. 把矩阵编译为独立 C++ 程序。** 14 个 stressors 从约 600 个 Fleetbench 和 stress-ng 候选中选出，覆盖整数/浮点计算、不同 working-set 的顺序/随机内存访问、LLC、顺序/随机磁盘读写和 sleep。generator 把每行绑定到物理 core，在每个一秒窗口内按比例执行；窗口内顺序随机打乱，避免固定顺序形成额外周期。最终输出不依赖 Python 模型运行时，是可单独执行的 C++ 程序（§5–6、附录 A）。

实现约有 1.8K 行 Python 训练/推理代码和 800 行 C++ generator。预训练在一块 A100 上约 2 小时，execution-driven alignment 再用约 2 小时并需 8 台 profiling 机器；从头算约 4 小时，不包括前述 8 小时训练数据收集。A100、batch size 128 时推理约 190 个窗口/秒（§6）。

## 设计取舍

- **环境级 fidelity 换应用级 fidelity。** 程序能复现资源压力，但不产生相同请求、数据访问语义、锁争用或业务输出；它适合性能环境，不是原应用替身。
- **固定 stressor library 换简单可执行表示。** primitives 容易组合和编译，却限制可达资源空间；增加或替换 stressor 要重新 profile 并重训整个模型。
- **一秒窗口换噪声与细节的平衡。** 更短窗口测量方差大，更长窗口会抹掉动态且增加收集时间；论文选 1 秒，但没有证明它适合微秒级 RPC 或分钟级 batch phase。
- **上一 composition 换低成本状态表示。** 它能修正一部分 cache/memory history，却不能观察实际调度、温度、page placement 或更长历史累积。
- **执行反馈换机器成本。** Alignment 不需要 label，但每次 reward 都要实际跑 workload；训练时间取决于可用 profiling machines，不能像纯离线 loss 一样廉价扩展。
- **平台内准确度换可移植性。** stressor→resource transfer function 与 CPU、cache、memory 和 storage 强绑定，输出必须带硬件 metadata；跨平台直接执行并不可靠。

## 实验设置

- 所有主要系统实验运行在 CloudLab c220g2：20-core Intel Haswell、Ubuntu 22.04、Linux 5.15。输入共有 23 维：per-core CPU utilization，加上 memory bandwidth、LLC traffic 和 disk I/O；采样粒度为 1,000 ms（§6–7）。
- 真实目标不是机密生产应用，而是公开 benchmark 的混合：Web Serving、Spark big data、Redis/FASTER KV、ResNet50/StableDiffusion inference、TPC-C/TPC-H database 和 GAP graph。比例按 Azure 已公开 workload distribution 取样，最多混部 6 个 workload，每个放在独立 KVM VM 中；每个 mix 跑 5 分钟，总计 10 小时 trace（§7、表 1）。
- 为明显制造 contention，§7.1 的 colocated workloads 使用超过 50% 的可用 CPU cores。六个受害应用是 TPC-C on Silo、Spark Sort、Redis-YCSB-A、FASTER-YCSB-A、FIO 和 DaCapo-Spring。
- 三类 baseline 是：从训练集找最近 trace 的 search-based 方法；对最近 100 个样本线性插值 composition；以及分别面向 cache/memory 或 I/O、再用 sleep 校准 CPU 的单 stressor。没有与 application cloning、普通神经回归或其他 conditional generative model 做相同 profiling 预算的比较。
- 轨迹指标是归一化 Dynamic Time Warping（DTW）距离，0 表示相同；应用指标是“与真实混部相比，吞吐下降或延迟上升相差多少个百分点”。

## 实验与结果

- **受害应用的总体性能影响**：六个应用上，MIMESYS 造成的 performance degradation 与真实 workload 平均相差 8.3 个百分点，next-best interpolation 为 19.4 个百分点。直接相除约为 2.34 倍，不是 2.6 倍；摘要和结论另称“准确 2.6 倍”，正文没有解释这两个汇总口径为何不同。DaCapo 使用 P90 latency 时仍相差 15 个百分点，说明平均优势不等于所有应用都接近（§7.1、图 6）。
- **时间变化案例**：TPC-C 与 Spark SVD、Renaissance web server 混部时，真实吞吐在 30 秒后最多下降 37%。MIMESYS 的平均吞吐偏差为 4%，资源轨迹 DTW 为 8%；interpolation 的吞吐偏差为 9%，简单 stressor 为 30%。图 8 同时对齐了内存带宽峰值和吞吐下降，支持“资源轨迹相近会带来相近干扰”这一局部因果链（§7.1、图 8）。
- **轨迹相似度**：按 CPU core allocation 分为 low 0%–30%、mid 30%–60%、high 60% 以上后，MIMESYS 在 CPU、LLC、memory bandwidth 和 I/O 上都得到最低或接近最低的 DTW，平均距离相对基线最多改善 5.5 倍，而且分配的 CPU cores 越多，heuristic baseline 与它的差距越明显。这个 5.5 倍是“最多”的 improvement factor，不是每个 metric、每个 load level 都有相同收益（§7.2、图 9）。
- **三个机制的消融**：随机收集替代 novelty guidance 后，平均 DTW error 高 2.5 倍；去掉上一 composition 条件后平均只高 7%，但在前态把指标改变超过 2 倍的 tail cases 中差距更大；去掉 execution-driven alignment 后平均 DTW 高 59%，尤其伤 memory bandwidth 和 I/O。LLC 的 alignment 收益较弱，作者认为等权 L1 reward 没有充分表达所有 trace 维度（§7.3、图 10–11）。
- **缺失 trace 的敏感性**：随机丢掉 20% 的输入段时，DTW 距离变差 1.4 倍；丢 80% 时变差 3.7 倍。逐类删除 metric 时，对应资源误差上升，但其他 metrics 的误差恶化少于 1.7 倍。模型能用跨资源相关性补一部分缺失信息，却不能把“80% 丢失仍可运行”理解成高 fidelity（§7.4、图 12）。
- **已暴露的语义和硬件边界**：Redis 的 throughput degradation 只差 5.3 个百分点时，P99 latency degradation 的倍率仍可相差最多 9 倍，说明 aggregate stressors 很难复现 request-level tail。把 Haswell 上生成的 workload 直接放到 Skylake，prediction error 比“在 Skylake 训练并在 Skylake 使用”的模型高 190%；同一 executable 不能安全地跨 CPU 代际复用（§7.1、§9）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 多资源 trace 可以反推成有较高 fidelity 的 executable | 图 9：DTW improvement 最多 5.5 倍 | Haswell、23 个 metrics、14 个 stressors、公开 benchmark mixes | 强（平台内） |
| 生成 workload 能较好复现目标应用的平均 contention | 图 6：8.3 对 19.4 个百分点；图 8：TPC-C 偏差 4% | 六个受害 benchmark，争用负载使用超过 50% CPU cores | 强（所测 workload） |
| execution-driven alignment 缩小 synthetic-to-real gap | 图 10：移除后平均 DTW 高 59% | 目标是 benchmark application traces，reward 为等权 L1 | 强 |
| state-aware conditioning 对 history-sensitive tail case 有用 | 平均改善 7%；LLC/内存效果的 P90 前态差为 135.7%/95.0% | 只输入上一 composition，不是完整观测 state | 中到强 |
| 生成物可在“相近硬件”直接复用 | §9：Haswell→Skylake error 高 190% | 只测一组跨代迁移，结果是否定性的 | 弱 |

## 批判性分析

### 论证链条

论文把一个原本过大的目标缩成了可执行问题：不重建应用，只重建环境压力。composition 表示提供可运行的输出；diffusion 处理一对多逆映射；上一 composition 处理短期历史；novelty collection 减少 profiling 浪费；execution feedback 再修正 synthetic-to-real gap。图 10 的消融显示，数据覆盖和 alignment 的贡献都很大，方法与证据基本对应。

需要收窄的是“state-aware”和“realistic”。模型没有直接观察上一窗执行后的 cache、memory bandwidth 或调度状态，只看到自己上次生成的 composition；若机器上还有 target app、后台 daemon 或热管理改变了真实状态，这个代理可能失准。评测的“real applications”是公开 benchmark mix，不是论文动机中不可共享的生产租户。按 Azure 分布采样增加了代表性，但不能等同于真实生产 trace 已被复现。

### 假设压力测试

相同 CPU utilization、LLC traffic 和 memory bandwidth 可以来自不同的 cache set、读写比例、共享 cache line、NUMA placement 或 branch 行为，对受害应用的影响并不相同。Redis P99 最多相差 9 倍正是反例：aggregate trace 匹配得不错，request-level tail 仍可完全不同。若使用者拿合成环境判定严格 SLO，仅看平均 8.3 个百分点误差也可能得出相反结论。

固定 14-stressor library 还可能存在不可达轨迹。Diffusion model 能在已覆盖空间内表示多解，却不能凭空创造 library 没有的 cache、network 或 accelerator interference。论文用新颖度扩展“已知 primitives 能到达”的范围，没有测 target trace 到可达集合的距离，也没有在模型无法匹配时给用户一个拒绝或置信度。

### 实验可信度

优点是同时测 resource trace 和受害应用性能，不只报告模型 loss；还包含时间序列案例、三个机制消融、缺失数据和跨硬件失败案例。workload categories 广，baseline 也覆盖最近邻、插值和常见单 stressor 用法。作者主动报告 DaCapo 和 Redis tail 的失败，边界比较清楚。

不足是只有一个主要硬件平台、总共 10 小时公开 benchmark mix，并没有 production trace、网络/GPU contention 或多代硬件训练。基线没有包括等参数的 deterministic neural inverse model、conditional VAE/flow 或 application cloning；因此实验证明 MIMESYS 胜过这些 heuristic baselines，不能单独证明 diffusion 是最佳模型。摘要的 2.6 倍又无法从正文 8.3/19.4 直接复算，发布页面应保留这个口径差异。

### 系统性缺陷

“发布 executable 而不是 trace”并不自动等于隐私安全。资源轨迹可能暴露活动周期、模型 phase 或业务事件；生成的 composition 也可能保留这些时间模式。反过来，stressor executable 本来就会大量占用 CPU、内存和 I/O，若缺少 sandbox、配额和签名，它也可以被当成 DoS 工具。论文没有给 threat model、隐私预算、artifact 审计或安全执行策略。

复现还需要严格记录 CPU 型号、cache、memory topology、kernel、governor、storage、stressor 版本和编译选项。仅标“Haswell”不够；同型号机器的 background load、thermal state 和磁盘布局也会改变 transfer function。平台升级后要重新收集约 8 小时数据并重训，长期维护成本没有纳入收益讨论。

## 局限与后续工作

- **局限 1**：输出只复现 aggregate resource pressure，不包含 application logic、request burst、同步、数据访问语义和完整 tail behavior。
- **局限 2**：模型与 stressor library 绑定硬件；Haswell→Skylake 已使误差高 190%，新增 stressor 也必须重新 profile 和训练。
- **局限 3**：主要评测使用按 Azure 分布组成的公开 benchmark mix，不是机密生产 workload，也只有一个主要测试平台。
- **局限 4**：指标只覆盖 CPU、memory bandwidth、LLC 和 disk I/O，没有 network、GPU、power、temperature、NUMA traffic 和细粒度 memory locality。
- **局限 5**：没有正式隐私、安全或可达性分析；模型即使无法用现有 stressors 匹配目标，也没有明确拒绝机制。
- **后续工作 1**：加入 NUMA traffic、IPC、branch、queue depth、network 和 accelerator metrics，并检查它们是否真正降低 Redis/DaCapo 的 P99/P90 误差，而不只降低 DTW。
- **后续工作 2**：把 CPU、cache、memory topology 和 storage descriptor 加入条件，在至少三代硬件上做 leave-one-platform-out；同时报告无需重训、少量 alignment 和完整重训三种迁移成本。
- **后续工作 3**：估计每个 target trace 到 stressor 可达集合的距离，输出置信度；超出范围时拒绝生成，而不是给出看似可执行但 fidelity 很低的程序。
- **后续工作 4**：为 trace→model→executable 建 threat model，测试 membership/attribute inference，并为发布 artifact 加资源上限、签名、sandbox 和可审计 metadata。
- **后续工作 5**：在相同 profiling 与训练预算下比较 deterministic regression、conditional generative model 和 search/optimization，分清收益来自 diffusion、数据覆盖还是 execution alignment。

## 相关

- **相关概念**：资源争用、工作负载合成、diffusion model、性能测试、[[NUMA]]
- **同类工具**：stress-ng、Fleetbench、SPEC
- **同会议**：[[OSDI-2026]]
