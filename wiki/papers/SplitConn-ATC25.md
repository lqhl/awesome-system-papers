---
type: paper
name: SplitConn
full_title: "Internet Connection Splitting: What's Old is New Again"
authors: [Gina Yuan, Thea Rossman, Keith Winstein]
venue: ATC
year: 2025
tags: [networking, congestion-control, bbr, quic, performance-enhancing-proxy]
source_pdf: "[[atc2025-yuan.pdf]]"
source_md: "[[atc2025-yuan]]"
---

# Internet Connection Splitting: What's Old is New Again (ATC 2025)

> **一句话总结**：经实证测量重新评估 PEP（performance-enhancing proxy）相关性——BBRv1 不需要拆分但 BBRv2/v3 在丢包路径上反而比 CUBIC 受益更多，且不同 QUIC 实现 CUBIC/BBR 行为差异巨大，结论是连接拆分远没有过时。

## 问题

1990 年代起，电信运营商在卫星和无线链路上部署透明 TCP PEP——拆分一条端到端 TCP 连接为两段，各自独立 ACK/重传，缓解长 RTT + 丢包对 loss-based 拥塞控制（CUBIC）的伤害。两件事让 PEP "看似过时"：(1) BBR 模型化拥塞控制不把丢包当主信号、于 2016 推出后业内传言 PEP 部署锐减；(2) QUIC 端到端加密让透明 PEP 不可能再拆，而 QUIC 实测性能并未明显落后 TCP+PEP。本文用 mininet emulation 系统重新检验"PEP 是否真的过时"。

## 核心方法

提出 **split-throughput heuristic**：对长流场景，split throughput 可由两段 path 独立测得的 end-to-end throughput 的最小值近似估计。这让作者：

- 缓存一次性 end-to-end 测量（5 bandwidth × 6 delay × 5 loss = 150 网络配置）就能在 7875 种 (s1, s2) 组合上预测 split 收益，无需为每对路径都跑 PEP emulation
- 对加密 QUIC（无法真正插透明 PEP）也能给出 split 收益预测——只测 QUIC 的 end-to-end 行为
- 评估 13 种实现/版本组合：Linux TCP CUBIC/BBRv1/v2/v3，Google quiche、Cloudflare quiche、IETF picoquic 各自的 CUBIC/BBR 实现

PEP 实际部署用 PEPsal 拦截 SYN 三次握手做 transparent split。拥塞控制评估对象覆盖三类网络场景：(a) 不对称 + 末端丢包；(b) 不对称 + 两段都丢包；(c) 对称 + 两段都丢包。

深度细节回 [[atc2025-yuan]]。

## 关键结果

- **Finding 1**：BBRv1（2016）几乎从拆分中无收益（85% 链路利用率），但 BBRv2/v3 因为加强了对丢包的敏感（为了和 CUBIC 公平共存）反而像 CUBIC 一样受益于 split——BBR 的演进让 PEP 重新相关
- **Finding 2**：BBRv3 在 (b)(c) 两类场景里 unsplit 利用率极低、split 后到达高利用率，而 CUBIC 只在场景 (a) 受益。共有 7875 个采样网络配置中，CUBIC 在 942 个、BBRv3 在 188 个能达到"split improve ≥3× 且 split util ≥50% 链路率"
- **Finding 3**：同名 CUBIC/BBR 在 Google quiche / Cloudflare quiche / picoquic / Linux TCP 之间行为差异巨大（baseline 性能、loss/delay 敏感度都不同），简单"BBR vs CUBIC"或"QUIC vs TCP"对比是不可靠的——必须 algorithm/implementation/version 三元组并报

## 相关

- **相关概念**：[[BBR]]、[[CUBIC]]、[[QUIC]]、[[TCP]]、[[Congestion-Control]]、[[Performance-Enhancing-Proxy]]
- **同会议**：[[ATC-2025]]
