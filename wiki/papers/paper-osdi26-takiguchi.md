---
type: paper
name: NestedSEV
full_title: "Nested SEV: Secure and Generic SEV Support for Nested Virtualization"
authors: [Kazuki Takiguchi, Kenichi Kourai]
venue: OSDI
year: 2026
tags: [confidential-computing, nested-virtualization, sev, hypervisor, trusted-execution]
source_pdf: "[[osdi26-takiguchi.pdf]]"
source_md: "[[osdi26-takiguchi]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-01
---

# 嵌套 SEV：为嵌套虚拟化提供安全且通用的机密计算支持（OSDI 2026）

> **原题**：Nested SEV: Secure and Generic SEV Support for Nested Virtualization

> **一句话总结**：现有方案要么无法保护运行 L1 hypervisor 的机密 VM，要么只能运行一个 L2 VM；Nested SEV 用物理 AMD-SP 上的无模拟复用和 SEV context 解耦，分别实现保护 L0、L1 两级 hypervisor 的 SEV virtualization，以及信任 L1 hypervisor 时性能更好的 SEV passthrough，在 KVM、BitVisor 和 Xen 上测得平均性能下降约 0.9%–30%。

## 问题与动机

嵌套虚拟化让 L1 hypervisor 在由 L0 hypervisor 管理的 L1 VM 中运行，并在其上创建多个 L2 VM。它适合构建 virtual cloud：云服务提供商只需租用机密 VM，就能在公共云之上运行自己的 hypervisor 和租户 VM。但现有 AMD SEV 支持没有同时覆盖这两个层次。

Microsoft 的 nested SNP 补丁只保护 L2 VM，L0 仍能直接读写 L1 VM，因此 L1 hypervisor 必须信任 L0。Hecate 和 OpenHCL 保护 L1 VM，但依赖 SEV-SNP 的 VMPL，缺少 MMU virtualization，只能支持一个 L2 VM，也不能防止 L1 hypervisor 读取 L2 的内部状态（§2.2）。

论文将问题拆成两个信任模型：L0 始终不可信；L1 可以不可信，也可以被同一组织信任。两种模型需要不同的密钥、ASID、RMP 和寄存器状态管理方式，不能只把单层 SEV 递归地套一遍。

## 关键观察 / 隐含假设

- **观察 1：SEV 的敏感状态不能交给不可信 L0 模拟。** L2 的加密 key、ASID、guest context page 和 RMP ownership 必须仍由物理 AMD-SP/处理器维护；否则 L0 可伪造虚拟 SEV context，破坏机密性或完整性（§3、§4.5–§4.6）。
  - **依赖假设**：AMD-SP、处理器和硬件 RMP 可信，且硬件允许 L0 在真实 ASID/HPA 与 L1 提供的虚拟映射之间做翻译。
  - **可能失效场景**：硬件接口无法表达多个嵌套层次，或 L0 可绕过 L1 的 VM-exit 控制流时，论文方案的安全论证不成立；后者被明确排除在威胁模型之外（§2.3）。
- **观察 2：不同 SEV context 会阻止 L1 hypervisor 直接访问 L2 的共享内存。** SEV virtualization 因而要求 L2 与 L1 共享的页面清除 C-bit；这使共享数据暴露给 L0，也带来 I/O bounce buffer 成本（§4.1、§6）。
  - **依赖假设**：共享区只承载可由 L2 端到端加密的数据，L1 不需要直接读取 L2 的加密页。
  - **可能失效场景**：高频网络 I/O、无法端到端加密的数据或依赖共享内存的设备模型，可能被未加密共享区和多次拷贝主导。
- **观察 3：SEV passthrough 共享 context 后，SNP 的 RMP 检查要求 GPA 唯一且跨层一致。** 论文使用 exclusive GPA assignment，使每个 L2 页的 L1 GPA 与 L2 GPA 相同，并让不同 L2 VM 的 GPA 不重叠（§5.3）。
  - **依赖假设**：L1 hypervisor 能预留连续的 1-GB huge-page 区域，并能使用定制 firmware 从 4 GB 以上的任意 GPA 启动 L2。
  - **可能失效场景**：内存碎片、动态 ballooning、热迁移或需要传统低地址启动协议的 guest，会增加实现成本或无法直接使用现有 firmware。

## 核心方法

Nested SEV virtualization 为 L1 VM 和每个 L2 VM 分配不同的 SEV context。L0 不模拟 AMD-SP，而是把 L1 发出的命令转发到物理 AMD-SP，并翻译虚拟 ASID 和 GPA。RMP virtualization 也采用同样思路：L1 维护可被读取的虚拟 RMP，L0 把 `VIRT_RMPUPDATE` 请求转换为真实 RMP 更新。敏感状态始终停留在硬件中，这对应观察 1（§4.5–§4.6）。

Nested page table（NPT）不能用传统同步 shadow 方法更新，因为 L0 无法读取加密的 NPT。论文采用异步同步：先临时解除写保护，让 L1 修改 NPT，待 L1 刷新 TLB 时再更新 shadow NPT 并恢复写保护（§4.3）。VMCB 和 NPT 本身保持未加密；作者认为它们本来就由不可信 hypervisor 控制，因此不扩大 SEV 的攻击类别。

寄存器状态通过 direct context switching 处理。L0 在 L1 与 L2 间切换时直接执行 `VMRUN`，让处理器保存和恢复加密 VMSA，避免访问加密的 L1 host save area（§4.7）。对 MMIO，SEV-ES/SNP 借助 #VC 和 GHCB 传递指令字节；SEV0 则虚拟化 Decode Assists。

SEV passthrough 面向信任 L1 的模型。L1 和多个 L2 共享同一个 SEV context，L0 不为 L2 调用 AMD-SP，也不分配新 ASID。共享加密内存可以避免 bounce buffer，L1 还能直接读取 L2 的 VMSA 和指令。SNP 下通过 exclusive GPA assignment 保持 RMP 检查成立（§5.1–§5.3）。该机制也支持不使用 SVM 的 Xen paravirtualized L2。

SEV-ES 的 VMSA checksum 由硬件保存在 TMR 中，L1 不能简单复用一个 VMSA。论文预先建立 VMSA pool，并在切换 vCPU 后用 backward CRC 调整三个 CRC-32C 值，使修改后的 VMSA 保持原 checksum（§5.5）。

## 设计取舍

- **安全性与性能**：SEV virtualization 隔离 L1/L2 context，可防止不可信 L1 读取 L2，但共享内存需未加密；SEV passthrough 性能较好，却明确依赖可信 L1，且不支持 L2 的硬件远程 attestation。
- **通用性与内存布局**：exclusive GPA assignment 让 SNP 的 RMP 检查可用，也支持多个 L2，但需要连续大页、专用 qboot firmware 和 ACPI Wakeup Mailbox，限制了现有 guest firmware 与动态内存管理。
- **硬件复用与控制流暴露**：无模拟 AMD-SP 保持密钥安全，但 L0 仍观察并控制 L1/L2 的 VM exits。控制流篡改和 side channel 被排除在威胁模型外，不能把结果理解成完全隐藏 L2。

## 实验与结果

- 实现基于 Linux/KVM 6.11、QEMU 9.1，并在 L1 使用 KVM、BitVisor 或 Xen 4.16；硬件为第四代 AMD EPYC 9334、128 GB DDR5 和 10 GbE（§7）。三种 SEV variant 均进行了测试。
- VM exit 开销在 SEV virtualization 中约为无 SEV 嵌套虚拟化的 2 倍；SEV passthrough 比 SEV virtualization 快 0.5%–28%（图 8、§7.1）。
- STREAM 2-GB 内存复制中，BitVisor/Xen 的嵌套开销为 0.4%–3.6%；KVM 即使在无 SEV 时也有 10%–12% 开销，主要来自 KVM 实现（图 9、§7.2）。
- iperf3 中单层 SEV 的吞吐下降 51%–53%。双流并发时，BitVisor 的 passthrough 与单层相比最多下降 18%，Xen Domain 0 下降 1.0%；KVM 仍受 VM-exit 开销影响（图 10、§7.3）。
- 小型 45-byte 页面、200 并发连接的 Web 服务中，嵌套开销为 31%–58%；KVM 下 SEV passthrough 比 SEV virtualization 最多快 15%。约 100 KB 页面时网络带宽成为瓶颈，KVM 仍有 6.3%–23% 下降（图 11、§7.4）。
- 启动是 SEV virtualization 的主要弱点：KVM 中 SEV0 virtualization 比无 SEV 嵌套慢 4.1 倍；SNP 还要验证约 2 GB 预分配内存。SEV passthrough 则只增加 12%（SEV0）和 49%（SEV-ES），SNP 在该配置下反而比单层快 1.6%，受益于 1-GB huge pages（图 13、§7.6）。
- 论文汇总跨机制、variant 和 L1 hypervisor 的平均性能下降为 0.9%–30%，但不同工作负载的范围差异很大，不能用单一平均值代表部署成本（§9）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Nested SEV 能在 L1 VM 已启用 SEV 时运行多个 SEV-enabled L2 VM | KVM、BitVisor、Xen 实现与对比表（表 1、§4–§5） | 单台 EPYC 9334；Xen 为 paravirtualized L2 | 强 |
| 无模拟 AMD-SP 能避免把 L2 的敏感 context 暴露给 L0 | context 转发、真实 RMP/AMD-SP 管理与安全分析（§4.5–§4.6） | 依赖可信 AMD-SP/处理器；控制流篡改不在范围 | 中 |
| SEV passthrough 通常比 SEV virtualization 更快 | VM exit 快 0.5%–28%，启动只增加 12%–49%（图 8、图 13） | 信任 L1；大页与定制 firmware 配置 | 强 |
| 性能代价取决于 L1 hypervisor 和 workload，而非只由 SEV variant 决定 | STREAM、iperf3、Web、kernel build（图 9–图 12） | 三类 hypervisor、单机实验，未覆盖大规模云 trace | 强 |

## 批判性分析

### 论证链条

论文从“L0 不能可信地模拟 AMD-SP”推出硬件 context 复用，再从“L1/L2 是否互信”分出两套机制，设计逻辑是闭合的。实验也覆盖了三类 L1 hypervisor 和三种 SEV variant。主要跳步在于安全结论依赖既有 SEV 假设：L0 不绕过 L1 的 VM-exit 处理，也不利用 side channel。论文明确承认这些攻击未覆盖，因此 Nested SEV 的保证是“在 SEV 威胁模型扩展下成立”，不是对恶意 L0 的完整隔离。

### 假设压力测试

SEV virtualization 把 L2/L1 共享区置为未加密，网络实验已经显示 SEV 的 bounce buffer 会带来 51%–53% 的单层吞吐损失。若设备模型更依赖共享内存，或者数据不能端到端加密，安全和性能都会恶化。SEV passthrough 消除了这部分问题，却把 L1 设为可信根；多租户 virtual public cloud 不能直接采用它。

exclusive GPA assignment 是 SNP 正确性的核心，但它与云平台常见的内存 overcommit、热插拔、碎片化和迁移机制存在张力。论文使用连续 1-GB huge pages 的实验配置证明机制可行，没有证明这些资源管理功能能够低成本接入。

### 实验可信度

基线包含无 SEV 嵌套虚拟化和单层 KVM，且有消融式的 SEV variant、L1 hypervisor 和 workload 对比。网络、Web、内存、编译和启动覆盖了不同瓶颈。局限是实验规模为单机、单个 AMD EPYC 型号，缺少生产 trace、迁移/恢复、内存超售、多个并发 L2 tenant 和远程 attestation 流程的评估。不同实现还使用了不同的设备路径，KVM、BitVisor 与 Xen 的绝对数值不应直接横向排名。

### 系统性缺陷

实现需要同时修改 L0/L1 hypervisor、guest OS、firmware 和 SEV 管理路径。SEV-ES 的 VMSA checksum 依赖对未公开 CRC 行为的逆向分析，跨 AMD 代际的兼容性风险较高。论文未评估故障恢复、实时迁移、可观测性和运维升级。L0 仍可观察 VM exits 和访问模式；即使 passthrough 隐藏了部分 L1-L2 交互，完全虚拟化 L2 的流量分析仍存在。

## 局限与后续工作

- **局限 1**：SEV virtualization 的共享内存必须未加密，网络和小 I/O workload 的成本明显；需要评估加密共享缓冲区或硬件 mediated I/O。
- **局限 2**：SEV passthrough 不提供 L2 的硬件 attestation，且 exclusive GPA assignment 依赖连续大页和定制启动链。
- **局限 3**：控制流篡改、side channel、DoS 和 L0-L2 collusion 未纳入威胁模型，安全结论不能覆盖这些场景。
- **后续工作 1**：在多节点迁移、内存 overcommit、动态 vCPU/内存调整和多个并发 L2 VM 下，测量 RMP/GPA 管理的额外成本与失败恢复行为。
- **后续工作 2**：将无模拟复用与 context 解耦映射到 Intel TDX，比较硬件 TDX module 对 L2 VM-exit 隐藏能力的影响（§9）。

## 相关

- **相关概念**：[[Nested Virtualization]]、[[Confidential Computing]]、[[Remote Attestation]]、[[Trusted Execution Environment]]
- **同类系统**：[[Hecate]]、[[OpenHCL]]、[[KVM]]、[[BitVisor]]、[[Xen]]
- **同会议**：[[OSDI-2026]]
