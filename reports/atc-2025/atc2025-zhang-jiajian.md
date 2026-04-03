# WIC: Hiding Producer-Consumer Synchronization Delays with Warp-Level Interrupt-based GPU Communications

**作者**：Jiajian Zhang (Xi'an Jiaotong-Liverpool University / University of Liverpool), Fangyu Wu (Xi'an Jiaotong-Liverpool University), Hai Jiang (Beijing University of Posts and Telecommunications), Qiufeng Wang (Xi'an Jiaotong-Liverpool University), Genlang Chen, Chaoyi Pang (NingboTech University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/zhang-jiajian
**源文件**：[[atc2025-zhang-jiajian.pdf]]

---

## 一、背景

GPU 跨设备通信在多 GPU 协作计算中至关重要，广泛应用于深度学习训练、科学模拟、图形渲染等大规模并行任务。尽管 NVLink、GPUDirect P2P、RDMA 等通信架构持续演进，但 producer-consumer 同步仍是 GPU 通信中的关键瓶颈。程序员需要手动协调 producer 数据生成和 consumer 消费的时序，通常依赖重复 polling 来检查 producer 数据的可用性，造成大量计算资源浪费。

现有优化工作主要聚焦于两类策略：inter-kernel coordination（通过调度计算 kernel 重叠同步开销）和 in-kernel coordination（在 kernel 内部实现异步数据传输）。但这些方法多侧重 producer 端优化，对 consumer 端的同步延迟关注不足。

---

## 二、要解决的问题

1. **Consumer 端延迟占主导**：实验表明 consumer 端通信延迟占比通常为 20%~50%，通信密集型应用（如 C_H3D）高达 81.97%，远超 producer 端（通常 <10%）。
2. **重复 polling 是主要开销来源**：consumer 反复 poll producer 数据可用性，polling 占 consumer 通信开销的 60%~90%，每次通信的检查次数达百万到千万量级。
3. **过早 polling 抢占计算资源**：在 GPU 环境下，consumer kernel 由大量并行线程执行，各线程完成进度不一。当 polling 提前开始时，尚未完成独立计算（C₁）的线程被迫与 polling 线程竞争计算资源，导致可执行任务停滞——这些被延误的任务本可与同步延迟重叠执行。
4. **缺乏原生跨设备信号量**：GPU API 不提供跨设备信号量，程序员只能通过 CUDA stream、event 或 flag 手动管理同步。

---

## 三、洞察与设计

**关键洞察**：在 GPU producer-consumer 模型中，当 consumer 开始 polling 时，大量线程仍在执行独立计算任务（尚未到达同步点 Tc），这些未完成的任务被 polling 抢占了计算资源。如果能将 polling 线程挂起，释放其占用的 warp 调度资源给其他可执行 warp，就能让这些未完成的计算任务与同步延迟重叠执行，从而有效隐藏同步开销。

基于此洞察，WIC 提出了 warp 级别的中断机制替代传统 polling：

- **Interrupter 模块**：当 consumer warp 请求 producer 数据时，在 UVM 中分配 PCM（Producer-Consumer Communication Medium）页面，引导 warp 访问这些页面以触发 page fault，从而挂起该 warp，释放计算资源给其他可执行 warp。使用 segment tree 管理 PCM 页面分配，时间复杂度 O(log n)。每次批量处理 16 个 warp。
- **Monitor 模块**：部署在 host 端 UVM driver 中，维护 DAB（Data Availability Bitmap）和 PFQ（Pending Faults Queue）。通过捕获 PCM fault 和 PAT（Producer Availability Tags）fault 来跟踪 producer 数据可用性。
- **Activator 模块**：在 Monitor 确认数据可用后，将 producer 数据写入 PCM 页面，发送 replay signal 重新激活被挂起的 consumer warp。同时负责回收 PCM 页面（使用 P/P' 交替方案保证连续通信流）。

整个框架集成在 UVM 上下文中，通过修改 UVM host kernel driver 实现，对程序员完全透明——请求 producer 数据的操作类似系统调用，无需手动编排 polling 同步。

---

## 四、实现细节

- **UVM 集成**：利用 UVM 的 warp stall/replay 机制——当 warp 访问不在本地设备的 UVM 页面时，UVM 系统自动 stall 该 warp 并调度其他 warp；host 端 UVM driver 可以发送 replay signal 重新激活 stalled warp。WIC 通过人为触发 UVM page fault 实现 warp 中断。
- **PCM 内存空间**：典型配置 16K 页面，可处理最多 256MB 通信数据。PCM 和 PAT 的 UVM prefetching 被禁用，防止页面被主动迁移到设备上（否则无法触发 fault）。
- **Segment tree 页面管理**：64K 树数组，每个节点维护 sum、maxLen、leftLen、rightLen 信息，支持 O(log n) 的连续空闲页面查询和状态更新。
- **双页面回收机制**：每个 PCM 页面 P 配对一个伴侣页面 P'，在通信周期中交替使用，解决 invalidation timing 问题。
- **CPU-GPU 通信**：producer 为 host 端用户进程，直接更新 DAB。
- **Inter-GPU 通信**：producer kernel 在另一 GPU 上，通过修改 host 端 PAT tag 触发 fault 来通知数据可用。
- **所有修改仅在 UVM host kernel driver 中**，无需 GPU 硬件改动。

---

## 五、实验结果

**实验平台**：
- CPU-GPU：NVIDIA RTX 4090 (24GB) + Intel 14900KF (24 cores)
- Inter-GPU：4× NVIDIA A800 (80GB) + 2× Xeon 6138 (20 cores each)

**Benchmark**：10 个应用，来自 FAIR1M、Mantevo、Comb、Polybench、Rodinia、Savina，覆盖 4 种通信访问模式（streaming、adjacent、scatter-gather、random）和 4 种通信模型（unidirectional、alternating、multiple、probabilistic）。

| 指标 | 结果 |
|------|------|
| 平均加速比 | 1.13× |
| CPU-GPU 应用加速 | C_CG、C_FE、C_H3D 超过 20%，C_H3D 超过 30% |
| Consumer 端开销降低 | 约 20%，基本与 producer 端持平 |
| 同步-计算重叠率 | WIC 平均 >80%（naive 仅约 10%）；CPU-GPU 场景达 90% |
| WIC 总开销 | 约 1.4%（consumer 端），host 端约 3% |
| 线程扩展性 | 1K~1M 线程范围内性能接近峰值 |
| 对比 SOTA | CPU-GPU 场景比 NBlocking 高 20%，比 DemandCpy 高 15%；inter-GPU 场景平均领先 15% |

**局限情况**：G_BS（Scenario 1，数据预生成）和 G_BFS（概率性通信模型）上 WIC 无明显提升或略有下降。

---

## 六、批判性分析

1. **平均加速比 1.13× 的掩盖效应**：该数字由 C_H3D（>30%）拉高，多个应用加速仅约 10%，G_BS 甚至略有性能下降（-0.02%）。对于非通信密集型应用，WIC 的收益有限。

2. **Scenario 1 下的退化问题被轻描淡写**：当 producer 数据已预生成（G_BS），WIC 反而引入额外开销（page fault + host 端处理），不如直接访问。论文承认了这一点但未深入讨论如何自动检测和切换策略。

3. **UVM fault buffer 256 限制**：论文承认 UVM 一次只能处理 256 个 fault，在大规模场景下会成为瓶颈。但 scaling 实验仅展示到 1M 线程，未探讨更大规模（如分布式多节点多 GPU）场景下的表现。

4. **实验平台代表性有限**：CPU-GPU 使用 RTX 4090（消费级），inter-GPU 使用 A800。两套平台的 UVM 实现和 NVLink 拓扑差异较大，结论的跨平台推广性不明确。论文声称 WIC 可适配 NVLink 和 Direct P2P 等架构，但仅停留在设计层面，未提供实际实验验证。

5. **Benchmark 选择偏向验证性**：10 个应用多为经典 benchmark，缺乏真实生产负载（如 DNN 训练中的 AllReduce、分布式推理的 KV cache 传输）的验证。论文提出的通信模式分类虽新颖，但未证明其分类体系在实际工作负载上的覆盖度。

6. **Host 端 3% 开销不可忽略**：在通信频繁的场景下（如 G_STN 的 3.6%），host CPU 成为潜在瓶颈。论文未讨论 host CPU 负载高时 Monitor/Activator 模块的延迟退化。

7. **与异步通信库的对比缺失**：未与 NCCL、Gloo 等主流 GPU 通信库做对比，也未讨论 WIC 如何与这些库集成。

---

## 七、AI Infra / MLSys 视角

1. **对分布式训练通信的启发**：WIC 揭示的 consumer 端 polling 瓶颈在分布式训练的 AllReduce、parameter server 场景中同样存在。Warp 级中断-恢复的思路可以借鉴到 NCCL kernel 的通信优化中——当 AllReduce 的 reduce-scatter 阶段某些 warp 在等待远端数据时，可以释放资源给本地计算 warp。

2. **推理场景的潜在价值**：在 LLM 推理的 tensor parallelism 中，各 GPU 之间的 AllReduce 通信需要同步等待。WIC 的中断机制理论上可以让等待通信的 warp 让出资源给 decode 阶段的其他计算任务，特别是在 continuous batching 场景下不同 request 的计算-通信重叠。

3. **UVM 路径的局限性**：当前 AI Infra 主流使用 GPUDirect RDMA 和 NVLink 而非 UVM 路径通信。WIC 要在 AI Infra 场景落地，需要将中断机制迁移到这些高性能通信路径上，这是一个非平凡的工程挑战。

4. **可跟进方向**：
   - 将 WIC 的 warp 级调度思想与 CUDA Graph、persistent kernel 等技术结合，减少 kernel launch 开销的同时优化 intra-kernel 同步
   - 探索在 MoE 模型的 All-to-All 通信中应用类似的中断-恢复机制
   - 研究 WIC 在 disaggregated GPU 架构（如 PCIe fabric 连接的 GPU pool）中的适用性

---

## 八、总结

WIC 提出了 warp 级中断机制替代传统 polling，通过 Interrupter/Monitor/Activator 三个模块协同工作，将 consumer 等待 producer 数据的同步延迟隐藏在其他 warp 的计算任务之后，平均加速 1.13×。该方法集成在 UVM host kernel driver 中，对程序员透明，适用于 CPU-GPU 和 inter-GPU 两种通信场景。主要局限在于依赖 UVM 路径、仅在 consumer 需要等待 producer 的场景（Scenario 2）有效、以及 UVM fault buffer 的扩展性限制。
