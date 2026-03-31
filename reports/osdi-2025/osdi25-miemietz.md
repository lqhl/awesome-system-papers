# MettEagle: Costs and Benefits of Implementing Containers on Microkernels

**作者**：Till Miemietz, Viktor Reusch, Matthias Hille (Barkhausen Institut); Lars Wrenger (Leibniz-Universität Hannover); Jana Eisoldt (Barkhausen Institut); Jan Klötzke (Kernkonzept GmbH); Max Kurze, Adam Lackorzynski (TU Dresden & Kernkonzept GmbH); Michael Roitzsch, Hermann Härtig (Barkhausen Institut & TU Dresden)
**会议**：OSDI 2025（第 19 届 USENIX OSDI，2025 年 7 月 7–9 日，Boston, MA）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/miemietz
**源文件**：[osdi25-miemietz.pdf](../../papers/osdi-2025/osdi25-miemietz.pdf)

---

## 一、背景

云计算场景中，容器（container）因其轻量、启动快、运行时性能接近裸机而成为隔离多租户工作负载的主流手段，逐步取代虚拟机（VM）在 serverless/FaaS 等场景的地位。然而，容器本质上只是"强化版的进程"——其隔离能力依赖宿主 Linux 内核提供的 cgroups、namespaces、seccomp-bpf 等附加机制，而这些机制本身显著增大了内核的复杂度和攻击面。

微内核架构（如 L4Re/Fiasco.OC）天然遵循最小权限原则（Principle of Least Authority, PoLA）：进程默认不持有任何权限，需显式获取 capability 才能访问系统服务；所有驱动和服务运行在用户态独立任务中，内核本身极小。这一特性理论上可以消除容器实现对 seccomp-bpf、namespaces 等复杂内核机制的依赖，从而降低 TCB 并提升安全性。

然而，微内核系统长期以来主要用于嵌入性系统（静态配置工作负载），其能否高效支撑云场景下高动态、大并发的容器部署尚无系统性研究。

---

## 二、要解决的问题

1. **单体内核容器的内在安全缺陷**：Linux 上实现容器需要 seccomp-bpf（50,200 行 BPF 代码）、namespaces、cgroups 等复杂内核机制，这些机制共享于所有容器，历史上产生了大量高危 CVE（如任意代码执行、权限提升、跨容器内存访问）。

2. **微内核容器可行性未知**：能否在微内核上构建功能完整、兼容现有应用（Python/OCI）、安全隔离的容器运行时，尚无实践验证。

3. **微内核在服务器级动态工作负载下的性能未知**：L4Re 的 IPC 开销、内存管理串行化、capability 委托的锁争用等问题能否满足 FaaS 场景的并发启动和 I/O 性能需求，需要量化分析。

---

## 三、核心设计

### MettEagle 整体架构

MettEagle 是运行在 L4Re 上的容器（compartment）引擎，分两层：

- **Compartment Service**（类比 runC）：负责为 compartment 分配资源（向各系统服务创建 session），委托 capability 给新 compartment，启动并监控其任务，compartment 结束后回收资源。
- **Phlox**（高级运行时，类比 containerd）：对外提供 FaaS API，通过网络远程触发函数执行，将每个函数实例沙箱化在独立 compartment 中。

### 隔离机制映射

| Linux 容器机制 | MettEagle 的对应实现 |
|---|---|
| namespaces（可见性隔离） | capability 集合即命名空间：compartment 只能看到/访问被委托的 capability，无 PID 共享等全局标识符 |
| seccomp-bpf（系统调用过滤） | **不需要**：L4Re 系统服务通过独立 IPC gate 限制接口，compartment 只持有 session-specific gate |
| cgroups（资源配额） | 每个系统服务在 session 创建时接受资源限制参数，通过 resource context 跟踪使用量 |

### Capability-Based 安全基础

L4Re 中 capability 是不可伪造的权限 token。任务启动时无任何 capability；capability 可委托（delegate）或撤销（revoke）；IPC gate 标识客户端身份，服务端可安全区分请求来源。compartment 引擎掌控所有 control plane gate（如创建 session），compartment 内应用只拿到 data plane gate（如网络收发）。

---

## 四、实现细节

### 新开发组件（89,271 SLOC 总计）

| 组件 | 功能 | 规模 |
|---|---|---|
| SPAFS | 带写支持的内存文件系统 | 501 SLOC |
| LUNA | 10GBit NIC 驱动 + UDP/IP 网络栈 | 8,735 SLOC |
| LSMM | 并行化内存管理器（基于 LLFree） | 4,289 SLOC |
| PROMFS | 并行化 boot 文件系统 | 780 SLOC |
| Compartment Service | compartment 生命周期管理 | 1,793 SLOC |
| Phlox | FaaS 启动器 / 高级运行时 | 826 SLOC |

### L4Re 优化

- 将 moe 改为多核运行，避免跨核 IPC
- 使用 LSMM 和 PROMFS 并行化 moe 的内存管理和 boot FS

### 遭遇的性能陷阱及规避方案

**1. 单 reply capability 限制并发**：L4Re 线程只有一个隐式 reply cap，服务线程每次只能服务一个客户端。解决：使用 callback 机制，客户端传入回调 gate，服务异步通知结果。

**2. Capability 撤销（unmap）在关键路径上造成高延迟**：L4Re 内核 RCU 实现导致 revoke 操作可能阻塞整个调度 tick（10ms）。解决：hot path 上从不执行 revoke；使用线程池复用监控线程；删除操作放入专用后台线程。

**3. Capability 数据结构锁争用**：delegation 时同时锁 source 和 dest task，阻碍并发委托。解决：去除 source task 的锁（依赖内核 cap 数据结构自身锁保护）。

### 应用支持

- 移植 Python 3 到 L4Re（使用自研交叉编译器从标准 Linux 源码生成 L4Re 可执行文件）
- 移植 10GBit Ethernet NIC 驱动（基于 Ixy 驱动框架）
- 集成 SeBS FaaS 基准测试框架

---

## 五、实验结果

### 实验平台

双插槽服务器，2× Intel Xeon Platinum 8358（32 核/CPU），500 GiB 内存，10GBit NIC；关闭 SMT 和 TurboBoost。对比基线：Linux process、runC v1.1.10、Kata Containers v3.3.0 + Firecracker（用 containerd 管理）。

### 容器启动延迟

| 并发数 N | Linux process | runC | Kata+FC | L4Re |
|---|---|---|---|---|
| 1 | ~0.2ms | ~70ms | ~300ms | ~1ms |
| 64 | ~0.2ms | ~200ms | ~300ms | ~100ms |

- L4Re 单容器启动比 runC 快约 70x（1ms vs 70ms）
- 高并发时 L4Re 因 moe 串行锁和 capability 操作锁争用而退化（100ms@N=64）
- 系统中已有大量 idle compartment 不影响新容器的启动延迟

### 网络性能（10GBit UDP 带宽）

- 低并发（少量线程）：L4Re 带宽约 350 MiB/s，Linux/runC 约 900 MiB/s（L4Re 缺少 Receive Side Scaling，单核处理）
- 高并发（多线程）：L4Re 可达线速；Linux/runC 反而因并发 UDP 传输下降
- UDP 延迟：各平台均约 40µs，基本持平

### SeBS FaaS 基准（顺序执行）

- 大多数 benchmark：L4Re 比 runC 慢 ≤15%；HTML benchmark L4Re 比 runC 快 10%
- ZIP benchmark：L4Re 比 runC 慢约 2x（文件系统操作密集：stat 约 4µs vs Linux 的 460ns）
- L4Re 的 Python 代码执行时间高于 runC，但快速启动延迟将差距抹平
- Kata+FC 端到端延迟最高（VM 启动开销大）

### SeBS FaaS 基准（16 并发 burst 模式）

- empty function 和 HTML：L4Re 与 runC 相近
- ZIP 和图计算：L4Re 比 runC 慢 1–2x（文件系统和并行共享对象加载慢）

### TCB 大小对比

| 系统 | SLOC |
|---|---|
| MettEagle（全部组件）| 89,271 |
| Linux 容器（内核+containerd+runC）| 2,699,812 |

### CVE 分析（33 个高危/严重 CVE）

| 类别 | 完全缓解（FM） | 部分缓解（PM） | 未缓解（N） |
|---|---|---|---|
| seccomp/eBPF | 8 | 0 | 0 |
| namespaces | 4 | 13 | 5 |
| cgroups | 0 | 3 | 0 |
| **合计** | **12** | **16** | **5** |

---

## 六、批判性分析

**CVE 分析方法论的局限性**：论文选取的 33 个 CVE 仅限于 Linux 容器隔离机制（seccomp、namespaces、cgroups）相关的高危漏洞，明确排除了用户态容器基础设施（containerd、runC）的漏洞——而论文自己承认 MettEagle 的 FaaS 运行时在功能上远不如 Linux 对应实现，因此排除是有利于自己的选择。此外，"partially mitigated"的标准相当宽松：只要不发生"即时、完全的跨容器内存隔离突破"，就算 PM，这掩盖了 MettEagle 用户态组件同样可能存在类似 bug 的事实。

**性能比较的公平性存疑**：论文与 runC 对比时使用 empty seccomp filter（`--seccomp unconfined` 等价），而生产环境中 seccomp filter 通常非空。这使 runC 基线性能偏高，削弱了 L4Re 的相对优势论据（如果 seccomp filter 有真实负载，runC 的启动延迟会更高，L4Re 的优势会更明显，但论文把这个选择轻描淡写）。

**文件系统性能问题被轻视**：stat 调用慢 10 倍（4µs vs 460ns）是个显著的系统性问题，直接导致 ZIP benchmark 慢 2x 以上，且影响所有 Python 初始化（模块加载）。论文将其归因于"实现问题"并建议用持久内存风格的 mmap-based FS 优化，但此优化未在论文中实现，结论依赖于"可以修"的假设而非实测数据。

**并发扩展性退化的根因不够深入**：N=64 时 L4Re 启动延迟从 1ms 增至 100ms（2 个数量级），论文归因于 moe 的单锁和 capability 操作锁争用，但并未给出具体的锁分析或 profiling 数据，无法判断这是根本性的架构限制还是可优化的实现问题。

**OCI 镜像不支持**：MettEagle 不支持 OCI 镜像格式，无法运行任何现有的 Docker/containerd 生态镜像，与生产系统的兼容性差距极大。论文将其定位为"未来工作"，但这对实际部署而言是关键障碍。

**timing side-channel 缓解只是定性分析**：Section 5.3 声称 L4Re 因 real-time capable 和较少共享状态而更能抵抗 timing 攻击，但没有提供任何实测验证（无论是攻击复现还是延迟方差测量）。

---

## 七、总结

MettEagle 通过在 L4Re 微内核上实现容器引擎，证明了微内核架构能提供比 Linux 容器更小的 TCB（89K vs 270W SLOC）和更好的安全姿态（33 个高危 CVE 中 12 个完全缓解）。性能方面，单容器冷启动比 runC 快约 70 倍（1ms vs 70ms），大多数 FaaS 基准端到端延迟与 runC 相当；但高并发启动因锁争用退化明显，文件系统操作慢 10 倍是当前主要性能瓶颈。该工作最适合对安全性和 TCB 大小有严格要求（如嵌入式云、认证系统）的场景，尚不适合要求 OCI 兼容性和高并发大规模部署的生产云环境。
