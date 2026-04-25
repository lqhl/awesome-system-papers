---
type: paper
name: PIMANN
full_title: "Turbocharge ANNS on Real Processing-in-Memory by Enabling Fine-Grained Per-PIM-Core Scheduling"
authors: [Puqing Wu, Minhui Xie, Enrui Zhao, Dafang Zhang, Jing Wang, et al.]
venue: ATC
year: 2025
tags: [anns, processing-in-memory, upmem, vector-search, scheduling]
source_pdf: "[[atc2025-wu-puqing.pdf]]"
source_md: "[[atc2025-wu-puqing]]"
---

# Turbocharge ANNS on Real Processing-in-Memory by Enabling Fine-Grained Per-PIM-Core Scheduling (ATC 2025)

> **一句话总结**：在 UPMEM PIM 上用每个 PU 的隐藏 control interface 实现 per-PU 细粒度总线仲裁 + persistent kernel + 动态副本调度，把 ANNS 吞吐相对 Faiss-CPU 提升 10.4×、相对 batching PIM 提升 2.4×。

## 问题

ANNS（IVFPQ 类）compute-to-memory 比接近 1:1，CPU/GPU 都受 memory wall 约束。UPMEM 提供 2,560 个 PU + 2 TB/s 带宽，但 strawman PIM ANNS 只达理论吞吐的 18.2%，PU 在 65% 时间空闲：

- **Inter-batch 利用率低**：UPMEM 的 DDR 总线被 CPU 和 PU 共享互斥，batching 范式下两 batch 间 PU 必须等 CPU 拷数据
- **Intra-batch 利用率低**：PU 间 share-nothing，热数据分布不均时 straggler PU 拖累整批

## 核心方法

PIMANN 的关键观察：**每个 UPMEM PU 都有一个未公开的 control interface**（原本用于发 launch/sync 命令），可被改造为细粒度总线仲裁通道，从而打破「kernel 启动后 PU 独占总线到结束」的假设。

1. **Persistent PIM Kernel**：系统初始化时启动一个长驻 kernel，PU 循环：从消息队列取请求 → 等 CPU 拷输入 → 切到 Running 算 distance → 切到 WaitCPUCopy → 等 CPU 取结果。eliminates inter-batch idle
2. **Hot Transfer 机制**：
   - **控制路径**：在 WRAM 上用 control interface link 实现消息队列（绕过 DDR 总线），存 query ID / 切换命令等小消息
   - **数据路径**：修改 UPMEM driver 让 CPU 在 PIM 运行时也能 mmap MRAM；建立变量符号→MRAM 偏移映射；用 coroutine 隐藏 CPU 总线获取等待
3. **Per-PU Query Dispatching**：用 selective replication 把热 cluster 在多 PU 上副本化，运行时按 PU 实时负载动态分发 query；支持 hotness shift 的 live data placement 调整

深度细节回 [[atc2025-wu-puqing]]。

## 关键结果

- 相对 Faiss-CPU 吞吐提升最高 **10.4×**
- 相对 batching paradigm 的 PIM ANNS 提升最高 **2.4×**
- 相对 Faiss-GPU 提升最高 **3.7×**
- 在 SPACE-1B 数据集（10 亿向量）上验证

## 相关

- **同会议**：[[ATC-2025]]
