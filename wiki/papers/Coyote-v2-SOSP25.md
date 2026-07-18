---
type: paper
name: Coyote-v2
full_title: "Coyote v2: Raising the Level of Abstraction for Data Center FPGAs"
authors: [Benjamin Ramhorst, Dario Korolija, Maximilian Jakob Heer, Jonas Dann, Luhao Liu, Gustavo Alonso]
venue: SOSP
year: 2025
tags: [fpga, shell, heterogeneous, rdma, reconfiguration, multi-tenancy]
source_pdf: "[[3731569.3764845.pdf]]"
source_md: "[[3731569.3764845]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-14
---

# Coyote v2: Raising the Level of Abstraction for Data Center FPGAs (SOSP 2025)

> **一句话总结**：三层 hierarchical shell 支持 services/user logic 动态 partial reconfiguration + 多流统一接口 + RoCEv2/共享虚拟内存， synthesis 快 **15–20%**、runtime reconfig 快一个数量级，AES pipeline idle 降 **7×**。

## 问题与动机

数据中心 [[FPGA]] 常从零搭建 networking/DMA/MMIO，~75% 精力在 infrastructure。现有 shell（Coyote、Catapult、Vitis）services 静态、接口不通用（单 host stream、难多输入 vector add）、缺透明 multi-user pipelining。

## 关键观察 / 隐含假设

- **观察 1**：将 services 从 static layer 移到可动态 reconfig 的 shell layer，可简化 static layer 并 orders-of-magnitude 加速 service 切换。
  - **依赖假设**：partial bitstream 管理可靠；corrupt bitstream 可回滚旧配置。
  - **可能失效场景**：极大 bitstream 或频繁切换导致 reconfig 带宽成为新瓶颈。
  - **证据强度**：强——§9.3 两数量级加速 vs full reconfig。
- **观察 2**：CBC AES、自回归 LLM 等顺序依赖 workload 需 multi-client 透明 pipelining 才能填满硬件。
  - **依赖假设**：多请求可并行占用 pipeline 各 stage，单请求内依赖不变。
  - **可能失效场景**：单 tenant 独占、无并发时 pipelining 无收益。
  - **证据强度**：中——AES 7× idle reduction，LLM 例为概念性。
- **假设 1**：与 GPU 对等的共享虚拟内存 + RoCEv2 栈可使 FPGA 成为 datacenter first-class citizen。
  - **证据强度**：中——有外部 GPU-FPGA DMA 贡献，生产规模部署数据有限。

## 核心方法

三层：**static**（CPU-FPGA 链路）、**dynamic services**（RDMA、MMU、DMA、traffic sniffer…）、**user applications**（可多租户 partial reconfig）。

统一接口：多路 host/card/network stream、硬件发起 DMA、generic interrupt。软件抽象支持 workload pipelining 与 fair-sharing。

## 设计取舍

- **取舍 1**：shell 与 application 绑定——换 service 需重链 user app，换灵活性为安全隔离。
- **取舍 2**：开源维护负担 vs 商业 shell 的 vendor 支持。
- **边界条件**：AMD Alveo 系列验证；Intel FPGA 可移植性依赖 static layer 封装。

## 实验与结果

- 相比 Vivado full reprogramming，Alveo U250 的 total reconfiguration latency 为 536.2–929.1 ms 对 55,922.5–71,417.9 ms；边界是含磁盘读取/bitstream copy 的 5-trial benchmark（§9.3，Table 3）。

- Synthesis 时间降 **15–20%**（locked static checkpoint）
- Runtime reconfiguration 快 **~100×** vs offline full reconfig
- AES pipelining：idle 时间最高降 **7×**
- hls4ml 集成：<10 行 Python 部署 NN，推理快一个数量级 vs baseline

## Claim–Evidence Map

| Claim | Evidence | Evaluation boundary | Confidence |
|---|---|---|---|
| 分层 locked-checkpoint app flow 缩短 FPGA build | 三种 shell configuration 的 app flow 比 shell flow 少 15–20%（§9.2，Fig. 7b） | Alveo U250 build-time，非 runtime performance | high |
| shell partial reconfiguration 的 total latency 显著更低 | 536.2/709.0/929.1 ms，对 Vivado 55922.5/63045.2/71417.9 ms；kernel-only 51.6/72.3/85.5 ms（§9.3，Table 3） | 5 trial；Vivado 包含 PCIe hot-plug/driver reinsertion，total 含 disk/copy | high |
| 多 cThread 提升 AES-CBC pipeline 利用率 | 单 cThread 在约 32 KB 饱和 280 MB/s；32 KB 时随 cThread 数线性增（§9.5，Fig. 10） | 一个 10-stage AES-CBC core、single vFPGA、round-robin arbiter | high |
| Coyote v2 支持按需 HLL kernel load | 对 Coyote baseline comparable performance，partial reconfiguration 平均 57 ms（§9.6，Fig. 11） | 单 HLL workload；comparable 无精确图表数值 | medium |
| hls4ml demo 中 Coyote backend 有受限优势 | Fig. 12 报告性能优势且 resource utilization 相近（§9.7） | U55C intrusion-detection network；PYNQ/Vitis baseline 未充分优化 | medium |

## Critical Analysis

### 论证链条

Table 1 feature matrix 建立 gap → 三 requirements → 三层设计，结构清晰。从 Coyote v1 演进路径可信。

### 假设压力测试

- 生产环境（Azure Boost 类）partial reconfig 失败率与 SLA 未披露。
- Multi-tenant 公平性在极端带宽竞争下如何保障？
- 与 DPU/SmartNIC 固定 function 的 TCO 对比缺失。

### 实验可信度

Workload 多样（AES、HLL、NN）。对比 baseline 含 Coyote v1 和 hls4ml。缺端到端 datacenter 应用（如 PolarDB FPGA 路径）production 数字。

### 系统性缺陷

论文未讨论：shell 漏洞 surface；bitstream 供应链安全；与 cloud FPGA 计费/调度集成。

## 局限与 Future Work

- **局限 1**：主要 AMD 平台，跨 vendor 需重复 static layer 工程。
- **局限 2**：multi-tenant 安全隔离 formal guarantee 未证明。
- **Future work 1**：与 cloud orchestrator 集成的 service-level SLO 与 reconfig 调度策略。

## 相关

- **相关概念**：FPGA shell、partial reconfiguration、[[RDMA]]、heterogeneous computing
- **同类系统**：Coyote、Catapult、Vitis XRT、TaPaSCo
- **同会议**：[[SOSP-2025]]
