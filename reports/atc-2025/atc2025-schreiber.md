# Bluetooth Low Energy Security Testing with Combinatorial Methods

**作者**：Dominik-Philip Schreiber, Manuel Leithner, Jovan Zivanovic (SBA Research); Dimitris E. Simos (SBA Research, Salzburg University of Applied Sciences, Paris Lodron University of Salzburg)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/schreiber
**源文件**：[[atc2025-schreiber.pdf]]

---

## 一、背景

Bluetooth Low Energy (BLE) 是 IoT 设备最广泛使用的无线通信协议之一，2019 年已有 142 亿台 BLE 设备联网，预计 2027 年每年将出货 76 亿台支持蓝牙的设备。由于 BLE 面向电池供电的低功耗设备，协议复杂度相比经典蓝牙有所降低，但这也意味着加密和隐私机制需要特殊适配。

近年来，BLE 协议栈中已发现大量漏洞，从拒绝服务（DoS）到远程代码执行，影响数百万设备。然而，由于 Host Controller Interface (HCI) 的隔离层设计，测试者无法直接访问底层协议层（Baseband、LMP），导致 BLE 协议栈极难进行全面测试。现有工作（如 SweynTooth/GreyHound）通过自定义固件绕过 HCI 限制实现了 fuzzing 测试，但 fuzzing 本质上是概率性的，无法保证输入空间的覆盖度。

---

## 二、要解决的问题

1. **Fuzzing 的概率性缺陷**：GreyHound 等 BLE fuzzer 基于粒子群优化（PSO）引导概率变异，可能遗漏某些参数组合触发的漏洞，且测试执行时间不可预估。
2. **掩蔽效应（Masking Effects）**：fuzzer 倾向于同时变异过多字段，导致某个字段的异常行为被其他字段的异常所掩盖，漏洞无法被触发或观察到。
3. **缺乏覆盖保证**：fuzzing 无法提供关于输入空间覆盖度的任何形式化保证，测试者无法确信"测试足够充分"。
4. **BLE 多层协议的复杂性**：BLE 协议栈包含多个相互关联的层（Link Layer、L2CAP、ATT、GATT、GAP 等），每层有独立的字段和合法值范围，构建完整的输入模型极具挑战。

---

## 三、洞察与设计

**关键洞察**：NIST 大规模实证研究表明，所有已分析的软件故障都是由最多 6 个参数的组合触发的——这意味着不需要穷举测试所有参数组合，只需保证一定强度（strength）的组合覆盖即可高效发现绝大多数缺陷。同时，BLE 数据包天然具有"复合系统"结构（多层嵌套），可以将每一层建模为子组件，利用组合测试（Combinatorial Testing）的 Covering Array 方法系统性地生成测试用例。

基于此洞察，作者设计了一套 Combinatorial Security Testing (CST) 方法：

1. **输入建模**：将 BLE 数据包视为复合系统，每个协议层为一个子组件。为每层的每个字段定义合法值、边界值和符号化的异常值（LARGER、SMALLER、UNCHANGED、RECALCULATE），并用 `~` 前缀标记非法值以防止掩蔽效应。
2. **分层 Covering Array 生成**：先为每层独立生成 seed CA（强度 t=2），再通过 meta IPM + meta CA 将各层的 seed CA 组合成一个 combined CA，既保证层内覆盖又保证跨层覆盖。
3. **结构化状态机遍历**：替换 GreyHound 的概率引导，改为枚举状态机中所有可达路径，对每个目标状态系统性地注入 CA 中的测试用例。在到达目标状态前发送正常包，仅在目标状态发送恶意包。
4. **双 Oracle 机制**：使用第二个 NRF52840 dongle 被动监听外设的 BLE 传输（超时 >1 秒判定失败），以及串口监控（检测 "trace"、"crash"、"dump" 等关键词）。

---

## 四、实现细节

- **硬件平台**：两个 NRF52840 dongle（运行 GreyHound 自定义固件），一个用于收发，一个用于被动监听（Oracle）。通过 USB 串口与主机通信。
- **软件基础**：基于 GreyHound 框架，使用 scapy 的 BLE 扩展构造和解析任意 BLE 包。完全替换了 GreyHound 的 PSO fuzzing 组件，改为 CST 测试生成。
- **CA 生成**：采用 Kampel 等人的复合系统组合方法。每层 IPM 独立生成 seed CA（t=2），通过 meta CA 组合。使用 PICT 工具的 negative value testing 机制（`~` 前缀），确保每行最多一个非法值。
- **路径管理**：从状态机生成所有可能路径，按距初始状态的远近排序。不可达路径标记为 invalid 并跳过。若某路径 400 秒内未到达目标状态，则排除。
- **结果存储**：使用 MongoDB 记录每个测试用例的 CA 行、包历史、Oracle 结果、状态和路径信息。
- **自动恢复**：通过 ESP32 微控制器控制 USB 继电器，实现设备的自动断电重启（REST API 控制），解决 dongle 和外设偶发性崩溃问题。
- **并行化**：4 套完整测试环境并行运行（4 台主机，各配 1 个 SUT + 2 个 dongle）。
- **测试规模**：每个设备 373–2,985 个测试用例（取决于可达状态数和路径数），最长设备不到 1 天完成全部测试。

---

## 五、实验结果

### 测试目标

10 款 BLE 芯片（含多个 SDK 版本），共 13 个设备/固件组合：

| 芯片 | 厂商 | SDK 版本 |
|------|------|----------|
| CC2640R2 | Texas Instruments | 3.30.00.20, 5.30.00.03 |
| ESP32 | Espressif | 4.1, 5.0 |
| nRF52 | Nordic | 15.3.0, 17.0.1 |
| bl602 | Bouffalolab | AI-Thinker WB2 beta v1.1.8 |
| CH582M | WCH | MounRiver Studio community v1.50 |
| W801 | Hi-Link | a93b517 |
| RTL8720DN | Realtek | Ameba Boards 3.1.6 |
| BG22 | Silicon Labs | Simplicity Studio v5.7.1.1 |
| Apollo3 | Ambiq | Sparkfun apollo3 boards v2.2.1 |
| MG126 | MacroGiga | Seeed SAMD boards 1.8.4 |

### 主要发现

共发现 **19 个独立漏洞**，涵盖超时（TO）、需代码修复恢复（URWF）、需重启恢复（URN）和 core dump 四类：

| 芯片 | 版本 | TO | URWF | URN | Dump | 测试数 |
|------|------|-----|------|-----|------|--------|
| CC2640R2 | 3.30.00.20 | 1 | 4 | 0 | 0 | 1,309 |
| CC2640R2 | 5.30.00.03 | 0 | 3 | 0 | 0 | 1,188 |
| ESP32 | 4.1 | 0 | 0 | 1 | 1 | 2,115 |
| ESP32 | 5.0 | 0 | 0 | 2 | 0 | 1,910 |
| nRF52 | 15.3.0/17.0.1 | 0 | 0 | 0 | 0 | 1,309 |
| bl602 | v1.1.8 | 0 | 0 | 1 | 1 | 2,985 |
| RTL8720DN | 3.1.6 | 4 | 0 | 1 | 0 | 2,664 |
| Apollo3 | v2.2.1 | 0 | 0 | 1 | 0 | 594 |
| MG126 | 1.8.4 | 2 | 0 | 0 | 0 | 373 |

### 与 GreyHound Fuzzer 对比（当前 SDK 版本，24 小时）

| 芯片 | GH 测试数 | CST 测试数 | GH Issues | CST Issues |
|------|-----------|------------|-----------|------------|
| CC2640R2 | 2,129 | 1,188 | 0 | 3 |
| ESP32 | 5,979 | 1,910 | 0 | 2 |
| RTL8720DN | 10,153 | 2,664 | 0 | 5 |
| bl602 | 7,233 | 2,985 | 1 | 2 |
| Apollo3 | 7,935 | 594 | 1 | 1 |
| MG126 | 9,993 | 373 | 0 | 2 |

CST 方法在**更少的测试用例**下发现了**更多的漏洞**（16 vs 2 issues on current versions），但未检测 anomalies（协议偏差）。

---

## 六、批判性分析

1. **所有漏洞仅需单参数触发（t=1 即可）**：作者承认所有发现的漏洞仅需一个参数取特定值即可触发，这意味着 t=2 的组合覆盖在本实验中并未展现出比 t=1 更强的发现能力。论文的核心卖点——组合覆盖的"保证"——在实验中缺乏实质性验证。
2. **序列变异的缺失是重大局限**：CST 方法无法变异包的顺序，而 GreyHound 发现的部分漏洞恰恰依赖于包序列的改变（尤其是 pairing/encryption 阶段）。论文对此仅简单提及"future work"，但这实际上是协议安全测试中极为关键的维度。
3. **对比实验的公平性存疑**：GreyHound 运行 24 小时但其 Oracle 产生大量误报（anomalies），作者选择不评估 CST 的 anomalies，导致两者的比较维度不完全一致。此外，GreyHound 的 NRF52 dongle 不稳定时没有自动恢复机制（CST 有），这对 GreyHound 的表现构成了不公平的劣势。
4. **测试设备的代表性有限**：10 款芯片中，nRF52（Nordic）和 BG22（Silicon Labs）——两个市场占有率最高的 BLE 芯片——均未发现任何问题，反而是较小众的芯片（bl602、MG126、Apollo3）暴露了更多漏洞，其中 Apollo3 和 MG126 的 SDK 在测试时"仍在开发中"，降低了发现的实际安全影响。
5. **漏洞影响分析不够深入**：大部分发现是 DoS 类问题（设备不可用需重启），仅 bl602 的 core dump 和 ESP32 的内存管理问题暗示可能存在更严重的代码执行风险，但论文未进行进一步的漏洞利用分析。
6. **可复现性验证流程**：虽然作者使用了 reproducer 脚本排除误报，但对于 Oracle 的误报率、各设备的 false negative 情况缺乏定量分析。

---

## 七、总结

本文将组合安全测试（CST）方法应用于 BLE 协议栈的安全测试，替换 GreyHound fuzzer 的概率引导组件，通过分层建模和 Covering Array 生成提供有保证的输入空间覆盖。在 10 款 BLE 芯片（13 个设备/固件组合）上发现了 19 个独立漏洞，在更少的测试用例下比 GreyHound fuzzer 发现了更多问题。主要局限在于无法变异包序列、所有发现仅需单参数触发（未充分体现组合覆盖的优势），以及大部分漏洞影响局限于 DoS。
