# Accelerating Model Loading in LLM Inference by Programmable Page Cache

**作者**：Yubo Liu, Hongbo Li, Xiaojia Huang, Yongfeng Wang, Hanjun Guo, Hui Chen, Yuxin Ren, Ning Jia（华为技术有限公司）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/liu-yubo
**源文件**：[[fast2026-liu-yubo.pdf]]

---

## 一、背景

LLM 推理服务的启动延迟是 MaaS（Model-as-a-Service）系统中的关键性能指标，直接影响服务 QoS 和资源利用率。随着模型规模持续增长（数百 GB 甚至 TB 级），模型加载成为推理服务启动的主要瓶颈。例如，在华为 MaaS 平台上冷启动 DeepSeek-R1-671B 推理服务需要约一小时，其中模型加载占总开销 70% 以上。

当前主流做法是将热模型存储在推理节点的高速 SSD 上，但内核文件系统的默认缓存策略无法充分利用 SSD 带宽。现有优化方案（如 ServerlessLLM、BlitzScale）虽然提升了性能，但以牺牲兼容性为代价——依赖定制化推理框架修改、特定硬件互联（NVLink、RDMA）或自定义模型格式，难以在多样化的生产环境中广泛部署。

---

## 二、要解决的问题

1. **SSD 带宽利用不足**：内核原生预取策略仅预取与触发 I/O 同文件的连续小段数据（约 128KB），受 kworker 数量限制，无法利用 SSD 的高并发能力。实测模型加载阶段平均带宽仅为峰值的 17%。

2. **XPU 亲和性未被利用**：内核缓存策略不感知数据的目标 XPU，预取的数据被盲目加载到 kworker 所在的 NUMA 节点，导致 host-to-device 传输效率低下。测试表明 NUMA 亲和性加载可减少约 20% 的模型加载延迟。

3. **驱逐策略无法感知时间局部性**：模型数据一旦加载到 XPU HBM 后，host 侧缓存即可释放。但内核基于采样和 LRU 的驱逐策略无法检测数据何时已被传输到 XPU，导致无效数据未及时驱逐，在内存受限场景下引发严重的 cache thrashing。

4. **兼容性约束**：优化方案需同时满足三个维度的兼容性——对推理框架/模型格式透明、不侵入式修改 OS 内核、不依赖特定硬件。

---

## 三、洞察与设计

**关键洞察**：相同 LLM 推理服务（相同模型、tensor parallelism 等运行时参数）的模型加载 I/O 模式是可复现的。利用这一特性，可以为每种推理服务预构建 I/O 模板，从而在不修改推理框架的前提下精确感知 I/O 行为，实现自适应的缓存优化。

基于这一洞察，论文设计了两层系统：

**PPC（Programmable Page Cache）框架**：一个可编程的内核页缓存框架，由两个核心组件构成：
- **RFS（Routing File System）**：一个只读的堆叠文件系统，作为独立内核模块挂载在现有文件系统之上。它劫持底层文件系统的 cache miss 流程，将 miss 事件封装后通过 UPC（Userspace Procedure Call）机制以非阻塞方式传递到用户空间。RFS 提供标准 POSIX 语义，应用无需修改。
- **CPRT（Cache Policy Runtime）**：用户空间的策略运行时，提供类 VFS 的编程接口（`ppc_init`、`ppc_exit`、`ppc_prefetch`、`ppc_evict`），用户通过编译动态库并注册来自定义缓存策略。CPRT 维护线程池监听 RFS 事件，并通过 cache manager 高效执行预取和驱逐操作。

**MAIO（Model-Accelerated I/O）**：基于 PPC 实现的模型加载优化缓存策略，包含三个关键机制：
1. **Interruptible Prefetching**：利用 I/O 模板中的序列信息，从 cache miss 位置开始激进预取到 I/O group 末尾。当前端 I/O 超过预取进度时，中断旧的预取请求并从新位置重新开始，避免冗余加载。
2. **XPU Affinity Loading**：通过 I/O 模板中的 Worker ID 到 XPU 的映射关系，将预取数据加载到目标 XPU 所在的 NUMA 节点，提升 host-to-device 传输效率。
3. **Burn-after-Reading（BAR）Eviction**：维护驱逐游标，将 miss I/O 位置之前（保持 1GB 安全距离）的已使用数据及时驱逐，精确利用模型加载的时间局部性。

---

## 四、实现细节

**RFS 实现**：
- 利用 Linux 堆叠文件系统机制（类似 OverlayFS），通过重写 VFS 接口劫持底层文件系统操作
- VFS 数据结构（superblock、inode、file、dentry）通过自定义字段（如 `i_private`、`private_data`）记录与底层文件系统结构的映射
- UPC 通过每个 RFS 实例创建的虚拟字符设备实现，用户空间通过 `poll`/`epoll` 获取事件，采用 per-core 队列（基于 xarray）提高并发性能
- 通过系统配置禁用 VFS 原生预取/驱逐机制

**CPRT 实现**：
- 用户策略编译为动态库（`.so`），通过 `dlopen` 加载，支持运行时热切换策略
- Cache Manager 的 loader 维护 core-bound 线程池充分利用 SSD 并发；evictor 使用 `fadvise`（`POSIX_FADV_DONTNEED` flag）通知内核释放目标页
- 预取支持可中断：内存不足、I/O 带宽不足、新预取请求触发时可中断当前预取

**MAIO I/O 模板**：
- 模板按推理服务粒度生成，以服务运行时参数（模型名、TP size、PD size 等）的哈希值作为 service ID
- 模板按 XPU Worker 分组，每组记录 I/O 序列（文件路径、offset、size）
- 模板存储为文件（可放在本地或 NFS 共享），DeepSeek-R1-671B 级模型的模板仅 545KB
- 首次运行时自动生成模板（通过特殊的 `ppc_prefetch` 实现跟踪 I/O 但不执行预取）

**集成方式**：PPC 运行在宿主机 OS 上，MaaS 控制面通过 PPC API 管理 MAIO 的启停，MAIO 实例与目标推理服务在同一 cgroup 中运行。

---

## 五、实验结果

**测试平台**：4 × Kunpeng 9205250 CPU（48 核 @2.6GHz）、8 × Ascend 910B2 NPU、1TB DRAM、3.75TB SSD。软件栈：vLLM-Ascend 0.9.2、PyTorch 2.5.1、Linux 5.10。

**基线**：Native（内核原生策略）、EagerLoad（首次 I/O 触发后一次性预取全部模型）、PreCache（预缓存整个模型到内存）、SLLM-NPU（ServerlessLLM 的 NPU 适配版本，不兼容优化）。

### 模型加载延迟

| 场景 | 对比基线 | MAIO 改进 |
|------|---------|-----------|
| 内存充足 | vs. Native | 最高降低 79% |
| 内存充足 | vs. EagerLoad | 最高降低 32% |
| 内存充足 | vs. PreCache | 最高降低 37% |
| 内存充足 | vs. SLLM-NPU（不兼容） | 最高降低 17% |
| 内存受限（64GB） | vs. 其他所有方案 | 最高降低 74% |

### 推理启动端到端延迟

| 场景 | MAIO vs. Native |
|------|-----------------|
| 内存充足 | 最高降低 38% |
| 内存受限 | 最高降低 51% |

### PPC 开销

| 指标 | 数值 |
|------|------|
| 读吞吐开销（memcpy-after-mmap） | EXT4 上最高 3.7%，XFS 上最高 6.4% |
| 内存开销 | 约 30MB（不随并发显著增长） |
| CPU 开销（UPC 事件监听） | 1%–11%（随并发变化） |

### 性能分解（Qwen2.5-72B）

| 设计 | 内存充足场景贡献 | 内存受限场景贡献 |
|------|----------------|----------------|
| Interruptible Prefetching | >65% 延迟下降 | >47% 延迟下降 |
| XPU Affinity Loading | 额外 >8.5% | 额外 ~6% |
| BAR Eviction | 几乎无影响 | 额外 ~19% |

### 真实工作负载（弹性部署）

在 MaaS 弹性部署场景中，MAIO 相比 Native 在内存充足/受限场景分别提升最高 13%/28% 的推理吞吐量。在 Intelligence BooM 生产环境中，DeepSeek-R1-671B 冷启动模型加载从 649s 降至 452s，甚至优于全量缓存到 DRAM 的 561s。

---

## 六、批判性分析

1. **BAR 安全距离的经验值问题**：BAR eviction 的 1GB 安全距离是经验值，论文仅声称"在我们验证过的场景下不会引发 cache thrashing"，但未分析这个值如何随模型结构、并行策略、I/O 并发度变化。对于极端场景（如模型权重碎片化严重或并行度很高的情况），这个固定距离是否仍然安全并不清楚。

2. **I/O 模板的可复现性假设过于理想**：论文核心假设是相同推理服务的 I/O pattern 完全相同，但实际生产中推理框架可能因版本更新、动态优化、lazy loading 策略变化等导致 I/O 行为漂移。论文未讨论模板失效检测和自动刷新机制，仅提到 MaaS 平台可以在规格变更时重新生成模板。

3. **实验硬件的单一性**：所有实验均在华为 Ascend NPU + Kunpeng CPU 平台上完成，论文虽声称"hardware-agnostic"，但未在 NVIDIA GPU 平台上验证。SLLM-NPU 作为唯一的不兼容基线，其适配质量存疑（论文提到"由于适配难度高存在 bug，只能使用 Transformers 运行"），这使得与不兼容方案的对比公平性打折扣。

4. **内存充足场景下的实际价值有限**：在内存充足场景下，MAIO 相比 PreCache 和 EagerLoad 的端到端启动优势仅约 6.6%，主要差异来自 XPU affinity 而非核心的预取/驱逐机制。论文的主要价值集中在内存受限场景，但这个场景的普遍性需要更多生产数据支撑。

5. **多实例资源竞争未解决**：论文承认多个 MAIO 实例同时运行时的资源竞争问题，对于容器化场景依赖 cgroup QoS，对于裸金属场景留作 future work。但在弹性部署场景中，多服务并行启动是常态，这个未解决的问题可能显著影响实际效果。

6. **只读文件系统的局限性**：RFS 当前只支持只读操作，论文声称"可以轻松扩展到写操作"，但对于涉及模型检查点写入、KV cache offloading 等场景的适用性未做讨论。

---

## 七、AI Infra / MLSys 视角

**启发价值**：
- **文件系统层优化的新思路**：相比传统的在推理框架层做模型加载优化（如 ServerlessLLM 修改加载逻辑），PPC 提供了一个更底层但兼容性更强的优化路径。这种"对上层完全透明"的设计哲学值得借鉴——在 AI Infra 的工程实践中，兼容性往往是决定技术能否落地的关键因素。

**可迁移的技术点**：
- **I/O 模板**的思想可推广到更多场景：分布式训练的 checkpoint 加载、模型服务的 live migration、LoRA adapter 的动态切换等，凡是 I/O 模式可预测的场景都可受益。
- **可编程缓存策略框架**（PPC）是一个通用的系统抽象，不仅适用于模型加载，还可用于 KV cache offloading to SSD、训练数据预取等 AI workload 的 I/O 优化。

**值得跟进的方向**：
1. **PPC + 分布式文件系统**：论文提到 PPC 可扩展到 Lustre、Ceph 等分布式文件系统，将 MAIO 的模板机制应用于模型仓库的远程加载是一个有价值的方向。
2. **动态模板生成与自适应**：当前 I/O 模板是静态的，结合运行时 profiling 实现模板的在线更新和自适应调整，可以处理推理框架行为漂移的问题。
3. **与 PD 分离架构的深度集成**：在 Prefill-Decode 分离部署中，Prefill 和 Decode 节点的模型加载 pattern 不同，MAIO 的模板机制天然可以为两者分别优化。
4. **推广到 checkpoint loading**：分布式训练中的 checkpoint 恢复与模型推理加载有类似的 I/O 特征（大文件顺序读、NUMA 亲和性需求），PPC/MAIO 的设计可以直接复用。

---

## 八、总结

PPC/MAIO 通过在文件系统层实现可编程的页缓存策略来加速 LLM 推理的模型加载，核心创新在于利用推理服务 I/O 模式的可复现性构建 I/O 模板，实现精准的预取、NUMA 亲和性加载和 Burn-after-Reading 驱逐。系统在保持对推理框架、OS 内核和硬件的完全兼容性的同时，在内存充足和受限场景下分别实现了最高 79% 和 74% 的模型加载延迟降低。主要局限在于 I/O 模板的静态假设、仅在华为平台上验证、以及多实例资源竞争问题未充分解决。适用于大规模 MaaS 弹性部署等需要频繁冷启动推理服务的场景。
