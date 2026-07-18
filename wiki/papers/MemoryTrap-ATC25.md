---
type: paper
name: MemoryTrap
full_title: "MemoryTrap: Booby Trapping Memory to Counter Memory Disclosure Attacks with Hardware Support"
authors: [Chenke Luo, Jiang Ming, Dongpeng Xu, Guojun Peng, Jianming Fu]
venue: ATC
year: 2025
tags: [security, memory-protection, jit-rop, intel-mpk, code-reuse]
source_pdf: "[[atc2025-luo.pdf]]"
source_md: "[[atc2025-luo]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# MemoryTrap: Booby Trapping Memory to Counter Memory Disclosure Attacks with Hardware Support (ATC 2025)

> **一句话总结**：MemoryTrap 的关键观察是 [[JIT-ROP]] 攻击者必须在随机化后极短窗口内按 4 KB 页粒度遍历大量代码才能凑齐 gadget chain；它在编译期向合法执行路径中织入不可读的 booby trap，借 [[Intel-MPK]] 做字节级权限区分，使攻击者平均最多泄露 657 B 即被终止，同时保留 code/data 混排兼容性，运行时开销仅 0.74%–1.85%。

## 问题与动机

[[ASLR]] 与 fine-grained code randomization 让传统离线 [[Code-Reuse-Attack]] 难以直接复用固定 gadget 地址，但 [[JIT-ROP]] 把攻击升级为两阶段：先借 memory disclosure 漏洞在线扫描可执行内存收集 gadget，再链式劫持控制流。作者 claim 的防御焦点是**第一阶段**——阻止或大幅压缩可泄露的代码量，而不是替代 [[Control-Flow-Integrity]] 或完整阻断第二阶段。

现有 memory permission 路线有两类，各有结构性缺陷。**Execute-only Memory（[[Execute-Only-Memory]] / XoM）** 如 XnR、Readactor、HideM、kRˆX 撤销代码页读权限，但 von Neumann 架构下 code/data 混排并不罕见：jump table、手写汇编常量、[[KCFI]] 签名、[[V8]] JIT 生成的 code+data 同页等都会让 XoM 把合法 data-in-code 读误判为 disclosure，或干脆无法部署。**Destructive Code Reads（DCR）** 如 Heisenbyte、NEAR 允许读但破坏已读代码，却被 ZombieGadgets 等 **code inference** 攻击绕过——攻击者维护多份代码副本，只 disclose 一份、执行另一份。

MemoryTrap 走第三条路：**cyber deception**。不在整页上封死读权限，而是在攻击者必经的 gadget 搜索路径上撒不可读 booby trap；正常执行用前缀 JMP 跳过，攻击者线性/图遍历代码页时几乎必然踩中。硬件上选用 [[Intel-MPK]] 而非 EPT 虚拟化或 CHERI 级 ISA 改造，目标是更低部署门槛和更细粒度 trap 管理。深度背景与相关工作见 [[atc2025-luo]]。

## 关键观察 / 隐含假设

- **观察 1：JIT-ROP gadget 搜索受 4 KB 页粒度和有限时间窗口约束，攻击者必须连续遍历大量代码页。** 证据来自 Ahmed et al. 对 traversal strategy 的测量，以及作者对 Metasploit / Exploit-DB 真实 exploit 的统计：相邻 gadget 最小跨度 94.0 KB，仅 13.7% 的 gadget 间距 < 4 KB；JIT-ROP 为避免访问未映射页，以页为单位增量 disclose。
  - **依赖假设**：目标进程已启用 load-time fine-grained randomization，攻击者无法在 disclosure 前离线拿到完整 gadget 库；且 arbitrary read 能力足以遍历代码段。
  - **可能失效场景**：攻击者已有足够信息推断 gadget 而无需大规模扫描；或 disclosure 粒度可小于页、可跳跃采样且恰好避开 trap 分布（论文 §6.2 显示间隔读策略仍与连续遍历结果相近，但采样策略空间未穷尽）。
- **观察 2：合法 data-in-code 读在真实 workload 中极其稀疏，全代码页 execute-only + 临时恢复读权限的开销可忽略。** 作者定义 Read Intensity = 合法读次数 / 执行指令数；SPEC CPU 2017 为 7.0E-11，web server 1.64E-10，database 4.80E-12，OpenSSL 最高也仅 1.40E-7；平均 3.51E-8，约每千万条指令才 1 次合法读。
  - **依赖假设**：程序主体执行路径不密集依赖 code 段内嵌数据；合法读可通过单步 trap + 临时 WRPKRU 恢复完成。
  - **可能失效场景**：手写汇编密集、大量 jump table 查找、或专门构造的 worst-case benchmark——论文自报此类场景可达 **3.23×**  slowdown；若未来 workload 的 Read Intensity 显著上升，MPK fault handler 会成为主瓶颈。
- **假设 1：攻击者在触发第一个 booby trap 前无法凑齐完整 gadget chain。** 插入规则为每函数至少 1 trap、函数 > 4 KB 则每 4 KB 再加 1 个；实测相邻 trap 距离 100% < 4 KB，86.5% < 1 KB。
  - **证据强度**：强。Nginx CVE-2013-2028 上 40,780 次 traversal 仅 39 次找到 ≤1 个 gadget；多份真实 exploit 上 disclosed 代码 273–687 B，远小于 94 KB 最小 gadget 跨度。
- **假设 2：威胁模型聚焦 direct memory disclosure，且系统具备 W⊕X 与 code randomization。** 论文明确不处理 indirect disclosure（从 stack/heap 读 function pointer 再当 gadget）；这与 Readactor 的间接防护正交。
  - **证据强度**：中。direct JIT-ROP 是论文主战场且有 CVE 复现；indirect 路径在 CFI+ASLR 组合下是否仍主导，论文未系统测量。
- **假设 3：Intel MPK 的 16 个 protection key 与 thread-local PKRU 足以支撑全代码页 XoM + trap 子区间区分，且 WRPKRU 无法被攻击者在 disclosure 阶段滥用。**
  - **证据强度**：中偏弱。§8 讨论 WRPKRU 绕过需 4 个 gadget，而 disclosure 阶段最多泄露 1 个；但若攻击者通过非 disclosure 路径先拿到 gadget，或 MPK 与多线程/第三方库 PKey 使用冲突，论文讨论较简略。

## 核心方法

MemoryTrap 是跨 **编译器 — 加载器 — 内核异常处理 — JIT 引擎** 的协同硬化框架，核心是把「检测 disclosure」从整页 XoM 下沉到 **trap 字节区间**。

**Booby trap 构造与织入**（[[LLVM]] pass）：每个 trap 是 5–30 条随机 NOP 组成的变长 snippet，前面加 JMP 跳过；正常执行永不进入 trap 体，但 trap 整体（含 JMP）标记为不可读。变长设计打乱 layout，增加攻击者基于模式识别定位 trap 的难度。插入策略直接回应观察 1：每函数 ≥1 trap，函数 > 4 KB 则每 4 KB 再加 1 个，位置随机化。该策略与 [[JIT-ROP]] 的页级遍历对齐，使攻击者在凑齐 gadget chain 前高概率踩 trap。

**MPK 驱动的细粒度权限**（回应观察 2）：加载时给整个代码段分配 execute-only PKey（读/写禁用，执行仍由传统 PTE 控制）。任何对代码页的读触发 protection fault，内核 handler 查 `.mtrap` 元数据：若地址落在 trap 区间 → 判定 memory disclosure，**立即终止进程**并保存上下文供取证；若在普通代码区 → 视为合法 data-in-code 读，临时恢复该页读权限，设 single-step trap flag，执行完该读指令后撤回权限。相比 Readactor 的 EPT 级 XoM 或 Heisenbyte 的页复制+破坏，MPK 的 WRPKRU 切换 < 20 cycles、无 TLB flush，适合高频 fault 路径上的轻量恢复。

**ELF 元数据通道**：复用 `EI_PAD` 首字节为 `MTRAP_ENABLE`，新增 `.mtrap` section 记录 trap 数量与起止地址；自定义 kernel loader 解析，非定制 loader 可忽略该 section 仍能运行（向后兼容）。内核改动仅 **312 LoC**，含 custom loader、MPK exception handler 和 `mtrap_enable` / `mtrap_add` / `mtrap_delete` syscall。

**三类代码覆盖**：(1) 静态 ELF 应用走 kernel loader；(2) 共享库由修改后的 glibc loader 在 `dlopen` 时 `mtrap_enable` 并注册 trap 列表；(3) [[V8]] TurboFan 在 IR 层按同样规则插 trap，JIT 代码生成后通过 syscall 动态注册，代码页更新时短暂恢复 RW、重写后再锁回。可与 CCR 等 load-time basic-block randomization 联动，随机化时同步更新 `.mtrap` 地址。

## 设计取舍

- **检测即终止 vs 可用性**：发现 disclosure 直接 kill 进程，能阻断攻击但引入 DoS 风险；论文提议可改接 re-randomization，但承认其高开销，当前实现选择硬终止。
- **全代码页 fault vs 仅 trap 区 fault**：为区分 trap 与普通 code 中的合法读，仍把**所有代码页**设为 MPK execute-only，任何 code read 都进 handler；收益是精确区分，代价是合法读走 slow path（尽管 Read Intensity 极低）。
- **编译期固定密度 vs 安全裕度**：4 KB 间隔是安全/性能折中——2 KB 间隔 SPEC 开销 +1.3%，8 KB 间隔开销 -0.7% 但扩大 disclosure 窗口；当前选择保证 100% 相邻 trap < 4 KB。
- **Intel MPK 绑定 vs 可移植性**：MPK 在主流 x86 桌面/服务器可用，ARM AP/XN、RISC-V PMP、PowerPC Protection Keys 可作替代，但论文原型未实现；MPK 16 key/thread-local 语义也与多线程 trap 同步（libmpk）形成工程依赖。
- **边界条件**：对 direct JIT-ROP、已随机化、Read Intensity 低的 server/DB/浏览器 workload 优雅；对 indirect disclosure、无 randomization、或极端 data-in-code 密集程序变脆；不替代 [[Control-Flow-Integrity]]，而是 defense-in-depth 的一层。

## 实验与结果

- **安全 — Nginx CVE-2013-2028**：815.8 KB 代码段、203.9 页；从 20,390 起点 × BFS/DFS 共 40,780 次 traversal，BFS 平均泄露 **657 B**、DFS **299 B** 后触发 trap；仅 25（BFS）/ 14（DFS）次找到 ≤1 gadget。7-gadget exploit 链上相邻 gadget 间有 47–279 个 trap。
- **安全 — MemoryTrap-aware 策略**：间隔读 50 B（步长 200/300/500 B）或从泄露 code pointer 起步，结果与 Table 2 一致（~636–678 B / ~290–451 B），作者用超几何分布解释 trap 不透明性。
- **安全 — 真实 exploit 集**：Metasploit + Exploit-DB 收集的 JIT-ROP exploit，BFS 泄露 499–687 B，DFS 273–340 B；最小 gadget 链跨度 94.0 KB，disclosed 量远不足。
- **安全 — V8 CVE-2020-16040**：5,213 KB JIT 代码含 7,025 traps；攻击仅泄露 **607 B**（到第一个 trap 的距离），完整 chain 需 **2,739 KB**。
- **安全 — Code inference**：两份 ~5 MB JIT 副本克隆攻击，各仅泄露 595 / 653 B；trap 织入每份副本，使 disclose-execute 分离失效。
- **性能 — 微基准**：lmbench 上 fork +0.88%、exec +0.58%、page fault +0.52%、prot fault +0.83%；context switch 开销接近 0。
- **性能 — SPEC CPU 2017**：算术平均 **1.85%**，几何平均 **0.60%**；峰值 povray **8.5%**（大量小 handler 函数各插 1 trap）；对比文献报告值 MemoryTrap **1.21%** vs XnR/Readactor 2.2%、HideM 1.4%、Heisenbyte 18.3%（基于 SPEC 2006 数据）。
- **性能 — 真实应用**：Nginx/Apache/Lighttpd 平均 **0.74%**（最大 2.11%）；MySQL/MongoDB/Redis/SQLite 平均 **1.30%**；Kraken JS benchmark **1.54%**。
- **性能 — OpenSSL 兼容性**：827,604 B 嵌入数据、656M+ 次合法读全部成功；平均每块嵌入数据仅 779 B，即使误触也不足以支撑 JIT-ROP。
- **开销 — 磁盘/内存**：二进制增大平均 **5.85%**（3.2%–8.8%），运行时内存 **1.05%**（0.3%–2.1%）；与 CCR 联用时 pointer fixup 一次性开销 web server 5.67%、DB 2.78%、SPEC 4.01%。

## Critical Analysis

### 论证链条

observation → design → result 在 **direct JIT-ROP + 已随机化** 场景下闭合较好。作者先用 gadget 间距与页粒度论证「搜索必须广泛遍历」，再用 4 KB trap 密度对齐该遍历模式，最后用 CVE 与合成 traversal 证明 disclosed 字节量级（~300–700 B）远低于 exploit 需求（94 KB–2.7 MB）。MPK slow path 的开销又被 Read Intensity 测量解释，与 SPEC/服务器低 overhead 一致。

主要跳步是把「踩 trap 即检测到攻击」等同于「阻止成功 JIT-ROP」。论文测量的是 disclosure 阶段，未端到端演示在启用 MemoryTrap 后完整 exploit 链失败率；且终止进程后攻击者仍可重试造成 DoS，这与「tip the balance toward defenders」的叙事之间还有运维成本缺口。把结论外推到 **所有** memory disclosure 场景也偏强——indirect disclosure、无需完整 chain 的信息泄漏、或侧信道读内存等不在 threat model 内。

### 假设压力测试

**Indirect JIT-ROP** 是最明显的压力点。Readactor 通过把 code pointer 重定向到 XoM 区防御 stack/heap 上的函数指针泄露；MemoryTrap 明确只做 direct disclosure。若漏洞允许从数据页拿到代码 指针再小块定向读，攻击者可能减少盲目遍历，trap 触发概率是否仍足够高，论文未定量验证。

**DoS 与重试攻击**：kill-on-detect 对安全有利，但面向互联网的 Nginx/MySQL 可被反复触发 trap 导致服务不可用；论文承认 re-randomization 替代方案但未实现，也未评估攻击者故意读 trap 区做 availability attack 的成本。

**MPK 语义与生态冲突**：MPK key 线程本地化，需 libmpk 同步；若同进程其他安全机制（如 ERIM/Hodor 式敏感数据隔离）已占用 PKey，或第三方库自行 WRPKRU，可能与 MemoryTrap 的 execute-only PKey 冲突。论文声称加载期分配 PKey 可隔离，但长生命周期多组件进程的集成风险未实验。

**攻击者适应**：§6.2 表明间隔读和 pointer-start 策略未显著改善 disclosure 量，但假设攻击者不能获得 trap 元数据（`.mtrap`）或使用非读侧信道（如 cache timing on trap fault）推断 layout。变长 NOP + 随机位置增加签名难度，却不等于不可学习；论文未讨论长期对抗中的 trap 定位或 binary 逆向。

### 实验可信度

强项：真实 CVE（Nginx、V8）、真实 exploit 集、多种 traversal 策略、code inference 复现、OpenSSL 高 Read Intensity 兼容性测试、ablation 式 overhead 分解（合法读检查 vs JMP 插入）、与 XoM/DCR 文献的性能对照。40,780 次 traversal 的统计规模对「高概率踩 trap」claim 有说服力。

不足：安全评估主要是 **模拟 disclosure**，非完整 weaponized exploit 成功率；baseline 系统（Readactor/Heisenbyte 等）未在同硬件上重跑安全实验，只能比性能文献值。平台单一（Linux 5.10.11 + Intel i9-13900KF）；无 ARM/云环境/容器嵌套虚拟化测试。正确性方面，对 JIT 代码频繁 RW 更新（TurboFan 优化路径）仅描述协议，缺少大规模 fuzz 或形式化保证。指标偏重平均 disclosed bytes，对「仍可能泄露的 1 个 gadget 能做什么」威胁分析较浅。

### 系统性缺陷

- **可用性**：检测即终止，论文未量化 DoS 概率或 failover 策略。
- **尾延迟 / fault 路径**：合法 data-in-code 读走 page fault + single-step，对 Read Intensity 极低 workload 可忽略，但论文未报告 tail latency 分布。
- **故障恢复**：进程被杀后状态丢失；无热重启、无 trap 触发告警分级，运维集成论文未讨论。
- **可观测性**：保存上下文供取证，但未描述与 SIEM/audit 管道集成或 false positive 率（合法调试器读代码？）。
- **部署成本**：需定制 kernel、LLVM 13、patched glibc、可选 patched V8；与 distro 主线合并成本高，论文未讨论。
- **多租户 / 容器**：MPK 与 namespace、KVM 嵌套、per-container loader 的交互论文未覆盖。

## 局限与 Future Work

- **局限 1**：响应策略仅为进程终止，存在 DoS 风险；re-randomization 仅作讨论未实现。
- **局限 2**：不防御 indirect memory disclosure；与 Readactor 类方案需组合部署。
- **局限 3**：绑定 Intel MPK + 定制 toolchain/kernel，移植与长期维护成本高。
- **局限 4**：worst-case data-in-code 密集程序可达 3.23× slowdown，虽非典型生产路径，但说明 handler 路径并非永远可忽略。
- **Future work 1**：在 production trace 上测量 indirect disclosure + MemoryTrap 的组合阻断率，明确与 CFI/指针加密方案的互补边界。
- **Future work 2**：实现 detect-then-re-randomize 路径，量化 DoS 风险、重随机化开销与可用性之间的 Pareto 前沿。
- **Future work 3**：在 ARM AP/XN、RISC-V PMP 上复现 trap 密度与 fault 成本，验证「MPK 高效」是否可跨平台推广。
- **Future work 4**：端到端 red-team 评估——完整 Metasploit exploit 在 MemoryTrap 下的成功率、重试 DoS 窗口、以及与调试/perf 工具共存的 false positive 率。

## 相关

- **相关概念**：[[ASLR]]、[[JIT-ROP]]、[[Code-Reuse-Attack]]、[[Intel-MPK]]、[[Execute-Only-Memory]]、[[Control-Flow-Integrity]]、[[LLVM]]、[[ELF]]、[[V8]]
- **同类系统**：XnR、Readactor、HideM、Heisenbyte、NEAR、BGDX、kRˆX、CHERI
- **同会议**：[[ATC-2025]]
- **对比**：MemoryTrap 相对 XoM 保留 code/data 混排；相对 DCR 抗 code inference；相对 Readactor 避免 EPT 虚拟化开销，但不覆盖 indirect disclosure
