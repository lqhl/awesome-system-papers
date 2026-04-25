---
type: paper
name: TLS-RA
full_title: "Separate but Together: Integrating Remote Attestation into TLS"
authors: [Carsten Weinhold, Muhammad Usama Sardar, Ionut Mihalcea, Yogesh Deshpande, Hannes Tschofenig, et al.]
venue: ATC
year: 2025
tags: [security, tee, remote-attestation, tls, confidential-computing]
source_pdf: "[[atc2025-weinhold.pdf]]"
source_md: "[[atc2025-weinhold]]"
---

# Separate but Together: Integrating Remote Attestation into TLS (ATC 2025)

> **一句话总结**：通过 TLS 1.3 message extension + double linking（TLS 证书签名 + 含 DHE shared secret 的 attestation linking hash）把 Remote Attestation 集成进 TLS，同时实现 deployment 与 failure 独立性，无额外 round trip。

## 问题

机密计算需要客户端建立到 TEE 内部的安全通道并验证 TEE 软硬件状态。已有 TLS + Remote Attestation 的组合都有缺陷：

- **HTTPA**：在 TLS 通道内嵌套 attestation 通道，加倍 handshake、双层加密
- **Platform Certificate / RA-TLS**：把 attestation 信息塞入 TLS 证书或与 TLS 私钥绑定——一旦 TLS 私钥泄露（如 Heartbleed 类侧信道），attestation 担保也失效（不具备 failure independence）
- **Walther / Armknecht**：用 TLS 私钥签 attestation——同样不防 TLS 密钥泄露后的 relay 攻击

## 核心方法

提出 **TLS+RA**，把 TLS 证书与 attestation 报告设计成**真正可加性**的两条独立担保：

- **不修改证书**：attestation 数据通过 TLS 1.3 的 message extension（client/server hello 和 certificate 消息扩展）传输，零额外 round trip
- **Double linking**：除了标准 TLS 用证书私钥签 transcript hash 外，TLS+RA 额外计算一个 **linking hash**——它在 transcript hash 基础上加入 DHE 推导的 ephemeral shared secret，作为 attestation challenge 给 RoT 签名。两个 link 用不同密钥（TLS 私钥 vs RoT 私钥）和不同基础设施
- **Failure independence**：TLS 私钥泄露不影响 attestation；RoT 失效不影响 TLS 身份。relay 攻击防御依赖 ephemeral DHE secret 不可预测

实现基于 OpenSSL（用 SSL_CTX_add_custom_ext + 新增 non-standard exporter 在握手中导出 linking hash），插件化支持 TPM、AMD SEV-SNP、Arm CCA 等多种 TEE。

深度细节回 [[atc2025-weinhold]]。

## 关键结果

- 80 ms 网络延迟下，SEV 上 TLS+RA 相对 baseline TLS overhead 仅 **5%**；dTPM 上 1.3×
- 比 post-handshake attestation（HTTPA 类）减少 100%+ 开销（在 ≥10 ms 网络延迟时）
- 握手后吞吐与标准 TLS 一致（无额外加密层）
- 在 AMD SEV-SNP / fTPM / dTPM / Arm CCA 上验证互操作

## 相关

- **相关概念**：[[Trusted-Execution-Environment]]
- **同会议**：[[ATC-2025]]
