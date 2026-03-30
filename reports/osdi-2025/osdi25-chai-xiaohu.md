# AFaaS: Fork in the Road — Reflections and Optimizations for Cold Start Latency in Production Serverless Systems

## 论文基本信息

- **标题**: Fork in the Road: Reflections and Optimizations for Cold Start Latency in Production Serverless Systems
- **作者**: Xiaohu Chai, Tianyu Zhou, Keyang Hu, Jianfeng Tan 等（清华大学 + 蚂蚁集团 + 上海交通大学）
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/chai-xiaohu
- **开源**: https://github.com/antgroup/AFaaS

---

## 研究背景与动机

### 无服务器计算的现状

Serverless/FaaS（Function as a Service）已在大规模云环境广泛采用（AWS Lambda、Azure Functions、Google Cloud Functions、阿里云 SAE 等）。然而，冷启动延迟（cold start latency）始终是关键性能瓶颈：请求到达时若无预热实例，需初始化新实例，通常耗时超过 1 秒。考虑到 serverless 函数执行时间往往只有 50-100ms，冷启动开销成为显著瓶颈。

### 蚂蚁集团的生产环境

蚂蚁集团公开云上有超过 50,000 个独特函数，日均约 1 亿次调用。使用基于微 VM 的安全容器。观察发现：
- 超过 50% 的函数冷启动概率超过 0.75
- 热启动（hot start）的缓存策略（1分钟超时）不足以覆盖不频繁调用的函数
- 用户代码执行时间分布：超过 80% 的请求在 221ms 内完成

### 现有方案的不足

1. **Catalyzer 等 fork-based 优化**：已在最优条件下实现 <1ms 的 sandbox fork，但忽略了端到端冷启动中的关键步骤
2. **控制路径开销被忽视**：高/低层运行时之间的交互引入 18-25ms 延迟，占总冷启动时间的 30-40%
3. **资源竞争**：高并发和持续执行下性能严重不稳定（吞吐量从 110 FPS 降至 45 FPS）
4. **用户代码初始化**：JIT 编译、框架加载等可超过 275ms

---

## 要解决的核心问题

如何将生产环境 serverless 系统的端到端冷启动延迟降低到毫秒级，同时在高并发和持续执行下保持稳定性能？

---

## 主要贡献

1. **生产环境冷启动的深度分析**：揭示三个被现有研究忽视的延迟来源：控制路径延迟、资源竞争延迟、用户代码初始化延迟
2. **FRI（Function Runtime Interface）**：专门为 serverless 场景设计的精简控制路径接口，替代 OCI 规范
3. **资源池化策略**：cgroup 池化、veth 共享（独立 veth pair）、seccomp 预编译
4. **树形 seed 结构**：通过 CoW 高效创建子 seed，减少内存占用的同时保持快速启动
5. **生产部署验证**：超过 18 个月的生产运行，在各种负载条件下交付 5.45ms-14.55ms 的稳定启动延迟

---

## 研究方法与设计

### 端到端冷启动的三个阶段

**阶段 1：控制路径交互（Control-path Interaction）**
- 高层运行时（containerd）通过 RPC 与低层运行时（Catalyzer）通信
- Shim 进程加载 Catalyzer runtime engine（二进制调用），每次调用耗时 18.02ms
- 三层调用链：containerd → shim → engine

**阶段 2：容器初始化（Container Initialization）**
- Sandbox fork：clone() 创建新网络和 IPC namespace（高并发下从 1.45ms 恶化到 418ms）
- Runtime 恢复：forked sandbox 初始化 Go runtime
- 日志重定向、控制服务器重建、VMX 模式切换、内核 unpause
- 网络准备：解析 config.json、setns()、创建 raw socket（高并发下从 2ms 升至 21.14ms）
- Seccomp 安装：解析、编译、安装 seccomp filter（高并发下从 7.58ms 升至 13.01ms）
- Cgroup 激活、rootfs 挂载

**阶段 3：用户代码执行（User Code Execution）**
- 语言运行时加载（Node.js、Python、Java 等）
- 代码框架初始化（Spring、Django 等）
- JIT 编译和依赖库加载
- Node.js 函数示例：275.53ms 中 238.73ms 用于依赖加载

### FRI：Function Runtime Interface

**核心洞察**：当前基于 OCI 的 shim+engine 架构对于 serverless 场景过于冗长。FRI 简化控制路径，让高层运行时直接与低层运行时通信。

**设计**：
- 新增 `create()` 调用替换原有的三层 RPC 链
- 复用已建立的通信通道，避免每次调用的二进制加载
- 将部分操作（网络配置、seccomp 规则）提前到 seed 创建时执行一次

### 资源池化策略

#### Clone 优化（cgroup/veth 池化）

**问题**：高并发下 clone() 创建新网络和 IPC namespace 导致严重竞争：
- 网络 namespace 创建：涉及 VFS 操作和 superblock 分配，高并发下锁竞争激烈
- IPC namespace：POSIX 消息队列依赖，每个 namespace 需要独立 superblock，导致 sb_lock 和 mount_lock 竞争

**解决方案**：
- **cgroup 池化**：为每个实例预分配和回收 cgroup，而非每次创建/销毁
- **独立 veth pair 共享**：预创建的独立 veth pair 可被安全复用，避免安全风险；每个 fork 初始化干净的 TCP/IP 栈，消除安全风险

#### Seccomp 预编译

**问题**：每次冷启动都需解析 seccomp 配置、编译规则、安装 filter，高并发下严重竞争。

**解决方案**：seccomp 规则在 seed 准备阶段预编译并缓存。seed fork 时直接应用已编译规则。

#### 网络栈预初始化（EPT Prefill）

**问题**：Sandbox 使用 raw socket fd 初始化容器网络栈涉及创建协议栈 ring buffer、复杂数据结构初始化，大量内存访问和 VM exit。

**解决方案**：在 seed 中预初始化网络栈，fork 时继承已初始化的栈状态。

### 树形 Seed 结构

**背景**：用户代码初始化（框架加载、JIT 等）是冷启动中耗时最长的部分。Catalyzer 的 seed 可以包含用户代码，但支持多进程运行时（Java、Node.js）时效率低下。

**解决方案**：采用树形结构管理 seed，Copy-on-Write（CoW）高效创建子节点，减少内存占用同时保持快速启动性能。

---

## 关键实现细节

- **AFaaS**：基于 AntGroup 内部 serverless 平台修改，新增约 5,000 行代码
- **Seed 树**：层级管理，CoW 减少内存开销
- **FRI 实现**：替换原有的 OCI shim-engine 架构
- **性能隔离**：cgroup 池化和 veth pair 共享确保安全隔离
- **开源地址**：https://github.com/antgroup/AFaaS

---

## 实验结果与分析

### 实验配置

- 测试函数：Node.js 函数（nunjucks 模板渲染）
- 对比基线：Catalyzer（业界最先进的 fork-based 冷启动优化）
- 测试环境：AntGroup 内部生产环境

### 端到端延迟

- **最优场景**：AFaaS 端到端延迟 5.45ms-9.41ms，相比 Catalyzer 提升 1.80×-8.14×
- **高负载（×24并发）**：AFaaS 保持 6.97ms-14.55ms，Catalyzer 恶化至 38.39ms-74.05ms
- **持续执行（1小时高并发）**：AFaaS 吞吐量稳定，Catalyzer 从 110 FPS 降至 45 FPS

### 各阶段优化效果

- **控制路径**：FRI 消除了 18ms 二进制加载开销
- **网络准备**：veth 共享从 21.14ms 降至 2ms 左右
- **Seccomp**：预编译从 13.01ms 降至 <1ms
- **Clone**：cgroup 池化大幅减少 namespace 创建延迟
- **用户代码**：树形 seed 减少框架加载时间

### 生产部署

- 已运行超过 18 个月
- 在各种负载条件下持续稳定
- 全面生产化部署（而非仅实验室验证）

---

## 潜在问题与局限性

1. **特定于安全容器的设计**：AFaaS 针对基于微 VM 的安全容器设计，结论可能不完全适用于传统 runc 容器
2. **平台锁定**：基于 AntGroup 内部基础设施，与开源生态（如 containerd 生态）的集成有限
3. **树形 Seed 的开销**：CoW 和树形管理引入额外复杂性，生产维护成本需评估
4. **用户代码初始化的固有限制**：Seed 预热策略需要预先知道哪些函数会被频繁调用，对完全未知的工作负载效果有限
5. **评估规模**：虽然有 18 个月生产运行的数据，但论文未提供具体的函数数量级、峰值 QPS 等量化指标

---

## 未来工作方向

- 进一步优化用户代码初始化阶段（可能结合更好的 Seed 预热策略）
- 与 Kubernetes 等开源生态集成
- 自适应资源池化（根据实时负载动态调整池大小）
- 探索在 ARM 架构上的性能优化

---

## 个人评注

### 优势

1. **生产经验驱动的洞察**：18 个月 + 50K 函数 + 日均 1 亿调用的生产环境，提供的数据和洞见远超学术仿真
2. **三个 Gap 的发现意义深远**：控制路径延迟（被忽视的 18ms）、资源竞争延迟（×24 并发下从 1.45ms 到 418ms）、用户代码初始化（275ms 中的 238ms）——这些在学术论文中很少被系统研究
3. **端到端视角**：不是孤立优化单个组件，而是覆盖完整冷启动链路，对用户更有实际价值
4. **工程完整性**：超过 18 个月的生产部署证明了方案的实用性和稳定性

### 潜在争议

1. **"毫秒级冷启动"的条件**：5.45ms-9.41ms 是最优场景的结果，高并发下为 6.97ms-14.55ms。"毫秒级"是真实的，但不同场景差异较大
2. **Seed 预热的工程复杂度**：树形 seed 结构、CoW 优化等方案引入了较高的实现和维护复杂度，small team 可能难以采用
3. **与 Knative 等开源方案的对比缺失**：论文主要对比 Catalyzer，但 Knative、OpenWhisk 等开源方案的处理方式未提及，难以评估 AFaaS 在更广泛生态中的优势
4. **开源的实际可用性**：GitHub 仓库是否包含完整生产代码、文档和测试？仅有代码可能不足以让其他团队复现结果
