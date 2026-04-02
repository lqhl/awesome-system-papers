# DISC: Backpressure Mitigation in Multi-tier Applications with Distributed Shared Connection

**作者**：Brice Ekane, Djob Mvondo (Univ. Rennes, Inria, CNRS, IRISA), Renaud Lachaize, Alain Tchana (Univ. Grenoble Alpes, CNRS, Inria, Grenoble INP, LIG), Yérom-David Bromberg (Univ. Rennes, Inria, CNRS, IRISA), Daniel Hagimont (IRIT, Université de Toulouse, CNRS, Toulouse INP)
**会议**：NSDI 2025 (22nd USENIX Symposium on Networked Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/nsdi25/presentation/ekane
**源文件**：[[nsdi2025-ekane.pdf]]

---

## 一、背景

数据中心中的互联网服务普遍采用多层（multi-tier）架构或微服务架构。在这种架构中，请求从外部客户端（EC）经由前端（FE）、中间层（IS）到达后端（BE），响应沿反向路径逐层返回。当 BE 产生的最终数据（final data）——即不需要中间层做任何修改、仅需原样中继的数据——在返回路径上经过所有中间层和 FE 时，会产生大量冗余通信。

这种冗余通信导致了 **backpressure 问题**：BE 负载的增加会按比例传导到 IS 和 FE，使得 FE 成为瓶颈、各层无法独立扩展。这一问题在响应体较大（如邮件附件、图片、JSON 集合）的场景中尤为严重。WordPress 等系统占据互联网 43% 的网站份额，广泛依赖多层架构，使得 backpressure 成为一个具有实际影响力的系统问题。

---

## 二、要解决的问题

1. **冗余数据中继造成的 CPU 浪费**：FE 和 IS 层仅仅充当 payload 的中转站，却承受了与 payload 大小成正比的 CPU 和网络开销。实验表明，在 3-tier 架构中，FE 的 CPU 负载显著高于 BE。

2. **现有方案的三大局限**：
   - **仅支持 2-tier 架构**：CRAB、Prism 等 connection handoff 方案只能绕过单个 FE（load balancer），无法处理更长的调用链。
   - **协议/API 锁定**：connection migration 要求 FE 和 BE 实现相同的协议和 API（如都用 HTTP），不兼容异构协议链（如 HTTP + IMAP + SOAP）。
   - **完全绕过的副作用**：全连接迁移会导致 FE 丢失 response header/footer 中的元数据，破坏 load balancer 的反馈驱动调度等功能逻辑。

3. **QUIC 不是替代方案**：QUIC 的 connection migration 机制面向客户端网络切换场景，同样受限于协议锁定和需要修改客户端的问题。

---

## 三、洞察与设计

**关键洞察**：在多层架构的响应路径中，response 消息可以被解耦为 metadata（header/footer，体积小但对中间层有语义价值）和 payload（体积大但仅被原样中继）。只要让 metadata 沿正常路径逐层返回、payload 直接从 BE 发送到 EC，就能在不破坏应用逻辑的前提下消除冗余通信。

基于这一洞察，DISC（Distributed Shared Connection）允许多个 tier 共同作为同一条 TCP 连接的端点。核心设计包括：

- **DISC-PROT 协议**：在 TCP 之上添加轻量级头部信息。请求路径中，每个 tier 通过 BYPASSED_TIERS bitmap 声明自己是否可以被绕过；响应路径中，payload 与 header/footer 走不同的网络路径。
- **角色动态分配**：在任意深度的调用链 T₀↔T₁↔...↔Tₙ 中，每个 tier 根据自身和相邻 tier 的 bypass 意愿，动态承担 FE、IS、BE 或 EC 角色。
- **DP（Data Plane）模块**：在 BE 上缓存 payload，等待 FE 发出 start_transmit() 请求后，构建 raw packets 直接发送到 EC，spoofing FE 的源地址。
- **TCP 序列号协调**：通过 kHook（BPF 内核模块）维护全局 SN 状态，翻译 FE 和 BE 各自发出的包的序列号，使 EC 看到一致的 TCP 流。
- **ACK 路由**：kHook 拦截 EC 的 ACK，根据 SN 范围判断属于 FE 还是 BE(DP) 发出的包，分别路由。
- **TLS 支持**：通过 wolfSSL 的 session 序列化/反序列化，将 TLS session 从 FE 迁移到 DP，加密工作从 FE 转移到 BE。
- **回调机制处理 footer**：协议如 IMAP 需要在 payload 后发送 footer。DISC 通过注册 callback 函数，在 payload 传输完成后异步触发 footer 发送，不阻塞 FE 线程。

---

## 四、实现细节

- **内核空间**：kHook 基于 BPF 实现，包含三个 interceptor（in_tc、out_tc、in_drv），分别在 TC 层和 NIC driver 层拦截/修改包。kvs 使用 BPF maps 实现，存储连接状态、SN 映射和 ACK 路由信息。
- **用户空间**：ackSender 进程在 FE 上轮询 kvs 中的 ACK 并转发给 DP。DP 内部分为 ctr_msg_manager（管理 job 红黑树、处理 ACK/传输请求）和 payload_sender（实际发包线程，消费 FIFO 任务列表）。
- **应用修改**：对 IS、FE、BE 各提供一个 hook（isHook、feHook、beHook），修改量约为在收发 response 处增加 DISC-PROT header 处理和 bypass 判断逻辑（约 15-20 行代码变更）。
- **payload 传输模式**：支持两种类型——buffered stream（BE 应用写入缓冲区）和 file（类似 sendfile 直接从文件读取）。
- **对 TrainTicket 的适配**：扩展了 SQL 语言以标记可绕过的返回路径，并修改了 MySQL JDBC driver 来实现 DP 组件。
- **实验平台**：CloudLab c220g5 节点，2×Intel Xeon Silver 4114 (10-core, 2.20GHz)，192GB 内存，10GB Intel X520-DA2 NIC，Debian 11 + Linux v5.19。

---

## 五、实验结果

| 实验场景 | Vanilla 累计 CPU (%) | DSR 累计 CPU (%) | DISC 累计 CPU (%) | DISC 降幅 |
|---|---|---|---|---|
| [FE-BE] 16KB | 52 | 54 | 54 | -3.8% |
| [FE-BE] 32KB | 67 | 65 | 64 | 4.5% |
| [FE-BE] 64KB | 111 | 75 | 74 | 33.3% |
| [FE-IS*-BE] 16KB | 136 | 132 | 120 | 11.7% |
| [FE-IS*-BE] 32KB | 173 | 158 | 128 | 26% |
| [FE-IS*-BE] 64KB | 246 | 208 | 145 | **41%** |
| SpecWeb | 130 | — | 76.11 | **41.5%** |
| SpecMail | 115 | — | 73.06 | **36.5%** |

**扩展性**：2 核配置下，vanilla 支持 18K req/s，DISC 支持 26K req/s（**提升 45%**）；4 核下 DISC 达到 30K req/s（受网卡限制）。DISC 使 BE 先饱和而非 FE，符合理想的扩展模式。

**延迟**：
- 2 IS 配置下，DISC 平均延迟比 vanilla 低 0.35ms，尾延迟（P99.99）从 4.803s 降至 2.959s
- 10 IS 配置下，尾延迟改善达 **5.71×**（8s → 1.4s）
- SpecWeb/SpecMail 平均延迟改善最高 12%

**微服务场景**：
| 应用 | 平均延迟降幅 | 吞吐提升 | FE/IS 卸载 | BE 增加 |
|---|---|---|---|---|
| TrainTicket | 74.1%（3.57s→0.928s） | 39.8%（635→889 req/s） | order 降 49% | MySQL +18.5% |
| Social Media | 66.7%（510ms→221ms） | 21.9%（80355→98009 req/s） | FE 降 41.7% | MongoDB +48.8% |

---

## 六、批判性分析

1. **IP spoofing 依赖是重大部署限制**：DISC 核心机制依赖 BE 的 DP 伪造 FE 的 IP 地址向 EC 发包。论文在结论中提到这在 IaaS 租户环境下不可行，只能由云厂商部署。但这一限制实际上极大地缩小了适用场景——在多租户公有云中，几乎所有 anti-spoofing 规则都会阻止这种行为。论文将此作为"Note"轻描淡写，未充分讨论其对实际部署的影响。

2. **微基准与宏基准的差异被模糊处理**：在 [FE-BE] 16KB 场景下，DISC 的 CPU 负载反而略高于 vanilla（-3.8%），说明在小 payload 场景下 DISC 的协调开销可能抵消收益。但论文未明确讨论 DISC 在什么 payload 大小阈值以下不值得启用。

3. **TrainTicket 实验中 gateway 的 traffic shaping 干扰**：论文承认 gateway 的 CPU 负载高是因为 traffic shaping 而非数据中继。但这恰恰意味着在 gateway 有复杂逻辑的真实场景中，DISC 对 FE 的卸载效果可能远不如微基准所示的那么显著。

4. **应用修改的"non-intrusive"声称需要推敲**：虽然每个 hook 的代码改动量不大，但 DISC 需要修改所有层的应用代码，包括扩展 SQL 语言和修改 JDBC driver。对于大型遗留系统，这种"每层都要改"的侵入性不容忽视。

5. **单核实验设置的代表性**：大部分微基准实验中每个 tier 仅使用 1 个 CPU 核。在多核环境下，kHook 的 BPF 拦截和 SN 翻译的并发正确性和性能开销未被充分验证。

6. **缺乏与现代 service mesh / sidecar proxy 的对比**：Envoy、Linkerd 等 service mesh 方案同样能通过 sidecar 优化服务间通信。论文未讨论 DISC 与这些实际部署广泛的方案的关系。

---

## 七、总结

DISC 提出了一种分布式共享连接机制，通过将多层架构中 response 的 metadata 和 payload 解耦到不同的网络路径，使 BE 可以直接向 EC 发送 payload，绕过中间层的冗余中继。相比现有 connection handoff 方案，DISC 支持任意深度的调用链、异构协议和细粒度的 bypass 控制。实验证明其在 CPU 负载（最高降 41.5%）、尾延迟（最高 5.71× 改善）和吞吐（最高 45% 提升）方面效果显著。主要局限在于依赖 IP spoofing（限制为云厂商部署）以及需要修改所有层的应用代码。
