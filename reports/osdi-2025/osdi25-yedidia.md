# Deterministic Client: Enforcing Determinism on Untrusted Machine Code

**作者**：Zachary Yedidia（Stanford University）；Geoffrey Ramseyer（Stanford University & Stellar Development Foundation）；David Mazières（Stanford University）
**会议**：OSDI 2025（19th USENIX Symposium on Operating Systems Design and Implementation，July 7–9, 2025, Boston, MA）
**链接**：https://www.usenix.org/conference/osdi25/presentation/yedidia
**源文件**：[osdi25-yedidia.pdf](../../papers/osdi-2025/osdi25-yedidia.pdf)

---

## 一、背景

智能合约（smart contracts）是由完全不可信方上传、却必须在诚实节点上以相同方式执行的程序。区块链系统的正确性依赖于这种**程序确定性（determinism）**：所有副本运行同一合约必须产生完全相同的副作用。现有主流方案（Ethereum EVM、WebAssembly、eBPF）的思路是定义一种具有确定性语义的**中间语言（IL）**，再通过可信的解释器或 JIT 编译器来执行。这种语言层隔离方式（language-based approach）是目前实现对抗性（adversarial）确定性的唯一已知途径。

随着智能合约的功能日益复杂（密码学原语、零知识证明），CPU 效率成为关键瓶颈。解释器过慢，JIT 编译器则依赖庞大的可信代码库（Trusted Computing Base，TCB）——Wasmtime 等 JIT 已多次出现安全漏洞（CVE-2021-32629、CVE-2023-26489）。

---

## 二、要解决的问题

1. **性能与安全的两难**：解释器（如 Wasm3）TCB 小但慢 30×；JIT（如 Wasmtime）快但 TCB 庞大且漏洞频出。两者都需要从中间语言翻译，引入额外的启动延迟和运行时开销。

2. **可信编译器依赖**：现有 IL 方案要求编译器/解释器是可信的。使用 LLVM 这类高性能编译器时，其复杂性本身成为攻击面。

3. **确定性计量（metering）**：传统定时器中断本身是非确定性的——同一合约在不同时刻可能在不同副作用发生后被抢占，导致副本状态分歧。

4. **内存隔离与确定性的结合**：LFI 等 SFI 系统提供内存隔离，但 LFI 程序能读取自己的加载基地址，导致行为依赖加载位置，破坏确定性。

---

## 三、核心设计

**DeCl（Deterministic Client）** 将 SFI（Software Fault Isolation）中用于保证内存隔离的二进制分析技术，扩展到强制执行更强的**确定性**属性。核心思路：设计一个**机器码静态验证器（verifier）**，只接受属于 x86-64 或 Arm64 确定性子集的程序，然后直接以 native 速度运行，无需任何中间翻译层。

三大组件：

1. **确定性指令强制（Deterministic Instruction Enforcement）**
   - Arm64：指令集中存在少量非确定性情况（UNPREDICTABLE 指令编码、原子操作、未分配指令），验证器一律拒绝。
   - x86-64 更复杂：使用 Binary Decision Diagram（BDD）枚举合法指令集（~100 基础指令 + 125 SSE2 SIMD）；对未定义 flag 进行数据流分析（flags analysis，Algorithm 1），拒绝可能读取未定义 flag 的程序；对可能产生未定义结果的指令（SHLD/SHRD/BSR/BSF）要求前置 guard 序列。
   - 使用 **对齐 bundle**（aligned bundles，32 字节/x86-64）防止跳转到指令中间，配合 WˆX 内存保护。

2. **确定性计量（Deterministic Metering）**
   - **Timer-based metering**：每个 basic block 的入口检查计数器寄存器，overhead ~19%，消除了所有 gas 检测（无分支开销），但需要额外 bundle 对齐（8B bundle on Arm64）。
   - **Branch-based metering**：每个 basic block 结尾通过减计数器并检查来计量，overhead ~20–40%；x86-64 更贵（需保存/恢复 flags）。
   - 两种方式均可由验证器静态验证，保证计量本身是确定性的。

3. **位置无关代码（Position-Oblivious Code，POC）**
   - 在 LFI 基础上增加约束：程序无法观测到自己的绝对加载地址。
   - 验证器确保保留寄存器（含绝对地址）只能以 32 位偏移量方式被读取（如 `w30` 而非 `x30`）；PC 相对寻址指令后必须立即清零高 32 位；`call` 指令被改写为 `lea+push+jmp` 序列以避免暴露绝对地址。
   - POC 程序无论加载到何处，输出结果完全一致，从而兼容 LFI 的共享地址空间设计。

---

## 四、实现细节

**编译流程**：`.c` → `Compile（LLVM/GCC）` → `.s` → `Rewrite（汇编重写器）` → `.s` → `Assemble+Link` → `.elf` → `Verify（静态验证器）` → `Run（native）`。

**验证器**：线性时间，独立可执行程序，TCB 极小。x86-64 使用 Fadec 编码器构建 BDD，存储 < 200KiB。Arm64 验证器更简单（固定宽度指令，无 bundle 对齐需求）。

**CPU Fuzzer**：对多种微架构（5+ 种）分发随机程序进行测试，验证跨微架构行为一致性。不属于可信 TCB，仅作测试辅助。

**Groundhog 集成**：
- 预分配沙箱内存（128KiB 代码 + 128KiB 数据），只在首次使用时设置内存保护（mprotect），复用时仅 memset 清零，无额外系统调用；
- 使用 page aliasing（in-memory files）将代码段同时映射为 read-execute（沙箱视角）和 read-write（运行时视角），避免权限切换；
- Arm64 需要 instruction cache flush（成为启动瓶颈，~15µs on M2）；
- x86-64 启动时间 ~2µs（无 icache flush）。

---

## 五、实验结果

**实验平台**：Mac Mini M2（Arm64，Debian Asahi Linux）、AMD Ryzen 9 7950X（x86-64，Ubuntu），均固定主频、隔离核心。

**SPEC CPU2017 整数基准（通用性能开销）**：

| 配置 | x86-64 geomean 开销 | Arm64 geomean 开销 |
|---|---|---|
| DeCl-HW | ~4.4% | ~0%（无重写） |
| DeCl-LFI-POC | ~9.3% | ~9.4% |
| LFI（基准） | ~9.5% | ~8.5% |
| DeCl-LFI-timer | ~19.2% | ~19.1% |
| DeCl-LFI-branch | ~39.3% | ~24.1% |
| Wasmtime（无计量） | ~56.3% | ~82.2% |
| Wasmtime-fuel（有计量） | ~76.5% | ~109% |

DeCl 在计量配置下比等价 Wasmtime 方案开销减少 **2× 以上**。

**智能合约（Groundhog）吞吐量**：DeCl 在 Ed25519 签名验证负载下（约 80–90% 时间在密码学计算），能同时实现低启动延迟（< 15µs）和低 CPU 开销，而 Wasm3 在沙箱内密码学时性能骤降，Wasmtime 受启动开销限制扩展性。

**零知识证明验证（Groth16/Plonk，7950X/M2）**：

| 系统 | Groth16 (x64) | Plonk (x64) | Groth16 (A64) | Plonk (A64) |
|---|---|---|---|---|
| Native | 0.313s | 0.588s | 0.189s | 0.338s |
| DeCl-timer | 0.344s（1.10×） | 0.650s（1.11×） | 0.202s（1.07×） | 0.365s（1.08×） |
| Wasmtime-fuel | 0.745s（2.38×） | 1.38s（2.34×） | 0.587s（3.11×） | 1.08s（3.07×） |
| Wasm3 | 10.5s（33.7×） | 20.4s（34.7×） | 5.38s（28.5×） | 10.1s（30.0×） |

DeCl 使链上零知识证明验证速度提升 **2×–30×**（相比现有 WebAssembly 方案）。

---

## 六、批判性分析

**1. 浮点排除的代价被低估**：论文将浮点支持完全排除在外，称其为"out of scope"。但现实中许多密码学实现（包括一些 elliptic curve 方案）依赖 FP/SIMD 混合指令，而 x86-64/Arm64 工具链无法分离 FP 和 SIMD。论文提到只能在验证器中用 nop 替换浮点指令，这对现有合约代码是破坏性变更，实际部署障碍被一笔带过。

**2. 基准测试局限性**：SPEC CPU2017 只使用了 8 个 benchmark（受 LFI 4GiB 内存限制和浮点排除影响），且只用 rate 模式。论文自称 FP 基准反而有更低开销（因为少用整数寄存器），却又把 FP 排除——这有选择性展示有利数据的嫌疑。

**3. TCB 声称的可信度**：论文核心卖点是"小 TCB、无需信任编译器"。但验证器本身的手写 x86-64 flags 分析表（来自 Intel 手册）、BDD 指令集、以及 ISA 特殊情况处理都是复杂代码，实际 TCB 的安全性依赖于这些手工维护代码的正确性，与作者声称的"简单高效"存在张力。Intel 手册对 BSR/BSF 的 underdefined 行为在 2024 年 10 月才更新，验证器的 ISA 理解可能持续滞后于硬件文档更新。

**4. 硬件漏洞风险轻描淡写**：论文承认硬件 bug 在 DeCl 下比 JIT 更易利用（因为 DeCl 直接运行 native 代码），但随后用"智能合约已有 BFT 系统容错"来一笔带过。实际上，一个针对特定 CPU 微架构的确定性硬件漏洞（如 Zenbleed、Downfall）可以导致同一微架构的所有节点产生相同的错误输出，BFT 无法检测。

**5. 启动延迟优化的可持续性**：15µs 的 Arm64 启动延迟主要来自 icache flush，这是架构约束，很难从根本上消除。Groundhog 代码缓存优化（复用已验证合约代码）未实现，当前评测实际上处于每次都冷启动的状态，对常见合约的真实吞吐量评估不够完整。

---

## 七、总结

DeCl 提出了一种新颖的机器码级确定性强制方案：通过扩展 SFI 的二进制分析技术，设计轻量级静态验证器，使 x86-64/Arm64 本机代码可被直接验证为确定性程序，从而在不依赖可信编译器/解释器的前提下运行智能合约。在性能上，DeCl 显著优于 WebAssembly JIT 方案，计量开销仅约 15–40%，零知识证明等计算密集型合约性能提升 2×–30×。主要局限在于：仅支持 x86-64 和 Arm64、浮点支持缺失、硬件漏洞对确定性保证构成潜在威胁。该工作对需要在效率和安全间取得平衡的区块链智能合约执行引擎有直接实用价值。
