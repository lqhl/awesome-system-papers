---
type: paper
name: RosenBridge
full_title: "RosenBridge: A Framework for Enabling Express I/O Paths Across the Virtualization Boundary"
authors: [Shi Qiu, Li Wang, Jianqin Yan, Ruofan Xiong, Leping Yang, et al.]
venue: FAST
year: 2026
tags: [virtualization, ndp, virtio, ubpf, io-uring, gpu-direct-storage]
source_pdf: "[[fast2026-qiu.pdf]]"
source_md: "[[fast2026-qiu]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# RosenBridge: A Framework for Enabling Express I/O Paths Across the Virtualization Boundary (FAST 2026)

> **一句话总结**：在 [[virtio]]-blk 虚拟化路径上，4KB 随机读 **87%** 延迟来自软件栈、同等吞吐 VM 比物理机多耗 **498–630%** CPU——[[Near-Data-Processing|NDP]] express path（[[XRP]]、[[GPU-Direct-Storage]]）无法跨虚拟化边界；RosenBridge 用 **virtio-ndp + [[uBPF]]@QEMU userspace + [[io_uring]] 双 hook + NVMe passthrough** 把 guest NDP 程序安全 offload 到 host，RosenXRP 相对 virtio-blk 吞吐 **+461.8%**、延迟 **-82.1%**，相对 bare-metal XRP 仍有约 **35%** 带宽与 **55%** 延迟损失。

## 问题与动机

商用 [[NVMe]] SSD 已达百万 IOPS、微秒级延迟，瓶颈从设备转向 **kernel storage stack 的数据搬运与上下文切换**。基于 [[Near-Data-Processing|NDP]] 的 express I/O path——如 [[XRP]] 在 NVMe 驱动 IRQ 上挂 [[eBPF]] 做 query resubmit、[[GPU-Direct-Storage|GDS]] 做 GPU↔存储 P2P DMA——能把计算推到数据附近，短路 block/fs/syscall 层。

但云环境普遍跑在 [[KVM]]/[[QEMU]] 虚拟化之上：guest 只能看到 [[virtio]]-blk 等 paravirtualized 设备，**虚拟化边界**切断了对 host 物理盘与 NVMe 驱动的直接访问。标准路径是 guest syscall → guest 存储栈 → virtio frontend → **VM-exit** → KVM → QEMU emulate → host syscall → host 存储栈 → 设备；数据密集型 VM 可达 **70%** 执行时间与显著 CPU 花在 I/O 上。把 NDP 放进 host kernel NVMe 驱动虽性能最好，却破坏 tenant 隔离；放进 guest kernel 又无法跨越 GPA→HPA、虚拟盘→物理盘的语义鸿沟。

作者 claim：RosenBridge 是首个让 **bare-metal express I/O path 跨虚拟化边界** 的框架，在保持 [[Paravirtualization]] 灵活性的同时，接近裸机 NDP 性能。

## 关键观察 / 隐含假设

- **观察 1：virtio-blk 的软件栈开销在微秒级 NVMe 时代已主导端到端延迟，且 VM-exit/QEMU emulate 是最大单项**。
  - **证据**：4KB 随机读均值 **35.5 µs**，软件占 **87%**；其中 KVM/QEMU 段 **49.6%**（5.1 µs），guest 栈 **20.8%**，host 栈 **8.7%**（Optane P5800X，raw virtio-blk）。
  - **依赖假设**：本地盘直挂 compute（AWS I3/P5、Azure Lsv3、阿里云 I3 类部署）；块 I/O 走标准 paravirtualized 路径而非 [[VFIO]]/[[SR-IOV]] 整机 passthrough。
  - **可能失效场景**：[[SPDK]] vhost-user 等 kernel-bypass 后端已把 dataplane 下沉；网络盘/分布式存储时 host 栈占比变化；大顺序 I/O 时设备带宽而非软件栈成瓶颈。

- **观察 2：同等吞吐下 VM 的 CPU 成本是物理机的数倍，使「快盘 + 慢虚拟化栈」在 cloud 上既不经济也难扩**。
  - **证据**：达到 2/4/8 GB/s 时，VM 比物理机多耗 **498.3% / 630.4% / 581.0%** CPU（16–64KB I/O size）。
  - **依赖假设**：tenant 按 vCPU 计费、I/O 密集 workload（DB、DL checkpoint、HPC）对 CPU 配额敏感。
  - **可能失效场景**：vhost-kernel/vhost-user 已部分 offload dataplane；polling 型后端用 CPU 换延迟但引入争用（论文 Related Work 已讨论）。

- **观察 3：标准 [[eBPF]] 的 event-driven 单次触发模型不足以支撑 NDP 的 content-based I/O resubmit（如 [[XRP]] 读一块再决定下一块地址）**。
  - **依赖假设**：NDP workload 需要在 **I/O submission 与 completion** 两处插入逻辑；resubmit 链长度有限（BPF-KV B-tree depth 6）。
  - **可能失效场景**：极长 resubmit 链或复杂状态机可能触及 uBPF 指令/栈限制；需 program chaining 时 guest 要维护跨调用上下文。

- 假设 1：把 NDP offload 到 QEMU userspace（[[uBPF]] + PREVAIL verifier）比 host kernel [[eBPF]] 更适合多租户云的安全模型。
  - **证据强度**：**中**——架构论证清晰（Ring-3 沙箱、无 kernel 内存直访），有 verifier + SQE 边界检查 + throttling，但缺少对抗性 red-team 或形式化安全证明实验。

- **假设 2：Guest 应用负责 metadata 一致性（含 [[XRP]] versioning），host 侧 NDP 程序只读共享区 meta、通过 helper 做地址翻译即可正确 resubmit**。
  - **证据强度**：**中**——RosenXRP 复用 XRP metadata digest + version 比较；论文明确「guest application is responsible for ensuring metadata consistency」，未测并发文件系统变更下的 race。

- **假设 3：存储用 virtio-blk 虚拟盘、GPU 用 [[VFIO]] passthrough 代表主流云 GPU+本地盘组合（RosenGDS）**。
  - **证据强度**：**弱–中**——与阿里云/AWS GPU 实例描述一致，但未覆盖 vGPU 分片、全虚拟 NVMe、远程盘等形态。

## 核心方法

RosenBridge 核心是 paravirtualized 设备 **virtio-ndp**：guest frontend 扩展 [[virtio]]-blk 协议，backend 在 QEMU 中用 [[uBPF]] 执行 guest offload 的 BPF 程序。

**跨 CPU 边界 offload**：Guest 通过 `ioctl(BPF_HOST_ATTACH)` 把 BPF 字节码经自定义 virtio 请求（`VIRTIO_BLK_T_LOAD`）送到 QEMU 加载；`read_nd`/`write_nd` 在标准 read/write 上附加 `bpf_fd` 与 `buf2`（应用 metadata）。卸载用 `VIRTIO_BLK_T_UNLOAD`。选择 **uBPF 而非 in-kernel eBPF**，因为程序跑在 QEMU 进程（Host Ring-3），不直接触 kernel 内存，更符合云隔离。

**[[io_uring]] 双 hook 调度**：针对两类 NDP 模式——(1) on-path（[[GPU-Direct-Storage|GDS]]、压缩等，提交前改 SQE）；(2) content-based resubmit（[[XRP]] 等，完成后读数据再提交下一跳）——在修改后的 `io_uring_prep_read`（**IO_URING_SQ** hook）和 `io_uring_cqe_seen`（**IO_URING_CQ** hook）触发 uBPF。Helper `BPF_uring_get_sqe` / `get_new_sqe` / `set_sqe` 让程序读/改 SQE；返回 `RESUBMIT` 时不完成 virtio 请求而继续提交。配合 **io_uring NVMe passthrough**（[[io_uring]] passthrough），uBPF 经 passthrough 直对话 NVMe 驱动，逼近 kernel eBPF 路径延迟。

**语义桥接**：QEMU 启动时为 virtio-ndp 分配 host 内存，经 PCIe BAR 映射为 guest 可访问的 **共享 metadata 区**；`read_nd`/`write_nd` 把 guest metadata 拷入该区，QEMU 将 GPA 转 HVA 填入 `rosenbridge_md` ctx（`meta`/`data` 指针 + `_end` 边界）。`BPF_disk_trans` 把 guest 虚拟盘 offset 转 host NVMe block address；`BPF_mem_trans` 把 GPA 转 host 虚拟地址（RosenGDS 中映射 GPU HBM）。

**安全与公平**：编译期 **PREVAIL** 静态验证限制 uBPF 内存访问；运行时 `BPF_uring_set_sqe` 校验地址落在 VM 分配盘区与 ctx 内。针对 NDP 路径绕过 QEMU 常规提交、可能突破 leaky-bucket 限流的问题，设计 **multi-path collaborative I/O throttling**：在 `io_uring_enter` 前调用 QEMU `throttle_group_co_io_limits_intercept`，与标准 VM I/O 共享配额与 burst。

**Case studies**：
- **RosenXRP**：BPF 挂 CQ hook，检查查询结果 → metadata_digest → `BPF_disk_trans` → 新 SQE resubmit；保留 XRP version 机制防 stale metadata。
- **RosenGDS**：BPF 挂 SQ hook，从共享区查 phony buffer 映射，`BPF_mem_trans` 改 SQE 指针实现虚拟盘到 VFIO GPU 的 P2P DMA。

## 设计取舍

- **QEMU userspace uBPF vs host kernel eBPF**：换来 **tenant 隔离与无需改 kernel**，代价是相对 bare-metal [[XRP]]/**GDS** 仍有 **~35%** 带宽、**~30–55%** 额外延迟（每次操作至少仍要走一遍虚拟化栈）。
- **virtio-ndp 扩展 vs [[VFIO]]/[[SR-IOV]] 盘 passthrough**：保留 over-provisioning、live migration、细粒度限流等 hypervisor 管理能力；牺牲绝对性能上限与硬件依赖。
- **共享内存 metadata vs socket/hyperupcall**：低延迟、可传 guest FS 状态；代价是 **guest 必须维护一致性**，host 无法替 guest 加锁。
- **io_uring passthrough**：绕过大部分 host kernel I/O 栈；依赖 Linux 6.1+ passthrough 支持与定制 QEMU/io_uring 补丁栈，通用发行版可移植性待验证。
- **边界条件**：**本地 NVMe + KVM/QEMU + O_DIRECT** 的 I/O 密集场景最优雅；远程/副本/storage service 抽象、非块设备 API（如分布式 FS）、纯 vGPU 无 VFIO 时 RosenGDS 路径不直接适用；多 VM 干扰需开启 throttling（论文已验证）。

## 实验与结果

**Setup**：双路 64 核、512GB RAM、Ubuntu 20.04 + Linux **6.1**、QEMU **7.1.50**、Intel Optane **P5800X**、NVIDIA L40S（VFIO 进 VM）；guest 同内核；`O_DIRECT`。

**RosenXRP**（BPF-KV，100 万 ops，B-tree 6 层）：
- Key lookup：相对 **virtio-blk** 吞吐 **+461.8%**、均延迟 **-82.1%**；相对 **vhost-kernel-blk** **+243.5%** / **-70.7%**；相对 **vhost-user-blk** **+102.1%** / **-49.4%**。
- 相对 bare-metal **XRP**：带宽约 **65%**，均延迟高约 **55%**；P99/P99.9 tail 在虚拟化配置中最低（仅次于 XRP）。
- Range query：各 range length 下均优于虚拟化基线；query 变长时 virtualization 开销占比下降，性能趋近 bare-metal XRP。
- CPU per KOPS：key lookup 为 virtio / vhost-kernel / vhost-user 的 **14.73% / 28.69% / 41.85%**；range query 为 **10.19% / 23.96% / 22.39%**。
- **Multi-tenant throttling**：未限速时 XRP VM 使邻域 virtio VM 带宽跌至配额 **30%**；开启 RosenBridge throttling 后两 VM 均贴近 **1300 MB/s** 限额（总带宽 1/4 配额实验）。

**RosenGDS**（虚拟盘 → GPU，VFIO GPU + virtio-blk）：
- 单线程：相对 virtio-blk+cudaMemcpy，延迟降 **27.5–56.4%**，CPU 至少降 **35.2%**；相对 bare-metal GDS 均延迟高约 **30%**。
- 四线程：4KB–256KB 粒度带宽优于 virtio-blk；盘饱和时带宽约为 GDS 的 **74%**（低 **26%**）；1MB/4MB 时 CPU 为 virtio-blk 的 **45.2% / 79.7%**。

## Critical Analysis

### 论证链条

主链条 **「虚拟化边界阻断 NDP → virtio-ndp 把 NDP 推到 QEMU + io_uring 补全 resubmit 语义 → 两 case study 验证」** 较闭合：§2 breakdown 量化软件栈主导；Fig.2 三条 NDP 路径对比说明为何必须跨边界 offload 到 host；§3 四个 challenge（执行、调度、语义、安全）与四块设计一一对应；§5 用同一 benchmark 族（BPF-KV、cuFileRead）对比 virtio/vhost/bare-metal。

薄弱跳步在于 **「首个支持 NDP express path 的虚拟化框架」** 与 **「轻微 degradation」** 的泛化：(1) 仅实现 **XRP + GDS** 两类已有 bare-metal 优化，压缩、encryption、λ-io 等 NDP 模式仅有设计层面 SNIA 对齐论述；(2) 相对 bare-metal 的 **35–45% 性能差距**在 latency-sensitive DB 场景可能不算「轻微」；(3) 与同期作者 **[[EXO]]**（eBPF 加速 paravirtualization）的 head-to-head 对比缺失——Related Work 称 RosenXRP 可消除 KV 操作内 VM-exit，但未给出与 EXO 的定量实验。

### 假设压力测试

| 假设 | 论文已证明 | 可能失效条件 |
|------|-----------|-------------|
| 软件栈是 virtio 场景主瓶颈 | 4KB 读分解 + CPU× 对比 | vhost-user/SPDK 后端；大 block 顺序读 |
| uBPF@QEMU 足够安全 | PREVAIL + 地址检查 + throttling 设计 | verifier 与真实 exploit 差距；QEMU 自身漏洞面叠加 |
| Guest metadata 自维护即可 | RosenXRP version + digest 工作流 | 并发 FS 操作、crash consistency、live migration 期间 metadata |
| VFIO GPU + virtio 盘代表云 GDS | RosenGDS 端到端数字 | vGPU、MIG 分片、GPU 与盘不在同一 NUMA/主机 |
| Multi-path throttling 恢复公平性 | 双 VM 1300 MB/s 限额实验 | 多租户 >2、混合 read/write、不同 block size 争用；仅带宽未测 IOPS 公平 |
| io_uring passthrough 可长期维护 | 基于 Linux 6.1 定制栈 | 上游 kernel/QEMU 合并进度；非 NVMe 后端 |

### 实验可信度

- **优势**：Baseline 覆盖 **virtio-blk、vhost-kernel-blk、vhost-user-blk** 三条主流 paravirtualized 路径；同时报告 **吞吐、均延迟、tail、CPU per KOPS**；含 **multi-tenant QoS** ablation；GDS 覆盖 4KB–4MB 粒度与单/四线程。
- **局限**：**单机单 VM（throttling 为双 VM）** 为主，未测大规模并发 VM、live migration、checkpoint；**未与 SPDK vhost-user、[[EXO]]、硬件 NVMe virtualization** 对比；RosenGDS baseline 是 virtio+cudaMemcpy 而非更新的 Phoenix 等无 phony buffer 栈；所有实验 **O_DIRECT** 绕过 page cache，对通用 buffered FS workload 外推有限。
- **Ablation**：缺少 virtio-ndp **各组件**（无 io_uring hook、无 passthrough、无共享内存）的逐步消融；uBPF 解释器 vs JIT、PREVAIL 开销未单独列出。

### 系统性缺陷

- **尾延迟与 SLO**：宣称 tail 最优（除 XRP），但未给出 **负载下 P99.9 vs SLA** 或 resubmit 链深度变大时的 tail 增长曲线；VM-exit 仍存在于每次 `read_nd` 入口。
- **故障恢复与可观测性**：论文 **未讨论** QEMU/uBPF 程序崩溃、BPF 加载失败、io_uring 队列背压时的 guest 行为；无 tracing/metrics 接口描述，运维如何 debug 跨边界 NDP 路径不清楚。
- **正确性**：metadata version 可防部分 stale read，但 **guest FS crash、迁移、snapshot** 与 host NDP 并发的一致性协议未形式化；GDS 地址翻译错误可能导致 silent data corruption，仅依赖 helper 边界检查。
- **部署成本**：需 **定制 QEMU、guest kernel 驱动、io_uring/liburing 补丁** 三端协同，通用云镜像落地门槛高；与 managed block storage（EBS 类）架构不匹配。
- **兼容性**：仅 block **read_nd/write_nd** 扩展；file-level API、[[io_uring]] 其他 op、非 Linux guest **论文未讨论**。

## 局限与 Future Work

- **局限 1**：刻意 **仅 offload 到 host userspace**，放弃 host kernel NDP 的极致性能，因 kernel offload 扩大语义鸿沟、且 user/kernel 无法共享锁（I/O throttling bucket 一致性为例）。
- **局限 2**：Case study 仅 **XRP + GDS**，框架通用性主要靠 SNIA CSD 模型与设计论述，其他 NDP（压缩、挖掘、加密）未端到端评测。
- **局限 3**：安全依赖 PREVAIL 与运行时地址检查，**未提供**针对恶意 VM 的渗透测试或形式化验证结果。
- **Future work 1**：探索 **host kernel offload** 的适用场景（作者点名 **network I/O**），并研究不共享锁前提下的一致性机制。
- **Future work 2**：与 **[[DPU]]** 集成，让 DPU 上存储程序发起的 I/O 直达 GPU HBM，绕过 host CPU/内存。
- **Future work 3**：扩展更多 storage I/O optimization use case，持续验证「桥接语义鸿沟」这一主线。

## 相关

- **相关概念**：[[Near-Data-Processing]]、[[Paravirtualization]]、[[virtio]]、[[uBPF]]、[[eBPF]]、[[io_uring]]、[[GPU-Direct-Storage]]、[[KV-Cache]]
- **同类系统**：[[XRP]]、[[EXO]]、[[vhost]]、[[SPDK]]、[[VFIO]]、[[QEMU]]
- **同会议**：[[FAST-2026]]
- **对比**：相对 **virtio/vhost** 把 NDP 引入虚拟化；相对 **[[EXO]]** 走完整 express path 而非仅加速地址翻译；相对 **VFIO/SR-IOV 盘 passthrough** 保留 hypervisor 可管理性
