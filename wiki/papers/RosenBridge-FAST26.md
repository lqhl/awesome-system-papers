---
type: paper
name: RosenBridge
full_title: "RosenBridge: A Framework for Enabling Express I/O Paths Across the Virtualization Boundary"
authors: [Shi Qiu, Li Wang, Jianqin Yan, Ruofan Xiong, Leping Yang, et al.]
venue: FAST
year: 2026
tags: [virtualization, ndp, virtio, ubpf, qemu, gpu-direct-storage]
source_pdf: "[[fast2026-qiu.pdf]]"
source_md: "[[fast2026-qiu]]"
---

# RosenBridge: A Framework for Enabling Express I/O Paths Across the Virtualization Boundary (FAST 2026)

> **一句话总结**：通过新的 paravirtualized 设备 virtio-ndp + uBPF 在 QEMU userspace 跨虚拟化边界执行 NDP 程序，让 [[XRP]]、[[GPU-Direct-Storage]] 等 bare-metal express I/O path 可在 VM 中复用，相对 virtio/vhost 大幅提速，相对 bare-metal 仅有「轻微」性能损失。

## 问题

NVMe SSD 软件栈占 4KB 随机读延迟 87%，bare-metal 上 NDP 优化（[[XRP]] resubmit、GPU Direct Storage 等）可以把 BPF 程序挂在 NVMe 驱动 IRQ handler 上短路 kernel 路径。但虚拟化打破了这条路：guest 看不见 host 物理设备，virtio-blk 走 VM-exit → KVM → QEMU emulate → host syscall → 设备的长路径，VM 比物理机做同样吞吐多花 498-630% CPU。把 BPF 直接放进 host kernel NVMe 驱动会破坏隔离，放进 guest 又跨不过语义鸿沟。

## 核心方法

- **virtio-ndp 设备**：扩展 virtio-blk header 增加 BPF semantics（VIRTIO_BLK_T_LOAD/READ_ND/WRITE_ND/UNLOAD），guest ioctl `BPF_HOST_ATTACH` 把 BPF 程序加载到 QEMU 中由 [[uBPF]]（用户态 BPF 实现）执行，比 [[eBPF]] 内核加载更适合云端隔离要求。
- **io_uring 双 hook 调度**：为支持 on-path（如 GDS、压缩）和 content-based resubmit（如 XRP）两种 NDP 模式，在 io_uring `prep_read` 和 `cqe_seen` 加 uBPF hook，提供 `BPF_uring_get_sqe` / `get_new_sqe` / `set_sqe` helper 让 BPF 修改/重提交 SQE；用 io_uring NVMe passthrough 绕过 kernel I/O 栈。
- **Guest-Host 语义桥接**：通过 PCIe BAR 映射的共享内存区传 guest metadata；提供 `BPF_disk_trans`（GPA→host 文件 offset）、`BPF_mem_trans`（GPA→HVA）helper；`rosenbridge_md` ctx 限制 BPF 仅可读 meta、读写 data。
- **安全与公平**：用 PREVAIL verifier 编译期静态分析约束 uBPF 内存访问；继承 QEMU leaky bucket 做 multi-path I/O throttling，防止 NDP 路径绕过 SLA。

两个 case study：RosenXRP（接 XRP 的 BPF-KV B-tree 查询）、RosenGDS（GPU 直传，VFIO passthrough GPU + virtio-blk 虚拟盘）。

## 关键结果

- 4KB 随机读 BPF-KV 在 VM 中性能显著超越 virtio-blk、vhost-kernel-blk、vhost-user-blk
- 相比 bare-metal XRP/GDS 仅有少量虚拟化固有开销
- CPU 用量比 paravirtualization 基线明显降低

## 相关

- **相关概念**：[[Near-Data-Processing]]、[[uBPF]]、[[eBPF]]、[[virtio]]、[[io_uring]]、[[GPU-Direct-Storage]]、[[Paravirtualization]]
- **同类系统**：[[XRP]]、[[vhost]]、[[SPDK]]、[[VFIO]]
- **同会议**：[[FAST-2026]]
