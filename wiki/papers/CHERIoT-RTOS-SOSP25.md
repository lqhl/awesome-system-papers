---
type: paper
name: CHERIoT-RTOS
full_title: "CHERIoT RTOS: An OS for Fine-Grained Memory-Safe Compartments on Low-Cost Embedded Devices"
authors: [Saar Amar, Tony Chen, David Chisnall, Nathaniel Wesley Filardo, Ben Laurie, et al.]
venue: SOSP
year: 2025
tags: [embedded, memory-safety, cheri, compartmentalization, rtos]
source_pdf: "[[3731569.3764844.pdf]]"
source_md: "[[3731569.3764844]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# CHERIoT RTOS: An OS for Fine-Grained Memory-Safe Compartments on Low-Cost Embedded Devices (SOSP 2025)

> **一句话总结**：与 CHERIoT capability 硬件 co-design 的嵌入式 RTOS，在 tens-of-KB SRAM 设备上提供细粒度 fault-tolerant compartment、深度接口加固与可审计静态隔离，可运行 Microvium JS、FreeRTOS TCP/IP、BearSSL。

## 问题与动机

嵌入式为省 BOM 常无 MMU，跑 C/C++ legacy 栈；上网后 Mirai 等 botnet 风险巨大。MPU/TrustZone 仅粗粒度隔离；retrofit 隔离缺接口加固与供应链审计；全量 Rust 重写不现实。

## 关键观察 / 隐含假设

- **观察 1**：无 MMU 的嵌入式场景可用 CHERI capability 作为唯一隔离机制，配合 load filter + revoker 实现确定性时空安全。
  - **依赖假设**：CHERIoT 硅片成本与普通 MCU 同级（2025 商用预期）；TCB（loader/switcher/allocator/scheduler）无 bug。
  - **可能失效场景**：物理攻击、侧信道；compiler 对 untrusted compartment 生成错误 capability 操作。
  - **证据强度**：强——硬件 spec 独立发表，OS 与之对齐。
- **观察 2**：嵌入式 integrator 需要 build-time 固定 compartment/thread 布局 + 机器可读审计报告，应对供应链与监管。
  - **依赖假设**：静态模型可覆盖部署期所有 trust boundary 变化。
  - **可能失效场景**：runtime 动态加载新 compartment（非目标 workload）。
  - **证据强度**：中——linker report + policy checker 原型，未展示大规模 firmware 审计案例。
- **假设 1**：hybrid compartment（code boundary）+ thread（flow boundary）+ micro-reboot 可在 KB 级内存下比 MPU-only 方案更细且可恢复。
  - **证据强度**：中——跑通真实 stack（JS/TCP/TLS），缺大规模 stress fault 数据。

## 核心方法

**硬件**：无 MMU；permit-load-mutable/permit-load-global 深度权限；sentry 区分 call/return 与 interrupt posture。

**OS**：四组件 TCB——loader（boot 后自毁）、switcher（~355 条汇编，compartment call）、quota-based unified heap allocator、scheduler。Compartment call 经 sealed capability；shared library 无 mutable globals。Wrapper 封装 legacy 代码（FreeRTOS TCP、BearSSL）。

## 设计取舍

- **取舍 1**：静态 compartment 换可审计性，丧失 runtime 动态加载灵活性。
- **取舍 2**：TCB 虽小但 switcher 权限大，availability 风险集中。
- **边界条件**：10s–100s KB SRAM MCU；非 Linux 级通用 OS。

## 实验与结果

- `-Oz` 编译、33 MHz Arty A7-100T FPGA 上，base OS 为 25.9 KB code 与 3.7 KB data；network+TLS+MQTT build 为 151.8 KB code（§5.3，Table 2）。
- empty compartment call 平均 209 cycles，256-B-stack call 为 452 cycles；论文引用的 Donky 比较值为 2,136 cycles（§5.3.2，Fig. 6a）。
- MQTT-over-TLS JavaScript demo 使用 13 个 compartment、243 KB total memory（182 KB code/28 KB data/33 KB heap）（§5.3.3）。
- 相对论文引用的 Donky baseline，compartment-call latency 的 benchmark 为 209/452 cycles 对 2,136 cycles；边界是 33 MHz FPGA microbenchmark（§5.3.2，Fig. 6a）。
- CPU benchmark 中，硬件面积相对 16-entry PMP 高 4.5%，CoreMark performance overhead 相对 non-CHERI RISC-V 32E 为 20.65%；边界是面积优化 core 的 FPGA implementation（§5.3.2）。

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| 基础 OS 与完整 IoT build 可在所测 footprint 内运行 | base OS 为 25.9 KB code/3.7 KB data，network+TLS+MQTT 为 151.8 KB code（§5.3，Table 2） | `-Oz`、33 MHz Arty A7-100T FPGA；不是已出货 MCU | high |
| compartment 的固定开销低于所引 Tock 对照 | 每增加一个 compartment 为 83 B，对 Tock process 的 164 B（§5.3.1） | post-link alignment 可变；比较限于引用的 Tock configuration | medium |
| compartment call 有可量化的 cycle cost | empty call 209 cycles、256-B-stack call 452 cycles，对 Donky 为 2,136 cycles（§5.3.2，Fig. 6a） | 33 MHz FPGA microbenchmark，stack clearing 主导 | high |
| 硬件扩展的面积与性能代价已测量 | 面积比 16-entry PMP 高 4.5%；CoreMark 相对 non-CHERI RISC-V 32E 的 overhead 为 20.65%（§5.3.2） | 面积优化的 core 实现；不是 OS-only overhead | high |
| 端到端 IoT demo 展示多 compartment 可行性 | MQTT-over-TLS JavaScript demo 使用 13 compartment、243 KB total memory（§5.3.3） | 单一 FPGA IoT application；不能证明 fleet reliability | high |

## Critical Analysis

### 论证链条

「成本与安全矛盾 → 硬件 capability + clean-slate OS」逻辑完整。五大原则 (P1–P5) 与 API 设计相互支撑。

### 假设压力测试

- 商业硅 2025 timeline 若延迟，整个 story 停留在 FPGA/sim。
- Untrusted compartment 任意指令前提下，侧信道与 timing 信道未讨论。
- 与 seL4 microkernel 形式 verified 路径对比，CHERIoT 验证完成度仍在进行。

### 实验可信度

真实 legacy stack 移植证明可用性。性能数字相对「普通无安全 MCU」而非「同等 MPU 方案」的细粒度对比偏少。

### 系统性缺陷

论文未讨论：OTA 更新 compartment 图；多核 CHERIoT（若存在）调度；与 Matter/TPM 等生态集成成本。

## 局限与 Future Work

- **局限 1**：静态 isolation，不适合动态 plugin 模型。
- **局限 2**：物理攻击 out of scope。
- **Future work 1**：继续验证硬件、软件与 TCB 组件，覆盖 switcher + loader 全路径，缩短 TCB 信任半径。

## 相关

- **相关概念**：CHERI、compartmentalization、MPU、memory safety
- **同类系统**：seL4、Tock、FreeRTOS
- **同会议**：[[SOSP-2025]]
