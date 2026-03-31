# Fork in the Road: Reflections and Optimizations for Cold Start Latency in Production Serverless Systems

**作者**：Xiaohu Chai (Tsinghua University, Ant Group), Tianyu Zhou, Jianfeng Tan, Tiwei Bie, Anqi Shen, Dawei Shen, Qi Xing, Shun Song, Tongkai Yang, Le Gao, Feng Yu, Zhengyu He (Ant Group), Keyang Hu, Kang Chen (Tsinghua University), Dong Du, Yubin Xia (Shanghai Jiao Tong University), Yu Chen (Quan Cheng Laboratory & Tsinghua University)
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/chai-xiaohu
**源文件**：[osdi25-chai-xiaohu.pdf](../../papers/osdi-2025/osdi25-chai-xiaohu.pdf)

---

## 一、背景

Serverless 计算（FaaS, Function as a Service）已被 AWS Lambda、Azure Functions、Google Cloud Run、阿里云函数计算等各大公有云广泛采用。其核心价值在于对开发者屏蔽基础设施管理，自动处理资源分配、扩缩容和成本优化。

Cold start（冷启动）是 serverless 计算长期存在的核心性能瓶颈：当函数被调用时若没有可用的预热实例，平台需要从头初始化一个新实例，通常耗时超过 1 秒。考虑到 serverless 函数本身往往只需 50-100ms 执行时间，冷启动延迟完全主导了用户体验。

学术界和工业界已提出多种优化方向：基于 fork/checkpoint-restore 的快速实例创建（Catalyzer、MITOSIS）、缓存保活策略（keep-alive）、定制化轻量运行时等。然而这些方法在真实大规模生产环境中的效果并不理想。

本文来自 Ant Group（蚂蚁集团）的 AFaaS（Ant FaaS）团队，拥有超过 5 万个 unique function、每日约 1 亿次调用的生产规模背景。

---

## 二、要解决的问题

通过对生产环境的深入分析，作者发现现有 cold start 优化存在三个被普遍忽视的关键瓶颈：

### Gap-1：Control Path 延迟
容器冷启动不只是 container initialization，整个 control path 同样关键。在 Catalyzer 已将 container initialization 优化到毫秒级的情况下，基于 OCI 规范的 containerd → shim → 运行时引擎二进制 → sandbox 调用链依然引入 **18ms–25ms** 的控制路径开销（占总冷启动时间 30%–40%）。每次 serverless 函数调用都需要重新加载 Catalyzer 运行时二进制文件，这是主要瓶颈。

### Gap-2：资源竞争延迟
高并发场景下容器冷启动性能极不稳定：
- `clone()` 系统调用（创建新的 network 和 IPC namespace）在 ×24 并发时最坏延迟从 1.45ms 暴增到 **418ms**
- IPC namespace 创建涉及 POSIX message queue 的 VFS superblock 操作，在高并发下 `sb_lock`、`mount_lock` 争用严重
- network prepare 阶段（设置 veth、IP 等）从 2ms 劣化到 21.14ms
- seccomp 安装阶段延迟从 7.58ms 飙升到 13.01ms
- 持续高并发（×24，1小时）下吞吐从 110 FPS 下降到 45 FPS

### Gap-3：User Code 初始化延迟
容器就绪后，用户代码的加载和初始化本身也是重大瓶颈：JIT 编译、语言运行时初始化、依赖库加载（如 Spring、AngularJS），往往超过函数执行时间本身。例如一个 Node.js 函数 275ms 的"用户代码执行阶段"中有 238.73ms 用于加载依赖。超过 50% 的函数冷启动概率超过 0.75，问题无法靠缓存策略覆盖。

---

## 三、核心设计

AFaaS 提出三个针对性的系统设计：

### 3.1 FRI（Function Runtime Interface）— 缩短 Control Path

OCI 规范为通用长生命周期容器设计，其 shim+binary call 调用链（containerd → containerd-shim → 加载运行时二进制 → RPC → sandbox）对 serverless 场景冗余严重。

AFaaS 将 control path 的交互分为两类：
- **shim-call**：只是转发调用，无实质工作（如 `fork()`）
- **service-call**：有复杂实际操作（如 `create()`）

针对 shim-call，AFaaS 用**直接函数调用取代二进制加载**：在 containerd 内实现 `containerd-faas-package` 插件，该插件包含 `create()`、`fork()`、`activate()` 三个接口。低级运行时作为 plugin 被高级运行时直接调用（via RPC），彻底消除每次调用时重新加载运行时二进制（18ms）的开销。root seed 只需 `create()` 一次，之后所有 `fork()` 和 `activate()` 均走更短路径。

### 3.2 资源池化与共享 — 消除竞争延迟

**资源池化**（针对可预分配资源）：
- **veth pool**：预分配足量虚拟以太网设备对，动态分配并在容器退出后回收，消除创建 veth 的高竞争开销
- **cgroup pool**：复用 cgroup 而非每次创建/销毁，减少并发冲突

**资源共享**（针对可继承资源）：
- **Namespace 共享**：seed 和 fork 出的实例共享同一 network 和 IPC namespace（guest OS 内隔离，host 层安全），彻底消除 `clone()` 时的 namespace 创建竞争
- **Seccomp 预编译**：在 seed 准备阶段完成 seccomp 规则的解析和编译，fork 新实例时只需简单的安装步骤
- **网络栈分层共享**：将网络协议栈拆分为可共享部分（clock、random seed、协议处理器、TCP/UDP 控制块、ARP 表）和不可共享部分（IP/MAC 地址、backend device），前者在 seed 阶段预初始化复用，后者在 fork 后独立配置

### 3.3 Tree-structured Seeds 与多级 Fork — 覆盖用户代码初始化

AFaaS 将 seed（sandbox 模板，预初始化状态的快照）扩展到用户代码层，组织为三层树形结构：

| 层级 | 内容 | 说明 |
|------|------|------|
| Level-0（root seed） | guest OS 状态 | 每个计算节点唯一一个 |
| Level-1（language seed） | 语言运行时（Node.js、Python 等）| 从 level-0 fork |
| Level-2（user-code seed） | 框架初始化、依赖导入、JIT 编译结果 | 从 level-1 fork |

子 seed 通过 **CoW（Copy-on-Write）** 机制从父 seed 创建，共享物理内存页，内存开销受控。

**多级 Fork 策略**：当请求到来时，高级运行时在 seed 树中搜索最合适的 seed：
- 有 user-code seed → 从 level-2 直接 fork（接近零初始化）
- 无 user-code seed → 从 level-1（language seed）fork
- 降级处理 → 从 level-0（root seed）fork

这是"best-effort"策略，确保任何函数都有可用的 seed，避免从零冷启动。

---

## 四、实现细节

- **基础**：在 Catalyzer（ASPLOS'20）之上构建，Catalyzer 提供了 sfork（sandbox fork）的基础能力和 gVisor 安全容器支持
- **Container Early Destroy**：serverless 函数通过统一 handler 执行，handler 返回即视为完成，AFaaS 随即暂停 guest OS、断开 TCP 连接、回收资源，彻底消除 JVM shutdown 等带来的 10+ 秒关闭延迟
- **EPT Prefill**：解决 fork 后 EPT（Extended Page Table）page table 未初始化导致的 VM-exit 开销——fork 时将 seed 的 EPT page table 复制给新实例，最后一级目录标记为 read-only，防止读操作触发 EPT violation
- **插件架构**：`containerd-faas-package` 作为 containerd 插件实现，提供 `create()`、`fork()`、`activate()` 三个核心接口
- **代码规模**：基于 Catalyzer，针对以上三个 gap 做增量实现
- **生产部署**：已在 Ant Group 生产环境稳定运行 18+ 个月；traces 公开于 https://github.com/antgroup/AFaaS

---

## 五、实验结果

**实验平台**：x86-64，24 核 Intel Xeon Platinum 8163 @ 2.50GHz，512GB RAM，Linux 5.10

**基线系统**：Kata Containers、gVisor、CataOnly（Catalyzer 基础增强版）、CataOPT1（+Gap-2 优化）、CataOPT2（+Gap-1 优化）

### 端到端延迟（顺序模式）

| 函数类型 | AFaaS vs CataOnly 平均延迟 | AFaaS vs CataOnly P99 延迟 |
|----------|--------------------------|--------------------------|
| 短初始化短执行（EH, HL, HM, JS） | 3.76×–6.68× 加速 | 6.31×–11.74× 加速 |
| 长初始化短执行（AES, DH, PR, GP, CH, IR） | 4.09×–31.48× 加速 | 6.19×–34.51× 加速 |
| 长执行函数（IP, VP） | 1.05×–1.14× 加速 | 1.07×–1.15× 加速 |

### 高并发稳定性（JS 函数，×24 并发）

| 系统 | Cold Start 延迟范围 |
|------|-------------------|
| AFaaS | 6.97ms–14.55ms |
| CataOnly | 38.39ms–74.05ms |
| CataOPT1/OPT2 | 介于两者之间 |
| Kata / gVisor | 数量级劣化，不可用 |

CataOnly 在 1 小时持续高并发下吞吐从 110 FPS 降至 45 FPS；AFaaS 保持稳定。

### 生产环境（8 个代表性 Node.js 函数）

- 端到端加速：**1.80×–8.14×**（相比 CataOnly）
- AFaaS 稳定启动时间：**5.45ms–9.41ms**

### 内存消耗

- 同等用户代码的 seeds，AFaaS vs CataOnly 内存节省 **28.11%–84.91%**
- Level-2 seed 典型内存：6.90MB（compile）~ 135.03MB（cc）
- Level-1（Node.js）seed：54.01MB；Level-0（root）：14.31MB

---

## 六、批判性分析

**实验设计的主要局限：**

1. **单机评测，规模受限**：所有微基准实验均在单台 24 核机器上完成。生产中 Ant Group 有数万 function 和数亿次调用/天，单机实验无法真正验证大规模调度带来的跨节点 seed 管理、负载均衡与 seed 预热的协调复杂性。

2. **"稳定 18+ 个月"缺乏量化**：论文以"生产稳定运行 18+ 个月"作为关键论据，但在 §6.6 仅展示了 8 个 Node.js 函数的产线结果，缺少系统级别的 SLO 达成率、P999 延迟分布、故障统计等量化数据。"稳定"这个结论缺乏充分数字支撑。

3. **用户代码 seed 的覆盖率未说明**：论文称"频繁调用的函数会有 level-2 seed"，但生产中有超 5 万个函数，实际上有多少百分比的冷启动能命中 level-2 seed？命中 level-1 的比例？完全 fallback 到 level-0 的比例？这些数字对评估 §4.3 设计的实际价值至关重要，论文没有给出。

4. **FRI 的可移植性夸大**：论文声称"FRI 设计具有广泛适用性"，但实际上 FRI 是深度定制的 containerd plugin，与 Catalyzer/gVisor 强耦合，根本不能开箱即用地迁移到 AWS Firecracker 或其他平台。"Google/AWS/Alibaba 可以从中受益"这一表述明显过于乐观。

5. **Seccomp 共享的安全论证不充分**：§7 对 seccomp 预编译的安全分析较薄，仅说"规则固定"，但未讨论如果不同 tenant 的函数需要不同 seccomp 规则时如何处理，或者预编译规则被攻击修改的威胁面。

6. **§8 提到的已知问题被轻描淡写**：如 bpf_jit_limit 泄漏导致 seccomp 安装失败、seed fork 串行化成为瓶颈、超高并发下仍有 cgroup lock 竞争，这些问题在正文中被放到"经验教训"章节一笔带过，但其对生产可用性的影响未充分量化。

7. **前后矛盾**：引言称"超过 50% 的函数冷启动概率超过 0.75"，但 §8 又说"95% 的请求通过热启动服务"。这两个数字并不矛盾（少量高频函数贡献大部分流量），但论文没有清晰解释，造成对冷启动影响程度的困惑。

---

## 七、总结

AFaaS 是 Ant Group 历时多年在生产 serverless 平台上构建并验证的端到端冷启动优化系统，核心贡献在于识别并填补了学术研究长期忽视的三个工业差距：control path 开销、高并发资源竞争、用户代码初始化。通过 FRI（替代 OCI control path）、资源池化与共享（消除 kernel lock 竞争）、tree-structured seeds 与多级 fork（覆盖用户代码初始化），AFaaS 在生产中将冷启动延迟降至 5-15ms 量级，相比 Catalyzer 提升 1.8×–8×。

主要局限：实验规模单一、生产数据不够充分、FRI 强依赖 Catalyzer 生态难以直接迁移。适合对 serverless 冷启动做全栈优化的工程团队参考，对研究者提供了大量来自真实工业环境的观察和教训。
