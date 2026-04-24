---
title: "Blueprint, Bootstrap, and Bridge: A Security Look at NVIDIA GPU Confidential Computing"
authors: [Zhongshu Gu, Enriquillo Valdez, Salman Ahmed, Julian James Stephen, Michael V. Le, et al.]
year: 2026
venue: MLSys
tags: [gpu-security, confidential-computing, tee, nvidia-h100, spdm]
---

# Blueprint, Bootstrap, and Bridge: A Security Look at NVIDIA GPU Confidential Computing

**作者**：Zhongshu Gu, Enriquillo Valdez, Salman Ahmed, Julian James Stephen, Michael V. Le, Hani Jamjoom, Shixuan Zhao, Zhiqiang Lin
**单位**：IBM Research, The Ohio State University
**会议**：MLSys 2026
**链接**：[MLSys Proceedings 2026](https://proceedings.mlsys.org/paper_files/paper/2026)
**源文件**：[[812b4ba287f5ee0bc9d43bbf5bbe87fb.pdf]]

---

## 1. 背景

机密计算（Confidential Computing）通过可信执行环境（TEE）在公有云上保护运行中的敏感数据与计算。早期工作聚焦 CPU 机密计算（CPU-CC），如 Intel TDX 和 AMD SEV，把保护域限制在 CPU 封装内并对系统内存进行加密。随着大语言模型和视觉模型推动 GPU 成为核心算力，NVIDIA 从 Hopper 架构开始引入 GPU Confidential Computing（GPU-CC）：把信任边界从 CPU 扩展到 GPU，形成统一的保护域，使不互信的多方能在不暴露私有数据的情况下协同执行 AI workload。

GPU-CC 对用户几乎无感：不需要修改应用代码或数据就能启用。但这份"易用"建立在一套跨系统软件、固件、硬件的复杂改造上。对 ML 系统社区研究者而言，要在给定威胁模型下判断 GPU-CC 是否满足特定安全需求，就必须深入理解其架构和执行机制。然而三重障碍让这件事很困难：

1. **缺乏公开规范**：NVIDIA 只发布了 high-level 白皮书，FSP / GSP / SEC2 等关键引擎只在示意图上出现，职责和交互细节未披露。专利文件有更多技术信息但是用法律化、抽象化语言写成。
2. **私有生态**：除了开源 GPU 内核模块和 nvTrust，GPU-CC 相关组件大多要么嵌入在 GPU 硬件内，要么只以二进制分发。
3. **系统复杂性**：为了兼容既有实现，GPU-CC 在异构、遗留组件之上叠加新保护机制。CPU-GPU 之间的数据传输走多条不同路径，每条路径都有独立的传输方式、数据格式和粒度，攻击面显著扩大。

---

## 2. 要解决的问题

作者希望通过三个阶段性的分析，回答"GPU-CC 是否真的满足机密计算的安全要求"：

- **Blueprint**：GPU-CC 内部有哪些架构引擎？它们各自承担什么安全职能？现有白皮书、专利、开源代码之间对引擎角色的描述是否一致？
- **Bootstrap**：从硬件上电到 GPU-CC 进入 READY 状态之间，秘钥协商、固件认证、防火墙、设备认证如何编排？信任链从哪里发起、在哪一环交接？
- **Bridge**：运行时 CVM 和 GPU 之间需要穿越不受信任的 PCIe 的数据路径有哪些？每条路径是否真的提供了 confidentiality + integrity 保证？遗留了哪些易被攻击的 metadata、timing、semaphore？

论文明确界定 **scope 外**：可用性（DoS）、对 HBM 进行开封去盖等高侵入性物理攻击，以及尚未在 H100 启用的 Multi-GPU / Trusted I/O 等新特性。

---

## 3. 洞察与设计

**关键洞察**：GPU-CC 的安全性不是由某一个独立引擎的强度决定，而是由"CPU 信任域 ↔ 不受信任的 PCIe ↔ GPU 信任域"之间每一条数据路径上"加密 / 签名 / staging buffer / metadata"组合的最弱环节决定。NVIDIA 为了在 proprietary ecosystem 上维持对 legacy 软件栈的兼容，在多条路径上只加密了 payload 而留下了 queue header、地址表、pointer、semaphore 等 metadata 以明文形式暴露在共享内存中——这些残留足以泄露计算行为，甚至可能让攻击者通过操纵指针改变执行顺序。因此重建一个"coherent view"并系统化枚举每条路径，就能暴露白皮书无法呈现的风险。

基于这一洞察，作者把分析分成三阶段，每阶段采用不同方法论：

### 3.1 Blueprint（静态架构）

作者把 GPU-CC 的关键引擎聚焦到四个 RISC-V 微控制器 / 硬件引擎上：

| 引擎 | 角色 | 关键能力 |
|---|---|---|
| **FSP** (Foundation Security Processor) | 硬件信任链锚点 | 安全启动、校验 GSP-FMC / GSP-RM 签名；早期版本还承担 GPU-CC 模式设置与 attestation |
| **GSP** (GPU System Processor) | GPU 控制面 | 托管 SPDM Responder 进行密钥协商；RMAPI RPC 通道终点；AES 硬件 |
| **SEC2** (Secure Processor) | GPU-CC 专用安全引擎 | 设立 CPR；生成 attestation report（基于硅内固化的 DIK）；签名验证；memory scrubbing；secure workload submission（只能解密，不支持加密） |
| **CE** (Copy Engine) | 批量数据搬移 | H100 上 8 个 logical CE；每个 CE 持有 4 个密钥（h2d/d2h × user/kernel），共 32 把；负责 CPR ↔ non-CPR 的加解密传输和 IV 管理 |

### 3.2 Bootstrap（初始化）

启动链路为：**CEC EROT → FSP → GSP → SEC2**。CEC1736 作为外部硬件 Root of Trust，FSP BROM 作为内部第二重校验。GSP 启动后，NVIDIA kernel-mode driver 中的 SPDM Requester 与 GSP 内的 SPDM Responder 协商 master secret，派生全部 session key。

作者整理出完整的密钥列表（共 **40+ 把**）：
- GSP 相关 6 把（RPC × 2、DMA × 2、replayable/non-replayable fault × 2）
- SEC2 相关 6 把（data/hmac × user/kernel + scrubber data/hmac）
- CE 相关 32 把（8 个 logical CE × h2d/d2h × user/kernel）

启用 GPU-CC 后，**BAR0 Decoupler** 防火墙会屏蔽绝大多数寄存器访问；BAR2 对 CPR 的访问也被切断，所有 CPU-GPU 数据传输必须走 staging buffer。设备认证基于五级证书链（Root → Model → Provisioner → Device Identity → Attestation），Verifier 将 attestation report 中 64 条 measurement 与 NVIDIA RIM service 提供的 golden measurement 逐条比对。

### 3.3 Bridge（运行时数据通道）

作者将 runtime 通道归类为 6 条数据路径（见下图），每条都需要跨越"CVM private memory（受 CVM key 保护） → staging buffer（不加密，I/O 可见） → GPU CPR（受 GPU-CC firewall 保护）"的边界：

1. **CPU-GSP RPC**：走 RMAPI over shared memory
2. **CPU-GSP Memory Transfers**：DMA over staging buffer
3. **GPU Memory Faults**：GSP 写入 shadow buffer，通知 UVM driver
4. **UVM**：三类 channel（SEC2 Channel / WLC × 16 / LCIC × 16）协作；两阶段 bootstrap + indirect CE push
5. **Memory Scrubbing**：走 SEC2 scrubber channel，只签名不加密
6. **CUDA**：由闭源 user-mode driver 管控，5 类数据（user data / kernel code / kernel args / QMD / command queue）需各自保护

---

## 4. 实现细节

研究方法本身即是论文的"实现"部分——作者开展了一系列反向工程实验：

**静态分析**：
- 对开源部分（kernel-mode driver、UVM driver）插桩记录控制流
- 对闭源部分（CUDA runtime、user-mode driver）用 `LD_PRELOAD` 预加载修改过的 OpenSSL，拦截所有加解密调用捕获密钥字符串
- 从 NVIDIA SDK 抽取 1,588 种 RMAPI 命令的 encoding（FINN 工具生成），把捕获 log 中的命令反编码

**动态测量**：
- BAR0 扫描程序：以 4 字节步长遍历 16 MB 空间（0x400000 次读），对比 non-GPU-CC / GPU-CC 模式下返回 value / zero / error 的比例
- 拦截 4,394 次 CPU-GSP DMA 传输（453 读 + 3,941 写），覆盖从 8 字节到 4,096 字节的尺寸
- 主动触发 CUDA memory fault 观察 shadow buffer 机制
- 拦截 SEC2 签名函数回溯到 memory manager 识别 scrubber 调用源

**测试平台**：
- dual-socket AMD EPYC 9634（SEV-SNP）+ 8× NVIDIA H100 SXM5（80 GB HBM）
- Host: Ubuntu 22.04.5 + Linux 5.19
- CVM: RHEL 9.4 (Linux 6.1.91, CUDA 12.4) 与 Ubuntu 22.04 (Linux 6.8, CUDA 12.8) 双配置
- VBIOS 96.00.61.00.01；单 GPU passthrough

---

## 5. 实验结果

### 5.1 BAR0 寄存器可见性变化

| 模式 | 返回 Value | 返回 Zero | 返回 Error |
|---|---|---|---|
| 非 GPU-CC | 7.94% | 11.81% | 80.25% |
| GPU-CC | **0.02%**（1,042 个字段） | **99.78%** | 0.19% |

防火墙将 99.78% 的寄存器屏蔽为 0，但仍留有 1,042 个可访问字段，文档缺失意味着无法独立判断其必要性。

### 5.2 CPU-GSP 内存传输的 timing channel

拦截 4,394 次传输（读 453 / 写 3,941），测量执行时间 vs 传输大小：
- 小传输（8–256 bytes）：执行时间由 RPC 固定开销主导，size 几乎无影响
- 大传输（4,096 bytes）：执行时间显著上移，与小传输形成 **bimodal 分布**

由此产生一个可观察的 size-dependent timing signal，攻击者仅通过 RPC channel 时间即可推断传输大小或活跃度。

### 5.3 六条数据路径的安全评级

| Data Path | Engine | Confidentiality | Integrity | 关键漏点 |
|---|---|---|---|---|
| CPU-GSP RPC | GSP | **leak** | partial | RMAPI metadata（physical address table / readPtr / writePtr / seqNum / elemCount）明文 |
| CPU-GSP DMA | GSP | ok | ok | Size 信息经 timing 泄露 |
| GPU Memory Faults | GSP | ok | ok | Shadow buffer PUT pointer 通过 BAR0 暴露（低风险：故障稀疏） |
| UVM | SEC2, CE | potential | partial | SEC2 channel 的 GPFIFO / GPPUT / semaphore 未加密 |
| Memory Scrubbing | SEC2 | **leak** | partial | Scrubber pushbuffer 只签名不加密；完成 semaphore 未保护 |
| CUDA | SEC2, CE | ? | ? | 闭源 user-mode driver，只能推断 |

关键发现（已向 NVIDIA PSIRT 披露）：

1. **RMAPI 物理地址表自引用**：首项存储表自身的物理地址，攻击者可在 CVM 物理内存上以 4096 字节步长扫描，若某 64-bit 值等于该位置地址即锁定表起始，进而定位全部 queue 元素
2. **SEC2 Channel metadata 未加密**：GPPUT / GPFIFO / tracking semaphore 在 staging buffer 可见，可被操纵重定向执行（但 method 有签名，不能直接注入任意 method）
3. **Scrubber 完成 semaphore 明文**：SEC2 只支持解密不支持加密，没有 `sec2_cpu_*` 方向的密钥，攻击者可观察或篡改完成信号

---

## 6. 批判性分析

1. **攻击的实用性边界偏弱**：整篇文章把发现定位为"潜在攻击面"和"leakage"，但没有一个端到端的 PoC 演示从这些 metadata 泄露中真正窃取出模型权重、训练样本或指令序列。timing channel 的 bimodal 区分只能判别 "大 vs 小"两档，距离真实威胁模型中的 membership inference / model stealing 仍隔着几层。Security insight 停留在"may weaken confidentiality / partially undermine integrity"，缺少攻击可行性证据。

2. **威胁模型宽泛但未穷尽**：作者声明 adversary 能完全控制 host、SMM、hypervisor，还能 reflash VBIOS 和重分配 GPU，但并未 address 这些能力叠加后的场景。例如 reflash VBIOS 是否会在 attestation 前被 FSP 捕获？BMC 写入与 BAR0 写入能否联合绕过防火墙？论文选择性演示单一攻击面。

3. **方法学的可重复性问题**：很多结论依赖于对 NVIDIA 专利的解读和 GTC talk 截图，而专利"以广义法律语言写就"。作者承认 FSP 与 SEC2 职责有"migration"但无法区分。对于不同 driver 版本（550 vs 570），论文只说"later versions introduced two dedicated scrubber keys"，未量化哪些发现在未来 driver 会失效。Blackwell 上 GSP 由 SEC2 引导的说法也仅是"suggestion"。

4. **实验规模与统计性**：4,394 次 DMA 被作为 timing channel 证据，但 CVM 正常运行中 DMA 频率、size 分布的覆盖范围未讨论；只用两档 size（≤256B vs 4,096B）难以说明攻击者能解多细。bimodal 只说明"有变化"，并未给出如 KL 散度之类的判别指标。

5. **负责任披露的效果不透明**：论文宣称已 disclosed to NVIDIA PSIRT，但 PSIRT 是否接收、是否修复、是否拒绝、CVE 编号等后续信息一概缺失。读者无法据此判断这些发现的严重性是否得到了厂商承认。

6. **Bridge 小节对 CUDA 完全是推断**：`?` 的风险评级意味着最核心的用户面路径并未被真正验证。论文把推断以 "reasoned speculation" 形式写入 A.6，这类内容在安全审计中价值有限，读者难以据此评估 CUDA 通道的真实强度。

---

## 7. AI Infra / MLSys 视角

尽管这是一篇 security 导向论文，它对 AI Infra / MLSys 研究者的启发远超纯安全范畴：

- **TEE overhead 的根因诊断**：作者枚举的 6 条数据路径、40+ 把密钥、staging buffer 双重拷贝解释了已有文献（Tan 2024、PipeLLM、Fastrack）报告的 confidential GPU 下推理/训练性能下降的**结构性来源**。优化 GPU-CC 下 LLM serving 的研究者可据此判断：哪些 overhead 是必须的（CE 加解密）、哪些是可以重构的（CPU-GSP RPC metadata 仍走 plaintext 反而不阻塞时延）、哪些应该联合规避（pushbuffer 加解密 + CPR 搬移）。

- **可迁移到 AI Infra 的设计思路**：
  - **WLC/LCIC 的两阶段 bootstrap** 本质是"先验证信任链，再让无验证的热路径跑"。同样的思路可借鉴到 vLLM / SGLang 的 scheduler 下：preempt / KV cache swap 路径如果受 TEE 保护，可以设计类似"signed prologue + encrypted runtime"结构降低每次 swap 的校验成本。
  - **SPDM-based key 协商 + per-channel IV** 的替代 TLS 方案适合 disaggregated serving 的 prefill ↔ decode 内部链路：如果未来 disagg inference 跑在多 CVM / 多 GPU 上，这套密钥层级可直接复用。

- **值得跟进的研究问题**：
  1. 能否把 **RMAPI metadata 泄露** 用于 side-channel attack 推断 LLM 的 batch size、KV cache eviction 模式，从而恢复用户 prompt 长度 / 活跃用户数？这是 GPU TEE 下的 membership inference 新入口，实验一台 H100 + nvtrust 即可复现
  2. GPU-CC 下 8 个 logical CE 的 32 把 key 能否被用来 **并发加密多 tenant 流量**？如果每 tenant 绑定一个 CE，multi-tenant LLM 服务能在单 GPU 上实现 key-level isolation（比当前 MIG 更细粒度）
  3. **Multi-GPU NVLink 未加密**（Hopper 上明确未实现，Blackwell 才引入）意味着 tensor parallelism、sequence parallelism 数据在 inter-GPU 传输中暴露。是否能设计 application-level 的加密重叠，使 TP/EP 通信在 NVLink 加密到位前就具备保护？这是大模型训练落地 confidential cloud 的卡点
  4. **Trusted I/O（TDX Connect、SEV-TIO）+ GPU DMA to CVM private memory** 路线图下，staging buffer 被移除后的性能增益可量化：把这篇论文的 6 条路径用 TIO 重建会剩几条？每条 latency 降多少？是开放的 MLSys 实验题

- **最具价值的切入点**：把该工作作为 baseline 系统模型，建立一个 **confidential GPU inference benchmark suite**，覆盖论文枚举的 6 条数据路径 × 典型 LLM workload（prefill / decode / prefix cache / KV migration），开源 profiler 并量化 per-path 的 throughput / latency / leakage——这一 benchmark 可支撑未来所有"加速 confidential LLM serving"的论文。

---

## 8. 总结

本文通过在 NVIDIA H100 上开展系统性反向工程，首次公开构建了 GPU-CC 的"coherent view"：Blueprint 层面辨识了 FSP / GSP / SEC2 / CE 四个关键引擎及其 40+ 把密钥；Bootstrap 层面拆解了 CEC EROT 起始的信任链、SPDM 密钥协商、BAR0 Decoupler 防火墙（屏蔽 99.78% 寄存器）和五级证书链 attestation；Bridge 层面枚举了 6 条运行时数据路径，发现 RMAPI metadata 明文暴露、CPU-GSP DMA timing 侧信道、SEC2 channel 的 GPPUT/semaphore 未加密、scrubber 完成信号缺乏保护等多项问题，均已向 NVIDIA PSIRT 披露。论文的主要贡献是把一个 proprietary 安全系统变为可被社区 scrutinize 的研究对象，为后续 confidential AI 系统设计、TEE 性能优化和安全验证奠定了基础。主要局限在于仍缺少端到端攻击 PoC、CUDA user-mode 路径完全依赖推断、以及与厂商披露后续的透明度不足。对 MLSys 研究者而言，本文既是理解 confidential LLM serving 性能结构的必读材料，也是一系列新研究问题（metadata side channel、Multi-GPU NVLink 加密、Trusted I/O 性能）的跳板。
