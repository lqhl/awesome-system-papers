# Fork in the Road: Reflections and Optimizations for Cold Start Latency in Production Serverless Systems

**作者**：Xiaohu Chai (Tsinghua University, Ant Group), Tianyu Zhou (Ant Group), Keyang Hu (Tsinghua University), Jianfeng Tan, Tiwei Bie, Anqi Shen, Dawei Shen, Qi Xing, Shun Song, Tongkai Yang, Le Gao, Feng Yu, Zhengyu He (Ant Group), Dong Du, Yubin Xia (Shanghai Jiao Tong University), Kang Chen (Tsinghua University), Yu Chen (Quan Cheng Laboratory, Tsinghua University)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/chai-xiaohu
**源文件**：[osdi25-chai-xiaohu.pdf](../../papers/osdi-2025/osdi25-chai-xiaohu.pdf)

---

## 一、背景

Serverless 计算已被 AWS Lambda、Azure Functions、Google Cloud 等主流云厂商广泛采用。然而，冷启动延迟一直是 serverless 平台的核心性能瓶颈——当没有预热实例可用时，平台需要从头初始化一个新实例来运行函数，通常耗时超过 1 秒，而 serverless 函数的执行时间往往仅为 50–100ms。

蚂蚁集团的 FaaS 平台运行超过 50,000 个独立函数，日调用量约 1 亿次。在生产环境中，超过 50% 的函数冷启动概率超过 0.75，超过 35% 的函数冷启动概率为 1。现有的基于缓存的热启动策略（将空闲实例保留 1 分钟）只能覆盖高频函数，对大量低频函数无效。此前蚂蚁集团基于 Catalyzer 的 sandbox fork 机制已将容器初始化优化到亚毫秒级别，但端到端冷启动延迟仍在数百毫秒到数秒级别。

---

## 二、要解决的问题

论文识别出现有冷启动优化方案的三个关键盲区（Gap）：

1. **控制路径延迟（Gap-1）**：高层运行时（containerd）和低层运行时（Catalyzer）之间遵循 OCI 规范的交互链路过长。每次函数调用都需要加载 Catalyzer runtime binary（18ms），再通过 RPC 触发 fork，即使 sandbox fork 本身不到 1ms，控制路径仍占端到端延迟的 30%–40%。

2. **资源竞争延迟（Gap-2）**：在高并发场景下，容器冷启动各阶段出现严重性能抖动。clone() 系统调用创建 network/IPC namespace 时竞争宿主内核全局锁，延迟从 1.45ms 恶化到 418ms；网络准备阶段从 2ms 退化到 21ms；seccomp 规则编译安装从 7.58ms 飙升到 13ms。持续执行下吞吐量从 110 FPS 衰退到 45 FPS。

3. **用户代码初始化延迟（Gap-3）**：函数实例就绪后，还需加载语言运行时（Node.js/Python/JVM）、JIT 编译、框架初始化（如 Spring XML 解析）和依赖库加载。例如一个 Node.js 函数 275ms 的用户代码执行时间中有 238ms 花在依赖加载上。现有方案（provisioning、SnapStart）难以在成本和效率间取得平衡。

---

## 三、洞察与设计

**关键洞察**：端到端冷启动延迟的瓶颈已从容器初始化本身转移到了三个被忽视的环节——控制路径交互、宿主内核资源竞争、用户代码初始化——它们各自可通过"精简接口、预分配/共享资源、层次化模板复用"来系统性消除。

基于上述洞察，AFaaS 的核心设计包含三个层面的优化：

### 精简控制路径：FRI（Function Runtime Interface）
分析发现高层和低层运行时之间的交互可分为 shim-call（纯转发）和 service-call（实际操作）。fork() 和 activate() 都是 shim-call，不需要每次加载二进制文件。FRI 用 plugin-based 直接函数调用替代二进制调用——将低层运行时实现为 containerd 的一个 plugin（containerd-faas-package），包含 create()、fork()、activate() 三个方法。create() 仅在创建根 seed 时调用一次，之后 fork/activate 直接通过 RPC 调用 plugin，消除了 18ms 的二进制加载开销。

### 资源池化与共享
- **池化**：veth pair 和 cgroup 预分配到池中，动态分配和回收，避免高并发下的创建竞争
- **共享**：seed 和 function instance 共享 network/IPC namespace（安全的，因为用户代码运行在 guest OS 内的安全容器中）；seccomp 规则在 seed 准备阶段预编译，fork 时只需简单安装；网络协议栈拆分为可共享部分（TCP/IP 栈核心元素）和不可共享部分（IP/MAC 地址），可共享部分在 seed 阶段初始化

### 层次化 Seed 树 + 多级 Fork
函数 seed 组织为三层树结构：
- Level-0（根 seed）：guest OS 状态，每节点唯一
- Level-1（语言 seed）：从根 seed fork，初始化语言运行时（Node.js/Python/JVM）
- Level-2（用户代码 seed）：从语言 seed fork，加载框架、依赖库、JIT 编译用户代码

子 seed 通过 CoW 机制共享父 seed 的物理内存页。当请求到达时，高层运行时在 seed 树中搜索最匹配的 seed：优先使用用户代码 seed，否则回退到语言 seed 或根 seed，实现 best-effort provisioning。

---

## 四、实现细节

AFaaS 基于 Catalyzer 实现，主要增强包括：

- **FRI Plugin**：实现为 containerd-faas-package 插件，通过 RPC 直接与 seed 交互，避免每次调用都 exec 二进制
- **资源池规模**：预分配 1,000 个 veth pair 和 600 个 cgroup，内存开销可忽略不计
- **Container Early Destroy**：函数 handler 返回后立即暂停 guest OS、断开 TCP 连接、回收容器，避免语言运行时关闭和文件系统刷新带来的 10+ 秒延迟
- **EPT Prefill**：fork 时将 seed 的 EPT 页表复制到新实例并标记末级目录为只读，避免内存读操作触发 EPT violation 和 VM-exit
- **唯一性状态处理**：fork 后重新初始化随机数种子、密码学 token 等不可复用的状态（如 gVisor 的随机数生成器需重新 seed）
- **安全模型**：遵循 Catalyzer/Firecracker/gVisor 的威胁模型；veth 回收前优雅终止长连接；cgroup 在函数退出后正确释放；namespace 共享仅在宿主层面，用户代码隔离在 guest OS 内

---

## 五、实验结果

**实验环境**：Intel Xeon Platinum 8163 (24 cores, 2.50GHz)，512GB RAM，Linux 5.10。基线系统包括 Kata (v3.15.0)、gVisor、CataOnly (Catalyzer + 生产增强)、CataOPT1 (+ Gap-2 优化)、CataOPT2 (+ Gap-1 优化)。

| 指标 | CataOnly | AFaaS | 提升 |
|------|----------|-------|------|
| 短函数 (EH/HL/HM/JS) 平均延迟 | 基线 | 3.76×–6.68× | 显著 |
| 短函数 P99 延迟 | 基线 | 6.31×–11.74× | 显著 |
| 长初始化函数 (AES/DH/PR 等) 平均延迟 | 基线 | 4.09×–31.48× | 极显著 |
| 长初始化函数 P99 延迟 | 基线 | 6.19×–34.51× | 极显著 |
| 长执行函数 (IP/VP) 平均延迟 | 基线 | 1.05×–1.14× | 有限 |
| 高并发 (×24) 冷启动时间 | 38.39–74.05ms | 6.97–14.55ms | ~4× |
| 高并发 E2E 延迟范围 | 51.32–117.92ms | 16.34–39.56ms | ~3× |
| 生产函数端到端加速比 | — | 1.80×–8.14× | — |
| 生产环境冷启动时间 | — | 5.45–9.41ms | 毫秒级 |
| Level-2 seed 内存节省 | 基线 | 28.11%–84.91% | — |

**可扩展性**：随并发度从 1 增加到 24，AFaaS 吞吐量持续线性增长且 E2E 延迟增长平缓；CataOnly 很快触及瓶颈并出现吞吐量下降。

**持续执行稳定性**：在 ×24 并发持续 1 小时执行下，AFaaS 吞吐量保持稳定，CataOnly 因 IPC namespace superblock 缓存 miss 和内核锁竞争导致吞吐量从 110 FPS 衰退到 45 FPS。

---

## 六、批判性分析

1. **函数类型覆盖面有限**：论文的评估函数以短函数和中等初始化函数为主。对于执行时间较长的函数（IP、VP），加速仅 1.05×–1.14×，说明 AFaaS 的优化主要针对冷启动占比大的场景。论文声称 95% 的请求是热启动（高频函数），仅 5% 触发冷启动——但这 5% 覆盖了超过 50% 的函数。这意味着 AFaaS 的收益主要体现在函数多样性层面而非请求量层面。

2. **Seed 管理策略的缺失**：论文未详细讨论 level-2 seed 的生命周期管理——哪些函数值得创建专属 seed？seed 何时淘汰？如何应对函数代码更新后 seed 失效？在 50,000+ 函数的规模下，这些决策对内存消耗和维护复杂性影响巨大，但论文仅一笔带过"不支持动态 seed scaling"。

3. **安全分析不够深入**：论文承认 namespace 共享和内存页共享存在信息泄露可能，但辩称"与 Catalyzer/Molecule/MITOSIS 一致"。然而 AFaaS 是多租户生产系统，共享更多资源（网络协议栈、IPC namespace、EPT 页表）带来的攻击面增量值得更严格的分析，而非简单类比。

4. **基线选择偏保守**：论文主要与 Catalyzer 对比，但 Catalyzer 是 2020 年的工作。AWS SnapStart、RainbowCake 等更新方案仅在 Table 1 中做了定性比较，缺少量化数据。特别是 RainbowCake 也采用了类似的层次化设计，直接对比实验数据会更有说服力。

5. **noisy neighbor 问题未量化**：Section 7 提到 seed 准备和资源池初始化可能干扰同节点其他工作负载（veth 池初始化导致 cb_mutex 竞争），但只给出了定性建议（"串行初始化"），没有量化影响程度。

---

## 七、AI Infra / MLSys 视角

1. **对 AI 推理服务冷启动的启发**：AI 推理服务（如 vLLM、TensorRT-LLM）也面临类似的冷启动问题——模型加载（几十 GB 权重）、CUDA context 初始化、KV cache 分配。AFaaS 的层次化 seed 树思路可迁移：level-0 为 CUDA runtime seed，level-1 为模型框架 seed（PyTorch/TensorRT），level-2 为特定模型 seed（含已加载的权重）。CoW 机制对 GPU 显存虽然不直接适用，但可以在 CPU 侧模型权重和 host memory 管理中借鉴。

2. **资源池化对 GPU 集群调度的借鉴**：AFaaS 对 veth/cgroup 的池化策略可迁移到 GPU 资源管理——预分配 CUDA stream、预创建 NCCL communicator 等高开销资源，避免推理请求到达时的初始化延迟。

3. **FRI 思路对 AI serving framework 的启发**：当前 AI serving 框架（Triton、vLLM）也存在类似的"控制路径过长"问题——请求经过 HTTP server → scheduler → model runner → GPU executor 多层传递。FRI 的"识别 shim-call 并消除不必要中间层"的方法论值得借鉴。

4. **可跟进的研究方向**：
   - 将 fork-based 冷启动应用于 serverless AI 推理场景（如 GPU 进程 fork + CUDA context 继承）
   - 探索 EPT Prefill 类似思路在 GPU 页表（如 NVIDIA UVM）上的应用
   - 研究多级 seed 树在 multi-model serving（同一节点服务多个模型）场景下的内存共享优化

---

## 八、总结

AFaaS 是蚂蚁集团部署超过 18 个月的生产级 serverless 冷启动优化系统。它通过三个互补的优化——FRI 精简控制路径、资源池化/共享消除内核竞争、层次化 seed 树复用用户代码初始化状态——将冷启动延迟从数百毫秒降至毫秒级（5.45–9.41ms），在高并发下维持 6.97–14.55ms 的稳定性能。系统适用于短生命周期、高函数多样性的 serverless 场景，对执行时间本身较长的函数收益有限。论文的最大价值在于从工业部署视角系统性地识别和解决了学术界长期忽视的端到端冷启动瓶颈。
