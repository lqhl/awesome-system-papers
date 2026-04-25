---
type: paper
name: FS-PI
full_title: "Advancing Data Integrity in Linux"
authors: [Anuj Gupta, Christoph Hellwig, Kanchan Joshi, Vikash Kumar, Javier González, et al.]
venue: FAST
year: 2026
tags: [data-integrity, linux-kernel, filesystem, nvme, io_uring]
source_pdf: "[[fast2026-gupta.pdf]]"
source_md: "[[fast2026-gupta]]"
---

# Advancing Data Integrity in Linux (FAST 2026)

> **一句话总结**：补齐 Linux 端到端数据保护（E2EDP）三大缺口——给 block-integrity 加 flexible PI placement、给 [[io_uring]] 加 PI 收发接口、再让文件系统直接生成/校验 PI（FS-PI），在 BTRFS 上提性能 26%、降 host CPU 58%、降 device 写 52%、延长 SSD 寿命 23%；XFS 首次拥有原生数据 checksum。

## 问题

End-to-end data protection（E2EDP）依赖 per-block protection information (PI)：guard tag (CRC)、application tag、reference tag。NVMe / SCSI 设备已支持十多年，但 Linux 主线仍有三个 gap：

1. **Block-integrity 假死 PI 总在 metadata 开头**（继承自 SCSI 单一布局），但 NVMe SSD 默认把 PI 放 metadata 末尾，导致一类合法配置无法启用 E2EDP。
2. **用户态无 PI 接口**：read/write 系统调用只能传数据 buffer，不能传 PI buffer。Oracle 等数据库不得不维护 out-of-tree 驱动（oracleasm）。
3. **文件系统不会用 PI**：XFS/Ext4 后期改不了数据 checksum（要改 on-disk format），BTRFS 用 CoW checksum tree（varmail workload 53M ops 多写 23GB checksum tree + 31GB 其他 tree），在 PI-capable 设备上完全冗余。

## 核心方法

三层修补，全部 upstream 到主线 kernel：

**Flexible PI in block-integrity**（§5.1，6.9 kernel）：引入 `pi_offset`，由 driver 在 integrity init 时告知 block layer。修改 PI 处理函数：checksum 计算时把 metadata buffer 中除 PI 外的部分纳入，PI 的存取偏移按 `pi_offset` 调整，从而支持「PI 在 metadata 末尾」的常见 NVMe 配置。

**io_uring PI interface**（§5.2，6.14 kernel）：选 [[io_uring]] 而非新 syscall，避免 opcode 爆炸（fixed buffer / vectored I/O 各种变体）。在 SQE 加 `attr_type_mask` + `attr_ptr`，应用置 `IORING_RW_ATTR_FLAG_PI` 后通过 32-byte 结构 `io_uring_attr_pi` 传 guard / apptag / reftag flag、PI buffer 地址、长度、apptag 值与 seed。仅支持 direct I/O（buffered I/O 与 page cache 写回粒度难协调）。block 层端复用 reftag remapping 处理用户元数据，正确处理 I/O split。配套加 fio 的 io_uring engine PI 支持 + ioctl 查询设备 PI capability。

**FS-PI（Filesystem Protection Information）**（§5.3）：让文件系统直接在自己掌控 layout 的位置生成/校验 PI，比 block-integrity 更靠上：
- **BTRFS-FS-PI**：去掉 CoW checksum tree，把 4-byte CRC 放进 NVMe 的 per-LBA metadata field。少写 checksum tree，少写 ripple 上传到 root 的链路。
- **XFS-FS-PI**：XFS 历来只 checksum 元数据不 checksum 数据（retrofit 数据 checksum 会破坏 4KB 对齐），借 PI 槽位首次拥有原生数据 checksum。

## 关键结果

- BTRFS + FS-PI：性能 +26%，host CPU −58%，device write −52%，SSD 寿命 +23%（[[DWPD]] 计算）。
- XFS 首次有数据 checksum，无 on-disk format 改动。
- BTRFS 关掉 checksum tree（FS-PI 等价效果）：varmail 减 23.31 GiB checksum tree 写 + 31.32 GiB 其他 tree 写。
- 三项修复均已 upstream（block flexible PI 在 6.9，io_uring PI 在 6.14）。

## 相关

- **相关概念**：[[E2EDP]]、[[Data-Integrity]]、[[NVMe]]、[[io_uring]]、[[Write-Amplification]]、[[DWPD]]
- **同类系统**：[[BTRFS]]、[[XFS]]、[[Ext4]]
- **同会议**：[[FAST-2026]]
