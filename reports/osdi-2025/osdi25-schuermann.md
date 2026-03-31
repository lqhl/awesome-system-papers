# Building Bridges: Safe Interactions with Foreign Languages through Omniglot

**作者**：Leon Schuermann, Jack Toubes（Princeton University）；Tyler Potyondy, Pat Pannuto（University of California, San Diego）；Mae Milano, Amit Levy（Princeton University）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation，Boston, MA, July 7–9, 2025）
**DOI**：https://www.usenix.org/conference/osdi25/presentation/schuermann
**源文件**：[osdi25-schuermann.pdf](../../papers/osdi-2025/osdi25-schuermann.pdf)

---

## 一、背景

内存安全与类型安全语言（如 Rust、Swift、Go）通过编译器静态保证消除了整类系统漏洞，是现代安全关键系统的重要基础。美国政府机构也已开始鼓励采用内存安全语言替代 C/C++。Rust 在操作系统内核（Linux、Microsoft 组件）、嵌入式系统（Tock OS、OpenTitan）、网络函数（NetBricks）等领域已有实际落地。

然而，真实世界的系统往往无法从零开始全部用安全语言重写，必须集成已有的 C/C++ 库（如密码学库、压缩库、文件系统实现）。这些外部组件在历史上被精心优化和充分测试，工程上不宜立即废弃，而是以增量方式逐步替换。

---

## 二、要解决的问题

将 C 库等"外来代码（foreign code）"集成到 Rust 中，会破坏 Rust 精心维护的安全不变式：

1. **内存安全（Memory Safety）**：外来代码与宿主程序共享地址空间，可任意读写宿主内存（如 OpenSSL Heartbleed 漏洞）。
2. **别名与可变性（Aliasing & Mutability）**：Rust 强制要求"aliasing XOR mutability"，但 C 函数可能返回指向同一内存的多个指针，违反此约束（如 `aes_encrypt` 同时接受可变 src 指针并在 in-place 模式下令 dst 指向同一位置）。
3. **类型安全（Type Safety）**：不同语言对类型的有效值定义不同。例如，C 函数返回的 `bool` 可能是非 0/1 的任意整数，Rust enum 的 niche-filling 优化会将其误解读为其他 variant，导致未定义行为。
4. **现有方案不足**：
   - 纯内存隔离方案（如 PKRU-Safe、ERIM）仅隔离地址空间，不处理类型与别名语义差异；
   - 使用序列化/拷贝跨越边界的方案（如 Sandcrust）性能开销大；
   - 现有 FFI 工具（`rust-bindgen` 生成的 `unsafe extern "C"` 绑定）将安全验证责任完全转移给开发者，极易出错。

---

## 三、核心设计

Omniglot 是首个在保持 Rust **全部**安全不变式（内存安全 + 类型安全 + 别名规则）的前提下，支持**零拷贝**访问外来内存的框架。其核心思路是：

1. **不直接暴露外来指针**：将外来函数调用的结果用特殊类型包装（`OGMutRef`、`OGVal`），只有通过类型系统验证后才可在 Rust 安全代码中使用。

2. **两层隔离机制**：
   - **内存隔离原语**：运行时将外来库加载到独立保护域（通过 RISC-V PMP 或 x86 MPK），防止外来代码任意访问宿主内存。
   - **类型与别名验证**：通过 Rust 类型系统静态表达并验证 Omniglot 的安全约束，利用借用检查器在编译期排除错误。

3. **三类核心类型**：
   - `OGMutRef<T>`：外来内存的"升级"指针，表示可读写的外来引用；
   - `OGVal<T>`：已验证的外来值，保证符合 Rust 类型有效值要求；
   - `AllocScope` / `AccessScope`：基于词法作用域的静态锁机制，零运行时开销地实现互斥，防止读写冲突和悬空引用。

4. **关键设计决策**：
   - 通过作用域（scope）的唯一/共享借用映射读写锁语义，用借用检查器在编译期保证时态约束（temporal constraints），而非运行时锁；
   - `validate` 操作在运行时检查类型有效性（如检查 UTF-8、bool 范围），Rust 编译器会优化掉对无条件有效类型（如 `u8`）的检查；
   - 支持任意满足特定条件的内存隔离原语，具有良好的可移植性。

---

## 四、实现细节

- **代码规模**：Omniglot 及两个运行时实现约 **7000 LoC**（Rust crates），对 `rust-bindgen` 扩展约 **860 LoC**，可自动从 C 头文件生成 Omniglot 兼容绑定。

- **OG_PMP（Tock OS / RISC-V）**：将外来库加载到类似 Tock 进程的低权限保护域；函数调用通过加载参数到寄存器并切换到低权限模式实现；强运行时（strong runtime），可抵御任意恶意外来代码。

- **OG_MPK（Linux userspace / x86）**：利用 x86 MPK 将外来库页面分配保护密钥；调用时禁用宿主页面访问；无需 syscall 即可切换保护域，开销极低。但 MPK 本身存在可绕过的安全问题（系统调用、信号、race condition），故为弱运行时（weak runtime）。

- **invoke 蹦床（Trampoline）**：Omniglot 的核心工程挑战是在不修改 Rust 编译器的前提下，拦截所有外来函数调用并切换保护域。方案：将 C ABI 函数符号别名到通用 `invoke` 符号，利用 Rust 编译器的 ABI 知识静态生成参数加载代码，避免 libffi 的动态分发开销。

- **与 rust-bindgen 集成**：修改后的 `rust-bindgen` 可为每个 C 函数自动生成对应的 Omniglot 包装，开发者通过机械化流程集成现有 C 库。

---

## 五、实验结果

**实验平台**：
- OG_MPK：CloudLab Wisconsin c220g5（2× Intel Xeon Silver 4114 @ 2.2GHz），Linux 5.15.0，rustc 1.84.0-nightly
- OG_PMP：ChipWhisperer CW310 FPGA，OpenTitan EarlGrey SoC，RISC-V rv32imc @ 24MHz

**评测库**（Table 2，各库端到端开销）：

| 库 | 运行时 | unsafe FFI | 仅隔离 | Omniglot | 隔离外开销 |
|---|---|---|---|---|---|
| CryptoLib（HMAC-SHA256） | PMP | 9105µs | 9145µs (+0.44%) | 9145µs | **+0%** |
| LittleFS（文件系统） | PMP | 3115.3µs | 3742.8µs (+20.1%) | 3764µs | **+0.5%** |
| LwIP（网络栈） | PMP | 51.74µs | 78.71µs (+52.1%) | 81.4µs | **+3.4%** |
| Brotli（压缩） | MPK | 3.12ms | 3.14ms (+0.6%) | 3.14ms | **+0%** |
| libsodium（密码学） | MPK | 51.61µs | 53.41µs (+3.4%) | 53.41µs | **+0%** |
| libpng（图片解码） | MPK | 352.98µs | 397.93µs (+12.7%) | 401.25µs | **+0.8%** |

**零拷贝优势**（Figure 5，libpng vs Sandcrust）：Sandcrust 需序列化/IPC，随图像大小线性增长；OG_MPK 性能接近 unsafe FFI baseline。

**微基准**（Table 3）：
- upgrade 操作：PMP 约 0.6–9.4µs（随 alloc 数量增长），MPK 约 32–1100ns；
- validate：对无条件有效类型（如 `u8`）编译器完全优化消除；对 `str`（UTF-8 验证）线性于数据量（8kB 约 161µs/70µs for PMP/MPK）。

---

## 六、批判性分析

1. **弱运行时（OG_MPK）的安全边界模糊**：MPK 本身已知可被系统调用（mmap）、信号处理等绕过，论文承认 OG_MPK 是"弱运行时"，但未给出量化的安全损失。在实践中，若外来库存在恶意行为，OG_MPK 的内存隔离可以被完全绕过，论文将此留给用户通过 seccomp-bpf 等工具自行缓解——这让 OG_MPK 的"安全"定位更接近防御粗心开发者而非防御攻击者。

2. **性能评测与实际工作负载的代表性**：CryptoLib、LittleFS 等基准测试中，Omniglot 的类型验证开销极小甚至为零，部分原因是 Rust 编译器能优化掉对简单类型的验证。论文以此作为"低开销"主要论据，但对于类型更复杂、外来指针更多、callback 频繁的真实场景，验证开销可能更显著（如 libpng 有 15 次 callback、16 次 upgrade，已有 0.8% 额外开销）。

3. **开发者负担被低估**：论文声称 Omniglot API 不给开发者造成"不当负担"，但 Section 4.5 的代码示例（Listing 3）中，scope 的管理、upgrade/validate 的时序要求相当复杂，初学者极易出错。与 unsafe FFI 相比，错误现在会以编译期错误形式体现（而非运行时漏洞），这是进步，但学习曲线较陡。

4. **与现有 unsafe 代码的迁移路径缺失**：论文承认 Omniglot 不兼容现有 unsafe FFI API，也不支持自动转换已有不安全绑定。这意味着在有大量存量 C FFI 代码的项目中，迁移成本极高，限制了实际采用。

5. **仅支持 Rust**：论文明确将 Rust 以外的安全语言（Swift、Go 等）留作 future work，而这些语言同样面临相同问题。Omniglot 的概念虽通用，但实现高度依赖 Rust 的借用检查器和类型系统，迁移到其他语言需重新设计大量机制。

6. **论文未评估对外来代码的正向安全保证**：Omniglot 不阻止宿主 Rust 代码在外来库内制造错误（如传递无效指针），只防止外来代码破坏宿主的安全性。这种单向性在混合可信度场景下可能不足。

---

## 七、总结

Omniglot 解决了一个重要且长期被忽视的系统安全问题：如何在 Rust 程序中集成不可信的 C 库，同时保持 Rust 的内存安全、类型安全和别名规则。其核心创新在于：将内存隔离与基于 Rust 类型系统的零成本静态验证结合，实现了首个支持零拷贝访问外来内存的健全 FFI 框架。评测显示，相比仅有内存隔离的方案，Omniglot 几乎无额外开销，相比序列化方案性能大幅领先。局限性主要在于仅支持 Rust、OG_MPK 的弱安全保证、以及与现有不安全代码的兼容性缺失。该工作对嵌入式安全关键系统（如 Tock/OpenTitan）和需要集成遗留 C 库的安全 Rust 项目具有直接实践价值。
