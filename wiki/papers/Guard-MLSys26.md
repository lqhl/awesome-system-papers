---
type: paper
name: Guard
full_title: "GUARD: Scalable Straggler Detection and Node Health Management for Large-Scale Training"
authors: [Guanliang Liu, Abhinandan Patni, Congzhu Lin, Zoe Zeng, Jack Wittmayer, "et al."]
venue: MLSys
year: 2026
tags: [distributed-training, straggler-detection, node-health, grey-nodes, moe]
source_pdf: "[[ed3d2c21991e3bef5e069713af9fa6ca.pdf]]"
source_md: "[[ed3d2c21991e3bef5e069713af9fa6ca]]"
---

# GUARD: Scalable Straggler Detection and Node Health Management for Large-Scale Training (MLSys 2026)

> **一句话总结**：Guard 用在线训练指标 + 离线 node sweep 闭环检测「grey nodes」（过健康检查但持续降速的机器），在万卡 foundation model 预训练上把 MFU 提升最高 **1.7×**、step time 方差从 20% 压到 1%、平均 step time 从 17s 降到 10s。

## 问题

大规模 LLM 训练依赖 data / tensor / pipeline / expert 混合并行，频繁 NCCL collective 让最慢节点 gate 全局进度。比 fail-stop 更棘手的是 **grey nodes**：NCCL test、GPU burn-in 能通过，但在真实长时 mixed compute–communication workload 下持续降速。根因横跨硬件（thermal throttling、NIC 降级、NVLink 不稳）、系统（CPU 带宽、NCCL 透明 reroute）和 [[MoE]] 动态负载，传统短测很难提前发现。

## 核心方法

Guard 把 **training step time** 作为主信号，硬件/网络指标作辅助，分两层：

**在线监控**：持续采集 GPU 温度、频率、功耗、利用率、NIC error/retransmit、有效带宽等，相对同 job peer baseline 做多信号、多窗口过滤；按影响分级响应（无影响→继续观察；~10% 持续慢→checkpoint 后处理；≥20%→立即换节点重启）。

**离线 node sweep**：
- **Single-node sweep**：测 per-GPU sustained FLOPS 与 NVLink 对称性，暴露 burn-in 漏掉的 intra-node 不对称
- **Multi-node sweep**：在 2/4/8 节点配置下压 cross-node collective，复现真实同步模式
- 事件驱动触发（在线告警或维修后），1–2 小时即可筛出 persistent degradation

**Triage workflow**：GPU/NIC 错误分级修复；一周内三次入 triage 直接终止节点。部分监控工具已开源到 Amazon fkat。

## 关键结果

- 生产级 foundation model 预训练（数千 GPU、数月）：**MFU 最高 1.7×**；run-to-run step time 方差 **20% → 1%**；平均 step time **17s → 10s（~70% 效率提升）**
- Ablation：仅在线监控 MTTF +14%、人工介入间隔 −40%、MFU 10%→14%；加 offline sweep 后 MTTF 再 +82%、MFU 14%→17%
- 修复 degraded NIC path 可把单 step 从 8.7s 降到 8.4s；错误 CPU 调度可带来 ~20% 训练减速
- 2-node sweep 已能捕获多数 inter-node 通信退化，成本低于全集群周期性 sweep

## 相关

- **相关概念**：[[Tensor-Parallelism]]、[[Pipeline-Parallelism]]、[[MoE]]、Straggler Detection
- **同类系统**：NCCL tests、GPU burn-in、SuperBench、Megascale grey-node 观测
- **同会议**：[[MLSys-2026]]