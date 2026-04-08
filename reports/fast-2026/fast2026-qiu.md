# RosenBridge: A Framework for Enabling Express I/O Paths Across the Virtualization Boundary

**作者**：Shi Qiu (XMU), Li Wang (KylinSoft), Jianqin Yan (XMU), Ruofan Xiong (XMU), Leping Yang (SJTU), Xin Yao (Huawei), Renhai Chen (Huawei), Gong Zhang (Huawei), Dongsheng Li (NUDT), Jiwu Shu (THU), Yiming Zhang (SJTU & XMU)
**会议**：FAST 2026
**链接**：https://www.usenix.org/conference/fast26/presentation/qiu
**源文件**：[[fast2026-qiu.pdf]]

---

## 一、背景

随着高性能 NVMe SSD 的出现（百万级 IOPS、微秒级延迟），存储硬件性能已不再是瓶颈，软件栈开销成为 I/O 性能的主要制约因素。为缩短计算与数据之间的距离，学术界提出了多种基于 near-data processing (NDP) 的 express I/O path 优化方案，如 XRP（基于 eBPF 的 I/O resubmission）和 GDS（GPU Direct Storage）。

然而，虚拟化是云计算的基石。在 KVM/QEMU 虚拟化环境中，guest VM 只能感知 hypervisor 提供的虚拟 I/O 设备（如 virtio-blk），无法直接使用底层物理设备。这意味着所有 bare-metal 上的 NDP express I/O path 都无法穿越虚拟化边界，VM 内的应用无法从这些优化中受益。实测表明，virtio-blk 的 4KB 随机读延迟中，软件开销高达 87%；VM 完成相同吞吐量所消耗的 CPU 资源是物理机的 5-7 倍。

---

## 二、要解决的问题

1. **NDP express I/O path 无法穿越虚拟化边界**：现有 XRP、GDS 等方案依赖在 host kernel NVMe driver 中插入 hook，guest VM 内的应用完全无法使用。
2. **Guest 侧 NDP 效果有限**：即使在 guest 的 virtio frontend driver 中实现 NDP，I/O 仍需经过 host 完整存储栈和代价高昂的 VM-exit 上下文切换，优化空间非常有限。
3. **语义鸿沟**：guest 感知的内存地址（GVA/GPA）和磁盘块地址被 hypervisor 重映射，offload 到 host 的 NDP 程序无法直接操作 guest 的地址空间。
4. **安全与公平性**：将 guest 的 BPF 程序 offload 到 host 执行存在安全风险；NDP 引入的新 I/O 路径可能绕过 QEMU 的 rate limiting，破坏多租户间的 QoS 保证。

---

## 三、洞察与设计

**关键洞察**：将 NDP 优化 offload 到 host 用户态（QEMU 进程中）而非 host kernel，既能消除虚拟化边界带来的多次存储栈遍历和 VM-exit 开销，又比 offload 到 kernel 更安全——uBPF 在用户态沙箱中运行，天然继承了进程级隔离，不会威胁 host kernel 安全。

基于这一洞察，RosenBridge 的核心设计包括：

1. **virtio-ndp 设备**：扩展 virtio-blk 协议，新增 BPF 语义，允许 guest 通过 ioctl 接口将 BPF 程序加载到 host QEMU 中。提供 `read_nd`/`write_nd` 系统调用扩展，支持携带额外 metadata buffer。

2. **io_uring-based NDP I/O Scheduling**：在 io_uring 的 SQ（提交）和 CQ（完成）路径上各插入一个 uBPF hook point，支持两种 NDP 模式：
   - **On-path processing**（SQ hook）：I/O 提交前修改数据/地址，用于 GDS 等场景
   - **Content-based I/O resubmission**（CQ hook）：I/O 完成后根据数据内容决定是否 resubmit，用于 XRP 等场景
   - 结合 io_uring passthrough 直接与 NVMe driver 交互，绕过 host kernel 大部分 I/O 栈

3. **语义鸿沟桥接**：
   - Guest-host 共享内存区域：通过 PCIe BAR 映射，guest 可直接写入 metadata，host uBPF 程序可直接读取
   - Helper functions：`BPF_disk_trans()` 和 `BPF_mem_trans()` 实现 guest 物理地址到 host 虚拟地址的转换

4. **安全与公平性保障**：
   - uBPF 在 Host Ring-3（用户态）运行，PREVAIL verifier 在加载时做静态分析
   - 内存访问范围严格限制在 `rosenbridge_md` context 内
   - 多路径协同 I/O 限流：复用 QEMU 的 Leaky-Bucket 算法，确保 uBPF 路径的 I/O 也受到 quota 控制

---

## 四、实现细节

- **virtio 协议扩展**：扩展 `virtio_blk_outhdr` 头部，新增 `bpf_fd`、`buf`、`len` 字段；增加 `VIRTIO_BLK_T_LOAD`、`VIRTIO_BLK_T_READ_ND`、`VIRTIO_BLK_T_WRITE_ND`、`VIRTIO_BLK_T_UNLOAD` 四种请求类型
- **BPF 程序注册流程**：guest kernel 分配内存区域 → 拷贝 BPF 文件 → 构造 LOAD 类型 virtio 请求 → QEMU backend 拷贝并经 PREVAIL 验证 → uBPF_load 加载 → 返回 bpf_fd
- **uBPF helper functions**：
  - `BPF_uring_get_sqe()`：获取当前 SQE 副本
  - `BPF_uring_get_new_sqe()`：获取新 SQE 用于 I/O resubmission
  - `BPF_uring_set_sqe()`：修改 SQE 条目，透明替换文件/块地址为 NVMe 块地址
  - `BPF_disk_trans()`/`BPF_mem_trans()`：地址转换
- **新 BPF 类型**：`BPF_PROG_TYPE_ROSENBRIDGE`，context 为 `rosenbridge_md` 结构（meta/data 指针及边界）
- **I/O passthrough**：利用 io_uring passthrough 在 uBPF 与 NVMe driver 间建立直接 I/O 通道
- **两个 use case 实现**：
  - RosenXRP：BPF 程序挂载在 CQ hook，每次 I/O 完成后检查结果、做两步地址转换（metadata_digest + BPF_disk_trans）、resubmit
  - RosenGDS：BPF 程序挂载在 SQ hook，查询共享内存中的 GPU buffer mapping、用 BPF_mem_trans 转换地址、启用 P2P DMA

---

## 五、实验结果

**实验平台**：双路 64 核 CPU、512GB 内存、Intel Optane P5800X SSD、48GB GDDR6 GPU（VFIO passthrough）、Ubuntu 20.04、Linux v6.1.0、QEMU 7.1.50

### RosenXRP（Key Lookup）

| 配置 | 吞吐量提升 (vs virtio-blk) | 平均延迟降低 | CPU/KOPS 占比 |
|------|---|---|---|
| RosenXRP vs virtio-blk | +461.8% | -82.1% | 14.73% |
| RosenXRP vs vhost-kernel-blk | +243.5% | -70.7% | 28.69% |
| RosenXRP vs vhost-user-blk | +102.1% | -49.4% | 41.85% |
| RosenXRP vs bare-metal XRP | 65% 带宽，+55% 延迟 | — | — |

### RosenXRP（Range Query）

- 随着 range size 增大，RosenXRP 性能逐渐接近 bare-metal XRP（因 resubmission 时间占比增大，虚拟化开销占比下降）
- CPU 消耗仅为 virtio-blk 的 10.19%

### RosenGDS

| 指标 | RosenGDS vs virtio-blk | RosenGDS vs bare-metal GDS |
|------|---|---|
| 延迟 | 降低 27.5%–56.4% | 高约 30% |
| CPU 利用率 | 降低 ≥35.2% | — |
| 带宽（4 线程） | 更高（小块 I/O） | 低约 26% |
| CPU（带宽饱和时） | 仅 45.2%–79.7% | — |

### I/O Throttling

- 未启用限流时，XRP VM 导致同机 virtio-blk VM 带宽降至配额的 30%
- 启用 RosenBridge 多路径限流后，两个 VM 均维持在配额附近

---

## 六、批判性分析

1. **Use case 过窄**：仅展示了 XRP 和 GDS 两个 use case，且它们的工作负载模式比较特定（B-tree lookup 和 GPU DMA）。论文声称框架通用、覆盖 SNIA CSD 的 direct/indirect 模型，但缺乏更多样化的 NDP 场景验证（如压缩、加密、数据预处理等）。

2. **与 bare-metal 差距被轻描淡写**：RosenXRP 相比 bare-metal XRP 仅达到 65% 带宽、延迟高 55%，这个差距不小。论文将此归因为"固有的虚拟化开销"，但未深入分析哪些开销是可以进一步优化的，哪些是本质不可避免的。

3. **安全分析不够深入**：论文强调 uBPF + PREVAIL verifier 的安全性，但 PREVAIL 是一个第三方开源项目，其成熟度和安全保证是否与 Linux 内核 eBPF verifier 相当？论文未讨论 PREVAIL 自身可能存在的漏洞或已知限制。

4. **可扩展性验证不足**：所有实验仅在单 VM 或少数 VM 场景下完成。在高密度多租户场景（数十甚至上百 VM 共享同一物理 SSD）下，共享 io_uring、多路径限流的性能和公平性表现未知。

5. **io_uring passthrough 的前提条件**：方案依赖 io_uring passthrough（Linux 5.19+引入），但论文使用的是 Linux v6.1.0。这一特性在早期版本中可能不够稳定，且论文未讨论与不同内核版本的兼容性。

6. **实验硬件单一**：仅使用 Intel Optane P5800X（极低延迟 SSD）。在更常见的 TLC/QLC NVMe SSD 上，软件栈开销占比可能不同，RosenBridge 的收益可能有所变化。

---

## 七、AI Infra / MLSys 视角

1. **GPU Direct Storage 在虚拟化环境的实用价值**：RosenGDS 使得 VM 中的 AI 训练/推理应用能直接从 NVMe SSD 做 P2P DMA 到 GPU 显存，跳过 CPU 和主存的中转。这对云上大规模 DL 训练（如 checkpoint loading、数据集加载）有直接意义，尤其是云厂商的本地盘实例（AWS I3/P5、Azure Lsv3、阿里云 I3）。

2. **DPU 集成方向值得关注**：论文 future work 提出将 RosenBridge 与 DPU 结合，使 DPU 上的存储程序发起的 I/O 直接传输到 GPU HBM，跳过 host CPU 和内存。这与当前 AI Infra 中"计算-存储-网络"分离卸载到 DPU 的趋势高度契合。

3. **可迁移的 insight**：uBPF 在用户态提供可编程 NDP 执行环境的思路，可以扩展到 AI Infra 的其他场景：
   - Checkpoint I/O 优化：训练框架可 offload checkpoint 的序列化/反序列化逻辑到存储路径
   - KV cache offloading：推理场景中 KV cache 的 SSD swap 可利用类似的 I/O resubmission 机制减少延迟

4. **局限性**：当前 RosenBridge 仅支持块设备 I/O 粒度的 NDP，对于 AI 训练中常见的大文件顺序读（数据集加载）和大块 checkpoint 写入，block-level NDP 的收益可能有限；更需要的是 file-level 或 object-level 的优化。

---

## 八、总结

RosenBridge 是首个支持 NDP 优化的 express I/O path 穿越虚拟化边界的框架。其核心思路是引入 virtio-ndp 设备，将 guest 的 uBPF NDP 程序 offload 到 host 用户态 QEMU 中执行，结合 io_uring passthrough 实现高效 I/O 调度，通过共享内存和 helper functions 桥接 guest-host 语义鸿沟。在 XRP 和 GDS 两个 use case 上，RosenBridge 大幅优于 virtio-blk/vhost 方案（吞吐量提升 100%-460%、CPU 消耗降至 10%-42%），与 bare-metal 方案的差距在可接受范围内（延迟高 30%-55%）。主要局限在于 use case 验证较窄、多租户高密度场景未充分测试。
