# 方向深度调研：RISC-V 全栈形式化验证

> 生成日期: 2026-04-03

---

## 一、方向概述

**核心命题**：利用 RISC-V 开源 ISA + 开源处理器（香山）的独特优势，构建从硬件 RTL 到 OS 内核到应用层的全栈可验证系统，这是 ARM/x86 闭源生态根本无法实现的。

**为什么是现在**：2025 年顶会出现了形式化验证的"实用化拐点"——[[3731569.3764821|Atmosphere]] 将证明代码比从 20:1 降到 3.32:1，[[atc2025-tang|CONVEROS]] 用 4 人月在真实 OS 上找到 20 个 bug，[[3731569.3764822|AutoMan]] 自动生成 70-97% 验证代码。同时 RISC-V 生态（[香山](https://github.com/OpenXiangShan/XiangShan)第三代昆明湖、[如意 SDK](https://ruyisdk.org/)）也在快速成熟。两条曲线正在交汇。

---

## 二、现有工作全景（Novelty 分析基础）

### 2.1 RISC-V 侧已有工作

| 层次 | 项目 | 状态 | 验证深度 |
|------|------|------|----------|
| ISA 形式规范 | [sail-riscv](https://github.com/riscv/sail-riscv) | RV64GC + Privileged 已完成 | 可生成 Isabelle/Coq/Lean 定义 |
| ISA 形式规范 | [sail-riscv H-ext](https://github.com/riscv/sail-riscv/pull/612) | PR #612 未合并，[KU Leuven 有独立实现](https://lirias.kuleuven.be/retrieve/762909) | 可启动 Xvisor，未进官方仓库 |
| 硬件 RTL 验证 | [riscv-formal](https://github.com/SymbioticEDA/riscv-formal) (SymbiYosys) | 成熟，支持 RVFI 接口 | 有界模型检查，非完整证明 |
| 硬件 RTL 验证 | [CHERI-Flute](https://www.cl.cam.ac.uk/research/security/ctsrd/cheri/cheri-risc-v.html) (JasperGold) | 已完成，发现未知 bug | 完整属性验证，但仅限简单顺序核 |
| 硬件 RTL 验证 | [VeriCHERI](https://arxiv.org/abs/2407.18679) | 2024，exhaustive security verification | 全局安全属性（机密性/完整性） |
| 香山验证 | [DRAV](https://github.com/OpenXiangShan/XiangShan) (DiffTest+XFUZZ+LightSSS) | 生产级，20000+ 测试用例 | **仅仿真验证，无数学证明** |
| CHERI-RISC-V | [CHERI-Toooba](https://github.com/CTSRD-CHERI/Toooba) (OoO) | FPGA 原型，非流片 | 功能正确，未形式化验证 |
| CHERI-RISC-V | [CHERIoT-Ibex](https://github.com/microsoft/cheriot-ibex) (嵌入式) | 有 observational correctness 验证 | 已验证，但仅限 32 位顺序核 |

### 2.2 OS/系统软件侧已有工作

| 项目 | 会议 | 技术栈 | RISC-V 支持 | 验证范围 |
|------|------|--------|-------------|----------|
| [seL4](https://github.com/seL4/seL4) | 历史 | C + Isabelle/HOL | ✅ RV64 已验证到二进制 | 功能正确性 + 完整性 + 二进制等价 |
| [[3731569.3764821\|Atmosphere]] | SOSP'25 | Rust + [Verus](https://github.com/verus-lang/verus) | ❌ 仅 x86-64 | 完整微内核，proof ratio 3.32:1 |
| [[atc2025-peng-yuke\|ASTERINAS]] | ATC'25 | Rust + Verus(部分) | ✅ SMP/FPU/VirtIO | framekernel，仅页表模块已验证 |
| [[atc2025-tang\|CONVEROS]] | ATC'25 | Rust + model checking | ✅ (基于 [ASTERINAS](https://github.com/asterinas/asterinas)) | 并发正确性，12 模块 20 bug |
| [[atc2025-jia\|Rex]] | ATC'25 | Rust | Linux 内核扩展 | 语言级安全替代 eBPF 验证器 |
| [[3731569.3764817\|Ghost/pKVM]] | SOSP'25 | C | ARM | 可执行规范，11K LoC 目标 |
| [[3731569.3764856\|TickTock]]/[[3731569.3764828\|Tock]] | SOSP'25 | Rust + [Flux](https://github.com/flux-rs/flux) 精化类型 | ✅ | MPU 隔离验证，发现 6 bug |
| [[3731569.3764826\|Miralis]] | SOSP'25 | Rust | ✅ RISC-V (VisionFive 2) | 固件隔离，6.2K LoC |
| [[osdi25-leblanc\|PoWER]] | OSDI'25 | 工具无关 Hoare 逻辑 | 通用 | crash consistency |
| [[osdi25-zhang-tony\|Basilisk]] | OSDI'25 | provenance invariants | 通用 | 分布式协议自动证明 |
| [[3731569.3764844\|CHERIoT RTOS]] | SOSP'25 | C/C++ | CHERI-RISC-V | 内存安全 + compartmentalization |

### 2.3 关键空白（Gap Analysis）

```
硬件 RTL ←——————→ ISA 规范 ←——————→ OS 内核 ←——————→ 应用
   ↑                  ↑                 ↑                ↑
   │                  │                 │                │
香山: 仅仿真      sail-riscv:       seL4: 已验证      应用层:
无数学证明        缺 H-ext         但非 Rust          几乎空白
                                   Atmosphere:
                                   已验证但无 RISC-V
                                   ASTERINAS:
                                   有 RISC-V 但仅
                                   部分验证
```

**最大的空白在"衔接处"**：

1. **硬件-ISA 衔接**：sail-riscv 有形式规范，香山有 RTL，但无人证明"香山的 RTL 实现符合 sail-riscv 规范"（对于 OoO 核这极其困难）
2. **ISA-OS 衔接**：seL4 在 RISC-V 上验证了，但 seL4 proof 假设硬件正确实现 ISA；Atmosphere 验证了 OS 但不在 RISC-V 上
3. **H-extension 全栈**：H-ext 的 sail 规范未合并、无验证过的 hypervisor、硬件实现也少——整条链都是空白

---

## 三、Novelty 分析：三个可能的子方向

### 子方向 A：验证香山关键微架构模块

**做什么**：选择香山的安全关键模块（TLB、cache coherence protocol、分支预测隐私性），用形式化方法证明其满足 sail-riscv 规范定义的属性。

**Novelty 评估**：⭐⭐⭐ 中等
- CHERI-Flute 已经做了顺序核的完整验证，但 **OoO 核的形式化验证是公认的开放问题**
- 香山是目前唯一开源的高性能 OoO RISC-V 核（6 发射、乱序执行），复杂度远超 Flute/Rocket
- 学术价值：回答"形式化验证能否 scale 到真实的 OoO 处理器？"
- **风险**：完整验证几乎不可能，必须选择关键子模块

**与顶会的关联**：
- [VeriCHERI](https://arxiv.org/abs/2407.18679) (2024) 证明了 RTL 级 exhaustive security verification 可行，但仅限简单核
- [SimFuzz](https://arxiv.org/abs/2601.11838) 在香山上用 fuzzing 发现了 17 个 bug（7 个 CVE），说明香山确实有值得验证的安全问题

### 子方向 B：Rust 验证内核移植 RISC-V + 硬件信任链

**做什么**：将 Atmosphere 的 Rust+Verus 验证微内核移植到 RISC-V，与 Miralis（已在 RISC-V 上运行的 Rust 固件监控器）组合，构建从固件到内核的验证信任链。

**Novelty 评估**：⭐⭐⭐⭐ 高
- [[3731569.3764821|Atmosphere]] 目前仅支持 x86-64，移植到 RISC-V 需要处理 **架构特定的验证挑战**（SBI 接口、RISC-V 特权级模型 vs x86 ring 模型、RISC-V 页表格式）
- [[3731569.3764826|Miralis]] 已经在 RISC-V 上证明了 M-mode 固件隔离的可行性，但 Miralis 本身未形式化验证
- 组合 Miralis（M-mode）+ 验证微内核（S-mode）= **首个 RISC-V 上从固件到内核的验证信任链**
- 这是 [ASTERINAS](https://github.com/asterinas/asterinas) 的 [vostd](https://github.com/asterinas/vostd) 项目正在尝试的方向（验证 framekernel TCB），但 ASTERINAS 的目标是 Linux 兼容性（宏内核），验证难度远高于微内核

**与顶会的关联**：
- [[3731569.3764821|Atmosphere]] (SOSP'25): flat permission 技术可直接复用
- [[3731569.3764826|Miralis]] (SOSP'25): RISC-V 固件监控器，99.98% M-mode trap 仅 5 种原因
- [[atc2025-peng-yuke|ASTERINAS]] (ATC'25): framekernel + [Verus](https://github.com/verus-lang/verus)，但仅页表模块已验证
- [[3731569.3764856|TickTock]] (SOSP'25): [Flux](https://github.com/flux-rs/flux) 精化类型验证嵌入式隔离，方法论可借鉴

### 子方向 C：RISC-V H-extension 验证 Hypervisor

**做什么**：基于即将合并的 sail-riscv H-extension 规范，构建第一个形式化验证的 RISC-V hypervisor。

**Novelty 评估**：⭐⭐⭐⭐⭐ 非常高
- H-extension sail 规范未合并（PR #612 in progress）
- **不存在任何验证过的 RISC-V hypervisor**（[[3731569.3764817|Ghost/pKVM]] 是 ARM 的）
- [RustVMM](https://github.com/rust-vmm) 刚获得 RISC-V 支持（2024.09），[Cloud-Hypervisor](https://github.com/cloud-hypervisor/cloud-hypervisor) v45 可运行
- 这是一个"三无地带"：无正式规范、无验证实现、硬件支持也刚起步——先行者优势巨大

**与顶会的关联**：
- [[3731569.3764817|Ghost/pKVM]] (SOSP'25): C 语言可执行规范方法，可迁移到 RISC-V
- [[3731569.3764821|Atmosphere]] (SOSP'25): Rust+Verus 验证方法，可用于 hypervisor
- [[3731569.3764822|AutoMan]] (SOSP'25): 自动生成 70-97% 验证代码，降低工程量
- [[3731569.3764826|Miralis]] (SOSP'25): 已解决 M-mode/S-mode 隔离，hypervisor 在 HS-mode，可复用思路

**风险**：依赖 sail-riscv H-ext PR 合并进度；硬件可用性有限（需要 QEMU 或 FPGA）

---

## 四、推荐路线：子方向 B + C 组合

### 为什么选这个组合

```
┌─────────────────────────────────────────────┐
│ M-mode:  Miralis (已有) → 形式化验证 Miralis │  ← 子方向 B
├─────────────────────────────────────────────┤
│ HS-mode: 验证 Hypervisor (新建)              │  ← 子方向 C
├─────────────────────────────────────────────┤
│ VS-mode: 验证微内核 (Atmosphere 移植)        │  ← 子方向 B
├─────────────────────────────────────────────┤
│ VU-mode: 用户态应用                          │
└─────────────────────────────────────────────┘
     ↕ 全部运行在 RISC-V (香山/QEMU) 上
```

1. **Novelty 最大化**：全球首个 RISC-V 全特权级验证系统栈
2. **增量可发表**：每一层都是独立贡献（Miralis 验证 → hypervisor → 微内核 → 组合）
3. **技术栈统一**：全部用 Rust + [Verus](https://github.com/verus-lang/verus)，复用 [[3731569.3764821|Atmosphere]] 的 flat permission 方法论
4. **RISC-V 差异化**：RISC-V 的 4 级特权模型（M/HS/VS/VU）比 ARM 的 EL0-3 更清晰，天然适合分层验证
5. **避开硬核区**：不碰 OoO RTL 验证（子方向 A），聚焦软件栈，可行性高得多

---

## 五、可行性分析

### 5.1 技术可行性

| 依赖项 | 状态 | 风险 |
|--------|------|------|
| Rust + [Verus](https://github.com/verus-lang/verus) 工具链 | 成熟，[[3731569.3764821\|Atmosphere]] 已验证可用 | 低 |
| [sail-riscv](https://github.com/riscv/sail-riscv) RV64GC 规范 | 已完成 | 无 |
| [sail-riscv H-ext](https://github.com/riscv/sail-riscv/pull/612) 规范 | PR #612 in progress，[KU Leuven 有独立实现](https://lirias.kuleuven.be/retrieve/762909) | 中（可先用独立实现） |
| RISC-V QEMU H-ext 支持 | 已支持 | 无 |
| [[3731569.3764826\|Miralis]] 源码 | Rust，6.2K LoC，[开源](https://github.com/CharlyCst/miralis) | 低 |
| [[3731569.3764821\|Atmosphere]] 源码 | Rust+Verus，开源（待确认） | 中（可能需联系作者） |
| [ASTERINAS](https://github.com/asterinas/asterinas) RISC-V 支持 | 已有 SMP/FPU/VirtIO | 低 |
| [香山](https://github.com/OpenXiangShan/XiangShan) H-ext 支持 | 昆明湖架构，需确认 | 中 |
| FPGA 原型验证 | VisionFive 2 等 RISC-V 板已可用 | 低 |

### 5.2 团队规模与时间估算

**最小可行团队**：3-4 人

| 角色 | 人数 | 技能要求 |
|------|------|----------|
| 系统验证研究员 | 1-2 | Rust + Verus/Coq，OS 内核经验 |
| RISC-V 架构工程师 | 1 | RISC-V 特权级模型，QEMU/FPGA |
| 形式化方法专家 | 1 | SMT solver、精化类型、proof engineering |

**时间线**（18-24 个月）：

| 阶段 | 时间 | 产出 | 可发表性 |
|------|------|------|----------|
| Phase 0: 基础设施 | M1-M3 | Verus on RISC-V 工具链打通，QEMU H-ext 环境搭建 | — |
| Phase 1: Miralis 验证 | M4-M9 | 形式化验证 Miralis 的 M-mode 隔离属性 | ✅ 独立论文（安全会议） |
| Phase 2: 微内核移植 | M7-M12 | Atmosphere 架构移植 RISC-V，验证 RISC-V 特定模块（页表、SBI 接口） | ✅ 独立论文（系统会议） |
| Phase 3: Hypervisor | M10-M18 | 轻量验证 hypervisor（基于 sail H-ext 规范） | ✅ 独立论文（系统/安全会议） |
| Phase 4: 全栈组合 | M16-M24 | M-mode → HS-mode → VS-mode 组合验证，端到端安全属性证明 | ✅ 旗舰论文（OSDI/SOSP 级别） |

### 5.3 与香山/如意的协作点

| 合作方 | 协作内容 | 互利点 |
|--------|----------|--------|
| [香山](https://github.com/OpenXiangShan/XiangShan) (BOSC/ICT) | 提供昆明湖 H-ext 支持信息；共享 DRAV 验证基础设施 | 香山获得首个形式化验证成果，提升可信度 |
| [如意 SDK](https://ruyisdk.org/) | 提供 RISC-V Rust 工具链支持；集成 Verus 到如意开发环境 | 如意获得"可验证系统"差异化特性 |
| [ASTERINAS](https://github.com/asterinas/asterinas) | 共享 RISC-V Verus 验证经验（页表模块）；复用 [vostd](https://github.com/asterinas/vostd) 验证库 | ASTERINAS 获得 hypervisor 层验证能力 |
| [sail-riscv](https://github.com/riscv/sail-riscv) 社区 | 协助推进 H-ext PR 合并；贡献验证发现的规范 bug | 社区获得 H-ext 的实际验证反馈 |

---

## 六、风险与缓解

| 风险 | 严重度 | 概率 | 缓解策略 |
|------|--------|------|----------|
| [[3731569.3764821\|Atmosphere]] 源码不开源或难移植 | 高 | 中 | 备选：基于 [ASTERINAS](https://github.com/asterinas/asterinas) TCB（10.5K LoC）做验证，或从零构建精简微内核 |
| [sail-riscv H-ext](https://github.com/riscv/sail-riscv/pull/612) 长期不合并 | 中 | 中 | 直接使用 [KU Leuven 的独立实现](https://lirias.kuleuven.be/retrieve/762909)，或自行贡献合并 |
| [Verus](https://github.com/verus-lang/verus) 在 RISC-V bare-metal 上不成熟 | 高 | 中 | [ASTERINAS](https://github.com/asterinas/asterinas) 已在做 RISC-V + Verus，可共享经验；最坏情况退回 Coq/Lean |
| 验证工作量超预期 | 高 | 高 | 严格控制验证范围：每层只验证隔离属性（isolation），不追求完整功能正确性 |
| 缺乏 H-ext 硬件 | 低 | 低 | QEMU 完全支持；FPGA 可用 [CHERI-Toooba](https://github.com/CTSRD-CHERI/Toooba) 或等待香山支持 |

---

## 七、竞争格局与定位

### 最可能的竞争者

| 竞争者 | 方向 | 我们的差异化 |
|--------|------|-------------|
| [[3731569.3764821\|Atmosphere]] 团队 (Utah) | 可能自行移植 RISC-V | 我们加 hypervisor 层 + Miralis 固件层，scope 更大 |
| [ASTERINAS](https://github.com/asterinas/asterinas) 团队 (蚂蚁/[vostd](https://github.com/asterinas/vostd)) | 验证 framekernel TCB | 他们目标是 Linux 兼容宏内核（验证难度高 10×），我们聚焦微内核+hypervisor |
| [seL4](https://github.com/seL4/seL4) 团队 (UNSW) | 已有 RISC-V 验证 + [实验性 VMM](https://github.com/SEL4PROJ/sel4_riscv_vmm) | 他们用 C+Isabelle（重），我们用 Rust+Verus（轻），proof ratio 差距巨大 |
| [Cambridge CHERI 团队](https://www.cl.cam.ac.uk/research/security/ctsrd/cheri/) | CHERI-RISC-V 安全验证 | 他们聚焦硬件，我们聚焦全栈软件 |
| [KU Leuven](https://lirias.kuleuven.be/retrieve/762909) | H-ext sail 规范 | 他们做规范，我们做基于规范的系统实现+验证 |

### 独特定位

> **首个在 RISC-V 上实现 M-mode 到 VS-mode 全特权级形式化验证的系统栈，使用统一的 Rust+Verus 方法论，证明代码比 < 5:1。**

这个定位的关键词：
- "全特权级"——不是只验证一层，而是 M/HS/VS 三层 + 层间接口
- "Rust+[Verus](https://github.com/verus-lang/verus)"——相比 [seL4](https://github.com/seL4/seL4) 的 C+Isabelle 更现代、更高效
- "< 5:1 proof ratio"——[[3731569.3764821|Atmosphere]] 做到 3.32:1，我们在更复杂的多层系统上控制在 5:1 以内
- "RISC-V"——ARM/x86 做不到

---

## 八、预期学术贡献

1. **[[3731569.3764826|Miralis]] 验证** → 首个形式化验证的 RISC-V 固件监控器（安全会议：USENIX Security / CCS / S&P）
2. **Atmosphere-RV** → 首个 Rust+[Verus](https://github.com/verus-lang/verus) 验证微内核移植到非 x86 架构的经验报告，量化架构移植对验证工作量的影响（系统会议：OSDI / ATC）
3. **RV-Hypervisor** → 首个基于 sail H-ext 规范验证的 RISC-V hypervisor（系统/安全会议：SOSP / USENIX Security）
4. **全栈组合** → 首个跨 3 个特权级的组合验证系统，端到端信息流安全证明（旗舰：OSDI / SOSP）
5. **方法论** → Rust+Verus 全栈验证方法论的可复用模板和经验教训（验证会议：PLDI / CAV）

---

## 九、与其他研究方向的协同

本方向与之前分析的其他 RISC-V 方向可形成互补：

- **方向 1（自定义指令 × LLM 推理）**：验证框架可用于证明自定义指令的正确性
- **方向 2（近数据计算核）**：DPU/SmartNIC 中的 RISC-V 核同样需要验证，本方向的方法论可迁移
- **方向 5（如意 SDK × Rust OS）**：直接产出 Rust RISC-V OS 工具链和验证库
- **方向 6（可编程网络）**：[[atc2025-jia|Rex]] 已证明 Rust 可替代 eBPF 验证器，本方向的验证方法可扩展到网络扩展

---

## 十、下一步行动

### 立即可做（本周）

1. 确认 [[3731569.3764821|Atmosphere]] 源码开放状态和许可证
2. 确认[香山](https://github.com/OpenXiangShan/XiangShan)昆明湖是否支持或计划支持 H-extension
3. 阅读 [KU Leuven 的 sail H-ext 实现](https://lirias.kuleuven.be/retrieve/762909)和 [PR #612](https://github.com/riscv/sail-riscv/pull/612) 状态
4. 搭建 QEMU RISC-V + H-ext 开发环境

### 短期（1 个月内）

5. 阅读 [[3731569.3764826|Miralis]] 源码，评估形式化验证的工作量
6. 在 RISC-V QEMU 上跑通 [ASTERINAS](https://github.com/asterinas/asterinas)，理解其 [Verus](https://github.com/verus-lang/verus) 验证模块
7. 联系 Atmosphere 和 ASTERINAS 团队，探讨协作可能
8. 撰写详细的技术方案（选择具体验证哪些属性）

### 中期（3 个月内）

9. 完成 [Verus](https://github.com/verus-lang/verus) on RISC-V bare-metal 工具链验证
10. 启动 Phase 1（[[3731569.3764826|Miralis]] 验证）的原型工作
11. 向 [sail-riscv](https://github.com/riscv/sail-riscv) 社区贡献 H-ext 测试/反馈
