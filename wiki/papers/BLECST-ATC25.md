---
type: paper
name: BLECST
full_title: Bluetooth Low Energy Security Testing with Combinatorial Methods
authors: [Dominik-Philip Schreiber, Manuel Leithner, Jovan Zivanovic, Dimitris E. Simos]
venue: ATC
year: 2025
tags: [security, ble, fuzzing, combinatorial-testing, iot]
source_pdf: "[[atc2025-schreiber.pdf]]"
source_md: "[[atc2025-schreiber]]"
---

# Bluetooth Low Energy Security Testing with Combinatorial Methods (ATC 2025)

> **一句话总结**：关键观察是 [[BLE]] 协议栈漏洞常由单个字段的非法取值触发，而 [[SweynTooth]]/[[GreyHound]] 的概率性 [[Fuzzing]] 无法保证输入空间覆盖且可能因多字段同时变异产生 masking；本文用 [[Combinatorial-Security-Testing]]（每层 + 层间 t=2 [[Covering-Array]]）替换 PSO fuzzer，在 10 款设备、13 个固件组合上发现 19 个可复现独特 fault，24 小时对比中 issue 检出数普遍高于 GreyHound 且测试用例更少。

## 问题与动机

[[Bluetooth-Low-Energy]] 是 [[IoT]]、可穿戴与医疗场景的主流短距协议，但协议栈实现长期暴露安全面：配对流程、链路层固件、控制器状态机均曾出现影响数百万设备的漏洞。测试难点在于 [[Host-Controller-Interface]]（HCI）把主机侧高层协议与控制器侧底层链路隔离，标准蓝牙适配器固件只允许通过 HCI 发包，黑盒测试者难以直接操纵 raw packet 字段。

前作 [[SweynTooth]] 基于 [[GreyHound]] 框架，用 NRF52840 自定义固件 + Python/scapy 绕过 HCI 限制，配合 BLE 状态机和 PSO 概率优化 fuzzer，在多款芯片固件中发现 17 个此前未知漏洞。作者承认该路线有效，但 [[Fuzzing]] 本质是概率搜索：既不能保证输入空间覆盖度，也可能在长时间运行后仍漏掉特定单字段触发器，或把预算耗在重复变异上。

本文的核心 claim 不是再造一套 BLE 测试硬件，而是把 GreyHound 的「可发 raw packet + 状态机遍历」能力与 [[Combinatorial-Testing]] 的覆盖保证结合，形成 [[Combinatorial-Security-Testing]]（CST）：对每个待测 packet 的各协议层建立 Input Parameter Model（IPM），生成有数学保证的 test set，用结构化替换取代概率 mutation，看能否在更少测试下发现更多、可复现的安全问题。

## 关键观察 / 隐含假设

- **观察 1：BLE 控制器/固件中的可复现 crash 与 DoS，多数只需单个参数字段取特定非法值即可触发，不需要复杂多字段组合或报文重排。** 论文在 19 个独特 fault 的事后分析中发现，所有 issue 都满足「单参数触发」；甚至 strength t=1 的 covering array 理论上就足够，而 GreyHound 在同等设备上常漏检。
  - **依赖假设**：测试 oracle 能观测到的 failure mode（超时、需复位、core dump）覆盖了目标漏洞的主要表现；IPM 里为每个字段枚举的边界值/符号变异（`~0`、`LARGER`、`RECALCULATE` 等）足够逼近真实攻击面。
  - **可能失效场景**：需要多包时序、跨状态信息依赖的 pairing/encryption 类漏洞；逻辑缺陷（如接受全零密钥）不导致 crash 或 advertisement 中断时，当前 oracle 完全看不见。
  - **证据强度**：强（针对已发现 fault 的复盘）；弱（不能外推为「所有 BLE 漏洞都是单字段触发」）。

- **观察 2：GreyHound 的多字段随机/位变异容易产生 masking effect——一个非法字段触发的异常会掩盖同包内其他非法字段的效果，降低 fuzz 效率。** 这与 PICT 的 negative value testing 原则一致：CA 生成时刻意限制每行最多一个带 `~` 前缀的非法值，且 meta CA 跨层组合时也用 `~` 标记含非法值的 seed row，避免层间 masking。
  - **依赖假设**：SweynTooth 漏检与「同时变异过多字段」存在因果关系，而非单纯运行时间或路径选择差异。
  - **可能失效场景**：若某些漏洞确实需要两个以上字段协同非法才触发，t=2 设计仍可能漏掉；论文未系统验证这类双触发器是否存在。
  - **证据强度**：中。有设计原则与事后单参数结论支撑，但缺少严格 ablation（例如强制 GreyHound 单字段变异的对照实验）。

- **观察 3：在「参数非法化」维度上，结构化遍历 BLE 状态机合法路径 + 在目标状态注入 malicious packet，比无序概率遍历更能稳定复现链路层/连接建立阶段的缺陷。** 多数 timeout、URN（需复位才恢复）发生在 initiating 状态后的恶意 `CONNECT_REQ`（如 `AA=0x00000000`）；设备错误地把非法连接参数当有效连接处理，卡在无法重新广播的状态。
  - **依赖假设**：GreyHound 状态机对目标 SUT 的路径集合足够代表真实交互；只测 reachable valid path、跳过 invalid path 不会漏掉主要漏洞类。
  - **可能失效场景**：依赖非标准状态跳转或需打乱报文顺序的 pairing/encryption 流程；不完整 BLE 实现（Apollo3、MG126）导致状态机走不完，测试覆盖率骤降。
  - **证据强度**：中到强。Table 2/3 与 JTAG 分析一致，但方法明确不覆盖 sequence mutation。

- **假设 1**：「1 秒无 BLE 发包」或 serial 口出现 `trace`/`crash`/`dump` 关键字，是安全测试足够好的 failure oracle。
  - **证据强度**：中。可复现脚本过滤了 false positive，但论文承认会漏掉不崩溃的认证/加密逻辑错误，且 timeout oracle 可能对慢恢复设备误判。

- **假设 2**：开发板 + 厂商 SDK 示例应用足以代表量产设备上的 BLE 栈行为。
  - **证据强度**：弱到中。覆盖 10 家 SoC 有广度，但仍是 lab 级 sample app，未测真实产品固件集成、OTA 补丁策略或多连接/多租户场景。

## 核心方法

实现完全建立在 [[GreyHound]] 的 BLE 通信栈上：NRF52840 自定义固件负责时序与 CRC，主机侧 Python 2.7 + scapy 扩展构造任意层 packet。论文**移除**原有 PSO 引导的 fuzzing 模块，换成 CST 流水线，保留状态机驱动的连接生命周期管理。

**测试策略（对应 Figure 3/4）**：先从 BLE 状态机枚举到达各状态的所有路径，按「离初始状态近者优先」选 path；标记该 path 及重传/超时转移为可遍历，到达「当前待测状态」后，分析下一待发 packet 含哪些协议层。对每个层生成 strength t=2 的 seed [[Covering-Array]]，再按 Kampel 复合系统方法构造 meta IPM（参数是各层 CA 的行号），生成 meta CA 后组合成跨层 combined CA。每行映射为一次 malicious packet：仅在该状态 outgoing 边替换字段，其余 traversal 仍发 normal packet；CA 耗尽后处理自环，再换下一 path。

**输入建模**：每层独立 IPM，字段值来自 GreyHound scapy 模型 + BLE 规范边界分析 + 符号操作符（`UNCHANGED`、`LARGER`、`SMALLER`、`RECALCULATE`）。非法值用 `~` 前缀，并遵循「每行最多一个非法值」以减少 masking。分层建模是为控制 CA 规模——参数值过多时 CA 指数膨胀，这是 CST 在复杂协议上的工程权衡。

**Oracle 与可信度**：Oracle 1 用第二块 NRF52840 被动监听 SUT 发包，>1s 无包判失败；Oracle 2 在有 serial 的开发板上匹配 crash 关键字。所有失败 case 用自动 reproducer 重放，不可复现则丢弃。测试元数据（CA 行、packet history、oracle 结果、路径/状态）写入 MongoDB。针对 dongle/SUT 偶发 hang，作者用 ESP32 控制 USB 继电器掉电复位，并并行 4 套 setup 缩短总墙钟时间（单 SUT 全量 CA 可接近一天）。

与 SweynTooth 的差异要点：**覆盖保证 vs 概率搜索**；**不做** GreyHound 的 specification deviation（anomaly）检测；**不做**报文顺序重排——这是相对原 fuzzer 的明确能力缺口。

## 设计取舍

- **t=2 覆盖 + 分层/meta CA 换规模**：相对 exhaustive 或更高 strength，测试集从天文数字降到千级，但层间全组合仍可能爆炸；作者建议未来用 variable-strength CA，只在 length/type 等相互依赖字段上做跨层覆盖。
- **结构化路径遍历换 sequence fuzz 能力**：保证每个合法状态下的 packet 字段组合被系统覆盖，但主动放弃 SweynTooth 擅长的 pairing/encryption 报文重排类漏洞；旧固件对比中部分 GH-only issue 正源于 sequence 变异。
- **双 oracle + 硬复现门槛换召回率**：reproducer 提高报告可信度，代价是逻辑型漏洞（密钥/认证接受异常）几乎不可能进入结果集；GreyHound 的 anomaly oracle 因 false positive 过多被作者弃用，CST 侧完全不评估 anomaly。
- **复用 GreyHound 基础设施换维护负担**：继承 Python 2.7、旧 scapy 模型与 dongle 固件，免去了重新实现射频频谱侧通道，但也继承 dongle 不稳定、无自动复位（原 GH 实验）等运维问题。
- **开发板 SUT 换可扩展性**：易于 JTAG 分析与 serial oracle，但与真实产品形态、功耗管理和 RF 环境仍有距离。

## 实验与结果

- **对象**：10 款 BLE SoC 开发板（TI CC2640R2、Espressif ESP32、Nordic nRF52、Bouffalolab bl602、WCH CH582M、Hi-Link W801、Realtek RTL8720DN、Silicon Labs BG22、Ambiq Apollo3、MacroGiga MG126），合计 13 个 SDK/固件组合；含 SweynTooth 曾测芯片的新旧版本。
- **独特 fault 总量**：19 个可复现独特 issue，类型含 timeout（TO）、需代码修复才能恢复广播（URWF）、需硬复位（URN）、serial core dump；多数为 [[Denial-of-Service]]，dump 类指示潜在内存破坏/任意代码执行风险。
- **典型触发器**：恶意 `CONNECT_REQ` 中 `AA=0x00000000` 使 ESP32 5.0 误判已连接、无法重开广播；ESP32 4.1 同包可致 HCI desync 与 core dump；bl602 在 length request 状态 `max_rx_bytes=0` 触发 dump；Apollo3 在 pairing request 非法 auth method 致挂死。
- **当前固件 24h 对比（Table 3）**：CST 测试数普遍少于 GH（如 ESP32 5.0：1910 vs 5979），但 issue 更多（ESP32 2 vs 0；RTL8720DN 5 vs 0；CC2640R2 5.30.0.03 3 vs 0；MG126 2 vs 0；bl602 2 vs 1）。GH 在 nRF52/CH582M 等记录更多 anomaly，CST 不评估该项。
- **旧固件复测（Table 4，约 1000+ 测试量级）**：CC2640R2 3.30.0.20 上 CST 5 issues vs GH 2；ESP32 4.1 上双方各 2 issues 但触发器不同（GH 一例依赖 sequence 修改）。说明 CST 在参数空间更系统，但 sequence 类漏洞仍属 GH 优势区。
- **补丁有效性**：多数 SweynTooth 时代漏洞在新 SDK 已修；CC2640R2 旧版 3 个问题在新版仍存在 3 个；ESP32 5.0 修了一个 dump 但引入新 URN。
- **负责任披露**：提前 90 天通知厂商；Espressif 全版本修复并计划 CVE，Realtek 有回应；PoC 与 MongoDB 导出已公开（Zenodo）。

## Critical Analysis

### 论证链条

observation → design → result 在「单字段非法 packet 导致 crash/DoS」这一子类漏洞上闭合较好：masking 假设解释 GH 漏检，分层 t=2 CA 给出可执行 test set，19 个可复现 fault 与 24h 对比支持「更少测试、更多 issue」的 claim。JTAG 与 GAP 事件分析进一步说明多数 SUT 在错误连接参数后进入「以为已连接、无法广播」的坏状态，与 initiating 状态测试策略一致。

链条在两类地方变弱。第一，把「CST 检出更多」外推成「CST 全面优于 fuzzing」不成立：方法明确不测 sequence anomaly，GH 的 anomaly 统计被剔除，对比维度不对称。第二，「所有 fault 只需 t=1」是结果反推，不是实验设计目标；若存在需 t≥2 的协同触发器，当前 meta CA 仍可能漏掉，论文未做否定实验。

### 假设压力测试

**Workload 变化**：真实 IoT 产品常有多连接、bonding 列表、长时间待机、主机侧协处理器交互；开发板跑 vendor sample app 且单 central 单 peripheral，结论对「量产固件 + 复杂应用状态」的外推需谨慎。

**Oracle 盲区**：接受全零加密密钥、错误认证参数但不崩溃的场景被作者明确列为 false negative；这意味着 CST 对「机密性/完整性降级」类漏洞几乎无检测力，与 conformance/security property testing 差距大。

**硬件与规模**：四副本并行 + USB 继电器复位说明工具链对硬件可靠性敏感；NRF52 17.0.1 等组合零 issue 可能意味着栈质量高，也可能意味着 IPM/oracle 对该实现不敏感——论文未区分「无漏洞」与「测不到」。

**时间预算公平性**：24h GH 对比控制了墙钟，但 GH 无自动复位、W801 等设备迭代不稳定，可能压低 GH 数字；CST 侧路径超时剔除（400s 无进展则换 path）也会改变有效搜索空间。对比支持「CST 更高效」，但不是严格 controlled variable 实验。

### 实验可信度

**强项**：多样 SoC _vendor、新旧固件对照、可复现脚本、JTAG 深挖、与 SweynTooth 同硬件栈对比，使结果对「BLE 控制器参数校验缺陷」这一具体问题可信。Table 2 区分 TO/URWF/URN/Dump 比单一 crash 计数更有安全语义。

**弱项**：baseline 基本只有 GreyHound 一条线，缺少对其他 BLE fuzzer（如 BLESA 类协议逻辑测试）或纯随机/穷举小模型对照；anomaly 维度被人为拿掉使 GH 优势被低估。metrics 侧重 fault 计数与测试数，缺少「覆盖了多少 IPM 组合」「每条 path 覆盖率」等更贴近 CT 理论的指标。生产 trace、真实手机 central 角色、RF 干扰环境均未涉及。

### 系统性缺陷

**执行与运维**：单 SUT 全量测试近一天，路径不可达检测与硬件复位使工程复杂度高；继承 Python 2.7 与老旧依赖，长期维护成本论文未讨论。

**尾延迟与隔离**：未测多设备并发测试时的 RF 干扰；oracle 1s 超时阈值对不同恢复速度固件可能产生系统性偏差。

**可观测性与调试**：MongoDB 存档利于复现，但对「为何某 CA 行未触发」缺少在线诊断/最小化反馈循环；失败归因仍依赖人工安全分析区分语义等价触发器。

**兼容性**：依赖 GreyHound 专用 dongle 与固件，标准 HCI 工具链用户无法直接复用；第二 oracle 需要 serial/JTAG，与量产封闭设备差距大。论文未讨论测试本身对设备寿命、NVM 磨损或合规射频的影响。

## 局限与 Future Work

- **局限 1（论文明确）**：不支持 combinatorial **sequence** 变异；SweynTooth 中依赖 pairing/encryption 阶段报文重排的漏洞超出 scope，这是相对 GH 最大的能力缺口。
- **局限 2**：不可靠路径识别与逐 path 测试使 wall-clock 远长于 GH 的单次迭代速率；MG126/Apollo3 等不完整实现导致 executed tests 仅 373–594，覆盖不均匀。
- **局限 3**：Oracle 面向 crash/unresponsive，对逻辑型安全缺陷不敏感；GH anomaly oracle 因 false positive 被放弃，也未提出更干净的 specification oracle。
- **Future work 1**：引入 Sequence Covering Arrays（SCA）并加可调权重启发式，优先在 pairing/encryption 等复杂阶段做有限 sequence 覆盖，避免组合爆炸。
- **Future work 2**：variable-strength CA，仅对 length/type 等跨层依赖字段维持高强度，其余层降 strength，在覆盖保证与测试规模间做可证化折中。
- **Future work 3**：对「单参数触发」结论做反向验证——系统搜索是否存在必须多字段或 sequence 才触发的漏洞类，以确定 t=2 与 path-only 策略的真实边界。

## 相关

- **相关概念**：[[Combinatorial-Testing]]、[[Combinatorial-Security-Testing]]、[[Covering-Array]]、[[Fuzzing]]、[[Denial-of-Service]]、[[IoT]]、[[Host-Controller-Interface]]
- **同类系统**：[[GreyHound]]、[[SweynTooth]]
- **同会议**：[[ATC-2025]]
- **对比**：[[BLECST-ATC25]] 与 [[SweynTooth]] — 覆盖保证的结构化字段测试 vs 概率 fuzz + 报文序变异