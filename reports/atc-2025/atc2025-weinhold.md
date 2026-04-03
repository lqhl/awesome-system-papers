# Separate but Together: Integrating Remote Attestation into TLS

**作者**：Carsten Weinhold (Barkhausen Institut), Muhammad Usama Sardar (TU Dresden), Ionut Mihalcea, Yogesh Deshpande (Arm), Hannes Tschofenig (University of Applied Sciences Bonn-Rhein-Sieg), Yaron Sheffer (Intuit), Thomas Fossati (Linaro), Michael Roitzsch (Barkhausen Institut)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/weinhold
**源文件**：[[atc2025-weinhold.pdf]]

---

## 一、背景

机密计算（Confidential Computing）基于可信执行环境（TEE）让软件在远程服务器上运行，即使服务器管理员也无法访问其代码和数据。远程证明（Remote Attestation）提供了对 TEE 内硬件和软件栈的可验证密码学证明。然而，要与 TEE 通信，还需要建立一条安全通道并保证该通道确实终止在 TEE 内部。TLS 是当前最广泛部署和经过充分安全分析的安全通道协议，但标准 TLS 本身不支持远程证明。如何将远程证明集成到 TLS 中，使得安全通道同时具备端点身份认证（TLS 证书）和 TEE 状态验证（attestation）的双重保障，是一个尚未解决的协议设计问题。

---

## 二、要解决的问题

现有的 TLS 与远程证明结合方案存在以下不足：

1. **Relay Attack 风险**：如果 TLS 和 attestation 没有密码学绑定，攻击者可以将合法 TEE 的证明报告转发给自己控制的恶意服务器，形成中继攻击（relay attack），使客户端以为连接到了合法 TEE 实际却连接到了攻击者。
2. **缺乏故障独立性（Failure Independence）**：现有方案（如 RA-TLS、RATLS、Trusted Channels 等）将 attestation 报告与 TLS 私钥绑定。一旦 TLS 私钥泄露（如 Heartbleed 类漏洞），attestation 的安全保障也随之失效——两个安全属性不是加性的，而是相互依赖的。
3. **性能开销**：HTTPA 等方案通过在 TLS 通道内嵌套第二层加密通道来实现故障独立性，但引入了额外的握手往返和双重加密开销。
4. **部署独立性缺失**：部分方案要求将 attestation 信息嵌入 TLS 证书，这打破了现有的 PKI 证书管理实践（签发、吊销、负载均衡），增加了部署复杂性。

---

## 三、洞察与设计

**关键洞察**：TLS 1.3 强制使用的 Ephemeral Diffie-Hellman（DHE）密钥协商会在双方之间建立一个仅双方知晓的临时共享秘密；将这个共享秘密包含在 attestation 的 linking hash 中，就可以独立于 TLS 私钥地将 attestation 报告绑定到 TLS 会话，从而实现真正的故障独立性——即使 TLS 私钥泄露，attestation 链接仍然有效。

基于此洞察，TLS+RA 协议采用 **双重链接（Double Linking）** 设计：

- **链接一（TLS 标准）**：TLS 证书私钥签名 transcript hash（覆盖握手消息日志），将端点身份绑定到 TLS 会话。
- **链接二（TLS+RA 新增）**：计算一个 **linking hash**，覆盖同样的握手消息日志 **加上 DHE 共享秘密**，将此 hash 作为 challenge 发送给 attestation RoT。attestation 报告中包含该 linking hash，将 TEE 状态绑定到 TLS 会话。

两条链接使用不同的签名密钥（TLS 私钥 vs attestation RoT 私钥）和独立的部署基础设施（Web PKI CA vs TEE 厂商），因此：
- 任一密钥泄露不影响另一条链接的安全性（故障独立性）
- 证书管理和 attestation 部署可以独立进行（部署独立性）
- attestation 数据通过 TLS 1.3 消息扩展传输，不增加网络往返（零额外 round trip）
- 握手完成后只有一层 TLS 加密（无嵌套通道）

---

## 四、实现细节

- 基于 **OpenSSL** 实现原型，利用 `SSL_CTX_add_custom_ext` API 注册回调函数在 TLS 握手消息中添加/解析 attestation 扩展数据。
- 使用 `SSL_CTX_set_verify` 回调在收到证书消息中的 attestation 报告后触发验证。
- **关键修改**：OpenSSL 标准 API 仅在握手完成后才能通过 RFC 5705 exporter 访问密钥材料。TLS+RA 需要在握手过程中（DHE 共享秘密计算完成后、attestation 报告生成前）获取该材料来计算 linking hash，因此添加了一个非标准的 exporter 函数。此修改不改变 TLS 线上协议。
- 设计了 **TEE 无关的插件 API**：插件只需实现 `remote_attest` 和 `check_report` 两个函数。已实现三个插件：
  - **AMD SEV-SNP**：用于云服务器 TEE，报告约 1 KiB 二进制格式
  - **Firmware TPM (fTPM)**：用于终端设备，JSON 序列化，握手数据约 6.4 KiB
  - **Hardware TPM (dTPM)**：用于 IoT 设备（Infineon Optiga SLB9670）
  - **Arm CCA**：通过模拟器验证功能正确性（硬件尚未公开）
- 代码开源：https://github.com/Barkhausen-Institut/ratls

---

## 五、实验结果

**实验平台**：

| 技术 | 硬件 | 系统 |
|------|------|------|
| AMD SEV-SNP | Amazon c6a.large | Amazon Linux 2023, kernel 6.1 |
| fTPM | Intel Core i5-13400 | Ubuntu, kernel 6.5 |
| dTPM (Infineon Optiga SLB9670) | Raspberry Pi 4 Model B | kernel 5.15 |

**握手延迟（本地 loopback，100 次测量均值）**：

| 技术 | TLS 基线 | TLS+RA | 主要开销来源 |
|------|---------|--------|-------------|
| SEV-SNP | ~4 ms | ~10 ms | 报告生成 ~6 ms |
| fTPM | ~4 ms | ~30 ms | 报告生成 + 验证 |
| dTPM | ~4 ms | ~220 ms | 硬件 TPM 签名慢（~210 ms） |

**网络延迟影响（netem 模拟）**：
- SEV-SNP：80 ms 网络延迟下，TLS+RA 相对 TLS 基线仅增加 5% 开销
- dTPM：80 ms 网络延迟下，TLS+RA 握手延迟约为基线的 1.3 倍

**与相关工作对比**：
- Post-handshake attestation（如 HTTPA）需要额外网络往返，10 ms 网络延迟下即引入 >100% 额外开销
- 嵌套通道方案的数据传输吞吐量低于 TLS+RA，因为需要双重加密
- TLS+RA 握手后吞吐量与标准 TLS 完全一致（~1.8 GiB/s），因为不引入额外加密层

---

## 六、批判性分析

1. **安全分析缺乏形式化验证**：论文的核心贡献是一个安全协议，但仅通过非形式化的论证说明其安全性。对于声称具有"加性安全属性"的协议，缺少形式化证明（如 ProVerif、Tamarin 等工具的验证）是一个显著缺陷。作者提到共同作者参与了相关 IETF 草案 [18]，但论文本身未给出协议的形式化安全模型。

2. **实验规模和场景单一**：所有实验均在单机 loopback 或模拟网络延迟下进行，未在真实的云部署环境中测试。缺少多租户场景、高并发连接、负载均衡等实际部署条件下的评估。

3. **需要修改 OpenSSL 内部代码**：实现需要添加非标准 exporter 函数来在握手期间访问 DHE 密钥材料。这意味着无法直接使用发行版自带的 OpenSSL，增加了部署门槛和维护负担。论文轻描淡写了这一点，但这对实际采用是一个重要障碍。

4. **dTPM 开销过高**：dTPM 场景下 220 ms 的握手延迟对于延迟敏感应用来说可能不可接受。论文没有讨论如何优化或缓解这一问题（如 session resumption、attestation 缓存等）。

5. **威胁模型假设较强**：假设攻击者只能泄露 TLS 私钥或 RoT 私钥之一，但不能同时泄露两者。这一假设在实际中是否合理值得讨论——例如同一个 side-channel 攻击可能同时影响两者。

6. **与 IETF 草案的关系模糊**：论文共同作者参与了 IETF TLS attestation 草案 [18]，但该草案选择了不同的设计（将 attestation 绑定到 TLS 私钥而非 DHE 秘密）。论文没有充分解释为何标准化路径选择了被本文批评的设计，以及 TLS+RA 的设计能否影响标准进程。

---

## 七、总结

TLS+RA 提出了一种将远程证明集成到 TLS 1.3 的协议设计，核心创新是利用 DHE 共享秘密进行双重链接，实现了 attestation 和 TLS 证书认证的部署独立性和故障独立性——两个安全属性相互加性而非相互依赖。协议不增加网络往返和加密层数，在 SEV-SNP 等现代 TEE 上开销可控。主要局限在于需要修改 TLS 库内部实现、缺乏形式化安全证明，以及在硬件 TPM 等慢速 RoT 上的延迟较高。该工作适用于机密计算场景下需要同时验证端点身份和 TEE 状态的安全通道建立。
