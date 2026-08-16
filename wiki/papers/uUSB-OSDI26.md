---
type: paper
name: uUSB
full_title: "µUSB: Practical and Safe USB Driver Reuse for Arm TrustZone"
authors: [Xuankai Zhang, Sijin Li, Pei Meng, Meng Wang, Yongzhao Zhang, Ting Chen, Xiaosong Zhang, Liwei Guo]
venue: OSDI
year: 2026
tags: [trustzone, usb, driver-specialization, tee, program-analysis]
source_pdf: "[[osdi26-zhang-xuankai.pdf]]"
source_md: "[[osdi26-zhang-xuankai]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 为 Arm TrustZone 复用实用且安全的 USB 驱动（OSDI 2026）

> **原题**：µUSB: Practical and Safe USB Driver Reuse for Arm TrustZone

> **一句话总结**：论文观察到特定 USB I/O 功能会沿高度确定的设备 FSM 路径运行；µUSB 因而从可信 Linux 驱动的多次变异执行中记录 MMIO、DMA 和 IRQ，离线提升成只含该功能的模板，再在 [[TrustZone]] 内重放，在 Raspberry Pi 5 上为 4 类、6 款设备生成 8 个驱动模板，达到接近或优于 native driver 的性能，但安全与正确性只覆盖被记录路径，并依赖 gold driver 和可信录制环境。

## 问题与动机

Arm TrustZone 能让 secure world 独占设备，从而在 normal-world OS 已被攻破时仍保护输入数据。但主流 TEE OS 只支持 RPMB、GPIO、SPI 等少数设备，没有 [[USB]]：USB 有 25 个 device class，audio driver 单独就约 245K SLoC，还依赖 600 多个 header 和约 560K SLoC 的其他 kernel subsystem。把整套 Linux USB stack 搬进 TEE，会大幅扩大可信计算基（TCB）和漏洞面（§2.2）。

只搬一部分 driver 也不理想。USB 数据经过 xHCI 的 MMIO、DMA ring 和 interrupt，在 trusted/untrusted boundary 上有大量 pointer 和共享状态；边界写错会产生 Iago attack 或泄露未加密的摄像头、麦克风数据。传统 record-and-replay 要么靠人工给 DMA interaction 加 annotation，要么用 symbolic/concolic execution；前者容易漏，后者跟不上 1 ms 周期的 isochronous transfer，甚至会让设备 timeout。

µUSB 不试图在 TEE 内提供完整 USB stack，而是为 trusted app 实际需要的少数功能生成 **micro-driver**，例如固定格式的录音、摄像、块读写、键鼠输入。其路线是“记录—提升—重放（record, lift, replay）”：复杂 Linux driver 只在离线可信机器上执行，TEE 最终只运行一段顺序 interaction template 和约 500 SLoC 的通用 replayer（图 1、图 3）。

## 关键观察 / 隐含假设

- **观察 1：给定 I/O 功能和合法输入后，USB 设备通常沿确定的 FSM beaten path 运行。** xHCI 规范把 MMIO、TRB ring、DMA 和 IRQ 交互标准化，因此重放同一组状态改变动作可以复现相同功能（§2.3、§3.3）。
  - **依赖假设**：设备 firmware、descriptor、时序和错误状态与录制时一致，输入变化不会触发另一条未记录路径。
  - **可能失效场景**：hotplug、power management、固件升级、传输错误、设备热状态或 vendor-specific recovery 会让 trace 偏离模板。
- **观察 2：USB driver/device interaction 与 CPU 架构相对独立，可以从 Linux 录制后在 Arm TEE 重放。** xHCI register、TRB 和 transfer semantics 由规范固定；录制机与 Raspberry Pi 5 的 OS/CPU 不同仍能工作（§2.3、表 3）。
  - **依赖假设**：目标 SoC 有可由 TrustZone 独占的 xHCI instance，且 TEE 能提供连续 DMA 内存、中断和内存屏障等基本服务。
  - **可能失效场景**：IOMMU、cache-coherence、controller errata 或 xHCI 外的 platform-specific 初始化无法由模板抽象时，跨平台复用会失败。
- **观察 3：trusted app 的 USB 使用通常比完整 OS 静态。** App 与 TEE 固定部署，可以接受设备长期连接，只需要少数明确功能，不必支持动态 discovery、hub、networking、hotplug 和复杂省电（§2.3）。
  - **依赖假设**：产品确实能冻结设备型号、端口和功能集合。
  - **证据强度**：中。论文的 surveillance、secure storage 和 trusted input 案例符合该模型，但没有生产设备 fleet 的变化数据。
- **假设 1：多次变异 trace 的结构收敛意味着必要 interaction 已覆盖。** Recorder 至少运行 10 次；实验中多数模板 2 条 trace 已找全 variant，Camera 1 需要 6 条（表 8）。
  - **证据强度**：中偏弱。收敛只说明已观察 trace 同构，不能证明未测试输入、异步错误或隐藏状态不会产生新路径；附录证明把这一点直接作为 Property 1，而非从模型推出。
- **假设 2：录制用 OS、driver 与 USB device 都可信，且 driver 是“gold driver”。** µUSB 的 correctness 继承原 driver 对设备完成状态的判断（§3.1、附录 A.3）。
  - **证据强度**：弱。该假设排除了供应链缺陷、录制期恶意设备和原 driver 的 silent error。

## 核心方法

**变异记录器（mutational recorder）**运行在精简 Linux 6.8 VM 中。开发者调用 `record(f, args, var)`，指出目标 I/O function、一个 concrete input 和哪些参数可在运行时变化。KVM hypervisor 用 stage-2 page fault 拦截 xHCI MMIO、DMA pool 和 interrupt，并同时用 ftrace/kprobe 保存 call trace；它还记录时间、随机数、DMA allocation 等少量 kernel input。Stage-2 trap 每个 DMA/MMIO event 增加约 0.03 ms，足以满足 USB 时序；stage-1 fault 则要 0.14 ms，会破坏 isochronous transfer（§4.1、§6.3.3）。

Recorder 用语义感知规则变异用户标记的动态参数，并在每次运行间重启 VM、利用 KASLR 改变地址，防止把偶然相同的 DMA address 当成常量。当大多数 trace 与 reference 在事件类型、顺序和长度上同构时停止，最少记录 10 次；若 10 分钟仍不收敛，则要求开发者减少动态参数。这一步的目标不是覆盖 driver 代码，而是逼出同一功能路径上的值变化（§4.1.2）。

**分析提升器（analytical lifter）**先对多条 trace 做 symbolic differential analysis：把 controller base、DMA buffer、用户/kernel/device input 变成 symbol，再比较相同位置的值，保留跨 trace 不变的 command/configuration，标出会随输入变化的 address、length 和 data。随后以 call trace 作为 path qualifier，对 Linux kernel source 做 context/path/flow/field-sensitive 的 qualified taint tracking，恢复动态值从输入到 MMIO/DMA write 的计算和 path constraint。没有 call trace 时，分析 12 小时仍不结束并产生超过 64 GB 中间状态；加入 qualifier 后每个功能平均 11.6 秒（§4.2、§6.3.3）。

对 camera/audio 的数十万重复 transfer event，lifter 用 peephole pattern 把访问重新卷成定长 loop。六款设备的 raw trace 从 950 到 434,154 个 event 不等，最终 template 只保留 21–59 个静态事件/循环结构（表 4）。Template 不带原 Linux driver code，签名后与 OP-TEE 静态链接。

**µUSB replayer**在 secure world 独占一套 xHCI controller，实例化模板并按 CPU/interrupt 两个 context 顺序执行。Write event 会重新计算 taint expression，且只能落到合法、不可执行的 DMA/MMIO range；read 和 IRQ 必须与模板 invariant 匹配。输入不满足 constraint 会直接报错；设备偏离路径时，replayer 停止、soft reset 后重试，持续失败则返回错误并释放 DMA，而不执行未记录的 device-specific recovery（§4.3）。

附录用 labelled transition system 说明 native driver 与 µUSB 对设备可见的 MMIO/DMA/IRQ trace 等价。但关键 Property 1——收敛 trace 足以覆盖该 I/O function——来自收敛准则和 gold-driver 假设，本身没有形式证明。因此它证明的是“在已记录功能和假设成立时的 trace equivalence”，不是完整 USB driver 的行为等价。

## 设计取舍

- **以功能特化换小 TCB**：15–400 KB template driver 比对应 native module 小 12–116 倍，也移除了大量 kernel bug；代价是每个 device/function/configuration 都要单独录制，完整 device feature 不可用。
- **以 concrete trace 换实时录制**：轻量 KVM tracing 能跟上 audio/video，却无法给出 symbolic execution 式的路径覆盖保证。
- **以 fail-stop 换机密性和完整性**：任何未记录 IRQ/value 都停止并 reset，可阻止 malicious device 把执行带到陌生路径，但 availability 可被拔盘或反复偏离轻易破坏。
- **以可信离线 pipeline 换 TEE 简洁性**：recording OS、driver、device 和 lifter 都在信任边界内；模板签名只能防部署后篡改，不能发现生成阶段的错误。
- **边界条件**：固定设备、固定功能、长期连接且 I/O trace 确定时最合适；开放式 PC USB、hub/network device、hotplug 和复杂 error recovery 不适用。

## 实验与结果

- **设置与基线**：目标实机是 Raspberry Pi 5，4 核 Cortex-A76 2.4 GHz、OP-TEE 4.4，预留 8 MB TEE RAM 给 DMA；录制机为 i9-14900K、32 GB DRAM、Linux 6.4。测试 4 个 class、5 个 vendor 的 6 款设备和 8 个 I/O function，比较 Linux 6.4 native driver 与 Raspberry Pi bare-metal Circle driver；Driverlet 不支持同一组 audio/video device，只作为理论参考。指标覆盖 throughput、latency、MFCC similarity、template size、生成时间和 tracing/analysis overhead（表 3–4、§6.3.1）。
- **存储性能**：FIO 处理 64 MiB 数据时，µUSB 平均读/写为 16.26/11.01 MiB/s，native 为 17.42/6.68 MiB/s；µUSB 读接近 native，写反而更快。小块随机写的短路径使 µUSB 与 Circle 分别达到 native 的 5 倍和 2.5 倍，但这是 CPU-bound microbenchmark，不能外推到更快 SSD 或完整 filesystem（图 6）。
- **video、audio 与 HID**：两款 camera 的单帧延迟为 2,964 ms 和 87 ms，分别比 native 低 3% 和 20%；Camera 2 的 100-frame LongBurst 最多快 26%。10 秒 audio 的 MFCC cosine similarity 均高于 0.99，延迟与 native 接近。Keyboard/mouse interrupt-to-result latency 平均比 native 低 4.5 倍、比 Circle 低 1.3 倍（图 7–8）。
- **模板体积与生成成本**：Storage、Video、Audio、HID 的 µUSB executable 分别为 24、400、160、15 KB，相对 native module 缩小 107、12、45、116 倍。生成一个 template 平均 56.9 秒，最慢 135.1 秒；differential analysis 对最大 400K 级 event trace 只需 3.29 秒，qualified taint tracking 每个功能平均 11.6 秒（表 7、图 9、§6.3.3）。
- **正确性与稳定性证据**：作者对 storage 发出 1,000 次读写并逐项比对数据，对 audio/video 人工检查配置和内容，连续 streaming 超过 24 小时；全部 template 又持续 stress test 两周。安全部分主要是对历史 CVE 和代码路径的设计分析，没有 malicious-device fuzzing、fault injection 或形式化验证（表 6、§6.2）。
- **端到端实机应用**：TEE 内 surveillance app 连续从 camera 取 frame 并写入 USB storage，1080P/480P 分别维持 1.92/11.6 FPS 超过一天；native 为 1.94/10.7 FPS。它证明两个模板能在同一实机 host controller 上组合，但仍是固定两设备、固定 workload（图 10）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| record–lift–replay 能生成可用的 TrustZone USB micro-driver | 表 4、图 6–10 | Raspberry Pi 5；4 class、6 device、8 固定 I/O function | 强 |
| 特化模板显著缩小 in-TEE driver 代码和数据体积 | 表 7、§5 | 15–400 KB，对比 Linux native module；不含离线 recorder/lifter | 强 |
| µUSB 对已测功能达到接近或优于 native 的性能 | 图 6–8、§6.3.2 | 论文选取的 storage/video/audio/HID 设备、8 MB secure DMA、平均吞吐/延迟；每类最多 2 个设备 | 强 |
| trace 收敛足以保证记录功能的正确性 | §3.3、§6.2.2、附录 A.3 | 依赖 trusted gold driver 与 Property 1；无完整 coverage proof | 中偏弱 |
| µUSB 能抵抗恶意 OS 和 USB device | 表 6、§3.1、§6.2.1 | 主要为 threat-model 推理和 CVE 代码排除；DoS、physical attack、录制环境攻击不覆盖 | 中偏弱 |

## 批判性分析

### 论证链条

论文把“完整 USB stack 太大”和“symbolic tracing 跟不上实时 transfer”映射到功能特化与轻量 concrete recording，再用 differential/taint analysis 补回动态输入，方法与动机对应清楚。实机上四类设备都工作，说明 beaten-path specialization 确有实用价值。最关键的逻辑缺口在正确性：附录的 trace-equivalence 结论依赖 Property 1，而 Property 1 正是“变异收敛已覆盖足够路径”的经验假设；形式化部分没有消除 coverage 风险。

### 假设压力测试

同型号设备若 firmware 版本、descriptor、endpoint timing 或错误恢复不同，模板可能频繁 fail-stop；不同型号更不能因为同属一个 USB class 就直接复用。多个动态输入的组合会放大状态空间，论文自己的 10 分钟 timeout 会要求缩减 mutable argument。若 gold driver 在错误状态下 silent success，µUSB 会忠实继承错误判断；若恶意 device 只在部署后特定长序列触发另一条仍“看似合法”的交互路径，有限 mutation 也未必发现。以上是该方法的固有边界，不是现有实验已排除的风险。

### 实验可信度

Raspberry Pi 5 + OP-TEE 是真实 TrustZone 硬件，设备跨 storage/video/audio/HID，性能、体积、生成开销和长时间运行均有量化，证据比 simulator 或 toy driver 更强。基线方面，native 与 Circle 合理，但最接近的 Driverlet 因功能不支持而没有定量比较；安全结论也没有红队测试。样本仍小：每类 1–2 个设备，固定配置，未测 USB 3 高速设备、hub、热插拔、故障注入或 firmware drift。media 正确性主要靠人工查看与 MFCC，而不是 bit-exact oracle。

### 系统性缺陷

部署者要维护“设备型号 × firmware × 功能 × 参数约束”的 template fleet，并在更新后重新录制、审计和签名。Replayer 遇到陌生状态只能 reset/retry，可能丢正在传输的数据，也让 malicious device 轻易制造 DoS。TEE 独占 xHCI controller 会减少 normal world 可用端口，并扩大 secure-world driver 对 DMA、IRQ 和 controller reset 的运维责任。论文没有给模板版本兼容、rollback、revocation、录制供应链审计或多 trusted-app 隔离方案。

## 局限与后续工作

- **局限 1：coverage 不是证明。** 建立包含 hotplug、stall、short packet、firmware reset 和 malformed descriptor 的 USB fault campaign，报告每个模板发现的新 trace/path 数。
- **局限 2：设备与功能覆盖窄。** 在同 class 的多 vendor、多 firmware 和 USB 3.x speed 下做交叉重放矩阵，客观划出模板可复用单位。
- **局限 3：安全验证以分析为主。** 用 malicious USB emulator fuzz device response、IRQ 顺序和 DMA length，验证所有偏离都 fail closed 且不会越界写 secure memory。
- **后续工作 1：可审计的 coverage 证据。** 将 template event、driver branch 与 mutation input 关联，输出未覆盖 branch 和不可符号化状态，而不是只给“trace 已同构”。
- **后续工作 2：版本化运维。** 为 firmware/driver/TEE 更新定义 template compatibility check、签名轮换和自动回归测试，并量化重新生成成本。

## 相关

- **相关概念**：[[TrustZone]]、[[USB]]、[[Driver-Specialization]]、[[Trusted-Execution-Environment]]
- **同类系统**：Driverlet、LDR、RevNIC
- **同会议**：[[OSDI-2026]]
