---
type: paper
name: TRIP
full_title: "TRIP: Coercion-resistant Registration for E-Voting with Verifiability and Usability in Votegral"
authors: [Louis-Henri Merino, Simone Colombo, Rene Reyes, Alaleh Azhir, Shailesh Mishra, et al.]
venue: SOSP
year: 2025
tags: [e-voting, coercion-resistance, zero-knowledge-proofs, usability, security]
source_pdf: "[[3731569.3764837.pdf]]"
source_md: "[[3731569.3764837]]"
---

# TRIP: Coercion-resistant Registration for E-Voting with Verifiability and Usability in Votegral (SOSP 2025)

> **一句话总结**:Votegral 系统的线下注册组件 TRIP,让选民在隐私亭的 kiosk 里用纸质信封打印真/假投票凭证,凭证可验证但从外观无法区分,真凭证端到端延迟仅 19.7 秒(Kiosk 硬件),150 人用户研究中 83% 成功创建并投出真凭证。

## 问题

远程电子投票在便利性上极具吸引力,但天然面临强制投票和买票问题——家暴伴侣、党派活动人士甚至外国势力可迫使选民按其意愿投票。用 cryptographic receipt 提供端到端可验证性的系统让选民反而能向强制者证明自己的投票。

"真假凭证"方案让选民拥有真假两种凭证,假凭证投出的票不计入,但这把最关键的安全问题从投票阶段前移到了注册阶段。现有方案要么假设每个选民都有昂贵且可信的智能卡(强制者完全可以没收卡片),要么假设完全可信的注册方,要么需要选民与多个注册机构打交道。Estonia 的 re-voting 方案则放弃了端到端可验证性。

## 核心方法

TRIP 利用**线下注册的物理安全性**作为信任锚。选民在注册点的隐私亭里与一台 kiosk 交互,打印纸质真假凭证:

1. **真凭证 4 步流程**:选民扫 check-in barcode → kiosk 打印一个符号和 QR 码 → 选民选择有匹配符号的信封并扫其 QR 码 → kiosk 打印额外两个 QR 码。每个凭证上编码了一个 interactive [[Zero-Knowledge-Proof]] (IZKP),真凭证 sound、假凭证 unsound。
2. **假凭证 2 步流程**:选民选信封扫 QR → kiosk 一次性打印整张 receipt。打印步骤顺序的差异让选民知道哪张是真,但事后其他人无法区分。
3. **纸质信封**上印有可透视的窗口区域,保护秘钥不外泄,同时让选民自由标记(如"R" / "RR")区分真假。
4. **激活**:选民在任何信任的设备上把 receipt 抽出 1/3,扫三个 QR 码完成激活,然后可以销毁纸质凭证。

关键性质:只有真正被强制的选民需要相信 kiosk;选民看到的打印步骤顺序差异作为"verifiability",不需要理解 IZKP 细节;凭证跨届选举复用,摊薄线下注册成本。

## 关键结果

- **延迟**:选民可见延迟 Kiosk 19.7s、Raspberry Pi 4 17.3s、Macbook Pro 15.8s、Mini PC 16s——都在选民通常会花的几分钟内
- **用户研究**:150 人主研究中 **83%** 成功创建并投出真凭证;在被告知存在恶意 kiosk 的条件下,**47%** 能发现并报告
- 与 Civitas、Swiss Post、VoteAgain 三个 SOTA 方案对比,Votegral 端到端延迟与 Swiss Post/VoteAgain 相当,显著优于 Civitas
- 原型实现 2633 行 Go 代码,包含形式化 coercion-resistance 和 verifiability 证明

## 相关

- **相关概念**:[[Zero-Knowledge-Proof]]、[[Coercion-Resistance]]、[[End-to-End-Verifiability]]、[[Sybil-Attack]]、[[Proof-of-Personhood]]
- **同类系统**:Civitas、VoteAgain、Swiss Post e-voting、Estonia e-ID
- **同会议**:[[SOSP-2025]]
