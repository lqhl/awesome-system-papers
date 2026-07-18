---
type: paper
name: HyperTurtle
full_title: "Accelerating Nested Virtualization with HyperTurtle"
authors: [Ori Ben Zur, Jakob Krebs, Shai Aviram Bergman, Mark Silberstein]
venue: ATC
year: 2025
tags: [virtualization, ebpf, nested-vm, kata-containers, kvm]
source_pdf: "[[atc2025-zur.pdf]]"
source_md: "[[atc2025-zur]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-18
---

# Accelerating Nested Virtualization with HyperTurtle (ATC 2025)

> **一句话总结**：嵌套虚拟化（L0→L1→L2）的 vm-exit 路径至少 4 次 world switch（单次 ~1µs、占 vm-exit 处理 ~33%），HyperTurtle 把 L1 hypervisor 关键路径封装为 [[eBPF]] hyperupcall 在 L0 安全执行，EPT fault 延迟降 5.1×、Kata 启动加速 27%、memcached 在 500µs SLO 吞吐 +72%，且保留 L1 对 L2 的策略控制。

## 问题与动机

[[Kata-Containers]] 等 VM-based container 用硬件虚拟化实现比 process-level [[Container]] 更强的隔离，适合 serverless 与多租户执行不可信第三方代码。但云厂商普遍把这类 workload 部署为 **nested VM**（L0 裸金属 hypervisor 上跑 L1 租户 VM，L1 再托管 L2 容器 VM），以方便整合与编排。

嵌套虚拟化的核心痛点是 **world switch 爆炸**：L2 每次 vm-exit 必须先 trap 到 L0，L0 再注入事件给 L1 处理，处理完再经 L0 回到 L2——至少 **4 次 world switch**，而非嵌套只需 2 次。EPT fault 等路径可达 **6 次**；且 L2→L0 的处理延迟普遍高于 L1→L0（如 cpuid 0.78µs vs 2.77µs，NMI 5.7µs vs 16.7µs）。作者测量 Kata 启动比非嵌套慢 **2×**（1.5s vs 0.7s），其中 EPT fault 占嵌套场景启动时间的 **46%**。

现有缓解方案各有硬伤：
- **DVH (Direct Virtual Hardware)** [[DVH]]：把 L0 设备直通给 L2，I/O 快但剥夺 L1 对 L2 的 traffic shaping / routing / monitoring 控制。
- **SVT**：用 [[SMT]] 把 L0/L1/L2 绑到 sibling hyperthread 加速切换，但不减少 handler 本身更贵的嵌套路径，且 SMT 在新 CPU 上逐步被禁用。
- **PVM / X-Containers / CKI**：syscall 重定向、library OS 或硬件改造，兼容性差或需专用 guest。
- **Peer-Pods / Free-The-Turtles / Dichotomy**：绕开嵌套，牺牲 hypervisor 级资源控制（如 L1 内 L2 内存 overcommit）或要求 L1 持续在线。

作者 claim：应有一种 **通用、非侵入、硬件无关** 的方式，在保留 L1 对 L2 完全控制权的前提下，削减嵌套虚拟化的 world switch 数量与成本。

## 关键观察 / 隐含假设

- **观察 1**：嵌套虚拟化的性能税主要来自 **world switch 次数 × 单次成本**，而非单一子系统逻辑本身；EPT fault、Nested-VirtIO 发包、PMC profiling 三类热路径都符合这一模式。
  - **依赖假设**：L0 能在不进入 L1 的前提下，用受限代码安全完成 L1 hypervisor 的部分关键路径逻辑；这些路径在目标 workload 中调用足够频繁，优化才有端到端收益。
  - **可能失效场景**：world switch 不是瓶颈的长运行计算密集型 workload；vm-exit 频率极低的 steady-state 服务；非 KVM 或更深嵌套（L3+）场景论文未覆盖。

- **观察 2**：[[eBPF]] 的 verifier 约束（无锁、无无界循环、受限内存访问）虽限制表达力，但 EPT fault 映射、网络包过滤、PMC 采样等 **短路径、无复杂同步** 的逻辑可在 eBPF 内实现，复杂情况 fallback 到原 L1 路径即可。
  - **依赖假设**：热路径上的 EPT fault 大多可用预分配 frame pool（4096 帧）满足；race 可通过共享 map + 锁 + cyclic log 协调；file-backed shmem 内存后端是 Kata 常见配置。
  - **可能失效场景**：huge page EPT fault、page cache 未映射到 VMM page table 的 fault、frame pool 耗尽或 lock 竞争导致频繁 fallback；需要文件系统级复杂逻辑的 offload。

- **观察 3**：DVH 的性能优势与 L1 策略控制之间存在结构性矛盾——L1 必须在 L2 数据路径上挂 hook 才能做 firewall / rate limit / 观测，而 Nested-VirtIO 的双层 virtio 又引入额外 world switch。
  - **依赖假设**：L1 可在 L0 管理的 per-vNIC [[eBPF]] hook（XDP/TC）上安装策略程序，且 per-interface 隔离足以防止跨 L1/L2 窃听；Kubernetes [[CNI]] 可通过自定义插件动态创建 DVH 接口。
  - **可能失效场景**：需要 L1 深度介入非 eBPF 可表达的网络语义（复杂 NAT、连接跟踪状态机）；多 L1 共享物理 NIC 时的隔离策略错误；CNI 生态外部署。

- **假设 1**：云租户信任 L1 提交的 eBPF（经 L0 verifier 或 cloud vendor 签名验证），且 `bpf_probe_read_hyperupcall` 的地址校验足以隔离不同 L1 的物理内存域。
  - **证据强度**：**中**——有 per-L1 内存边界检查与 per-vNIC hook 隔离设计，但安全模型依赖 verifier/签名正确性；未做对抗性 red-team 或形式化隔离证明。

- **假设 2**：评测中的 Kata + Cloud-Hypervisor + virtiofsd shmem 配置代表生产 nested container 部署；启动阶段 EPT fault 密集，因此 EPT 优化能显著改善短生命周期 serverless 体验。
  - **证据强度**：**中**——Baidu/AWS 等确实用 nested Kata，但论文 testbed 为单 NUMA、SMT off、idle=poll 的实验室配置；未用真实 cloud trace 验证 steady-state 占比。

## 核心方法

HyperTurtle 在 [[Hyperupcalls]] 思想基础上，为 **嵌套虚拟化** 设计通用 offload 框架：L1 把关键路径逻辑编译为 eBPF program，经 hypercall 加载并 attach 到 L0 的 vm-exit / 网络 / perf hook；L0 处理 L2 事件时直接调用 hyperupcall，**跳过进入 L1 的 world switch**，同时 L1 仍完全控制 offload 逻辑内容。

**1. Hyperupcall 基础设施**

- **注册**：拆分为 load 与 link 两步 hypercall，支持一个 program 挂多个 hook、避免重复加载。
- **数据共享**：新增 shared-memory PCI device 暴露 array eBPF map 给 L1；新 helper `bpf_probe_read_hyperupcall` 让 eBPF 安全读取 L1 物理内存（校验地址归属、隔离不同 L1）。
- **安全模型**：L1 自供 eBPF（L0 verifier / Prevail）或 cloud vendor 签名 eBPF（Hornet）；均限制 eBPF 只能访问所属 L2 资源。

**2. EPT fault hyperupcall**（最复杂，560 LOC eBPF）

回应观察 1/2：在 L0 处理 L2 EPT fault、发现 `EPT_{1→2}` 缺页时插 hook，由 hyperupcall 直接在 L0 完成 `EPT_{1→2}` 映射并更新 `EPT_{0→2}`，把 6 次 world switch 路径缩短。

- L1 预维护 **4096 帧** frame pool（eBPF map）；池空则 fallback 传统路径。
- **hyperupcall fault log** 记录 hyperupcall 新建的 L2-PA 映射，L1 下次 vm-exit 时同步 VMM page table。
- **page fault log** + 全局锁协调与 virtiofsd 等 shmem 用户的 race；shmem page fault handler 也参与锁协议。
- 仅支持 **file-backed shmem** 后端（QEMU/Cloud-Hypervisor/Kata 常见）；不支持 huge page。

**3. 网络 hyperupcall + DVH 兼容层**

回应观察 3：L1 把 eBPF 挂到 L0 为 L2 创建的 DVH vNIC 上（Pass / Firewall / Rate Limiter / TCP-Top 等），兼得 DVH 单跳数据路径与 L1 策略控制。

- per-vNIC hook 保证 L1 不能窃听非自有接口流量。
- 自定义 **CNI plugin**：k8s 创建 pod 时经 hypercall 让 L0/QEMU 动态 hotplug DVH 接口到 L1，再配置 namespace 与地址，恢复与 Cilium 等 eBPF 网络工具的兼容。

**4. Profiling hyperupcall**

L0 在 PMC 溢出中断路径直接采样 L2 寄存器（新 helper `vcpu_probe`），经 ring buffer 共享给 L1；避免 profiling 路径上 **26 次** world switch。

实现改动集中在 [[KVM]] 模块与 QEMU installer：L0 kernel/KVM ~151 LOC、eBPF helper ~119 LOC、QEMU ~775 LOC、L1 KVM ~653 LOC（Table 5）。深度实现见 [[atc2025-zur]] 或 [[atc2025-zur.pdf]]。

## 设计取舍

- **取舍 1：eBPF 安全沙箱 vs 表达力与 fallback 频率**——为通过 verifier，EPT fault 用预分配池 + 锁 + log 而非动态分配或复杂同步；池空、锁失败、log 满、page cache 未就绪时均 fallback 到完整 L1 路径，保证正确性但最坏情况性能回到 baseline。
- **取舍 2：保留 L1 控制 vs 实现复杂度**——相对 DVH 裸直通，每个包可能执行 L1 编写的 eBPF（Firewall 使平均延迟比 Direct-Assignment 高 11%）；Pass-through eBPF 开销可忽略（p=0.5% 与 Direct-Assignment 相同）。
- **取舍 3：非侵入 KVM 修改 vs 功能覆盖**——仅支持单层嵌套、单全局 EPT fault hook（同时仅一个 L1 可用）、不支持 huge page 与多 EPT hyperupcall 并存；换通用性换 ~2.5K LOC 级改动量。
- **取舍 4：硬件无关 vs 极致性能**——不依赖 SMT/新 ISA 扩展，但也不做 SmartNIC/XDP-AF_XDP 等进一步 offload（§4.7 列为 future direction）。
- **边界条件**：Kata 短生命周期启动、memcached/nginx 等 latency-sensitive 服务、需 L1 网络策略的 k8s 部署表现最佳；长稳态 CPU-bound、依赖 huge page 或大页启动、多租户 L1 争抢同一 EPT hook 时变脆。

## 实验与结果

- **Testbed**：2×Xeon Silver 4216、512GiB RAM、SMT off；L1 为 12 vCPU QEMU VM；L2 为 1 vCPU 2GiB Kata + Cloud-Hypervisor；网络 virtio+vhost zero-copy；10 次迭代平均。
- **EPT fault 微基准**：嵌套 VM 平均 28.39µs / P99 49.13µs → HyperTurtle 5.39µs / 10.32µs（**5.25× / 4.76×**），平均延迟与非嵌套 L1 VM 相同（5.58µs），P99 仅慢 8%。
- **Kata 启动**：Node.js 等应用平均 **27%** 加速（4KiB 页），2MiB 页 **8%**；Redis 1GiB snapshot 启动 **55%** 加速，DeathStarBench TextService **35%** 加速。
- **网络**：相对 Nested-VirtIO，平均延迟降 **33%**（90.2µs → 60.5µs with Firewall），吞吐与 Direct-Assignment 持平（~17 Gb/s）；HyperTurtle+Pass 与 Direct-Assignment 几乎相同（55µs vs 54.5µs）。
- **memcached**（Facebook ETC load）：500µs SLA 吞吐从 **29 KQPS → 50 KQPS**（+72%），仅比 Direct-Assignment 低 9%（Firewall eBPF 开销）；与普通 container 性能持平。
- **Nginx / Redis**：Nginx QPS +45%（1.24K → 1.8K）；Redis memtier 吞吐最高 **+65%** vs Nested-VirtIO。
- **Profiling**：采样事件处理时间比 vanilla L1→L2 降 **7.15×**，仅比最优 L0→L1 慢 16%；4000Hz 采样下 memcached 500µs 吞吐从 42 → 53 KQPS（+26%）。

## Critical Analysis

### 论证链条

Observation（world switch 是嵌套虚拟化首要瓶颈，EPT/网络/profiling 三类路径可量化）→ Design（eBPF hyperupcall 在 L0 执行 L1 关键逻辑，共享 map + helper 解决状态与隔离）→ Implementation（KVM/QEMU 小改动 + 三例 hyperupcall）→ Evaluation（微基准 + Kata 启动 + memcached/nginx/redis 宏基准）逻辑链条闭合较好。

薄弱跳步在于：(1) **「通用框架」claim 主要靠三个子系统 proof-of-concept**，storage、scheduling、SmartNIC 等仅 §4.7 提纲；(2) **端到端「与 regular container 持平」** 在 memcached 等场景成立，但 Kata 启动仍比非嵌套慢 ~57%（1.1s vs 0.7s），论文强调「缩小差距」而非完全追平；(3) **正确性** 依赖 lock+log+fallback 协议，实验以性能为主，缺少并发 fault / virtiofsd race 的正确性压力测试或 formal argument。

### 假设压力测试

- **论文已证明**：在 file-backed shmem + 4096 frame pool 配置下，EPT fault 延迟可降至非嵌套同级；DVH + L1 eBPF 可恢复网络策略且 Pass eBPF 几乎零开销；profiling 采样路径大幅缩短；Kata 启动与多个宏基准显著受益。
- **可能失效**（推断）：
  - **Huge page / 大页启动**：论文明确不支持 huge page EPT hyperupcall；2MiB 页场景收益仅 8%，说明假设 2 对页大小敏感。
  - **Steady-state 长运行服务**：EPT fault 主要在启动期密集；对长期运行的内存稳定 workload，HyperTurtle 收益可能接近零。
  - **多 L1 租户**：全局 EPT fault hook 限制「仅一个 L1 可用」，多租户云 L1 场景需 per-L2 handler（论文标为 future work）才能扩展。
  - **eBPF 策略复杂度**：Firewall 已带来 11% 延迟损失；更复杂连接跟踪或状态ful 策略可能使 DVH 优势被 eBPF 执行成本吃掉。
  - **非 Kata 栈**：评测绑定 Cloud-Hypervisor（支持 pass-through）；Firecracker 等不支持 pass-through 的 VMM 网络优化路径未验证。
  - **更深嵌套或 Xen**：设计声明面向 KVM 单层嵌套；外推到 Xen 或 L3+ 缺乏证据。

### 实验可信度

- **Workload 代表性**：Kata 启动、memcached ETC、DeathStarBench、nginx/redis 覆盖云原生常见路径；但缺少真实 production nested trace（多租户混部、迁移、长期运行）。
- **Baseline 公平性**：Nested-VirtIO 作为嵌套 baseline 合理；Direct-Assignment 作为性能上界；**未与 SVT、PVM、CKI 等最新嵌套优化方案对比**——主要对比 vanilla nested + DVH 两极。
- **Ablation**：网络 Pass vs Firewall 分离了基础设施 vs 策略开销；**缺少** EPT fault 各组件（pool 大小、lock、log）的独立 ablation，以及 fallback 触发频率统计。
- **Metric**：覆盖平均/P99 延迟、吞吐、启动时间；**未系统报告** tail latency 在 fallback 风暴下的行为、hyperupcall 安装/卸载开销、故障恢复、多 L2 并发下的锁竞争率。

### 系统性缺陷

- **尾延迟与 fallback**：池空、锁失败、log 满时静默退回 6-switch 原路径；论文未量化 fallback 比例及其对 P99/P999 的影响。
- **故障隔离与恢复**：L0 hyperupcall 崩溃、eBPF 验证失败、QEMU installer 异常时 L2 行为 **论文未讨论**；无热升级或版本回滚机制描述。
- **可观测性 / 运维**：L1 需维护 eBPF 程序、frame pool  replenishment、fault log 同步；与现有 KVM/QEMU 运维流程的集成成本未评估。
- **资源隔离**：eBPF 在 L0 执行消耗 host CPU；多 L2 高密度场景下 L0 侧 eBPF 开销可能成为新的 noisy neighbor 源 **论文未讨论**。
- **安全运维**：信任 L1 提交 eBPF 在云环境仍是有争议模型；per-vNIC 隔离设计合理但未提供跨租户渗透测试。

## 局限与 Future Work

- **局限 1**（论文承认）：复杂功能（文件系统访问、全量 offload）难以在 eBPF 内实现，必须保留 L1 fallback；EPT hyperupcall 不支持 huge page、page cache 未映射页、且仅单 L1 可用。
- **局限 2**（论文承认）：仅验证单层 KVM 嵌套；更深嵌套时 hyperupcall 应安装在哪一层未回答。
- **局限 3**（实验边界）：评测为实验室单 NUMA 配置（SMT off、idle=poll），与主流云实例（Graviton 无 SMT 但多租户混部）存在差距。
- **Future work 1**（论文提出）：per-L2 EPT fault handler 消除全局 hook 限制；优化 page fault log 大小与同步协议。
- **Future work 2**（论文提出）：XDP AF-XDP 直路由、storage DVH + eBPF、SmartNIC offload、DVH direct execution/scheduling 等扩展场景。
- **Future work 3**（可验证）：在 **真实 cloud nested Kata trace** 上测量 fallback 率与 steady-state 收益占比；与 **PVM/SVT** 等方案在同硬件上 head-to-head；对 **多 L1 并发 EPT fault** 做正确性 fuzzing。

## 相关

- **相关概念**：[[eBPF]]、[[Nested-Virtualization]]、[[KVM]]、[[Kata-Containers]]、[[VM-Exit]]、[[EPT]]、[[VirtIO]]、[[XDP]]、[[CNI]]
- **同类系统**：[[Hyperupcalls]]、[[DVH]]、SVT、PVM、X-Containers、CKI、Peer-Pods、Free-The-Turtles、Dichotomy、[[Firecracker]]、[[gVisor]]
- **同会议**：[[ATC-2025]]
- **对比**：相对 DVH 牺牲 L1 控制，HyperTurtle 用 L0 eBPF 恢复策略且 Pass 路径性能等同 DVH；相对 SVT 依赖 SMT，HyperTurtle 硬件无关但需改 KVM/QEMU；相对绕开嵌套的 Peer-Pods，保留 full hypervisor 编排灵活性与内存 overcommit
