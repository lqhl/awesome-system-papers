---
type: paper
name: TGW
full_title: "TGW: Operating an Efficient and Resilient Cloud Gateway at Scale"
authors: [Yifan Yang, Lin He, Jiasheng Zhou, Xiaoyi Shi, Yichi Xu, et al.]
venue: ATC
year: 2025
tags: [cloud-gateway, dpdk, load-balancing, networking, production-system]
source_pdf: "[[atc2025-yang-yifan.pdf]]"
source_md: "[[atc2025-yang-yifan]]"
---

# TGW: Operating an Efficient and Resilient Cloud Gateway at Scale (ATC 2025)

> **一句话总结**：腾讯云运行 8 年的 DPDK 软件云网关，单节点 SpMM 转发能力是 Tripod 的 2.9×、4 秒内零丢包跨集群迁移、tens of Tbps 真实流量下最差丢包率 10⁻⁷~10⁻⁴、多年保持 100% 可用性。

## 问题

腾讯云的 killer service 是在线游戏和直播，对延迟/抖动/丢包远比电商/搜索严苛（在线游戏需 <100ms RTT，网关须 µs 级延迟）。云网关已从 NAT 演化成集弹性公网接入 + 云负载均衡为一身的复杂网络功能集合，需同时满足 efficient packet forwarding、scalable state management、fast failure recovery。可编程交换机（Tofino）有线速优势但供应链风险大（Intel 已停产 Tofino），DPU/FPGA/smartNIC 成本高，VPP 性能不够，现有学术系统又只在 lab 验证过。

## 核心方法

- **架构**：解耦 TGW-EIP（区域级无状态弹性公网，RTC 模型）和 TGW-CLB（AZ 级有状态负载均衡，two-stage pipeline，dispatcher:processor=1:2）；模块化 LD/operator/orchestrator/probers/brains。
- **DPDK 转发优化**：batch hash lookup（bucket size 64B 对齐 cache line + prefetch 第一个 node）使 cache miss 从 20% CPU 降到 5%；针对 IP-pair / QUIC-aware 调度的灵活 dispatcher 替代 NIC RSS。
- **Live state migration**：90% 状态先迁移再切 BGP；新集群作 LD proxy 把未知流转发到旧集群所有 LD；利用 backend vSwitch 的 source IP learning 加速收敛（出方向流量自动直连新集群）；migration agent 按 VIP 重组状态避免 240M states 跨核聚合开销。
- **故障容灾**：Intra-AZ Active-Active（共享状态表，BGP+BFD 毫秒级故障切换）+ Inter-AZ Active-Standby（不同 IP 段互为热备，用不同前缀长度宣告）+ Inter-region DNS 重路由；多周期 state synchronization（≥3s 才同步、4 分钟批次 + 2 秒导出）；Decentralized migration 把异常 VIP 拆分到 k 个 buffer set 缩小 blast radius。
- **Taint-based telemetry**：TCP 半握手探测 + Trace Points / Drop Points + 分布式 brain 流式分析，1 分钟内自动定位故障。

深度细节回 [[atc2025-yang-yifan]]。

## 关键结果

- Testbed：单节点 TGW-CLB 在 512B 包下吞吐是 Tripod 的 2.9×（99% CPU）、最大 96.8 Gbps（1024B），平均处理延迟 66-105 µs。
- 双集群迁移：8M 连接 4 秒内迁移完成且零丢包。
- 真实环境：tens of Tbps 流量、worst case 丢包率 10⁻⁷~10⁻⁴；130M 连接 13s 同步完，单 LD 故障流量秒级被其他 LD 接管。
- 大规模 VIP 迁移：1371 VIP / 130M 连接，95.6% 在 20s 内迁完。
- 30+ 个 region 部署，单 region 上百集群、上千机器；多年 100% 可用性。

## 相关

- **相关概念**：[[DPDK]]、[[Load-Balancer]]、[[ECMP]]、[[BGP]]
- **同类系统**：Sailfish、Luoshen、Ananta、Maglev、Tripod
- **同会议**：[[ATC-2025]]
