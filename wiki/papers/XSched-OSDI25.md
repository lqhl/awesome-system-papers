---
type: paper
name: XSched
full_title: "XSched: Preemptive Scheduling for Diverse XPUs"
authors: [Weihang Shen, Mingcong Han, Jialong Liu, Rong Chen, Haibo Chen]
venue: OSDI
year: 2025
tags: [gpu-scheduling, preemption, xpu, npu, accelerator]
source_pdf: "[[osdi25-shen-weihang.pdf]]"
source_md: "[[osdi25-shen-weihang]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# XSched: Preemptive Scheduling for Diverse XPUs (OSDI 2025)

> **一句话总结**：用类 CPU thread 的 XQueue 抢占式命令队列 + 三级硬件模型（Lv1 pending / Lv2 in-flight / Lv3 running）统一 GPU/NPU/ASIC/FPGA 的软件抢占调度，在 10 种 XPU 上高优任务 P99 尾延迟降 2.10×、带宽分区平均开销 1.5%，Triton 接入仅需十几行代码。

## 问题与动机

[[GPU]]、NPU、ASIC、FPGA 等 XPU 在多云多租、实时车载、AI PC 等场景必须共享，但片上调度器多为 FCFS 或简单 RR，无法表达优先级、带宽份额或 deadline。已有软件抢占方案（EffiSha、FLEP、REEF、TimeGraph、TGS）绑死特定 GPU：依赖 kernel 重写（NPU/ASIC 不可编程）、AMD microcontroller、或 NVIDIA Tegra 专用 ioctl，在异构云/边缘平台面临 **Portability / Uniformity / Evolvability** 三重缺口。根因是 XPU 硬件能力与软件栈差异大且快速演进，缺少类似 CPU thread 的统一抽象与分级硬件模型。

## 关键观察 / 隐含假设

- **观察 1**：绝大多数 XPU 任务可建模为 host 顺序提交的 command 流（kernel、memcpy、tensor op 等），驱动普遍提供 hwQueue/stream 接口——抢占可在 host 侧通过 suspend/resume 队列实现，不必改应用语义。
  - **依赖假设**：任务由多条 command 组成；单条巨型 command（CUDA Graph、整模型 NPU 推理）需 Lv3 或 model slicing 才能快抢占（§9）。
  - **可能失效场景**：DPU/部分 FPGA 主动执行任务、不经 host 下发 command 时，host-managed 方案不适用。
- **观察 2**：per-command 同步抢占会把现代 GPU 流水线打爆（8.2%–151.3% 退化，越新 GPU 越糟），必须在「保留少量 in-flight command」与「host 可控」之间折中。
  - **依赖假设**：progressive launching 的 threshold（实验 2–16）可按 workload 调；command 执行时间分布相对稳定。
  - **可能失效场景**：极短 command 密集流仍放大同步比例；Lv1-only 设备抢占延迟 ≈ 整条 hwQueue 执行时间（8×0.5ms 实验）。
- **假设 1**：Lv1（仅 launch/sync）即可覆盖新兴「弱」XPU，214–841 行 C++ 可移植；成熟设备再叠 Lv2/Lv3 换更低抢占延迟。
  - **证据强度**：强；Table 3 覆盖 7 平台 10 设备，首次在 Intel NPU、NVIDIA ASIC 等实现软件抢占。

## 核心方法

**XQueue 抽象**：类比 CPU thread，每任务一条顺序 command 队列，接口 `submit/wait/suspend/resume`；策略（固定优先级、bandwidth partition、SRTF、EDF、laxity）与硬件解耦。

**三级硬件模型**（灵感来自 DB 隔离级别）：
- **Lv1**：阻止 pending command launch，所有 XPU 可支持。
- **Lv2**：`deactivate/reactivate` hwQueue——Intel NPU 用 microcontroller stalling；NVIDIA GPU 用 DBI 注入 guardian code 做 flushing（首个二进制级方案，兼容 TensorRT/cuBLAS 闭源 kernel）。
- **Lv3**：`interrupt/restore` 正在执行的 command——NVIDIA TSG timeslice ioctl（进程级）或 undocumented queue ioctl + trap handler（hwQueue 级，仅抢占幂等 kernel）。

**XSched 框架**：XShim 拦截 driver API；XPreempt 实现 XQueue + progressive command launching（in-flight 达 threshold 则 sync 一半完成）；XAL 封装多级接口；XScheduler daemon 经 shared-memory IPC 全局协调跨进程/容器 XQueue。

## 设计取舍

- **取舍 1**：Lv3 queue-based 无法从断点恢复非幂等 kernel，只能重启——换细粒度 hwQueue 抢占与可部署性。
- **取舍 2**：GV100 Lv3 依赖未文档化 ioctl，可被厂商废弃——模型允许降级禁用 Lv3 而不动其余栈。
- **边界条件**：假设 XPU 物理内存充足（不算 paging）；恶意 tenant 可绕过 XShim，需 API remoting/虚拟化配合；跨 VM 调度需网络 IPC（未深入评测）。

## 实验与结果

- **可移植性**：10 种 XPU × 7 软件平台；Lv1 214–841 LoC，OpenCL 实现可共享多厂商 GPU/FPGA。
- **固定优先级**：前景任务 P99 相对原生调度降最多 2.10×（前景 standalone 的 1.02×–1.30×）；原生共享可使 P99 恶化 1.60×–2.19×。
- **带宽分区**：75%/25% 份额，平均总吞吐开销 1.5%。
- **异构协同**：Jetson Orin / Core Ultra 上 NPU 前景 + GPU 背景，统一策略使 NPU P99 再降 2.63×（仅调度 NPU 时仍 1.55×–1.67× standalone）。
- **抢占延迟**：GV100 Lv1≈8T、Lv2≈1T、Lv3≈32µs（T=0.5ms）；Lv1 运行时开销 <3.4%，CPU 单核 +5% 以内（910b 18.3% 因 driver spin）。
- **案例**：多租 GPU 收割 Ojob 资源 2.74× vs TGS 且 Pjob 退化 ≤1%；视频会议 NPU P99 帧延迟 9.26×；Triton Bert P99 降 30% 与 Paella 持平/高吞吐 1.3×。

## Critical Analysis

### 论证链条

「XPU 异构 → 需统一抽象 + 分级模型 → 软件抢占可移植」逻辑闭合；progressive launching 直接回应同步 strawman 的测量（Fig. 5）。案例研究把策略收益与生产系统（Triton）对接，比纯 microbenchmark 更有说服力。Lv2 flushing 的二进制 DBI 是独立工程贡献，支撑「闭源生态可抢占」claim。

### 假设压力测试

- **已证明**：10 设备上优先级/带宽策略有效；heterogeneous SoC 上内存带宽干扰需跨 XPU 协同调度。
- **可能失效**：单 command 任务、非幂等 Lv3 kernel、AMD 仅 Lv1 时长 command 仍高抢占延迟；恶意 bypass、显存 oversubscription 未在本工作中解决。
- **论文未覆盖**：跨 VM/多节点全局调度延迟；与 [[Continuous-Batching]] 类推理调度器深度协同时的 batch 级抢占语义。

### 实验可信度

前景/背景双进程 ResNet-152 等 workload 代表常见 AI 争用；与 TGS/vCUDA/Paella 对比有针对性。阈值 per-device 手工调优可能掩盖最差配置；financial Pjob 上 TGS 70% 退化凸显 baseline 选取的重要性。

### 系统性缺陷

依赖 LD_PRELOAD shim、daemon IPC 与部分未文档化接口，运维与厂商升级风险高；Lv2 DBI 有 2%–4% 额外开销；不信任 tenant 需另层虚拟化；DPU 等主动执行 XPU 完全 out of scope。

## 局限与 Future Work

- **局限 1**：仅计算调度，未与 Unified Memory / DeepUM 等 paging 协同。
- **局限 2**：单 command 任务与主动执行型 XPU 需 Lv3 或架构扩展。
- **Future work 1**：与显存 oversubscription 系统联合调度 swap 与抢占，量化端到端 SLO。
- **Future work 2**：hypervisor API remoting 集成下的多租安全抢占与跨 VM 策略评测。

## 相关

- **相关概念**：[[Continuous-Batching]]、[[Pipeline-Parallelism]]
- **同类系统**：REEF、TimeGraph、EffiSha、FLEP、TGS、Paella
- **同会议**：[[OSDI-2025]]
