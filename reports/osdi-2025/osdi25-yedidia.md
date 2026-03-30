# DeCl: Deterministic Client - Enforcing Determinism on Untrusted Machine Code

## 论文基本信息

- **标题**: Deterministic Client: Enforcing Determinism on Untrusted Machine Code
- **作者**: Zachary Yedidia, Geoffrey Ramseyer (Stanford University / Stellar Development Foundation), David Mazieres (Stanford University)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/yedidia

## 研究背景与动机

智能合约（Smart Contracts）是当今数字货币系统的支柱，由完全不受信任的各方上传，必须在诚实节点上保证每次运行产生完全一致的结果。现有方法主要依赖语言级沙箱（WebAssembly、EVM 字节码），需要可信的解释器或 JIT 编译器，这引入了巨大的可信计算基（TCB）。

核心矛盾：
- **传统 SFI（软件故障隔离）** 只能保证内存隔离，不能保证确定性
- **语言级沙箱** 需要可信运行时，且通常比原生代码慢
- **硬件** 本身不足以防止所有非确定性指令行为

## 要解决的核心问题

如何在**不需要可信编译器/解释器**的前提下，对不受信任的 x86-64 或 Arm64 机器码实施**确定性**约束，同时保持高性能和快速启动？

## 主要贡献

1. **将 SFI 技术从内存隔离扩展到确定性**：证明通过二进制分析技术（原本用于 SFI）可以验证程序是否属于确定性子集
2. **无需可信翻译层**：程序通过验证后直接作为原生代码运行，消除了对 LLVM/GCC 的信任依赖
3. **两种高效的确定性计量机制**：基于分支的计量（branch-based metering）和基于定时器的计量（timer-based metering）
4. **与 LFI 的集成**：提出位置无关代码（Position-Oblivious Code, POC）方案，使 DeCl 可在 LFI 共享地址空间模型下工作
5. **集成到 Groundhog 智能合约引擎**：相比 JIT 编译提速 2 倍，相比解释执行提速 30 倍；沙箱启动延迟 < 15 微秒

## 研究方法与设计

### 确定性指令集约束

DeCl 仅接受**已知确定性语义的指令**，拒绝任何可能导致非确定性结果的指令。

**Arm64**：相对简单。固定宽度指令（4字节）便于验证，只需拒绝以下情况：
- 含有malformed SBZ/SBO 字段的指令
- 含显式非确定性语义的指令（如 `txr` 返回值依赖独占监视器状态）
- 未分配指令

**x86-64**：更复杂。使用 BDD（Binary Decision Diagram）编码的 FADEC decoder 枚举可接受指令集（约 100 条基础指令 + 125 条 SSE2 SIMD 指令）。

#### 防止未定义结果

对于可能产生未定义结果的指令（如 `SHLD`、`BSR`/`BSF`），rewriter 在指令前插入 guard 序列，确保输入合法：

```
# SHLD 的 guard：确保 %cl < 操作数宽度
and $0xf, %cl     # cl &= 0xf（对 16-bit 数据）
shldl %cl, %ebx, %eax
```

#### 防止未定义标志位

x86-64 中许多指令会修改或产生未定义标志位。通过**数据流分析**（Algorithm 1 FlagsAnalysis）对基本块迭代分析，推导每个基本块出口处哪些标志位是未定义的。若程序读取了未定义标志位则拒绝。

迭代收敛性：论文观察到所有符合规范的 LLVM/GCC 编译程序在 2 次迭代内通过验证。

### 对齐 Bundle

借鉴 PittSFIeld 系统，将指令组织为固定大小的 bundle（x86-64: 32 字节，Arm64: 8-16 字节），所有跳转目标必须 bundle 对齐。这防止了跳转到指令中间执行不同指令序列的可能。

### 确定性计量（Deterministic Metering）

**目标**：程序消耗完 gas 后必须**确定性**终止，而非由定时器随机中断。

**基于分支的计量**（Branch-based）：
- 在每个基本块末尾插入 metering 序列（递减 gas 计数器、检查溢出）
- x86-64 利用 `jrcxz`（仅当 %rcx=0 时跳转，不依赖标志位）
- Arm64 利用 `tbz`（按位测试跳转）
- 通过 bundle 对齐确保无法跳过 metering 指令

**基于定时器的计量**（Timer-based）：
- 结合 gas 计数器和定时器中断
- 关键洞察：若 gas 为负则程序无任何外部可见效果——因此在 runtime call 前检查 gas 即可

### 与 LFI 集成：位置无关代码（POC）

LFI 中所有沙箱共享同一地址空间，程序可以访问其基地址。DeCl 要求程序不能依赖其加载地址——即**位置无关**。Rewriter 确保：
- 保留寄存器（x21/%r14）存沙箱基址，但程序从不直接观察
- 所有地址通过 32 位偏移访问（零扩展 top 32 bits）
- `call` 指令被重写为不暴露绝对地址的序列

## 关键实现细节

### 多配置支持

| 配置 | 隔离方式 | 计量 | 备注 |
|------|---------|------|------|
| DeCl-HW | 硬件页表 | 无 | 最小开销，需自定义内核 |
| DeCl-LFI | LFI 软件隔离 | 无 | 进程内快速启动 |
| DeCl-metered | LFI/HW | 分支或定时器 | 智能合约必需 |

### Reserved Registers

不同配置保留不同寄存器（x23/%r12 用于 gas，x24/%r11 用于 bundle 对齐跳转目标等），verifier 确保程序不使用这些寄存器。

### CPU Fuzzing

论文描述了一个 fuzzer，在多种微架构上对随机指令组合进行 fuzz，验证 verifier 的正确性。Fuzzer 快速发现未定义标志位和未定义结果的 case。

## 实验结果与分析

### SPEC CPU 2017（整数基准）

| 配置 | x86-64 平均开销 | Arm64 平均开销 |
|------|--------------|-------------|
| DeCl-HW | ~5% | ~5% |
| DeCl-LFI-POC | ~9% | ~8% |
| DeCl-LFI-metered | ~20% | ~20% |
| LFI（参考） | ~8% | ~8% |

DeCl-LFI-POC 性能与原始 LFI 几乎相同，额外开销仅来自确定性约束而非 POC 本身。带计量的配置开销约 20%。

### Groundhog 智能合约引擎

- **启动时间**：沙箱加载和执行 < 15 微秒
- **执行速度**：相比 JIT 编译提速 ~2 倍；相比解释执行提速 ~30 倍
- **可扩展性**：加载沙箱不影响 Groundhog 的整体可扩展性

### 技术洞察

- DeCl-LFI 在某些工作负载上反而**优于** VM-RR（RocksDB 随机读取/搜索），原因是 VM-RR 在处理高频 RDTSC 指令时陷入频繁的 VM exit
- 在多核场景（>8 核）下，KRR 自身的锁竞争成为瓶颈，性能不再随核数提升

## 潜在问题与局限性

1. **浮点运算缺失**：DeCl 完全不支持浮点指令（认为其不确定性过强），限制了适用场景
2. **x86-64 复杂性**：Verifier 依赖 BDD 编码的 decoder，跨 ISA 版本维护成本高
3. **Position-Oblivious Code 的限制**：要求所有绝对地址只能通过保留寄存器访问，这限制了某些合法的程序模式
4. **未定义标志位分析的完备性**：依赖于对 Intel/ARM 手册的逐条分析，若手册本身存在错误或歧义，Verifier 可能接受非法程序
5. **Fuzzer 覆盖范围**：虽然运行在多个微架构上，但无法穷举所有 CPU 实现
6. **与自定义内核绑定**：DeCl-HW 配置需要特殊内核支持，限制了通用性

## 未来工作方向

- 支持浮点运算的确定性子集（如仅限加/减/乘，排除 rsqrtss 等）
- 跨 ISA 版本的 verifier 自动化维护
- 动态重编译以支持老旧处理器

## 个人评注

1. **核心贡献扎实**：将 SFI 技术从内存隔离扩展到确定性是一个简洁有力的思想创新。无需信任编译器这一特性极具实用价值。

2. **潜在夸大**：
   - 摘要称"DeCl is able to combine and improve upon the benefits of both interpreters and JIT compilers"，但实际上 DeCl 的优势来自"跳过解释/JIT"而非真正的组合
   - 在某些 SPEC 基准上开销达 40%+（如 xz），20% 的平均开销掩盖了长尾

3. **技术细节严谨**：未定义标志位的数据流分析（Algorithm 1）是本文最具技术深度的部分，iterative analysis 确保了正确性。

4. **与 Groundhog 的集成验证了真实场景适用性**：智能合约是确定性需求的完美场景，DeCl 在此找到了最佳应用。

5. **Intel SDM 与伪代码不一致**：论文脚注提到截至 2024 年 10 月 Intel SDM 更新了 BSR/BSF 的行为（从"未定义"变为"不变"），但伪代码仍写"未定义"，Verifier 仍按保守处理。这种不一致是文档问题，不会影响安全性，但值得关注。
