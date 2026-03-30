# Omniglot: Safe Interactions with Foreign Languages through Memory Isolation

## 论文基本信息

- **标题**: Building Bridges: Safe Interactions with Foreign Languages through Omniglot
- **作者**: Leon Schuermann, Jack Toubes (Princeton), Tyler Potyondy, Pat Pannuto (UCSD), Mae Milano, Amit Levy (Princeton)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/schuermann

## 研究背景与动机

内存安全（memory-safe）和类型安全（type-safe）语言（如 Swift、Go、Rust）通过编译时检查从结构上消除整类 bug。近年来在政府推动和实际系统需求的驱动下，这些语言被越来越多地用于编写系统组件（kernel、网络栈、存储等）。

然而，现实世界的系统通常需要集成其他语言编写的库——这些库通常缺乏安全保证（如 C 库）。现有工具（如 Rust 的 rust-bindgen）生成的 FFI 绑定：
- 直接暴露原始指针
- 要求开发者用 `unsafe` 块包裹调用
- **实质上绕过了 Rust 的所有安全保证**

这导致安全的 host 语言程序与不安全的 foreign 代码之间的交互，重新引入了 safe 语言本应消除的安全漏洞。

## 要解决的核心问题

**核心问题**：如何在不牺牲性能（避免昂贵的 copy 或 serialization）的前提下，为 safe 语言（以 Rust 为例）提供真正安全的 foreign function interface？

**具体挑战**：
1. **Memory Safety**：Foreign 代码对 host 内存拥有不受限制的访问权
2. **Aliasing & Mutability**：不同语言对指针别名和可变性的约束不同（如 Rust 的 XOR-aliasing 规则）
3. **Type Safety & Valid Values**：类型合法的取值范围可能不同（如 C bool 可能超出 Rust bool 的 {0, 1} 范围）
4. **Concurrency**：并发场景下 foreign 代码可能违反 Rust 的无数据竞争保证

**先前方法的不足**：
- 粗粒度内存隔离（separate protection domains）不够：即使 foreign 代码只访问 sandboxed 内存，语义差异（如指针别名规则）仍可能导致 violation
- 手动验证和类型转换容易出错且不切实际

## 主要贡献

1. **第一个在 presence of arbitrary untrusted foreign code 的情况下维持 Rust 所有 safety-critical 语言不变量的框架**
2. **Omniglot 的核心机制**：
   - Memory isolation primitive 隔离 foreign 库的内存访问
   - **Reference & Validation Types**：将 foreign 返回的值包装在特殊类型中，逐步验证其符合 Rust 的约束
   - **Scopes**：编译时强制执行的 zero-cost 机制，防止 Omniglot runtime 与 Rust code 交互时违反不变量
3. **两种平台的具体实现**：RISC-V PMP（嵌入式 OS kernel）和 x86 MPK（Linux userspace）
4. **对 rust-bindgen 的扩展**：生成兼容 Omniglot 的 safe FFI bindings
5. **广泛的评估**：crypto、compression、image decoding、filesystem、TCP/IP 等多种库

## 研究方法与设计

### 威胁模型

Omniglot 维护 Rust 在 arbitrary untrusted foreign code 存在时的 soundness。为此假设：
1. **存在可用的内存隔离原语**（硬件/OS/软件）能防止 foreign 库访问除明确允许外的任何内存区域
2. **存在能限制 foreign 代码执行时机的原语**：如阻止 foreign 库在 host 代码运行期间在后台继续运行（spawn threads、处理 signals）

### Omniglot 核心设计

#### 1. Safety Invariants 分类

Omniglot 识别了 Rust soundness 所需的四类不变量：

**Memory Safety**：
- 每个语言一侧的分配属于独立的内存区域
- Foreign 代码只能访问自己的 sandboxed 内存区域
- Rust 只能通过特殊引用类型解引用指向 foreign 内存的指针

**Aliasing & Mutability**：
- 所有从 foreign 内存派生的引用保守地假设为相互 mutable aliased
- Safe 支持 mutable aliasing 只能通过互斥（mutual exclusion）

**Type Safety**：
- Foreign 代码返回的对象标记为 tainted（受污染），标记为特殊 "any" 类型
- Omniglot 提供 downcast 方法，只有在验证对象满足特定类型约束后才允许转换为有用类型

**Concurrency**：
- Foreign 代码不能与 Rust 并发运行，或必须使用同步和内存隔离原语

#### 2. Sandboxing Runtime（平台相关）

Omniglot 实现了一个可插拔的 sandboxing runtime：

**RISC-V PMP（embedded OS kernel）**：
- 使用 Physical Memory Protection (PMP) 设置细粒度内存权限
- 每个 foreign 库实例被分配独立 PMP region

**x86 MPK（Linux userspace）**：
- 使用 Memory Protection Keys (PKRU) 隔离 foreign 内存区域
- 通过 `wrpkru` 指令切换权限域

Runtime 暴露的 API：
- `load_library()`：将 foreign 库加载到 sandbox
- `call()`：调用 foreign 函数
- `malloc()/free()`：管理 foreign 内存分配
- `restrict_concurrency()`：限制 foreign 代码并发执行

#### 3. Reference & Validation Types

Omniglot 提供两类关键类型：

**ForeignPtr\<T\>**：指向 foreign 内存的指针
- 解引用前必须通过验证
- 不允许 raw pointer 在 Rust 中自由流动

**Any**：foreign 代码返回或写入 foreign 内存的对象的标记类型
- 持有 tainted 数据，不允许直接使用
- 通过 downcast 验证并转换：
  ```rust
  if is_valid_bool(b) { Ok(b.unwrap()) } else { Err }
  ```

**Downcast 验证的内容**：
- Underlying size、alignment、bit-pattern
- High-level invariants（如 UTF-8 valid string、valid enum discriminant）

**对于不可验证的类型**（如 Rust references written to foreign memory）：
- 只能传递象征性表示（如 handle），而非实际指针

#### 4. Scopes（零成本 Temporal Invariant 强制）

**问题**：Omniglot runtime 和 Rust code 之间的交互本身可能违反 Omniglot 类型依赖的不变量。

**解法**：引入 Scopes——一种编译时强制执行的 zero-cost 机制：
- 每个 Scope 定义了一个有效期（lifetime）
- 在 Scope 退出时，强制所有验证状态重置
- 编译时拒绝可能违反作用域不变量（temporal invariants）的代码

Scopes 还支持互斥协议：
- 在访问 foreign 内存中的 mutable 数据时，自动获取互斥锁
- 互斥锁在 Scope 退出时自动释放
- 避免死锁（zero-cost deadlock freedom）

### 代码生成（rust-bindgen 扩展）

修改 rust-bindgen 为 Omniglot 生成 bindings：
- 替代 raw pointers：`*mut u8` → `ForeignPtr<u8>`
- 生成 validation wrappers：检查返回值是否满足 Rust 类型约束
- 自动插入 scope annotations

## 关键实现细节

### 验证例程的实现

```rust
fn is_valid_bool(b: u8) -> bool {
    b == 0 || b == 1
}
```

对于复合类型（如 enum），验证例程检查 discriminant 和 active variant 的内存布局。

### Scope 的编译时强制

Omniglot 利用 Rust 的 lifetime 系统来编译时强制 scopes：
- 每个验证操作关联一个 scope lifetime
- 引用只能在 scope 有效期内保持有效
- 编译器拒绝将验证引用泄漏出 scope 的代码

### Concurrency 处理

Foreign 代码执行期间：
- 在 Linux 上，Omniglot 禁用 signals 和异步回调
- Foreign 代码必须通过 Omniglot 暴露的 API（而非直接 threads）来请求并发执行

## 实验结果与分析

### 测试用例

评估覆盖 5 类 10 种库：
- **Crypto**：AES encryption、HMAC、SHA256
- **Compression**：zlib、LZ4
- **Image decoding**：JPEG、PNG
- **Filesystem**：POSIX file I/O
- **TCP/IP networking**：lwIP stack

### 性能评估

#### 与 Memory Isolation Only 比较
Omniglot 比单纯内存隔离（如 SFI-based 方法）的开销可忽略不计（negligible overhead）。

#### 与 Unchecked FFI 比较
Omniglot 相比 raw unsafe FFI 有 practical overhead：
- 验证检查引入的运行时成本
- Scope annotation 的约束

但与 copying/(de)serialization 方法相比显著更好：
- 避免了跨 FFI 的数据复制
- 避免了序列化/反序列化开销

#### 端到端应用评估

在 Rust embedded OS kernel（使用 RISC-V PMP）和 Linux userspace（使用 x86 MPK）两个平台上验证：
- **Crypto throughput**：接近 raw C 实现（仅验证检查的开销）
- **Image decode latency**：显著低于需要数据拷贝的方案

### 安全性评估

Omniglot 在 presence of buggy/malicious foreign libraries 下维持 Rust 的 soundness guarantees：
- 所有安全不变量在编译时或运行时（通过验证）得到强制
- 不依赖 foreign 代码的正确性

## 潜在问题与局限性

1. **Rust 的未定义行为定义不完整**：论文承认 Rust 的 UB 定义缺乏形式化规范，Omniglot 的设计基于"当前已知的不变量"。随着 Rust 语言演化，这些不变量可能变化，Omniglot 需要相应更新
2. **平台支持有限**：目前只支持 RISC-V PMP 和 x86 MPK；其他常见平台（ARM、MIPS、ARM TrustZone）没有实现
3. **Complex foreign types 的验证不完整**：对于包含指针、跨语言引用计数的复杂数据结构（如 C++ std::vector），Omniglot 的验证可能不够充分
4. **Performance isolation 的 cost**：禁用 async signals 和后台 threads 意味着 foreign 库中任何依赖这些特性的功能无法正常工作（如 event-driven C libraries）
5. **验证开销的规模性**：每个 foreign 函数调用的返回值都需要验证，在高频调用场景下（如 tight loop 中的 small function calls），验证开销可能累积
6. **与 async Rust 的兼容性**：异步 Rust 运行时在等待 I/O 时可能产生并发任务，这与 Omniglot 的 concurrency restriction 可能冲突，论文未讨论 async 场景

## 未来工作方向

1. 扩展到更多平台（ARM TrustZone、RISC-V PMP 的更精细粒度）
2. 自动化验证例程生成（基于类型系统推断）
3. 形式化验证 Omniglot 的安全属性
4. 与 Rust async 生态系统的集成

## 个人评注

### 优点

1. **问题定义精准**：FFI 的 soundness 问题在 Rust 社区一直被讨论，但缺乏系统性的解决方案。Omniglot 第一次系统性地识别并处理了 memory safety、aliasing/mutability、type safety、concurrency 四类不变量
2. **零成本安全的理念优雅**：通过编译时强制（Scopes）而不是运行时检查来防止 temporal invariants 违反，避免了性能惩罚
3. **验证类型的灵活性**：允许逐步验证（downcast）而非全有或全无，是一个务实的折中
4. **与 rust-bindgen 的集成**：修改业界标准工具而非另起炉灶，降低了实际采用门槛

### 不足与可疑之处

1. **Rust soundness invariants 的完备性无法保证**：论文本身承认"there is no exhaustive list of defined or undefined behavior" for Rust。Omniglot 的设计依赖于"当前已知的不变量"，这意味着可能被未来的 Rust 编译器或语言特性所破坏
2. **"Arbitrary untrusted foreign code"的假设过于乐观**：Omniglot 假设 foreign 库是 adversarial 的，但同时假设 isolated 机制（MPK/PMP）本身是 trustworthy 的。然而，MPK 已被证明容易受到 Spectre 类攻击，MPK keys 的切换不能防止 speculative execution 下的信息泄露
3. **与安全领域已有工作的关系不够清晰**：关于 safe FFI 的研究（如 Rust 社区的 safe-transmute、C2Rust 项目）与 Omniglot 的关系和差异化未充分讨论
4. **Scope 的死锁避免协议未在理论上证明**：论文声称 scopes 支持互斥协议并防止死锁，但缺乏形式化证明，只有一个 high-level 描述。在复杂的并发场景下，死锁避免的完整性难以仅通过实现验证
5. **评估的代表性可能不足**：论文测试的库相对简单（crypto primitives、compression），对于复杂的 C++ libraries（如 STL containers、RTTI）Omniglot 的适用性未经测试
6. **PCIe 拓扑利用的对比基准选择有偏**：论文将 Omniglot 与"弱安全保证"和"copy/(de)serialize"方案比较，但没有与同样提供强安全保证的其他方案（如 formal verification-based FFI、language-based enforcement）进行对比，读者无法判断 Omniglot 相比这些替代方案的相对优劣
