# Extending Applications Safely and Efficiently

**作者**：Yusheng Zheng (UC Santa Cruz), Tong Yu (eunomia-bpf Community), Yiwei Yang (UC Santa Cruz), Yanpeng Hu (ShanghaiTech University), Xiaozheng Lai (South China University of Technology), Dan Williams (Virginia Tech), Andi Quinn (UC Santa Cruz)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/zheng-yusheng
**源文件**：[[osdi25-zheng-yusheng.pdf]]

---

## 一、背景

软件扩展（Software Extension）是定制和增强应用行为的核心机制，广泛应用于 Web 服务器（Nginx）、数据库（Redis、MySQL）、浏览器等场景。扩展允许在不修改源代码的前提下添加监控、安全防护、性能优化等功能，便于部署维护和上游更新集成。

然而，扩展框架需要在三个关键属性之间取得平衡：**安全性**（safety，防止有 bug 的扩展损害宿主应用）、**隔离性**（isolation，防止被攻破的宿主应用篡改扩展状态）、**高效性**（efficiency，接近原生执行速度）。现有框架在这三者间的平衡表现不佳——有的牺牲安全性换取效率（如 LD_PRELOAD、动态二进制插桩），有的用重量级隔离换取安全但开销巨大（如 SFI、子进程隔离），且大多缺乏细粒度的安全/互联性权衡能力。历史上，扩展 bug 已导致 Bilibili 生产事故（Nginx 扩展死锁）、Apache httpd 崩溃（CVE-2021-44790）、Redis 远程代码执行（CVE-2024-31449）等严重后果。

---

## 二、要解决的问题

1. **缺乏细粒度的安全/互联性权衡**：现有框架要么完全不支持配置扩展权限（如 Lua、WebAssembly、NaCl），要么只能以粗粒度限制扩展行为（如 RLBox、lwC），无法按扩展入口点（extension entry）级别定制不同的安全策略。例如 Nginx 的监控扩展只需读取状态，而防火墙扩展需要读写不同状态——现有框架无法表达这种差异。

2. **隔离机制开销过大**：子进程隔离（Orbit、lwC、Wedge）需要上下文切换级别的开销；SFI（WebAssembly、NaCl）的运行时检查导致显著性能下降（相比原生执行慢很多）。

3. **eBPF uprobe 用户态扩展效率低**：eBPF 的 uprobe 机制在每个扩展入口放置软件断点，需要 trap 进内核执行扩展，开销很大；且是系统级的（影响所有进程），无法做到只对目标进程生效。

4. **现有框架难以在不修改宿主源码的前提下支持扩展**：Orbit、Wedge 等系统虽然支持细粒度权限，但要求修改宿主应用源码，不是为扩展性设计的。

---

## 三、洞察与设计

**关键洞察**：扩展所需的每个功能特性（读取宿主变量、调用宿主函数、使用内存等）都可以被统一抽象为「资源」（resource），并通过 capability 模型来控制访问权限。将安全性约束和互联性需求都表示为 capability 的授予与限制，就能在同一框架下实现任意细粒度的安全/互联性权衡——而且这种规范（specification）可以与具体运行时实现解耦。

基于这一洞察，论文提出了两个贡献：

### Extension Interface Model (EIM)

EIM 是一个两阶段的接口规范模型：
- **开发时规范**（Development-time）：由应用开发者编写，定义宿主应用能提供的所有 capability（State Capability 读写宿主变量、Function Capability 调用宿主函数及其约束、Extension Entry 扩展入口点）。
- **部署时规范**（Deployment-time）：由扩展管理者编写，为每个扩展入口创建 Extension Class，指定该入口允许使用的 capability 子集，从而实现最小权限原则。

### bpftime 运行时系统

bpftime 是高效执行 EIM 规范的扩展运行时，核心设计包括：
- **分离式轻量级安全与隔离**：用 eBPF 风格的静态验证实现 EIM 安全约束（零运行时开销），用 ERIM 风格的 Intel MPK 硬件内存保护实现进程内隔离（极低开销）。
- **Concealed Extension Entries**：通过二进制重写（Frida + libcapstone）在运行时注入扩展入口，未使用的扩展入口零开销——从编译后的程序中移除所有扩展入口调用，只在加载扩展时才通过 trampoline 注入。
- **eBPF 生态兼容性**：不重新实现 eBPF 技术栈，而是在 eBPF 系统调用层做 interposition，复用现有编译器（clang/bcc）、运行时库（libbpf）和工具链。

---

## 四、实现细节

bpftime 以约 13,000 行代码实现，开源于 GitHub（1,000+ stars，20+ 贡献者）。

**Loader 加载器**：
- **验证器**：接收 eBPF 字节码扩展，解析宿主应用 DWARF 调试信息生成 BTF 类型信息，将 EIM 规范中的 capability 约束转换为 eBPF 字节码中的断言和类型约束，复用 Linux 内核 eBPF verifier 进行验证。对于自定义资源约束，回退到 PREVAIL 验证器。
- **二进制重写器**：用 ptrace 暂停宿主进程，注入 bpftime 运行时。对于 uprobe/uretprobe 使用标准 instruction trampoline（替换目标指令为跳转调用）；对于 syscall tracepoint 遍历所有 sysenter 指令，使用 zpoline 技术（利用零页容纳两字节 call 指令）。

**Runtime 运行时**：
- **进程内隔离**：扩展代码页设为不可写；扩展内存通过 Intel MPK 保护——为扩展分配独立的 memory protection key，在进入扩展前用 WRPKRU 解锁，退出时重置。扩展自身的 key 值直接编码在扩展代码中，且扩展内存设为不可读（从宿主侧）。
- **bpftime Maps**：兼容 eBPF maps 接口但无需系统调用，支持三种共享模式（进程局部、跨进程、进程-内核共享），提供 hash map、array、LPM trie、ring buffer、perf event array 等数据结构，支持 per-CPU 变体和无锁同步。

**EIM 注解支持**：应用开发者通过基于 eBPF kfunc 的代码注解定义 capability，bpftime 编译工具从注解和调试符号中自动提取 development-time EIM 规范。同时自动生成 uprobe/uretprobe/sysenter/sysexit 入口和常用 helper function capability。

---

## 五、实验结果

实验平台：
- Server A：双路 Intel Xeon Gold 5418Y（24 核 2.00GHz），256GB DDR5
- Server B：双路 Intel Xeon E5-2697-v2（48 核 2.7GHz），256GB DDR3

| 用例 | 主要结果 |
|------|---------|
| **Nginx 插件** | bpftime 仅 2% 开销（4461 RPS vs 原生 4536 RPS）；Lua 11%、WebAssembly 12%、ERIM 11%、RLBox 9%——bpftime 比它们低 4.5×–6× |
| **DeepFlow 微服务监控** | eBPF DeepFlow 导致吞吐量下降最高 54%；bpftime 改进 DeepFlow 吞吐量至少 1.5× |
| **Redis 持久化调优** | Batch-48 模式比 alwayson 吞吐量提升 4.17×，最多丢失 24 条更新（vs everysec 可丢 72,000 条）；delayed-fsync + fast-notify 达 65K req/s，仅比 everysec 低 10%，但数据丢失降低 5 个数量级 |
| **FUSE 缓存** | bpftime 缓存加速 FUSE 操作最高达 2.4 个数量级（fstat 3.65s → 0.176s） |
| **sslsniff SSL 流量监控** | eBPF 降低 Nginx 吞吐量最高 28%；bpftime 仅降低 7.4%，改进 3.79× |
| **Syscount 系统调用统计** | eBPF syscount 影响所有进程（降低 ~10%）；bpftime 仅影响目标进程（降低 3.36%），非目标进程零影响 |

**微基准测试**：

| 操作 | eBPF (ns) | bpftime (ns) | 加速比 |
|------|-----------|-------------|--------|
| Uprobe | 2561 | 190 | 13.5× |
| Uretprobe | 3019 | 187 | 16.1× |
| Syscall Tracepoint | 151 | 232 | 0.65× (bpftime 较慢) |
| 用户态内存读 | 23.3 | 1.5 | 15.5× |
| 用户态内存写 | 23.9 | 1.4 | 17.1× |

bpftime 的 JIT 执行引擎比 ubpf 和 rbpf 分别快 1.53× 和 1.72×。扩展加载延迟 48ms（vs LD_PRELOAD 30ms）。eBPF 兼容性测试中 bpftime 仅 1 个失败（ubpf 22 个、rbpf 23 个）。

---

## 六、批判性分析

1. **Syscall tracepoint 性能反而不如 eBPF**：微基准显示 bpftime 的 syscall tracepoint 延迟为 232ns，而 eBPF 仅 151ns（bpftime 慢 1.5×）。论文在正文中没有深入讨论这一劣势的根因（zpoline 的间接跳转开销？），也没有分析在 syscall-heavy 的场景下端到端性能会受多大影响。

2. **安全模型假设较强**：威胁模型假设扩展管理者是「trusted and infallible」——即管理者能准确无误地为每个扩展入口配置正确的 capability。这在实际大规模部署中是不现实的，EIM 规范的编写和维护本身就可能成为安全隐患的来源。论文未讨论 EIM 规范本身出错时的后果。

3. **Intel MPK 的已知攻击未完全解决**：论文承认 bpftime 目前容易受到 ERIM 的 syscall-based 攻击（恶意代码通过 syscall 直接修改 PKRU 寄存器绕过保护），仅提到「可以采用 Jenny 的 syscall filtering」来解决，但未实现。这意味着当前系统的隔离保证在面对恶意扩展时是不完整的。

4. **仅支持 Intel x86**：硬件隔离依赖 Intel MPK，当前实现不支持 ARM。论文提到 ARM 有类似技术但未实现。在 ARM 服务器日益普及的今天（AWS Graviton、Ampere），这限制了实际部署范围。

5. **每个入口点仅支持一个扩展**：当前实现限制每个 extension entry 只能绑定一个扩展，需要用 dispatcher pattern 来支持多个扩展。这在实际场景中（同一函数入口需要同时运行监控、安全、定制化扩展）会增加额外的工程复杂度。

6. **Redis 用例需要修改源码**：虽然论文主打「不修改源码」的扩展能力，但 Redis 持久化调优用例实际需要在 Redis 中添加约 20 行代码来定义新的 extension entry。这与 Nginx 和 DeepFlow 等开箱即用的用例形成反差，说明对未预先设计扩展点的应用，EIM 的适用性有限。

7. **评估缺乏安全性定量分析**：论文的评估集中在性能方面，但 EIM 的核心卖点之一是安全性。除了列举历史 bug 的定性说明外，没有系统性地评估 EIM 能防止多少类型的安全违规，也没有与其他安全框架做安全性的对比分析。

---

## 七、AI Infra / MLSys 视角

1. **ML 推理框架的插件安全**：vLLM、TensorRT-LLM 等推理引擎支持自定义 sampling、tokenization、调度策略等插件。EIM 的细粒度 capability 模型可以借鉴用于限制推理插件的权限——例如只允许自定义 sampler 读取 logits 但不能修改 KV cache，防止插件 bug 导致推理引擎崩溃。

2. **eBPF 在 AI 系统监控中的潜力**：bpftime 将 eBPF uprobe 的开销降低了 13×+，这使得在 GPU 通信密集的训练/推理场景中使用 eBPF 做低开销的 NCCL 调用监控、CUDA kernel launch 追踪、内存分配分析变得更可行。DeepFlow 用例已展示了对微服务的监控，延伸到 AI serving 场景很自然。

3. **FUSE 缓存加速对 AI 存储有启发**：大规模训练常用分布式文件系统（通过 FUSE 挂载），如 JuiceFS、Alluxio FUSE。bpftime 的 FUSE 缓存用例展示了通过用户态扩展缓存 metadata 操作带来数量级加速的可能，值得在 AI 训练数据加载场景中探索。

4. **可跟进的研究方向**：
   - 将 EIM/bpftime 应用于 ML serving 框架（如 Triton Inference Server）的请求处理流水线，实现低开销的自定义路由/限流/监控
   - 探索用 bpftime 的 concealed extension entry 技术为 GPU driver（如 open-source NVIDIA kernel module）添加低开销的性能监控点
   - 将 bpftime 的 capability 模型用于多租户 ML 推理场景中的插件隔离

---

## 八、总结

本文提出了 EIM 和 bpftime，前者通过 capability 模型实现了扩展接口的细粒度安全/互联性权衡规范，后者通过 eBPF 风格静态验证、Intel MPK 硬件隔离和 concealed extension entry 二进制重写三项技术高效执行该规范。在 Nginx、DeepFlow、Redis、FUSE、sslsniff、syscount 六个用例中，bpftime 展现了比 eBPF uprobe、Lua、WebAssembly、ERIM、RLBox 等现有框架显著更低的性能开销（Nginx 场景比 Lua/Wasm 低 5-6× 的开销），同时提供了更强的安全保障。主要局限包括仅支持 x86、MPK 隔离存在已知攻击面未完全修复、EIM 规范的编写维护成本，以及对未预设扩展点的应用适用性有限。
