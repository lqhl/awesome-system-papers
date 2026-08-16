---
type: paper
name: Nested-SEV
full_title: "Nested SEV: Secure and Generic SEV Support for Nested Virtualization"
authors: [Kazuki Takiguchi, Kenichi Kourai]
venue: OSDI
year: 2026
tags: [confidential-computing, nested-virtualization, amd-sev, hypervisor, memory-encryption]
source_pdf: "[[osdi26-takiguchi.pdf]]"
source_md: "[[osdi26-takiguchi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 嵌套虚拟化中的安全通用 SEV 支持（OSDI 2026）

> **原题**：Nested SEV: Secure and Generic SEV Support for Nested Virtualization

> **一句话总结**：Nested SEV 让受 AMD SEV 保护的 L1 VM 同时运行多个 L2 VM，并按“L1 hypervisor 是否可信”提供两种机制：SEV virtualization 给 L1/L2 独立硬件 context，SEV passthrough 让它们共享 context；原型覆盖 KVM、BitVisor、Xen 和 SEV₀/SEV-ES/SEV-SNP，平均性能退化为 0.9%–30%，但保证不包括 L0 绕过 L1 处理 VM exit、侧信道、DoS 和 L0-L2 合谋。

## 问题与动机

嵌套虚拟化有三层：公有云的 L0 hypervisor 管理 L1 VM，虚拟云提供者在 L1 VM 中运行自己的 L1 hypervisor，再为用户创建 L2 VM。若 L1 VM 不受保护，恶意云管理员可以先控制 L1 hypervisor，再间接破坏所有 L2 VM；只给 L2 打开 SEV 因而不够。

已有方案各缺一块。Microsoft 的 nested SNP patch 能保护多个 L2 VM，却不能给承载它们的 L1 VM 开 SEV，L0 仍可直接攻击 L1 hypervisor。Hecate 和 OpenHCL 同时保护 L1/L2，但依赖 SEV-SNP 的 VM Privilege Level（VMPL），缺少 MMU virtualization，只能支持一个 L2，而且 L2 必须信任最高 VMPL 的 L1 hypervisor。

Nested SEV 想同时覆盖两个真实场景：虚拟公有云中，L2 tenant 不信任 L0 和 L1；虚拟私有云或 VM introspection 中，组织信任自己的 L1 hypervisor，只需防底层 L0。两者不应被强行塞进同一个安全—性能点。

## 关键观察 / 隐含假设

- **观察 1：是否信任 L1 决定 SEV context 是否应共享。** 不信任 L1 时，L2 必须有独立 encryption key、ASID 和 RMP ownership；信任 L1 时，共享 context 反而允许加密的 L1-L2 memory sharing、直接检查 L2 状态和更快 I/O（§3，图 2、表 1）。
  - **依赖假设**：部署者正确选择 trust model。SEV passthrough 不是较快但等价安全的 virtualization，它明确把 L1 放进 L2 的 TCB。
- **观察 2：不能让不可信 L0 模拟保存秘密的 AMD Secure Processor。** virtual AMD-SP 只转发并翻译 command，真正的 L2 context 始终由 physical AMD-SP 保存；real RMP 也由硬件维护。作者称之为 emulation-less multiplexing（§3、§4.5–§4.6）。
  - **依赖假设**：processor 与 AMD-SP 正确可信，command buffer 的篡改能被 launch measurement/remote attestation 等既有机制发现。
- **观察 3：共享 key 不足以满足 SEV-SNP 完整性。** RMP 同时检查 ASID 和 GPA；L1、L2 若用不同 GPA 指同一页会检查失败，用重复 GPA 指不同页又会允许 swap。passthrough 因而让每个 L2 page 的 L2 GPA 等于唯一 L1 GPA（§5.3，图 6）。
  - **依赖假设**：L1 能预留足够、互不重叠的高地址 GPA；该选择限制 L2 可用 GPA 范围并需要 custom firmware。
- **观察 4：安全等级与性能不是单调关系。** SEV-SNP 的 memory integrity 更强，但 VM exit 不做 SEV-ES 的 VMSA CRC，某些网络和 I/O workload 反而更快；真正开销取决于 L1 hypervisor、bounce buffer、NPT、VM exit 和 huge page（§7）。
- **假设 1：威胁模型继承并进一步收窄 SEV。** CPU/AMD-SP 可信；不考虑 L0 通过 VM-exit routing 或 VMCB 操纵绕过 L1，不考虑 access-pattern/VM-exit side channel、DoS，也不考虑恶意 L2 与 L0 合谋（§2.3、§6）。

## 核心方法

### 两种机制对应两种信任模型

**SEV virtualization** 面向 L0、L1 都不可信。L1 hypervisor 看到 virtual SEV 接口，为每个 L2 创建不同于 L1 和其他 L2 的 context。physical AMD-SP 同时保存 L1/L2 key，real RMP 同时表示 L0-owned、L1-owned 和 L2-owned page；L0 只做 virtual-to-real ASID、GPA/HPA translation，不接触 key（§3–§4）。

**SEV passthrough** 面向可信 L1。AMD-SP 根本不知道各 L2 VM，L1 把自己的 ASID 和 encryption key 复用于所有 L2，这就是 SEV context decoupling。L1 可读 L2 的 memory、VMSA 和 register state，L0 仍只看到密文。该方式还支持不使用 AMD SVM 的 Xen paravirtualized VM 和 PVM 一类 software L2（§3、§5）。

两种机制均支持 SEV₀、SEV-ES 和 SEV-SNP。SEV₀ 只加密 memory；SEV-ES 还保护 VM exit 时的 register state；SEV-SNP 再以 RMP 提供 page ownership 和 integrity。它们的安全保证不能混写。

### SEV virtualization：让加密 L1 仍能管理独立 L2

L1 与 L2 使用不同 key，因此共享 DMA buffer 必须由 L2 和 L1 都清掉 C-bit。L0 也能读这些 unencrypted page，L2 若要对 L0/L1 保密，仍需 full-disk 或 end-to-end encryption。VMCB₁₂ 和 NPT₁₂ 也保持未加密，因为 L0 要生成 shadow VMCB₀₂/NPT₀₂；论文认为这些结构本就受不可信 hypervisor 控制，不额外降低其 SEV threat model（§4.1–§4.3）。

同步 shadow NPT 通常要让 L0 模拟 L1 的 page-table write，但加密 L1 的 register state 使模拟昂贵。Nested SEV 采用异步方式：第一次 write 只解除 NPT₁₂ write protection，让 L1 重执行；等 L1 随后 flush TLB 时，L0 才同步 shadow NPT 并重新保护（§4.3）。

MMIO 在 SEV-ES/SNP 下由 L2 的 `#VC` handler 解码 instruction，把必要 byte 和 GPA 放进 GHCB，再经 L0 转发给 L1；SEV₀ 使用 Decode Assists。virtual RMP 是 L1 可读的 cache，安全决定仍写入 real RMP。virtual AMD-SP 同理只转发物理命令；SEV context 和 SNP guest context page 从不落到 L0 模拟器（§4.4–§4.6）。

L0 不能读加密的 L1 host-save area。L1 进入 L2 时，L0 直接 `VMRUN` 加载 L2 VMSA；L2 exit 后再直接加载 L1 VMSA，依靠 processor 在 exit 时隐式保存原状态。L1 还可直接准备 GHCB 并 `VMGEXIT`，省去一次无意义的 `#VC`（§4.7，图 5）。

### SEV passthrough：共享加密状态但分开 GPA

共享 ASID 后，L1 与 L2 能直接访问同一 encrypted buffer，无需 L2 bounce buffer；L1 也能直接读 VMSA 解码 MMIO，不再需要 virtual AMD-SP、virtual ASID 或 L2 `#VC` path（§5.1–§5.2）。代价是 L1 可完整观察和修改 L2，且 AMD-SP 没有独立 L2 identity，因此不支持 L2 hardware attestation，只能信任 L1 boot 或使用 vTPM 软件证明（§6）。

为通过 SNP RMP check，L1 给每个 L2 page 分配全局唯一 GPA，并令 L1 GPA 与 L2 GPA 相同。原型让 L0 给 L1 提供 1 GiB huge page，并在 L1 的 4 GiB 以上地址空间分给 L2。传统 x86 firmware 从固定低地址启动，因而作者改造 qboot，让 firmware 和 ACPI 64-bit table 可放在任意 GPA；AP 使用 ACPI Wakeup Mailbox 从 long mode 启动（§5.3）。

Xen paravirtualized L2 不使用 NPT/SVM，天然共享 L1 context；特权 `PVALIDATE` 由 L1 的 `#GP` handler 代执行，page ownership 用新 hypercall 修改（§5.4）。

### SEV-ES 的 VMSA pooling

passthrough 没有 virtual AMD-SP，L1 不能临时请求加密新 VMSA。L0 在启动 L1 时预先准备有限 VMSA，L1 把它们做成 pool，只给当前 active vCPU 分配。切换时，L1 保存旧 register state、装入新状态，但 SEV-ES 在 TMR 中保存 VMSA CRC 防 rollback；直接改内容会让 `VMRUN` 失败（§5.5，图 7）。

作者逆向确认 VMSA 使用三个 CRC-32C，并利用只在 VM exit 时使用的三个 32-bit field 做 backward CRC adjustment，恢复原 checksum。L0 无法照做，因为它看不到加密 VMSA。SEV-SNP 用 RMP 保护 VMSA，不需要这套 pooling/CRC 技巧。

## 设计取舍

- **独立 context 换取最强 L1/L2 隔离**：SEV virtualization 防 L0 和 L1，但共享内存必须明文，VM exit、NPT 与 boot path 更长。
- **共享 context 换取 I/O 与管理能力**：passthrough 可用 encrypted shared buffer、VM introspection 和 paravirtualized L2，却要求完全信任 L1，且没有 L2 hardware attestation。
- **physical multiplexing 换取硬件信任复用**：不用扩展 AMD-SP 或在 L0 保存 key，但 virtual command、address translation 与 shadow state 更复杂。
- **exclusive GPA 换取 SNP integrity**：避免 page swap/alias attack，也让 huge page 有优化机会；却牺牲部分 L2 GPA space，并要求 custom firmware 与 L1 memory planning。
- **支持三种 SEV variant 换取配置复杂性**：使用者可按 workload 选择，但“SEV 已开启”不再足以描述 confidentiality、register protection 和 integrity 到底是哪一级。
- **软件原型换取威胁模型缺口**：不需要新 AMD 硬件，但无法阻止 L0 劫持 VM-exit control flow；更强隔离可能需要类似 TDX module 的硬件仲裁。

## 实验与结果

- 原型以修改后的 Linux/KVM 6.11.0 与 QEMU 9.1.0 作为 L0，在 L1 分别运行 KVM/QEMU、BitVisor 和 Xen 4.16 paravirtualization；覆盖 SEV₀、SEV-ES、SEV-SNP。主机为第四代 AMD EPYC 9334、128 GB DDR5-4800、1.6 TB SAS SSD 和 10 GbE NIC；L2 均分配 6 vCPU/8 GB，KVM/Xen L1 分配 12 vCPU/16 GB，BitVisor L1 分配 6 vCPU/8 GB。论文汇总的平均性能退化跨组合为 0.9%–30%（§7、表 2）。
- 单层虚拟化中，SEV₀ 的 `VMMCALL` VM exit 比 no-SEV 慢 41%，SEV-ES 又是 SEV₀ 的 2.9×，SEV-SNP 因不做 VMSA CRC 比 SEV-ES 快 12%。nested SEV virtualization 约为 no-SEV nested 的 2×；passthrough 比对应 virtualization 快 0.5%–28%（§7.1，图 8）。
- 2 GiB STREAM copy 中，BitVisor 和 Xen 的 nested overhead 只有 0.4%–3.6%；KVM 为 10%–12%，而 KVM 的 no-SEV L2 已有 10% overhead，说明主要问题在 KVM nested implementation，不是 SEV 机制本身（§7.2，图 9）。
- 单 iperf3 stream 中，SEV 即使在单层 VM 也使 throughput 降 51%–53%，原因是频繁 VM exit 和 encrypted/un­encrypted bounce-buffer copy。两条并发 stream 能隐藏部分开销：相对单层，BitVisor 最多慢 18%，Xen Domain 0 只慢 1.0%，KVM 改善很小；SEV-SNP 因 exit 较快，常胜过 SEV-ES（§7.3，图 10）。
- Apache 45-byte 小文件测试中，nested overhead 为 31%–58%；100 KiB 大文件转为网络瓶颈后，BitVisor/Xen 接近单层，KVM 仍慢 6.3%–23%。Linux 6.1 build 中，KVM nested SEV 慢 5.8%–22%，BitVisor 慢 2.6%–6.8%，Xen 慢 34%–40%；Xen 的 no-SEV nested 本身也慢 34%–36%（§7.4–§7.5，图 11–12）。
- KVM 与 BitVisor 的 SEV₀ virtualization boot 都约为 no-SEV nested 的 4.1×，分别受 shadow NPT/无 huge page 和 AMD-SP 加密 110 MiB boot image 影响；KVM passthrough 的 SEV₀、SEV-ES boot 只慢 12%、49%，SEV-SNP 还因 1 GiB huge page 比单层快 1.6×。启用 SVSM 对非 boot workload 影响很小，但使单层和 SEV virtualization boot 分别再慢 12%、29%（§7.6–§7.7，图 13–14）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 同一框架支持“L1 不可信”和“L1 可信”两种模型 | virtualization 使用独立 context，passthrough 共享 context；均能启动多个 L2（§3–§5、表 1） | AMD SEV、当前原型与列明的威胁模型 | 强 |
| 设计不依赖某一种 L1 hypervisor | KVM、BitVisor、Xen PV 均实现并运行五类 benchmark（§7） | 只用 KVM 作为 L0，未测其他 host VMM | 强 |
| passthrough 总比 virtualization 快 | VM exit 与 boot 一贯更快，但其他 workload 的胜者随 SEV variant 和 L1 改变（§7.8） | 不能据两个亮点推出全 workload 优势 | 中偏弱 |
| 更强 SEV variant 必然更慢 | SNP 的 VM exit、network 和部分 I/O 常快于 ES，boot virtualization 却更慢（图 8–13） | 结果含实现成熟度与 huge-page 差异 | 弱 |
| Nested SEV 抵御恶意 L0/L1 的所有攻击 | memory/register boundary 有机制分析；VM-exit control manipulation、side channel、DoS 和 L0-L2 collusion 明确排除（§2.3、§6） | 只能在限定威胁模型内声称安全 | 中 |

## 批判性分析

### 论证链条

论文最好的地方是没有把“nested confidential VM”当成单一需求。L2 是否信任 L1 直接决定 key、ASID、RMP、shared memory 和 attestation 设计；emulation-less multiplexing 与 context decoupling 各自服务一个清楚的 trust model。实现跨 KVM、薄 hypervisor 和 paravirtualized Xen，证明抽象不只适配一种 VMM。

不过，安全结论必须带上很窄的限定。L0 是所有 L2 VM exit 的第一接收者，却可以在论文模型外直接不转发给 L1；VMCB、NPT、GHCB 和 virtualization shared buffer 也对 L0 可见或可改。作者认为这些是 SEV 本身的既有边界，但 virtual cloud 用户可能自然理解成“L0 不可信就不能越过 L1”。系统在 data confidentiality/integrity 与 execution/control-flow integrity 之间仍有明显缺口。

### 假设压力测试

最关键的测试是让恶意 L0 随机 drop、重排、伪造或自行处理 L2 VM exit，观察 L2/L1 能否检测；如果只能 silent mis-execution，就需要把该限制放进 attestation 或协议接口，而不只是 threat-model 文字。对 unencrypted GHCB/shared buffer 应注入 replay、cross-VM substitution 和 malformed response，分别在 SEV₀、ES、SNP 下确认真实保护差异。

exclusive GPA 还应在碎片化 L1 address space、多 L2 动态扩缩容、memory ballooning 和 oversubscription 下测试。恶意 L2 与 L0 合谋虽然被排除，但多租户虚拟云中 tenant VM 本来就可能恶意；应验证它能否利用 passthrough 的 shared ASID 和 L0 提供的 shadow NPT 读 L1 或其他 L2。

### 实验可信度

评测覆盖两种机制、三种 SEV variant、三种风格不同的 L1 hypervisor，以及 VM exit、memory、network、Web、kernel build、boot 和 SVSM。作者没有用一个平均数掩盖反常结果：KVM no-SEV baseline 已慢、SNP 有时比 ES 快、Xen PV build 很差、passthrough 并非处处领先，这些负面结果提高了可信度。

但所有结果来自一台 AMD EPYC 9334、固定资源配置和 KVM L0。没有多 L2 并发扩展性、AMD-SP command contention、RMP/ASID 容量、tail latency、memory overhead、live migration、failure recovery 或 attestation latency。不同机制还使用不同 firmware、huge page 和 memory manager；例如作者自己指出 SEV-SNP KVM 使用标准 `guest_memfd`，SEV-ES 使用自定义 manager，因此 variant 对比混入实现成熟度。

### 系统性缺陷

SEV virtualization 的 L1-L2 shared memory 是明文，实际 I/O confidentiality 依赖 L2 再做 disk/network encryption；passthrough 虽能共享密文，却把 L1 纳入 TCB并失去独立 hardware attestation。也就是说，两条路径没有同时给出“高性能共享、L1 不可信、独立证明”三者。

实现需要修改 L0/L1 KVM、QEMU、firmware 和 guest path，passthrough 还要管理高地址 exclusive GPA、1 GiB huge page、Wakeup Mailbox 与 VMSA pool。SEV-ES 的 checksum 算法是逆向得到的三个 CRC-32C，未来 CPU revision 若改变实现，兼容性会很脆弱。设备 passthrough、IOMMU trust、migration、snapshot、oversubscription 和 crash cleanup 都未形成完整生命周期方案。

## 局限与后续工作

- **局限 1**：不防 L0 操纵 VM-exit control flow、side channel、DoS 或 L0-L2 collusion；SEV₀、SEV-ES 也没有 SNP 级 memory integrity。
- **局限 2**：passthrough 没有 L2 hardware attestation，且 shared context 使 L1 能完全访问 L2；virtualization 的 shared buffer 又对 L0/L1 明文。
- **局限 3**：实验没有测试多个 L2 同时运行时的 AMD-SP、ASID、RMP、network 和 memory scalability，也没有 live migration 与故障恢复。
- **局限 4**：exclusive GPA、custom qboot 和 VMSA CRC adjustment 增加部署与跨 CPU revision 维护成本。
- **后续工作 1**：增加可信 VM-exit forwarding 或可验证 transcript，让 L2 能检测 L0 绕过、drop 和 replay L1 handling。
- **后续工作 2**：在 1–数十个 L2、内存碎片、ballooning 和 overcommit 下测 throughput、p99 exit、AMD-SP queue 和 RMP/ASID 使用量。
- **后续工作 3**：设计 migration、snapshot、device assignment 与 remote attestation 协议，并明确两种 trust model 下谁能导出、恢复和撤销 context。
- **后续工作 4**：扩展到 Intel TDX 或其他 TEE，验证 emulation-less multiplexing/context decoupling 是否真是跨架构抽象。

## 相关

- **相关系统**：AMD SEV、Hecate、OpenHCL、Microsoft nested SNP、KVM、BitVisor、Xen
- **相关概念**：confidential VM、nested virtualization、memory encryption、RMP、remote attestation、VMPL
- **同会议**：[[OSDI-2026]]
