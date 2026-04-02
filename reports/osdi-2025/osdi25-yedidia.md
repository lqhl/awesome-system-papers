# Deterministic Client: Enforcing Determinism on Untrusted Machine Code

**作者**：Zachary Yedidia (Stanford University), Geoffrey Ramseyer (Stanford University & Stellar Development Foundation), David Mazières (Stanford University)
**会议**：OSDI 2025 (19th USENIX Symposium on Operating Systems Design and Implementation)
**链接**：https://www.usenix.org/conference/osdi25/presentation/yedidia
**源文件**：[[osdi25-yedidia.pdf]]

---

## 一、背景

智能合约是区块链系统的核心执行单元，由完全不受信任的第三方上传，但必须在所有诚实节点上产生完全一致的执行结果（确定性）。随着智能合约日益成为数字货币系统的支柱，其性能变得至关重要。

现有智能合约沙箱方案均采用**语言级方法**：定义一种具有确定性语义的中间语言（如 WebAssembly 或 EVM 字节码），然后通过受信的解释器或 JIT 编译器执行。这种方案虽然保证了确定性，但存在性能瓶颈和安全依赖——受信代码库（TCB）庞大，且 JIT 编译器和解释器本身曾多次出现严重安全漏洞。

Software Fault Isolation（SFI）是一种成熟的二进制分析技术，长期用于保证内存隔离，但此前从未被应用于保证确定性。

---

## 二、要解决的问题

1. **性能瓶颈**：解释器执行智能合约比原生代码慢约 30×，JIT 编译器也慢约 2×，且 JIT 编译器启动延迟较高，影响短时合约的吞吐量。
2. **受信代码库过大**：WebAssembly JIT 编译器（如 Cranelift/Wasmtime）是复杂的大型软件系统，存在已知安全漏洞（如 CVE-2021-32629、CVE-2023-26489），将其全部纳入 TCB 风险极高。
3. **确定性计量（metering）**：智能合约需要限制执行时间（gas），但传统 timer interrupt 是非确定性的，可能导致副作用不一致，进而造成状态机副本间的分歧。
4. **可移植性 vs 性能的取舍**：语言级方案（WebAssembly）天然可移植，但牺牲了原生代码性能；直接执行原生代码则需要解决确定性保证问题。

---

## 三、洞察与设计

**关键洞察**：SFI 中用于保证内存隔离的二进制分析技术——静态验证器配合对齐 bundle——可以被扩展为保证更强的属性（确定性），从而将确定性检查从编译器/解释器层面下推到机器码层面。这意味着不需要信任编译器，只需信任一个简单的线性时间验证器。

基于这一洞察，DeCl 的核心设计包含三个组件：

### 1. 确定性指令执行
- 构建 x86-64 和 Arm64 的**确定性指令子集**。验证器只接受已知语义完全确定的指令，拒绝所有未知指令。
- 对于有条件产生未定义结果的指令（如 SHLD 在移位量过大时），通过 rewriter 插入 guard 指令强制输入合法。
- 对于 x86-64 的 undefined flags 问题，实现基于数据流的 flags 分析（Algorithm 1），确保无指令读取未定义状态的标志位。

### 2. 确定性计量
两种机制：
- **Branch-based metering**：在每个基本块末尾插入 gas 扣减和检查序列，用保留寄存器（x23/%r12）维护 gas 计数器。利用 aligned bundle 保证计量代码不可被跳过。
- **Timer-based metering**：仅在基本块末尾扣减 gas（不做检查），利用 timer interrupt + runtime call 时的 gas 检查实现确定性抢占——因为只有 runtime call 才能产生外部可见副作用。

### 3. Position-Oblivious Code（POC）与 LFI 集成
- 与 LFI（Lightweight Fault Isolation）结合，所有沙箱共享地址空间，实现极快的沙箱启动。
- 引入 POC，确保程序无法感知自身加载地址（仅观察 32-bit offset），消除因地址分配非确定性导致的行为差异。

---

## 四、实现细节

**编译流程**：`.c → .s（LLVM/GCC）→ .s（rewriter 重写）→ .elf（汇编+链接）→ 验证 → 原生执行`。Rewriter 在汇编层面操作，插入 guard 指令、metering 序列、bundle padding。

**验证器**：
- 独立程序，复杂度有限，运行于线性时间
- x86-64：使用 Fadec encoder 生成的 BDD（<200KiB）限制指令到已知可编码子集，约 100 条基础指令 + 125 条 SSE2 SIMD 指令
- Arm64：约 180 条基础指令 + 430 条 SIMD 指令（Armv8.0）
- 排除所有浮点指令（认为大部分浮点可安全支持，但留作 future work）

**LFI 集成细节**：
- 每个沙箱 4GiB 区域，128KiB code + 128KiB data
- 预分配沙箱避免 mmap/mprotect 系统调用和 TLB shootdown
- 使用 page aliasing（in-memory files）实现代码区域的 read-execute + read-write 双映射
- 空程序 load+execute+exit 延迟：M2 上 15µs，AMD 7950X 上 2µs

**CPU Fuzzer**：随机采样指令构建验证后程序，在多种微架构（5+）上执行比较结果，用于发现验证器遗漏的非确定性。

---

## 五、实验结果

**平台**：AMD Ryzen 9 7950X（x86-64），Apple M2 Mac Mini（Arm64）

### SPEC CPU2017 Integer 开销

| 配置 | x86-64 | Arm64 |
|------|--------|-------|
| DeCl-HW | 4.4% | ~0% |
| LFI (baseline) | 9.5% | 8.5% |
| DeCl-LFI-POC | 9.3% | 9.4% |
| DeCl-LFI-timer | 19.2% | 19.1% |
| DeCl-LFI-branch | 39.3% | 24.1% |
| Wasmtime (无 fuel) | 56.3% | 82.2% |
| Wasmtime-fuel | 76.5% | 109% |

DeCl 在所有配置下均显著优于 Wasmtime，metered 场景下开销不到 Wasmtime 的一半。

### Groundhog 智能合约引擎集成

- 支付交易吞吐量：DeCl 可线性扩展至 192 核，Wasmtime 受限于启动开销出现扩展瓶颈
- 用户可在沙箱内实现自定义密码学原语（如 Ed25519），不依赖 runtime 内置

### 零知识证明验证

| 系统 | Groth16 (x64) | Plonk (x64) |
|------|---------------|-------------|
| Native | 0.313s | 0.588s |
| DeCl-timer | 0.344s (1.10×) | 0.650s (1.11×) |
| DeCl-branch | 0.407s (1.30×) | 0.763s (1.30×) |
| Wasmtime-fuel | 0.745s (2.38×) | 1.38s (2.34×) |
| Wasm3 | 10.5s (33.7×) | 20.4s (34.7×) |

---

## 六、批判性分析

1. **浮点支持完全缺失**：论文将整个浮点指令集排除在外，声称"大部分浮点操作是确定性的，可以安全支持"，但未提供任何量化分析。SPEC 浮点 benchmark 全部被排除，且现实中许多智能合约（DeFi 中的定价计算、数值优化）依赖浮点运算。这不只是"future work"——它显著限制了 DeCl 的实际适用性。

2. **SPEC 基准选择偏差**：由于 LFI 的 4GiB 内存限制，只能运行 SPEC rate（而非 speed），最终只跑了 8 个 benchmark。样本量较小，且未包含内存密集型工作负载，难以全面反映实际开销。

3. **硬件正确性假设的脆弱性**：论文承认依赖硬件在接受的指令子集内行为正确，并提到可通过补丁验证器来应对硬件 bug。但实际操作中，发现硬件 bug 后需要禁用或模拟受影响的已部署合约——对于去中心化系统这可能需要昂贵的协调升级，论文对此困难轻描淡写。

4. **Branch-based metering 在 x86-64 上开销显著**：flags-preserving 的 metering 序列在 x86-64 上导致 ~39% 的 geomean 开销，部分 benchmark（如 gcc）高达 80%+。论文承认"有更多优化空间"，但未给出具体方案或上限分析。

5. **与 Wasmtime 的比较不够公平**：Wasmtime 提供完整的浮点支持和跨架构可移植性。DeCl 限制到单一架构的整数子集后再比性能，优势部分来自缩小了问题范围。

6. **Position-Oblivious Code 的安全论证**：POC 通过限制只能观察 32-bit offset 来隐藏加载地址。但论文未讨论侧信道泄漏的可能性——虽然显式 timer 被移除，但 cache 行为、branch predictor 状态等微架构侧信道是否完全被 DeCl 的确定性保证覆盖，值得更深入分析。

---

## 七、AI Infra / MLSys 视角

DeCl 本身面向智能合约确定性执行，但其核心技术——在原生机器码上通过静态验证实施强安全属性——对 AI Infra 有潜在启发：

1. **确定性训练/推理的硬件级保证**：AI 系统中的确定性复现（reproducibility）是长期痛点。DeCl 的思路——枚举确定性指令子集并通过验证器强制执行——可以用于构建"确定性执行模式"，保证同一模型在不同机器上的 bit-exact 结果，尤其在 integer quantization 推理场景下。

2. **轻量级沙箱用于 UDF 执行**：AI 推理服务中用户自定义的 pre/post-processing 逻辑（如 NVIDIA Triton 的 model ensemble）需要安全隔离执行。DeCl 的 15µs 沙箱启动时间和 ~20% 的 metered 执行开销，远优于现有 WebAssembly 方案，值得在 serving pipeline 中探索。

3. **可验证的原生代码执行**：当前 ML 编译器（TVM, XLA, Triton）生成的 kernel 代码通常不经过安全验证。DeCl 的验证器思路可扩展为 ML kernel 的安全性检查——例如保证 kernel 不会越界访问 GPU 内存（虽然 DeCl 目前只支持 CPU）。

4. **Future work 方向**：将 DeCl 的 SFI + 确定性验证思路扩展到 RISC-V（论文已提及 Ethereum 社区提案），进而为 RISC-V AI 加速器上的确定性执行提供基础。

---

## 八、总结

DeCl 通过将 SFI 的二进制分析技术从内存隔离扩展到确定性保证，首次实现了在不信任编译器的前提下、以接近原生速度（~20% metered 开销）执行确定性机器码的沙箱系统。其核心优势在于极小的 TCB（线性时间验证器）、快速沙箱启动（2-15µs）、良好的多核扩展性，以及允许用户在沙箱内实现自定义密码学原语。主要局限是缺乏浮点支持、单架构绑定（失去可移植性）、以及对硬件正确性的依赖。最适合对性能和启动延迟敏感的智能合约执行场景，特别是需要高吞吐量的 ZK proof 验证和支付交易。
