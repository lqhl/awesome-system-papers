---
type: paper
name: CoPilotIO
full_title: "CoPilotIO: CPU as a Co-pilot for GPU I/O to Free GPU Compute"
authors: [Guanyi Chen, Qi Chen, Shu Yin, Jian Zhang]
venue: OSDI
year: 2026
tags: [gpu-io, storage, nvme, asynchronous-io, gpu-compute]
source_pdf: "[[osdi26-chen-guanyi.pdf]]"
source_md: "[[osdi26-chen-guanyi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# CoPilotIO：让 CPU 协助 GPU 完成 I/O（OSDI 2026）

> **原题**：CoPilotIO: CPU as a Co-pilot for GPU I/O to Free GPU Compute

> **一句话总结**：GPU-centric I/O 为了获得按需访问而让 GPU 持续轮询 NVMe 完成队列，造成 warp 调度和显存争用；CoPilotIO 让 GPU 写入 submission queue、CPU 在用户态轮询 completion queue，再用硬件 barrier 唤醒等待的 warp，在四块 SSD 上以 24 个 SM 饱和约 25 GB/s PCIe 带宽，并在 DLRM 推理中比 BaM 快 1.85×。

## 问题与动机

GPU 应用的数据集和模型状态已超过单卡 HBM 容量，需要从 NVMe 存储持续获取数据。CPU-centric 方案如 GDS 不占用 GPU 计算资源，却受内核 I/O 路径和 CPU 并行度限制；GPU-centric 方案如 BaM 支持 GPU 发起的细粒度按需 I/O，但把 NVMe 命令提交、完成处理和轮询都放到 GPU 上。

作者指出，GPU 轮询不只是消耗少量线程。等待完成的 warp 会产生 intra-warp stall；持续处于 ready 状态的轮询 warp 会挤占同一 SM 上的计算 warp；位于 GPU 显存的完成队列还会与应用访存争用，形成 inter-SM stall。CoPilotIO 的目标是在保留 GPU 按需发起 I/O 的同时，把 I/O 进度从 GPU 计算路径中移开。

## 关键观察 / 隐含假设

- **观察 1：GPU 轮询造成三层 stall。** BaM 中 intra-warp stall 最多增加至 CoPilotIO 的 1.87×，与计算 warp 共运行时执行时间最多增加 1.71×；在重显存争用下，I/O 带宽最多下降 50.6%（图 2、图 6）。
  - **依赖假设**：应用中的 I/O 等待与计算存在可重叠部分，释放出来的 warp 调度资源能转化为有效计算。
  - **可能失效场景**：纯计算负载或几乎没有并行计算可重叠时，消除轮询对端到端时间的收益有限。
- **观察 2：CPU 用户态轮询可以达到设备带宽，但 CPU 并行度对小 I/O 不足。** 16 个 CPU 线程在请求大于 16 KB 时可使单 SSD 接近饱和；4 KB 等小请求需要更高轮询速率，CPU-only 配置会成为瓶颈（图 3a、图 9）。
  - **依赖假设**：服务器能够预留若干 CPU 核心作为 I/O polling agent。论文的稳定中等负载配置通常需要 4–8 个核心。
  - **可能失效场景**：CPU 被其他服务占满或请求突发超过自适应机制反应速度时，完成处理会积压。
- **观察 3：控制队列的跨 PCIe 访问成本相对数据搬运可接受。** SQ 放在 GPU memory、CQ 放在 CPU memory 时，GPU 对小型 CQ entry 的 zero-copy 访问不会明显限制 NVMe 吞吐（图 3b）。这一结论依赖 CQ entry 很小，不能直接外推到大控制元数据或不同互连拓扑。

## 核心方法

CoPilotIO 由 GPU 侧 CoPilot-GPUIOLib 和 CPU 侧 CoPilot-CPUIOLib 组成。GPU 应用调用 POSIX-like 的 `async_read`/`async_write`，把 NVMe 命令写入 GPU-resident SQ 后立即继续执行；CPU 侧库采用 SPDK-like 用户态队列，绕过内核处理 SQ/CQ 和 DMA。

论文将 CQ 放在 CPU memory，将完成检测交给 CPU。每个请求分配 command ID（cid）和一个 CUDA `cuda::barrier`，GPU 把二者写入共享的 lock-free barrier table。CPU 轮询 CQ 读到 cid 后查表并触发对应 barrier，等待数据的 GPU warp 被挂起，硬件调度器可以运行其他 ready warp。该设计回应观察 1，避免了应用 warp 自旋，也避免 GPU 显存中的 CQ 轮询流量与应用访存竞争。

CPU 核心不足时，CQ-based adaptive CPU-GPU co-polling 根据每个 CQ 的 pending entry 数量在 CPU 和 GPU 间分配新请求。超过高阈值后启用 GPUAgent，低于低阈值后切回 CPU；CPUAgent 不必停止，两个 agent 分别轮询独立 CQ。GPUAgent 每个 SM 只使用一个可唤醒的 polling warp，而不是让每个 I/O warp 自己轮询，从而降低 GPU 轮询的调度干扰。

## 设计取舍

- **取舍 1：跨设备同步换取 GPU 计算资源。** CPU 需要持续占用若干核心，系统还依赖 pinned CPU memory、zero-copy 访问和 CUDA hardware barrier；收益是 GPU 不再承担常态 CQ polling。
- **取舍 2：自适应方案保留 GPU 轮询作为退路。** 高 IOPS 下 GPUAgent 能补足 CPU 并行度，但一旦启用就重新引入部分 GPU 资源消耗和 PCIe 访问压力。论文未给出跨 NUMA、不同 PCIe 拓扑或多租户隔离下的迁移成本。
- **边界条件**：细粒度、I/O 与计算交错、GPU SM 压力高的工作负载最适合该设计；纯计算或大块顺序传输中，轮询开销本来较小，收益可能不明显。

## 实验与结果

- 在 stall 微基准中，CoPilotIO 相比 BaM 将 inter-warp stall 最多降低 18.6%，并在增加计算 warp 的情况下保持 I/O 带宽，而 BaM/AGILE 在重显存争用下最多下降 50.6%（图 6）。
- 4 KB 随机读写的纯 I/O 测试中，CoPilotIO 在吞吐和延迟上均超过 BaM 与 AGILE（图 7、表 2）；论文使用 A100/H800、四块 Samsung 990 Pro NVMe SSD，PCIe 4.0 x16 上限约 25 GB/s。
- 在动态 IOPS 负载下，自适应 polling 比 CPU-only 更稳定；高负载时 GPU 接管更多 CQ，CPU 活跃 polling 核心可由最多 16 个降至 3–4 个，稳定中等负载通常为 4–8 个（图 9）。
- 四块 SSD、8 KB 随机读下，CoPilotIO 以 24 个 SM 饱和 25 GB/s；BaM 和 AGILE 需要超过 72 个 SM（图 10a）。
- 集成 GoFS 后，4 KB 随机读性能比 BaM 最多提高 17.4%，改动少于 20 行（图 10b）。FlashMoE 的 SSD expert-weight offload 中最高加速 1.44×；DLRM 推理中比 BaM 加速 1.85×，比 AGILE 的 1.41× 更高（图 11）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| CPU 负责完成轮询可以消除 GPU 侧三类 I/O stall | §3、§5.2、图 2、图 6 | A100/H800，合成混合 I/O-计算负载 | 强 |
| 分离 SQ/CQ 不牺牲 I/O 吞吐 | §3、§5.2.2、图 3b、图 7、表 2 | 4 KB 随机读写，四块 PCIe 4.0 SSD | 中 |
| 自适应 co-polling 能应对 CPU 并行度不足 | §4.5、§5.3、图 9 | 人工构造的随时间变化 IOPS 负载 | 中 |
| 节省的 SM 能转化为应用性能 | §5.5–§5.6、图 10b、图 11 | GoFS、合成 FlashMoE、Criteo DLRM 配置 | 强 |

## 批判性分析

### 论证链条

论文的主链条较完整：GPU CQ polling 导致 stall，将 CQ 放到 CPU memory 可减少显存争用，CPU 用户态 polling 可承担完成处理，硬件 barrier 可把完成通知传回 GPU。实验分别覆盖 stall、纯 I/O、扩展性和应用集成，能够支持“减少 GPU I/O 干扰”的结论。

自适应机制的必要性也有测量支撑，但阈值和 batch size 的选择没有充分敏感性分析。GPUAgent 仍然是 GPU polling，只是集中到每个 SM 一个 warp；因此“消除 stall”应理解为常态 CPU polling 下的消除，而不是所有负载下的绝对消除。

### 假设压力测试

CoPilotIO 假设 GPU 通过 PCIe 访问 CPU-resident CQ 的延迟和带宽足以处理小型控制项。该假设在所测 A100/H800 和 PCIe 4.0 x16 上成立，但论文未覆盖 CXL、NVLink、PCIe 5/6、NUMA 远端 DRAM 或虚拟化环境。CPU polling 还依赖专用核心和用户态 NVMe 管理权限，多租户云环境可能改变这一成本模型。

对 MoE 的评测使用 2,048 个专家、固定维度和合成访问配置；DLRM 使用单一 Criteo 配置。不同 expert 热度分布、SSD 错误、缓存命中率和更大 GPU 集群的结论仍需测量。

### 实验可信度

BaM 和 AGILE 是合适的 GPU-centric 对照，GDS 只在其支持的随机读场景中比较。GoFS 与 DLRM 展示了混合 I/O-计算收益，但 AGILE 无法运行 GoFS 和 MoE，导致应用层对照不完整。论文报告了吞吐、延迟、SM 数和端到端时间，却没有系统评估 CPU 能耗、尾延迟、故障恢复、隔离或多租户干扰。

### 系统性缺陷

实现约 5K 行，依赖 CUDA hardware barrier、GDRCopy 备用路径、用户态 NVMe 队列和 pinned memory。论文提到 NVMe I/O 错误时会设置 error flag 并回收 cid，但没有实验验证 SSD reset、CPUAgent 崩溃、进程退出或 barrier 泄漏后的恢复流程。自适应迁移也以 CQ pending count 为主要信号，可能无法区分 SSD 服务时间变化、CPU 抢占和应用请求模式变化。

## 局限与后续工作

- **局限 1**：CPU 侧 polling 的核心占用和特权配置会增加部署成本；CPU 资源极度紧张时只能启用 GPUAgent，收益会退化。
- **局限 2**：评测集中在单机、PCIe 4.0、四块 NVMe SSD；跨 NUMA、多 GPU、容器隔离和更新硬件互连的可扩展性未验证。
- **后续工作 1**：在 CPU oversubscription、NUMA 远端 CQ、SSD 延迟抖动和多租户并发下测量 P99 I/O 与端到端延迟，并评估阈值策略是否需要以尾延迟而非 pending count 为信号。
- **后续工作 2**：测试 CPUAgent 故障、NVMe reset 和进程恢复，验证 cid/barrier 生命周期在异常路径上的一致性。

## 相关

- **相关概念**：[[GPU I/O]]、[[NVMe]]、[[Asynchronous I/O]]、[[Zero-Copy]]
- **同类系统**：[[BaM]]、[[AGILE]]、[[GoFS]]、[[GPUDirect Storage]]
- **同会议**：[[OSDI-2026]]
