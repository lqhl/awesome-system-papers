---
type: paper
name: RISTRETTO
full_title: "Here, There and Everywhere: The Past, the Present and the Future of Local Storage in Cloud"
authors: [Leping Yang, Yanbo Zhou, Gong Zeng, Li Zhang, Saisai Zhang, et al.]
venue: FAST
year: 2026
tags: [cloud-storage, dpu, nvme, ebs, experience-paper, alibaba]
source_pdf: "[[fast2026-yang.pdf]]"
source_md: "[[fast2026-yang]]"
---

# Here, There and Everywhere: The Past, the Present and the Future of Local Storage in Cloud (FAST 2026)

> **一句话总结**：阿里云三代云端 local storage 演进经验论文——从 SPDK 用户态栈 ESPRESSO（2017）→ ASIC DPU 卸载 DOPPIO（2019）→ ASIC+SoC 协同 RISTRETTO（2023，单 VD 900K IOPS、整机 7.2M IOPS），并提出未来 LATTE：本地盘 + 弹性 EBS 混合，借 ML dispatcher 与 S3-FIFO 做 admission，平衡性能/可用性/成本。

## 问题

云服务商提供的 cloud local storage（AWS、Azure、阿里云）是把物理 SSD 直挂在 compute server 上做虚拟盘，价格便宜性能近物理。但要榨干 SSD 性能并跟上代际演进很难——

- 内核 stack 在 [[NVMe]] SSD 上仅达 9.54% 物理 IOPS、1.4 核 CPU 占用，VM_Exit/syscall/interrupt 三类 context switch 严重。
- ASIC DPU 灵活性差、跟不上 SSD 迭代（PCIe Gen3 → Gen4 时单 DPU 仅能做到 1.3M IOPS）。
- 物理盘还有 LDL_1-3 三大局限：可用性（disk 故障 → 小时级停服）、弹性（容量被单 SSD 限制）、可访问性（少用户区域不部署）。

## 核心方法

**ESPRESSO（gen-1, 2017）**：基于 [[SPDK]] 把 stack 从内核移到用户态 + polling-mode + 专核绑定，HDD 软件开销 -82.35%。但需要专核（不能 bare-metal）、CPU 利用率 <60%、I/O completion 仍要 VM_Exit。

**DOPPIO（gen-2, 2019）**：用商用 ASIC DPU 做 SR-IOV 虚拟化，每个 DPU 管 2 块 NVMe SSD，VF 通过 PCI passthrough 给 VM。优点：bare-metal 就绪、硬件中断、解放 host CPU。缺点：ASIC 算力跟不上 PCIe Gen4 SSD、不灵活（不支持 LVM/[[ZNS]] 等云特性）。

**RISTRETTO（gen-3, 2023）**：PCIe 扩展卡，板上 ASIC + ARM Cortex-A72 SoC 协同。
- ASIC 做 NVMe 虚拟化后端 + DMA 引擎 + 仿真 NVMe 控制器，支持 1000+ VF。
- SoC 跑 [[SPDK]] BDEV，提供 LVM、RAID、Caching、FTL（含 [[ZNS]] SSD 的 host-side FTL），轮询 ASIC-SoC 间的 virtual queue。
- DMA 由 ASIC 直接路由到 guest OS 内存（zero copy），中断直通 (Intel VT-D)。
- 单 VD 900K IOPS @ PCIe Gen4 SSD，整机 8 VD 共 7.2M IOPS，对 DOPPIO 单 VD IOPS +80%，cost-of-ownership 优于纯 SoC 方案。

**LATTE（PoC, 未来）**：local disk（RISTRETTO，作为高性能写缓冲与热数据 cache）+ 标准 EBS（兜底）混合。
- 基于 CSAL（与 Solidigm 联合开源）改造：替换 Optane→local disk、QLC SSD→cloud disk。
- ML-based I/O dispatcher（参考 LinnOS、Heimdall）按 per-I/O 推理决定写本地还是远端。
- [[S3-FIFO]] 替换 LRU 做 admission control。
- 拿掉 CSAL 的 log-compaction/GC（EBS 自身具备）。

## 关键结果

- ESPRESSO：HDD stack 软件开销 -82.35%；8 VD 3,848K IOPS @ 4 cores。
- DOPPIO：6M IOPS / 整机；HDD-stack 6 cores 节省。
- RISTRETTO：900K IOPS / VD（PCIe Gen4），整机 7.2M IOPS、48 GB/s 吞吐；SoC 提供 LVM/FTL/[[ZNS]] 支持。
- LATTE：在 RISTRETTO 上多花 ~3% CapEx 即可获得近物理性能 + EBS 级可用性，避免 EBSX 直接当本地盘的 ~20× 价格。
- 三代均规模化部署到上千台服务器，文章提供完整 microbench/trace-driven 评测。

## 相关

- **相关概念**：[[NVMe]]、[[SPDK]]、[[ZNS]]、DPU、SR-IOV、[[S3-FIFO]]
- **同类系统**：AWS Nitro、Azure Boost、Alibaba EBS、CSAL
- **同会议**：[[FAST-2026]]
