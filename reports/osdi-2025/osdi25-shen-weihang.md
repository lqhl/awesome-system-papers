# XSched: Preemptive Scheduling for Diverse XPUs

**作者**：Weihang Shen, Mingcong Han, Jialong Liu, Rong Chen, Haibo Chen（上海交通大学并行与分布式系统研究所）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会），2025 年 7 月，Boston, MA
**DOI**：https://www.usenix.org/conference/osdi25/presentation/shen-weihang
**源文件**：[osdi25-shen-weihang.pdf](../../papers/osdi-2025/osdi25-shen-weihang.pdf)

---

## 一、背景

随着 AI 应用的爆发式增长，各类硬件加速器（XPU）——包括 GPU、NPU、ASIC、FPGA——被大规模部署在从云端到边缘的各类系统中。这些加速器往往需要被多个任务并发共享：云端服务商将单块 GPU 分给多个租户以降低成本，自动驾驶汽车在单块 NPU 上并发运行感知、规划、决策等多个 AI 算法，智能手机在单个 NPU 上同时运行前台实时语音输入与后台图片索引。

多任务并发对 XPU 调度提出了丰富的需求：实时系统要求关键任务具有最低延迟保障，数据中心需要租户间的公平性和最大硬件利用率，移动设备优先考虑功耗效率和用户响应性。任务抢占（preemption）是满足这些需求的核心机制，它能显著提升系统响应性和公平性，并提供调度灵活性。

---

## 二、要解决的问题

**问题一：XPU 硬件调度器不支持灵活抢占。**
XPU 通常作为外设由主机 CPU 管理，任务命令被顺序提交至硬件队列（hwQueue）。硬件调度器普遍采用非抢占式 FCFS（如 Intel NPU、NVIDIA/AMD GPU）或简单 Round-Robin 策略。这导致：高优先级任务被低优先级任务阻塞，尾延迟（P99）在多任务场景下可增大 20× 以上；租户间调度不公平；策略固化在硬件中无法按需调整。

**问题二：现有软件层抢占调度方案缺乏通用性。**
现有软件调度系统（EffiSha、FLEP、REEF、TimeGraph 等）存在三类不足：
- **可移植性差**：绑定特定 GPU 架构或驱动实现（如 REEF 集成在 AMD GPU 驱动中，TimeGraph 依赖 DRI 驱动），无法迁移到 NPU、ASIC、FPGA 或不同厂商的 GPU；对 NPU 和 ASIC 目前几乎没有软件抢占方案。
- **缺乏统一抽象**：没有跨 XPU 的统一调度接口，导致难以实现硬件无关的调度策略，也无法协调异构 XPU 之间的任务调度。
- **难以随硬件演进**：软件与硬件实现紧耦合，新硬件特性难以快速集成，废弃特性也难以去除。

---

## 三、核心设计

### XQueue 抽象

XSched 提出 **XQueue**（可抢占命令队列）作为核心抽象，类比 CPU 线程抽象：

- XPU 任务 = 一组顺序执行的命令（GPU kernel、内存拷贝、tensor 算子等），对应 CPU 任务的指令序列
- XQueue 承载一个 XPU 任务，XPU 作为 worker 从多个 XQueue 消费命令
- 任务抢占通过切换 XQueue 实现，与 CPU 线程切换的逻辑类似

XQueue 提供四个接口（见下表）：

| 接口 | 功能 |
|------|------|
| `submit(xq, cmd)` | 提交命令到 XQueue 异步执行 |
| `wait(xq, cmd)` | 等待指定命令完成 |
| `suspend(xq)` | 暂停 XQueue，挂起任务执行 |
| `resume(xq)` | 恢复 XQueue，继续任务执行 |

### 多级硬件模型（XAL）

为适配不同硬件能力，XSched 提出三级硬件模型：

- **Level 1（Lv1）**：暂停已提交但尚未启动的 pending 命令。所有 XPU 均可支持，通过控制命令的提交速率实现（progressive command launching）。
- **Level 2（Lv2）**：在 Lv1 基础上，还能终止已启动但尚未执行完毕的 in-flight 命令。需要硬件/驱动支持命令停止（stalling）或主动终止（flushing-based deactivation）。
- **Level 3（Lv3）**：在 Lv2 基础上，还能中断正在执行的 running 命令。需要硬件中断支持。

### XSched 框架架构

- **XShim**：透明拦截层，应用无需修改，XShim 将原始平台 API 转发给 XSched。
- **XPreempt**：实现不同级别的抢占机制，封装 XPU-specific 的硬件接口。
- **XScheduler**：守护进程，实现事件驱动的调度循环，根据策略调用 `suspend`/`resume` 切换 XQueue。
- **Progressive Command Launching**：Worker 线程异步、批量地向 hwQueue 提交命令，在保持低延迟的同时将大多数命令留在主机侧可控范围内；当 in-flight 命令数超过阈值时主动等待，以加快响应抢占请求。

---

## 四、实现细节

### Lv1 实现

利用各平台原生的 hwQueue API（CUDA stream、HIP stream、OpenCL command queue、ACL stream 等），仅需 214–841 行 C++ 代码，且可在同一软件平台的多种 XPU 间复用（如 OpenCL 实现同时适配 Xilinx FPGA、Intel GPU 和 Qualcomm GPU）。

### Lv2 实现（两种方案）

**Stalling-based（Intel NPU3720）**：通过新固件暴露的接口停止 hwQueue 中的命令。无额外运行时开销。

**Flushing-based（NVIDIA GPU）**：在运行时通过动态二进制插桩（DBI，利用 NVBit）在每个 GPU kernel 二进制的起始位置注入"guardian code"。guardian 代码检查 per-hwQueue 的 deactivation flag，若该 flag 被设置，则记录当前命令 ID 并退出（abort kernel）。Deactivate 时主机设置 flag，Reactivate 时清除 flag 并重新提交被中止的命令。这是首个 binary 级别的 flushing-based deactivation，兼容 TensorRT、cuBLAS、cuDNN 等闭源框架。

### Lv3 实现（NVIDIA GPU 两种方案）

**TSG-based（inter-process 粒度）**：利用 NVIDIA GPU 的 TimesliceGroup 中断机制，动态将目标 TSG 的 timeslice 设为 0 触发进程级抢占。

**Queue-based（hwQueue 粒度）**：通过逆向工程发现了未文档化的 ioctl 接口，可触发 GPU 中断并进入 trap handler；结合 guardian 技术，在 trap handler 中中止目标 kernel（仅适用于幂等 kernel，执行后从头重启）。

### 代码规模

Lv1 实现：214–841 行 C++；固定优先级策略：104 行；带宽分区策略：200 行；Triton 集成改动：10 行；Paella baseline 集成：15 行。总计覆盖 10 类 XPU，7 个软件平台（CUDA、HIP、LevelZero、ACL、CUDLA、VPI、OpenCL）。

---

## 五、实验结果

### 测试平台与硬件

10 款 XPU：NVIDIA GV100、K40m（GPU）；AMD MI50（GPU）；Intel Arc iGPU；Intel NPU3720；Ascend 910b（NPU）；NVIDIA DLA（ASIC）；NVIDIA OFA/PVA（ASIC）；Xilinx VU9P（FPGA）。

### 固定优先级策略（P99 尾延迟）

| XPU / 级别 | 原生调度器相对 standalone 劣化倍数 | XSched 相对 standalone 劣化倍数 | XSched 改善倍数 |
|---|---|---|---|
| GV100 / Lv3 | 1.60× | 1.02× | ~1.57× |
| K40m / Lv2 | 2.19× | ~1.04× | ~2.11× |
| MI50 / Lv1 | ~1.8× | ~1.3× | ~1.4× |
| NPU3720 / Lv2 | ~2.0× | ~1.05× | ~1.9× |
| 其余 XPU / Lv1 | 1.60–2.19× | 1.07–1.30× | 最高 2.11× |

### 带宽分区策略

在 75%/25% 的目标分配比下，XSched 整体吞吐与 standalone 相差仅 **1.5%**（平均开销），成功实现目标比例。

### 异构 XPU 协同调度

在 Jetson Orin 上同时调度 NPU 和 GPU，仅调度 NPU 时前台任务 P99 仍比 standalone 差 1.67×；启用 XSched N+G 联合调度后降至 **1.09–1.18×**，改善最高 **2.63×**。

### 运行时开销

- Lv1：所有 XPU 上不超过 **3.4%**
- Lv2（GV100/K40m）：额外增加 2.1%–4.0%
- CPU 利用率：大多数 XPU 增加不超过 **5%**（910b 18.3%、PVA 11.9% 因驱动使用 spinning 同步）

### Case Study 结果

| 场景 | 指标 | 结果 |
|---|---|---|
| 多租户云 GPU（GV100）| XSched vs TGS 闲置资源利用率 | **2.74×** 更多 GPU 资源给后台任务，生产任务性能损失仅 **1.0%** |
| AI PC 视频会议（NPU3720）| LFBW P99 帧延迟 vs 原生 | **9.26× 降低**（880ms → 95ms），whisper.cpp 无内容丢失 |
| Triton 推理服务（GV100）| 高优先级模型 P99 延迟 | 相比 vanilla Triton 降低 **30.0%** |
| Paella 对比（GV100，1000 reqs/s）| P99 延迟 | XSched **优于 Paella 1.3×** |

---

## 六、批判性分析

**1. Lv3 的"幂等 kernel"假设过强，论文轻描淡写。** 实现 Lv3 抢占需要中断并重启 kernel，这仅对幂等（idempotent）kernel 安全。论文承认目前靠人工标注幂等性，并引用一篇同组 arXiv 预印本称可自动验证——但该论文尚未发表，可靠性存疑。在生产环境中，cuBLAS/cuDNN 等闭源库的 kernel 幂等性难以验证，实际 Lv3 的适用范围可能远比实验中展示的更窄。

**2. queue-based Lv3 依赖未文档化的 ioctl，稳定性存疑。** 论文自己也承认该接口"potentially unstable"，且如果被 NVIDIA 废弃，Lv3 将回退到 Lv2。这不是一个可以在生产系统中可靠依赖的机制，但实验结果（尤其是 Case 1）依赖 Lv2 而非 Lv3，说明作者对此有意识地控制了实验范围。

**3. 带宽分区策略的"overhead 仅 1.5%"是平均值，方差被掩盖。** 实验中 MI50、910b、VU9P 原生调度器的总吞吐本就高于 standalone（因为可空间复用），XSched 在这些设备上的性能其实有所下降。1.5% 的平均 overhead 并不代表所有 XPU 场景下的真实代价。

**4. Case Study 的"9.26×"是针对 P99 尾延迟峰值的改善，有夸大之嫌。** 原始基线 P99 高达 880ms 是因为 NPU 采用 FCFS 策略导致 LFBW 等待 whisper.cpp 完整执行（0.8s），这是一个极端 bad case，并非平均情况。改善倍数的选择对应了最戏剧性的数据点。

**5. 内存问题被显式排除在系统边界之外。** 论文假设 XPU 有足够物理内存容纳所有任务数据，实际上多任务场景下内存竞争是重要的调度约束，XSched 尚不处理内存调度，与 SUV 等系统的集成留作"future work"。

**6. 安全模型依赖 shim 层，不可信租户场景无解。** 论文在 Discussion 中承认恶意租户可绕过 XSched，依赖 API remoting 作为外部安全边界。这意味着 XSched 在真正多租户云场景中需要额外的系统支撑，并非开箱即用的完整解决方案。

---

## 七、AI Infra / MLSys 视角

**调度框架对 AI 推理系统的直接价值。** XSched 与 Triton 的集成（10 行代码）以及与 Paella 的性能对比，展示了软件定义 XPU 调度对 LLM/DNN 推理服务的实际价值。在 disaggregated inference、prefill-decode 分离等场景中，不同阶段的任务具有不同优先级和延迟要求，XSched 的固定优先级和带宽分区策略可直接映射到这类需求。

**NPU 调度是被忽视的重要方向。** 随着 AI PC（Intel Core Ultra、Apple Silicon）和边缘设备（Jetson Orin）的普及，NPU 成为端侧推理的主力芯片。XSched 是首个支持 NPU 软件抢占调度的系统，其在 Intel NPU3720 和 Ascend 910b 上的实现经验对 AI 系统研究有重要参考价值。

**多 XPU 协同调度是 AI 异构系统的关键未解问题。** Case Study 展示了 GPU+NPU 内存带宽竞争导致的性能干扰，以及跨 XPU 统一调度的必要性。这与当前 LLM 推理系统中 CPU+GPU+专用 ASIC 混合部署的趋势高度吻合，XSched 的 XQueue 统一抽象为跨异构加速器调度提供了一个有价值的参考框架。

**可跟进的研究方向：**
- 将 XSched 扩展至 LLM 推理中的 KV cache 感知调度：不同请求的 KV cache 占用与 token 生成速率差异大，结合 XSched 的带宽分区策略可以实现更细粒度的 SLO 保障。
- 与 GPU 内存管理系统（如 vLLM 的 paged attention、Mooncake）结合：当任务被抢占时，如何高效保存和恢复 KV cache 状态？
- 针对 AI PC 端侧推理的跨 CPU/GPU/NPU 统一调度：端侧模型越来越多地在异构计算单元间流水执行，XSched 的跨 XPU 协同调度思路值得在这一场景下系统化研究。

---

## 八、总结

XSched 提出了 XQueue 抽象和三级硬件模型（XAL），首次实现了跨 GPU、NPU、ASIC、FPGA 等 10 类 XPU 的统一软件抢占调度框架，支持固定优先级和带宽分区等硬件无关策略。系统在延迟（P99 最高降低 2.11×）、公平性和资源利用率上均有显著提升，运行时开销不超过 3.4%，并可以极低的代码改动量（10–15 行）集成到生产系统中。主要局限在于 Lv3 对幂等 kernel 的假设难以在闭源环境下普遍满足、未处理内存资源调度，以及在不可信多租户场景中需要依赖额外的 API remoting 安全机制。
