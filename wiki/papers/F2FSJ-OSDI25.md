---
type: paper
name: F2FSJ
full_title: "Decentralized, Epoch-based F2FS Journaling with Fine-grained Crash Recovery"
authors: [Yaotian Cui, Zhiqi Wang, Renhai Chen, Zili Shao]
venue: OSDI
year: 2025
tags: [filesystem, journaling, f2fs, crash-recovery, mobile-storage]
source_pdf: "[[osdi25-cui.pdf]]"
source_md: "[[osdi25-cui]]"
---

# Decentralized, Epoch-based F2FS Journaling with Fine-grained Crash Recovery (OSDI 2025)

> **一句话总结**：F2FSJ 为 out-of-place 的 F2FS 首套 ordered journaling：只记 metadata diff、per-inode 分散日志、epoch 解耦 data/control 平面，checkpoint 时间最高降 4.9×、延迟降 35%、crash recovery ratio 优于默认 60s checkpoint（最多少丢 9.1% 数据）。

## 问题与动机

F2FS 广泛用于 Android，但靠 **粗粒度 checkpoint** 恢复：触发时阻塞读写，最坏 checkpoint 延迟 293 ms；默认 60s 间隔导致 crash 间最多丢 9.1% 数据/metadata；fsync 不触发 checkpoint，已刷盘数据仍可能丢。JBD2/EXT4 式 journaling 不能直接套用——F2FS inode 位置随 out-of-place update 变化，只 journal inode 无法恢复一致 NAT/SIT/SSA。

## 关键观察 / 隐含假设

- **观察 1**：F2FS 崩溃不一致主要来自 in-memory NAT/SIT/SSA 与 inode 的新 LBA 映射未落盘；需 journal **metadata 变更**而非整页，并覆盖相关 filesystem metadata。
  - **依赖假设**：ordered mode：data flush 严格先于 metadata commit。
  - **可能失效场景**：writeback/data journal 模式未实现；roll-forward + 无序 IO 栈仍可能不一致（论文指出 F2FS 原有问题）。
- **观察 2**：JBD2 中心化 transaction + j_list_lock 在 metadata 密集 benchmark 占 journaling 时间 25%–30%。
  - **依赖假设**：per-inode log list 可把锁争用摊到 inode 粒度。
  - **证据强度**：强——filebench mkdir/rmdir/create/unlink 对比 JBD2 时间分解。
- **假设 1**：out-of-place 特性使 fast-forward-to-latest apply 安全——旧版本 on-disk 不被覆盖，可按 epoch 顺序重放。
  - **证据强度**：中——依赖 page flag 阻止 page cache 过早刷盘。

## 核心方法

1. **change-based journaling**：只记录 filesystem/file metadata 字段变更。
2. **decentralized per-inode log list**：SIT/NAT/SSA 相关变更挂到对应 inode。
3. **epoch + data/control 解耦**：data plane 写 per-inode list；control plane 只注册 inode 到 epoch；commit 当前 epoch 时可立即开新 epoch，消除 JBD2 式 period transfer 等待（7%–16% journaling 时间）。
4. **fast-forward-to-latest apply**：同 metadata 跨 epoch 多次变更合并为一次刷盘。

约 3000 行 C 基于 Linux 5.15 F2FS。

## 设计取舍

- **取舍 1**：仅 ordered journal mode（与 EXT4 默认一致），不追求 writeback 性能。
- **取舍 2**：apply 路径复杂度换 checkpoint 阻塞减少。
- **边界条件**：极高 metadata churn 时 journal 体积与 apply 成本上升。

## 实验与结果

- vs F2FS checkpoint：checkpoint 时间最高 4.9× 缩短；端到端延迟最高 -35%。
- recovery ratio：优于 60s checkpoint（最多 9.1% loss → F2FSJ 更细粒度）；对比 1s checkpoint 仍更快且 loss 更低。
- filebench 四类密集 metadata 工作负载；含 ARM 嵌入式板结果（见 source_md §5.7）。

## Critical Analysis

### 论证链条

checkpoint 阻塞+粗恢复 → OOP 使 JBD2 不适用 → 分散+epoch+diff journal → 微基准与 recovery 改善。链条在 Android/F2FS 主路径闭合；通用 writeback 未覆盖。

### 假设压力测试

- 若 workload 大量随机写大文件，journal apply 与 page flag 交互可能变复杂。
- 与 ZNS/FTL 协同、encryption 层论文未讨论。
- 缩短 checkpoint 间隔的运维策略是否与 F2FSJ 重复投资。

### 实验可信度

filebench + crash 实验直观；缺真实手机长时间 field study。与 JBD2 对比主要是说明动机，非声称替换 EXT4。

### 系统性缺陷

论文未讨论：journal 空间耗尽、恶意 fsync 风暴、与 f2fs gc 峰值叠加的 tail latency。

## 局限与 Future Work

- **局限 1**：仅 ordered mode；data journal/writeback 未支持。
- **局限 2**：实现与 upstream F2FS 合并成本未知。
- **Future work 1**：与 checkpoint 协同的自适应触发；加密/压缩 metadata journal。
- **Future work 2**：形式化验证 fast-forward apply 与 roll-forward 交互。

## 相关

- **相关概念**：Crash Consistency、Log-structured File System
- **同类系统**：F2FS、EXT4/JBD2、nilfs2
- **同会议**：[[OSDI-2025]]