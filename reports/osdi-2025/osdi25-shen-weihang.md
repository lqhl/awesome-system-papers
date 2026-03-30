# XSched: Preemptive Scheduling for Diverse XPUs

## 论文基本信息

- **标题**: XSched: Preemptive Scheduling for Diverse XPUs
- **作者**: Weihang Shen, Mingcong Han, Jialong Liu, Rong Chen, Haibo Chen（上海交通大学）
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/shen-weihang

## 研究背景与动机

XPUs（GPU、NPU、ASIC、FPGA 等各类加速器）被广泛部署于从云到边缘的各类系统中，用于卸载 CPU 的密集计算任务。多任务共享同一 XPU 是提高硬件效率的必要手段（如云服务商在单 GPU 上服务多 tenant、边缘设备在单 NPU 上运行多个 AI 模型）。

然而，XPUs 的硬件调度器普遍缺乏灵活性：
- **Non-preemptive FCFS**（Intel NPU、NVIDIA/AMD GPU）：紧急任务可能被低优先级任务阻塞
- **Simple Round-Robin**（multi-process GPU tasks）：无法满足差异化优先级需求

**后果**：不公平、优先级反转、SLO 违规。论文实测视频会议应用在 NPU 上与语音识别任务共享时，尾延迟增加超过 **20×**。

**现有软件预emption方案的局限**：
- **Portability**：现有方案专为特定 GPU 设计，难以移植到其他加速器
- **Uniformity**：缺乏统一的 XPU 任务调度抽象
- **Evolvability**：软硬件紧耦合，无法快速适应新硬件特性

## 要解决的核心问题

**核心问题**：XPUs 的硬件调度器不支持灵活策略，而现有软件预emption方案缺乏跨 XPU 类型的可移植性、统一抽象和可演化性。

**根本原因**：XPUs 在硬件能力和软件栈上存在显著且不断演化的差异。例如：
- GPU 支持通用可编程性（可通过 kernel transformation 实现 preemption），但主流 NPU/ASIC 通常不可编程
- 不同厂商的驱动和 runtime 差异巨大（NVIDIA CUDA vs. AMD ROCm vs. Intel oneAPI）

## 主要贡献

1. **XQueue 抽象**：一种 preemptible command queue 抽象，提供统一的任务调度接口
2. **Multi-level 硬件模型**：将 preemptive 调度能力分为 Lv1/Lv2/Lv3 三个层次，使不同能力的 XPU 都能找到合适的实现
3. **XSched 框架**：基于 XQueue 和 multi-level 硬件模型，实现了跨 10 种 XPU（NVIDIA/AMD GPU、Ascend/Intel NPU、NVIDIA PVA/OFA ASIC、Xilinx FPGA）的 preemptive 调度
4. **硬件无关调度策略**：实现了 fixed priority 和 bandwidth partition 两种策略

## 研究方法与设计

### XQueue 抽象

XQueue 是一个 preemptible command queue，类比 CPU thread abstraction：

| CPU Thread | XQueue |
|---|---|
| 指令序列 | XPU 命令序列 |
| CPU 执行 | XPU 执行 |
| 线程切换 | XQueue 切换（暂停/恢复）|

**接口**：
- `submit(xq, cmd)`：提交命令
- `wait(xq, cmd)`：等待命令完成
- `suspend(xq)`：暂停任务执行
- `resume(xq)`：恢复任务执行

**与 hwQueue 的关键区别**：hwQueue（CUDA streams、Level Zero command queues）是 non-preemptible 的；XQueue 支持 host CPU 通过 suspend/resume 控制命令是否能在 XPU 上执行。

### Multi-level 硬件模型

三个 preemption 层次对应命令的三种状态：

#### Lv1: Pending Command Preemption
- **目标**：暂停尚未 launch 到 hwQueue 的命令
- **能力要求**：launch + synchronize 命令（所有 XPU 都提供）
- **Preemption latency**：所有已 launch 命令的执行时间
- **适用范围**：不可编程的 NPU/ASIC

#### Lv2: In-flight Command Preemption
- **目标**：阻止已在 hwQueue 中但尚未执行的命令
- **关键能力**：deactivate/reactivate hwQueue
- **两种实现**：
  - **Stalling-based**：通过 stall 命令出队来暂停（需要微控制器支持）
  - **Flushing-based**：清空队列重新调度
- **Preemption latency**：当前 running 命令的执行时间
- **适用范围**：具有微控制器的现代 GPU

#### Lv3: Running Command Preemption
- **目标**：中断正在执行的命令
- **能力**：GPU interrupt 支持
- **Preemption latency**：interrupt response 时间
- **适用范围**：Pascal 之后支持 interrupt 的 NVIDIA GPU

### 调度策略实现

#### Fixed Priority Policy
- 每个 XQueue 分配固定优先级
- 触发时机：XQueue 状态变化（新命令到达、命令完成）
- 动作：恢复最高优先级 ready XQueue，暂停其他

#### Bandwidth Partition Policy
- 每个 XQueue 分配比例份额（timeslice）
- 触发时机：timeslice 耗尽（timer 中断）
- 动作：暂停当前 XQueue，恢复下一个（round-robin）

两种策略都只需 XQueue 的 suspend/resume 接口，与 XPU 硬件实现无关。

## 关键实现细节

### Lv2 实现：Stalling-based Deactivation

NVIDIA GPU（Kepler/Volta/Amd）：

对于 command queue 的 deactivate：
- 注入特殊 barrier 命令到队列，暂停后续命令执行
- 新命令可在其他 queue 执行
- Reactivate：注入 activation 命令

### Lv2 实现：Flushing-based Deactivation

Intel NPU：
- 将未执行的命令 flush 回 host memory
- 重新 submit 到新 XQueue
- 通过 ioctl 控制 NPU scheduling

### Lv3 实现：NVIDIA GPU Interrupts

Pascal 之后 NVIDIA GPU 支持 interrupt：
- 通过 CUDA event + interrupt 实现 Lv3 preemption
- 比 Lv2 更快的响应时间

### 代码规模

Lv1 实现：214–841 行 C++ 代码（per XPU software platform）
Lv2/Lv3：额外少量代码

## 实验结果与分析

### 测试环境
- 10 种不同 XPU（见上述）
- 7 个软件平台

### 固定优先级策略

**Tail latency (P99)**：高优先级任务尾延迟降低最高 **2.10×**

### 带宽分区策略

平均 overhead **1.5%**（跨不同 XPU 和工作负载）

### Cooperative Scheduling（跨 XPU 协作）

背景和前景任务分别在不同 XPU 上运行时的协作调度：
- **P99 尾延迟降低最高 2.63×**

### 案例研究 1: Multi-tenant Cloud

两容器共享单 GPU：
- **XSched vs. TGS（NVIDIA container scheduling）**：XSched 收集 **2.74×** 更多 GPU 资源，同时维持 production container 性能

### 案例研究 2: Video Conferencing

单 Intel NPU 上运行视频会议（前景）+ 语音识别（背景）：
- **P99 尾延迟降低 9.26×**（从 20× 增加到"接近单任务性能"）

### 案例研究 3: Multi-model Inference Serving

Triton inference server 上：
- **P99 推理延迟降低 30.0%**
- 性能与 Paella（hardware-specific 方案）相当
- 集成 XSched 仅需约 12 行代码

## 潜在问题与局限性

1. **与 vendor 官方工具链的兼容性**：XSched 需要拦截应用程序的命令提交，这可能与 NVIDIA/AMD 的官方 toolchain（Nsight、cuBLAS、TensorRT）的内部假设冲突，特别是当这些工具直接管理 GPU command queues 时
2. **跨 vendor 的硬件能力检测**：不同 XPU 的 preemption 能力检测缺乏标准化方法；XSched 依赖人工检查和特定于平台的探测代码，扩展到新 XPU 需要额外工程工作
3. **高精度 timeslice 调度的 timer 精度**：Bandwidth partition policy 依赖 timer 中断来触发重新调度；在 Linux 上 timer 精度受调度器 jitter 影响，可能无法满足微秒级 SLO 需求
4. **GPU memory management 与 preemption 的交互**：当被 preempted 的任务正在分配 GPU memory 时，resume 时需要处理 GPU memory allocator 的状态一致性，论文对此讨论不足
5. **跨 XPU heterogeneous scheduling 的实现**：论文提到了 heterogeneous platforms（如 Intel Core Ultra 同时有 CPU 和 NPU）上的协作调度，但具体实现细节（如跨 XPU 优先级映射）有限
6. **长时运行任务的影响**：当一个高优先级任务需要 preempt 正在执行的长 kernel（如大型矩阵乘法）时，恢复点的选择（kernel 中断 vs. kernel 边界）影响 preemption 精度，论文主要关注 command 级别的 preemption 而非 intra-kernel preemption

## 未来工作方向

1. 探索 Lv3 在更多 XPU 平台上的支持
2. 自适应调度策略（根据运行时工作负载特征调整）
3. 与容器编排系统（Kubernetes、Docker）的集成
4. 在生产环境中的长期稳定性评估

## 个人评注

### 优点

1. **问题现实且重要**：XPUs 的调度不灵活性在云和边缘部署中是广泛存在但缺乏系统性解决方案的问题。20× 的尾延迟退化是一个令人信服的问题动机
2. **Multi-level 硬件模型的设计出色**：将 preemption 能力按命令状态分层（pending/in-flight/running）是一个聪明且可扩展的设计，允许不同能力的 XPU 找到合适的实现层次
3. **覆盖广泛**：10 种 XPU、7 个软件平台的支持是同类工作中最广泛的
4. **代码量可接受**：Lv1 实现只需 214-841 行 C++，表明框架的工程复杂度可控

### 不足与可疑之处

1. **Triton 集成仅需 12 行代码的说法需要验证**：论文声称"Triton 集成仅需 12 行代码"，但 Triton 是一个复杂的 inference serving 系统，其 plugin 架构是否真正支持 XSched 的 suspend/resume 控制需要更多信息验证
2. **TGS 比较的公平性**：TGS（Temporal GPU Sharing）是 NVIDIA 官方的 container scheduling 方案，但 XSched 是更底层的 preemption 机制，两者是否在相同的基准上比较（TGS + Linux CFS vs. XSched + XSched scheduler）？如果 TGS 本身使用了 CFS 调度，TGS 的不公平可能部分来自 CFS 而非 GPU 调度
3. **Preemption latency 的量化数据缺失**：论文描述了三个 preemption 层次的 latency 特性，但没有报告具体数值（如 Lv2 在 NVIDIA GPU 上从 preempt 到 resume 需要多少微秒）。这是评估 XSched 实用性关键数据
4. **Multi-tenant 场景的资源收集数字需要更仔细解读**："2.74× more GPU resources"的定义不够清楚——是 GPU utilization 的 2.74× 提升，还是 GPU memory 利用的提升？不同的度量标准对应不同的实际意义
5. **XSched 与其他 GPU sharing 方案（time-slicing、MIG）的对比缺失**：论文没有与 NVIDIA MPS（Multi-Process Service）、MIG（Multi-Instance GPU）等生产级 GPU sharing 方案进行直接比较，读者难以判断 XSched 相对于这些成熟方案的优劣
6. **Security/isolation 问题未涉及**：在 multi-tenant 场景中，被 preempted 任务 A 的 GPU state（registers、local memory）是否可能被下一个运行的任务 B 观察到？Preemption 点的选择是否可能成为 side-channel？这些问题在高安全需求场景下至关重要
