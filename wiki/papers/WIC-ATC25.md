---
type: paper
name: WIC
full_title: "WIC: Hiding Producer-Consumer Synchronization Delays with Warp-Level Interrupt-based GPU Communications"
authors: [Jiajian Zhang, Fangyu Wu, Hai Jiang, Qiufeng Wang, Genlang Chen, Chaoyi Pang]
venue: ATC
year: 2025
tags: [gpu, synchronization, uvm, warp-scheduling, interrupt]
source_pdf: "[[atc2025-zhang-jiajian.pdf]]"
source_md: "[[atc2025-zhang-jiajian]]"
---

# WIC: Hiding Producer-Consumer Synchronization Delays with Warp-Level Interrupt-based GPU Communications (ATC 2025)

> **一句话总结**：把消费者 warp 上反复 polling producer 数据可用性的开销改成 UVM page-fault 触发的 warp-level 中断+换出，让其他可执行 warp 抢占资源跑起来，10 个跨设备通信应用平均加速 1.13×（C_H3D 30%+）。

## 问题

GPU 跨设备 producer-consumer 通信里，consumer kernel 要等 producer 把数据准备好。CUDA 没原生跨设备 semaphore，应用层只能用 sync flag 反复 atomicAdd polling。实测 10 个 benchmark：(1) consumer 端通信延迟 20–50%（C_H3D 高达 81.97%），producer 端 DMA 异步基本不阻塞；(2) polling 占 consumer 通信开销 60%+（C_H3D、G_KMN 超 90%），单次通信 polling 检查上百万到上千万次；(3) **关键洞察**——polling 启动时大量 thread 还没完成 C₁（独立计算），polling 抢占了它们的 SM 资源，让本可与同步重叠的计算被压住。

## 核心方法

**Warp-level Interrupt-based Communication (WIC)**：把 polling 替换为细粒度的 warp 中断，借 UVM page fault 机制实现，无需 GPU 硬件改动。

三个组件：

- **Interrupter**（GPU 上）：consumer warp 申请 producer 数据时，分配 PCM（Producer-Consumer Communication Medium）UVM page，让 warp 访问这些 host-side page 触发 page fault → warp 被 UVM driver 自动 stall，SM 资源让给其他 warp。用 segment tree O(log n) 找连续空闲 PCM page
- **Monitor**（host driver 上）：维护 Data Availability Bitmap (DAB) 与 Pending Faults Queue (PFQ)。捕获 PCM fault 后查 DAB；不可用就入 PFQ 等待，可用则唤醒 Activator。Producer 在另一 GPU 时，它写 PAT（Producer Availability Tag）触发 page fault，host 据此更新 DAB
- **Activator**（host 上）：把 producer 数据写入 PCM page，发 replay 信号让 stall 的 warp 复活；同时把上次的 PCM page 标 invalidate 回收（用 P/P' 配对页交替使用，确保 invalidate 时机不卡死）

WIC 完全在 UVM 内核驱动里实现，对应用层透明，程序员像调 syscall 一样 request producer data。深度细节回 [[atc2025-zhang-jiajian]]。

## 关键结果

- 10 个应用（CPU-GPU 4 个 + inter-GPU 6 个，覆盖 streaming/adjacent/scatter-gather/random × unidirectional/alternating/multiple/probabilistic 双维度通信模式）平均加速 1.13×
- C_H3D（halo 3D cube，通信密集）加速 30%+；C_CG、C_FE >20%
- WIC 把 consumer 端通信开销占比降约 20%，与 producer 端基本对齐
- G_BS（数据预生成、Scenario 1）下 WIC 略慢（多了 host-side overhead）；其他 9 个均改善

## 相关

- **相关概念**：[[GPU]]、[[UVM]]、[[Warp-Scheduling]]、[[Producer-Consumer]]、[[Page-Fault]]
- **同会议**：[[ATC-2025]]
