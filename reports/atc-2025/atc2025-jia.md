# Rex: Closing the Language-Verifier Gap with Safe and Usable Kernel Extensions

**作者**：Jinghao Jia*, Ruowen Qin*, Milo Craun†, Egor Lukiyanov†, Ayush Bansal*, Minh Phan*, Michael V. Le‡, Hubertus Franke‡, Hani Jamjoom‡, Tianyin Xu*, Dan Williams† (*University of Illinois Urbana-Champaign, †Virginia Tech, ‡IBM T.J. Watson Research Center)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/jia
**源文件**：[[atc2025-jia.pdf]]

---

## 一、背景

内核可扩展性是现代操作系统的核心能力。eBPF 已成为 Linux 事实上的内核扩展机制，从最初的包过滤器发展为能够定制存储、网络和 CPU 调度的复杂程序框架。eBPF 的核心价值在于通过内核验证器（verifier）对扩展程序进行静态验证，确保内存安全、类型安全、资源安全和终止性等安全属性，防止编程错误导致内核崩溃或挂起。

然而，随着 eBPF 扩展程序变得越来越大和复杂，验证器引入了严重的可用性问题——安全的扩展程序经常被验证器错误拒绝，开发者不得不投入大量精力来"取悦"验证器。

---

## 二、要解决的问题

论文识别了 **language-verifier gap**（语言-验证器鸿沟）这一核心问题：开发者使用高级语言（C/Rust）编写 eBPF 程序，遵守语言契约；编译器也遵守语言契约。但 eBPF 验证器不在语言契约中，它对字节码有独立的、不同的期望。这导致：

1. **符号执行可扩展性限制**：验证器对程序复杂度有硬性限制（指令数、分支数），安全的大程序被拒绝，开发者被迫将程序拆分为多个小程序通过 tail call 连接（如 BMC 从概念上的 2 个程序被拆成 7 个）
2. **编译器与验证器冲突**：LLVM 的优化可能生成验证器无法理解的字节码（如 32-bit move 导致指针被误判为标量），开发者不得不用内联汇编或 volatile 来阻止编译器优化
3. **验证器实现缺陷**：不同内核版本有不同的验证器 bug，开发者需要维护跨版本兼容的 workaround
4. **辅助验证的代码改动**：开发者需要手动重构代码来帮助验证器追踪值的状态，甚至需要重新实现标准库函数（如 memset/memcpy）

论文分析了 Cilium、Aya、Katran 等项目的 72 个与验证器相关的 commit，确认了这些 workaround pattern 的普遍性。

---

## 三、洞察与设计

**关键洞察**：内核扩展所需的安全属性可以完全建立在安全编程语言（Rust）的语言级特性之上，配合轻量级的运行时检查来处理纯静态分析难以保证的属性（如终止性、栈安全），从而完全消除对独立静态验证层的需求，彻底关闭 language-verifier gap。

基于此洞察，Rex 的整体设计如下：

**语言级安全（编译时）**：
- Rex 扩展严格使用 safe Rust 编写，禁止 unsafe 代码、`core::mem::forget`、`ManuallyDrop`、浮点/SIMD、动态分配等
- **内存安全**：通过 Rust 泛型编程和 const generics 在编译时保证 helper function 参数的类型和大小匹配；内核指针通过 Rust slice 提供运行时边界检查
- **扩展类型安全**：引入 `rex::NoRef` auto trait，确保 transmute 的目标类型不包含指针/引用，配合边界检查保证类型转换安全
- **资源安全**：使用 Rust RAII 模式管理内核资源（如 spinlock 的 lock guard），通过 Drop trait 自动释放

**Rex kernel crate**：包装 eBPF helper function 接口为 safe Rust API，是扩展与内核的唯一交互通道

**轻量级运行时（extralingual runtime）**：
- **异常处理**：实现 dispatcher + landing pad + panic handler 机制。Panic 时通过 per-CPU buffer 记录已分配的内核资源并正确释放，然后通过 landing pad 恢复上下文优雅退出
- **栈安全**：混合方案——无间接/递归调用时静态计算栈使用量；有间接/递归调用时在每个函数调用前插入 `rex_check_stack` 运行时检查。使用 8 页专用栈（4 页给扩展，4 页给 helper 和 panic 处理）
- **终止性**：使用 hrtimer watchdog 定时器，per-CPU 部署，到期后通过修改被中断上下文的指令指针寄存器跳转到 panic handler。使用三态 flag 避免在 helper 执行或 panic 处理期间中断

---

## 四、实现细节

- 基于 Linux v6.11 实现
- 支持 5 种 eBPF 程序类型：tracepoint、kprobe、perf-event、XDP、TC
- **Kernel crate**：3.5K 行 Rust 代码（其中 360 行 unsafe，约 10%），包含 helper function 接口封装、内核数据类型绑定（rust-bindgen 自动生成）、程序上下文封装
- **内核支持**：2.2K 行 C 代码，实现扩展加载（ELF 解析、段映射、fixup）和运行时（栈切换、终止机制、异常处理）
- **编译器支持**：在 LLVM 中实现 Rex-specific 编译器 pass 用于栈安全检测；在 rustc 中添加编译器开关；使用 fat LTO 和单一 codegen unit 确保全局视图
- 排除了因验证器约束而存在的 helper（如 `bpf_loop`、`bpf_strtol`、`bpf_strncmp`）
- 采用 crash-stop 失败模型：panic 的扩展连同其使用的 map 和共享该 map 的其他扩展一并从内核移除

---

## 五、实验结果

### 可用性评估

- 用 Rex 重写了 BMC（BPF MemcachedCache）：Rex-BMC 仅 326 行 Rust，而 eBPF-BMC 为 513 行 C（拆成 7 个程序）
- 消除了所有 5 类 verifier workaround 的需求
- 代码显著更简洁：利用 Rust iterator、closure、slice 等特性替代复杂的边界检查和状态机

### 宏观性能（BMC throughput）

| 配置 | 8 核吞吐量 | 相对 Memcached 加速比 |
|------|-----------|---------------------|
| Memcached（原始） | 365K RPS | 1x |
| eBPF-BMC | 1.92M RPS | 5.26x |
| Rex-BMC | 1.98M RPS | 5.43x |

Rex-BMC 略优于 eBPF-BMC，归因于消除了 tail call 和 map 状态传递的开销。

### 微观基准测试

| 指标 | eBPF | Rex |
|------|------|-----|
| 空程序执行时间 | 42.1 ± 4.1 ns | 42.6 ± 5.8 ns |
| Spinlock 获取+释放 | 130.4 ± 20.3 ns | 183.1 ± 27.5 ns |
| 递归调用（深度 33） | ~3x 慢于 Rex | 基准 |
| Array map lookup 额外开销 | — | ~0.5 ns（vs inlined eBPF） |
| Hash map lookup 额外开销 | — | ~1.2 ns（vs inlined eBPF） |

- Setup/teardown 仅增加 8 条指令，开销约 1 ns
- Spinlock 的 50 ns 额外开销来自 per-CPU buffer 记录和状态标记，在实际场景中可忽略
- 递归场景下 Rex 反而比 eBPF tail call 快 ~3x（eBPF tail call 有计数限制检查和 map 访问开销）

---

## 六、批判性分析

1. **TCB 扩大的风险被低估**：论文承认将 Rust 工具链纳入 TCB，但用"其他项目也这么做"来论证可接受性。rustc 的代码量远大于 eBPF verifier，且 Rust 编译器的 soundness bug 历史上并不罕见（如 unsound auto trait 推导、lifetime 相关 bug）。论文未量化 TCB 扩大带来的实际安全风险。

2. **评估的代表性有限**：核心宏观基准仅有 BMC 一个应用，且 BMC 的 workload 特征（高频短请求、主要是网络操作）可能不能代表所有复杂扩展场景。缺少对存储、调度等其他扩展类型的端到端评估。

3. **crash-stop 模型过于激进**：一个扩展 panic 会连带移除所有共享 map 的扩展，这在生产环境中可能导致级联故障。论文将此描述为"防止不一致状态"，但未讨论这种策略对系统可用性的影响。

4. **不支持硬中断上下文的局限性被淡化**：Rex 使用硬中断实现终止，因此无法保护运行在硬中断或 NMI 上下文中的扩展。论文称这些扩展"小且简单，不太遇到 language-verifier gap"，但这是一个未经验证的假设。

5. **不支持动态内存分配**：这是 eBPF 近年的重要进展（kfunc-based allocator），Rex 对此仅在 Discussion 中提及"未来计划支持"。这限制了 Rex 处理更高级 use case 的能力。

6. **72 commit 分析的方法论**：通过关键词搜索 + 手动检查收集样本，存在选择偏差风险。未说明关键词是什么、覆盖了多长时间范围、遗漏率如何。

---

## 七、AI Infra / MLSys 视角

1. **GPU 内核扩展的启示**：Rex 的"用安全语言替代独立验证器"思路可以迁移到 GPU 编程场景。当前 CUDA kernel 缺乏系统性的安全验证，如果能用类似 Rex 的方法在 GPU 内核调度层面提供安全保证（如防止显存越界、资源泄漏），对 AI 推理系统的可靠性有价值。

2. **eBPF for AI workload 调度**：sched_ext 等基于 eBPF 的调度器正在被用于 AI 训练/推理的 CPU 调度优化。Rex 消除 verifier 限制后，可以实现更复杂的调度策略（如基于 GPU utilization 的动态调度、跨 NUMA 的 tensor 数据局部性优化），而不必担心程序复杂度超出验证器限制。

3. **内核旁路网络的安全扩展**：AI 集群中的高性能网络（如 RDMA、DPDK）通常绕过内核，缺乏安全隔离。Rex 的 XDP 支持展示了在网络数据面进行安全扩展的可能性，可以用于实现 AI 训练通信的安全监控和流量整形，而不牺牲性能。

4. **值得跟进的方向**：
   - 将 Rex 的 RAII 资源管理模式应用于 GPU 显存管理的内核扩展
   - 探索 Rex + sched_ext 在 LLM 推理集群中的 request-level 调度
   - 基于 Rex 实现 AI workload 的 kernel-level profiling 和 tracing，替代现有的 eBPF-based 方案以支持更复杂的分析逻辑

---

## 八、总结

Rex 是一个新的 Linux 内核扩展框架，通过将安全保证从独立的 eBPF 静态验证器转移到 Rust 语言的编译时安全 + 轻量运行时检查，彻底消除了 language-verifier gap。Rex 在 BMC 案例中展示了显著的可用性提升（代码量减少 36%，消除所有 verifier workaround）和相当甚至略优的性能。其主要局限在于扩大了 TCB（依赖 Rust 编译器正确性）、不支持动态内存分配、以及 crash-stop 失败模型在生产环境中可能过于激进。Rex 最适合大型、复杂的内核扩展场景，而简单扩展仍可继续使用 eBPF。
