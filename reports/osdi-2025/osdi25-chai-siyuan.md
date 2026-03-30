# EMT: An OS Framework for New Memory Translation Architectures

## 论文基本信息

- **标题**: EMT: An OS Framework for New Memory Translation Architectures
- **作者**: Siyuan Chai, Jiyuan Zhang, Jongyul Kim, Alan Wang, Fan Chung, Jovan Stojkovic (UIUC); Weiwei Jia (University of Rhode Island); Dimitrios Skarlatos (CMU); Josep Torrellas, Tianyin Xu (UIUC)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/chai-siyuan
- **开源**: https://github.com/xlab-uiuc/emt

---

## 研究背景与动机

### 内存翻译已成为性能瓶颈

随着 TB 级内存容量和内存密集型虚拟化环境的普及，内存翻译开销被显著放大。传统 x86-64 架构使用四级页表，嵌套翻译（虚拟化环境下两层页表的二维遍历）最多需要 24 次顺序内存访问。已有研究表明嵌套翻译可占据内存密集型工作负载 50% 以上的执行时间。

### 新硬件翻译方案层出不穷，但缺乏 OS 支持

学术界和工业界提出了多种新的内存翻译方案：
- **基于哈希的翻译**：如 ECPT（Elastic Cuckoo Page Table），通过并行查找条目来加速翻译
- **扁平化页表（FPT）**：动态合并中间树层级，减少翻译间接跳转
- **混合翻译架构**：不同场景使用不同方案，或选择性暴露给用户空间

然而，这些新硬件方案几乎没有在主流操作系统（如 Linux）上进行实验验证。主要原因在于：Linux 的内存管理模块硬编码了 radix-tree 页表结构，缺乏对这些新硬件方案的扩展能力。添加第五级页表都需要修改 23 个文件、715 行代码。研究者因此转向性能模型估算或 trace-driven 模拟，假设"不同翻译架构下 OS 开销恒定"——本文证明这一假设是错误的。

---

## 要解决的核心问题

如何为 Linux 构建一个可扩展的框架，使开发者能够在不修改架构无关代码的情况下，支持新的内存翻译架构，同时保持极低的运行时开销？

---

## 主要贡献

1. **EMT 框架**：首个在 Linux 上支持新型内存翻译架构的可扩展 OS 框架，类比 VFS 的设计思路
2. **EMT API**：架构中立的三元素抽象（Translation Object、Translation Database、Translation Service）+ 15 个基础函数 + 35 个可定制函数
3. **ECPT 和 FPT 的 Linux 移植经验**：利用 EMT 在 Linux 上实现两个新型硬件翻译方案，证明框架的实用性和有效性
4. **QEMU 工具链**：支持在没有真实硬件的情况下，通过仿真 MMU 运行 EMT-Linux 并进行性能评估
5. **实验验证**：在多种翻译方案上验证 EMT 的通用性和极低开销

---

## 研究方法与设计

### 核心设计原则

EMT 遵循四个设计原则：
1. **架构中立**：不硬编码特定翻译结构（如多级 radix tree）
2. **支持硬件特定优化**：允许 MMU driver 定制例程
3. **模块化、可维护**：对象化设计，消除架构特定或过载语义
4. **极低开销**：通过编译器优化、缓存效率和内联实现

### 三层核心抽象

**1. Translation Object（翻译对象）**
- 编码虚拟地址到物理地址的映射及其元数据（大小、保护位、存在位、交换信息等）
- MMU driver 负责将硬件定义的翻译条目编码为 Translation Object
- 元数据编码为 attribute，可通过 `tobj_read_attr()` / `tobj_write_attr()` 查询和更新

**2. Translation Database（翻译数据库）**
- 存储一个地址空间的所有 Translation Object
- 可实现为页表（各种形状）、多页表并存（如 ECPT 需要分别为用户空间和内核空间维护）、或 VMA registers
- 必须为每个虚拟地址返回唯一的一个 Translation Object

**3. Translation Service（翻译服务）**
- 抽象 MMU 本身
- 负责地址空间的创建、销毁和切换
- 上下文切换时调用切换数据库

### API 设计

**基础函数（15个）**：每个 MMU driver 必须实现，包括 `tdb_find_tobj()`（查找翻译对象）、`tdb_update_tobj()`（更新）、`tdb_remove_tobj()`（删除）等。

**可定制函数（35个，分7组）**：提供架构无关的默认实现，但 MMU driver 可覆盖以实现硬件特定优化。关键分组包括：
- **Translation-Object Iterator**：迭代遍历大量翻译对象（用于页面迁移、huge-page 提升等场景）。x86-64 驱动利用 radix tree 空间局部性直接递增指针，而默认实现每次都从根遍历
- **Huge Page**：检查给定 VA 范围是否可作为 huge page
- **Address Range**：检查 VA 范围是否无映射
- **Lock**：获取保护 VA 范围内所有翻译对象的锁
- **Swap**：从翻译对象获取 Linux swp_entry_t

### 工具链：QEMU 仿真

新硬件方案尚未量产，EMT 提供工具链在 QEMU 上运行 EMT-Linux：
- 在 QEMU 中仿真 MMU，实现硬件翻译逻辑
- 支持 cycle-accurate 硬件模拟
- 允许在真实 Linux 内核上测试新翻译架构的 OS 层面开销

---

## 关键实现细节

### EMT-Linux 实现

- **基于 Linux v5.15**，对架构无关代码进行模块化改造
- 保留了所有现有功能和硬件特定优化
- 平均开销 < 0.5%（关键 OS 操作）
- 约 1 万行新增代码（~7,000 行 C + ~3,000 行测试/工具）

### ECPT MMU Driver

- 实现基于 Elastic Cuckoo Page Table 方案
- 需要维护用户空间和内核空间两个独立的页表
- 解决了 kECPT（内核 ECPT）的自引用问题：修改 kECPT 的翻译需要查询 kECPT 本身，形成循环依赖
- 探索了细粒度锁策略和内存扫描优化

### FPT MMU Driver

- 实现基于 Arm Flattened Page Table 提案
- 需要修改 Linux 架构无关代码以折叠中间层级
- 相比 ECPT 改动更小

### Iterator 优化的效果

优化的 Iterator（利用 radix tree 空间局部性直接递增指针）将页故障处理成本降低 52.5%。

---

## 实验结果与分析

### 实验配置

- 仿真环境：QEMU（模拟 x86-64 MMU，包括 PWALK、PWC 等缓存）
- 对比基线：vanilla Linux（硬编码 radix tree）
- 工作负载：lmbench（内存操作基准）、page fault handling、页迁移

### 开销评估

- **lmbench lat_pagewalk**：EMT-Linux 相比 vanilla Linux 仅增加 0.4% 开销
- **页故障处理**：优化后的 Iterator 相比未优化版本快 52.5%
- **页迁移**：优化 Iterator + in-place 操作的综合优化效果显著

### 通用性验证

- 在 x86-64 radix tree（vanilla Linux 的基准）、ECPT（哈希并行方案）、FPT（扁平化页表）三种方案上均成功运行
- 三种方案代表树形和哈希两类不同翻译设计，覆盖大多数新兴架构

### 工具链验证

- QEMU 仿真能够成功启动完整 Linux 系统
- 支持性能分析和调试

---

## 潜在问题与局限性

1. **硬件仿真精度**：QEMU 仿真无法完全捕获真实硬件的行为特性（如真实缓存命中率、内存访问延迟等）
2. **实验规模**：主要在仿真环境中评估，缺少真实硬件环境下的性能数据
3. **仅支持用户空间透明页面（HUGE pages）、交换、DAX 内存等特性**：虽然声称支持 Linux 所有相关特性，但尚不完整
4. **ECPT 的 kECPT 自引用问题**：该问题需要仔细处理，可能影响内核翻译性能
5. **工具链门槛**：使用 QEMU 仿真需要额外的工程投入，不如直接使用真实硬件直观

---

## 未来工作方向

- 支持更多新的翻译架构（如 Midgard 等用户空间映射方案）
- 进一步优化 ECPT 的内核空间翻译性能
- 与其他 OS 框架（如 FBMM）的对比研究
- 探索 EMT 在新兴内存技术（如 CXL）上的应用

---

## 个人评注

### 优势

1. **问题定位精准**：首次系统性地指出"新硬件翻译方案缺乏主流 OS 支持"这一核心障碍，并将其归因于 Linux 内存管理的不可扩展性
2. **类比 VFS 的设计思路**：将 Translation Object/Database/Service 与 VFS 的 superblock/inode/filesystem operations 对应，降低了理解门槛，也暗示了工程上的可行性
3. **理论与工程结合**：不只停留在框架设计，还包括完整的 QEMU 工具链，使研究者能够在没有真实硬件的情况下评估新架构
4. **Iterator 优化的洞察**：发现优化的 Iterator 能将页故障降低 52.5%，这说明看似微小的优化在 OS 路径上可产生巨大影响

### 潜在争议

1. **"极低开销"的量化**：论文报告 < 0.5% 平均开销，但这主要来自 lmbench 页表遍历测试。实际内核路径（如 swap、migration）中开销可能更高
2. **框架复杂度的权衡**：引入 EMT 增加了新的抽象层，开发者需要实现 MMU driver。虽然比直接修改 Linux 更简单，但仍有学习成本
3. **自引用问题的解决**：ECPT 的 kECPT 自引用问题（修改 kECPT 本身需要先查 kECPT）在论文中讨论得不够深入，实际影响有待进一步评估
4. **生态构建的挑战**：EMT 的价值取决于社区是否愿意为其编写 MMU driver。如果只有 UIUC 团队自己维护的驱动，框架的实际影响力将受限
