---
type: paper
name: Pallas
full_title: Towards Optimal Rack-scale µs-level CPU Scheduling through In-Network Workload Shaping
authors: [Xudong Liao, Han Tian, Xinchen Wan, Chaoliang Zeng, Hao Wang, et al.]
venue: ATC
year: 2025
tags: [rack-scheduling, programmable-switch, tail-latency, microservices, cFCFS]
source_pdf: "[[atc2025-liao.pdf]]"
source_md: "[[atc2025-liao]]"
---

# Towards Optimal Rack-scale µs-level CPU Scheduling through In-Network Workload Shaping (ATC 2025)

> **一句话总结**：在 ToR 交换机做 application-aware workload shaping 把混合请求拆成同质组，配合简单 cFCFS 内部调度，把 µs 级服务尾延迟比 RackSched 降低 8.5×（中负载）至两个数量级（高负载）。

## 问题

µs 级服务（Memcached、RocksDB、TPC-C）SLO 严苛。SOTA RackSched 用 JSQ-based inter-server LB + Shinjuku 服务器内调度，在混合长短请求时有两个问题：(1) JSQ 完全 application-agnostic，10 µs RTT 拿到的队列长度已过期，导致跨服务器负载倾斜（实测 ~3× tail slowdown 差距）；(2) 每台服务器都要处理长短混合，DARC、TS、cFCFS 等都无法消除 head-of-line blocking，相比理想 PS 慢 ~50×。

## 核心方法

Pallas 把调度拆为三层：

- **Workload Shaper (ToR 交换机)**：根据 packet 头中 type 字段（Memcached/Redis/RPC 自然携带）+ 服务器回写的实际执行时间（EWMA 滑动平均），离线用 customized k-means 生成多组 group mapping policy，再用 99% tail latency 仿真选最优。例如 TPC-C 的 Payment+OrderStatus 一组、Delivery+StockLevel 一组、NewOrder 单独一组。
- **Intra-group Load Balancer**：weighted round-robin 按各服务器在该 group 的预留 core 数派发，避免实时跨 RTT 拿状态。
- **Intra-server Scheduler**：因为输入已同质化，用最简单的 cFCFS（Wierman 等理论证明确定性轻尾负载下 cFCFS 是 tail-optimal）；少数混合服务器仍用 DARC。
- **Long-term workload change adaptation**：10ms 粒度监控偏差，超过阈值 δ=10 时增量更新策略表，并用 **request bouncing**（让短请求把长请求队列里的 pending 长请求弹回交换机）防止过渡期 HoL。
- **Short-term burst handling**：20µs 粒度检测 burst，用 **request cloning** 把过载短请求克隆到欠载组，目标服务器忙时直接 drop（no-regret），用全局 unique req.index 过滤重复响应。

P4 实现 763 行（占 Tofino SRAM 2.8% / SALU 10.4%），control-plane Python 1067 行；server 基于 [[Persephone-SOSP23|Perséphone]]。深度细节见 [[atc2025-liao]]。

## 关键结果

- Bimodal（10 µs / 100 µs）中负载下 P99 比 RackSched 低 8.5×；TPC-C 200 µs SLO 下吞吐高 1.7×。
- Port RocksDB（50% GET / 50% SCAN）高负载下尾延迟比 RackSched 低两个数量级（0.22–0.23 Mrps）。
- Trimodal 1200 µs SLO 下吞吐 2.0× 于 RackSched-DARC。
- 比 R2P2 (JBSQ)、Draconis (in-switch cFCFS)、Horus 都更优。
- request bouncing + burst handling 在动态 workload 下让 P99 短请求平稳；burst handling 单独贡献 6.1× 平均尾延迟改进。
- 开源 https://github.com/HKUST-SING/pallas

## 相关

- **相关概念**：[[Tail-Latency]]、[[Load-Balancing]]、[[Programmable-Switch]]、[[Head-of-Line-Blocking]]
- **同类系统**：RackSched、Shinjuku、Perséphone (DARC)、R2P2、Draconis、Horus
- **同会议**：[[ATC-2025]]
