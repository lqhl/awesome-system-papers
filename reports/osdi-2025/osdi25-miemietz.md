# osdi25-miemietz: MettEagle

## 论文基本信息

- **标题**: MettEagle: Costs and Benefits of Implementing Containers on Microkernels
- **作者**: Till Miemietz, Viktor Reusch, Matthias Hille（Barkhausen Institut）；Lars Wrenger（Leibniz-U Hannover）；Jana Eisoldt（Barkhausen Institut）；Jan Klötzke（Kernkonzept）；Max Kurze（TU Dresden）；Adam Lackorzynski（TU Dresden & Kernkonzept）；Michael Roitzsch, Hermann Härtig（Barkhausen Institut & TU Dresden）
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/miemietz

---

## 研究背景与动机

容器是云环境中隔离工作负载的主流方式，但现有容器实现存在根本问题：
- **复杂性**：seccomp-bpf、namespace、cgroups 等机制增加了内核代码复杂性
- **攻击面扩大**：更大的共享内核代码库意味着容器间的隔离更容易被突破

**微内核设计**天然符合最小权限原则（PoLA）——进程默认没有环境权限，需要显式请求资源访问。这使得在微内核上实现容器可能比在宏内核上更简洁。

但有两个关键问题：
1. 微内核概念能否扩展到运行服务器级硬件上的高度动态工作负载（如无服务器计算）？
2. 在微内核上托管容器的**性能影响**是什么？

---

## 要解决的核心问题

1. 在微内核（L4Re）上实现容器级隔离需要什么？
2. 微内核方法在安全性和 TCB 规模上与传统容器相比如何？
3. 在服务器级硬件和动态工作负载下，微内核容器的性能如何？

---

## 主要贡献

1. **容器级隔离的全面分析**：在微内核上实现容器级隔离需要什么（visibility restrictions、resource budgets、接口限制）
2. **MettEagle 设计**：在 L4Re 微内核上构建的容器服务原型
3. **详细安全评估**：CVE 分析显示微内核方法在容器隔离方面有更好的安全态势
4. **全面性能评估**：在 SeBS 无服务器基准测试上与 runC 和 Firecracker 对比
5. **工程洞察**：在 L4Re 上实现高性能微内核服务的关键 lessons learned

---

## 研究方法与设计

### 容器在宏内核上的三大隔离机制

1. **接口限制**：seccomp-bpf 阻止不必要的系统调用
2. **Visibility 限制**：namespace 隐藏资源（如 PID、网络接口）
3. **资源限制**：cgroups 强制 CPU/内存/带宽配额

### 微内核方法

微内核天然提供 **capability-based 访问控制**，进程需要显式 capability 才能访问资源。

- **无环境权限**：这是 PoLA 的核心——进程默认无法访问任何资源
- **Capability 是不可伪造的访问令牌**：授予持有者对特定对象的特定操作权限
- **能力可委托和撤销**：灵活的权限管理

### MettEagle 架构

```
Phlox（FaaS 高级运行时）
       ↓
MettEagle（容器引擎）
       ↓
Compartment Service（隔离机制配置）
       ↓
L4Re 微内核 + 系统服务（FS/网络/内存/ROM）
```

**组件**：
- **Compartment Service**：配置容器的 capability 集（类似 runC）
- **Phlox**：高级 FaaS 运行时，支持远程代码执行
- **SPAFS**：支持写入的内存文件系统
- **LUNA**：网络服务，多路复用 NIC
- **LSMM/PROMFS**：并行化的内存管理和 ROM 文件系统

### MettEagle 中的隔离机制

1. **Visibility 限制**：
   - Capability 决定哪些资源对 compartment 可见
   - L4Re 的 namespace 提供能力到名称的映射（类似 Linux namespace）
   - 无全局 PID 或共享内存 key

2. **接口限制**：
   - 不需要 seccomp-bpf——服务通过 IPC gate 限制可用 API
   - 控制平面（创建会话）和数据平面（发送/接收）操作通过不同 gate

3. **资源配额**：
   - 基于 L4Re 的 quota 机制
   - 通过每个会话的 resource consumption context 实现
   - 无统一的 cgroups——但 compartment 引擎透明地翻译为服务特定会话请求

### 关键工程 Lessons Learned

1. **回调和资源池**：L4Re 的单一回复 capability 策略限制性能——服务器线程一次只能服务一个客户端。使用回调机制和线程池避免重复创建/删除开销。

2. **资源释放在关键路径**：unmap（capability 撤销）操作可能阻塞整个调度周期（10ms）。解决方案：在非关键路径执行删除操作，复用系统资源避免释放。

3. **capability 数据结构的锁定**：map/unmap 操作中的锁定瓶颈。优化：从源任务解锁（已在内核中持有关键字）。

---

## 安全评估

### TCB 规模对比

| 系统 | SLOC（总计） |
|------|------|
| L4Re 内核 + sigma0 + moe + ned + IO + LSMM + PROMFS + SPAFS + LUNA + MettEagle | 89,271 |
| Linux 内核 + NIC 驱动 + containerd + runC | 2,699,812 |

**宏内核方法代码量是微内核方法的 30 倍**。

### CVE 分析

搜索 NIST 数据库中的容器隔离相关漏洞（关键词：seccomp/bpf/namespace/cgroups）：
- 33 个相关漏洞，CVSS 7.0+
- **微内核方法从根本上减少了相关 CVE 的暴露面**

---

## 性能评估

### 微基准测试（计算、内存、网络）

- **计算**：与 runC 性能相当（~100%）
- **内存**：略低于 runC（~90-95%）
- **网络**：MettEagle **优于** runC（启动延迟更低，网络性能相当或更好）

### SeBS 无服务器基准测试

MettEagle 在大多数函数上**与 runC 性能相当**：
- CPU 密集型：与 runC 持平
- 内存密集型：略低 5-10%
- **冷启动延迟**：MettEagle **更快**（无需特权操作）

### Firecracker 对比

- MettEagle vs Firecracker：取决于工作负载
- Firecracker 启动时间更长但隔离更强

---

## 潜在问题与局限性

1. **功能完整性**：微内核方法需要重新实现所有必要的系统服务（文件系统、网络栈等），工程量大。L4Re 的服务生态系统不如 Linux 丰富。
2. **与现有容器生态的兼容性**：OCI 标准在微内核上的实现需要额外工作
3. **动态工作负载支持**：虽然论文声称支持，但评估主要在相对静态的基准测试上
4. **多租户安全**：capability 管理的复杂性可能导致配置错误
5. **与 Firecracker 的公平性**：Firecracker 是全 VM 隔离，提供了比容器的更强隔离。MettEagle 的对比应该在相同隔离保证下进行。

---

## 个人评注

**优点**：
- 这是一个概念上令人信服的研究：微内核天然符合最小权限原则，在宏内核上用 seccomp-bpf 等 hack 模拟这一原则是"打补丁而非设计"
- 详细的 CVE 分析提供了可量化的安全改进证据（30 倍代码量差距）
- SeBS 基准测试提供了实用的性能数据，证明微内核方法在真实工作负载下的可行性
- 工程 lessons learned（回调机制、RCU 优化、capability 锁定）对未来在微内核上构建系统的人非常有价值

**值得关注的点**：

1. **"容器在微内核上天然更安全"的论点需要条件**：论文论证微内核因为没有环境权限所以不需要额外的隔离机制。但这忽略了微内核上**系统服务的可信性**。如果文件系统服务本身有漏洞，持有该服务 capability 的容器仍然可能利用漏洞。TCB 包括了所有系统服务（89,271 SLOC），这些服务也需要正确性保证。

2. **30 倍代码量的差距需要澄清**：Linux 内核包含了大量与容器隔离无关的功能（文件系统、驱动程序、网络协议栈等）。更公平的比较应该只计算与容器隔离直接相关的内核子系统。

3. **与 Firecracker 的对比存在根本性差异**：Firecracker 是 microVM，提供比容器更强的隔离（完全独立的内核实例）。MettEagle 提供的是容器级隔离。将两者直接对比有点像比较苹果和橘子——它们有不同的威胁模型。

4. **L4Re 服务实现的完整性**：论文承认需要重新实现 SPAFS、LUNA、LSMM 等服务。这些服务的正确性和性能尚未达到生产级别。

5. **可扩展性未充分验证**：虽然论文声称支持"高度动态工作负载"，但评估主要在少量函数和相对简单的场景下。没有关于大规模多租户场景（如实际无服务器平台）的性能数据。

6. **Python 移植的复杂性**：Porting Python 3 到 L4Re 是一个重要的工程工作，但论文未详细说明这花了多少时间，以及维护这个移植版本的长期成本。

7. **研究机构的协作性质**：多个机构（Barkhausen Institut、TU Dresden、Kernkonzept）参与开发——这是学术/行业合作。这可能解释了为什么有足够的工程资源来实现完整的系统，但也意味着该系统可能难以由单个团队维护。
