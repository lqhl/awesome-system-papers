---
type: paper
name: Mohabi
full_title: "Mohabi: Disaggregating and Sandboxing the Firefox JavaScript Engine"
authors: [Abhishek Sharma, Anand Balaji, Zachary Yedidia, Anthony Du, Taehyun Noh, Iain Ireland, Jan de Mooij, Matthew Gaudet, Tal Garfinkel, Deian Stefan, Hovav Shacham, Shravan Narayan]
venue: OSDI
year: 2026
tags: [browser-security, javascript-engine, software-fault-isolation, jit-sandboxing, firefox]
source_pdf: "[[osdi26-sharma.pdf]]"
source_md: "[[osdi26-sharma]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-06-16
---

# 将 Firefox 的 JavaScript 引擎隔离并沙箱化：Mohabi（OSDI 2026）

> **原题**：Mohabi: Disaggregating and Sandboxing the Firefox JavaScript Engine

> **一句话总结**：Mohabi 把 Firefox 的 SpiderMonkey 与浏览器其余部分拆开，再用支持大内存和 JIT 动态代码的 MH-LFI 软件故障隔离（SFI）沙箱保护它；在 Firefox ESR-115 上 Speedometer 3.1 和 JetStream 2.2 的开销分别为 24.43% 和 24.82%，在 SPEC 2017 上 MH-LFI 的开销为 5.9%–6.6%。

## 问题与动机

JavaScript 引擎同时包含解释器、多个分层 JIT、WebAssembly 和正则表达式执行引擎。优化器会依据运行时类型信息删除边界检查，因而内存安全漏洞可能出现在运行时生成的机器码中。仅靠 C++ 类型系统或关闭 JIT 都不能覆盖全部攻击面；关闭 JIT 还会牺牲 SpiderMonkey 约 3.5–7× 的性能（引言）。

浏览器已有多进程和站点隔离，但把 SpiderMonkey 单独放进进程会让 DOM、事件循环和 JSAPI 的高频交互都经过 IPC。Mohabi 选择进程内隔离：把 SpiderMonkey 的控制流、栈、堆和 JIT 代码放入 SFI 沙箱，只允许经过显式跳板的交互。

论文的范围是“引擎被攻破后不能任意破坏浏览器其余内存或调用危险系统调用”。它没有声称消除 SpiderMonkey 内部的内存破坏，也没有完成所有跨边界数据的自动检查。

## 关键观察 / 隐含假设

- **观察 1：浏览器的站点隔离减少了读隔离要求。** 内容进程通常不包含其他站点的秘密，因此 Mohabi 在默认部署中主要限制 sandboxed SpiderMonkey 的写入；任意读取不会直接泄露其他站点秘密（§3）。
  - **依赖假设**：站点隔离和浏览器进程中的秘密布局保持成立。
  - **可能失效场景**：UI、扩展或其他进程中的敏感数据进入同一进程，或未来浏览器改变站点隔离边界时，只做写隔离可能不足。
- **观察 2：JS 引擎的 JIT 通常共享架构相关的 MacroAssembler 后端。** SpiderMonkey 的多个 JIT 通过同一个 x86-64 发射后端生成机器码，Mohabi 可在这个 choke point 统一插入 SFI 检查（§3、§6.1）。
  - **依赖假设**：所有可执行 JIT 路径都经过被修改的后端；新增后端或低级汇编路径不会绕过它。
  - **证据强度**：中。论文报告了对 SpiderMonkey 各 JIT 的改造，但验证器仍在原型阶段发现了低级汇编漏插间接跳转掩码的情况（§6.3）。
- **观察 3：浏览器边界代码大量由 WebIDL 等工具自动生成。** 这使得 DOM reflector 的回调注册、指针表查验和边界 sanitization 可以集中修改生成器，而非手改数千个调用点（§4.3、§4.6）。
  - **依赖假设**：关键跨边界接口仍由可控的生成器覆盖，手写或特殊路径数量有限。
  - **可能失效场景**：未生成的 JSAPI、共享对象或隐藏回调没有同样的检查；论文明确把完整边界覆盖列为开放问题（§8）。
- **假设 1：必须支持超过 4 GiB 的 sandbox memory。** ArrayBuffers 和 WebAssembly 使固定 4 GiB 的传统 SFI 沙箱不适合现代浏览器；MH-LFI 因而采用对齐的 256 GiB 连续区域（§5.1）。这是部署硬件和虚拟地址空间足够宽的前提，论文主要在 x86-64 上验证。

## 核心方法

Mohabi 先把 SpiderMonkey 编译成带私有 libc 的独立库，并为每个 Firefox 进程实例化 sandbox。Firefox 到引擎的调用经过 springboard，切换栈、保存寄存器并设置 SFI 保留寄存器；引擎回调 Firefox 则经过 trampoline。自动生成的 stub library 为 2,250 个 JSAPI 函数建立跳转表，避免修改其在 Firefox 中数量更多的调用点（§4.1、§4.4）。

跨边界数据采用类型化拆分。split-allocation type 把一个逻辑对象的字段分放在 sandbox 内外，例如让 GC 能更新 `Rooted<T>` 的对象指针，同时保护其 root 链接字段。DOM reflector 使用 pointer table 保存合法 DOM 指针、类型和引用计数；自动生成的 binding code 在调用宿主对象前检查指针是否存在且类型匹配（§4.2、§4.6）。virtual trampoline 和 virtual springboard 则处理 C++ 虚调用跨边界分派，覆盖 Promise job queue、Proxy、外部 DOM 字符串和 GC tracing 等约 20 个类（§4.5）。

MH-LFI 是建立在 LFI 之上的 x86-64 assembly rewriter。它在写操作前把地址掩码到 sandbox，限制间接跳转落在 32-byte bundle 起点，并把系统调用改成由可信 runtime 检查的函数调用。返回地址也先弹出、掩码后再跳转，以避免并发线程修改栈上的返回地址。它不要求编译器分叉：只对 clang/LLVM 做约 600 行修改，主要工作由编译产物重写器完成（§5.1、§5.4）。

JIT 代码通过修改 SpiderMonkey 的 MacroAssembler 后端生成同样的掩码和 bundle 对齐指令。为防止可执行页中的常量被解释为 gadget，常量被放入 bundle 的字节 1–31，字节 0 使用 `HLT`。JIT 页更新采用 dual mapping：sandbox 内映射为只读可执行，外部 shadow mapping 暂时可写；runtime 只验证新增代码，再恢复执行权限（§6.1–§6.2）。

二进制 validator 不把 AOT/JIT 编译器当作完整可信根。它在执行前检查代码页中的数据访问、控制流和保留寄存器规则。验证器曾发现零填充 `0x00`、未掩码间接跳转和 Wasm trap 恢复覆盖 `r14` 等问题，说明它不仅是安全机制，也是集成完整性检查（§6.3）。

## 设计取舍

- **进程内 SFI 换取低交互成本**：避免 IPC，但需要处理 Firefox 与 SpiderMonkey 之间大量共享对象、回调、虚调用和 GC 指针，边界代码成为新的审计面。
- **写隔离换取性能**：在站点隔离假设下不限制读取，减少检查；若同一进程存在跨站秘密，安全结论需要重新评估。
- **二进制重写器换取编译器可维护性**：可跟随 LLVM 版本升级，代价是需要稳定的汇编语义、寄存器约束和 validator；x86 指令前缀、bundle 和 `pext` 优化也增加实现复杂度。
- **dual mapping 换取 JIT 更新性能**：减少权限切换次数且只验证新增代码，但 runtime 的页映射和并发协议必须正确处理，论文未给出形式化证明。

## 实验与结果

- 在 Intel i9-13900K、32 GiB RAM、Ubuntu 24.04、2.2 GHz 固定频率、两个隔离 CPU 核上，Firefox ESR-115 的 Speedometer 3.1 中 Mohabi 开销为 **24.43%**，JetStream 2.2 中为 **24.82%**；两项均取 15 次运行的中位数（§7、表 2）。
- Speedometer 的组件拆分显示，后向控制流保护是主要开销来源；关闭 JIT 作为参照的代价更高，论文同时指出日常访问 YouTube 和 Reddit 未观察到明显变慢（§7.1、图 5）。
- 在 SPEC 2017、2.2 GHz 单核上，与 NaCl 的兼容 4 GiB 配置比较，MH-LFI 开销为 **6.6%**，NaCl 为 **22.3%**；Mohabi 使用的大内存、只写保护配置开销为 **5.9%**（§7.2、图 6）。
- MH-LFI 的优化使其性能提升约 **6%–8%**；其 validator 吞吐高于 NaCl，论文将主要原因归于现代 Fadec x86 解码器（附录、表 3、图 9）。
- 论文分析了代码指针劫持、可执行内存覆盖、JIT spray、并发代码篡改和危险系统调用等攻击路径，并以数个 2026 年 Firefox SpiderMonkey 漏洞为例说明：若边界检查完整，内存破坏会被限制在 sandbox 内（§7.3）。这部分是设计分析，不是长期生产攻击评测。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Mohabi 能把完整 SpiderMonkey 放入 Firefox 的进程内 SFI sandbox | disaggregation 类型、stub library、reflector、trampoline 和 springboard 的实现描述（§4） | Firefox ESR-115；边界覆盖尚未完整自动证明 | 中 |
| MH-LFI 能支持大内存 sandbox 和动态 JIT 代码 | 256 GiB sandbox 方案、dual mapping、JIT MacroAssembler 与 validator（§5–§6） | x86-64；未覆盖 ARM64/RISC-V；并发安全依赖 runtime 实现 | 中 |
| 安全机制带来可用但非零的浏览器开销 | Speedometer 3.1 为 24.43%，JetStream 2.2 为 24.82%，表 2 | 单台 i9-13900K、固定频率、Firefox ESR-115、15 次中位数 | 强 |
| MH-LFI 的通用 SFI 开销低于 NaCl | SPEC 2017 兼容子集为 6.6% 对 22.3%，图 6 | 不同 clang 版本，按各自基线归一化；不是完整浏览器比较 | 强 |

## 批判性分析

### 论证链条

论文的主链条是闭合的：JS 引擎漏洞持续存在，进程隔离交互成本过高；浏览器已有站点隔离，且 JS 引擎和 binding layer 存在可利用的结构化 choke point；因此可以用 disaggregation 加完整 SFI 约束整个引擎。工程展示覆盖了控制流、GC、DOM、异步队列和 JIT 页更新，不是只在独立 JS shell 上做实验。

但“漏洞被限制在 sandbox”依赖边界 sanitization 的完整性。论文只实现了有限的数据清理层，约 650 行 wrapper 定义和 80 行 DOM 表维护，并明确说完整 JSAPI 覆盖仍是后续工作（§7.3、§8）。因此安全结论更准确地说是：在已检查的边界和正确的 MH-LFI validator/runtime 下，内部内存破坏的影响范围被缩小；它尚未证明 Firefox 全部跨边界路径都满足该条件。

### 假设压力测试

只写隔离依赖站点隔离和秘密不在同一可写进程。扩展、浏览器 UI 和特殊共享内存路径可能改变这一前提。256 GiB 连续区域和地址掩码适合 x86-64，但论文尚未证明虚拟地址碎片、容器限制和其他架构上的部署成本。JIT 代码更新还依赖 dual mapping 的并发协议；论文用设计和 validator 分析 TOCTOU，但没有给出形式化验证或压力测试数据。

### 实验可信度

Speedometer 覆盖端到端浏览器交互，JetStream 便于与旧工作比较，SPEC 2017 则隔离 MH-LFI 的一般开销。固定 CPU 频率、隔离核心和 15 次中位数减少了噪声。仍有三项缺口：Firefox 版本较旧；没有真实的大型 WebAssembly/ArrayBuffer 内存压力结果；安全评估主要是攻击面分析和漏洞回溯，不是 fuzzing、exploit replay 或长期生产数据。NaCl 对比也受编译器版本和兼容 benchmark 子集限制。

### 系统性缺陷

边界检查的可观测性、升级流程和失败恢复没有展开。新增 WebIDL、JSAPI 或手写 binding 时，若生成器和 validator 未覆盖，可能出现安全回归。每个进程的 sandbox instance、线程上下文、私有 libc 和 JIT 页管理也会增加启动、内存映射和调试成本；论文给出了运行时开销，却没有给出这些运维指标。形式化验证被列为可能方向，当前 TCB 仍包括约 6,200 行 runtime、validator、解码器和边界 sanitization。

## 局限与后续工作

- **局限 1：边界覆盖未完成。** 论文没有证明所有 JSAPI、共享对象和宿主回调都经过类型检查；应建立接口清单和自动化覆盖检查，并在 Firefox CI 中对新增 binding 施加失败门槛。
- **局限 2：仅评估 x86-64。** ARM64 和 RISC-V 的固定长度指令、寄存器数量与地址布局不同；需要实现对应 rewriter/validator，并在相同 WebAssembly、JIT 和浏览器工作负载上比较开销。
- **局限 3：真实浏览器负载覆盖有限。** 应加入包含大 ArrayBuffer、WebAssembly、多 Web Worker、长尾页面交互和多标签页的 trace，分别测量 P95/P99 延迟、内存占用、启动时间和 JIT 编译暂停。
- **局限 4：边界与 runtime 的正确性尚未形式化。** 可为 pointer table、springboard/trampoline、dual mapping 和 syscall policy 建立可检查不变量，再用并发 fuzzing 和故障注入验证实现。

## 相关

- **相关概念**：[[Software Fault Isolation]]、[[Control-Flow Integrity]]、[[JIT Compilation]]、[[WebAssembly]]
- **同类系统**：[[NaCl]]、[[Ubercage]]、[[RockJIT]]、[[NoJITsu]]
- **同会议**：[[OSDI-2026]]
