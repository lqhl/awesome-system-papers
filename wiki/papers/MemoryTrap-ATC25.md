---
type: paper
name: MemoryTrap
full_title: "MemoryTrap: Booby Trapping Memory to Counter Memory Disclosure Attacks with Hardware Support"
authors: [Chenke Luo, Jiang Ming, Dongpeng Xu, Guojun Peng, Jianming Fu]
venue: ATC
year: 2025
tags: [security, memory-protection, jit-rop, intel-mpk, code-reuse]
source_pdf: "[[atc2025-luo.pdf]]"
source_md: "[[atc2025-luo]]"
---

# MemoryTrap: Booby Trapping Memory to Counter Memory Disclosure Attacks with Hardware Support (ATC 2025)

> **一句话总结**：编译期在每个函数及每 4 KB 代码插入不可读的"booby trap" NOP snippet，借 Intel MPK 在字节级控权限阻止 JIT-ROP gadget search，攻击者最多只能泄露 ~657 B 代码就触发陷阱，运行时开销仅 0.74%–1.85%。

## 问题

ASLR 之后 JIT-ROP 攻击靠在线 memory disclosure 搜寻 gadget。已有防御要么是 Execute-only Memory（XnR、Readactor、HideM、kRX）——必须严格区分 code/data，对掺杂数据（jump table、汇编手写函数、KCFI 签名）会误报；要么是 Destructive Code Read（Heisenbyte、NEAR、BGDX）——已被 ZombieGadget 等 code inference 攻击破解。同时 Readactor 用 Intel EPT 性能高、CHERI 要新硬件。

## 核心方法

MemoryTrap 在编译期 + 运行期协作：

- **Booby trap 插入策略**（LLVM pass）：每个函数至少 1 个、函数 > 4 KB 每 4 KB 再插一个；snippet 是 5–30 条随机 NOP 加前缀 JMP 跳过；变长打乱 layout。SPEC/Nginx 等真实 binary 中 86.5% 相邻陷阱距离 < 1 KB，全部 < 4 KB。
- **MPK-based 不可读权限**：把所有代码页设 execute-only PKey，任何代码读触发 page fault；handler 检查目标地址是否落入陷阱区——若是直接终止进程并保存上下文取证，若是合法 data-in-code 则临时恢复读权限 + 单步执行该指令再撤回。
- **新 ELF 格式**：复用 EI_PAD 保留位作 MTRAP_ENABLE 标志，新增 `.mtrap` section 存陷阱 list；自定 loader 配合，旧内核可向后兼容运行。
- **覆盖 ELF 应用 / 共享库 / JIT 代码**：共享库走修改后的 glibc loader + `mtrap_enable/add/delete` syscall；V8 TurboFan 生成 JIT 代码时同步插陷阱并注册，code 更新时短暂恢复 RW 再注销旧陷阱。

兼容 CCR 等 fine-grained code randomization。深度细节见 [[atc2025-luo]]。

## 关键结果

- CVE-2013-2028 (Nginx)：广度优先平均只能泄露 657 B 后即触发陷阱，深度优先 299 B；20,390 个起点 × 2 策略共 40,780 次尝试中只有 39 次能找到 ≤1 个 gadget。
- CVE-2020-16040 (V8)：5,213 KB JIT 代码插 7,025 个陷阱，攻击只能 disclose 607 B；要凑齐 gadget chain 需 2,739 KB。
- 抵御代码克隆型 code inference 攻击：维护两份 5 MB JIT 代码，分别仅泄露 595 / 653 B。
- SPEC CPU 2017 平均运行时开销 1.85%（几何平均 0.60%），最坏 povray 8.5%；Nginx/Apache/Lighttpd 平均 0.74%；MySQL/Redis/MongoDB/SQLite 平均 1.30%；Kraken JS 1.54%。
- 内核改动仅 312 LoC；MPK 切换 < 20 cycles，无 TLB flush。
- 优于 XnR (2.2%) / Readactor (2.2%) / HideM (1.4%) / Heisenbyte (18.3%) 的 SPEC 2006 报告值。

## 相关

- **相关概念**：[[ASLR]]、[[Code-Reuse-Attack]]、[[Intel-MPK]]、[[Execute-Only-Memory]]、[[Control-Flow-Integrity]]
- **同类系统**：XnR、Readactor、HideM、Heisenbyte、NEAR、BGDX、kRX、CHERI
- **同会议**：[[ATC-2025]]
