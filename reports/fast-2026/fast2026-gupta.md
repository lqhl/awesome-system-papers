# Advancing Data Integrity in Linux

**作者**：Anuj Gupta (Samsung Semiconductor), Christoph Hellwig, Kanchan Joshi (Samsung Semiconductor), Vikash Kumar (Samsung Semiconductor), Javier González (Samsung Semiconductor), Roshan R Nair (EPFL), Jinyoung Choi (Samsung Semiconductor)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/gupta
**源文件**：[[fast2026-gupta.pdf]]

---

## 一、背景

存储系统面临持续的数据完整性挑战，硬件和软件错误均可导致数据损坏。硬盘驱动器和闪存设备使用 ECC 保护持久化数据，但数据在存储设备与应用之间的软件栈中传输时同样可能发生损坏。End-to-End Data Protection (E2EDP) 通过在 I/O 栈各层携带 per-block Protection Information (PI)——包括 checksum、reference tag 和 application tag——来实现全链路数据保护。

NVMe 和 SCSI 企业级 SSD 已支持 PI 超过十年，通过 Data Integrity Field (DIF) 和 Data Integrity Extension (DIX) 实现。Linux 内核的 block-integrity 框架基于 DIX 构建，在 block layer 自动处理 PI metadata 的附加/分离/验证。然而，Linux 在 PI 支持上仍存在多个关键缺口，限制了端到端数据保护的实际应用。

---

## 二、要解决的问题

论文明确指出 Linux 数据完整性支持的三个核心缺口：

1. **Block-integrity 的 PI 放置方式僵化**：NVMe SSD 允许 PI 位于 per-LBA metadata 的首部或尾部（通过 PIL 设置），但 block-integrity 框架源自 SCSI 时代，硬编码假设 PI 总在 metadata 首部。当 NVMe 设备将 PI 放在尾部（这是未指定 PIL 时的默认行为）时，Linux 直接拒绝该设备配置。

2. **缺少用户态 PI 交换接口**：现有 read/write 系统调用只能传递数据 buffer，无法同时传递 metadata/PI buffer。用户态软件（数据库、分布式文件系统、厂商库）要参与 E2EDP，要么放弃端到端保护，要么维护树外的自定义驱动（如 Oracle ASMLib）。

3. **文件系统不感知 PI**：没有 Linux 文件系统利用设备 PI 能力。BTRFS 虽有数据 checksum，但依赖开销高昂的 CoW checksum tree；XFS 完全没有数据 checksum；Ext4 情况类似。将数据 checksum 改造进已有文件系统的 on-disk format 代价极高，而 PI-capable 设备提供的 per-LBA metadata 字段本可大幅降低这一门槛。

---

## 三、洞察与设计

**关键洞察**：PI-capable 设备已在每个 LBA 旁提供了轻量的 per-block metadata 字段，文件系统可以直接利用这一硬件能力来生成和验证 checksum，而不需要维护独立的、开销昂贵的 checksum 元数据结构（如 BTRFS 的 checksum tree）。将 PI 感知从 block layer 上移到文件系统层，既能扩大保护覆盖范围（涵盖文件系统自身的数据变换），又能让文件系统按自身策略决定何时、对什么数据施加保护。

基于此洞察，论文提出三层递进的设计：

### 1. Flexible PI（Block Layer 增强）
引入 `pi_offset` 机制，让 block-integrity 的 PI 处理函数感知 PI 在 metadata 中的偏移位置，从而支持 PI 在 metadata 首部或尾部的两种配置。

### 2. io_uring PI 接口（用户态支持）
在 io_uring 中扩展现有 read/write 操作，通过新增 `attr_type_mask` 和 `attr_ptr` 字段，让应用以 32 字节的 `io_uring_attr_pi` 结构传递 PI buffer。设计上选择指针方式而非 Big SQE，避免所有 SQE 膨胀到 128 字节。仅支持 Direct I/O（Buffered I/O 因 page cache 粒度和 writeback 同步问题不兼容）。

### 3. FS-PI（文件系统驱动的 PI）
核心创新——让文件系统自己分配 PI buffer、生成和验证 PI，取代 block-integrity 的自动处理：
- **BTRFS FS-PI**：新增 `dev_pi` mount option，用设备 PI 替代 checksum tree，彻底消除 checksum tree 的写放大。Type-0 PI 模式下支持 CRC32c。
- **XFS FS-PI**：通过 `IOMAP_F_INTEGRITY` flag，在 iomap 层实现 PI 的分配和生成/验证，为 XFS 首次引入数据 checksum，且无需修改 on-disk format。支持 Direct I/O 和 Buffered I/O 的全部四条路径。
- **Block Layer Helpers**：提供 `fs_bio_integrity_*` API 集中 PI 逻辑，降低不同文件系统集成 PI 的工程成本。
- **REQ_NOINTEGRITY 优化**：文件系统 metadata I/O 已有自身的 checksum 保护，设置此 flag 跳过 block-integrity 的冗余 checksum，由设备自动插入/剥离 PI。

---

## 四、实现细节

**Flexible PI**：修改 block-integrity 的四个核心函数（generate_fn、verify_fn、prepare_fn、complete_fn），增加 `pi_offset` 参数。驱动在初始化时将 PI 偏移量传递给 block layer。已合入 Linux 6.9 内核。

**io_uring 接口**：
- 在 SQE 中新增 `attr_type_mask` 和 `attr_ptr` 字段，应用设置 `IORING_RW_ATTR_FLAG_PI` 并指向 `io_uring_attr_pi` 结构（含 flags、app_tag、len、addr、seed 等字段）
- 支持 `IO_INTEGRITY_CHK_GUARD`、`IO_INTEGRITY_CHK_REFTAG`、`IO_INTEGRITY_CHK_APPTAG` 三种细粒度检查标志
- Block 设备侧扩展 block-integrity 支持用户生成的 metadata，复用 reftag remapping 避免应用暴露物理位置
- 处理大 I/O 拆分时正确分割 user meta buffer
- 新增 ioctl 供用户态查询设备 PI 能力（metadata/tuple size、checksum 类型、PI offset 等）
- 扩展 fio 的 io_uring 引擎支持 PI，含自包含验证测试
- 已合入 Linux 6.14 内核

**BTRFS FS-PI**：
- 在 `btrfs_submit_dev_bio()` 中根据 I/O 类型分别处理：写时分配 PI buffer 并生成 tuple，读时在 `btrfs_check_read_bio()` 的 process context 中验证
- Type-0 PI 模式下增加 CRC32c 生成和验证，提供与原生 checksum tree 等价的保护

**XFS FS-PI**：
- 新增 `IOMAP_F_INTEGRITY` flag，在 iomap 层实现 PI 逻辑
- Direct Read/Write：在 `iomap_dio_rw()` 中分配 PI buffer，分别在 bio completion 和 submission 前完成验证/生成
- Buffered Read：通过新的 `iomap_read_folio_ops` 结构 hook bio 提交，在 process context 中验证后数据才进入 page cache
- Buffered Write：在 writeback 路径 `iomap_ioend_writeback_submit()` 中生成 PI
- 整个实现在通用 iomap 层完成，其他使用 iomap 的文件系统可直接复用

---

## 五、实验结果

**实验平台**：Ubuntu 22.04，Linux 6.15，AMD Ryzen 9 5900X 12核，16GB DDR4，1.88TB Samsung PM9D3 SSD。所有实验运行 4 次，报告标准差。

### BTRFS FS-PI 结果

| 指标 | Base | FS-PI | 变化 |
|------|------|-------|------|
| Host Writes (Direct Randwrite, 240GiB App) | 813.66 GiB | 391.14 GiB | -52% |
| Host Writes (Buffered Randwrite, 240GiB App) | 835.46 GiB | 666.90 GiB | -20% |
| NAND Writes (Direct Randwrite) | 839.91 GiB | 403.76 GiB | -52% |
| FS WAF (Direct Randwrite) | 3.39 | 1.62 | -52% |
| FS WAF (Buffered Randwrite) | 3.42 | 2.77 | -19% |
| Reads Issued (Direct) | 30.43 GiB | 14.12 GiB | -53% |
| Reads Issued (Buffered) | 19.76 GiB | 8.19 GiB | -58% |
| Idle CPU (Direct Randwrite) | ~12% | ~70% | +58pp |
| Varmail (Filebench) | 83 Kops/s | 94 Kops/s | +13% |
| DWPD (rate-limited) | 27.33 | 22.15 | -19% |
| SSD 寿命提升 | — | — | +23.4% |

- Tree-wise 分析：checksum tree 写入完全消除；FS tree 写入减少 ~70%；extent tree 写入减少 ~62%（Direct I/O）
- 顺序 I/O 和随机读性能无退化

### XFS FS-PI 结果

| 工作负载 | 性能影响 |
|----------|---------|
| Direct Random Write | -4% |
| Direct Sequential Write | -1~2% |
| Direct Read | 可忽略 |
| Buffered Sequential Write | -20% |
| Buffered Random Read | -1~6% |
| Filebench (Varmail/OLTP/Fileserver/Webserver) | 基本持平 |

- XFS FS-PI 的主要开销在 Buffered Sequential Write（writeback 时 PI 生成），Direct I/O 路径开销很小
- 延迟方面，写操作和随机读有小幅增加，顺序读增加较明显

---

## 六、批判性分析

1. **XFS Buffered Sequential Write 的 20% 性能下降被轻描淡写**：论文称"predictable penalty"，但 20% 对顺序写密集的工作负载（如日志、大文件写入）是显著退化。论文未深入分析这一开销的来源和优化空间，也未在 Filebench 中设计此类场景进行验证。

2. **BTRFS 评估仅用单盘、非冗余 profile**：论文承认 RAID profile 下的错误恢复留作 future work，但 BTRFS 生产部署常用 RAID1/RAID10。checksum tree 在冗余场景下还承担定位正确副本的角色，FS-PI 替代后的恢复语义未讨论。单盘评估可能高估了 FS-PI 的适用性。

3. **SSD 寿命估算方法粗糙**：仅用 1 小时 rate-limited 的 fio random write 线性外推到 full-day DWPD，忽略了真实工作负载的时变特性、GC 行为随充盈度变化等因素。23.4% 的寿命提升数字的置信度存疑。

4. **Buffered I/O PI 接口被排除**：虽然论文给出了合理的技术解释（page cache 粒度、mmap 一致性），但大量用户态应用使用 Buffered I/O。用户态 PI 接口仅支持 Direct I/O 显著限制了其适用范围，而论文对此局限的讨论不足。

5. **仅评估一款 SSD**：所有实验基于 Samsung PM9D3。不同 SSD 的 FTL、GC 策略、PI 实现差异可能影响结论的普适性，缺乏跨设备验证。

6. **XFS FS-PI 未展示 checksum 实际检测到损坏的案例**：论文评估了添加 checksum 的开销，但缺少故障注入实验证明新增的 checksum 确实能在实践中检测和报告损坏，即功能正确性验证不足。

---

## 七、AI Infra / MLSys 视角

1. **Checkpoint 写放大优化**：大规模分布式训练的 checkpoint 写入是 I/O 密集型操作，BTRFS FS-PI 的 52% 写放大缩减可直接惠及 checkpoint 存储层，降低 SSD 磨损并加速写入。特别是 checkpoint 通常使用 Direct I/O，正好是 FS-PI 收益最大的路径。

2. **训练数据完整性保障**：AI 训练数据集规模持续增长（数十 TB 级），silent data corruption 可导致难以定位的训练质量下降。XFS FS-PI 为 XFS 首次引入数据 checksum，对使用 XFS 的 AI 存储集群（如 GPFS/Lustre 的 OST）有直接价值，且几乎无需修改现有部署。

3. **用户态 PI 接口与 AI 推理引擎**：vLLM 等推理系统使用 Direct I/O 加载模型权重，io_uring PI 接口允许在模型加载路径中嵌入端到端完整性验证，防止权重损坏导致的推理错误。这对安全关键场景（金融、医疗）的 AI 部署尤为重要。

4. **可跟进方向**：
   - 结合 FS-PI 研究 checkpoint 压缩+完整性保护的联合优化
   - 在 NVMe-oF（网络传输）场景下评估 FS-PI 对远程存储的保护效果，这与 disaggregated storage 架构下的 AI 训练高度相关
   - 利用 Type-0 PI 的灵活 metadata 字段存储 AI 训练的 provenance 信息（如数据版本、预处理哈希）

---

## 八、总结

本文系统性地填补了 Linux 端到端数据保护的三个核心缺口：block-integrity 的灵活 PI 放置、io_uring 用户态 PI 交换接口、以及文件系统驱动的 PI (FS-PI)。在 BTRFS 中，FS-PI 通过消除 checksum tree 实现了 52% 的写放大缩减、58% 的 CPU 利用率降低和 23% 的 SSD 寿命延长；在 XFS 中，FS-PI 以较小的性能代价首次引入了数据 checksum 能力。部分贡献已合入 Linux 6.9 和 6.14 主线内核。主要局限在于用户态接口仅支持 Direct I/O、BTRFS 冗余 profile 支持缺失、以及评估仅覆盖单一 SSD 型号。
