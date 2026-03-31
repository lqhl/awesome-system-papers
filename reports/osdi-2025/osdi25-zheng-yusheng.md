# Extending Applications Safely and Efficiently

**作者**：Yusheng Zheng (UC Santa Cruz), Tong Yu (eunomia-bpf Community), Yiwei Yang (UC Santa Cruz), Yanpeng Hu (ShanghaiTech University), Xiaozheng Lai (South China University of Technology), Dan Williams (Virginia Tech), Andi Quinn (UC Santa Cruz)
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation，Boston, MA，July 7–9, 2025）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/zheng-yusheng
**源文件**：[osdi25-zheng-yusheng.pdf](../../papers/osdi-2025/osdi25-zheng-yusheng.pdf)

---

## 一、背景

软件扩展（software extension）是一种无需修改原始应用源码即可定制化行为的机制，广泛应用于 Web 浏览器、HTTP 服务器、文本编辑器、数据库等各类系统。扩展能够提升应用性能、增加自定义功能、增强安全性，以及实现可观察性监控。对于部署方来说，扩展机制的好处是可以轻松集成上游维护更新，同时保持定制化能力。

现有的扩展框架在以下三个核心属性之间难以取得良好平衡：

- **扩展安全性（Safety）**：扩展故障不应损害宿主应用或底层系统；
- **扩展隔离性（Isolation）**：宿主应用不应能修改扩展逻辑（安全监控场景尤其需要）；
- **扩展效率（Efficiency）**：扩展执行应接近原生速度。

Linux 内核的 eBPF 已成为内核扩展的事实标准，但其对用户态扩展的支持较弱，且不支持细粒度的互联性/安全性权衡。

---

## 二、要解决的问题

**1. 互联性与安全性的权衡难以精细控制**

扩展必须具备互联性（interconnectedness），即能够读写宿主状态、调用宿主函数。但安全性要求限制扩展的能力。现有框架要么无法表达这一权衡（如 WebAssembly、NaCl），要么只能粗粒度地设置（如 lwC、RLBox、Shreds），要么需要修改宿主源码（如 Orbit、Wedge）。

**2. 现有框架效率低下**

许多框架（Orbit、lwC、Wedge）为隔离引入了操作系统级的上下文切换开销；Wasm、NaCl 等使用软件故障隔离（SFI），运行时开销远高于原生执行。eBPF uprobe 的每次调用延迟超过 2500 ns，远高于理想水平。

**3. 用户态 eBPF 支持不足**

现有用户态 eBPF 运行时（ubpf、rbpf）性能差、eBPF 兼容性不完整，无法用于生产环境。

**4. 扩展的"最小权限原则"缺乏系统性支持**

不同部署场景（监控、防火墙、负载均衡）对扩展的互联性需求不同，但现有框架缺乏系统化方式让管理员按扩展入口点精细指定权限。

---

## 三、核心设计

本文提出两个主要贡献：

### Extension Interface Model（EIM）

EIM 是一套新的扩展接口规范模型，核心抽象是**资源（resource）**：将扩展运行所需的每个特性（包括具体硬件资源如内存，以及抽象资源如调用宿主函数的能力）统一表示为资源，并通过**能力（capability）**来控制扩展对资源的使用权限。

EIM 的规范由两方共同生产：

- **应用开发者**：定义宿主能提供给扩展的 capability 集合（本质是枚举可扩展的互联性），在开发时完成；
- **扩展管理员**：在部署时为每个扩展入口点创建 extension class，指定该入口允许的 capability 子集，实现部署级别的细粒度权衡。

EIM 是运行时无关的规范层，原则上可增强任意现有扩展框架。

### bpftime

bpftime 是一个新的用户态扩展运行时，负责执行和强制 EIM 规范，核心设计原则两条：

**原则一：轻量级安全与隔离**
- 使用 eBPF 风格的静态验证（基于 PREVAIL verifier）确保扩展遵从 EIM 规范、内存安全、类型安全；
- 使用 Intel MPK（Memory Protection Keys）实现进程内硬件级隔离（ERIM 风格），开销极低；
- 验证通过后通过用户态 JIT 编译为原生代码执行。

**原则二：隐式扩展入口（Concealed Extension Entries）**
- 通过动态二进制重写（基于 Frida 和 libcapstone）实现：只有当用户实际加载了某个扩展时，才将对应的 trampoline 注入宿主程序，否则不产生任何运行时开销；
- uprobe/uretprobe 使用标准指令 trampoline；系统调用入口使用 zpoline（利用 zero page 适配两字节指令）。

**bpftime 架构**：
- **Loader**：包含验证器（Verifier）和二进制重写器（Rewriter）；
- **Runtime**：在宿主同进程内执行扩展，实现进程内 MPK 隔离和 bpftime maps；
- **Maps**：提供跨扩展调用的状态存储，支持进程本地、跨进程、进程-内核三种共享模式，兼容 eBPF map 系统调用接口。

bpftime 完全兼容现有 eBPF 生态（libbpf、bcc、bpftrace），通过对 eBPF 相关系统调用的拦截实现透明替换。

---

## 四、实现细节

**验证器**：
- 接收 eBPF 字节码格式的扩展程序；
- 解析宿主程序的 DWARF 调试信息生成 BTF 类型信息，注入字节码；
- 将 EIM 中的 function capability 转为 mock kfunc，将 state capability 编码为 verifier 支持的约束子句；
- 调用 eBPF verifier 完成验证，复杂 resource constraint 回退到 PREVAIL verifier；
- 验证通过后由用户态 JIT 编译为原生代码。

**重写器**：
- 使用 ptrace 暂停宿主进程，注入 bpftime user runtime；
- 使用 Frida + libcapstone 实现指令级插桩；
- 对 uprobe/uretprobe 类型使用标准 trampoline（替换原指令，末尾附加被覆盖的指令）；
- 对系统调用类型使用 zpoline，遍历所有 syscall 指令替换为 zero page 跳转。
- 当前每个入口点仅支持单个扩展，多扩展可通过 dispatcher pattern 实现（类似 libxdp 设计）。

**进程内隔离（IntraProcess Isolation）**：
- 为每个扩展的内存分配独立 MPK protection key；
- 在扩展调用前执行 WRPKRU 切换权限，返回宿主后恢复；
- 扩展内存页设为 non-writable，key 值编码在扩展代码中、设置 non-readable 防篡改；
- 已知存在 syscall-based ERIM bypass 漏洞，建议采用 Jenny 的 syscall filtering 防御。

**bpftime Maps**：
- 实现进程本地 / 跨进程 / 进程-内核三种共享模式；
- 通过 interposing eBPF map syscall 透明替换内核 eBPF map；
- 支持哈希表、数组、LPM trie、ring buffer、perf event array 及 per-CPU 变体；
- 使用 per-CPU 变体和 lock-free 同步减少竞争。

**代码规模**：bpftime 开源（GitHub 1,000+ stars，20+ contributors），Redis 扩展性改造仅需约 20 行代码。

---

## 五、实验结果

**实验平台**：
- Server A：双路 Intel Xeon Gold 5418Y（24核，2.00GHz，45MB LLC），256GB DDR5
- Server B：双路 Intel Xeon E5-2697-v2（48核，2.7GHz，30MB LLC），256GB DDR3
- 每个指标取 10 次均值，speedup 用几何平均。

### 主要 use case 性能结果

| Use Case | 对比基线 | bpftime 结果 |
|---------|---------|-------------|
| Nginx Plugin | Lua / WebAssembly / ERIM / RLBox | 仅 2% overhead；比 Lua/Wasm 低 5.5×/6× 开销；比 ERIM/RLBox 低 5.5×/4.5× 开销 |
| Deepflow 微服务监控 | eBPF Deepflow | 吞吐量提升至少 1.5×（eBPF 版最高降低 54%） |
| Redis 持久化调优 | alwayson / everysec | Batch-48 比 alwayson 提升 4.17×；delayed-fsync+fast-notify 比 alwayson 提升 5×+，仅比 everysec 慢 10%，但数据丢失减少 5 个数量级 |
| FUSE Caching | 原生 FUSE | 操作延迟降低最高 2.4 个数量级（240×） |
| sslsniff SSL 监控 | eBPF sslsniff | 吞吐量下降从 28% 降至 7.4%，提升 3.79× |
| Syscount 系统调用统计 | eBPF Syscount | 监控进程 overhead 从 10.3% 降至 3.36%；非监控进程 overhead 降至 0（eBPF 为 9.6%） |

### 微基准测试

| 操作 | eBPF | bpftime |
|------|------|---------|
| Uprobe 延迟 | 2561.57 ns | 190.02 ns（快 13.5×） |
| Uretprobe 延迟 | 3019.45 ns | 187.10 ns（快 16×） |
| Syscall Tracepoint | 151 ns | 232 ns（慢 1.5×） |
| User memory read | 23.3 ns | 1.5 ns（快 15.5×） |
| User memory write | 23.9 ns | 1.4 ns（快 17×） |
| hash_map_update | 50.8 ns | 23.8 ns（快 2.1×） |

与 ubpf/rbpf 相比，bpftime 在 8 个微基准上平均快 1.53×/1.72×。

**加载延迟**：bpftime 扩展加载约 48 ms（vs LD_PRELOAD 30 ms），差距较小。

**eBPF 兼容性**：测试 17 个 BCC/bpftrace 工具均可直接运行（无需修改代码）；bpf-conformance 测试套件仅失败 1 例（ubpf/rbpf 分别失败 22/23 例）。

---

## 六、批判性分析

**1. Concealed extension entries 的 overhead 分析存在选择性报告**

论文强调 concealed extension entries 为"未使用的入口点"节省 1.35 ns/call，但实际已使用的 extension entry 因 trampoline 带来 190 ns 延迟（vs 无 trampoline 的 1.35 ns 基础延迟），额外开销达 140×。作者将这 190 ns 与 eBPF 的 2561 ns 对比，看起来优势巨大，但并未与更轻量的方案（如 LD_PRELOAD、纯 function pointer）对比，也未讨论高频调用路径下 140× overhead 的实际影响。

**2. FUSE caching 结果存在不公平对比嫌疑**

Table 2 显示 bpftime 将 fstat 延迟从 3.65s 降至 0.176s（20×），将 openat 从 17.0s 降至 0.074s（229×）。这些数字是 100,000 次操作的总时延，来自 FUSE 本身的额外 context switch 开销极为可观。bpftime 通过缓存绕过了 FUSE 调用，实质上是"跳过了整个 FUSE 栈"，而非优化了 FUSE。论文将此与 ExtFUSE 类比，但 ExtFUSE 是 kernel-level 缓存，与 bpftime 的用户态缓存在功能完整性和一致性保证上差异显著，这一点被轻描淡写。

**3. Redis 持久化评估未考虑真实故障场景**

论文声称 delayed-fsync 比 everysec 少丢 5 个数量级的数据，但评估基于理论分析（"最多丢 2 个更新"），而非真实 crash 场景下的实测。Redis 的 AOF fsync 行为在高并发、IO 争用情况下可能远比模型复杂，理论上界未必等于实测平均损失。

**4. 威胁模型假设较为理想化**

论文明确假设 extension manager 是"trusted and infallible"（可信且不会犯错），但现实中管理员错配 EIM 规范本身就是主要风险来源。论文未讨论如何防止管理员过度授权（如给所有扩展赋予所有 capability）导致 EIM 形同虚设。

**5. MPK 隔离已知漏洞被轻描淡写**

论文承认 bpftime 容易受 syscall-based ERIM bypass 攻击，并建议采用 Jenny 的 syscall filtering 防御——但这一防御并未在当前实现中集成，而是被留为 future work。对于一篇强调安全性的论文，这一缺陷值得更多篇幅讨论。

**6. 单个扩展入口点限制被低估**

"当前实现仅支持每个 entry point 一个扩展，多扩展需要 dispatcher pattern"——这一设计限制对于真实部署场景（多个独立团队各自部署扩展）是实质性约束，但论文几乎一笔带过。

---

## 七、总结

本文提出 EIM 和 bpftime，共同解决了用户态软件扩展中安全性、隔离性与效率三者难以兼顾的问题。EIM 提供了一套以资源和能力为核心的细粒度接口规范模型，使扩展管理员能够按最小权限原则精确控制每个扩展入口的互联性与安全性权衡。bpftime 通过 eBPF 风格验证、Intel MPK 进程内硬件隔离和动态二进制重写，在完全兼容现有 eBPF 生态的前提下，将扩展性能提升至接近原生，uprobe 延迟较内核 eBPF 降低超过 13×。在 Nginx、Redis、FUSE、微服务监控等 6 个真实 use case 中均有显著收益。主要局限在于每个入口点仅支持单扩展、MPK 旁路漏洞尚未修复、以及加载延迟高于 LD_PRELOAD。
