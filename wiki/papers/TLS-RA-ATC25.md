---
type: paper
name: TLS-RA
full_title: "Separate but Together: Integrating Remote Attestation into TLS"
authors: [Carsten Weinhold, Muhammad Usama Sardar, Ionut Mihalcea, Yogesh Deshpande, Hannes Tschofenig, Yaron Sheffer, Thomas Fossati, Michael Roitzsch]
venue: ATC
year: 2025
tags: [security, tee, remote-attestation, tls, confidential-computing]
source_pdf: "[[atc2025-weinhold.pdf]]"
source_md: "[[atc2025-weinhold]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Separate but Together: Integrating Remote Attestation into TLS (ATC 2025)

> **一句话总结**：针对「TLS 身份担保与 TEE 状态担保正交、但简单并列会遭 relay 攻击，而现有集成方案要么牺牲 failure independence 要么加倍 handshake/加密」这一观察，提出 **TLS+RA**——在 [[TLS]] 1.3 handshake 的 message extension 中携带 attestation，并用 **double linking**（证书签 transcript hash + RoT 签含 DHE shared secret 的 linking hash）实现 deployment/failure 独立且无额外 round trip；SEV-SNP 在 80 ms 单向网络延迟下握手开销仅 **+5%**，握手后吞吐与标准 TLS 一致。

## 问题与动机

[[Confidential-Computing]] 要求客户端既能与远端 [[Trusted-Execution-Environment]] 建立保密/完整性通道，又能通过 [[Remote-Attestation]] 验证对方软硬件栈。单独使用 [[TLS]] 只能证明「谁控制该域名/端点」，attestation 只能证明「某时刻某机器上跑了什么」；二者 trust decision **正交**（端点行政控制 vs TEE 内部状态），但简单 side-by-side 组合不安全：攻击者可 relay 合法 TEE 的 attestation report，在 TEE 外终止加密通道（Figure 1 relay attack）。

已有集成路线各有硬伤：

- **Post-handshake / 嵌套通道**（如 HTTPA）：先建 TLS 再在内层做 attestation，或双层加密——满足 failure independence，但 **额外 round trip + 双层 payload 加密**，握手与吞吐成本翻倍（Figure 5–6）。
- **证书静态绑定**（Platform Certificate、RA-TLS 把 report 塞进证书）：零额外 RTT，但证书与连接无关；TLS 私钥一旦泄露（Heartbleed 类），攻击者可用同一证书 + relay 的 report 伪造「通道在 TEE 内终止」。
- **握手期用 TLS 私钥签 attestation**（RATLS、Trusted Channels、IETF draft）：无额外 RTT，但 attestation 可信度 **隐式依赖 TLS 私钥保护**——泄露后即可在 TEE 外完成 linking，不具备 failure independence。

作者 claim：应把 TLS 证书体系与 attestation 基础设施 **部署分离、失效分离**，同时在 handshake 内用密码学把「本次连接」与「本次 attestation」绑死，防 relay 且不加 RTT/加密层。TLS 1.3 强制 ephemeral DHE 与 message extension 机制使这一组合在 2025 年可行。

## 关键观察 / 隐含假设

- **观察 1**：TLS 证书担保与 attestation 担保回答不同问题——前者是 FQDN/行政控制，后者是 RoT 背书的软硬件度量；云场景下基础设施方可能持有 TLS 私钥，若 attestation 绑定该私钥，就 **把 TEE 可信度降格为信任云运营商**。
  - **依赖假设**：客户端仍需要并信任 Web PKI/CA 体系来做端点识别；attestation verifier 与 CA 运维独立。
  - **可能失效场景**：客户端只关心 TEE 状态、不关心域名；或 CA 与 TEE vendor 被同一攻击者同时攻破（威胁模型明确排除「双泄露」）。

- **观察 2**：防 relay 的 linking 必须包含 **仅会话双方知晓的 DHE shared secret**；只绑公开 handshake 字段或 TLS nonce（Walther/Armknecht 等）不足以在 TLS 私钥泄露后阻止未来 relay——攻击者可用窃取的私钥签 transcript，但无法预知新会话的 ephemeral secret，故 linking hash 含 DHE secret 可检测双通道 hash 不一致。
  - **依赖假设**：连接使用 TLS 1.3 常规模式下的 ephemeral DHE（非 PSK-only）；TLS+RA 实现代码与关键状态在 TEE 内运行并被度量进 report。
  - **可能失效场景**：PSK-only、会话复用绕过 DHE；实现不在 TEE 内则 report 不覆盖 linking 逻辑；侧信道泄露 DHE secret 可削弱 binding。

- **观察 3**：attestation report 生成/验证延迟往往主导握手开销，但 **不增加网络 RTT**；在跨洲级延迟（80 ms/向）下，固定处理开销被摊薄——SEV 报告生成仅 6 ms 时，端到端握手相对 baseline 仅 +5%。
  - **依赖假设**：benchmark 的 co-located loopback 测的是处理上界；生产路径上 report 仍为粗粒度整栈度量，格式体积可控（SEV 二进制 ~1 KiB；TPM JSON 较大）。
  - **可能失效场景**：dTPM 等慢 RoT（~210 ms 生成）在边缘 IoT 场景仍带来 **1.3×** 握手倍数；mutual attestation 双倍报告成本论文未细拆。

- **假设 1**：威胁模型中攻击者 **只 compromize TLS 私钥或 RoT 之一**，且 RoT 泄露时 TEE 隔离仍成立（无法在 TEE 内伪造有效 report）。
  - **证据强度**：**中**——标准密码分析叙事清晰，但无形式化证明或第三方密码审计；对「双泄露」与 TEE 侧信道未展开。

## 核心方法

**TLS+RA** 在标准 TLS 1.3 握手上叠加 attestation 状态机（OpenSSL callback 并行驱动），核心设计如下。

### Message extension 承载 attestation（回应观察 3、deployment independence）

- Client Hello 扩展：**attestation request**（客户端支持的 evidence 格式列表 + verifier 提供的 freshness nonce）。
- Server Certificate 消息扩展：**attestation report**（opaque quote，格式由插件决定）。
- 与常规 handshake 同包发送，**零额外 network round trip**；**不修改 X.509 证书内容**，CA/PKI、证书透明度、数据中心同域名多机不同 TEE 技术均不受影响。

### Double linking（回应观察 1–2、failure independence）

两条独立密码学链接，对称地锚定同一份 handshake message log：

1. **TLS link（既有）**：`transcript hash` 覆盖至 Server Hello 的公开握手材料 → 用 **TLS 证书私钥** 签名 → 绑定端点身份。
2. **Attestation link（新增）**：`linking hash` = hash(message log **+ DHE-derived shared secret** + attestation nonce) → 作为 challenge 交给 RoT → **RoT 私钥** 签入 quote。

验证方因参与 DHE 可本地重算 linking hash，与 report 中 nonce/签名比对。TLS 私钥泄露时：攻击者可冒充域名，但若 fake server 软件栈不符预期，attestation 仍失败；仅当攻击者同时运行 **相同软硬件栈的另一台合法 TEE** 才能骗过——这属于 RoT/部署层问题，而非 TLS 密钥连带失效。RoT 泄露时：栈真实性不可信，但 TLS 仍证明域名仍属所有者。

### 实现与 TEE 插件化

基于 **OpenSSL**：`SSL_CTX_add_custom_ext` 注入扩展；`SSL_CTX_set_verify` 在收到 certificate 扩展后触发 report 校验。关键补丁：新增 **non-standard exporter**，在 DHE 完成后、握手结束前导出 linking hash（RFC 5705 exporter 太晚）。协议层对 report **opaque**，通过 `remote_attest` / `check_report` 插件对接 TPM 2.0、fTPM、dTPM、AMD SEV-SNP、Arm CCA（仿真）。源码开源（GitHub: Barkhausen-Institut/ratls）。

深度协议步骤与 related work 对比表见 [[atc2025-weinhold]] / [[atc2025-weinhold.pdf]]。

## 设计取舍

- **OpenSSL 内部补丁 vs 标准 API**：为在握手中拿到 DHE secret + transcript，修改库内部而非仅扩展 wire protocol——部署需维护 fork/patch，与「纯 extension、不动 TLS on-wire」目标部分张力；论文称不改变 wire format。
- **插件 opaque report vs 统一 evidence 标准**：互操作靠多格式协商；与 IETF RATS / TLS attestation draft 的标准化路径并存，但 draft 选择 TLS 私钥 linking，**安全性弱于 TLS+RA 的 failure independence**（§3 明确批评）。
- **粗粒度整栈 attestation**：简化插件与 benchmark，但不区分「仅 TLS+RA 库在 TEE 内」与「整 VM 度量」的细粒度 policy；验证策略留给 verifier，协议不规定。
- **边界条件**：在 **机密计算 server TEE + 现有 Web PKI 客户端** 场景最优雅；PSK-only、TLS 1.2、无 DHE 的传统栈不适用；mutual attestation 逻辑支持但实验侧重 server-side。

## 实验与结果

- **互操作（定性）**：AMD SEV-SNP（AWS c6a.large）、Intel fTPM（桌面）、Infineon dTPM（Raspberry Pi 4）、Arm CCA（仿真）均跑通 server/client/mutual attestation 流程。
- **握手延迟（loopback，100 次均值）**：相对 baseline TLS，开销主要来自 report 生成+验证；fTPM 消息量 **6.4 KiB vs 1.5 KiB**（JSON 序列化 quote + AIK）；SEV 约 **6 ms** 报告生成，dTPM 约 **210 ms**（Figure 4）。
- **含模拟网络延迟（netem，单向最高 80 ms）**：SEV 上 TLS+RA 端到端握手 overhead **≈5%**；dTPM **≈1.3×**；post-handshake attestation（HTTPA 类，双倍 RTT）在 ≥10 ms 延迟时相对 baseline **>100%**（Figure 5）。
- **握手后吞吐（1 GiB AES payload，同机）**：TLS+RA 与标准 TLS **几乎相同**；嵌套双通道方案因额外 AES-GCM 层明显更低（Figure 6）——证明「合并协议」相对「双层加密」的运行时优势。
- **对比维度**：Table 1 相对 HTTPA、Platform Cert、RA-TLS、RATLS 等，TLS+RA 是唯一同时满足 **无额外 RTT、无嵌套加密、deployment independence、failure independence** 的行（在相关工作中）。

## Critical Analysis

### 论证链条

Observation（TLS 与 RA 正交但需密码学绑定；现有方案在 independence 与性能间二选一）→ Design（extension 零 RTT + double linking 用不同密钥与 infra）→ Result（多 TEE 互操作、SEV 跨洲延迟下 +5% 握手、吞吐无损）在 **「server TEE 机密计算 + TLS 1.3 + ephemeral DHE」** 主场景下链条闭合较好。最强证据是 Table 1 性质矩阵与 Figure 5–6 对 HTTPA 类方案的定量对比，直接支撑「合并优于嵌套」的性能 claim。

薄弱跳步：从 prototype（需 patched OpenSSL）外推到 **「可广泛部署的 attestation-in-TLS 标准」**——与 co-author 参与的 IETF draft 路线不同，产业化需解决补丁上游化、多 TEE evidence 策略、客户端 verifier 生态；论文未证明 double linking 在形式化模型下达到 compositional security。

### 假设压力测试

- **论文已证明**：在所述四类 RoT 上协议可互通；loopback 与 netem 下握手开销可量化；相对 post-handshake 与 nested channel 有明显优势；TLS 私钥泄露场景下 linking hash 不可伪造的 **叙事级** 论证与 Stumpf 等非 TLS 协议一致。
- **可能失效（推断）**：
  - **双泄露 / CA+RoT 协同攻击**：威胁模型排除；现实 APT 可能同时偷密钥与污染 verifier。
  - **TLS+RA 代码不在 TEE 或度量不含 linking 状态**：部署失误时 channel 未必终止在预期代码路径；论文要求但未实验「错误部署」失败模式。
  - **负载均衡与连接迁移**：同域名多机不同 TEE 时 extension 协商失败即 abort——符合设计，但是否影响大规模 rolling upgrade 未讨论。
  - **慢 RoT（dTPM 210 ms）**：边缘/IoT 首包延迟敏感场景，+1.3× 握手可能不可接受，尽管无额外 RTT。
- **论文未覆盖**：侧信道对 linking hash 计算时序的泄露、quote 重放窗口（依赖 nonce 但 verifier 策略未标准化）、与 mTLS/中间盒/TLS inspection 的交互、故障恢复与 attestation 过期后的重协商策略。

### 实验可信度

- **Benchmark 代表性**：覆盖云 VM TEE（SEV）、桌面 fTPM、IoT dTPM，与论文动机（机密计算 + 多形态设备）对齐；Arm CCA 仅功能测试无性能数字，硬件缺席限制完整性。
- **Baseline 公平性**：同一 OpenSSL、同一 TLS 1.3、复现 HTTPA 类 post-handshake 与 nested AES-GCM，对比可信；未与 RA-TLS/RATLS **同等实现条件下的微基准** 并排（Table 1 为性质非数值对比）。
- **Ablation**：未单独消融「仅 transcript 无 DHE secret」「仅 DHE 无 nonce」等 linking 组成；对 JSON vs 二进制 report 体积影响有描述但无系统 ablation。
- **Metric 覆盖**：握手延迟与吞吐充分；**尾延迟分布**（仅均值+std）、并发连接扩展、mutual attestation 双倍成本、CPU/能耗、大报告下的 MTU 分片与重传未测。

### 系统性缺陷

- **实现复杂度**：非标准 OpenSSL exporter 是 adoption 硬门槛；运维需同步 TEE 插件、verifier 信任锚与 TLS 证书生命周期两套体系。
- **可观测性 / 调试**：握手失败时区分 TLS 错误 vs attestation policy 拒绝 vs linking mismatch，论文未讨论生产级诊断接口。
- **资源隔离**：同一机器 co-located benchmark 不反映 TEE 调度、RoT 争用或与业务负载并跑时的延迟抖动。
- **标准化分裂**：IETF draft 走 TLS 私钥 linking，与 TLS+RA 哲学冲突；若工业界跟 draft，failure independence 优势可能被标准稀释——论文未给出迁移路径。
- **正确性形式化**：论文未讨论；对 active MITM 在 extension 字段上的篡改依赖 TLS 1.3 既有完整性保护，但未独立验证实现。

## 局限与 Future Work

- **局限 1**：依赖 **修改版 OpenSSL** 在握手中导出 linking material；非纯用户态扩展，上游合并与长期维护成本论文承认但未解决。
- **局限 2**：威胁模型假设 **单点泄露** 且 RoT  compromise 不破坏 TEE 内 TLS 私钥隔离——强 TEE 侧信道或供应链攻击可能同时削弱两条 link。
- **局限 3**：Arm CCA 仅在仿真器验证，无真实硬件性能数据；mutual attestation 的开销与策略复杂度未系统量化。
- **局限 4**：Attestation 粒度为整栈粗度量；细粒度「仅密码模块/仅 enclave image」policy 与 verifier 联邦信任未展开。
- **Future work 1**：形式化分析 double linking 在 composable security 框架下的 relay resistance，并与 IETF TLS attestation draft 做性质级对比与互操作实验。
- **Future work 2**：在真实跨云 RTT、连接 churn、LB 后端异构 TEE 集群下测量 P99 握手延迟与失败率；对比 dTPM/云 RoT 的 SLO 可达性。
- **Future work 3**：将 linking hash exporter 推进为标准 TLS exporter 或内核/TEE 内建 primitive，消除 OpenSSL fork 依赖；量化 JSON→CBOR 等序列化对 TPM 路径的体积与延迟收益。
- **Future work 4**：端到端案例（机密推理服务、远程 WASM enclave）验证 deployment independence 在「CA 轮换 / RoT 证书更新」异步场景下的运维 playbook。

## 相关

- **相关概念**：[[Trusted-Execution-Environment]]、[[Remote-Attestation]]、[[TLS]]、[[Confidential-Computing]]、[[TPM]]
- **同类系统 / 协议**：HTTPA、RA-TLS、RATLS（Walther et al.）、Platform Certificate、Trusted Channels（Armknecht et al.）
- **同会议**：[[ATC-2025]]
- **对比**：TLS+RA vs HTTPA（failure independence 相同、无嵌套加密）；vs RA-TLS/RATLS（failure independence 更强、证书部署解耦）
