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

> **一句话总结**：用 Combinatorial Security Testing (CST) 替换 SweynTooth/GreyHound 的概率性 fuzzer，覆盖 BLE 协议栈输入空间，在 10 款 BLE 设备 + 13 个固件组合上发现 19 个独特问题。

## 问题

BLE（Bluetooth Low Energy）协议栈实现的安全测试一直是难点：HCI 抽象屏蔽了底层链路层，黑盒访问受限。前作 SweynTooth/GreyHound 用自定义 NRF52840 dongle 固件 + PSO 概率优化的 fuzzing 揭示了 17 个新漏洞，但 fuzzing 的概率本质决定了不能保证输入空间覆盖度，可能漏掉缺陷或测试时间过长。

## 核心方法

CST 基于 Covering Array (CA)：对每个 BLE 协议层独立建立 Input Parameter Model (IPM)，包含字段及合法/非法符号值（如 `~0`、`UNCHANGED`、`LARGER`、`RECALCULATE`）。借鉴 Kampel 的复合系统建模方法，对每层生成 strength t=2 的 seed CA，再用 meta CA 把多层 seed array 组合成最终 combined CA，保证层内 + 层间的 t=2 覆盖。

测试流程：从 BLE 状态机里枚举所有可达状态路径，对当前 packet to test 生成 CA，每行作为一个 malicious packet 替换原始 packet 字段值发送给 SUT。两个 oracle 协同检测：第二个 NRF52840 dongle 监听 BLE 通信，1 秒无响应判失败；同时通过 serial port 抓 `trace`/`crash`/`dump` 关键字。所有失败 case 自动 reproducer 重放剔除 false positive。

## 关键结果

- 在 10 款 BLE SoC（CC2640R2、ESP32、nRF52、bl602、CH582M、W801、RTL8720DN、BG22、Apollo3、MG126）+ 多固件版本上发现 19 个独特 fault，含多个 DoS 与潜在内存破坏。
- 与 GreyHound fuzzer 24 小时对比：CST 总测试数更少但发现更多 issue（如 RTL8720DN 上 5 vs 0、CC2640R2 5.30.00.03 上 3 vs 0、MG126 上 2 vs 0）。
- 所有错误均仅需单个参数取特定非法值即可触发——意味着 GreyHound 可能因同时变异过多字段产生 masking effect 而漏掉。
- Espressif、Realtek 已确认并修复，CVE 待分配。

## 相关

- **相关概念**：Combinatorial Testing、Covering Array、Fuzzing
- **同会议**：[[ATC-2025]]
