---
type: paper
name: GPU-CC-Security
full_title: "Blueprint, Bootstrap, and Bridge: A Security Look at NVIDIA GPU Confidential Computing"
authors: [Zhongshu Gu, Enriquillo Valdez, Salman Ahmed, Julian James Stephen, Michael V. Le, Hani Jamjoom, Shixuan Zhao, Zhiqiang Lin]
venue: MLSys
year: 2026
tags: [confidential-computing, gpu-security, nvidia, tee, attestation, sev-snp]
source_pdf: "[[812b4ba287f5ee0bc9d43bbf5bbe87fb.pdf]]"
source_md: "[[812b4ba287f5ee0bc9d43bbf5bbe87fb]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# GPU-CC-Security：蓝图、引导程序和桥接：NVIDIA GPU 机密计算的安全视角（MLSys 2026）

> **原题**：Blueprint, Bootstrap, and Bridge: A Security Look at NVIDIA GPU Confidential Computing

> **一句话总结**：在 H100 + AMD SEV-SNP CVM 上通过 instrument 开源 kernel/UVM 驱动、preload 闭源 CUDA/nvTrust 与 BAR0 全空间扫描，重建 GPU-CC 的 FSP/GSP/SEC2/CE 蓝图与 SPDM 派生 **44** 类密钥链，量化 BAR0 Decoupler（**99.78%** 读零）并逐路径发现 RPC 元数据明文、CPU-GSP DMA 时序侧信道、UVM SEC2 队列暴露等残余泄漏，已向 NVIDIA PSIRT 披露。

## 问题与动机

NVIDIA GPU Confidential Computing（GPU-CC）把 [[TEE]] 信任边界从 CPU 扩展到 GPU，使用户在 CVM 内跑 AI workload 时**无需改应用**即可获得 in-use 数据保护。但对 MLSys 研究者而言，判断其是否满足声明 threat model 极难，原因有三：

1. **规格封闭**：FSP、GSP、SEC2 等引擎仅出现在示意图与专利中，公开白皮书细节不足。
2. **生态专有**：CUDA runtime、user-mode driver、GPU 固件多为闭源或仅二进制分发。
3. **兼容层叠**：为兼容 legacy GPU 栈，CPU-GPU 数据经 RPC、DMA、UVM、CUDA launch、scrub 等多条异构路径，每条机制、格式、粒度不同，攻击面难推理。

论文不提出新系统，而是以 **Blueprint → Bootstrap → Bridge** 三阶段**逆向重建** GPU-CC 架构并做 targeted security experiment，填补「能用 GPU-CC」与「理解 GPU-CC 是否真安全」之间的鸿沟。平台为 Hopper H100；Multi-GPU、Trusted I/O 在测试机上不可用，仅概念讨论（Appendix B）。完整路径分析与证书链见 [[812b4ba287f5ee0bc9d43bbf5bbe87fb]]。

## 关键观察 / 隐含假设

- **观察 1：GPU-CC 安全依赖 staging buffer 中介模型——CVM private memory 与 GPU CPR 之间的一切敏感数据必须先加密/签名再进入未保护共享内存。**
  - **证据**：Figure 4 + 六类数据路径 instrument；SPDM master secret 派生 GSP/SEC2/CE 分路径密钥（§7.2）。
  - **依赖假设**：host/hypervisor 可读写 staging buffer 与 BAR 映射区；PCIe 上流量可被观测与篡改；CVM 侧 CPU-CC（AMD SEV-SNP）已正确隔离 private memory。
  - **可能失效场景**：若某路径绕过 staging（未来 Trusted I/O 直访 guest memory），本文 Bridge 分析需重写；CVM 被攻破则 GPU 配置权落入攻击者，统一 TCB 崩溃。

- **观察 2：bulk payload 已加密，但 queue metadata、指针、时序信号仍大量明文留在 staging buffer 或 BAR0——legacy 栈与 CC 要求之间存在系统性缝隙。**
  - **证据**：RPC 仅加密 command/status **payload**，physical address table、queue header、readPtr/writePtr 明文（§A.1）；scrub pushbuffer 签名未加密（§A.5）；SEC2 Channel 的 GPFIFO/GPPUT 未加密（§A.4）；fault shadow buffer PUT 指针经 BAR0 暴露（§A.3）。
  - **依赖假设**：攻击者能扫描 CVM 物理内存定位 page-aligned 自指 address table（§A.1）；或读 BAR0 残留寄存器。
  - **可能失效场景**：云厂商禁用 host 物理内存访问、或 BAR0 进一步收紧后，部分 metadata 攻击门槛升高——但 hypervisor 级 adversary 在 threat model 内仍成立。

- 观察 3：启用 GPU-CC 后 BAR0 Decoupler 将绝大多数寄存器读归零，但仍有 0.02%（1042 个字段）返回非零值。
  - **证据**：16 MB BAR0、4-byte stride 全扫描；非 CC 模式 **7.94%** 返回 value、**80.25%** error；GPU-CC 下 **99.78%** 为零（Fig. 2）。
  - **依赖假设**：读零可能混淆「未映射」与「受保护」，但 **1042** 个可读字段对管理操作仍必要；寄存器语义专有，作者无法逐字段定性风险。
  - **可能失效场景**：不同 VBIOS/驱动版本暴露集合可能变化；Blackwell 上 GSP 经 SEC2 初始化路径迁移（§7.1）或改变 firewall 行为。

- 观察 4：CPU-GSP DMA 传输耗时对 4096 B 大块呈双峰分布，小传输（8–256 B）由 RPC 固定开销主导——时序与传输大小可相关。
  - **证据**：CVM 生命周期 **4394** 次 CPU-GSP 传输（453 read / 3941 write）；Fig. 6 直方图显示 4 KB 与大块/小块簇分离。
  - **依赖假设**：攻击者能观测 RPC 通道或 DMA 完成时间（host 侧）。
  - **可能失效场景**：constant-time RPC 或噪声注入可缓解；高负载下时序信号可能被淹没——论文未测并发干扰。

- **假设 1：威胁模型继承 VM-based CPU-CC（Intel TDX / AMD SEV）并扩展——adversary 控制 firmware、hypervisor、BMC、PCIe 流量，可 flash VBIOS、重分配 GPU，但不包括芯片 decap 与可用性攻击。**
  - **证据强度**：**强**——与 NVIDIA 公开 threat model 对齐；论文明确 out-of-scope DoS 与物理探针。
  - **可能失效场景**：租户仅信任云 hypervisor 但不信任同机其他 VM 时，MIG/侧信道类攻击（论文引用的 prior work）需与 CC 模式交叉评估，本文未深入。

- **假设 2：闭源 CUDA user-mode driver 对 kernel args、QMD、command queue 的保护方式，可由 CE/SEC2 密钥用法与 UVM 类比合理推测。**
  - **证据强度**：**弱**——Table 2 中 CUDA 路径多项标为 `?`；依赖 OpenSSL preload 与 GetKMB API 观测，非完整控制流证明。
  - **可能失效场景**：CUDA 版本迭代、Blackwell Trusted I/O 可能改变数据路径，推测失效。

## 核心方法

研究按时间线分三阶段，每阶段方法论不同（§4）。

### Blueprint：架构引擎角色重建

通过开源 **NVIDIA kernel-mode driver**、**UVM driver** instrument，以及对 **CUDA runtime**、**nvTrust** 的 library preload，拦截与 FSP/GSP/SEC2/CE 的交互，再与专利/白皮书交叉验证：

| 引擎 | 角色（GPU-CC） |
|------|----------------|
| **FSP** | RISC-V MCU；secure boot 链前端；向 GSP 下发签名 GSP-FMC/GSP-RM |
| **GSP** | 控制平面；SPDM Responder；RMAPI RPC + CPU-GSP DMA 密钥协商 |
| **SEC2** | GPU-CC 专用 RISC-V MCU；CPR 建立、attestation、scrub、secure workload channel（可验签不可加密 outbound） |
| **CE** | 逻辑/物理 copy engine；h2d/d2h AES + per-channel IV 防 replay；CPR 访问控制 |

FSP vs SEC2 在「设置 CC 模式 / attestation」上的职责在专利与 GTC 表述间有迁移（Hopper→Blackwell），作者认为二者均在 TCB 内，安全语义等价。

### Bootstrap：可信初始化

1. **Secure boot**：CEC EROT（Microchip CEC1736）→ FSP → GSP → SEC2；GSP-FMC 经 MCTP CoT 由 FSP 验签后启动 GSP-RM。
2. **密钥派生**：kernel driver SPDM Requester 与 GSP Responder 协商 master secret，派生 **44** 类密钥——GSP **6**（RPC×2、DMA×2、fault×2）、SEC2 **6**（user/kernel × data/HMAC + scrubber×2）、8 个 logical CE 各 **4**（user/kernel × h2d/d2h）= **32**（Table 1）。
3. **Firewall**：BAR0 Decoupler + CPR 直访阻断；host 不能经 BAR2 读 GPU CPR。
4. **Device attestation**：DIK（fuse）→ AK（firmware measurement 混合）签名 report；verifier 拉 device cert chain（5 级）+ OCSP 吊销检查 + RIM golden measurement 比对（64 条 record）；report 含 opaque driver/VBIOS ID。

### Bridge：六类运行时数据路径安全评估

对每条路径做 Methodology → Observation → Security Insight（主文摘要，附录 A 完整）：

1. **CPU-GSP RPC**：解码 **1588** 种 RMAPI 命令；payload 加密但 metadata 明文 → 可跟踪调用状态、篡改 readPtr/writePtr 重排/跳过 RPC。
2. **CPU-GSP memory transfer**：经 staging 的 encrypt/DMA/decrypt 流程正确，但 **4 KB** 级传输暴露时序侧信道。
3. **GPU memory faults**：GSP 加密 fault packet 至 shadow buffer；replayable/non-replayable 路径统一；PUT 指针 BAR0 泄漏，风险低（fault 稀少）。
4. **UVM**：GPU-CC 引入 SEC2 Channel → 16 WLC/LCIC 对 → 间接 CE push；WLC/LCIC/CE 关键结构在 CPR 或加密 staging 中，但 **SEC2 Channel 自身队列结构未保护**。
5. **Memory scrubbing**：SEC2 scrubber channel HMAC 签名 memset pushbuffer；**pushbuffer 明文**、**completion semaphore 未保护**。
6. **CUDA**：instrument kernel/UVM/OpenSSL；观测 `cpu sec2 {data,hmac} user` 与 `lce{x} {h2d,d2h} user` 密钥；大流量走 CE、小结构推测走 SEC2 pull 模型——闭源导致 Table 2 多项未知。

## 设计取舍

- **兼容 legacy GPU 栈 vs 端到端加密**：选择在旧 RPC/DMA/UVM/CUDA 通道上**逐路径打补丁**（staging + 会话密钥），而非重写软件栈；换来用户无感部署，但 metadata/timing/scrub semaphore 等「非 bulk data」保护不一致。

- **SEC2 只解密不加密 outbound**：简化 GPU 侧硬件，但 driver 侧 semaphore、scrub 完成信号必须明文或另寻通路；增加 host 观测与篡改面（完整性仍靠 HMAC/AES-GCM tag）。

- **BAR0 Decoupler 读零 vs 完全拒绝**：**99.78%** 字段读零隐藏寄存器语义，利于防探测，但 **1042** 个仍可读字段缺乏公开文档——安全与可管理性之间的黑箱权衡。

- **Attestation 依赖在线 RIM/OCSP**：verifier 用本地 root 替换 driver 提供的 root 防恶意驱动；但依赖 NVIDIA 在线服务与 RIM 版本同步，air-gapped 或滞后 RIM 时策略不明。

- **边界条件**：单 GPU passthrough + SEV-SNP CVM 最贴合分析；Multi-GPU NVLink **不加密**（H100 Protected PCIe 仅保护 PCIe 段）、Trusted I/O 未启用时，staging 双跳开销与遗漏保护风险最高。

## 实验与结果

**平台**：双路 AMD EPYC 9634 + SEV-SNP；**8×** H100 SXM5 80GB（VBIOS 96.00.61.00.01）；单 GPU passthrough 至 CVM。两套 guest：RHEL 9.4 + driver **550.54.15** + CUDA 12.4；Ubuntu 22.04 + driver **570.86.15** + CUDA 12.8；各 64 GB RAM。

**Blueprint / Bootstrap**
- 重建四引擎职责图（Fig. 1）与 SPDM 密钥表（Table 1，**44** keys）。
- BAR0 扫描（§7.3）：GPU-CC 下 **99.78%** 读零，**0.02%**（**1042**）非零，**0.19%** error。
- Attestation 链：5 级 device cert + RIM file cert chain；64 条 measurement vs golden list。

**Bridge（Table 2 摘要）**
- **确认问题**：CPU-GSP RPC 元数据机密性/完整性（C/I）；CPU-GSP DMA 时序信道（C）；UVM SEC2 队列部分泄漏（C/I）；scrub 通道明文 pushbuffer + 未保护 semaphore（C/I）。
- **低风险**：fault PUT 指针暴露。
- **未观测问题**：UVM WLC/LCIC/CE bulk 路径 bulk 加密有效；CE IV replay 防护按设计工作。
- **未知**：CUDA 多条目（闭源）。

**披露**：全部 findings 已报 NVIDIA PSIRT。

## 批判性分析

### 论证链条

链条：**障碍**（GPU-CC 黑箱）→ **方法**（驱动 instrument + 专利关联 + 全 BAR0 扫描 + 分路径实验）→ **结论**（bulk 数据保护大体到位，但 metadata/timing/协调信号残留泄漏，integrity 可被部分削弱）。

最强支撑：（1）开源驱动 + **1588** RPC 类型 + 物理内存 dump 的 RPC metadata 证据；（2）**4394** 次 DMA 时序统计；（3）BAR0 定量前后对比。链条在「重建架构」与「发现具体路径缺陷」上闭合良好。

薄弱环节：CUDA 路径大量 **reasoned speculation**，Table 2 标 `?`；未构建端到端 exploit，多为「可观测/可篡改」层面的 security insight；对「metadata 泄漏的实际 ML 模型重建影响」未量化（与 pre-CC 侧信道论文对比仅定性）。

### 假设压力测试

**Workload**：实验覆盖 UVM 页迁移、CUDA kernel launch、memory scrub 等通用路径，但未测大规模 **Multi-GPU** 训练、**MIG** 分片、或高频 **NCCL** collective——Appendix B 指出 NVLink 明文，生产多卡 CC 风险更高。

**硬件**：固定 **H100 SXM5**；Blackwell 上 GSP 初始化可能经 SEC2、Trusted I/O 将改变 staging 模型——结论需按架构版本迁移验证。

**部署**：SEV-SNP CVM + GPU passthrough；Intel TDX + GPU-CC 栈未测。Driver **550** vs **570** 行为差异（如 scrubber 专用 key）仅部分提及。

**对抗模型**：假设 host 能读 CVM 物理内存做 address table 扫描——在正确配置的 SEV-SNP 下 private memory 应不可读；攻击针对的是 **unprotected staging** 与 **BAR 映射区**，而非 guest encrypted memory 本身。若 hypervisor 错误映射 staging 到 guest 可读区，风险模型变化，论文未讨论 misconfiguration。

### 实验可信度

**优点**：可复现性相对同类安全研究较高（开源驱动 instrument + 明确平台/驱动版本）；定量 BAR0 扫描；分路径表格化；负责任披露。

**限制**：
- 无 formal verification 或自动化路径枚举；闭源组件依赖 intercept 间接推断。
- 时序实验为生命周期累计分布，非主动 adversary 模拟。
- Multi-GPU / Trusted I/O / 最新 Blackwell 特性**未实测**，Future 方向偏规格级。
- 寄存器 **1042** 暴露字段无功能标注，风险评级保守。

### 系统性缺陷

- **可观测性**：CC 模式下 host 失去大部分 GPU 寄存器/CPR 直访，运维/debug 与 security audit 成本上升；论文未讨论 attestation 失败后的降级策略。
- **性能**：staging encrypt/decrypt 双跳；与 PipeLLM 等后续性能优化 work 正交，本文未测 overhead。
- **TCB 大小**：FSP+GSP+SEC2+CE+kernel driver+CUDA+nvTrust+CVM firmware 构成庞大统一 TCB；CPU-CC 历史漏洞（SEV-SNP/TDX）可直接危及 GPU-CC。
- **在线依赖**：RIM/OCSP 服务可用性影响 attestation；论文未讨论离线策略。
- **论文未讨论**：生产环境 GPU 热迁移、BMC 带外管理与 in-band nvTrust 交互的组合威胁建模深度有限。

## 局限与后续工作

- **局限 1**：测试平台禁用 Multi-GPU 与 Trusted I/O，Bridge 分析本质上是 **单 GPU + staging-centric** 模型；NVLink 明文多卡场景（Appendix B.1）留待后续架构（Blackwell NVLink encryption）。
- **局限 2**：CUDA user-mode 栈闭源，六类 CUDA 数据对象的保护状态未完全确认，是 GPU-CC 安全论证的最大空洞。
- **局限 3**：发现以 leakage/tampering **潜力**为主，未演示完整攻击链（如凭 RPC 元数据重排导致越权 CPR 访问），对「partial integrity loss」的实际危害边界仍依赖 NVIDIA 内部不变量。

- **Future work 1**：对 **1042** 个残留 BAR0 字段做语义标注与必要性证明；公开 register allowlist 与 GPU-CC 模式差异说明。
- **Future work 2**：RPC/DMA metadata 全量加密 + constant-time RPC 的 performance–security 实测（作者已建议，需 vendor 配合）。
- **Future work 3**：Multi-GPU **peer-to-peer key** 建立与 NVSwitch 威胁模型下的端到端实验；Trusted I/O（Intel TDX Connect / AMD SEV-TIO / Blackwell）启用后重新审计六类路径是否消除 staging 类漏洞。
- **Future work 4**：在闭源 CUDA 栈上构建 binary analysis 或 NVIDIA 协同的 formal channel model，将 Table 2 中 `?` 项闭合。

## 相关

- **相关概念**：[[RDMA]]（DMA 与 I/O 威胁模型相关）、[[Disaggregation]]（GPU 卸载与跨域数据路径）
- **同类工作**：Graviton/HIX/SAGE/Honeycomb 学术 GPU-CC；Intel TDX、AMD SEV-SNP CPU-CC 综述与漏洞研究；PipeLLM、Fastrack 等 GPU-CC 性能优化
- **同会议**：[[MLSys-2026]]
- **上游技术**：NVIDIA Hopper GPU-CC、nvTrust attestation、open-gpu-kernel-modules
