---
status: todo
date: 2026-04-03
keywords:
  - RISC-V
  - Near-Data Processing
  - LLM Inference
  - CXL
  - PIM
  - Hardware-Software Co-design
---

# 面向 LLM 推理的 RISC-V 近数据计算架构

---

## 一、现状地图：谁做了什么，什么没人做

### 工业界

| 厂商 | 产品 | 用了 RISC-V？ | 状态 |
|------|------|-------------|------|
| XCENA | MX1 CXL 计算内存 | 是，数千 RISC-V 核 | 2025 Q4 量产 |
| 澜起 (Montage) | M88MX6852 CXL 3.1 控制器 | 是，双 RISC-V 核（管理+安全） | 2025 送样 |
| UPMEM（下一代） | LPDDR5X PIM | 是，Semidynamics RISC-V + Tensor Unit | 2024 宣布，研发中 |
| FADU | Annapurna SSD 控制器 | 是，SiFive E51 | 已量产 |
| Western Digital | SweRV EH1/EH2/EL2 | 是，开源 | 已验证于 SSD 原型 |
| Samsung SmartSSD | CSD | 否，Xilinx FPGA | 已量产 |
| NVIDIA BlueField | DPU | 否，ARM 核 | 市场主导者 |
| UPMEM（当前代） | DRAM PIM | 否，自定义 32-bit 核 | 已量产 |

### 学术界

| 工作 | 方向 | 核心 | 局限 |
|------|------|------|------|
| [NM-Caesar/NM-Carus](https://arxiv.org/abs/2406.14263) (EPFL, 2024) | RISC-V NMC | CV32E40P + 自定义 `xvnmc` 向量扩展 | 仅边缘/嵌入式，非数据中心 |
| [AI-PiM](https://www.frontiersin.org/journals/electronics/articles/10.3389/felec.2022.898273/full) (2022) | RISC-V + SRAM PIM | RISC-V 功能单元集成 PIM 阵列 | 仅 IoT 场景，无存储系统集成 |
| [[fast2025-cui\|PIMLex]] (FAST'25) | PIM learned index | UPMEM 自定义核（非 RISC-V） | 受限于 UPMEM 硬件能力 |
| [[fast2025-zhu\|HiDPU]] (FAST'25) | DPU hybrid index | 华为 Hi1823 ARM 核 | 闭源硬件，23KB 内存极端受限 |
| [[osdi25-sun\|Scalio]] (OSDI'25) | DPU JBOF KV store | 模拟 DPU（Xeon 限核） | 未在真实 DPU 上验证 |
| [[atc2025-liu-ruili\|DSA-2LM]] (ATC'25) | Intel DSA 页迁移 | x86 专用加速器 | 仅限 Intel 平台 |
| [[osdi25-huang-yibo\|Tigon]] (OSDI'25) | CXL pod 数据库 | 无自定义计算核 | CXL 侧无可编程性 |

### 关键空白

1. **开源 RISC-V CXL 控制器 RTL 不存在**。XCENA/Montage 闭源，学术界无法复现或修改
2. **数据中心级 RISC-V + NDP 无人做**。学术 RISC-V NDP 全部面向 edge/IoT（CV32E40P 级别），没人用高性能 RISC-V 核做数据中心 NDP
3. **AI 工作负载特化的 NDP ISA 扩展无人做**。现有 NDP 论文都用通用核跑通用代码，没有为 LLM 推理特定操作定制 ISA

---

## 二、核心 Idea

### 问题

LLM decode 阶段的 KV cache attention 是 memory-bound 操作（计算强度极低，FLOP/byte < 1），恰好匹配近数据计算的"高带宽 + 弱计算"特性。但现有 NDP 硬件（UPMEM、SmartSSD FPGA）的 ISA 和微架构不是为这个工作负载设计的，存在严重的 impedance mismatch：

- UPMEM：无浮点运算单元，32-bit 定制 ISA，每核仅 64KB WRAM
- Samsung HBM-PIM：仅 9 条指令（NOP/JUMP/EXIT/ADD/MUL/MAC/MAD/MOV/FILL），无分支预测
- SmartSSD FPGA：可编程但开发周期长，功耗高，非面向计算密集

### 方案

设计面向 LLM 推理 memory-bound 操作的 RISC-V 近数据计算架构，通过 ISA-workload 协同设计实现：

1. **自定义 RISC-V 指令扩展**：针对 attention 计算（Q·K^T → softmax → ×V）设计融合原语
2. **NDP-friendly 数据布局**：KV cache 按 DRAM bank 分布，对齐 bank-level 并行
3. **自适应 Host-NDP 卸载**：编译器 + 运行时自动决策哪些 operator 卸载（参考 [[fast2025-park\|SODE]] 的自适应执行）
4. **全栈开源**：从 RTL 到编译器到运行时，基于 RISC-V 开源生态

### Novelty 来源

| 维度 | 现有工作 | 本方向 |
|------|---------|--------|
| 目标工作负载 | Learned index（PIMLex）、地址翻译（HiDPU）、通用 NDP（XCENA） | **LLM 推理 attention** |
| 硬件可定制性 | 固定 ISA（UPMEM/Hi1823/XCENA 闭源） | **开源 RISC-V RTL，ISA 可定制** |
| ISA 扩展 | 无 | **attention-specific 指令** |
| 编译器支持 | 手写代码 | **MLIR/TVM 自动卸载** |
| 可复现性 | 需特定硬件 | **gem5 模拟器 + FPGA 原型** |

---

## 三、可行性分析

### 硬件平台

| 选项 | 可行性 | 成本 | 说明 |
|------|-------|------|------|
| [gem5](https://github.com/gem5/gem5) + [DRAMSys](https://github.com/tukl-msd/DRAMSys) 模拟 | ★★★★★ | 免费 | 功能验证和性能估算首选；[PIMSys](https://github.com/SAITPublic/PIMSys) (MEMSYS'24) 已有 PIM 模拟框架 |
| [Chipyard](https://github.com/ucb-bar/chipyard) + FPGA | ★★★★ | ~$5-20K | UCB Chipyard 集成 Rocket/BOOM/Gemmini，Xilinx VCU118/Alveo U250 |
| [香山](https://github.com/OpenXiangShan/XiangShan) RTL + FPGA | ★★★ | ~$10-30K | 更高性能但更复杂；Kunminghu 已有 FPGA 原型 |
| UPMEM 真实硬件 | ★★★ | ~$10K | 当前代非 RISC-V，但可做 baseline 对比 |

**推荐路径**：gem5 模拟（论文主实验）→ Chipyard FPGA（硬件验证 + demo）

### 软件工具链

| 组件 | 现有支持 | 需要的工作 |
|------|---------|-----------|
| RISC-V 编译器 | [LLVM](https://github.com/llvm/llvm-project) 上游完整支持，香山已提交 Kunminghu target | 添加自定义指令 intrinsic |
| 模拟器 | [gem5](https://github.com/gem5/gem5) RISC-V 支持成熟 | 集成 NDP 内存模型 |
| AI 框架 | [TVM](https://github.com/apache/tvm)/[MLIR](https://github.com/llvm/llvm-project/tree/main/mlir) 有 RISC-V backend | 添加 NDP offload pass |
| CXL 模拟 | gem5 有 CXL.mem 模型（有限） | 扩展 CXL.compute 支持 |

### 风险评估

| 风险 | 严重程度 | 缓解策略 |
|------|---------|---------|
| NDP 带宽优势被 CXL 延迟抵消 | 高 | Phase 1 用 Roofline 提前验证；不成立则转 HBM-PIM 场景 |
| gem5 模拟精度不够 | 中 | 与 UPMEM 真实硬件交叉验证；FPGA 原型补充 |
| ISA 扩展收益有限 | 中 | 先用 intrinsic 验证算法效果，确认后再设计硬件 |
| LLM 架构变化快（MLA 等） | 低 | 设计通用 NDP 原语（matmul-reduce）而非 softmax-specific |

---

## 四、实施计划

### Phase 1: Workload 分析与 Roofline 验证（Month 1-3）

**目标**：量化 LLM decode 中哪些操作适合 NDP 卸载，建立理论上界。

1. **Profile LLM decode attention**
   - PyTorch profiler + NVIDIA Nsight 分析 Llama-3-8B/70B decode 阶段
   - 测量每个 operator 的计算强度（FLOP/byte）、内存访问模式、数据量
   - 重点：KV cache attention（GQA/MQA）、embedding lookup、RMSNorm、残差加法

2. **构建 NDP Roofline Model**
   - 参数：NDP 核频率（500MHz-1GHz）、DRAM bank 带宽（~25.6 GB/s/bank for DDR5）、计算能力（INT8/FP16 MACC）
   - 与 GPU（A100/H100）Roofline 对比，找到 NDP 占优的操作区间
   - 关键问题：什么 batch size 下 NDP 带宽优势能抵消计算劣势？

3. **调研 KV cache 数据布局**
   - 分析 [vLLM](https://github.com/vllm-project/vllm) PagedAttention 内存布局（block table → physical blocks）
   - 设计 NDP-friendly 布局（按 bank 分布、对齐 cache line）
   - 参考 PIMLex "解耦 search layer / data layer" 思路

**产出**：技术报告 + Go/No-go 决策

### Phase 2: ISA 设计与模拟器实现（Month 3-9）

**2a. ISA 扩展设计（Month 3-5）**

基于 Phase 1 profiling 结果设计指令类别：

```
# 1. 向量化 attention 原语
vndf.qkv      # Fused Q*K^T 点积 + scale，利用 bank-level 并行
vndf.softmax   # 在线 softmax（streaming，不需全局 max）
vndf.sv        # Score * V 聚合

# 2. 数据搬运原语
ndp.prefetch   # 根据 block table 预取 KV cache blocks
ndp.gather     # 跨 bank 收集非连续 KV cache entries
ndp.reduce     # 跨 bank 归约 partial attention 结果

# 3. 控制原语
ndp.offload    # Host 向 NDP 核提交计算任务描述符
ndp.sync       # Host 等待 NDP 计算完成
ndp.status     # 查询 NDP 核状态
```

设计原则：
- 指令粒度对齐 DRAM bank 操作粒度（64B-256B）
- 参考 PIMLex "用 lookup table 替代浮点" → INT8 lookup-table-based softmax 指令
- 参考 HiDPU "连续性分段" → 条件模式切换（连续 KV block 用 streaming，随机 block 用 gather）

**2b. gem5 模拟器实现（Month 5-9）**

- 基于 [gem5](https://github.com/gem5/gem5) RISC-V + [PIMSys](https://github.com/SAITPublic/PIMSys) 框架
- 实现：NDP 核模型（in-order pipeline + 自定义功能单元 + bank-local SRAM scratchpad）
- 实现：DDR5/CXL 内存模型 + bank-level 并行 + NDP-DRAM controller 接口
- 实现：Host-NDP 通信（描述符队列 + 中断/轮询两种模式）

**产出**：ISA 规范文档 + gem5 模拟器（开源）

### Phase 3: 编译器与运行时（Month 8-12）

**3a. LLVM 后端扩展**
- 自定义指令 LLVM intrinsic（`__builtin_riscv_ndp_*`）
- RISC-V 后端 instruction selection pattern
- C/C++ intrinsic header

**3b. TVM/MLIR Offload Pass**
- Operator-level offload 决策：
  - 输入：计算图 + NDP 硬件参数 + 当前 batch size
  - 输出：哪些 operator 跑 NDP、哪些跑 host
  - 策略：参考 SODE 自适应执行，根据 NDP 核忙闲动态切换
- 为 offloaded operator 生成 NDP kernel 代码

**3c. 运行时调度器**
- Host-NDP 任务调度（参考 [[osdi25-wang-xiaoyang\|XSched]] 的 XQueue 抽象）
- KV cache manager：block table + bank 映射，与 [vLLM](https://github.com/vllm-project/vllm) PagedAttention 接口对齐
- 异步执行：Host 发起 offload 后继续做 FFN，NDP 并行做 attention

**产出**：编译器工具链 + 运行时库（开源）

### Phase 4: 评估与论文（Month 12-16）

**实验设计**

| 实验 | 目标 | 方法 |
|------|------|------|
| 微基准 | 单 operator 加速比 | 对比 GPU [FlashAttention](https://github.com/Dao-AILab/flash-attention)、CPU baseline |
| 端到端推理 | 系统级吞吐/延迟 | Llama-3-8B/70B decode，对比 [vLLM](https://github.com/vllm-project/vllm) on GPU |
| 敏感性分析 | 设计空间探索 | 变 NDP 核数、频率、scratchpad 大小、batch size |
| 面积/功耗 | 可部署性 | Chipyard → Synopsys DC 综合或 [OpenROAD](https://github.com/The-OpenROAD-Project/OpenROAD) |
| vs UPMEM | 定制 vs 通用 | 在 UPMEM 上实现同样 attention 卸载做对比 |

**论文定位**
- 目标会议：ASPLOS / MICRO / ISCA（偏体系结构）或 OSDI / SOSP（偏系统，强调全栈）
- 核心 claim：面向 LLM decode attention 的 RISC-V NDP 架构，通过 ISA-workload 协同设计，在受限面积/功耗下实现显著加速，首次证明 NDP 可有效加速 LLM attention
- 团队规模：3-4 人，12-16 个月

---

## 五、延伸方向

| 延伸 | 描述 | 依赖 |
|------|------|------|
| CXL 计算内存 | NDP 核集成到 CXL 控制器，Host 通过 CXL.compute 卸载 | Phase 2 |
| SSD 端 KV cache | 冷 KV cache 存 SSD，SSD 内 RISC-V 核做 importance filtering（参考 [[fast2025-chen-weijian-impress\|IMPRESS]]） | Phase 1 |
| DPU 端推理调度 | DPU RISC-V 核运行 KV cache routing（参考 [[fast2025-qin\|MOONCAKE]] 分布式 KV pool） | Phase 3 |
| 训练 checkpoint 加速 | NDP 核做 checkpoint 压缩/序列化（参考 [[atc2025-liu-ruili\|DSA-2LM]] batching 思路） | 独立方向 |

---

## 六、综合评估

| 维度 | 评分 | 说明 |
|------|------|------|
| Novelty | ★★★★ | AI workload + RISC-V NDP + 全栈协同设计的交叉全新；单独组件不新，组合有明确 novelty |
| 可行性 | ★★★★ | gem5 + Chipyard 成熟；不需流片；3-4 人可执行 |
| 影响力 | ★★★★★ | 开源全栈可复现 → 社区价值大；LLM + NDP 热门交叉；RISC-V 生态急需系统研究 |
| 风险 | ★★★ | 最大风险：Roofline 不支持 → Phase 1 早期止损 |
| 时效性 | ★★★★ | UPMEM 下一代转 RISC-V、XCENA 量产 → 2025-2026 是窗口期 |

---

## 七、关键参考文献

### 顶会论文（NDP/CXL/DPU 方向）

- [[fast2025-cui\|PIMLex]] (FAST'25): PIM learned index，"用更多访问换更少计算"适配弱计算 PIM
- [[fast2025-zhu\|HiDPU]] (FAST'25): DPU 23KB 内存做 PB 级索引，连续性分段 + 混合索引
- [[osdi25-sun\|Scalio]] (OSDI'25): DPU JBOF 扩展，NVMe-oF target offload 卸载 CPU
- [[atc2025-liu-ruili\|DSA-2LM]] (ATC'25): Intel DSA 加速页迁移，batch + multi-WQ 并行
- [[osdi25-huang-yibo\|Tigon]] (OSDI'25): CXL pod 数据库，HWcc/SWcc 分离存储
- [[fast2025-park\|SODE]] (FAST'25): 自适应 on-device vs in-kernel 执行
- [[fast2025-ren\|PolyStore]] (FAST'25): 异构存储水平架构，带宽感知放置
- [[fast2025-qiu\|GeminiFS]] (FAST'25): GPU companion FS，ML I/O 可预测且只读
- [[fast2025-chen-weijian-impress\|IMPRESS]] (FAST'25): KV cache importance-aware 三层存储
- [[fast2025-qin\|MOONCAKE]] (FAST'25): 分布式 KV cache pool，prefill/decode 分离

### RISC-V + NDP 学术工作

- [NM-Caesar/NM-Carus](https://arxiv.org/abs/2406.14263) (EPFL, 2024): RISC-V NMC with `xvnmc` extension
- [AI-PiM](https://www.frontiersin.org/journals/electronics/articles/10.3389/felec.2022.898273/full) (Frontiers in Electronics, 2022): RISC-V + SRAM PIM functional units
- [PIM-AI](https://arxiv.org/abs/2411.17309) (arXiv, 2024): PIM for LLM inference
- [PIMSys](https://github.com/SAITPublic/PIMSys) (MEMSYS'24): gem5-based PIM virtual prototype

### 开源硬件平台

- [XiangShan 香山](https://github.com/OpenXiangShan/XiangShan): 高性能开源 RISC-V，Kunminghu 6-wide OoO，接近 Neoverse N2
- [Chipyard](https://github.com/ucb-bar/chipyard): UCB SoC 生成框架，集成 Rocket/BOOM/Gemmini
- [WD SweRV EH1](https://github.com/westerndigitalcorporation/swerv_eh1): 面向 SSD 控制器的开源 RISC-V
- [Rocket Chip](https://github.com/chipsalliance/rocket-chip): 经典 in-order RISC-V 核，适合轻量 NDP 控制器
- [CVA6/Ariane](https://github.com/openhwgroup/cva6): OpenHW 6-stage in-order核，Linux-capable
- [如意 SDK](https://ruyisdk.org/): RISC-V 开发工具链生态

### 开源模拟/EDA 工具

- [gem5](https://github.com/gem5/gem5): 全系统微架构模拟器，RISC-V 支持成熟
- [DRAMSys](https://github.com/tukl-msd/DRAMSys): DRAM 子系统模拟器，支持 DDR5/HBM/LPDDR
- [PIMSys](https://github.com/SAITPublic/PIMSys): Samsung 开源 PIM 模拟框架（gem5 + DRAMSys）
- [Ramulator2](https://github.com/CMU-SAFARI/ramulator2): CMU SAFARI 内存模拟器，支持 PIM 建模
- [OpenROAD](https://github.com/The-OpenROAD-Project/OpenROAD): 开源 RTL-to-GDSII 流程

### 开源 AI/系统软件

- [vLLM](https://github.com/vllm-project/vllm): LLM 推理引擎，PagedAttention KV cache 管理
- [SGLang](https://github.com/sgl-project/sglang): LLM 推理引擎，RadixAttention
- [FlashAttention](https://github.com/Dao-AILab/flash-attention): IO-aware attention 算法
- [TVM](https://github.com/apache/tvm): 深度学习编译器，有 RISC-V backend
- [MLIR](https://github.com/llvm/llvm-project/tree/main/mlir): 多层 IR 编译框架
- [LLVM](https://github.com/llvm/llvm-project): 编译器基础设施，RISC-V 后端完整支持
