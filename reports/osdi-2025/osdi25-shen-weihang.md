# XSched: Preemptive Scheduling for Diverse XPUs

**作者**：Weihang Shen, Mingcong Han, Jialong Liu, Rong Chen*, Haibo Chen（上海交通大学并行与分布式系统研究所）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation）
**链接**：https://www.usenix.org/conference/osdi25/presentation/shen-weihang
**源文件**：[[osdi25-shen-weihang.pdf]]

---

## 一、背景

随着 AI 和异构计算的快速发展，各种加速器（XPU）——包括 GPU、NPU、ASIC、FPGA——被广泛部署在从云端到边缘的各类系统中。这些系统通常需要多个任务共享同一个 XPU：云服务商让多个租户共享 GPU 以降低成本，自动驾驶平台在单个 TPU/ASIC 上运行感知、规划、决策等多个算法，智能手机在单个 NPU 上同时运行前台和后台 AI 任务。

丰富的应用场景对 XPU 任务调度提出了多样化需求：实时系统需要低延迟确定性响应，数据中心需要租户间公平性和 SLO 保障，移动设备需要用户响应优先。任务抢占（preemption）是满足这些调度需求的关键机制，但现有 XPU 在抢占式调度方面存在严重不足。

---

## 二、要解决的问题

1. **硬件调度器能力不足**：XPU 内置的硬件调度器通常采用非抢占式 FCFS 或简单 round-robin 策略，导致优先级反转和尾延迟飙升。例如，在 Intel NPU 上与 speech-to-text 任务共享时，fake-background 任务的尾延迟增加超过 20 倍。

2. **现有软件方案缺乏通用性**：
   - **可移植性差**：现有方案（如 EffiSha、FLEP、REEF）针对特定 GPU 设计，无法移植到 NPU、ASIC、FPGA，甚至不同厂商的 GPU。
   - **缺乏统一抽象**：没有跨 XPU 的统一调度抽象，阻碍了硬件无关调度策略的开发和异构平台上的协同调度。
   - **演进能力差**：软硬件紧耦合，无法灵活适应新硬件能力或淘汰旧功能。

3. **根本原因**：XPU 硬件能力差异大且持续演化，软件栈高度定制化，缺乏像 CPU 线程/磁盘块设备那样的统一硬件模型和抽象。

---

## 三、洞察与设计

**关键洞察**：尽管各种 XPU 在硬件能力和软件栈上差异巨大，它们的驱动程序普遍提供了基于队列的编程模型和接口（hardware queue, hwQueue）。这种共性使得构建统一的可抢占命令队列抽象成为可能。同时，XPU 的抢占能力可以按照命令状态（pending → in-flight → running）划分为三个层级，形成渐进式的硬件模型——低层级仅需基本能力（所有 XPU 都支持），高层级利用高级硬件特性实现更精细的抢占。

### XQueue 抽象

XSched 提出 XQueue——可抢占命令队列抽象，类比 CPU 线程抽象：
- 每个 XQueue 承载一个 XPU 任务（命令序列）
- XPU 作为 worker 从多个 XQueue 消费命令
- 通过 `suspend`/`resume` XQueue 实现任务抢占
- 接口简洁：`submit(xq, cmd)`、`wait(xq, cmd)`、`suspend(xq)`、`resume(xq)`

### 三级硬件模型

| 级别 | 抢占目标 | 所需硬件能力 | 抢占延迟 |
|------|----------|-------------|---------|
| Lv1 | Pending commands（已提交未发射） | 基本的命令发射和同步 | 所有 in-flight 命令执行时间之和 |
| Lv2 | In-flight commands（已发射未执行） | hwQueue 的 deactivate/reactivate | 当前正在执行的单条命令执行时间 |
| Lv3 | Running commands（正在执行） | 中断和恢复运行中命令 | 近乎即时（~32µs） |

### 系统架构

XSched 由四个组件构成：
- **XShim**：透明拦截应用的 XPU 驱动 API 调用，重定向到 XQueue
- **XPreempt**：实现 XQueue 抽象，包含 progressive command launching 机制
- **XAL（XPU Adapter Layer）**：实现多级硬件模型接口，封装 XPU 特定的驱动 API
- **XScheduler**：事件驱动的调度守护进程，协调所有进程的 XQueue，支持可插拔策略

---

## 四、实现细节

### Progressive Command Launching

解决同步执行的性能瓶颈（8.2%–151.3% 开销）。维持少量 in-flight 命令（阈值可调，实验中 2–16），在抢占延迟和运行时开销之间取平衡。当 in-flight 数量超过阈值时，同步等待一半命令完成后再继续发射。

### Lv2 实现

- **Stalling-based（Intel NPU）**：利用 NPU 固件中的微控制器（Leon RT core）暂停命令出队，零额外开销。修改驱动暴露了 2024 年 7 月新固件的能力。
- **Flushing-based（NVIDIA GPU）**：运行时动态二进制插桩（DBI），在每个 GPU kernel 二进制前注入 guardian 代码片段，检查 per-hwQueue deactivation flag。flag 置位时 kernel 自行 abort。首次在二进制层面实现 flushing，兼容闭源库（cuBLAS、cuDNN、TensorRT）。

### Lv3 实现

- **TSG-based（NVIDIA Pascal 架构后的 GPU）**：动态调整 Timeslice Group 的时间片为零触发中断，实现进程级抢占。
- **Queue-based（NVIDIA Volta/Ampere）**：发现未文档化的 ioctl 触发 GPU 中断，结合 trap handler 和 guardian 技术，实现 hwQueue 粒度的细粒度抢占。仅支持幂等 kernel（需手动标识）。

### 适配范围

覆盖 10 种 XPU、7 个软件平台：NVIDIA/AMD/Intel GPU，Intel/Ascend/NVIDIA NPU，NVIDIA PVA/OFA ASIC，Xilinx FPGA。Lv1 实现仅需 214–841 行 C++ 代码。

---

## 五、实验结果

### 调度性能（10 种 XPU）

**Fixed Priority 策略**：

| 指标 | Native 硬件调度器 | XSched |
|------|-----------------|--------|
| 前台任务 P99 延迟（vs standalone） | 1.60×–2.19× | 1.02×–1.30× |
| 最大改善 | — | 尾延迟降低 2.11× |

**Bandwidth Partition 策略**：XSched 平均仅 1.5% 开销，实现目标吞吐量分配比。

### 异构平台协同调度

在 Intel Core Ultra 和 NVIDIA Jetson Orin 上，XSched 统一调度 NPU+GPU，前台 NPU 任务 P99 延迟降低最多 2.63×。

### Case Study 结果

| 场景 | 关键指标 |
|------|---------|
| GPU harvesting（多租户） | 比 TGS 多收割 2.74× GPU 资源，生产任务仅 1.0% 性能损失 |
| AI PC 视频会议（Intel NPU） | P99 帧延迟从 880ms 降至 95ms，改善 9.26× |
| Triton 推理服务 | 高优模型 P99 延迟降低 30.0%，仅需修改 10 行代码 |
| vs Paella（SOTA） | 低负载相当，高负载（1000 reqs/s）超越 1.3× |

### 开销

- 运行时开销：Lv1 < 3.4%，Lv2 额外 2.1%–4.0%（flushing-based），硬件辅助 Lv2（NPU）零额外开销
- CPU 开销：大多数 < 5%（910b 和 PVA 较高，因驱动 spinning 同步）
- Lv3 抢占延迟：GV100 上仅 32µs，与命令执行时间无关

---

## 六、批判性分析

1. **Lv3 的实用性受限**：Queue-based Lv3 抢占依赖未文档化的 NVIDIA ioctl 接口，作者自己承认其"potentially unstable"。更关键的是，Lv3 仅支持幂等 kernel 且需要手动标识，这在生产环境中实用性存疑——DNN 推理中大量 kernel 涉及原子操作或状态更新，幂等性难以保证。

2. **内存管理完全缺失**：XSched 假设 XPU 物理内存充足以容纳所有任务数据，但实际多租户场景中内存竞争是核心挑战之一。论文将内存管理推给 future work，但缺少内存调度的抢占式调度框架在真实部署中价值打折扣。

3. **Lv1 在快命令场景下效果有限**：对于仅支持 Lv1 的 XPU（占覆盖 XPU 的大多数），抢占延迟等于所有 in-flight 命令的总执行时间。实验中部分 XPU 的尾延迟退化高达 29.6%，这对实时场景可能仍不够。论文对此轻描淡写，重点突出了 Lv2/Lv3 的效果。

4. **安全模型的漏洞**：恶意租户可绕过 XSched 直接访问 XPU。论文建议结合 API remoting 解决，但这引入了额外的虚拟化开销，与 XSched 追求的低开销目标存在张力。

5. **实验工作负载偏单一**：主要评估使用 ResNet-152 推理作为基准，且前后台任务运行相同模型。缺乏混合工作负载（如训练+推理、不同模型大小）的评估，难以判断策略在复杂真实场景中的效果。

6. **DBI 兼容性风险**：Flushing-based Lv2 依赖 CUDA 隐藏的 export table 函数来分配和访问 GPU instruction/constant memory，这些未公开接口在 CUDA 版本升级时可能随时失效。

---

## 七、AI Infra / MLSys 视角

1. **推理服务的直接价值**：XSched 与 Triton 的集成仅需 10 行代码即可将高优模型 P99 延迟降低 30%，这对多模型推理服务场景非常实用。随着 LLM serving 中 prefill 和 decode 的优先级调度需求增加，XQueue 抽象可以自然地映射到这一场景。

2. **与现有 GPU 共享方案的互补**：XSched 在 GPU harvesting 场景中显著优于 TGS（2.74× 资源收割提升），说明细粒度抢占对 GPU 多租户共享有实质帮助。可以探索将 XSched 与 MIG/MPS 等空间复用方案结合，实现时间+空间的联合调度。

3. **NPU 调度的先行者价值**：XSched 是首个在 NPU 和 ASIC 上实现软件抢占式调度的系统。随着端侧 AI（AI PC、手机 NPU）的兴起，NPU 多任务调度将成为关键问题，XSched 的 XQueue 抽象和多级模型为后续工作奠定了基础。

4. **可操作的跟进方向**：
   - 将 XQueue 抽象扩展到 LLM serving 中的 KV cache 管理——抢占时保存/恢复 KV cache 状态
   - 结合 XSched 的调度框架和 memory oversubscription 系统（如 vLLM 的 PagedAttention），实现计算+内存的联合抢占调度
   - 探索在分布式训练中利用 XQueue 实现跨节点 GPU 资源的弹性调度

---

## 八、总结

XSched 提出了 XQueue 可抢占命令队列抽象和三级硬件模型，首次实现了跨 GPU、NPU、ASIC、FPGA 的通用抢占式调度框架。其核心贡献在于通过分层硬件模型优雅地处理了不同 XPU 能力差异的问题——弱设备获得基本抢占支持，强设备发挥高级硬件能力。系统已适配 10 种 XPU、7 个软件平台，在多个实际场景中展现了显著的调度收益。主要局限在于高级抢占（Lv3）依赖未文档化接口且受限于幂等 kernel 要求，内存管理的缺失也限制了其在内存紧张场景下的适用性。项目已开源于 https://github.com/XpuOS/xsched。
