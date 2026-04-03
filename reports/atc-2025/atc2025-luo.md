# MemoryTrap: Booby Trapping Memory to Counter Memory Disclosure Attacks with Hardware Support

**作者**：Chenke Luo (Wuhan University & Tulane University), Jiang Ming (Tulane University), Dongpeng Xu (University of New Hampshire), Guojun Peng, Jianming Fu (Wuhan University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/luo
**源文件**：[[atc2025-luo.pdf]]

---

## 一、背景

Code-reuse 攻击（尤其是 Return-Oriented Programming, ROP）通过从程序可执行内存中搜索可复用的 code gadgets 来构造恶意 payload，对现代系统的 Data Execution Prevention (DEP / W⊕X) 保护构成严重威胁。随着 Address Space Layout Randomization (ASLR) 和 fine-grained code randomization 的部署，攻击者进化为 Just-In-Time ROP (JIT-ROP)——在运行时通过 memory disclosure 漏洞实时搜索 gadgets，使静态随机化失效。

现有防御手段主要分两类：Execute-only Memory (XoM) 禁止读取代码页，以及 Destructive Code Reads (DCR) 允许读取但销毁已读代码。两类方法各有明显缺陷，亟需新的防御思路。

---

## 二、要解决的问题

1. **XoM 与 code-data 混合不兼容**：XoM 要求严格分离代码和数据，但实际程序中代码段内嵌数据非常普遍（jump tables、手写汇编中的常量、JIT 编译生成的 code+data 混合页等）。XoM 会将合法的 data-in-code 读取误判为攻击，导致程序崩溃。
2. **DCR 无法抵御 Code Inference 攻击**：DCR 在代码被读后销毁，但攻击者可以维护多份代码副本（JIT cloning、shared library reloading、process reloading）或通过 implicit reads 推断未读代码内容，绕过 DCR 保护。
3. **硬件方案过重**：CHERI 需要重新设计 ISA、新增指令和寄存器、128-bit 指针，部署成本极高。基于 Intel EPT 的方案（如 Readactor）性能开销仍然高于 MPK。
4. **缺少对 JIT compiled code 的保护**：现有方案主要针对静态编译的应用程序，对 JavaScript JIT 引擎等动态生成代码的保护支持不足。

---

## 三、洞察与设计

**关键洞察**：JIT-ROP 攻击者必须在有限时间窗口内遍历大量代码页来收集足够的 gadgets，而这种遍历行为具有可预测的空间模式——攻击者以 4KB（一个内存页）为粒度搜索，且 gadgets 之间通常间隔数 KB 到数百 KB。如果在代码中密集插入不可读的"陷阱"（booby traps），使得任意两个相邻陷阱之间的距离小于一个内存页（4KB），攻击者在遍历代码页搜索 gadgets 时就必然触发陷阱，而正常程序执行可以通过 JMP 指令跳过这些陷阱。

基于此洞察，MemoryTrap 的核心设计为：

1. **编译时插入 Booby Traps**：通过 LLVM pass 在每个函数中至少插入一个 booby trap（5-30 个 NOP 指令的代码片段），大于 4KB 的函数每 4KB 额外插入一个。陷阱前加 JMP 指令使正常执行路径跳过。插入位置随机化以防攻击者预测。

2. **利用 Intel MPK 实现细粒度权限控制**：通过 Memory Protection Keys 将代码页设为 execute-only。合法的 data-in-code 读取通过 exception handler 单步执行处理——临时恢复读权限、执行一条读指令、再关闭权限。读取 booby trap 区域则立即终止进程。

3. **新 ELF 格式**：在 ELF header 中新增 MTRAP_ENABLE 标志，新增 `.mtrap` section 存储所有 booby traps 的地址范围，供内核加载时初始化保护。

4. **支持三类代码**：应用程序通过自定义 kernel loader 加载；共享库通过修改 GNU C Library loader + mTrap syscalls 注册；JIT 代码通过修改 V8 TurboFan 在 IR 级插入陷阱并通过 syscall 注册。

5. **天然抗 Code Inference 攻击**：booby traps 嵌入代码本身，代码复制（cloning）时陷阱随之复制，因此基于多副本的推理攻击无法规避。

---

## 四、实现细节

- **实现平台**：Linux kernel 5.10.11, LLVM 13.0.1, V8 9.7, GNU C Library 2.31
- **内核修改**：仅 312 行代码，包含自定义 loader、exception handler 和三个新 syscall（mtrap_enable、mtrap_add、mtrap_delete）
- **内核数据结构**：在 `task_struct` 中新增 `mtrap_info_t` 成员，存储 enable 标志、trap 标志、PKey、booby trap 数量和列表
- **Booby trap 格式**：每个 trap 由 start/end 地址对表示，存储在 `.mtrap` ELF section 中
- **Exception handler 流程**：代码页读操作触发 page fault → 检查目标地址是否在 booby trap 范围 → 若是则终止进程并保存取证信息 → 若不是（合法 data-in-code）则临时恢复读权限、设置 single-step trap flag 执行一条指令后重新关闭权限
- **JIT 代码保护**：修改 TurboFan 在 IR 级插入 booby traps，编译后通过 MPK 设置 execute-only，通过 mtrap_add syscall 注册。JIT 代码更新时临时恢复读写权限，abandon 时调用 mtrap_delete 注销
- **兼容 fine-grained randomization**：适配 CCR（Compiler-assisted Code Randomization），随机化代码布局时同步更新 booby trap 地址

---

## 五、实验结果

**测试平台**：Intel i9-13900KF 24 核 CPU，64GB RAM

### 安全评估

| 实验 | 关键结果 |
|------|---------|
| Nginx CVE-2013-2028 JIT-ROP | breadth-first 平均披露 657 bytes、depth-first 299 bytes 即触发陷阱；40,780 次遍历中仅 25+14 次找到至多 1 个 gadget |
| MemoryTrap-aware 策略 | 间隔 200/300/500 bytes 读取，结果与普通策略一致（636-678 bytes），booby trap 对攻击者不透明 |
| JIT code protection (CVE-2020-16040) | 成功保护 V8 JIT 编译代码，披露代码仅 499-687 bytes |
| Code Inference (JIT cloning) | booby traps 随代码副本传播，两个 5MB+ 的代码副本中陷阱均存在 |

### 性能评估

| 基准测试 | 平均开销 |
|---------|---------|
| SPEC CPU 2017 | 1.85% |
| Web 服务器 (Nginx/Apache/Lighttpd) | 0.74% |
| 数据库 (MySQL/MongoDB/Redis/SQLite) | 1.30% |
| V8 Kraken JavaScript Benchmark | 1.54% |
| lmbench 进程相关操作 | ~0.5% |

| 开销类型 | 数值 |
|---------|------|
| 磁盘大小增加 | 3.2%-8.8%（平均 5.85%） |
| 内存开销 | 0.3%-2.1%（平均 1.05%） |
| Randomization fixup 开销 | 平均 4.01%（一次性，不影响运行时） |

---

## 六、批判性分析

1. **安全模型的前提条件较强**：MemoryTrap 假设系统已部署 W⊕X 和 load-time fine-grained randomization。fine-grained randomization 本身在工业界并未广泛部署（主流系统只有 coarse-grained ASLR），这使得 MemoryTrap 的实际部署场景有限。论文没有讨论在仅有 ASLR 而无 fine-grained randomization 时的安全保证。

2. **单步执行的性能影响被低估**：data-in-code 读取需要触发 page fault → exception handler → single-step execution → 再次 trap 恢复权限，这是一个重量级路径。论文用 SPEC CPU 2017 等测量平均开销很低（1.85%），但这些 benchmark 可能不代表 data-in-code 读取密集的场景。对于大量使用 jump tables 或内嵌常量的程序，开销可能显著更高，论文未提供这类 worst-case 分析。

3. **MPK 域数量有限**：Intel MPK 仅支持 16 个 protection keys，MemoryTrap 占用一个 PKey 用于代码页保护。论文提及使用 libmpk 做线程间同步，但未讨论与其他 MPK-based 安全方案（如 ERIM、Hodor）的兼容性——如果系统同时部署多个 MPK 方案，16 个 key 可能不够用。

4. **Booby trap 的确定性可被利用**：booby traps 在编译时确定且位置固定（除非配合 CCR 随机化），如果攻击者能通过 side channel 或部分信息泄露推断 trap 位置，可以有针对性地避开。论文承认 trap 对攻击者是 opaque 的，但未分析 timing side channel（读 trap vs 读正常代码的延迟差异）的风险。

5. **Code inference 防御的论证不够严谨**：论文声称 booby traps 随代码复制而传播，因此天然抗 code inference 攻击。但论文只用 JIT cloning 一种攻击作为代表性实验，对 T2 (shared library reloading)、T3 (process reloading)、T4 (implicit reads) 三种攻击仅做定性讨论，缺少实验验证。

6. **内核修改的安全性未经审计**：虽然只有 312 行内核代码修改，但涉及 page fault handler 和新 syscall，是高敏感路径。论文未讨论这些修改本身引入的攻击面（例如 mtrap syscall 的参数校验是否充分）。

---

## 七、总结

MemoryTrap 提出了一种基于 cyber deception 思想的 JIT-ROP 防御方案：在编译时向代码中插入不可读的 booby traps，利用 Intel MPK 实现高效的细粒度内存权限控制。与现有 XoM 方案相比，它允许代码段内嵌数据；与 DCR 方案相比，它天然抗 code inference 攻击。系统支持应用程序、共享库和 JIT 代码三类目标，运行时开销仅 0.74%-1.85%。主要局限在于依赖 fine-grained randomization 前提、MPK 域数量受限、以及对 data-in-code 密集场景的性能影响未充分评估。
