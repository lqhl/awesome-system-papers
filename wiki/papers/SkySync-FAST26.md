---
type: paper
name: SkySync
full_title: "SkySync: Accelerating File Synchronization with Collaborative Delta Generation"
authors: [Zhihao Zhang, Huiba Li, Lu Tang, Guangtao Xue, Jiwu Shu, Yiming Zhang]
venue: FAST
year: 2026
tags: [file-sync, sky-computing, storage-metadata, checksum-reuse, delta-sync]
source_pdf: "[[fast2026-zhang-zhihao.pdf]]"
source_md: "[[fast2026-zhang-zhihao]]"
---

# SkySync: Accelerating File Synchronization with Collaborative Delta Generation (FAST 2026)

> **一句话总结**：在 [[Sky-Computing]] 跨云 delta sync 场景下，checksum 计算与 chunk searching 占 [[rsync]]/[[dsync]] 同步时间高达 95%，而现代存储栈已为完整性维护了块级 checksum；SkySync 复用这些元数据并用 [[CRC32C]] 代数组合推出 chunk checksum，计算开销最高降 **89.3%**，client/server 同步 **1.1×–2×** 加速，网络流量持平。

## 问题与动机

[[Sky-Computing]] 把计算与存储拆到多个地理分布的云上，跨云文件同步成为数据共享瓶颈。相比 full sync，[[Delta-Sync]] 只传变更部分，是 WAN 场景下的标准选择。现有方案分 FSC-based（[[rsync]]：Adler32 + MD5，server 先发 checksum list）和 CDC-based（[[dsync]]：FastCDC + FastFP，client 先发 checksum list）两类，但 delta generation 的三步——file chunking、chunk checksum 计算、chunk searching——在 client 与 server 两端都极耗 CPU。

作者在典型云 VM（AWS EC2 / 阿里云 ECS + EBS/OSS 后端）上测量：client + server 时间占总同步时间 **71.2%–93.7%**，其中 checksum 计算与 searching 合计占两端时间的 **95%**。在 500Mbps WAN 下，网络传输反而只是小头。即便给 rsync/dsync 加上 AVX-512 Adler32、SSE SHA-NI 等硬件加速，因 rolling hash 的不规则访存与缓存利用率差，整体收益有限——说明瓶颈是「算了多少 checksum」，而非「算得快不快」。

Dropbox（rsync-like）和 Seafile（dsync-like）即便跑在已有 [[BTRFS]]/[[ZFS]] checksum 的文件系统上，仍必须在 sync 时重算 checksum，因为 boundary-shift problem 使 dedup 用的 fixed-size checksum 无法直接对应 sync 所需的 chunk boundary。作者据此提出：不应把存储层 checksum 当「碰巧相同」的 shortcut，而应设计一套**协作式 delta generation**，主动从存储层「继承 + 适配 + 组合」元数据。

## 关键观察 / 隐含假设

- **观察 1**：rsync/dsync 的 sync 时间由 checksum 计算与 searching 主导，而非网络带宽（在 ≥500Mbps 云 WAN 下）。
  - **依赖假设**：实验 workload 以 10MB–100MB 微基准 + 最大 221GB 真实数据集为主；修改规模从 256B 到 8MB；网络 RTT ~35ms、带宽 500Mbps。
  - **可能失效场景**：低带宽（100Mbps 以下）或极高 RTT 链路下，网络时间占比上升，SkySync 的 CPU 节省对端到端收益缩小；论文在 100Mbps 下仍观察到 compute 主导，但边际收益需重新测量。

- **观察 2**：现代存储栈（block device / file system / dedup / distributed）已维护丰富的块级 checksum/digest，且可通过用户态工具、系统 API 或自定义解析器提取（Table 1：dm-verity、fs-verity、[[BTRFS]]/[[ZFS]]、MeGA、[[HDFS]]、BlueStore 等）。
  - **依赖假设**：sync 涉及的文件确实存放在已启用 checksum 的存储后端上；管理员愿意承担 per-filesystem 配置成本（如 EXT4/F2FS 需显式 enable fs-verity）。
  - **可能失效场景**：裸块设备无 verity、旧式文件系统未开 checksum、对象存储直传（无本地 FS 元数据）、或 sync 源是内存/网络流而非持久化文件——此时 SkySync 退化为传统重算路径或根本无法启用。

- **观察 3**：[[CRC32C]] 等 XOR-friendly 多项式 checksum 满足线性组合性质，可用 storage-layer 固定块 checksum 通过 XOR + 零位追加推出 CDC 变长 chunk 的 weak checksum，只需对边界处差异字节做真算。
  - **依赖假设**：client/server 至少一方提供 CRC32C（或协议协商后统一算法）；storage-layer 块大小与 sync chunk 大小可通过对齐策略调和（FSC 跟 server 块大小，CDC 跟 client 块大小）。
  - **可能失效场景**：两端 checksum 类型完全不兼容且无法协商到共有算法；storage 块 checksum 与 sync 所需 strong hash（如 MD5 vs SHA-256）差异大时，strong checksum 仍须重算；非线性 hash（如某些加密 digest 无组合闭包）无法走组合路径。

- **假设 1**：存储层 checksum 在 sync 时刻与文件内容一致（fresh & correct）。
  - **证据强度**：**中**——论文在 BTRFS 上直接读 checksum tree，隐含信任 FS 一致性；但未讨论 checksum 陈旧（写后未 flush metadata）、静默损坏、或跨层拷贝后 metadata 未同步等运维场景。

- **假设 2**：chunk searching 的主要开销来自 rsync/dsync 的 16-bit hash code → 32-bit weak → strong 三级指针跳转，而非 hash 表本身内存占用。
  - **证据强度**：**强**——Figure 3 分解实验明确显示 searching 占 client/server 时间大比例；SkySync 用 CRC32C 直接派生 Cuckoo bucket 位置（Eq. 3–4）有清晰设计动机。

## 核心方法

SkySync 在 [[rsync]]/[[dsync]] 协议骨架上增强通信层，形成 **SkySync-F**（FSC）与 **SkySync-C**（CDC）两个变体，核心是把 delta generation 从「全量重算」改为「storage-layer 协作」。

**元数据提取（§3.1, §3.4）**：按存储类型分三路——(1) 用户态工具（fs-verity ioctl、btrfs-progs、zbd、cryptsetup dump dm-verity hash tree）；(2) 系统 API（HDFS NameNode 等）；(3) 自定义解析（MeGA dedup fingerprint）。作者称 fs-verity 对 EXT4/F2FS 顺序/随机读写延迟增加 ≤4.7%，吞吐几乎不变；metadata extraction 耗时（1.8–119.2s）远低于直接重算 checksum（26–246s），且占 BTRFS 总 sync 时间仅 **0.11%–7.14%**。

**Weak checksum 组合（§3.2.1）**：对 CDC 场景，storage 以 4KB 固定块 $C_F$ 存 CRC32C，CDC 切出变长块 $C_R$。利用 $\text{CRC}(S)=\text{CRC}(A\cdot 0^{|B|})\oplus\text{CRC}(0^{|A|}\cdot B)$，从相邻 $C_F$ 的 checksum 推出 $C_R$ 的 CRC32C；滚动计算时复用上一 chunk 边界字节 $x$ 的 CRC，仅对新差异字节 $y$ 做真算。FSC 场景下若 client 4KB、server 8KB，可用两个 4KB checksum XOR 组合出 8KB checksum。该思路可泛化到任何支持线性组合的 polynomial checksum。

**轻量化 chunk searching（§3.2.2）**：预分配 flat-array [[Cuckoo-Hashing]] 表，每桶 4 条目（负载因子 0.85–0.91 前不溢出）。主/备 bucket 位置直接从 chunk CRC32C 派生（$P_1=\text{CRC}\bmod 2^l$，$P_2=P_1\oplus 2^{l-1}$），省去独立 hash 函数与 16-bit 中间层。相比 Adler32/FastFP，CRC32C 碰撞率更低，减少每桶遍历。

**协议协商（§3.3）**：client/server 交换 chunk size 与 checksum type；FSC 对齐 server 块大小，CDC 对齐 client chunking 参数；weak 默认 CRC32C，strong 优先 SHA-256/SHA-1 且跟 server 侧算法以减少 server 重算。HTTP(S) 承载增强后的 rsync/dsync 数据流（checksum list → matching tokens → delta bytes）。

**实现**：FSC 基于 librsync（~1100 LOC C++）；dsync 原版不开源，作者自实现 FastCDC 版（~1800 LOC）作 baseline；CDC-SkySync 再加 ~1600 LOC。开源：https://github.com/skysync-project/skysync

## 设计取舍

- **收益 vs 部署复杂度**：用 storage metadata 换 CPU，但要求 per-FS 配置（fs-verity enable、btrfs checksum 类型选择）或维护 custom parser（MeGA）。**边界**：在已运营 checksum-rich 存储的云备份/跨云复制场景优雅；对「任意 endpoint 随便一个目录」的通用 rsync 替代则变脆。

- **兼容性 vs 性能**：保留 rsync/dsync 的 checksum list / matching token / delta 数据结构，网络流量与 baseline 几乎相同（略增因 SHA-256 strong checksum 比 MD5/SHA-1 更长）。**边界**：不牺牲 delta 正确性，也不减少 WAN 流量，纯优化 compute path。

- **Checksum 算法统一 vs 异构存储**：协议层强制协商到共有 weak/strong 算法，可能让一端放弃更优的本地 hash。**边界**：双端存储异构且 checksum 类型完全不交时，协商失败后的 fallback 行为论文未详述。

- **Cuckoo 表预分配 vs 动态扩容**：高负载因子换少 resize，但内存按 chunk 数预配；极大文件 chunk 数爆炸时内存 footprint 论文未量化。

## 实验与结果

- **微基准（10MB/100MB，insert/cut/inverse/无修改）**：SkySync-F client 比 rsync **1.2×–2.0×**，计算开销降 **32.1%–64.9%**；SkySync-C client 比 dsync **1.3×–1.7×**，开销降 **25.7%–42.3%**。Server 端计算开销最高降 **89.3%**（相对 rsync/dsync）。
- **总同步时间**：小修改（10MB 文件 <2KB、100MB 文件 <128KB）SkySync-F 总时间比 baseline 降 **26.7%–72.1%**；100Mbps 与 500Mbps 带宽下趋势一致。
- **时间分解（100MB insert）**：SkySync-F checksum 计算降 **23.4%–88.3%**，searching 降最高 **61.3%**；SkySync-C 计算降 **24.5%–33.6%**，searching 降 **65.7%**。HW 加速三方法差距缩小至 ≤10.8%，SkySync 仍领先。
- **真实数据集（Chat/Ubuntu/Nutsnap/Enwiki/Kernel，25–221GB）**：多线程（1/2/4/8）下 SkySync **1.2×–1.5×** 于 rsync/dsync；单线程 client+server 时间降 **19.2%–43.7%**。
- **网络流量**：与 rsync/dsync 基本一致（Figure 17）；Ubuntu 数据集修改率高故 delta 流量大，与 sync 算法无关。
- **Metadata extraction**：BTRFS/MeGA 远快于 EXT4/F2FS（fs-verity 路径更重）；提取时间仍显著低于重算。

## Critical Analysis

### 论证链条

观察（compute 占 95%）→ 设计（复用 storage checksum + 组合 + 简化 searching）→ 结果（1.1×–2× 加速、流量持平）链条整体闭合。最强证据在 **server 端**（最高 89.3% 开销削减），与「server 需对 old file 全量算 checksum」的 rsync/dsync 工作流高度吻合。较弱环节是 **client 端 CDC 路径**：weak checksum 组合减少计算，但 CDC rolling boundary 检测仍须扫描文件内容，dsync 上 25%–42% 的改进幅度也小于 FSC 路径，说明「metadata 复用」对 client 侧 CDC 只解决了一半问题——与同作者 [[ParaSync-FAST26|ParaSync]] 关注的并行 chunking 瓶颈形成互补而非替代。

论文将结论外推到 Sky computing 跨云场景，但实验仅在阿里云双数据中心 VM（BTRFS + EBS）完成；「多云异构存储」靠协议协商逻辑支撑，缺少 AWS/GCP 与阿里云混搭的端到端实测。

### 假设压力测试

- **Checksum 新鲜度**：若文件刚写入、FS checksum tree 尚未持久化，或副本跨层拷贝（如 S3 → 本地盘）后 storage metadata 缺失，SkySync 的正确性依赖重算 fallback——论文未给出 fallback 路径的性能与正确性保证。
- **安全与信任**：复用 storage-layer digest 意味着 sync 正确性绑定 FS 完整性机制；对 encrypted-at-rest 且 checksum 覆盖密文（非明文）的场景，delta 语义是否与 rsync 一致需逐案验证——论文未讨论。
- **小规模修改 + 超大文件**：rsync client 时间随修改规模增长（Figure 3），SkySync-F 在「文件相同」时最快；但对「TB 级文件、KB 级修改」的 tail latency，metadata extraction（最高 119s on Kernel dataset）是否可摊销、是否阻塞首次 sync，论文只报告占比 ≤7.14%，未测 cold-cache 尾延迟。
- **dsync baseline 公平性**：原版 dsync 不开源，作者自实现 ~1800 LOC 并称「as efficient as the original」——这是关键 baseline，但缺少与开源 NetSync 等第三方实现的交叉验证，削弱「2×」claim 的绝对可信度。

### 实验可信度

- **Workload 代表性**：五个真实数据集（聊天日志、Ubuntu 镜像、网盘快照、Wikipedia dump、Kernel 源码）覆盖 backup/sync 典型场景，优于纯微基准；但缺少数据库页文件、VM 镜像块设备直读、高频小文件目录树等生产形态。
- **Baseline 强度**：对比 rsync + 自实现 dsync，均加 HW 加速变体，ablation 隐含在 FSC vs CDC 两变体及 Figure 13 分解中，但**没有**「仅组合 checksum、不换 hash 表」「仅换 hash 表、不重算 checksum」的独立 ablation，难以量化各设计贡献占比。
- **Metric 覆盖**：吞吐/时间/流量/开销分解充分；**未测** tail latency 分布、多租户并发 sync 时的 CPU 争抢、metadata extraction 失败率、或 sync 后内容一致性 fuzz test。

### 系统性缺陷

- **运维成本**：fs-verity per-file enable、BTRFS checksum 算法选择、MeGA custom parser 均把复杂度推给管理员；论文承认 custom function 有 **significant maintenance burden**，但未估人力。
- **尾延迟与隔离**：多线程实验把文件/区域分给独立线程，但未讨论与生产 workload 混部时的 cgroup 干扰或 sync 突发对同机服务的冲击——论文未讨论。
- **故障恢复**：HTTP 协议、中途断线重传、部分 metadata 提取失败时的行为——论文未讨论。
- **可观测性**：无 sync pipeline 各阶段 latency tracing 的生产级 instrumentation 设计——论文未讨论。

## 局限与 Future Work

- **局限 1**：metadata 提取目前覆盖 Table 1 所列系统，但大量对象存储（S3/OSS 直读）与无 checksum 的旧式部署仍需全量重算；custom parser 随存储版本演进需持续维护。
- **局限 2**：主实验环境单一（BTRFS + 阿里云双 DC），对 EXT4/F2FS fs-verity 路径仅测了 extraction 耗时，未测完整 SkySync 端到端加速。
- **局限 3**：与硬件加速正交但未叠加测量「SkySync + AVX + ParaSync 式并行」的上界；client 侧 CDC rolling 瓶颈仍残留。
- **Future work 1**（论文自述）：扩展 metadata extraction 到更多存储系统——可客观验证方式为在 BlueStore/HDFS/S3 后端各跑一轮端到端 benchmark 并报告 extraction 占比。
- **Future work 2**（推断）：与 [[ParaSync-FAST26|ParaSync]] 的并行 chunking / streaming matching 叠加，量测「metadata 复用 + 并行化」是否接近理论下限；需在同一真实数据集上测 A/B/AB 组合。
- **Future work 3**（推断）：在 <10Mbps 或跨洲高 RTT 链路上重测，明确 SkySync 的 breakeven 网络条件，避免把 compute-bound 结论误用到 bandwidth-bound 部署。

## 相关

- **相关概念**：[[CRC32C]]、[[Content-Defined-Chunking]]、[[Cuckoo-Hashing]]、[[Delta-Sync]]、[[Sky-Computing]]、[[Rolling-Hash]]
- **同类系统**：[[rsync]]、[[dsync]]、NetSync、WebR2sync+、DeltaCFS、PandaSync、[[ParaSync-FAST26|ParaSync]]
- **同会议**：[[FAST-2026]]
- **对比**：[[ParaSync-FAST26|ParaSync]] 解并行化与 pipeline 依赖，SkySync 解 checksum 冗余计算；二者同作者、同会议，优化正交