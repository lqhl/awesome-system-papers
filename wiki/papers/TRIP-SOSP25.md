---
type: paper
name: TRIP
full_title: "TRIP: Coercion-resistant Registration for E-Voting with Verifiability and Usability in Votegral"
authors: [Louis-Henri Merino, Simone Colombo, Rene Reyes, Alaleh Azhir, Shailesh Mishra, et al.]
venue: SOSP
year: 2025
tags: [e-voting, coercion-resistance, zero-knowledge, security, hci]
source_pdf: "[[3731569.3764837.pdf]]"
source_md: "[[3731569.3764837]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# TRIP: Coercion-resistant Registration for E-Voting with Verifiability and Usability in Votegral (SOSP 2025)

> **一句话总结**：fake credential 抗胁迫 e-voting 把难题从投票时移到注册时；Votegral 的 TRIP 在隐私亭 kiosk 用 **纸上 interactive ZK proof** 发放真/假凭证（仅选民知真假），资源受限 kiosk 延迟 ≤19.7s，150 人可用性研究 83% 成功投票、47% 识破恶意 kiosk。

## 问题与动机

远程 [[E-Voting]] 便利但 ballot secrecy 弱，胁迫/贿选风险高。fake credential 思路：选民给胁迫者假凭证、用真凭证秘密投票——但 **credential issuance** 往往假设可信硬件 registrar 或多注册机构， usability/security 难兼顾。

Votegral 用 **in-person registration**（物理隐私亭） amortize 成本，凭证可复用于多届选举；本文聚焦注册组件 **TRIP**。

## 关键观察 / 隐含假设

- **观察 1**：注册时物理隐私亭可提供短暂 coercion-free 环境，弥补远程投票无法提供的隔离。
  - **依赖假设**：亭内无 covert camera/coercer；选民单次注册可承受几分钟流程。
  - **可能失效场景**：注册点外胁迫「交出全部纸张凭证」；亭内硬件被篡改。
- **观察 2**：真凭证需 **voter-verifiable** 但事后对第三方 **不可区分** 真假；假凭证 IZKP **unsound** 但打印后外观一致。
  - **依赖假设**：选民能观察打印步骤顺序差异理解真假，无需懂 ZK 细节。
  - **可能失效场景**：可用性差的选民可能无法可靠区分或保存凭证。
- **观察 3**：纸质凭证 + 随机 challenge 信封降低 transport 泄露风险，无需选民自带 trusted device。
  - **依赖假设**：纸张成本可接受；激活凭证可用任意设备（含朋友设备）。
  - **证据强度**：中强。原型延迟 + 150 人 study + 形式化安全证明。

## 核心方法

TRIP kiosk 在 privacy booth：

1. **Real credential**：interactive zero-knowledge proof（IZKP）向选民证明凭证有效；打印于纸。
2. **Fake credential**： visibly distinct 流程伪造 unsound IZKP，打印后不可区分。
3. **Paper transcripts + envelopes**：隐藏敏感密钥；简化 challenge 选择。
4. **Votegral 架构**：注册一次，多届复用；密码学路径主导延迟（Go 原型 2633 LOC）。

形式化证明：verifiability + coercion-resistance（论文 claim）。

## 设计取舍

- **In-person registration vs pure remote**：抗胁迫强，便利性降。
- **Paper vs smartcard trusted hardware**：低成本、可多张假凭证；纸易损毁/丢失。
- **IZKP complexity vs voter understanding**：技术藏底层，依赖 procedural observability。
- **Cryptographic path focus**：网络投票全路径、计票系统不在本文重点。

## 实验与结果

- vs Civitas、Swiss Post、VoteAgain：Votegral end-to-end latency 可比 Post/VoteAgain，显著优于 Civitas。
- TRIP voter-visible latency：POS kiosk **19.7s**（最慢）→ MacBook Pro **15.8s**。
- Usability：150 participants——**83%** 成功用真凭证 mock vote；恶意 kiosk 教育后 **47%** 报告。
- 2633 LOC Go prototype。

## Critical Analysis

### 论证链条

「credential issuance 是 fake-credential 方案瓶颈 → 隐私亭 + paper IZKP → 安全证明 + 延迟 + HCI」链条在 prototype 层闭合。到国家级选举 scale（百万选民、供应链、法务）差距巨大——论文 §4.5 承认 limitations。

### 假设压力测试

- 胁迫可发生在注册后（保管纸张凭证）——物理安全仍关键。
- 47% 识破恶意 kiosk 意味着半数仍可能受骗——教育/UX 需强化。
- 形式化证明 assumptions（如 kiosk 仅短暂恶意）需与真实 threat actor 对齐。

### 实验可信度

- 150 人 study 在 e-voting 领域偏大；mock vote 非真实选举压力。
- 与 Civitas/Post 对比偏 cryptographic latency component，非 full deployment cost。
- 41 页论文 proof 需专家审计——wiki 读者应回 source_pdf。

### 系统性缺陷

- 论文未讨论大规模 kiosk 供应链、打印耗材、残障选民 accessibility 完整方案。
- 与 blockchain/dark DAO 贿选 scale 对抗的 deterrence 未量化。
- 计票/投票阶段组件 only lightly covered。

## 局限与 Future Work

- **局限**：in-person 注册；纸凭证风险；HCI 失败率；国家级部署未验证。
- **Future work**：与 in-person pseudonym party 结合 proof-of-personhood；残障友好 UI；full Votegral 端到端 audit。

## 相关

- **相关概念**：E-Voting、Coercion-Resistance、Zero-Knowledge-Proof、End-to-End-Verifiability
- **同类系统**：Civitas、VoteAgain、Swiss Post e-voting、Helios
- **同会议**：[[SOSP-2025]]
