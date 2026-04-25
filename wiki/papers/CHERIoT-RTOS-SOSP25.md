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
---

# CHERIoT RTOS: An OS for Fine-Grained Memory-Safe Compartments on Low-Cost Embedded Devices (SOSP 2025)

> **一句话总结**:基于 CHERIoT 硬件 capabilities 的嵌入式 RTOS,在与普通 MCU 同等面积/功耗的低成本芯片上提供细粒度 fault-tolerant compartment + 时空内存安全,跑得动 Microvium JS 引擎、FreeRTOS TCP/IP stack 和 BearSSL,只需几十 KB SRAM。

## 问题

嵌入式设备为了成本(每分钱 BOM 都要计较)往往砍掉 MMU/MPU 等安全特性,同时跑 C/C++ 这类不安全语言的 legacy stack。当它们被推到 IoT 场景上网,Mirai 这类僵尸网络就能轻松圈养数十万台。现有嵌入式 OS 要么只能用 MPU/TrustZone 做粗粒度隔离(MPU 通常只支持 8 个 region),要么要求重写成 Rust 等安全语言,对既有代码不现实;同时缺少接口加固、可用性保证、供应链攻击防御的研究。

## 核心方法

**硬件-软件协同设计**:与 CHERIoT core(CHERI capability 的嵌入式特化)co-design——无 MMU,capability 是唯一隔离机制,每 8 字节 heap granule 关联一个 revocation bit,load filter 在 capability 加载时检查 revocation bit,硬件 revoker 后台 sweep。新增 permit-load-mutable(强制深度不可变)、permit-load-global(深度 no-capture)permission,加上 sentry(sealed entry)做前后向控制流区分,一次性把 compartment 接口加固到 "深度语义" 层面。

**Hybrid compartment 模型**:Compartments 在代码边界上隔离,threads 在跨/内 compartment 的 flow 上隔离,支持细粒度 micro-reboot(单个 compartment reset 到 pristine 状态)。TCB 只有 4 个组件:loader(仅在 boot 时全权)、switcher(~355 条汇编,管 context switch/compartment call)、allocator、scheduler——每个都仅持有完成其安全属性所需的最小权限。

**API 与 auditing**:Opaque objects(通过 token API 虚拟化 sealing,绕过硬件仅 7 种 seal type 的限制)、allocation capabilities + quotas(授权 + 配额分离)、quota delegation、basin of futex 的锁和消息队列。静态 compartment/thread 布局使得 firmware image 能在集成时被机械审计,linker 产出人机可读的结构报告。

## 关键结果

- 在只有几十 KB SRAM 的低成本 MCU 上实现了比 MMU 更细粒度的隔离
- 运行 Microvium JS 引擎 + FreeRTOS TCP/IP + BearSSL,证明 legacy code 迁移路径
- CHERI 的形式化验证基础沿用,硬件和软件正在进行形式化验证工作
- 开源硬件和软件;CHERIoT 商业 silicon 预计 2025 出货

## 相关

- **相关概念**:[[CHERI]]、[[Capability]]、[[Memory-Safety]]、[[Compartmentalization]]、[[TCB]]
- **同类系统**:seL4、Tock OS、FreeRTOS
- **同会议**:[[SOSP-2025]]
