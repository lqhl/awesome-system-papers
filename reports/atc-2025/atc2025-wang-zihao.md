# Minos: A Lightweight and Dynamic Defense against Traffic Analysis in Programmable Data Planes

**作者**：Zihao Wang (Pengcheng Laboratory & Tsinghua SIGS), Qing Li, Guorui Xie, Dan Zhao, Kejun Li, Zhuochen Fan (Pengcheng Laboratory), Lianbo Ma (Northeastern University), Yong Jiang (Pengcheng Laboratory & Tsinghua SIGS)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/wang-zihao
**源文件**：[[atc2025-wang-zihao.pdf]]

---

## 一、背景

加密流量分析（Encrypted Traffic Analysis）是一种被动攻击技术，攻击者无需解密数据包内容，仅通过观察加密流量的元数据（包大小、方向、时间间隔等），利用机器学习分类器推断用户正在访问的资源（网站、视频、IoT 设备类型等）。典型攻击场景包括 Website Fingerprinting（WF）和 IoT Fingerprinting。

现有防御手段分为两大类：
- **Proxy-based 防御**（如 IPsec 网关、Shadowsocks、V2Ray）：通过替换 5-tuple 隐藏用户身份（identity anonymity），但无法抵抗基于 per-flow/per-packet 特征的新型攻击
- **Traffic morphing-based 防御**（如 Tamaraw、WTF-PAD）：通过填充、插入 dummy 包、延迟等方式混淆流量特征（traffic anonymity），但带宽开销极大（Tamaraw 达 143%），且无法同时提供 identity anonymity

可编程交换机（如 Tofino）提供了线速包处理能力和数据面可编程性，为在网络设备上直接实现高效防御提供了新机会。

---

## 二、要解决的问题

1. **现有 proxy 防御缺乏 traffic anonymity**：IPsec 网关等只隐藏用户身份，但新型攻击（如 per-packet labeling）仍能从加密隧道中推断设备类型和用户行为
2. **Traffic morphing 防御开销过大**：Tamaraw 带宽开销达 199%，实际 goodput 不足 40%；且缺乏 scalability，无法同时为多用户提供保护
3. **两类防御无法兼得**：Traffic morphing 防御不提供 identity anonymity，需额外配合 VPN；proxy 防御不提供 traffic anonymity
4. **现有可编程交换机方案（Ditto）的局限**：Ditto 虽然利用可编程交换机实现了 traffic morphing，但采用固定流量模式（fixed interval + fixed size），每个包需过两次 pipeline，导致吞吐量上限仅 45 Gbps，且依赖外部 IPsec/MACsec 网关提供加密，无法独立提供 identity anonymity

---

## 三、洞察与设计

**关键洞察**：在可编程交换机中，多用户并发传输的多条流本身就可以互相充当"dummy 流量"——通过将不同流的包交错调度（flow interleaving），无需额外插入大量 dummy 包即可有效混淆攻击者的分类模型，当并发流数量达到 4-5 条时，攻击准确率即可降至 20% 以下。

基于此洞察，Minos 设计了三个协同工作的模块：

### Proxy Module：线速包头加密
- 选用 PRINCE 轻量级分组密码（64-bit 块，最多 10 轮加密）
- **Encryption Round Compression**：将 S-box、矩阵乘法和 XOR 操作合并为单个 4-bit 到 4-bit 的 match-action 表映射，每轮加密只占 1 个 pipeline stage
- 利用 PRINCE 的 α-reflection 特性，加密和解密共用同一套 match-action 表，SRAM 消耗减半
- 加密源 IP 和源端口，替换为网关公共 IP，建立端到端加密隧道

### Schedule Module：动态流调度
- 维护 per-flow 状态（timestamp、queue ID、flow count）在寄存器中
- 将同一目标 IP 的流均匀分配到不同队列，通过 round-robin 调度实现流交错
- 新流分配到最短队列以均衡队列长度
- 监控每条加密隧道的活跃流数量，决定是否需要启用 Traffic Morphing Module

### Traffic Morphing Module：轻量级流量混淆
- **Dummy Module**：设计基于优先级队列的 dummy 包调度——dummy 队列拥有最高优先级，通过控制面周期性暂停/恢复队列来精确控制 dummy 包注入速率
- **Padding Module**：基于平均包大小进行随机填充，填充长度与源 IP 一起加密，接收端可精确去除

---

## 四、实现细节

- **硬件平台**：Barefoot Tofino1 交换机，32×100 Gbps 端口
- **加密实现**：PRINCE 密码 6 轮加密（受限于 pipeline 12 stage），每轮将 64-bit 分为 16 个 4-bit 串，通过 match-action 表执行 S-box + 矩阵乘法的合并映射
- **资源消耗**：Proxy Module 占 10 stages、6.15% VLIWs、55.96% SRAM，不使用 ALU 和 TCAM；完整 Minos 占 12 stages、7.81% VLIWs、59.06% SRAM。由于不占用 ALU，可与 Sketch、网络攻击检测等常用 P4 程序共存
- **流管理**：Tofino1 提供 80 pages × 1000 entries 的 128-bit RAM，支持管理超过 10,000 条并发流；仅追踪需要防御的目标流
- **包格式**：在传输层头部后插入加密头（32-bit 源 IP + 16-bit 源端口 + 8-bit padding 长度 + 8-bit 随机填充 = 64 bits / 8 Bytes 静态开销）
- **Dummy 包速率控制**：通过公式 `Dummy_rate = (1/n - d - i) * r/R` 精确调节，其中 n 为恢复周期轮数，i 为恢复间隔，r 为 dummy 队列输出速率，R 为当前流输出速率

---

## 五、实验结果

### 吞吐量与开销

| 指标 | Minos（单流） | Minos（多流） | Ditto |
|------|-------------|-------------|-------|
| Goodput | 95.3% | 99.2% | 上限 45 Gbps（Mixed） |
| 延迟开销 | ~0.4% | ~2.4% | 显著（包过两次 pipeline） |
| 带宽开销（静态） | 8 Bytes/packet | 8 Bytes/packet | 固定模式填充 |

### 与 Ditto 对比（100 Gbps 背景流量下）
- TCP 吞吐量：Minos ~4 Gbps vs Ditto ~0 Gbps
- UDP 丢包率：Minos 几乎无影响 vs Ditto 显著丢包
- 网页加载时间：Minos 接近无防御基线 vs Ditto 明显延迟

### Website Fingerprinting 防御效果

| 防御方案 | kNN Acc% | CUMUL Acc% | kFP Acc% | DF Acc% | 带宽开销% | 延迟开销% |
|---------|---------|-----------|---------|--------|---------|---------|
| 无防御 | 84.62 | 91.47 | 91.68 | 96.9 | 0 | 0 |
| Tamaraw | 2.55 | 4.42 | 4.99 | 1.47 | 143.82 | 14.23 |
| WTF-PAD | 20.38 | 44.42 | 57.28 | 81.06 | 60 | 0 |
| Minos-500 | 5.63 | 39.82 | 31.73 | 7.06 | 6 | 0 |
| Minos-1000 | 7.38 | 38.73 | 32.66 | 6.67 | 12 | 0 |

### 流交错效果
- 并发流数 ≥5 时，所有攻击模型准确率降至 <20%，无需任何额外带宽开销

### IoT Fingerprinting 防御
- 16 Bytes 平均 padding 即可将 HomeMole 和 ByteIoT 准确率降至 20%，goodput 率 98%

---

## 六、批判性分析

1. **加密强度存疑**：受 Tofino1 pipeline 12 stage 限制，PRINCE 密码实际只执行 6 轮加密（原始设计 10 轮）。论文未讨论 6 轮 PRINCE 的安全性是否足够，也未引用密码学分析证明其在减少轮数后的安全边界。对于安全防御系统，加密方案的安全性评估不应被省略

2. **WF 防御对 CUMUL 和 kFP 效果有限**：Minos-500 对 CUMUL 准确率仍达 39.82%，对 kFP 达 31.73%，远未降至随机猜测水平。论文以"因为开销低所以可以接受"来辩护，但这种 trade-off 的合理性缺乏量化论证——攻击者 40% 的准确率在某些场景下仍然构成严重威胁

3. **流交错的前提条件较强**：核心防御效果依赖同一加密隧道中有 ≥5 条并发活跃流。论文未讨论在低流量时段（如深夜）或小型网络中，这一条件多久/多频繁能被满足。当条件不满足时退回 Traffic Morphing Module，但该模块的防御效果（如上所述）对部分攻击模型不理想

4. **实验中 Dummy Module 被禁用**：在与 Ditto 的吞吐量对比实验（Section 7.6）中，Minos 禁用了 Dummy Module，理由是"多流传输时不需要"。但这使得对比不够完整——当需要启用 Dummy Module 时（单流或少流场景），Minos 的实际吞吐量表现未与 Ditto 直接对比

5. **攻击模型假设较弱**：假设被动攻击者只能通过 5-tuple 观察流量，不能修改或注入包。论文未讨论面对主动攻击者（如选择性丢包、流量注入）时 Minos 的鲁棒性

6. **IoT 防御仅为软件模拟**：Appendix A 的 IoT Fingerprinting 防御实验全部在软件中模拟，未在 Tofino 硬件上验证，与论文强调的"硬件线速防御"定位存在落差

---

## 七、总结

Minos 是一个基于可编程交换机（Tofino1）的加密流量分析防御系统，通过 Proxy Module（线速包头加密）、Schedule Module（动态流交错调度）和 Traffic Morphing Module（轻量 dummy 包注入 + 随机 padding）三个模块协同工作，同时提供 identity anonymity 和 traffic anonymity。其核心优势在于利用多流交错替代大量 dummy 包注入，在并发流 ≥5 时以零额外带宽开销将攻击准确率降至 20% 以下。硬件实现达到接近 100 Gbps 线速、99.2% goodput。主要局限在于：6 轮 PRINCE 加密的安全性未经充分论证；低并发流场景下对 CUMUL/kFP 等攻击的防御效果仍有差距；流交错效果高度依赖网络中的并发流数量。
