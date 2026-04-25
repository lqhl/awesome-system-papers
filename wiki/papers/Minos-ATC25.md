---
type: paper
name: Minos
full_title: "Minos: A Lightweight and Dynamic Defense against Traffic Analysis in Programmable Data Planes"
authors: [Zihao Wang, Qing Li, Guorui Xie, Dan Zhao, Kejun Li, et al.]
venue: ATC
year: 2025
tags: [network-security, programmable-switch, traffic-analysis, p4, privacy]
source_pdf: "[[atc2025-wang-zihao.pdf]]"
source_md: "[[atc2025-wang-zihao]]"
---

# Minos: A Lightweight and Dynamic Defense against Traffic Analysis in Programmable Data Planes (ATC 2025)

> **一句话总结**：在 Tofino1 可编程交换机上实现 line-rate 包头加密 + 动态流交错调度 + 优先级 dummy 队列，把网站指纹攻击准确率压到 <20%，开销仅前任 1/10。

## 问题

加密流量分析（Website Fingerprinting、IoT Fingerprinting）通过 5 元组和包大小/方向特征推断用户访问的网站/设备/活动。已有防御缺陷：

- **Proxy 类**（IPsec、Shadowsocks）只提供身份匿名，不抗 per-flow / per-packet 的流量分析
- **Traffic morphing**（BuFLO、WTF-PAD、Tamaraw）抗指纹但带宽开销巨大（Tamaraw 199%）、扩展性差
- **Ditto** 在 P4 交换机上实现但用静态 traffic pattern、需 IPsec 网关协作、过 pipeline 两次

## 核心方法

Minos 在 Tofino1 上同时提供 identity anonymity + traffic anonymity，三个模块：

1. **Proxy Module**：用轻量 SPN 加密算法 PRINCE 替代 AES，配合 **Encryption Round Compression**——把 Sbox + matrix multiplication + key/RC XOR 融合到单一 4-bit→4-bit 查找表，使 PRINCE 的多轮加密能塞进 12-stage match-action pipeline；利用 PRINCE 的 α-reflection 让加密/解密共用同一组表，SRAM 减半
2. **Schedule Module**：维护 per-flow timestamp / queue ID / flow count / 上次队列分配等状态于 register，动态把同 destination IP 的不同 flow 交错到不同 queue（让 flow A 的包成为 flow B 的「dummy」），按 round-robin 方式严格调度
3. **Traffic Morphing Module**：当活跃流数量少时启用——用 **priority queue based dummy packet scheduling** 在数据面实时插入 dummy 包；Padding 子模块对包尺寸做填充

深度细节回 [[atc2025-wang-zihao]]。

## 关键结果

- 把 Website Fingerprinting 攻击准确率压到 **<20%**
- 带宽和延迟开销约为之前防御的 **1/10**
- 100 Gbps line rate（Tofino1 实测）
- 也适配 IoT Fingerprinting 防御

## 相关

- **相关概念**：[[RDMA]]
- **同会议**：[[ATC-2025]]
