---
type: paper
name: Krypton
full_title: "Efficient Performance-Aware GPU Sharing with Compatibility and Isolation through Kernel Space Interception"
authors: [Shulai Zhang, Ao Xu, Quan Chen, Han Zhao, Weihao Cui, Zhen Wang, Yan Li, Limin Xiao, Minyi Guo]
venue: ATC
year: 2025
tags: [gpu-sharing, virtualization, kernel-space, mig, scheduling, performance-isolation]
source_pdf: "[[atc2025-zhang-shulai.pdf]]"
source_md: "[[atc2025-zhang-shulai]]"
---

# Efficient Performance-Aware GPU Sharing with Compatibility and Isolation through Kernel Space Interception (ATC 2025)

> **一句话总结**：KRYPTON 的关键观察是所有 GPU runtime 最终都经 UMD 写入 command buffer、再经 ioctl 交给 KMD，因此在 Linux 内核拦截 command buffer 与显存分配即可跨 CUDA/Vulkan 兼容并做强隔离；配合 MIG 空间切分、NVML/DCGM 反馈式 CPU token 调度与两阶段 spatio-temporal bin-packing，在 A100/RTX4090 上比 Temporal / Best-fit-MIG / GPUlet-MIG 少需 GPU 32.1% / 23.1% / 20.5%，性能目标相对误差均值 3.3%。

## 问题与动机

云与数据中心里大量 AI inference、科学计算、视频渲染等 workload 只需 fractional GPU 即可达标，但多租户共享同一物理 GPU 时必须同时满足 **compatibility**（CUDA / Vulkan / OpenGL 等多 runtime、多版本）、**isolation**（fault + performance）、**utilization**（少碎片、少空卡）。现有方案在这三角上普遍缺腿：

- **API-remoting**（[[TGS]]、GaiaGPU、Orion 等）在 user space 拦截显式 API，维护成本随 CUDA 70+ 版本与大量动态库爆炸（TGS 仅支持 CUDA 11.2）；更致命的是无法捕获 **隐式 GPU 操作**——adversary 起 48 个进程即可让 7/8 个 victim OOM。
- **[[MPS]]** 把多进程 kernel funnel 进同一 GPU context，cross-border 显存访问会让全部 8 个 victim crash；性能隔离也弱（ResNet50 50 rps 目标共置时掉到 37.5 rps）。
- **[[MIG]]** 硬件隔离强，但分区粒度固定、灵活性差；且 graphics API、P2P 等能力受限。ResNet50 达标时 MIG 实例时间片利用率仅 62%，造成 spatial fragment。
- **纯 time-sharing**（API-remoting / cGPU 类）SM 利用率仅 44%，temporal fragment 严重。

作者 claim 的边界是：**在 NVIDIA datacenter GPU 上**，以 throughput / latency QoS 为性能目标，通过 kernel-space 拦截 + spatio-temporal orchestration，在保持兼容与隔离的前提下减少集群所需 GPU 数。论文动机实验（ResNet50 50 rps、Figure 5–6）表明：固定 time quota 或固定 MIG 实例都无法同时守住性能目标与高利用率，因此需要把 spatial（MIG）与 temporal（time slice）两个维度一起编排。

## 关键观察 / 隐含假设

- **观察 1：所有 runtime 的 GPU 请求最终汇聚为 command buffer + ioctl，内核层拦截可天然跨 runtime 且精确管控显存。**
  - **证据**：NVIDIA 开源 KMD 工作流分析（Figure 4）：runtime → UMD 写 command buffer → ioctl 通知 KMD → GPU 执行；每个 GPU context 有独立地址空间。KRYPTON 通过 ioctl 追踪 command buffer 分配地址，并用 `do_mprotect_pkey` 锁页 + segfault handler 做 temporal gate；显存 ioctl 可记录含 context 创建时 ~400MB 隐式分配在内的全部 device memory。
  - **依赖假设**：目标部署为 Linux + NVIDIA 官方或开源 KMD；command buffer 地址在 context 生命周期内稳定；拦截点位于 UMD→KMD 边界而非 MMIO 层。
  - **可能失效场景**：闭源驱动内部语义变更导致 ioctl 参数映射失效；AMD/Intel GPU 需重新逆向 KMD（论文称机制可推广到 command-buffer 类 PCIe 设备，但未实现）；未来 runtime 绕过标准 ioctl 路径时兼容性断裂。
- **观察 2：在强隔离前提下，workload throughput 对 time slice quota 近似线性，从而可把「满足性能目标」从固定配额问题变成可搜索的配置空间。**
  - **证据**：离线 profiler 在 6 种 MIG 配置（整卡 + 5 种 MIG profile）上测 $Thr(s_i, 100\%, m_i)$，再估算 $Thr(s,t,m) \approx Thr(s,100\%,m) \times t$；Transformer-XL 训练在 3g.20gb 上 >48% time slice 可达 2 rps 目标（Figure 8）。分布式双卡训练在 RTX4090 上 time slice 比例与吞吐相对误差仅 1.8%。
  - **依赖假设**：共置 workload 间无显著 memory bandwidth / L2 干扰；kernel 时长与 SM 占用相对稳定（训练、离线渲染、稳态 inference）；MIG 提供的空间隔离足够「强」使 temporal 缩放成立。
  - **可能失效场景**：memory-bound 或 bursty LLM serving 使 util/quota 线性关系破裂；多租户争抢 HBM 带宽时 offline profile 失真；极短 kernel 下 100ms token 粒度引入调度 overhead。
- **观察 3：纯 spatial（MIG）或纯 temporal（API-remoting）都会在另一维度留下碎片；spatio-temporal 联合编排可让 normalized throughput 更接近 1。**
  - **证据**：10 个 test case（20–40 workloads）上，KRYPTON 的 normalized throughput 最接近 1，而 Best-fit-MIG 系统性偏高（过度分配整 MIG 实例）；Temporal 在部分 case 未达标。Inf-bs8-R2 上 20 workloads 压到 ~3.4 张 A100（Figure 14）。
  - **依赖假设**：集群规模足够大、workload 数量多，bin-packing 有填充空间；性能目标以 solo throughput 的分数形式给出（R1/R2 列表）；离线 orchestrator 的 O(MP) 启发式足够接近最优。
  - **可能失效场景**：workload 数极少或全是大模型独占 MIG 上限时，碎片收益消失；动态到达/离开需要重跑 orchestrator，论文未做在线重规划实验。
- **假设 1：CPU token + GPU utilization 反馈可近似控制真实 GPU time slice，优于固定 token 或 per-API sleep。**
  - **证据强度**：强（在评测集上）。双 ResNet50 共置 adaptive control 相对误差 ≤0.9%，无 feedback 5.3%，GaiaGPU 24.2% 吞吐损失；默认 token 100ms。
  - **可能失效场景**：NVML 在 MIG 下功能受限需切换 DCGM；GPU 异步执行导致长 kernel 在首个 token 窗口「透支」——论文用 util/quota 补偿缓解，但极端长尾 kernel 仍可能扰动邻居。
- **假设 2：评测用的 CUDA inference/training + Vulkan rendering benchmark 能代表生产混部场景。**
  - **证据强度**：中。覆盖 4 模型 × 2 batch × 2 模式 + 3 Vulkan demo；但 LLM serving 仅作为 profiler 讨论，未进入主实验矩阵；论文自称已部署千卡级生产集群一年，细节未公开。

## 核心方法

KRYPTON 由 **offline profiler**、**kernel-space scheduler**（interception + feedback controller）、**spatio-temporal orchestrator** 组成（Figure 7）。每个 tenant 获得一个 **IGPU** 抽象：$IGPU(s,t,m)$ = MIG 空间份额 $s$ + time slice 配额 $t$ + device memory $m$。

**Kernel-space command buffer interception**（回应观察 1）：每个物理 GPU/MIG 实例对应 `/dev/igpu` 模拟设备，容器经 `LD_PRELOAD` 库转发到内核模块。模块在 context 创建 ioctl 时记录 command buffer 物理页；非活跃进程将 buffer 页标为 read-only，写操作触发 SIGSEGV → 用户态 handler 阻塞查询内核是否获 token。仅 gate GPU 相关页，不暂停整个进程（对比 whole-process pause）。显存分配 ioctl 经 central allocator 记账，超额返回错误，从而挡住隐式 context memory。

**Feedback-controlled CPU token scheduling**（回应观察 2 的 runtime 部分）：因无法改 vendor GPU context switch，KRYPTON 在 host 侧发 **CPU token**——持 token 方可写 command buffer。调度器每 100ms 选 $argmin(util/quota)$ 的 app 激活，其余 pause；用 NVML `nvmlGetProcessUtilization`（非 MIG）或 DCGM（MIG 模式）累积 GPU util，对「独占时间片但低 util」的 app 视作满占，避免饿死。轻载 app 还可弹性借用同 MIG 实例上空闲 time slice（Figure 18）。

**Spatio-temporal orchestrator**（回应观察 3）：离线两阶段 bin-packing，复杂度 O(MP)：(1) 每 workload 选满足目标的最小 spatial MIG；(2) 同 spatial 配置做 temporal fuse；(3) 从大 temporal fragment 的 IGPU 向小 spatial IGPU 迁移 workload；(4) MIG instance bin-pack 减 GPU 数。多卡 workload（如 NCCL 分布式训练）保持配置一致，内核侧对齐 token 使相关 GPU 同时 active。

实现约 3k LOC C（内核模块）+ 1k LOC Python（orchestrator），不改应用代码、不改 NVIDIA 驱动逻辑；可用开源或官方驱动。深度 ioctl 逆向与 signal 路径见 [[atc2025-zhang-shulai]]。

## 设计取舍

- **用内核 LKM + 逆向 ioctl 换 runtime 无关兼容**：避免 API-remoting 对每版本 CUDA/Vulkan 的适配；代价是绑定 NVIDIA KMD 实现细节、驱动升级需维护拦截逻辑，且 `do_mprotect_pkey` 经 kallsyms 非正式导出，可移植性与上游内核政策风险高。
- **用 segfault-based gate 换细粒度 GPU preemption**：不修改 hardware scheduler，尊重 vendor context switch；代价是每次 kernel launch 可能多一次 fault/handler 往返，且 token 粒度（默认 100ms）与 QoS 存在张力（Figure 17：小 batch 怕短 token overhead，大 batch 怕长 token 等待）。
- **用 MIG 固定 spatial + 内核 temporal 换隔离与灵活性折中**：MIG 保证 compute/memory 硬隔离，time slice 在实例内弹性编排；代价是 **无法在线重配 MIG**（§7），负载下降时 spatial 资源不能回收，dynamic LLM serving 会受限。
- **用离线 profile + 启发式 bin-packing 换可解性**：搜索空间 $O(N^M P^M)$ 不可穷举；O(MP) 启发式可扩展但无最优性保证。收益是千卡级规划可批处理；边界是 workload 组合变化需重 profile + 重规划。
- **边界条件**：workload 多、batch 小、目标吞吐为 solo 分数时最赚（论文主结果）；单一大模型或强依赖 graphics + CUDA 混部且需 MIG 外 graphics 特性时变脆；latency QoS 依赖 Poisson 到达与 p99 目标，token 长度需 per-workload 调参。

## 实验与结果

- **平台**：Intel Xeon Silver 4216、NVIDIA A100 40GB × N + RTX4090 ×2、Linux 5.15、CUDA 12.1、Vulkan 1.3、Docker + NVIDIA Container Toolkit（Table 1）。
- **Workload**：ResNet50 / MobileNetV2 / BERT-Large / Transformer-XL 的 inference+training（bs=8/32）+ 3 个 Vulkan 渲染 benchmark；吞吐目标 R1/R2 为 solo 的 {2/3…1/12} 等分数（Table 2）。
- **主结果（10 test cases，对比 Temporal、Best-fit-MIG、GPUlet-MIG）**：所需 GPU 数相对减少 **32.1% / 23.1% / 20.5%**；KRYPTON normalized throughput 最接近 1，Temporal 部分未达标，Best-fit-MIG 系统性过高。小 batch、多 workload case 收益更大。
- **隔离**：对 TGS（API-remoting）/ MPS adversary（48 进程或 cross-border 访问），KRYPTON 下 victim 不被 OOM 或 fatal error 击穿；MIG 亦安全，前两者失败（Figure 3）。
- **Vulkan**：2–3 个 Vulkan app 共置，及 Vulkan+CUDA 混部，吞吐相对目标误差 **<3.4%**（仅 time-sharing 层，因 baseline 不支持 Vulkan）。
- **Feedback ablation**：2/4/8 个 ResNet50-train 共置整卡 A100：pass-through 误差 53.6%，GaiaGPU -24.2%，无 adaptive 21.6%，KRYPTON **3.0%**；GPU util 曲线更贴近 25%/75% 目标（Figure 16）。
- **Latency QoS**：Transformer-XL inference，Poisson 到达，p99 目标；全配置平均 QoS violation **1.23%**；token 长度与 batch size 存在 trade-off（Figure 17）。
- **Elastic sharing**：固定 token 下 Transformer-XL-Inf 共置相对误差 1.3%；新任务到达时短暂 util burst 后自适应收敛（Figure 18）。
- **开销**：内核模块 ~4.8MB 主机内存；GPU monitor 占 1 CPU 线程；除 token 切换外不额外破坏 vendor context switch 逻辑。

## Critical Analysis

### 论证链条

主链条清晰：**user-space 拦截不可维护且漏隐式操作** → **所有请求经 command buffer** → **内核拦截 + 独立 context 显存账本** → **fault+token 做 temporal 隔离** → **MIG 做 spatial 隔离** → **profile 线性缩放 + feedback 守住 runtime 目标** → **spatio-temporal bin-packing 压 GPU 数**。Figure 3（隔离）、Figure 5–6（动机）、Figure 13（主结果）、Figure 16（feedback）逐步闭合「兼容 + 隔离 + 性能 + 利用率」四元 claim。

薄弱跳步在于：**生产可部署性**主要靠 Discussion 一段文字（千 GPU、一年），主文实验仍是实验室 benchmark + 容器；**与 TGS/Orion/GSlice 等未隔离基线的 GPU 数对比**未出现在 Figure 13，主对比对象是自建的 Temporal / MIG 变体，因此「比 SOTA 少 32.1%」中的 SOTA 实际是论文定义的 isolation-preserving baseline，而非全文 Related Work 里所有 GPU sharing 系统。

### 假设压力测试

**线性 throughput 缩放**是最需压力测试的假设。论文在强 MIG 隔离下验证 ResNet50、Transformer-XL 等 CNN/Transformer 训练推理；但对 **memory-bandwidth 敏感共置**（两训练 job 同卡）、**LLM 动态 batch**、**CUDA Graph 持久 kernel**，$Thr \propto t$ 是否成立缺乏 ablation。Elastic sharing（Algorithm 1 选最低 util/quota）在轻载时会借出空闲 slice，可能暂时抬高某 tenant 吞吐，与严格 performance isolation 的语义需在生产 SLO 下再验证。

**NVIDIA-only 绑定**：ioctl 逆向、NVML/DCGM、MIG profile 集均围绕 A100/RTX4090。新卡（H100）、新驱动、MIG 分区表变化、或云厂商虚拟化层插入后，拦截点是否稳定是工程风险；论文未提供 driver version matrix。

**Latency QoS**：1.23% violation 听起来低，但实验基于 Poisson + 固定 p99 目标，且 token 100ms 对 <50ms SLO 本身就不友好（论文承认需减 token 但增 switching overhead）。Interactive serving、multi-tenant 尾延迟竞争未系统测量 p99/p999。

### 实验可信度

**强项**：(1) baseline 选择对齐 claim——对比对象均「保证隔离」，避免用弱隔离的 MPS 刷利用率；(2) 同时报 GPU 数、normalized throughput、relative error，防止只优化一个 metric；(3) 威胁模型实验（48 进程 adversary）直接支撑 isolation claim，比纯 microbenchmark 有说服力；(4) Vulkan 段证明 compatibility 不只停留在 CUDA。

**不足**：(1) 集群规模实验是「所需 GPU 数」离线推算，非真实千卡 trace replay；(2) GPUlet-MIG 是作者改造版（原 GPUlet 用 MPS），与原版可比性有限；(3) 缺少端到端 **cost**（profile 多久、orchestrator 多久、故障恢复）、**tail latency**、**fairness/starvation**；(4) 与 GaiaGPU 只在 feedback ablation 出现，未参与 GPU 数主对比。

### 系统性缺陷

- **运维与安全**：LKM 劫持 GPU 设备节点、修改页保护、依赖 kallsyms——论文称与其他 LKM 等价且生产无事故，但 **未讨论** CVE 面、与 SELinux/AppArmor 交互、内核升级回归测试、多租户审计日志。
- **可观测性**：有 NVML/DCGM util 反馈，但 **未讨论** 租户级 metrics 导出、调度决策可解释性、OOM/segfault storm 排障。
- **故障恢复**：进程 crash 时 command buffer / token 状态如何清理、是否会导致 GPU 挂死或 neighbor 饿死，**论文未讨论**。
- **动态性**：明确承认 **不能在线调整 MIG**；负载骤降时 spatial 碎片无法回收；live migration 列为 future work——对 LLM serving 弹性伸缩是实质性限制。
- **资源隔离维度**：MIG 隔离 SM/内存，但 **同机 PCIe、CPU、NIC、电源** 未评估；feedback 调度在实例内弹性借 slice 时，严格 quota 租户可能被「善意」抢占。

## 局限与 Future Work

- **局限 1**：不支持 MIG 空间资源的实时重配置与弹性回收；负载波动大的 dynamic serving 只能调 time slice，不能缩小 spatial footprint。
- **局限 2**：强依赖 NVIDIA KMD ioctl 语义与 MIG 能力矩阵；graphics API、P2P、多 vendor 场景未验证。
- **局限 3**：Orchestrator 与 profiler 离线运行；workload 混合变化时的在线重规划、迁移成本、SLO 违约窗口 **论文未量化**。
- **局限 4**：Token 长度固定 100ms 对亚 50ms latency SLO 不友好；per-workload 自适应 token 仅有 QoS 实验，未与 orchestrator 联合优化。
- **Future work 1**：**Live migration of GPU resources**——在保持 isolation 的前提下迁移 IGPU（MIG 实例 + memory + scheduling state），支撑负载下降时的 spatial 回收。
- **Future work 2**：在 production trace 上测量 profile 漂移（新 CUDA 版本、新 kernel fusion）对 $Thr(s,t,m)$ 线性的破坏，并设计在线 recalibration。
- **Future work 3**：把 orchestrator 与 feedback controller 闭环——共置组合变化时增量 replan，而非全量离线 bin-packing。
- **Future work 4**：系统评估 H100/MIG 新分区、[[MPS]] 共存、multi-tenant p99/p999、segfault path overhead 与 security hardening。

## 相关

- **相关概念**：[[GPU-Sharing]]、[[MIG]]、[[MPS]]、[[API-Remoting]]、[[Performance-Isolation]]、[[Bin-Packing]]
- **同类系统**：[[TGS]]、Orion、GaiaGPU、[[GSlice]]、[[GPUlet]]、Temporal（cGPU/qGPU）、Muxflow、Laius
- **同会议**：[[ATC-2025]]
- **对比**：[[GPreempt-ATC25]] 从 driver timeslice 做低延迟 preemption，面向 LC/BE 抢占而非 fractional quota serving；[[XSched-OSDI25]] 追求跨 XPU 统一调度抽象，KRYPTON 则是 NVIDIA 栈上兼容+隔离+性能目标的垂直方案