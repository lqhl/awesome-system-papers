# Building Bridges: Safe Interactions with Foreign Languages through Omniglot

**作者**：Leon Schuermann, Jack Toubes (Princeton University); Tyler Potyondy, Pat Pannuto (UC San Diego); Mae Milano, Amit Levy (Princeton University)
**会议**：OSDI 2025
**链接**：https://www.usenix.org/conference/osdi25/presentation/schuermann
**源文件**：[osdi25-schuermann.pdf](../../papers/osdi-2025/osdi25-schuermann.pdf)

---

## 一、背景

内存安全和类型安全的编程语言（如 Rust、Go、Swift）通过编译时检查消除了整类系统漏洞，正被越来越多地用于构建操作系统内核、安全关键固件等场景。然而，现实中的系统几乎不可能完全用单一安全语言编写——它们往往需要集成用 C 等不安全语言编写的成熟库（如加密库、文件系统、网络协议栈）。这些库经过数十年打磨，不可能一夜之间被替换。

当安全语言通过 Foreign Function Interface (FFI) 调用外部库时，外部代码与宿主程序运行在同一地址空间、拥有相同权限。一个外部库中的 bug（如 OpenSSL Heartbleed）可以任意违反宿主语言的安全不变量。现有的 FFI 工具（如 rust-bindgen）生成的绑定几乎不编码任何语言语义信息，将安全验证的负担完全推给开发者，而手动维护这些不变量极其容易出错。

---

## 二、要解决的问题

1. **内存安全被破坏**：外部函数可以不受限地访问宿主内存。即使不是恶意行为，一个简单的 off-by-one 错误就可以覆盖 Rust 内部数据结构（如 `Vec` 的 length 字段），导致后续越界访问。

2. **别名与可变性规则被违反**：Rust 的核心规则是"别名 XOR 可变性"（aliasing XOR mutability）——一个值要么有多个不可变引用，要么只有一个可变引用。C 函数的指针语义无法表达这一约束，例如 `aes_encrypt` 的 `src` 和 `dst` 在 in-place 模式下指向同一内存，同时存在可变和不可变引用。

3. **类型安全被违反**：不同语言对同一类型有不同的有效值约束。例如 Rust 的 `bool` 只接受 0 或 1，而 C 的 `bool` 本质上是 `int`。当 C 返回一个值为 2 的 "bool" 时，Rust 的 niche filling 优化会将其错误解释为另一个 enum variant，导致段错误或 use-after-free。

4. **现有隔离方案不足**：已有方案要么只做内存隔离而忽略类型安全和别名规则（如 TRust、PKRU-Safe），要么需要昂贵的序列化和跨进程通信（如 Sandcrust），性能代价过大。

---

## 三、洞察与设计

**关键洞察**：维护 FFI 安全不需要对外部代码的正确性进行推理或建模整个程序的组合语义——只需在 FFI 边界上对外部代码的每次执行结果进行运行时验证，就足以恢复宿主语言的所有安全不变量。换言之，安全性可以从"证明外部代码正确"降级为"验证外部代码的输出符合宿主类型系统的要求"。

基于这一洞察，Omniglot 的设计包含三个核心机制：

### 1. 可插拔的沙箱运行时

Omniglot 将内存划分为宿主（Rust）和外部库各自独占的区域，通过硬件内存隔离原语（RISC-V PMP 或 x86 MPK）阻止外部代码访问宿主内存。运行时提供统一 API：`OGRt::new` 加载库到沙箱，`stack_alloc` 在外部栈上分配内存，`setup_callback` 注册回调，`invoke` 在沙箱内调用外部函数。

### 2. Typestate 引用与验证类型

Omniglot 设计了一套渐进式验证的类型体系：
- `*mut T`（原始指针）→ `OGMutRef<T>`（经 `upgrade` 验证指向合法外部分配）→ `OGVal<T>`（经 `validate` 验证 bit pattern 符合 Rust 类型要求）→ `&T`（安全引用）
- `OGMutRef<T>` 内部表示为 `&UnsafeCell<MaybeUninit<T>>`，允许可变别名同时避免编译器对值有效性的假设
- 对于无法仅通过 bit pattern 验证的高阶类型（如引用、typestate），开发者传递符号表示而非直接传递对象

### 3. 零成本 Scope 机制

为解决时序约束问题（如写操作可能使已验证的值失效、释放分配可能使引用悬挂），Omniglot 引入 `AllocScope` 和 `AccessScope` 两种编译时作用域标记。利用 Rust 的 borrow checker 实现读写互斥：
- 共享借用（`&`）= 读锁：upgrade/validate 操作需要
- 独占借用（`&mut`）= 写锁：write/invoke/stack_alloc 操作需要
- 编译器静态拒绝不安全的交叉使用，零运行时开销，无死锁

---

## 四、实现细节

Omniglot 实现为一组 Rust crate，约 7000 行代码，并扩展 rust-bindgen 860 行以自动从 C 头文件生成 Omniglot 兼容绑定。

### 两个运行时实现

- **OG_PMP**（Tock OS 内核，RISC-V PMP）：强运行时。外部库运行在低特权级，无系统调用接口，无并发原语。通过 PMP 配置完全隔离外部内存。能安全运行任意不可信甚至恶意的外部库。
- **OG_MPK**（Linux 用户空间，x86 MPK）：弱运行时。利用 MPK 的 16 个保护键为外部库分配独立保护域，域切换不需要系统调用。但恶意库可通过 `mmap` 等系统调用绕过隔离，需配合 seccomp-bpf 等缓解措施。适用于非恶意但可能有 bug 的库。

### Invoke Trampoline 机制

Omniglot 设计了一个泛型 invoke trampoline，利用 Rust 编译器对 C 调用约定的知识，在编译时静态生成参数加载代码（而非使用 libffi 等动态方案）。具体流程：
1. rust-bindgen 为每个 C 函数生成一个新的 `extern "C"` Rust 函数
2. 将该函数符号别名到运行时的泛型 `invoke` 符号
3. `invoke` 函数：保存寄存器 → 复制栈溢出参数到外部栈 → 启用内存保护 → 调用外部函数 → 禁用保护 → 编码返回值

### 对特殊模式的支持

- 回调：通过 `setup_callback` 注册，外部代码跳转到注册地址时，运行时将控制权交回 Rust
- `setjmp/longjmp`：不直接支持，需 C wrapper 将 longjmp 转换为错误返回值
- 库的传递依赖：OG_MPK 通过 link-map list 将库及其所有依赖加载到隔离命名空间

---

## 五、实验结果

### 端到端性能（Table 2）

| 库 | 运行时 | invoke 次数 | callback 次数 | upgrade 次数 | validate 次数 | 隔离开销 (vs unsafe) | Omniglot 额外开销 (vs 仅隔离) |
|---|---|---|---|---|---|---|---|
| CryptoLib (HMAC-SHA256, 4kB) | PMP | 14 | 0 | 10 | 2 | +0.44% | +0% |
| LittleFS (1kB 文件读写) | PMP | 7 | 0 | 0 | 7 | +20.1% | +0.5% |
| LwIP (ICMP echo) | PMP | 3 | 1 | 2 | 5 | +52.1% | +3.4% |
| Brotli (1kB 压缩) | MPK | 2 | 0 | 0 | 4 | +0.6% | +0% |
| libsodium (32kB hash) | MPK | 1 | 0 | 0 | 2 | +3.4% | +0% |
| libpng (23kB 图片解码) | MPK | 5 | 15 | 16 | 3 | +12.7% | +0.8% |

### 与 Sandcrust 的对比

在 libpng 图片解码场景中，Omniglot 的性能接近 unsafe FFI 基线，而 Sandcrust 的开销随解码图片尺寸增长显著增大（因为需要序列化和跨进程拷贝数据）。

### 微基准测试（Table 3）

- **Setup**：PMP 0.17µs, MPK 1.49ms
- **Invoke（单次热调用）**：PMP 6.57µs, MPK 98.90ns
- **Upgrade**（64 个分配）：PMP 9.4µs, MPK 1.10µs
- **Validate**（8kB u8）：PMP 0.23µs, MPK 1.70ns（编译器可优化掉无条件合法类型的验证）
- **Validate**（8kB str/UTF-8）：PMP 161.5µs, MPK 70.94µs（需线性扫描）

---

## 六、批判性分析

1. **弱运行时的安全性被低估了其局限性**：OG_MPK 被称为"弱运行时"，但论文在讨论中过于轻描淡写其安全缺陷。MPK 可被系统调用绕过（Connor et al. 已证明），恶意库可通过 `mmap` 突破隔离、注册信号处理器、创建后台线程。论文建议"手动检查库代码"或使用 seccomp-bpf，但未实现也未评估这些缓解措施的有效性和实用性。对于一个声称维护 Rust soundness 的系统，这是一个显著的实际安全缺口。

2. **嵌入式场景的基线选择需要审视**：PMP 运行时的 LwIP 基准显示隔离本身带来 52.1% 的开销，Omniglot 只增加 3.4%。但这意味着实际总开销超过 55%。论文将 Omniglot 开销与"仅隔离"对比以突出其低开销，但用户关心的是与 unsafe FFI 相比的总体代价。

3. **通用性声称 vs 实际局限**：论文声称 Omniglot 支持"任意、不可信"的外部库，但实际上：(a) 不支持 `setjmp/longjmp`，需要额外 C wrapper；(b) 无法验证引用、lifetime、typestate 等高阶类型；(c) 对于有状态的并发库（如带内部线程池的库），即使是强运行时也难以处理。这些限制未被充分讨论。

4. **缺少 developer effort 的评估**：论文未量化将现有 unsafe FFI 绑定迁移到 Omniglot API 所需的工作量。虽然声称"高度机械化"，但从 Listing 3 的代码可以看出，开发者需要显式管理 scope、upgrade、validate 等操作，这与直接使用 unsafe FFI 的认知负担有本质差异。

5. **评估规模有限**：测试的库（CryptoLib、LittleFS、LwIP、Brotli、libsodium、libpng）接口相对简单。缺少对大型、复杂库（如 OpenSSL、SQLite、glibc 子集）的评估，这些库有复杂的回调模式、全局状态和线程使用。

---

## 七、总结

Omniglot 是首个在不修改外部库的前提下，同时维护 Rust 内存安全、类型安全和别名规则的 FFI 框架。其核心创新在于将安全保证从"证明外部代码正确"转化为"验证 FFI 边界数据的合法性"，并巧妙利用 Rust 类型系统和 borrow checker 实现了零成本的时序约束执行。在两个运行时（RISC-V PMP 嵌入式内核、x86 MPK 用户空间）上的评估表明，Omniglot 相比仅做内存隔离几乎无额外开销，且显著优于需要序列化的同类方案。主要局限在于弱运行时对恶意库的防护不足、对高阶 Rust 类型的验证能力有限，以及在大型复杂库上的实用性尚待验证。
