# Unleashing Zoned UFS: Cross-Layer Optimizations for Next-Generation Mobile Storage

**作者**：Jungae Kim (SK hynix), Jaegeuk Kim (Google), Kyu-Jin Cho (Seoul National University), Sungjin Park, Jinwoo Kim, Jieun Kim, Iksung Oh (SK hynix), Chul Lee, Bart Van Assche, Daeho Jeong, Konstantin Vyshetsky (Google), Jin-Soo Kim (Seoul National University)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/kim-jungae
**源文件**：[[fast2026-kim-jungae.pdf]]

---

## 一、背景

智能手机已成为全球超 58 亿用户的主要计算平台，存储性能直接影响用户体验。Universal Flash Storage (UFS) 是当前移动存储的事实标准，提供高带宽、低延迟和高能效。然而，随着设备容量从 2017 年的 32 GB 增长到 2024 年的 1 TB，UFS 控制器中用于 L2P (Logical-to-Physical) 映射表的 SRAM 始终停留在约 1 MB，形成了严重的可扩展性瓶颈。传统 UFS (CUFS) 采用页级映射，1 TB 设备需要约 1 GB 映射表，远超片上 SRAM 容量，频繁的 map cache miss 导致随机读性能不稳定。

Zoned UFS (ZUFS) 作为 JEDEC 标准的一部分于 2023 年发布，将 zoned storage 模型引入 UFS 接口，通过强制 zone 内顺序写入，将映射粒度从页级提升到 zone 级，大幅缩小映射表（1 TB 仅需 8 KB），同时消除设备级 GC，降低写放大。

---

## 二、要解决的问题

尽管 ZUFS 概念上是 UFS 的自然扩展，但在商用智能手机中部署面临三大非平凡挑战：

1. **写缓冲区管理**：ZUFS 需要至少 6 个并发 open zone（F2FS 按数据冷热分离），每个 zone 的 superpage 编程需要 768 KB 缓冲区，6 个 zone 加上 conventional LU 共需 7 × 768 KB = 5,376 KB SRAM，远超移动设备的 SRAM 预算。朴素设计导致频繁的未对齐 flush 和缓冲区抖动。

2. **端到端写入顺序保证**：ZUFS 要求 zone 内严格顺序写入，但移动设备激进的电源管理策略（如 clock gating）、block layer 的 requeue 机制、mq-deadline 调度器的 corner case（stale next_rq 指针、FUA 请求绕过序列化、I/O 优先级重排）都可能悄然破坏写入顺序。

3. **大 zone 引发的 GC 开销**：ZUFS 的 zone 大小为 1,056 MB（对齐 superblock 粒度），导致 F2FS 的 section 级 GC 每轮需迁移大量有效数据，可分配 section 数量减少，前台 GC 更频繁触发，严重影响用户 I/O。

对 10,000 台真实智能手机的调研显示：约 30% 设备碎片化水平超过 0.7，即使在低利用率下也存在严重碎片化；碎片化超过 0.8 时写延迟急剧恶化，最差达 2 s/MB。

---

## 三、洞察与设计

**关键洞察**：ZUFS 的性能潜力不能仅通过设备层或主机层单独实现，必须跨越整个移动存储栈（设备固件、SCSI/UFS 驱动、block layer、F2FS、Android 框架）进行协同优化。具体而言：(1) 写缓冲区可以在 zone 间以细粒度 slot 动态共享，而非静态分配；(2) 电源管理和 I/O 调度中的顺序违反可以通过修改 SCSI core 和 UFS driver 来消除；(3) 大 zone 的 GC 开销可以通过分阶段的主动式后台 GC 来摊销。

### 4.1 ZUFS 设备架构

设备由多个 TLC NAND die 组成，每个 die 含 4 个 plane。Zone 跨 die 和 plane 聚合 block，有效 zone 大小 1,056 MB。控制器维护 Zone Mapping Table (ZMT，每条 8 字节：4 字节起始物理地址 + 4 字节有效数据长度) 和 Zone Mapping Log (ZML)，全部可驻留在 SRAM 中。

### 4.2 Zone-Aware Buffer Management (ZABM)

核心组件是 Scatter-Gather Buffer Manager (SGBM)，一个专用硬件控制器模块：
- 将 SRAM 划分为 4 KB slot，维护 per-zone slot table
- 写请求到达时分配空闲 slot，追加到对应 zone 的 slot table
- 只要凑够一个 die 的编程单元 (192 KB) 就立即 flush，无需等待完整 superpage (768 KB)
- 繁忙 zone 可动态获取更多 slot，空闲 zone 仅保留最小缓冲区
- 硬件开销仅占控制器芯片面积约 0.4%

相比 ZMS 的 IOTailer 方案（需要主机侧 I/O 整形、依赖未标准化的设备几何信息），ZABM 完全在设备内部完成，无需主机侧修改。

### 4.3 端到端写入顺序保证

在多个层次修复顺序违反：
- **UFS driver**：用同步 ungating 机制替代原有的 requeue 处理，确保 clock gating 恢复后按原始顺序 dispatch
- **mq-deadline 调度器**：修复 stale next_rq 指针、FUA 请求绕过排序路径、I/O 优先级导致 zoned write 乱序等 corner case
- 所有修复已合入上游 Linux 内核

### 4.4 主动式垃圾回收

引入三阶段后台 GC 策略，通过 7 个可调参数控制：
- **No-GC 阶段**：空闲 section 比例 > 60%，禁用后台 GC
- **Normal-GC 阶段**：启用后台 GC，使用 cost-benefit 算法，每轮扫描 3 个 segment
- **Boosted-GC 阶段**：空闲 section < 25%，切换为 greedy 算法，扫描窗口放大 5 倍

新增 reserved_segments 参数实现 segment 级（而非 section 级）OP 空间预留（默认 6336 segment，即 6 个 open zone 所需 segment 数的两倍）。ZUFS 消除设备级 GC 后释放的 OP 空间回馈给 F2FS，用于文件系统级 GC。用户读请求到来时立即暂停后台 GC，优先保证读响应。

---

## 四、实现细节

- **平台**：Google Pixel 10 Pro，12 GB LPDDR5X SDRAM + 512 GB ZUFS
- **软件栈**：Android OS 16，Android kernel 6.6，F2FS（ZUFS 以纯 LFS 模式挂载）
- **基线对比**：同一硬件上配置 conventional LU 覆盖全部存储容量作为 CUFS 基线
- SGBM 硬件模块仅占控制器芯片面积 0.4%
- ZMT 每个 zone 8 字节，1 TB ZUFS 整个映射表仅 8 KB
- 所有 Linux 内核修改（block layer、mq-deadline、SCSI/UFS driver）和 F2FS GC 参数均已上游化并公开发布
- ZUFS 官方支持随 Android 16 和 Android Generic Kernel 6.6/6.12 发布

---

## 五、实验结果

### 基线 I/O 吞吐量（干净设备）

CUFS 和 ZUFS 在顺序读写和随机读写上性能相当，均可充分利用 NAND 带宽。

### 宽范围随机读

| 访问范围 | CUFS | ZUFS |
|---------|------|------|
| 4 GB | 两者相当 | 两者相当 |
| 256 GB | 性能显著下降（map cache miss） | 吞吐稳定 |

小 block size (< 128 KB) 时 ZUFS 优势明显，大 block size 时差距缩小。

### 写缓冲区管理效果

| 方案 | 吞吐量 |
|------|--------|
| ZMS (768 KB chunk) | 基线 |
| ZUFS (768 KB chunk) | 高于 ZMS（动态 slot 分配） |
| ZUFS (192 KB chunk) | 比 ZMS 高 26%（die 级 flush + 流水线） |

192 KB 与 768 KB chunk 在 ZUFS 上吞吐差异可忽略，证明细粒度 flush 无性能惩罚。

### 碎片化下的持续性能

| 指标 | CUFS | ZUFS |
|------|------|------|
| 写吞吐崩溃点 | ~90 轮（降至 ~100 MB/s） | 始终维持 > 200 MB/s |
| 读吞吐 | 第 90 轮后下降 ~35% | 全程稳定 |
| 碎片化控制 | 线性增长至耗尽 | 三阶段 GC 有效控制 |

### 应用级性能

| 测试场景 | CUFS | ZUFS | 提升 |
|----------|------|------|------|
| 原神资源验证+加载 | 35 秒 | 30 秒 | 14% |
| 照片滑动 jank rate | 0.60% | 0.26% | 57% 降低 |
| 照片平均碎片数/文件 | 46.29 | 2.31 | 20× 减少 |
| 照片 p99 帧时间 | 16 ms | 11 ms | 31% 降低 |

CUFS 下 66.3% 读请求为 4~8 KB（SSR 导致数据分散），ZUFS 大部分读请求 > 512 KB。

---

## 六、批判性分析

1. **CUFS 基线的公平性**：实验使用同一 ZUFS 硬件上的 conventional LU 模式作为 CUFS 基线，而非真正的 CUFS 设备。虽然作者声称"identical hardware conditions except for the storage mode"，但 ZUFS 硬件设计（如 SGBM 模块）可能在固件层面对 conventional LU 的表现有影响，无法完全排除硬件差异的干扰。

2. **碎片化实验的人工性**：碎片化通过"创建 32,768 个 128 KB 文件，隔一个删一个"的方式模拟，这与真实用户使用模式差异较大。虽然论文有 10,000 台真机的碎片化统计作为动机，但实验本身并未在真实碎片化状态下测量。

3. **GC 参数的通用性存疑**：7 个 GC 调参（如 60%/25% 阈值、greedy vs cost-benefit 切换）在 512 GB 设备 + 特定 zone 大小下调优，论文承认"allows system integrators to tune"，但未分析这些默认值在不同容量（128 GB~1 TB）和不同 zone 大小下的敏感性。

4. **应用级评估范围有限**：仅测试了原神资源验证（大顺序读为主）和照片滑动（碎片化随机读）两个场景。缺少对数据库密集型 App（如微信、SQLite 频繁 fsync）、后台多任务并发 I/O 等关键移动场景的评估。

5. **写放大因子未量化**：论文多次提及 ZUFS 降低 WAF 是核心优势，但实验部分没有直接测量和报告 ZUFS vs CUFS 的 WAF 数值，这是一个明显的遗漏。

6. **能耗和热控未报告**：移动设备的功耗和温度极其关键，论文背景部分强调了 1~1.5W 的功耗约束，但评估中完全没有能耗对比数据。

---

## 七、AI Infra / MLSys 视角

1. **端侧 AI 推理的存储瓶颈**：论文提到 on-device AI（实时图像增强、语音识别、个人助手）是移动存储压力增长的重要推动力。ZUFS 的稳定随机读性能对端侧 LLM 推理（大模型权重加载）和 RAG（向量数据库检索）具有直接价值——这些场景需要在大范围地址空间上进行随机读，正好命中 CUFS 的 map cache miss 问题。

2. **Zoned storage 思想在 AI 系统中的迁移**：ZUFS 的核心思路——通过限制写入模式来简化元数据管理和消除 GC——可以迁移到 AI 训练的 checkpoint 存储和推理的 KV cache 持久化。这些场景天然以 append-only 或顺序写为主，非常适合 zoned 模型。

3. **跨层协同优化的方法论价值**：ZUFS 的成功说明存储栈优化不能只在单一层面进行。AI Infra 领域同样面临类似问题——GPU 显存管理、NVLink 通信、存储 I/O 之间需要跨层协调，但目前大多数工作仍在单一层面优化。

4. **可跟进的方向**：
   - 端侧 LLM 权重的 zoned storage 感知加载策略（利用 zone 的顺序性优化 prefetch）
   - 训练 checkpoint 和推理 KV cache 在 zoned SSD 上的放置策略
   - SGBM 式的动态缓冲区共享机制应用于 GPU HBM 中多 tenant 的显存分配

---

## 八、总结

本文是 ZUFS 在商用智能手机（Google Pixel 10 Pro）上的首次部署实践，通过设备侧动态写缓冲区管理 (ZABM/SGBM)、跨 block layer 和 UFS driver 的端到端写入顺序保证、以及三阶段主动式后台 GC 三项跨层优化，解决了 ZUFS 从标准走向量产的关键工程挑战。评估显示 ZUFS 在碎片化条件下维持 2× 以上写吞吐优势、稳定的随机读性能，并在应用层带来 14% 的游戏加载提速和 57% 的滑动 jank 降低。该工作展示了 industry-wide（SK hynix + Google + SNU）协作将研究成果转化为生产系统的范例，所有改动已上游化至 Linux 内核和 Android 框架。主要局限在于评估覆盖场景有限，WAF 和能耗等关键指标缺失。
