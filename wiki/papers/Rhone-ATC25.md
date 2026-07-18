---
type: paper
name: Rhone
full_title: Emulating Space Computing Networks with Rhone
authors: [Liying Wang, Qing Li, Yuhan Zhou, Zhaofeng Luo, Donghao Zhang, Shangguang Wang, Xuanzhe Liu, Chenren Xu]
venue: ATC
year: 2025
tags: [satellite-network, emulator, space-computing, leo, container, edge-computing]
source_pdf: "[[atc2025-wang-liying.pdf]]"
source_md: "[[atc2025-wang-liying]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Emulating Space Computing Networks with Rhone (ATC 2025)

> **一句话总结**：论文观察到现有 [[LEO-Satellite-Network]] emulator 在能耗/热/COTS 异构性上严重失真（如 [[StarryNet]] 容器推理延迟波动比真星载 Pi 小 160–330%），因而用真卫星 telemetry + hardware-in-the-loop profiling 离线建模、在线 [[Docker]] 容器 + SCA/SNA 动态对齐；单节点可扩至 700 卫星，power/computation 误差 <5%、温度误差 1.3–2.5°C。

## 问题与动机

LEO 卫星正从昂贵、单一功能的通信节点演化为 **Space Computing Network（SCN）**：星载 [[COTS-Hardware]]（Raspberry Pi、Jetson、Atlas NPU 等）承担 onboard 推理/压缩/路由，星座组网（[[Starlink]]、Planet Dove 等）提供全球覆盖与高带宽 ISL/GSL。两类应用推动研究：近实时 [[Earth-Observation]]（capture-to-insight 可从数十小时缩到分钟级）与卫星骨干全球联网（星载 5G UPF、跨洲视频会议等）。

但 SCN 应用难设计、难评估，核心障碍是**无法在真实星座上反复实验**：小卫星发射成本约 \$150K，且星座规模已达数千颗。研究者只能依赖实验平台，而平台需同时满足三类要求：

1. **Satellite-level fidelity**：能耗/热/异构 COTS 算力与真实软件栈行为一致；
2. **Constellation-level fidelity**：拓扑动态、GSL handoff、ISL 带宽、节点失效等网络行为可复现；
3. **High usability**：可扩到整星座、可跑用户未修改应用、成本低且接口友好。

作者 claim 现有三类方案均不完整（Tab. 1）：物理 setup（[[Starlink]]、[[Tiansuan]]）fidelity 高但不可扩或不可自由跑用户应用；analytical simulator（[[STK]]、[[Hypatia]]、[[Cote]]、StarPerf）缺真实 system/network stack；virtualized emulator（[[Celestial]]、[[StarryNet]]）有容器与网络栈，但**不建模星载 COTS 在太空环境下的能耗与热约束**，导致算力与延迟严重偏离真值。

动机实验（Fig. 1）量化了两处典型失真：[[Cote]] 假设日照区 harvest power 恒定，与 BUPT-1 实测轨迹不符；[[StarryNet]] 用调 CPU 核数/频率模拟 Pi，YOLOv3/v5 推理延迟波动幅度比 onboard 小 160–330%，平均延迟偏差可达 15%，且无法复现过热初期 25 分钟的 throttling 抬升。RHONE 的目标就是同时补齐 satellite-level 与 constellation-level fidelity，并保持容器路线的可扩展性。

## 关键观察 / 隐含假设

- **观察 1：星载 COTS 的可用算力由能耗与热状态强耦合决定，且随轨道周期非平稳变化。** BUPT-1 / Tiansuan telemetry 显示：日照/阴影切换影响 harvest；电池放电深度限制可用功率；无主动散热时芯片温度触发 DVFS，短期降吞吐、长期损可靠性。Fig. 7 中 Pi 在 >80°C 时 YOLOv3/v5lite 延迟显著上升，Atlas 在不同功率档下响应不同。
  - **依赖假设**：研究对象以短任务 onboard inference（秒级 DNN）为主，单次执行对芯片温升可忽略；telemetry 来自 BUPT-1 与 Tiansuan 能代表典型 CubeSat 级 SCN。
  - **可能失效场景**：长时满载、多芯片并发、辐射致参漂移、或新型 rad-hard COTS 的热行为与论文 profiling 设备不一致时，power–thermal–compute 闭环可能偏离。

- **观察 2：同等温度下，地面拆掉风扇的 COTS 芯片性能退化可近似 in-space 行为。** 论文在 Earth 上对 Pi / Atlas 做 cyclic stress profiling，与在轨同温度点的任务延迟相对误差多数较小（Fig. 8），支撑「温度对齐即可镜像 throttling」的设计。
  - **依赖假设**：性能退化主要由温度驱动，而非微重力、真空、辐射或结构导热差异；用户注册的应用都可通过 offline profiling 建 satPerfTable。
  - **可能失效场景**：YOLOfastest 等极短延迟任务相对误差大；Atlas YOLOv3-Full 在部分温度点误差高——论文承认需热真空实验或直接在轨 profiling 才能进一步收敛。

- **观察 3：星座网络动态（拓扑变化、可预测轨道、能量触发的 node failure）与计算负载会互相放大。** 恶意 heavy traffic 可在阴影区加速电池耗尽并强制关闭 COTS（energy drain attack）；EO 场景下 onboard 处理可换带宽但增加计算功耗，通信子系统（X-band）功耗与链路占用强相关。
  - **依赖假设**：node failure 可由 power/thermal 模型确定性导出，比 [[StarryNet]] 的随机 failure 更贴近真实；orbit/network 模型沿用已有 LEO 可见性 + 传播延迟计算即可支撑 SCN 研究。
  - **可能失效场景**：辐射软错误、姿态失控、推进器故障、ISL 激光对准失败等未建模失效模式；攻击模型仅覆盖流量型 energy drain，不含物理层注入等。

- **假设 1：用 cgroup CPU share + CUDA API 拦截限速，可把更强 ground server 容器「放慢」到星载 COTS 性能。**
  - **证据强度：中。** emuPerfTable ↔ satPerfTable 映射在多数 DNN workload 上 mean relative error <5%；但极短任务与部分 Atlas 配置仍有高相对误差，说明资源配额粒度与异构加速器建模存在边界。

- **假设 2：离线重建模 + 在线轻量 agent 能在 constellation 规模下保持可接受 host 开销。**
  - **证据强度：强（规模维度）/ 中（绝对 fidelity）。** 720 卫星单节点 CPU 37.7%、内存 24.5%，与 StarryNet 持平或更低；但 setup time 因离线 trace 计算明显更长，且 fidelity 验证主要在 25 星网格与两种 COTS 设备上完成。

## 核心方法

RHONE 采用 **offline model building + online container emulation** 两阶段架构（Fig. 2），化解「单星高保真 emulation 成本高」与「星座规模可扩展」之间的冲突。实现约 4500 行 Python/C#；深度细节见 [[atc2025-wang-liying]]。

### 离线五类模型

1. **Power Model**
   - **Harvester**：$P_h = S \eta I_d L_d A \cos\theta$，θ 由轨道、姿态、帆板朝向决定，回应观察 1 中日照区功率非常数的问题。
   - **Consumer**：组件级 telemetry 聚类为 **Markov-based**（多功率档随机切换，如磁力矩器）与 **function-based**（X-band idle/active + 数据率；COTS 计算 $P_c = P_s(f) + U \cdot P_d(f) + P_l(T_{hottest})$）两类 pattern。

2. **Thermal Model**：在 SolidWorks 上做 [[Finite-Element-Analysis]]，解 $\rho c \frac{\partial T}{\partial t} = \nabla \cdot (k\nabla T) + q'''$，以 power model 产出的功耗为输入，implicit 时间步进更新芯片温度；外部轨道热流通过 interface temperature 边界锚定，避免为每颗卫星做昂贵热真空实测。

3. **Computation Model**：**hardware-in-the-loop chip mirroring**——真 COTS 板（去风扇）与对应 [[Docker]] 容器分别 profiling，得到 satPerfTable（温度→延迟）与 emuPerfTable（资源配额→延迟）。回应观察 2，把 in-space throttling 行为映射到地面可重复的 stress–cool 循环。

4. **Orbit + Network Model**：与 [[StarryNet]] 类似，由用户星座配置计算实时位置、ISL/GSL 可见性与传播延迟，并向 power model 提供太阳/地球相对几何。

### 在线 emulation 与对齐器

- **Emulated satellite node**：每星一个 state manager（context simulation agent）+ 多个容器，每容器代表一颗 COTS chip（ARM CPU 容器、GPU/NPU 容器等），支持星内多 SoC 通信，优于 StarryNet「一星一容器」的粗粒度。
- **Satellite COTS Aligner（SCA）**：读取 thermal model 当前温度 → 查 satPerfTable 得目标延迟 → 查 emuPerfTable 得 cgroup CPU/GPU share → 动态调频/限速（GPU 经 TGS 拦截 CUDA driver）。核心假设是 ground server 算力强于星载芯片，可通过**限资源**而非**造硬件**对齐性能。
- **Satellite Network Aligner（SNA）**：继承 StarryNet docker network，按 orbit/network model 配置时变带宽/时延/拓扑；**model-based node failure** 在低电量或过热时关闭 COTS，替代随机断链。
- **User APIs**：Monitor API 暴露温度、电量、链路、负载；Command API 支持改模式、改链路、在指定 COTS 上启停任务。

模型在线交互形成闭环（Fig. 9）：温度影响功耗 → 功耗驱动热更新 → 热影响 SCA 资源分配 → 应用负载再反馈功耗，与真实 SCN 的耦合路径一致。

## 设计取舍

- **离线建模 vs 在线全物理仿真**：收益是 constellation 规模下 host CPU/内存可控；代价是 setup 时间长，且新 COTS/新卫星需用户自行采集 telemetry 或重复 profiling 流程。
- **容器 + 资源限速 vs 星载硬件 farm**：收益是成本低、可跑真实 Linux 网络栈与用户二进制；代价是架构异构（x86 server 镜像 ARM+GPU 异构 SoC）靠查表对齐，对极短任务和未 profile  workload 脆弱。
- **FEA 热模型 vs 在轨热真空**：收益是可扩展、可复用工程界成熟流程；代价是边界条件靠经验接口温度锚定，平均误差 1.3–2.5°C，对精细 throttling 阈值可能不够。
- **继承 StarryNet 网络层**：收益是快速获得成熟 docker constellation 管理与 ISL 仿真；代价是 RHONE 的网络 fidelity 部分受限于 StarryNet 假设，论文主要增量在能耗/热/计算对齐与节点内多容器。
- **Telemetry 来源集中**：主要用 BUPT-1 开源数据 + 自采 Tiansuan 80 万条记录；收益是模型有真实 in-orbit ground truth；代价是对其他平台（大型 bus、不同电源架构）的外推需用户自扩展。

## 实验与结果

- **Scalability**：企业级双 Xeon E5-2670 v3、64GB RAM 单节点部署 172 / 348 / 720 星（对标 Starlink S3 shell）；720 星时 CPU 均值 37.7%、内存 24.5%，均 ≤ StarryNet；setup time 更长（720 星 42.2 vs 17.1 分钟），因离线环境 trace 与 COTS profiling。
- **Power fidelity**：harvest 电流 trace 在 Plane-Rotating 姿态下 99th percentile NSE 0.05，显著优于 CoteSim（90th percentile >1.5）；consumer 侧 X-band 平均误差 3.0%，Pi/Atlas 3.5%/3.8%，其他常开组件 4.1%。
- **Thermal fidelity**：25 星 5×5 网格 @550 km，Pi / Atlas 温度序列平均误差 2.5°C / 1.3°C。
- **Computation fidelity**：镜像 Pi/Atlas 跑 YOLOv3/5 系列，多数配置 mean relative error <5%；YOLOfastest、部分 Atlas 低温点例外。
- **Case study — energy drain attack**：720 星 36×20 网格，botnet 经 victim 卫星灌流；阴影区攻击更易把电池打到 60% 安全阈值并强制关闭 COTS，带宽瞬降至 0，复现 security + power 耦合。
- **Case study — real-time EO**：150 星 @550 km（对标 Planet Dove），200 Mbps 下行上限，比较 Direct / Compress(Q=75,50,25) / Detect(YOLOv3) / Reasoning 四策略；onboard 处理可将链路占用降至直传的 0.3× / 0.8× / 0.99×，且推理虽增计算功耗但降通信功耗，体现 computation–communication tradeoff。

## Critical Analysis

### 论证链条

论文链条清晰：**测量证明 SOTA emulator 在 power/compute 上失真** → **提出两阶段「真数据建模 + 轻量在线对齐」** → **分量验证五类模型误差** → **用安全攻击与 EO 案例展示端到端 SCN 行为**。从 motivation Fig. 1 到 SCA 查表机制，设计与观察 1/2 的映射明确。

薄弱环节在于：scalability 与 fidelity 实验配置不完全一致（720 星测资源，25 星测温/功耗/算力）；case study 展示的是「能跑出合理动态」，未与真实攻击 trace 或 Planet Dove 生产 telemetry 做数值对照。作者将 RHONE 定位为 research emulator 而非 operator 数字孪生，这一边界合理，但读者不应把 <5% 误差直接外推为「所有 SCN 应用性能预测误差 <5%」。

### 假设压力测试

- **COTS 种类**：profiling 仅覆盖 Raspberry Pi 4B 与 Huawei Atlas 200 DK；Jetson TX1/TX2、FPGA SoC 等论文引言提到的平台需用户走同一 mirroring 流程，论文未给出自动化成本与误差上界。
- **Workloads**：以 [[DNN-Inference]] 为主；长事务、流式视频路由、5G UPF 等 CPU+网络混合负载对 Markov/function 功耗分解是否足够，论文未验证。
- **星座规模外推**：700 星单节点是容器数量极限的一例；数千星需多节点集群，论文仅「预期可扩展」，未给跨节点时钟同步、全局 state store 一致性或 tail latency。
- **安全模型**：energy drain 基于饱和链路与路由开销，未覆盖 ICARUS 类拓扑预测攻击、物理层注入等；辐射、碰撞规避等 §9 明确留给 future work。

### 实验可信度

- **Baseline 选取合理**：CoteSim / StarryNet 正是论文 Tab. 1 指出的代表性缺口（能耗模型简化、容器算力失真），对比能支撑 design motivation。
- **Ground truth 可信**：BUPT-1 / Tiansuan 真卫星 telemetry + 在轨 DNN 实验，比纯解析 simulator 更有说服力。
- **Ablation 不足**：SCA、FEA 热模型、model-based failure、多容器 per satellite 等关键设计缺少逐一剔除实验；读者难判断误差主要来自哪一层。
- **Metric 覆盖**：偏重均值误差与案例趋势；未系统报告 emulation 引入的 tail latency 分布、多租户隔离、或长时间运行 drift。

### 系统性缺陷

- **Setup 与运维成本**：离线 phase 依赖 SolidWorks FEA、PyBaMM、真 COTS 板与可选热电制冷器；比纯软件 simulator 重得多，论文未量化用户接入新卫星的全流程人天。
- **可观测性**：提供 Monitor/Command API，但未讨论与真实卫星 OSS 对接、trace 导出格式标准化或 replay 可复现性（随机 Markov 功耗档的 seed 控制论文未强调）。
- **故障恢复**：case study 展示电池 recharge 后 COTS 恢复，但容器层 crash、docker network 分区、模型 store 损坏等 IT 故障论文未讨论。
- **正确性**：emulation 对齐的是性能与资源曲线，不验证应用语义正确性（例如压缩后图像质量、检测 mAP）；对 EO 案例仅报告 bitrate/功耗，不报告任务质量。
- **多节点生产部署**：论文未讨论。

## 局限与 Future Work

- **局限 1**：环境上下文仅覆盖 energy + thermal；辐射失效、碰撞规避、物理层安全等 SCN 关键因素未纳入（§9 自述）。
- **局限 2**：computation mirroring 对极短延迟任务与部分 Atlas 配置误差偏大，根因是地面 profiling 与在轨绝对延迟的微小偏差被短任务放大。
- **局限 3**：orbit/network 模型 largely 沿用已有工作，RHONE 的网络创新主要是对齐与 failure 语义，而非新 routing/transport 协议。
- **Future work 1**：对目标 COTS 做严格热真空或直接在轨 profiling，量化能否把 Fig. 8 高相对误差 workload 收敛到 <5%，并测量成本–精度曲线。
- **Future work 2**：在千星以上多节点 RHONE 集群上测量 setup time、state synchronization 开销与 case study 结果稳定性，验证「预期可扩」假设。
- **Future work 3**：引入辐射/单粒子失效模型，与现有 power-based failure 组合，评估对 constellation routing 与 [[Orbital-Edge-Computing]] 调度策略的影响。

## 相关

- **相关概念**：[[Orbital-Edge-Computing]]、[[LEO-Satellite-Network]]、[[Earth-Observation]]、[[COTS-Hardware]]、[[Docker]]、[[Finite-Element-Analysis]]、[[Hardware-in-the-Loop]]、[[DNN-Inference]]
- **同类系统**：[[StarryNet]]、[[Celestial]]、[[Hypatia]]、[[Cote]]、StarPerf、[[Tiansuan]]
- **同会议**：[[ATC-2025]]
- **对比**：相对 [[StarryNet]]，RHONE 补齐能耗/热/COTS 异构对齐与模型驱动 node failure；相对 [[Cote]] 等 analytical simulator，保留真实容器软件栈与交互流量，但以更高 offline 建模成本换取 fidelity
