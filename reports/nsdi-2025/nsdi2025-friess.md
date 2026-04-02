# ValidaTor: Domain Validation over Tor

**作者**：Jens Frieß (ATHENE & TU Darmstadt), Haya Schulmann (ATHENE & Goethe-Universität Frankfurt), Michael Waidner (ATHENE & TU Darmstadt)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/friess
**源文件**：[nsdi2025-friess.pdf](../../papers/nsdi-2025/nsdi2025-friess.pdf)

---

## 一、背景

数字公钥证书是互联网安全的基石。证书颁发机构（CA）通过域名验证（Domain Validation, DV）确认申请者对域名的控制权后才能签发证书。DV 过程依赖 DNS 和 BGP 等未加密、未认证的协议，天然容易受到中间人攻击。

当前最先进的 DV 机制是 Let's Encrypt 的 MultiVA：从多个固定 vantage point 同时发起验证请求，要求多数一致才通过。然而 MultiVA 仅使用 7 个固定的 BGP origin（对应约 11 个 IP），攻击者可以提前侦察并针对性地发起 BGP hijack 或 DNS cache poisoning。研究表明 MultiVA 对 same-prefix BGP hijack 的平均抵抗率仅 88.6%，对于 PKI 这样的关键基础设施而言远远不够。

---

## 二、要解决的问题

1. **Vantage point 固定且可预测**：Let's Encrypt 的验证节点 IP 地址固定不变，攻击者可以在发起 DV 前提前准备 BGP hijack，将所有验证流量劫持到自己控制的服务器。
2. **Vantage point 数量太少**：仅有个位数的验证节点，路径多样性不足，单个 well-positioned AS 就可能截获大部分验证路径。
3. **扩展成本高**：部署更多地理分布的专用验证基础设施成本巨大，阻碍了大规模分布式 DV 的推广。
4. **DNS 解析器缺乏多样性**：验证节点使用的 DNS 解析器同样集中，进一步增大了攻击面。

---

## 三、洞察与设计

**关键洞察**：Tor 网络拥有约 2,200 个分布在 280 个不同 BGP origin 的 exit node，它们天然构成了一个大规模、去中心化、持续被监控的代理基础设施。如果将 Tor exit node 用作 DV 的验证节点，CA 无需自建任何额外基础设施就能实现大规模随机化分布式验证——攻击者无法预测每次验证将使用哪些节点，从根本上消除了针对性攻击的可能。

基于这一洞察，ValidaTor 的设计如下：

- **随机化验证器选择**：每次 DV 从全部 Tor exit node 中随机选择 k 个节点（确保它们在 /8 前缀级别互不重叠），通过不同 Tor circuit 分别向目标域名发起 HTTP 挑战请求。
- **k-out-of-n 投票**：先用 k 个节点验证，若结果一致则通过；若不一致则追加节点至最多 n 个，只要 k 个结果匹配即通过（与 Let's Encrypt 的 3-out-of-4 模式兼容）。
- **2-hop circuit**：因 DV 不需要匿名性，使用 2-hop 而非默认 3-hop circuit 以降低延迟。
- **无缝集成**：CA 只需将 ACME 的挑战请求 URL 替换为 ValidaTor 的 URL，无需修改其他基础设施。

---

## 四、实现细节

- **容器化架构**：Docker 容器内包含 Tor daemon、自定义 circuit 管理服务（Python stem 库）、Flask web 应用和 web server。
- **手动 circuit 构建**：通过 stem 库手动构建 circuit，绕过 Tor 默认的按带宽加权选择算法。从标记为 EXIT（非 BADEXT）的节点中均匀随机选择 exit node，确保所选节点的 IP 不共享相同 /8 前缀。
- **Entry node 优化**：从约 2,500 个标记为 GUARD 和 FAST 的节点中按带宽加权随机选择，优先选择网络路径较短的节点。
- **并发 circuit 池**：维护约 50-60 个并发 circuit（受 Tor daemon 稳定性限制），每 3 分钟重建一次以平衡网络开销与不可预测性。
- **Stream 手动分配**：通过 Tor 控制协议将同一域名的不同验证请求分配到不同 circuit，确保每个请求经过不同的 exit node。
- **水平扩展**：通过部署多个 Docker 容器实例并做负载均衡实现扩展。
- **代码开源**：https://github.com/jenfrie/tova

---

## 五、实验结果

**实验平台**：24 核虚拟服务器，Tranco top 10K 域名，请求 `/robots.txt` 模拟 ACME 挑战。

| 指标 | k=3, c=1 | k=5, c=1 | k=7, c=1 | k=5, c=3 | k=5, c=10 |
|------|----------|----------|----------|----------|-----------|
| 吞吐量 (validations/s) | 2.7 | 2.1 | 1.6 | 6.5 | 11.9 |
| 中位延迟 | ~2s | ~3s | ~4s | <2s | <2s |
| 95% 延迟 | <6s | <10s | <15s | — | — |

**路径多样性（path overlap metric）**：

| 部署方式 | k=3 | k=5 | k=7 |
|----------|-----|-----|-----|
| Let's Encrypt | ~0.48 | — | — |
| ValidaTor (Tor) | ~0.24 | ~0.21 | ~0.19 |
| AWS 30 节点 | ~0.23 | — | 0.29 |

- Tor 将 path overlap 降低约 50%，可截获 100% 验证器的 AS 数量减少 21%（k=3）至 27%（k=7）。
- DNS 解析器多样性：Tor exit node 使用 1,118 个唯一解析器 IP / 174 个 BGP origin，远超 Let's Encrypt 的 28 个 IP / 9 个 origin。
- Tor 流量被阻断率约 20%，但主要由目标域名自身屏蔽 Tor，非中转 AS 所为。
- 带宽影响：即使全 Web PKI 切换到 ValidaTor（k=7），仅消耗 Tor 剩余带宽的 0.11%。
- 恶意 exit node 攻击：控制 700 个恶意节点时，k=3 成功率约 10%，k=5 约 2.5%，k=7 < 1%。

---

## 六、批判性分析

1. **HTTP-only 限制被轻描淡写**：ValidaTor 目前仅支持 HTTP-based DV，不支持 DNS TXT 记录验证（Tor 不支持 TXT 查询）。作者声称 HTTP 是 ACME 默认方式所以"不是严重限制"，但 DNS-01 challenge 在通配符证书和 CDN 场景下广泛使用，这一限制实际上排除了相当多的真实使用场景。

2. **20% 的 Tor 流量屏蔽率是显著的**：约 20% 的域名屏蔽 Tor 流量，这意味着五分之一的域名无法使用 ValidaTor 进行验证。论文将此问题归咎于域名方（"域名可以选择放行"），但在实际部署中让数百万域名修改防火墙策略是不现实的。

3. **安全模型的简化假设**：恶意节点分析假设攻击者的节点"均匀分布在所有网络中"，且每个网络节点数相同。真实场景中攻击者可以策略性地在关键网络部署节点，实际威胁可能高于模型预测。

4. **对 Tor 网络稳定性的依赖**：系统的安全性和可用性完全依赖 Tor 网络的健康状况。论文未充分讨论 Tor 网络本身遭受攻击（如大规模 Sybil 攻击）或节点数量萎缩时的影响。

5. **性能可扩展性存疑**：单容器仅 50-60 个并发 circuit（受 Tor daemon 限制），10 容器才达到 11.9 validations/s。Let's Encrypt 高峰期约 65 certificates/s，需要约 55 个容器才能匹配。论文声称"可水平扩展"但未验证如此大规模部署的实际可行性。

6. **与云方案的成本对比不公平**：论文将 AWS 30 节点部署作为 baseline，但未给出 ValidaTor 自身的实际运营成本（服务器、维护、监控），且 Tor 的"免费基础设施"依赖志愿者捐赠的带宽资源。

---

## 七、总结

ValidaTor 提出了一个巧妙的思路：利用 Tor 网络的大规模分布式 exit node 作为域名验证的随机化 vantage point，以极低的基础设施成本大幅提升 DV 的安全性。实验证明其路径多样性比 Let's Encrypt MultiVA 提升约 50%，恶意 exit node 的攻击成功率在合理参数下低于 1%，且对 Tor 网络的带宽影响微乎其微（0.11%）。主要局限在于仅支持 HTTP-based 验证、约 20% 的域名屏蔽 Tor 流量、以及对 Tor 网络稳定性的依赖。总体而言，这是一个设计优雅且易于集成的方案，为 PKI 安全提供了一条实用的改进路径。
