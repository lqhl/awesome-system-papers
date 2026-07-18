---
type: paper
name: FS-PI
full_title: "Advancing Data Integrity in Linux"
authors: [Anuj Gupta, Christoph Hellwig, Kanchan Joshi, Vikash Kumar, Javier González, Roshan R Nair, Jinyoung Choi]
venue: FAST
year: 2026
tags: [data-integrity, linux-kernel, filesystem, nvme, io-uring, write-amplification]
source_pdf: "[[fast2026-gupta.pdf]]"
source_md: "[[fast2026-gupta]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Advancing Data Integrity in Linux (FAST 2026)

> **一句话总结**：Linux 主线 [[E2EDP]] 长期卡在 block-integrity 刚性 PI 布局、用户态无法传 PI、文件系统不用设备 PI 三处缺口；本文补齐 flexible PI placement（6.9）、[[io_uring]] PI 接口（6.14），并提出 **FS-PI** 让 [[BTRFS]]/[[XFS]] 在 I/O 路径直接生成/校验 PI——BTRFS 去掉 checksum tree 后吞吐最高 +26%、host CPU −58%、device write −52%、SSD 寿命 +23%；XFS 首次在不改 on-disk format 前提下获得原生数据 checksum。

## 问题与动机

[[E2EDP]]（End-to-End Data Protection）依赖 per-block Protection Information（PI）：guard tag（CRC）、application tag、reference tag 随数据穿越 I/O 栈，让各层协同检测 silent data corruption。企业级 [[NVMe]]/SCSI 设备支持 PI 已逾十年，Linux 也有 block-integrity 框架，但作者 claim 主线仍**不完整**：硬件能力存在，软件栈却未形成从应用到文件系统再到设备的闭环。

三个结构性 gap 支撑了本文动机：

1. **Block-integrity 假死单一 PI 布局**：框架继承 SCSI 假设，PI 总在 per-LBA metadata **开头**；而 [[NVMe]] 默认 PIL（Protection Information Location）把 PI 放 metadata **末尾**，一类合法设备配置会被内核拒绝，E2EDP 无法启用。
2. **用户态无 PI 通道**：`read`/`write` 只能传 data buffer。数据库等需要应用参与完整性策略的栈只能维护 out-of-tree 方案（如 Oracle ASMLib / oracleasm），部署与维护成本高。
3. **文件系统层 PI 空白**：完整性停在 block layer。已有数据 checksum 的 [[BTRFS]] 用 CoW checksum tree，持续付出 metadata 写放大；[[XFS]]/[[Ext4]] 虽能 checksum 元数据，但 retrofit 数据 checksum 会破坏 4 KB 对齐或需额外 on-disk 结构。PI-capable 设备每 LBA 自带 metadata 槽位，却未被文件系统利用。

作者的核心 claim 不是单点 patch，而是把 PI awareness **上移到文件系统语义层**（FS-PI），同时补齐 block layer 与用户接口，使 Linux 能覆盖真实 NVMe 部署与企业数据库场景。背景与实现细节见 [[fast2026-gupta]]。

## 关键观察 / 隐含假设

- **观察 1：NVMe 主流默认把 PI 放在 metadata 末尾，与 block-integrity 的「PI 在开头」假设冲突。** 证据来自 §4 Gap #1 对 PIL 设置的描述及 Figure 3 的多块写 checksum 覆盖范围差异。
  - **依赖假设**：目标部署使用 NVMe Type 1/2/3 PI 或 Type 0 预留槽位；设备在 format 时固定 PIL，内核需适配而非要求重格式化。
  - **可能失效场景**：仅 SCSI 开头布局、或非 PI-capable 消费级 SSD 上，flexible PI 贡献为零；混合拓扑中部分设备不支持 DIX 分离 metadata buffer。
- **观察 2：BTRFS checksum tree 在 CoW 下引发跨树写放大，在 PI 设备上完全冗余。** varmail workload（53M ops）下 checksum tree 写 23.31 GiB，关掉 checksum 后 other trees 写仍少 31.32 GiB（Table 4）；随机写场景 FS WAF 可达 3.39（Table 7）。
  - **依赖假设**：工作负载触发频繁小块随机写与 checksum tree 更新；设备提供 per-LBA PI 槽位可承载 BTRFS 原有 CRC32c 语义（Type 0 PI）。
  - **可能失效场景**：大块顺序写、或已 `nodatasum` 的部署——FS-PI 相对收益缩小；多副本/RAID 配置下 checksum tree 与冗余策略的交互论文未充分展开。
- **观察 3：XFS 无法在不改 on-disk format 的前提下内嵌数据 checksum，但可借设备 PI 槽位「外挂」完整性元数据。** XFS 自 3.15 起仅 checksum 元数据；在 data stream 内嵌 checksum 会破坏 4 KB 对齐假设（§4 Gap #3）。
  - **依赖假设**：评估与生产环境愿意使用 PI-formatted NVMe；XFS 走 generic [[iomap]] 路径（direct/buffered read/write/writeback 四条路径均可挂 `IOMAP_F_INTEGRITY`）。
  - **可能失效场景**：非 iomap 文件系统、或 buffered write-heavy 顺序写为主——§6.3 显示 buffered sequential write 开销可达 ~20%。
- **假设 1：Block-integrity 在 bio 形成之后才介入，无法覆盖文件系统侧的 split/merge、CoW、reflink、RAID stripe 等变换，因此更高层 FS-PI 有必要。** §5.3.1 从 coverage 与 policy 两维论证。
  - **证据强度**：中。逻辑清晰且有 BTRFS 树写减少的间接证据，但未定量对比「仅 block-integrity」与 FS-PI 在相同 reflink/RAID 场景下的漏检面。
- **假设 2：用户态 PI 交换只需 direct I/O；buffered I/O 与 page cache 写回粒度使 PI 缓存/失效问题不可接受。** §5.2.4 列举 writeback 独立调度、`mmap` 绕过文件系统等理由。
  - **证据强度**：强（设计论证），但意味着大量默认 buffered 应用无法走新 io_uring PI 接口，E2EDP 仍偏数据库/O_DIRECT  niche。
- **假设 3：实验用 Samsung PM9D3 + 单节点 Ubuntu 22.04 / kernel 6.15 上的 FS-PI 树可代表企业 NVMe + BTRFS/XFS 部署趋势。**
  - **证据强度**：弱偏弱。单 SSD、单厂商、评测 kernel 含未完全 upstream 的 FS-PI 补丁；外推到多租户云盘、网络存储或 HDD 需额外测量。

## 核心方法

三层修补，前两层已 upstream，第三层 FS-PI 在 BTRFS/XFS 上实现并评测。

**Flexible PI in block-integrity**（§5.1，Linux 6.9）：引入 `pi_offset`，由 driver 在 integrity init 时告知 block layer PI 在 metadata 内的偏移。修改 `generate_fn`/`verify_fn` 等：当 PI 在末尾时，checksum 覆盖 data + metadata 中除 PI 外的部分；PI 读写按偏移访问。直接回应观察 1，解锁 NVMe 默认 PIL 配置。

**[[io_uring]] PI interface**（§5.2，Linux 6.14）：选 io_uring 而非新 syscall，避免 fixed buffer / vectored I/O 等变体导致 opcode 乘法爆炸。在 SQE 增加 `attr_type_mask` + `attr_ptr`；应用置 `IORING_RW_ATTR_FLAG_PI` 后通过 32-byte `io_uring_attr_pi` 传 guard/apptag/reftag 校验 flag、PI buffer 地址与长度、apptag 值、reftag remapping seed。block 层扩展支持用户生成 metadata，复用 reftag remapping，I/O split 时正确切分 user meta buffer。配套 ioctl 查询设备 PI capability、fio io_uring engine PI 支持。回应观察 2 的用户态缺口，但**限定 direct I/O**（回应假设 2）。与同期 [[I/O-Passthrough]] 工作（Joshi et al., FAST'24）同属 io_uring 扩展路线，但本文强调协议无关的 block/file 通用 PI 交换。

**FS-PI（Filesystem Protection Information）**（§5.3）：文件系统在掌控 layout 与数据可见性的位置分配 PI buffer、写路径生成、读路径校验。相对 block-integrity 的优势 claim：保护 host–device 线缆传输、更早捕获 in-memory bit flip、支持 per-file apptag 等文件系统策略；通过 `fs_bio_integrity_*` helper 集中 buffer 管理与 checksum 语义。

- **PI 模式**：Type 1/2/3 由设备硬件校验 guard/ref tag，FS 生成/验证即可；**Type 0** 设备不校验，FS 可把整段 metadata 当自定义 checksum 槽（如 CRC32c），绕过「多数 NVMe 仅实现 CRC16/64」的限制（Table 6）。
- **BTRFS-FS-PI**：`dev_pi` mount option 停用 checksum tree；`btrfs_submit_dev_bio()` 写前 `fs_bio_integrity_generate()`，读完成 `btrfs_check_read_bio()` 验证。Type 0 下 CRC32c 等价原 tree 保护但写放大更低。`REQ_NOINTEGRITY` 跳过已有自描述 checksum 的元数据 bio，避免双重计算。
- **XFS-FS-PI**：`IOMAP_F_INTEGRITY` 挂到 generic iomap，覆盖 direct read/write、buffered read（`iomap_read_folio_ops`）、buffered writeback（`iomap_ioend_writeback_submit`）四条路径；任何 iomap 文件系统理论上可一行 flag 启用。

失败语义：FS-PI **仅保护数据块**；元数据仍走各自机制。PI mismatch 报 I/O error；BTRFS 在 DUP/RAID profile 下的冗余恢复**明确 defer** 到 future work。

## 设计取舍

- **io_uring 属性扩展 vs 新 opcode**：用 `attr_type_mask`/`attr_ptr` 保持 SQE 大小稳定、可扩展其他属性；代价是应用必须理解 PI 结构与设备 capability ioctl，学习曲线高于普通 read/write。
- **Direct I/O only（用户 PI）vs 全覆盖**：回避 page cache 与 PI 一致性噩梦；牺牲默认 buffered 应用与 `mmap` 路径的端到端 PI，数据库/O_DIRECT 栈受益，通用桌面/容器 workload 仍依赖 FS-PI 或 block-integrity。
- **BTRFS 去掉 checksum tree vs 冗余修复**：换 PI 显著降 WAF 和 CPU，但 PI 失败时不像 tree 那样天然配合 BTRFS 冗余副本做修复——论文在评测用的 single profile 下「无纠正动作」。
- **XFS 不改 on-disk format vs 完整性粒度**：借设备 PI 槽位获得数据 checksum，部署门槛低；依赖 PI-formatted 设备，且 buffered 顺序写路径 PI 在 writeback 时生成，带来最高 ~20% 吞吐损失。
- **Type 0 灵活 checksum vs 硬件加速**：FS 自选 CRC32c，设备不 offload 校验；CPU 成本由 helper 集中承担，在 BTRFS 上仍净赚 58% host CPU（固定 IOPS 对比）。
- **边界条件**：对 PI-capable NVMe + CoW 随机写重的 BTRFS 优雅；对无 PI 设备、已 nodatasum、或 XFS buffered 大顺序写变脆；用户态 PI 与 FS-PI 可叠加但 buffered 用户路径仍不可用。

## 实验与结果

**Setup**：Ubuntu 22.04、Linux 6.15、AMD Ryzen 9 5900X、16 GB RAM、1.88 TB Samsung PM9D3；每项实验 4 次取标准差。Workload：fio 合成（24 job × 10 GiB、QD 128、4 KiB）、Filebench（varmail/webserver/fileserver/OLTP）、单 job QD 1 延迟测试。

**BTRFS FS-PI（相对 basecase checksum tree）**：

- **写放大**：direct random write host write 813.66 → 391.14 GiB（−52%），FS WAF 3.39 → 1.62；NAND write −52%。buffered random write host write −20%，FS WAF 3.42 → 2.77。checksum tree 写归零；FS/extent 等树写 direct I/O 下减 62%–70%。
- **读放大**：写路径伴随读操作 direct −53%、buffered −58%。
- **吞吐**：Filebench varmail 83 → 94 K ops/s（+13%，fsync 密集受益最大）；webserver/OLTP/fileserver 基本持平。fio 随机写提升最明显（Abstract 汇总 **+26%** 性能应主要来自该路径）；顺序读/写与随机读与 base 相近。
- **CPU**：固定 `rate_iops` 对比，随机写 idle CPU 12% → 70%（**−58% host CPU utilization** 语境）。
- **耐久**：限速 72 MiB/s 一小时随机写，外推 DWPD 27.33 → 22.15（−19%），估算 SSD 寿命 **+23.4%**。

**XFS FS-PI（相对无数据 checksum basecase）**：

- Filebench 吞吐几乎相同（varmail 219/219 K ops/s；webserver 902 → 890）。
- fio：direct random write 约 −4%；buffered sequential write 最大约 **−20%**；其余场景 1%–6% 量级。
- 延迟：写与随机读有小幅上升，顺序读 buffered 更明显（Figure 15）。

**Upstream 状态**：flexible PI → 6.9；io_uring PI → 6.14；FS-PI BTRFS/XFS 评测用定制 kernel tree，结论 §8 称未来继续推动 upstream。

## Critical Analysis

### 论证链条

observation → design → result 在「PI-capable NVMe + BTRFS 随机写/元数据繁重」主线上闭合较好。flexible `pi_offset` 直接对应 NVMe PIL 事实；io_uring 接口对应用户态缺口；BTRFS 用 FS-PI 砍掉 checksum tree 与 Table 4/7/11 的树写、WAF、NAND 写、CPU idle 测量一致。XFS 分支逻辑也自洽：无 format 变更的数据 checksum 以可预测开销购买完整性。

主要跳步在于把 **BTRFS 单盘 fio/Filebench 收益**外推为「Linux 数据完整性全面进步」。Abstract 的 +26% 与 Table 8 varmail +13% 并存，论文未统一解释聚合口径，读者需自行对应 workload。此外，「FS-PI 比 block-integrity 更早捕获错误」更多是架构论证，**实验未注入 bit flip 或线缆错误**验证检测率与延迟优势。

### 假设压力测试

**非 PI 或 Type 1-only 设备**：FS-PI 与 flexible PI 收益骤降，论文几乎不讨论降级路径（除 `REQ_NOINTEGRITY` 在元数据上的条件优化）。

**BTRFS 冗余配置**：DUP/RAID 下 PI mismatch 后的修复策略 deferred；生产若依赖 btrfs scrub + 副本修复，FS-PI 是否与现有自愈流程集成未证明。

**用户态 PI + 通用应用**：direct I/O 限制使 oracleasm 类场景仍需迁移成本；buffered 数据库若不能 O_DIRECT，只能依赖 FS-PI 层保护，应用级 apptag 策略无法贯穿。

**多设备/云存储**：评测单机直挂 NVMe。网络块设备、多路径、[[dm-integrity]]/[[dm-verity]] 与 FS-PI 的组合边界仅在 Related Work 文字对比，无实测。

**XFS buffered 顺序写 −20%**：邮件/日志类顺序 append 若启用 FS-PI，尾延迟与吞吐平台化风险论文有数据但缺少 production trace 验证。

### 实验可信度

**强项**：host write（iostat）与 NAND write（SSD log page）分层测量；CPU 对比用 `rate_iops` 固定负载，避免「跑得快所以 CPU 占比低」的假象；覆盖 direct/buffered、合成与 Filebench、延迟细分；artifact 公开 kernel tree 与脚本。

**不足**：**单 SSD、单厂商、单节点**；FS-PI 评测依赖非主线 6.15 补丁树，与已 upstream 的 block/io_uring 部分混在一起读结果时需小心。缺少 corruption injection、长时间 aging、并发多租户 fsync 压力。Baseline 未包含「BTRFS nodatasum」或「仅 block-integrity 无 FS-PI」的 ablation，难以单独量化「上移到 FS」的边际收益。XFS 安全收益（首次数据 checksum）未量化误检率或与备份/scrub 工具链兼容性。

### 系统性缺陷

- **故障恢复**：BTRFS 冗余 profile 下 PI 错误无自动修复；论文未讨论运维 playbook（scrub 行为、是否需离线 fsck）。
- **尾延迟**：XFS FS-PI 在部分 buffered 读路径有序列读延迟抬升，论文未报告 p99/p999 或 SLO 视角。
- **可观测性**：PI mismatch 仅以 I/O error 暴露，未讨论 tracing、per-file apptag 审计、与 enterprise monitoring 集成。
- **隔离与多租户**：单文件系统配置实验，未涉及容器共享 PI 设备、quota、或恶意 apptag 混淆。
- **兼容性**：依赖 PI-formatted NVMe；与现有云盘虚拟化、ZNS、[[Write-Amplification]] 优化 FTL 的交互论文未讨论。
- **部署成本**：XFS/BTRFS 需特定 mount/flag + 设备 format；从 legacy 盘迁移的路径论文未覆盖。

## 局限与 Future Work

- **局限 1**：用户 io_uring PI 仅支持 direct I/O，buffered/mmap 路径无法携带用户 PI。
- **局限 2**：FS-PI 当前只保护数据块；BTRFS 元数据与 XFS 冗余策略下的 PI 失败恢复未实现。
- **局限 3**：评测平台与 workload 偏企业 NVMe + 合成/Filebench，对云盘、HDD、QLC 极限写循环的泛化证据有限（Related Work 提及 QLC 动机但无 QLC 实测）。
- **局限 4**：XFS buffered sequential write ~20% 开销在写密集场景可能成为采纳障碍。
- **Future work 1**：在 PI-capable 生产 trace 上对比 FS-PI、block-integrity-only、nodatasum 的 WAF/CPU/检测延迟 Pareto 曲线，明确何时值得 format 设备启用 FS-PI。
- **Future work 2**：实现并测量 BTRFS DUP/RAID profile 下 PI mismatch 的冗余恢复路径，闭合「完整性 vs 可修复性」设计空间。
- **Future work 3**：将 FS-PI 通过 `IOMAP_F_INTEGRITY` 推广到 Ext4、F2FS 等 iomap 文件系统，并量化 Type 0 vs hardware-verified PI 的 CPU 权衡。
- **Future work 4**：fault injection（线缆/NAND/内存 corruption）端到端实验，验证 FS-PI 相对 checksum tree 的检测时机与漏检率，而不只测性能侧收益。

## 相关

- **相关概念**：[[E2EDP]]、[[Data-Integrity]]、[[NVMe]]、[[io_uring]]、[[Write-Amplification]]、[[DWPD]]、[[iomap]]、[[BTRFS]]、[[XFS]]、[[Ext4]]、[[dm-integrity]]、[[dm-verity]]
- **同类系统**：block-integrity、Oracle ASMLib/oracleasm、ZFS checksumming、[[I/O-Passthrough]]（FAST'24）、SPDK PI 路径
- **同会议**：[[FAST-2026]]
- **对比**：ZFS/BTRFS out-of-place checksum tree vs FS-PI per-LBA PI；dm-integrity 软件标签 vs FS-PI 文件系统原生策略
