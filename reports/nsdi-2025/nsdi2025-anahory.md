# Suppressing BGP Zombies with Route Status Transparency

**作者**：Yosef Edery Anahory (The Hebrew University of Jerusalem), Jie Kong, Nicholas Scaglione, Justin Furuness (University of Connecticut), Hemi Leibowitz (The College of Management Academic Studies), Amir Herzberg, Bing Wang (University of Connecticut), Yossi Gilad (The Hebrew University of Jerusalem)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/anahory
**源文件**：[nsdi2025-anahory.pdf](../../papers/nsdi-2025/nsdi2025-anahory.pdf)

---

## 一、背景

BGP (Border Gateway Protocol) 是互联网域间路由的核心协议，决定了数据包如何在自治系统 (AS) 之间传输。尽管 RPKI 的部署日益广泛（目前约 54% 的 prefix-origin 对已有有效 RPKI 记录），且 BGPsec 等路由认证机制不断推进，但这些安全增强都无法解决路由**新鲜性**（freshness）问题——即一个 AS 无法确认收到的 BGP 路由公告是否已经被撤回。

这导致了所谓的 "zombie routes"（僵尸路由）现象：当某个 AS 撤回了一条路由公告，但下游 AS 未能传播该撤回消息（无论是配置错误还是恶意行为），其他 AS 仍会继续使用这条已失效的路由。测量研究表明，zombie 路由每天都在发生，可能导致流量黑洞、路由环路和服务中断。2020 年 CenturyLink/Level 3 的重大故障就是一个典型案例——内部 BGP 流量被防火墙规则阻断后，路由器未能发出撤回消息，导致外部网络持续向其发送流量，故障持续数小时。

---

## 二、要解决的问题

1. **Withdrawal suppression 无解**：现有 BGP 安全机制（RPKI、BGPsec）只解决路由来源和路径的真实性验证，不解决路由是否已被撤回的问题。即使部署了完整的 BGPsec，zombie 路由仍然可以通过认证检查。

2. **唯一已知方案代价过高**：此前唯一被提出的解决方案是 key rollover，它依赖于 BGPsec 的全面部署，需要定期轮换签名密钥，每次轮换都要刷新所有已公告的路由（约 120 万条/客户），带来巨大的计算和通信开销，因此无法以短周期运行来快速检测 withdrawal suppression。

3. **渐进部署困难**：key rollover 需要 BGPsec 的广泛部署才能生效，而 BGPsec 本身的部署进展缓慢，形成了鸡生蛋的困境。

---

## 三、洞察与设计

**关键洞察**：路由的"状态"（是否仍然有效）与路由的"认证"（路径是否真实）是两个正交的问题，可以通过一个独立于路由认证的透明性机制来解决——让每个 AS 主动向公共仓库发布其路由状态信息，而非依赖撤回消息沿路径传播。

基于此洞察，RoST (Route Status Transparency) 的核心设计如下：

1. **Route Status Vector (RSV)**：每个 AS 的 agent 维护一组 RSV，记录该 AS 向每个邻居公告的路由状态。每条 RSV 包含 `(Prefix, RouteID, Status)`，其中 RouteID = (BatchID, PathID) 用批次化方式追踪路由变更。

2. **批量发布机制**：agent 按固定时间间隔（如 5 分钟）将变更的路由状态（∆RSV-Out）发布到可信仓库。使用 Merkle tree 对所有条目做承诺，并用 RPKI 私钥签名，确保完整性和真实性。

3. **选择性订阅**：验证方 agent 只订阅自己关心的 prefix 和 interface 的更新（∆RSV-In），通过 Merkle inclusion proof 验证子集的完整性，大幅降低带宽开销。

4. **RouteID 传播**：在 BGP 公告中添加 transitive extended community 属性来传播 RouteID，使验证方能将收到的路由与仓库中的状态信息进行匹配。

5. **独立 agent 架构**：RoST agent 与 BGP 路由器分离部署，通过现有的路由器 CLI/API（如 Netmiko）进行交互，无需修改路由器软硬件。

---

## 四、实现细节

- **RouteID 编码**：每跳编码为 7 字节的 transitive BGP 属性（1B 长度 + 6B BatchID/PathID），平均增加 27 字节/BGP update（平均路径长度 3.86 跳）。

- **路由器集成**：
  - 使用 Cisco extended community 属性附加 RouteID：`set extcommunity rt <routeid>`
  - 通过 `logging host <agent-ip>` 将 BGP 事件日志发送给 agent
  - 默认阻止所有出站路由（`route-map deny`），由 agent 验证后逐条放行
  - 使用 `clear ip bgp ... soft in prefix-list` 过滤无效路由

- **仓库端**：存储所有 AS 的 RSV，总存储需求约 8.1 TiB（最坏情况假设）。使用 Merkle tree（深度 20，支持约 100 万 IP prefix）为每个 ∆RSV-Out 生成承诺。

- **批次设计原因**：分析 RIPE-RIS 实际数据发现，虽然平均每 prefix 每天路由变更不超过 20 次，但某些 prefix 可达每天 100 万次变更。批次化可将突发变更吸收到一个 BatchID 中，避免计数器快速增长。

- **伪代码**：论文附录提供了完整的 RoST agent 伪代码（Algorithm 2），包含约 175 行，覆盖 BGP update 处理、RSV-In 合并验证、RSV-Out 生成上传、无效路由处理等所有核心流程。

---

## 五、实验结果

### 开销评估（基于 RIPE-RIS 2022-2024 年实际路由数据）

| 指标 | 5 分钟批次 | 15 分钟批次 | 1 小时批次 |
|------|-----------|------------|-----------|
| Agent 发送 ∆RSV-Out（最大接口类 201-639） | 122.13 Kbps | 98.49 Kbps | 76.45 Kbps |
| Agent 接收 ∆RSV-In | 0.21 Kbps | 0.17 Kbps | 0.13 Kbps |
| 仓库总响应带宽 | 12.63 Gbps | 10.18 Gbps | 7.90 Gbps |
| 仓库总存储 | 8.1 TiB | - | - |
| Agent 计算开销（最大类） | 859,833 h/s + 258 sig/5min | 286,611 h/s | 71,653 h/s |
| 仓库计算开销 | 48.5M h/s | 39.1M h/s | 30.3M h/s |

- 89.11% 的 AS 只有 1-10 个接口，带宽仅需约 1 Kbps
- MacBook Pro M1 单核可生成 300 万 SHA-256 hash/s 和 100 RSA sig/s，完全满足 agent 需求
- 仓库计算需约 18 核 CPU（54M h/s），可行

### 与 Key Rollover 对比

RoST 每次只需发送变更的路由状态（平均 258 签名/5 分钟），而 key rollover 每次需刷新所有 120 万条路由/客户，开销差距数个数量级。RoST 可以以分钟级间隔运行，key rollover 只能低频率运行。

### 部分部署效果（BGPy 模拟器，CAIDA 2025 年 1 月拓扑）

- 即使只有少量 AS 采用 RoST，zombie AS 数量就开始单调下降
- 采用 RoST 的 AS 还能间接保护其下游非采用者（collateral benefit）
- 与 BGPsec/key rollover 不同，RoST 不需要接近普遍部署才能获益

---

## 六、批判性分析

1. **仓库是单点瓶颈**：虽然论文讨论了多仓库方案和 BFT 共识，但都停留在"设想"层面，没有实际评估。单仓库 12.63 Gbps 的带宽需求已经不低，多仓库的同步开销、延迟影响和实际可操作性都未验证。尤其是 BFT 方案在互联网规模下的可行性存疑。

2. **仓库信任假设过强**：论文假设存在"可信仓库"(trusted repository)，但谁来运营这个仓库、如何保证其中立性和可用性，是一个重大的治理和实践问题。虽然提到可以搭建在现有 RPKI 仓库之上，但 RPKI 仓库本身也面临可用性和安全性挑战。

3. **安全模型限制未充分讨论**：RoST 假设 RPKI 已正确部署且私钥安全。如果一个恶意 AS 同时控制了 RPKI 密钥和 BGP 路由器，它可以发布虚假的路由状态信息。论文将此归为"path manipulation"范畴而排除在外，但实际攻击场景往往是复合的。

4. **默认阻止所有出站路由的方案激进**：为了让 agent 在路由传播前验证和附加 RouteID，需要默认阻止所有出站路由。这意味着如果 agent 宕机，AS 将无法发布任何路由——这比 withdrawal suppression 本身可能造成更严重的后果。论文虽提到"默认回退到标准 BGP 行为"，但未评估回退机制的可靠性。

5. **部分部署模拟场景单一**：模拟仅考虑了单个 prefix 被单个 Tier-1 AS 抑制撤回的场景，且采用者均匀随机分布。真实世界中，多个 prefix 同时受影响、非 Tier-1 AS 的抑制行为、采用者集中在特定区域等复杂场景均未评估。

6. **缺乏端到端原型实现和部署评估**：论文的评估完全基于数据分析和模拟，没有构建端到端原型系统，也没有在真实或仿真网络环境中测试。agent 与路由器的交互延迟、并发处理能力、故障恢复等实际问题均未触及。

---

## 七、总结

RoST 提出了一种通过路由状态透明性机制来检测和缓解 BGP withdrawal suppression 的新方案。其核心贡献在于将路由状态验证与路由认证解耦，通过公共仓库发布签名的路由状态向量，使任何采用 RoST 的 AS 都能独立验证收到的路由是否已被撤回。与现有方案（key rollover）相比，RoST 不依赖 BGPsec 的部署，兼容现有 BGP 路由器，开销低数个数量级，且在部分部署下即可获益。主要局限在于依赖可信仓库基础设施的建设、缺乏端到端系统验证，以及 agent 故障可能引入新的可用性风险。
