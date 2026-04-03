---
status: hold
date: 2026-04-03
keywords:
  - RISC-V
  - Formal Verification
  - Hypervisor
  - Rust
  - Verus
---

# 方向深度调研：RISC-V 全栈形式化验证

> [!caution] Hold
> 需要 RISC-V 架构 + 形式化验证两方面的前置知识积累。建议先学习 RISC-V 特权级架构（尤其 H-extension）、Verus/Rust 验证基础、sail 规范语言，再评估是否启动。

---

## 一、方向概述

**核心命题**：利用 RISC-V 开源 ISA + 开源处理器的独特优势，构建从硬件 RTL 到固件到 OS 内核的全栈可验证系统。这是 ARM/x86 闭源生态根本无法实现的。

**为什么是现在**：2025 年顶会出现了形式化验证的"实用化拐点"——[[3731569.3764821|Atmosphere]] 用 Rust+Verus 在 2.5 人年内构建了 proof ratio 仅 3.32:1 的验证微内核（前代 seL4 约 20:1），[[atc2025-tang|CONVEROS]] 用 4 人月在真实 OS 上找到 20 个并发 bug，[[3731569.3764822|AutoMan]] 自动生成 70-97% 验证代码。与此同时，[VeriSMo](https://github.com/microsoft/verismo)（OSDI'24 Best Paper）证明了 Verus 可用于 bare-metal 固件验证。RISC-V 生态方面，[香山](https://github.com/OpenXiangShan/XiangShan)第三代昆明湖已支持 H-extension（RV64GCBSUHV），[ASTERINAS](https://github.com/asterinas/asterinas) v0.17.0 已实现 RISC-V SMP 支持。两条曲线正在交汇。

---

## 二、现有工作全景

### 2.1 RISC-V 侧已有工作

| 层次 | 项目 | 状态 | 验证深度 |
|------|------|------|----------|
| ISA 形式规范 | [sail-riscv](https://github.com/riscv/sail-riscv) | RV64GC + Privileged 已完成，RISC-V 基金会官方规范语言 | 可生成 Isabelle/Coq/Lean 定义 |
| ISA 形式规范 | [sail-riscv H-ext](https://github.com/riscv/sail-riscv/pull/612) | PR #612 仍 open（截至 2025-03），[KU Leuven 有独立实现](https://lirias.kuleuven.be/retrieve/762909) | KU Leuven 版可启动 Xvisor+Linux（约 13h 仿真） |
| 硬件 RTL 验证 | [riscv-formal](https://github.com/SymbioticEDA/riscv-formal) (SymbiYosys) | 成熟，支持 RVFI 接口 | 有界模型检查，非完整证明 |
| 硬件 RTL 验证 | [VeriCHERI](https://arxiv.org/abs/2407.18679) (ICCAD'24) | TU Kaiserslautern，exhaustive security verification | 仅需 4 条无界属性证明机密性/完整性，含 Meltdown 级侧信道 |
| 硬件 RTL 验证 | [CHERI-Flute](https://www.cl.cam.ac.uk/research/security/ctsrd/cheri/cheri-risc-v.html) (JasperGold) | 已完成 | 完整属性验证，仅限简单顺序核 |
| 香山验证 | [DRAV](https://github.com/OpenXiangShan/XiangShan) (DiffTest+XFUZZ+LightSSS) | 生产级，20000+ 测试用例 | **仅仿真验证，无数学证明** |
| CHERI-RISC-V | [CHERIoT-Ibex](https://github.com/microsoft/cheriot-ibex) | 有 observational correctness 验证 | 已验证安全属性，仅限 32 位顺序核 |
| 处理器验证框架 | [Kami](https://github.com/mit-plv/kami) (MIT/IU) | Coq 框架，已验证 Riscy 处理器 | 可生成可综合 Verilog，完整证明 |
| 验证编译 | [CompCert RISC-V](https://compcert.org/) | RISC-V 后端已可用（~2020） | 验证 C → RISC-V 机器码翻译 |
| 验证编译 | [CakeML RISC-V](https://cakeml.org/) | RISC-V 后端已可用 | 验证 ML → RISC-V 机器码翻译 |

### 2.2 OS/系统软件侧已有工作

| 项目 | 会议 | 技术栈 | RISC-V 支持 | 验证范围 |
|------|------|--------|-------------|----------|
| [seL4](https://github.com/seL4/seL4) | 历史 | C + Isabelle/HOL | ✅ RV64：功能正确性 + 完整性/机密性 + **二进制等价**（首个 64-bit 架构） | ~100 万行 Isabelle 证明，~20 人年 |
| [[3731569.3764821\|Atmosphere]] | SOSP'25 Best Paper | Rust + [Verus](https://github.com/verus-lang/verus) | ❌ 仅 x86-64 | 功能正确性 + 内存安全 + 非干扰隔离，proof ratio 3.32:1，2.5 人年 |
| [VeriSMo](https://github.com/microsoft/verismo) | OSDI'24 Best Paper | Rust + Verus | ❌ AMD SEV-SNP | 机密 VM 固件验证，no_std bare-metal Verus 的首个验证 |
| [[atc2025-peng-yuke\|ASTERINAS]] | ATC'25 | Rust + Verus(部分) | ✅ SMP/FPU/VirtIO (v0.17.0) | framekernel，[vostd](https://github.com/asterinas/vostd) 已验证页表模块（~6K spec + ~2K proof / ~2K code） |
| [[atc2025-tang\|CONVEROS]] | ATC'25 | Rust + model checking | ✅ (基于 ASTERINAS) | 并发正确性，12 模块 20 bug |
| [[3731569.3764817\|Ghost/pKVM]] | SOSP'25 | C | ARM | 可执行规范，11K LoC 目标 |
| [[3731569.3764826\|Miralis]] | SOSP'25 | Rust + **Kani** 模型检查 | ✅ RISC-V M-mode | 6.2K LoC VFM，Kani 验证 43% 代码（2.7K LoC），发现 21 bug，**非完整形式化验证** |
| [[3731569.3764856\|TickTock]]/[[3731569.3764828\|Tock]] | SOSP'25 | Rust + [Flux](https://github.com/flux-rs/flux) 精化类型 | ✅ | MPU 隔离验证，发现 6 bug |
| [[3731569.3764826\|Miralis]] HotOS | HotOS'25 | 同上 | ✅ | "Lightweight Hypervisor Verification" 配套方法论论文 |
| [[atc2025-jia\|Rex]] | ATC'25 | Rust | Linux 内核扩展 | 语言级安全替代 eBPF 验证器 |
| [[3731569.3764844\|CHERIoT RTOS]] | SOSP'25 | C/C++ | CHERI-RISC-V | 内存安全 + compartmentalization |

### 2.3 RISC-V Hypervisor 现有实现

| 项目 | 语言 | 类型 | 状态 | 形式化验证 |
|------|------|------|------|-----------|
| [KVM RISC-V](https://www.kernel.org/) | C | Type-2 | 主线 Linux 5.16+（2021） | 无 |
| [Xvisor](https://github.com/xvisor/xvisor) | C | Type-1 单体 | 成熟，首批支持 H-ext | 无 |
| [Bao](https://github.com/bao-project/bao-hypervisor) | C | Type-1 静态分区 | ~8K SLoC，面向混合关键性 | 无 |
| [Salus](https://github.com/rivosinc/salus) | **Rust** | HS-mode 微 hypervisor | Rivos Inc.，RISC-V CoVE 参考实现 | 无 |
| [RVirt](https://github.com/mit-pdos/RVirt) | **Rust** | S-mode trap-and-emulate | MIT PDOS，研究原型 | 无 |
| [Diosix](https://diosix.org/) | **Rust** | Type-1 bare-metal | 进行中，多核支持 | 无 |

**关键观察**：已有 3 个 Rust RISC-V hypervisor（Salus/RVirt/Diosix），但**无一经过形式化验证**。

### 2.4 关键空白（Gap Analysis）

```
硬件 RTL ←——————→ ISA 规范 ←——————→ 固件/Hypervisor ←——————→ OS 内核
   ↑                  ↑                    ↑                    ↑
   │                  │                    │                    │
香山: 仅仿真      sail-riscv:          Miralis: Kani 轻量      seL4: 已全验证
无数学证明        缺 H-ext             验证 43%，非完整        但 C+Isabelle 重
                                       无验证 hypervisor       Atmosphere: 已全验证
                                                              但仅 x86-64
```

**三个核心空白**：

1. **无验证 RISC-V hypervisor**：存在多个实现（含 Rust），但无一验证。Ghost/pKVM 仅覆盖 ARM。
2. **Miralis 验证不完整**：Kani 模型检查覆盖 43%，缺乏隔离属性的完整数学证明。
3. **Atmosphere 缺 RISC-V**：最先进的 Rust+Verus 验证微内核仅支持 x86-64，移植是开放问题。

**最大的机会在 Hypervisor 层**：有开放规范（sail H-ext）、有 Rust 实现可参考（Salus）、有验证工具（Verus + VeriSMo 先例）、有硬件支持（QEMU + 香山）——但无人做过验证。

---

## 三、子方向分析

### 子方向 A：验证香山关键微架构模块（不推荐）

OoO 核的形式化验证是公认开放问题。香山 6 发射乱序执行的复杂度远超已验证的顺序核（CHERI-Flute/CHERIoT-Ibex），完整验证不现实。即使选择子模块（TLB、cache coherence），工作量也难以预估，且需要深入 Chisel/FIRRTL 工具链的形式化方法——与 Rust+Verus 技术栈正交。

**结论**：学术价值高但风险不可控，不纳入推荐路线。

### 子方向 B：验证 RISC-V 固件 + 微内核

**做什么**：
- 用 Verus 对 Miralis 进行完整形式化验证（当前仅有 Kani 轻量级验证）
- 将 Atmosphere 移植到 RISC-V（或基于其架构构建新的验证微内核）

**Novelty 评估**：⭐⭐⭐⭐ 高

Miralis 方面：
- Miralis 团队自己用 Kani（有界模型检查），验证深度有限——用 Verus 做无界证明是本质提升
- Miralis 6.2K LoC 规模适中，VeriSMo（类似规模的 bare-metal 固件）已证明 Verus 可胜任
- 可直接复用 Miralis 已有的 Sail 参考模型翻译（2K 行 OCaml 后端）

Atmosphere-RV 方面：
- Atmosphere 源码已开源（MIT，[github.com/mars-research/atmosphere](https://github.com/mars-research/atmosphere)），移植有基础
- 需处理 RISC-V 特定挑战：SBI 接口建模、Sv39/Sv48 页表验证、RISC-V 特权级模型
- ASTERINAS/vostd 已积累 RISC-V + Verus 经验（页表验证），可借鉴

### 子方向 C：首个验证 RISC-V Hypervisor

**做什么**：基于 sail-riscv H-extension 规范，构建并验证一个轻量级 RISC-V hypervisor。

**Novelty 评估**：⭐⭐⭐⭐⭐ 非常高

- **不存在任何验证过的 RISC-V hypervisor**——全球空白
- 已有 Rust 实现可参考：[Salus](https://github.com/rivosinc/salus)（Rivos 的 HS-mode 微 hypervisor）架构最接近验证目标
- VeriSMo 证明了 Verus 可验证类 hypervisor 的隔离属性（机密 VM 固件 ≈ 轻量 hypervisor）
- Ghost/pKVM（SOSP'25）提供了 hypervisor 可执行规范方法论，可迁移到 RISC-V + Rust

**风险**：依赖 sail-riscv H-ext 规范进度（可先用 KU Leuven 独立实现）；硬件可用性已解决（QEMU 支持 + 香山昆明湖已有 H-ext）

---

## 四、推荐路线：分阶段递进

### 策略调整：从"全栈并行"到"逐层递进"

原方案试图在 18-24 个月内 3-4 人并行推进三层验证，这不现实。参考数据：

| 项目 | 规模 | 投入 | 日历时间 |
|------|------|------|----------|
| Atmosphere（单层微内核） | 6K 代码 + 20K 证明 | 2.5 人年 | 1.5 年 |
| seL4 原始验证 | ~10K 代码 | ~20 人年 | 多年 |
| seL4 今日估算（Gernot Heiser） | 同上 | ~10 人年 | — |
| VeriSMo（bare-metal 固件） | ~5K 代码 | 未公开（Microsoft Research 团队） | — |
| vostd（ASTERINAS 页表模块） | ~2K 代码 | 进行中，11/14 目标完成 | — |

**修正后的策略**：聚焦单层做到最好，而非三层做到一半。

### 推荐路线：子方向 C 为主（验证 RISC-V Hypervisor）

**为什么选 C 而非 B**：

1. **Novelty 最大**：全球首个验证 RISC-V hypervisor，比 Miralis 重新验证或 Atmosphere 移植更有辨识度
2. **scope 可控**：轻量 hypervisor（参考 Salus/Bao 的 ~8K SLoC 规模）比全功能微内核更适合验证
3. **工具链成熟**：VeriSMo 已铺平 Verus bare-metal 路径，可直接复用 no_std + tracked permission 模式
4. **参考实现丰富**：Salus（Rust HS-mode）提供实现骨架，Ghost/pKVM 提供规范方法论
5. **硬件就绪**：QEMU H-ext + 香山昆明湖 (RV64GCBSUHV)，不再是瓶颈

### 系统架构

```
┌─────────────────────────────────────────────────────┐
│ M-mode:  Miralis（已有，Kani 验证 43%）              │  不在 scope 内，
│          可作为未验证信任基础                          │  后续独立工作
├─────────────────────────────────────────────────────┤
│ HS-mode: VerHV — 验证 RISC-V Hypervisor（核心目标） │  ← 本项目聚焦
│          Rust + Verus，基于 sail H-ext 规范          │
├─────────────────────────────────────────────────────┤
│ VS-mode: Guest OS（Linux / 轻量 RTOS）              │  不在验证范围
├─────────────────────────────────────────────────────┤
│ VU-mode: 用户态应用                                  │
└─────────────────────────────────────────────────────┘
     运行在 QEMU virt + 香山昆明湖 FPGA 上
```

### 验证目标（严格限定）

只验证**隔离属性**，不追求完整功能正确性：

| 属性 | 定义 | 对标 |
|------|------|------|
| Guest 内存隔离 | 不同 Guest 的 GPA 映射到不相交的 HPA | Ghost/pKVM 核心属性 |
| Hypervisor 自保护 | Guest 无法访问 Hypervisor 私有内存 | VeriCHERI 机密性属性 |
| 中断隔离 | Guest 只能接收分配给它的中断 | Miralis 中断虚拟化属性 |
| 二阶段页表正确性 | VS-stage + G-stage 地址翻译符合 sail H-ext 规范 | ASTERINAS/vostd 页表验证的扩展 |

**不验证**：设备模拟、调度公平性、性能、Guest 完整功能。

---

## 五、实施方案与时间线

### 5.1 团队配置

**最小可行团队**：3 人

| 角色 | 人数 | 技能要求 | 备注 |
|------|------|----------|------|
| 验证系统研究员 | 1-2 | Rust + Verus，OS/hypervisor 经验 | 核心，负责实现 + 证明 |
| RISC-V 系统工程师 | 1 | RISC-V 特权级模型，QEMU，sail 规范 | 负责 H-ext 建模 + 测试环境 |
| 形式化方法顾问 | 0.5 | SMT solver 调优，proof engineering | 可为兼职/合作方 |

### 5.2 分阶段计划

#### Phase 0：工具链验证与 Go/No-Go 决策（M1-M4）

**目标**：验证 Verus 在 RISC-V bare-metal 上可用，否则整个方案需要调整。

| 任务 | 产出 | 风险点 |
|------|------|--------|
| 搭建 QEMU RISC-V H-ext 开发环境 | 可运行 Salus 的测试环境 | 低 |
| Verus no_std + RISC-V 交叉编译 | 可编译验证的 RISC-V bare-metal 二进制 | **高**：Verus 使用定制 Rust 编译器，交叉编译可能有问题 |
| 用 Verus 验证一个 RISC-V 页表操作（PoC） | 验证 Sv39 PTE 位域操作的正确性 | 中：参考 VeriSMo PTE 和 vostd ConcreteCursor |
| 阅读 Salus 源码，评估可验证性 | 架构分析报告 | 低 |
| 将 sail H-ext 规范翻译为 Verus 可用形式 | RISC-V H-ext Verus spec（部分） | 中：参考 Miralis 的 Sail→Rust 翻译后端 |

**Go/No-Go Gate**（M4 末）：
- ✅ Go：Verus 可交叉编译到 RISC-V，PoC 页表验证成功
- ❌ No-Go 备选方案 1：改用 Kani（牺牲证明强度，换取工具成熟度）
- ❌ No-Go 备选方案 2：退回 Coq/Lean + CompCert（工作量增大 3-5×，但工具链可靠）

#### Phase 1：最小验证 Hypervisor 原型（M5-M14）

**目标**：构建并验证一个最小 RISC-V hypervisor，支持 2 个静态分区 Guest。

| 子阶段 | 时间 | 任务 | 产出 |
|--------|------|------|------|
| 1a 实现 | M5-M8 | 基于 Salus 架构，实现最小 HS-mode hypervisor：二阶段页表、trap 转发、基本 MMIO | 可在 QEMU 上启动 2 个 Guest 的原型 |
| 1b 规范 | M6-M9 | 定义隔离属性的 Verus 抽象规范；建立 H-ext CSR/指令的 trusted spec wrapper | 形式化规范文档 |
| 1c 验证 | M9-M14 | 验证内存隔离 + hypervisor 自保护属性；二阶段页表正确性证明 | 已验证核心模块 |
| 1d 评估 | M13-M14 | 在 QEMU + 香山 FPGA 上运行，收集性能数据和 proof ratio | 可发表的实验数据 |

**Phase 1 产出**：⭐ 第一篇论文——首个形式化验证的 RISC-V Hypervisor（目标：OSDI / SOSP / USENIX Security）

#### Phase 2：扩展验证范围 + 全栈探索（M15-M24）

根据 Phase 1 经验，选择以下方向之一深入：

**选项 2A：扩展 Hypervisor 验证**
- 增加中断隔离验证
- 支持动态 Guest 创建/销毁
- 对接 Miralis（M-mode 信任基础）

**选项 2B：Miralis 完整验证**
- 将 Miralis 从 Kani 轻量验证升级为 Verus 完整验证
- 验证 M-mode 隔离属性（faithful emulation + faithful execution 的无界证明）
- 与 Phase 1 的 hypervisor 组合：首个 M-mode → HS-mode 验证信任链

**选项 2C：Atmosphere-RV 移植**
- 将 Atmosphere 移植到 RISC-V
- 量化架构移植对验证工作量的影响
- 与 hypervisor 组合：HS-mode → VS-mode 验证链

**Phase 2 产出**：⭐ 第二篇论文——根据选择方向不同

### 5.3 时间线总览

```
M1  M2  M3  M4  M5  M6  M7  M8  M9  M10 M11 M12 M13 M14 M15 ... M24
|---Phase 0----|
    Go/No-Go ──┤
                |------Phase 1: 验证 RISC-V Hypervisor------|
                                                     论文 1 ─┤
                                                              |--Phase 2--|
                                                                  论文 2 ─┤
```

**总投入估算**：
- Phase 0: 1-1.5 人年（3 人 × 4 月）
- Phase 1: 3-4 人年（3 人 × 10 月，含密集验证期）
- Phase 2: 2-3 人年（3 人 × 10 月）
- **总计：6-8.5 人年 / 24 个月日历时间**

---

## 六、技术可行性

### 6.1 已确认的依赖项

| 依赖项 | 状态 | 风险 |
|--------|------|------|
| [Verus](https://github.com/verus-lang/verus) 工具链 | 成熟：Atmosphere、VeriSMo、vostd 均已验证可用 | 低 |
| Verus no_std bare-metal | VeriSMo 已在 AMD SEV-SNP 上实现 | 低（x86 已验证），**中（RISC-V 交叉编译未验证）** |
| [sail-riscv](https://github.com/riscv/sail-riscv) RV64GC | 已完成，RISC-V 基金会官方规范 | 无 |
| [sail-riscv H-ext](https://github.com/riscv/sail-riscv/pull/612) | PR #612 仍 open；[KU Leuven 独立实现](https://lirias.kuleuven.be/retrieve/762909)可用 | 中（可先用独立实现） |
| RISC-V QEMU H-ext | 已支持 | 无 |
| [Atmosphere](https://github.com/mars-research/atmosphere) 源码 | **已开源，MIT 许可证**，活跃维护（截至 2026-02） | 低 |
| [[3731569.3764826\|Miralis]] 源码 | **已开源，MIT 许可证**，6.2K LoC Rust | 低 |
| [Salus](https://github.com/rivosinc/salus) 源码 | 开源，Rust HS-mode hypervisor | 低 |
| [香山](https://github.com/OpenXiangShan/XiangShan)昆明湖 H-ext | **已确认支持**（RV64GCBSUHV） | 无 |
| [ASTERINAS](https://github.com/asterinas/asterinas) RISC-V | v0.17.0 已有 SMP/FPU/VirtIO | 低 |
| [vostd](https://github.com/asterinas/vostd) Verus 经验 | 页表验证进行中，~6K spec + ~2K proof | 低（可复用经验） |

### 6.2 Verus 用于 RISC-V bare-metal 的技术路径

基于 VeriSMo 和 ASTERINAS 的先例，Verus 用于 RISC-V bare-metal 的模式已基本明确：

| 挑战 | 解决方案 | 先例 |
|------|----------|------|
| no_std 支持 | `vstd = { features = ["alloc"], default-features = false }` | VeriSMo |
| 内联汇编（CSR 操作、sfence.vma 等） | `#[verifier::external_body]` + trusted spec | VeriSMo（AMD 指令），Miralis（Sail→Rust 翻译） |
| unsafe 内存操作 | Tracked permission（`PointsTo<T>`）线性类型 | Atmosphere flat permission storage，VeriSMo `SnpPointsToRaw` |
| 页表位域验证 | `assert ... by(bit_vector)` 证明块 | VeriSMo PTE，vostd ConcreteCursor |
| 自定义分配器 | `#[verifier::external]` GlobalAlloc + 独立验证分配逻辑 | VeriSMo `VeriSMoAllocator` |
| H-ext CSR/指令建模 | 将 sail H-ext 规范翻译为 Verus trusted spec | Miralis 2K 行 Sail→Rust OCaml 后端 |

**关键未验证环节**：Verus 定制 Rust 编译器 → RISC-V 目标的交叉编译。这是 Phase 0 的核心验证内容。

---

## 七、风险与缓解（合并）

| 风险 | 严重度 | 概率 | 缓解策略 |
|------|--------|------|----------|
| Verus RISC-V 交叉编译不可用 | **致命** | 中 | Phase 0 前 4 个月验证，Go/No-Go gate；备选 Kani（有界）或 Coq+CompCert（重量级） |
| sail H-ext PR 长期不合并 | 中 | 中 | 直接使用 KU Leuven 独立实现（已验证可启动 Xvisor） |
| Hypervisor 验证工作量超预期 | 高 | **高** | 严格限制验证范围：仅 4 个隔离属性，不追求完整功能正确性 |
| Atmosphere 团队自行移植 RISC-V | 中 | 低 | 我们聚焦 hypervisor 层（他们不太可能做），两者互补而非竞争 |
| Verus 对 RISC-V 特权级模型的表达力不足 | 中 | 低 | VeriSMo 已验证类似的特权级隔离（AMD VMPL），可类比 |
| proof ratio 超预期（> 10:1） | 中 | 中 | 采用 Atmosphere 的 flat permission storage 方法论降低 ratio |

---

## 八、竞争格局与定位

### 最可能的竞争者

| 竞争者 | 方向 | 我们的差异化 |
|--------|------|-------------|
| [[3731569.3764821\|Atmosphere]] 团队 (Utah) | 可能自行移植 RISC-V | 他们聚焦微内核，不太可能做 hypervisor；协作优于竞争 |
| [[3731569.3764826\|Miralis]] 团队 (EPFL/ETH) | 可能升级到 Verus 验证 | 他们用 Kani 且聚焦 M-mode VFM；我们做 HS-mode hypervisor，正交 |
| [ASTERINAS](https://github.com/asterinas/asterinas)/[vostd](https://github.com/asterinas/vostd) 团队 | 验证 framekernel TCB | 他们目标是 Linux 兼容宏内核（远难于 hypervisor），且尚无 hypervisor 计划 |
| [seL4](https://github.com/seL4/seL4) 团队 (UNSW) | 已有 RISC-V 验证 | C+Isabelle 方法论沉重（100 万行证明 / 20 人年），且无 RISC-V VMM |
| [Cambridge CHERI](https://www.cl.cam.ac.uk/research/security/ctsrd/cheri/) | CHERI-RISC-V 硬件验证 | 聚焦 RTL 级，不做系统软件验证 |
| SeKVM 团队 (Columbia) | 验证 KVM hypervisor | 仅 ARM + Coq，未涉及 RISC-V |
| [Serval](https://unsat.cs.washington.edu/projects/serval/) (UW) | RISC-V 安全监控器验证 | 符号执行方法，仅简单监控器（非 hypervisor），已停更 |

### 独特定位

> **首个形式化验证的 RISC-V Hypervisor：基于 sail H-extension 规范，使用 Rust+Verus 证明 Guest 内存隔离、Hypervisor 自保护、中断隔离和二阶段页表正确性。**

关键差异化：
- **"RISC-V Hypervisor"**——全球空白，ARM/x86 生态做不到（闭源 ISA）
- **"sail 规范驱动"**——不是 ad-hoc 验证，而是基于官方 ISA 形式规范
- **"Rust+Verus"**——相比 seL4 的 C+Isabelle（20:1 ratio / 20 人年），目标 proof ratio < 8:1
- **"隔离属性"**——聚焦安全关键属性，不追求完整功能正确性，scope 可控

---

## 九、预期学术贡献

### 第一篇论文（Phase 1，M14）

**首个形式化验证的 RISC-V Hypervisor**

- 目标会议：OSDI / SOSP / USENIX Security
- 贡献：
  1. 基于 sail H-ext 规范的 hypervisor 隔离属性形式化定义
  2. Rust+Verus 验证实现，量化 proof ratio 和工作量
  3. 与 Ghost/pKVM（ARM, C）和 VeriSMo（AMD, Rust）的系统对比
  4. RISC-V H-ext 规范的验证反馈（可能发现规范 bug）

### 第一篇论文价值评估

**核心问题**：Reviewer 会问"除了换了个架构，我们学到了什么新东西？"如果答案只是"Verus 在 RISC-V 上也能用"，就是 incremental work。

**真正有价值的技术贡献**：

1. **二阶段页表的组合验证**（核心卖点）：现有 hypervisor 验证工作（Ghost/pKVM on ARM、SeKVM on ARM）都只处理单层地址翻译的隔离证明。RISC-V H-ext 的 VS-stage × G-stage 二阶段翻译让证明复杂度从加法变成乘法——两层页表的组合语义、TLB 一致性（hfence.gvma / hfence.vvma）的形式化，这些在已有工作中没人证过。如果能给出二阶段组合安全定理，这是实质性的 verification contribution。
2. **sail 规范 → Verus trusted spec 翻译管线**：目前 sail 规范和 Verus 之间没有桥梁。系统化的翻译方法对所有 RISC-V 扩展（V-ext、Crypto-ext 等）的未来验证都可复用。
3. **发现 sail H-ext 规范 bug**（高价值但不可控）：H-ext 规范仍在 PR 阶段，形式化验证过程中发现规范歧义或错误对整个 RISC-V 生态有直接影响。
4. **ARM vs RISC-V 验证架构对比**：同一隔离属性在 ARM（Ghost/pKVM, C）vs RISC-V（本工作, Rust+Verus）上的证明结构差异，产出架构洞察。

**论文价值取决于执行深度**：
- 仅做 2-Guest 静态分区 + 简单内存不重叠证明 → 工程报告水平（ATC/EuroSys）
- 聚焦二阶段页表组合定理 + ARM 对比 + 方法论可复用 → 顶会水平（OSDI/SOSP）
- 三者至少占两个才有竞争力

### 第二篇论文（Phase 2，M24）

根据选择方向不同：
- **2A**：扩展 hypervisor → 动态 Guest + 中断隔离的完整验证（系统会议）
- **2B**：Miralis Verus 验证 → M-mode 到 HS-mode 跨特权级验证信任链（安全会议）
- **2C**：Atmosphere-RV → 架构移植对验证工作量影响的量化研究（系统会议）

### 方法论贡献

- Verus 在 RISC-V bare-metal 上的实践指南（工具链、pattern、陷阱）
- sail 规范到 Verus trusted spec 的翻译方法论
- RISC-V 特权级模型的 Verus 建模模板（可复用于其他 RISC-V 验证项目）

---

## 十、与其他 RISC-V 研究方向的协同

- **自定义指令 × LLM 推理**：验证框架可扩展到证明自定义指令的正确性（需 Kami 级硬件验证能力）
- **近数据计算核**：DPU/SmartNIC 中的 RISC-V 核同样面临隔离需求，hypervisor 验证方法论可迁移
- **如意 SDK × Rust OS**：验证 RISC-V Rust hypervisor 直接产出工具链经验，可回馈如意生态
- **可编程网络**：[[atc2025-jia|Rex]] 的 Rust 安全扩展 + 本方向的验证方法 = 可验证网络功能

### 协作生态

| 合作方 | 协作内容 | 互利点 |
|--------|----------|--------|
| [Atmosphere](https://github.com/mars-research/atmosphere) 团队 (Utah) | 共享 Verus 验证经验，复用 flat permission storage 方法论 | 他们获得 RISC-V 移植反馈 |
| [vostd](https://github.com/asterinas/vostd) 团队 (蚂蚁) | 复用页表验证经验和 Verus fork | 他们获得 H-ext 二阶段页表验证成果 |
| [Miralis](https://github.com/CharlyCst/miralis) 团队 (EPFL) | 复用 Sail→Rust 翻译后端，共享 M-mode 建模 | 他们获得 Verus 验证路径（对比 Kani） |
| [sail-riscv](https://github.com/riscv/sail-riscv) 社区 | 协助推进 H-ext PR，贡献验证发现的规范 bug | 社区获得 H-ext 实际验证反馈 |
| [香山](https://github.com/OpenXiangShan/XiangShan) (ICT) | 提供昆明湖 FPGA 测试平台 | 香山获得首个基于其 H-ext 的形式化验证系统 |

---

## 十一、前置知识与入门路径

本方向需要 RISC-V 架构和形式化验证两方面的知识。以下是建议的学习路径：

### RISC-V 架构

1. RISC-V 特权级架构规范（Volume II: Privileged Architecture），重点关注 M/S/U 模式和 H-extension
2. 阅读 [sail-riscv](https://github.com/riscv/sail-riscv) 模型，理解 ISA 形式规范的表达方式
3. 在 QEMU 上运行一个 RISC-V hypervisor（如 Salus 或 Bao），建立直观理解

### 形式化验证

1. [Verus](https://github.com/verus-lang/verus) 官方教程和示例
2. 阅读 VeriSMo 论文（OSDI'24）和 Atmosphere 论文（SOSP'25），理解 Verus 用于系统软件验证的 pattern
3. 了解 Kani（有界模型检查）作为轻量级替代方案

---

## 十二、下一步行动（当前 Hold）

### 如果决定启动

1. 搭建 QEMU RISC-V H-ext 环境，运行 Salus hypervisor
2. 阅读 VeriSMo 源码（[github.com/microsoft/verismo](https://github.com/microsoft/verismo)），理解 Verus bare-metal 模式
3. 尝试 Verus RISC-V 交叉编译（Phase 0 关键路径，Go/No-Go 决策点）
4. 阅读 Salus 源码，评估架构和可验证性
5. 联系 Atmosphere、vostd、Miralis 团队探讨协作

### 持续关注

- sail-riscv H-ext [PR #612](https://github.com/riscv/sail-riscv/pull/612) 合并进度
- Verus 对 RISC-V target 的支持进展
- 是否有其他团队开始做 RISC-V hypervisor 验证（竞争窗口）
