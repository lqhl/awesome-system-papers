---
status: deprecated
date: 2026-04-03
keywords:
  - RISC-V
  - Near-Data Processing
  - LLM Inference
  - PIM
  - Hardware-Software Co-design
---

# 面向 LLM 推理的开源 RISC-V 近数据计算架构

> [!warning] Deprecated
> 核心前提不成立。文档假设 LLM decode attention 是 memory-bound（FLOP/byte < 1），适配 NDP 的"高带宽 + 弱计算"特性。但这仅对标准多头注意力（MHA）成立。当前主流模型已全面转向 GQA（Llama-3、Mistral、Qwen-2 等），GQA 通过减少 KV heads 但保持 Q heads 不变，将算术强度提升了 GQA ratio 倍（Llama-3-8B: ~4.2 FLOP/byte，Llama-3-70B: ~8.4 FLOP/byte）。在 NDP 核的弱算力下（ridge point ~2.4 FLOP/byte），GQA attention 反而是 compute-bound 的——NDP 的高带宽优势无法发挥。此外，NDP for LLM attention 方向已有 CENT (ASPLOS'25)、STARC (ASPLOS'26) 等多项竞品发表，novelty 空间也已收窄。

---

## 一、现状地图：谁做了什么，什么没人做

### 工业界

| 厂商 | 产品 | 用了 RISC-V？ | 状态 |
|------|------|-------------|------|
| XCENA | MX1 CXL 3.2 计算内存 | 是，数千 RISC-V 核 | 2025.10 工作样品，2026 量产 |
| 澜起 (Montage) | M88MX6852 CXL 3.1 控制器 | 是，双 RISC-V 核（管理+安全） | 2025 送样 |
| UPMEM（下一代） | LPDDR5X PIM | 是，Semidynamics RISC-V + Tensor Unit（8 TFLOPS FP16） | 2024.12 宣布，研发中 |
| FADU | Annapurna SSD 控制器 | 是，SiFive E51 | 已量产 |
| Western Digital | SweRV EH1/EH2/EL2 | 是，开源 | 已验证于 SSD 原型 |
| Samsung SmartSSD | CSD | 否，Xilinx FPGA | 已量产 |
| NVIDIA BlueField | DPU | 否，ARM 核 | 市场主导者 |
| UPMEM（当前代） | DRAM PIM | 否，自定义 32-bit 核 | 已量产 |

### 学术界：NDP/PIM 通用

| 工作 | 方向 | 核心 | 局限 |
|------|------|------|------|
| [NM-Caesar/NM-Carus](https://arxiv.org/abs/2406.14263) (EPFL, 2024) | RISC-V NMC | CV32E40P + 自定义 `xvnmc` 向量扩展 | 仅边缘/嵌入式，非数据中心 |
| [AI-PiM](https://www.frontiersin.org/journals/electronics/articles/10.3389/felec.2022.898273/full) (2022) | RISC-V + SRAM PIM | RISC-V 功能单元集成 PIM 阵列 | 仅 IoT 场景，无存储系统集成 |
| [[fast2025-cui\|PIMLex]] (FAST'25) | PIM learned index | UPMEM 自定义核（非 RISC-V） | 受限于 UPMEM 硬件能力 |
| [[fast2025-zhu\|HiDPU]] (FAST'25) | DPU hybrid index | 华为 Hi1823 ARM 核 | 闭源硬件，23KB 内存极端受限 |
| [[atc2025-wu-puqing\|PIMANN]] (ATC'25) | PIM ANNS 调度 | UPMEM 2,560 PU | 揭示 PIM 核间负载不均（65% PU 空闲）和 host-PIM 总线争用问题 |
| [[osdi25-sun\|Scalio]] (OSDI'25) | DPU JBOF KV store | 模拟 DPU（Xeon 限核） | 未在真实 DPU 上验证 |
| [[osdi25-huang-yibo\|Tigon]] (OSDI'25) | CXL pod 数据库 | 无自定义计算核 | CXL 侧无可编程性 |

### 学术界：NDP/PIM for LLM（直接竞品）

| 工作 | 方向 | 核心 | 局限 |
|------|------|------|------|
| [CENT](https://arxiv.org/abs/2502.07578) (ASPLOS'25) | CXL-enabled GPU-free PIM for LLM | Near-bank processing units，2.3x throughput over GPU | 自定义 PIM 单元，闭源设计 |
| [L3](https://arxiv.org/abs/2504.17584) (arXiv, 2025) | DIMM-PIM + GPU co-design for long-context attention | 6.1x speedup over HBM-PIM | 依赖 GPU 协同，非纯 NDP 方案 |
| [STARC](https://arxiv.org/abs/2505.05772) (ASPLOS'26) | PIM-aware sparse attention | Bank-aligned KV clustering，19-31% attention 延迟降低 | 仅优化稀疏 attention，不适用密集场景 |
| [HPIM](https://arxiv.org/abs/2509.12993) (arXiv, 2025) | 异构 SRAM-PIM + HBM-PIM for LLM | Attention 映射到 SRAM-PIM | 硬件复杂度高，可行性存疑 |
| [PAM](https://arxiv.org/abs/2602.11521) (arXiv, 2026) | Tiered PIM for KV-centric LLM serving | 多层 PIM 模块 | 早期工作，无硬件验证 |
| [PIM-AI](https://arxiv.org/abs/2411.17309) (arXiv, 2024) | DDR5/LPDDR5 PIM for LLM inference | 6.94x TCO reduction vs GPU | 无 ISA 定制，通用 PIM |
| [SAIL](https://arxiv.org/abs/2509.25853) (arXiv, 2025) | ARM + NDP at L3 cache for LLM | Lookup-table GEMV，32 near-data processors | ARM 核，非 RISC-V；L3 cache 级非 DRAM 级 |

### 关键空白

1. **开源 RISC-V CXL 控制器 RTL 不存在**。XCENA/Montage 闭源，学术界无法复现或修改
3. **上述 LLM NDP 工作全部使用自定义闭源 PIM 单元或 ARM 核**，无人用可定制 ISA 的开源 RISC-V 核
4. **AI 工作负载特化的 NDP ISA 扩展无人做**。现有 NDP 论文用通用核跑通用代码，未针对 attention 操作定制指令（但需先证明 ISA 定制相比 RVV 有实际收益）

---

## 二、核心 Idea

### 问题

LLM decode 阶段的 KV cache attention 在**小 batch size + 长序列**条件下是 memory-bound 操作（计算强度 ~1 FLOP/byte），匹配近数据计算的"高带宽 + 弱计算"特性。但：

- 现有 NDP for LLM 工作（CENT/STARC 等）使用闭源自定义 PIM 单元，**学术界无法复现、修改或探索设计空间**
- 通用 PIM 硬件的 ISA 和微架构不是为 attention 设计的，存在 impedance mismatch：
  - UPMEM：无浮点运算单元，32-bit 定制 ISA，每核仅 64KB WRAM，host-PIM 总线争用严重（[[atc2025-wu-puqing\|PIMANN]] 实测 65% PU 空闲）
  - Samsung HBM-PIM：仅 9 条指令，无分支预测
  - SmartSSD FPGA：可编程但开发周期长，功耗高

**前提条件与适用范围**（必须在 Phase 1 定量验证）：

| 条件 | 对 NDP 收益的影响 |
|------|------------------|
| MHA（标准多头注意力） | 最有利：KV cache 大，memory-bound 明显 |
| GQA（Llama-3 等） | KV cache 缩小 16x，绝对带宽需求降低，NDP 收益缩小 |
| MLA（DeepSeek 等） | KV cache 压缩 ~93%，可能不再 memory-bound，NDP 价值存疑 |
| Batch size > 4 | 逐渐转 compute-bound，NDP 不适用 |
| 短序列（< 2K tokens） | KV cache 小，NDP 卸载开销可能大于收益 |

**最佳目标场景**：GQA/MHA + batch size 1-4 + 长序列（4K+ tokens）的 decode 阶段。

### 方案

设计面向 LLM 推理 memory-bound 操作的**开源 RISC-V** 近数据计算架构：

1. **In-DRAM bank-level PIM**：NDP 核紧耦合 DRAM bank，利用 bank 内部带宽（聚合 ~42 GB/s），避免外部总线瓶颈。CXL 仅作为 host-NDP 互联接口，**计算发生在 DRAM bank 侧而非 CXL 设备控制器侧**
2. **自定义 RISC-V 指令扩展**：在 RVV baseline 基础上，针对 attention 计算设计融合原语（需先量化 RVV 的指令开销占比以证明必要性）
3. **NDP-friendly 数据布局**：KV cache 按 DRAM bank 分布，对齐 bank-level 并行
4. **自适应 Host-NDP 卸载**：运行时根据 batch size 和序列长度自动决策卸载策略
5. **全栈开源**：从 RTL 到编译器 intrinsic 到运行时，基于 RISC-V 开源生态

### Novelty 来源

| 维度 | CENT/STARC 等 | 通用 PIM（UPMEM/XCENA） | 本方向 |
|------|-------------|------------------------|--------|
| 目标工作负载 | LLM attention | 通用 | LLM attention |
| 硬件可定制性 | 闭源自定义 PIM | 闭源 | **开源 RISC-V RTL，ISA 可定制** |
| ISA 扩展 | 固定功能单元 | 固定 ISA | **attention-aware 指令（需证明相比 RVV 的增量收益）** |
| 可复现性 | 不可复现 | 需特定硬件 | **gem5 模拟器 + 开源 RTL** |
| 设计空间探索 | 无法修改 | 无法修改 | **参数化探索（核数/频率/scratchpad/ISA 组合）** |

核心 claim 不是"NDP 加速 LLM attention"（CENT 等已证明），而是：**开源 RISC-V 平台上通过 ISA-workload 协同设计 + 参数化设计空间探索，可以为 NDP for LLM 提供可复现的研究基础设施，并量化 ISA 定制的实际收益边界**。

---

## 三、可行性分析

### 硬件平台

| 选项 | 可行性 | 成本 | 说明 |
|------|-------|------|------|
| [gem5](https://github.com/gem5/gem5) + [DRAMSys](https://github.com/tukl-msd/DRAMSys) 模拟 | ★★★★★ | 免费 | 功能验证和性能估算首选；[PIMSys](https://github.com/SAITPublic/PIMSys) (MEMSYS'24) 已有 PIM 模拟框架 |
| [Chipyard](https://github.com/ucb-bar/chipyard) RTL 仿真 | ★★★★ | 免费 | UCB Chipyard 集成 Rocket/BOOM/Gemmini，用于 RTL 级功能验证（无需 FPGA） |
| UPMEM 真实硬件 | ★★★ | ~$10K | 当前代非 RISC-V，但可做 baseline 对比；参考 PIMANN 的调度优化经验 |

**推荐路径**：gem5 模拟（论文主实验）+ Chipyard RTL 仿真（硬件设计验证）

### DRAM 带宽参数（用于 Roofline 建模）

| 参数 | 数值 | 来源 |
|------|------|------|
| DDR5-4800 单通道总带宽 | ~38.4 GB/s | 标准规范 |
| DDR5 bank 数量 | 32（4 BG × 4 Bank × 2 Subchannel） | 标准规范 |
| 单 bank 带宽（受 tRAS ~48ns 限制） | **~1.3 GB/s** | bank cycle time 约束 |
| 聚合内部 bank 带宽（所有 bank 并行） | **~42 GB/s** | 32 × 1.3 GB/s |
| CXL 内存带宽 | ~26-32 GB/s | 实测（vs 本地 DDR5 218-238 GB/s） |
| CXL 内存延迟 | 259-300 ns | 实测（vs 本地 DRAM 112-159 ns） |

关键推论：**CXL 带宽仅为本地 DDR5 的 ~13%**。NDP 核必须在 bank 侧直接访问 DRAM 内部带宽，不能通过 CXL 外部接口访问——否则带宽优势不存在。

### 软件工具链

| 组件 | 现有支持 | 需要的工作 |
|------|---------|-----------|
| RISC-V 编译器 | [LLVM](https://github.com/llvm/llvm-project) 上游完整支持 | 添加自定义指令 intrinsic |
| 模拟器 | [gem5](https://github.com/gem5/gem5) RISC-V 支持成熟 | 集成 NDP 内存模型 |
| DRAM 模拟 | [DRAMSys](https://github.com/tukl-msd/DRAMSys) / [Ramulator2](https://github.com/CMU-SAFARI/ramulator2) | 建模 bank-level PIM 访问 |
| AI 框架集成 | [vLLM](https://github.com/vllm-project/vllm) PagedAttention | C++ intrinsic 对接 KV cache manager |

### 风险评估

| 风险 | 严重程度 | 缓解策略 |
|------|---------|---------|
| GQA/MLA 下 NDP 收益不够 | **极高** | Phase 1 分别 profile MHA/GQA/MLA 三种场景；GQA 收益不足则转向 long-context 专用场景 |
| CXL 延迟/带宽抵消收益 | 高 | 明确定位为 in-DRAM PIM（非 CXL 控制器侧计算）；CXL 仅作互联 |
| ISA 扩展相比 RVV 收益有限 | **高** | Phase 2 先用 RVV baseline 跑 attention，量化指令开销占比；收益 < 10% 则放弃自定义 ISA，转为"RVV-based NDP 设计空间探索" |
| PIM 核间负载不均 | 中 | 参考 PIMANN 的 per-core 细粒度调度；设计 bank-aware KV cache 分配策略 |
| gem5 模拟精度不够 | 中 | 与 UPMEM 真实硬件交叉验证 |
| LLM 架构变化快 | 中 | 设计通用 NDP 原语（matmul-reduce）而非 softmax-specific |

---

## 四、实施计划

### Phase 1: Workload 分析与 Go/No-go 决策（Month 1-3）

**目标**：量化 LLM decode 中哪些操作适合 NDP 卸载，明确适用场景边界。

1. **Profile LLM decode attention（分场景）**
   - PyTorch profiler + NVIDIA Nsight 分析 Llama-3-8B（GQA）和 Llama-2-7B（MHA）decode 阶段
   - 测量每个 operator 的计算强度（FLOP/byte）、内存访问模式、数据量
   - 分别测量 batch size = 1/2/4/8/16，序列长度 = 1K/4K/16K/64K
   - 额外 profile DeepSeek-V2（MLA），评估 MLA 下 NDP 是否仍有意义

2. **构建 NDP Roofline Model**
   - 参数：NDP 核频率（500MHz-1GHz）、**单 bank 带宽（~1.3 GB/s）**、聚合 bank 带宽（~42 GB/s for 32 banks）、计算能力（INT8/FP16 MACC）
   - 分 MHA/GQA/MLA 三条 Roofline 曲线，与 GPU（A100/H100）对比
   - 关键问题：在 GQA 下，什么 batch size × 序列长度组合使 NDP 带宽优势能抵消计算劣势？

3. **分析 KV cache 数据布局**
   - 分析 [vLLM](https://github.com/vllm-project/vllm) PagedAttention 内存布局（block table → physical blocks）
   - 设计 bank-aware 布局（按 bank 分布、对齐 bank cycle）
   - 评估 bank-level 并行度：32 banks 能否充分并行服务 GQA 的 8 个 KV head？

**Go/No-go 决策标准**：
- GQA + batch size 1-4 + 序列 4K+ 下，NDP 理论加速比 > 2x → Go
- 仅 MHA 场景有意义但 GQA 没有 → Pivot 到 long-context 专用场景（128K+）
- 所有场景 NDP 收益 < 1.5x → No-go

**产出**：技术报告 + Go/No-go 决策 + 目标场景定义

### Phase 2: ISA 设计与模拟器实现（Month 3-9）

**2a. RVV Baseline 评估（Month 3-4）**

在 gem5 RISC-V + RVV 上实现 attention kernel：
- 用标准 RVV 指令（`vfmacc`, `vfredosum` 等）实现 Q·K^T → softmax → ×V
- 分析 cycle breakdown：内存等待 vs 指令执行 vs pipeline stall
- **关键判断**：如果内存等待占 > 90%，自定义 ISA 收益有限，转为"RVV-based NDP 设计空间探索"；如果指令开销占 > 20%，则设计融合指令有意义

**2b. 自定义 ISA 扩展设计（Month 4-5，仅当 2a 证明有必要）**

```
# 1. 融合 attention 原语（减少指令开销）
vndf.qkv      # Fused Q*K^T 点积 + scale，单指令完成 bank-local 向量化计算
vndf.softmax   # 在线 softmax（streaming，不需全局 max）
vndf.sv        # Score * V 聚合

# 2. 数据搬运原语（减少 bank 间通信）
ndp.gather     # 跨 bank 收集非连续 KV cache entries
ndp.reduce     # 跨 bank 归约 partial attention 结果

# 3. Host-NDP 控制
ndp.offload    # Host 向 NDP 核提交任务描述符
ndp.sync       # Host 等待 NDP 计算完成
```

设计原则：
- 指令粒度对齐 DRAM bank 操作粒度（64B-256B）
- 参考 PIMANN 教训：设计 per-bank 任务调度原语，避免 bank 间负载不均
- 参考 PIMLex "用 lookup table 替代浮点" → INT8 lookup-table-based softmax

**2c. gem5 NDP 模拟器实现（Month 4-9）**

- 基于 [gem5](https://github.com/gem5/gem5) RISC-V + [PIMSys](https://github.com/SAITPublic/PIMSys) 框架
- 实现：NDP 核模型（in-order pipeline + bank-local SRAM scratchpad）
- 实现：DDR5 内存模型 + bank-level 并行（参数化：bank 数、频率、scratchpad 大小）
- 实现：Host-NDP 通信（描述符队列 + 中断/轮询两种模式）
- 关键：模拟 host-PIM 总线争用（PIMANN 发现这是主要瓶颈来源）

**产出**：ISA 规范文档（或 RVV baseline 分析报告）+ gem5 NDP 模拟器（开源）

### Phase 3: 系统集成与评估（Month 8-14）

**3a. LLVM 后端扩展**
- 自定义指令 LLVM intrinsic（`__builtin_riscv_ndp_*`）
- RISC-V 后端 instruction selection pattern
- C/C++ intrinsic header

**3b. 运行时调度器**
- Host-NDP 任务调度：根据 batch size / 序列长度 动态决策卸载
- KV cache manager：block table + bank 映射，与 vLLM PagedAttention 接口对齐
- Bank-aware 负载均衡：KV head 到 bank 的映射策略
- 异步执行：Host 发起 attention offload 后继续做 FFN，NDP 并行计算

**3c. 端到端评估**

| 实验 | 目标 | 方法 |
|------|------|------|
| 微基准 | 单 operator 加速比 | attention kernel：RVV baseline vs 自定义 ISA vs GPU [FlashAttention](https://github.com/Dao-AILab/flash-attention) vs CPU |
| 端到端推理 | 系统级吞吐/延迟 | Llama-3-8B（GQA）decode，对比 [vLLM](https://github.com/vllm-project/vllm) on GPU |
| 场景敏感性 | 适用边界 | 变 batch size（1-16）× 序列长度（1K-64K）× 注意力机制（MHA/GQA/MLA） |
| 设计空间探索 | 参数化最优配置 | 变 NDP 核数（8-64）、频率（500M-1G）、scratchpad（4-64KB） |
| 面积/功耗估算 | 可部署性 | McPAT / Chisel 参数化模型 |
| vs UPMEM | 定制 vs 通用 | 在 UPMEM 上实现同样 attention 卸载做对比 |
| vs CENT | 开源 vs 闭源 | 用 CENT 论文数据做间接对比（无法复现其硬件） |

**产出**：评估数据 + 论文

---

## 五、论文定位

- 目标会议：ASPLOS / MICRO / ISCA（偏体系结构）
- 核心 claim：基于开源 RISC-V 的 in-DRAM NDP 架构，通过 ISA-workload 协同设计和参数化设计空间探索，为 LLM decode attention 提供**可复现的 NDP 研究基础设施**，并首次量化了 ISA 定制相比通用 RVV 的实际收益边界
- 与 CENT/STARC 的差异化：不是"NDP for LLM 能不能做"（已被证明），而是"如何通过开源 ISA 定制做得更好 + 让其他研究者也能做"
- 团队规模：3-4 人，12-14 个月

---

## 六、延伸方向

| 延伸 | 描述 | 依赖 |
|------|------|------|
| Long-context 专用 NDP | 128K+ 序列下 KV cache 极大，NDP 带宽优势最明显；与 L3 对标 | Phase 1 |
| SSD 端冷 KV cache | 冷 KV cache 存 SSD，SSD 内 RISC-V 核做 importance filtering（参考 [[fast2025-chen-weijian-impress\|IMPRESS]]） | Phase 1 |
| DPU 端推理调度 | DPU RISC-V 核运行 KV cache routing（参考 [[fast2025-qin\|MOONCAKE]] 分布式 KV pool） | Phase 3 |
| PIM-aware sparse attention | 与 STARC 方向结合，在 RISC-V NDP 上实现 bank-aligned 稀疏 attention | Phase 2 |

---

## 七、综合评估

| 维度 | 评分 | 说明 |
|------|------|------|
| Novelty | ★★★ | NDP for LLM attention 已有 CENT/STARC 等；剩余 novelty 在**开源 RISC-V ISA 定制 + 可复现设计空间探索** |
| 可行性 | ★★★★ | gem5 + Chipyard 成熟；范围已缩减到可执行；3-4 人 12-14 月 |
| 影响力 | ★★★★ | 开源全栈可复现 → 社区作为研究基础设施的价值大；但需真实 PIM 硬件才能产业落地 |
| 风险 | ★★ | GQA/MLA 对前提的削弱是主要风险；ISA 定制的增量收益可能有限；Phase 1 早期止损 |
| 时效性 | ★★★ | UPMEM 下一代转 RISC-V、XCENA 量产 → 窗口期仍在，但 CENT/STARC 已抢先发表 |

---

## 八、关键参考文献

### NDP/PIM for LLM（直接竞品）

- [CENT](https://arxiv.org/abs/2502.07578) (ASPLOS'25): "PIM Is All You Need"，CXL-enabled GPU-free LLM inference with near-bank PIM
- [L3](https://arxiv.org/abs/2504.17584) (arXiv, 2025): DIMM-PIM + GPU co-design for long-context LLM attention
- [STARC](https://arxiv.org/abs/2505.05772) (ASPLOS'26): PIM-aware sparse attention with bank-aligned KV clustering
- [HPIM](https://arxiv.org/abs/2509.12993) (arXiv, 2025): Heterogeneous SRAM-PIM + HBM-PIM for LLM
- [PAM](https://arxiv.org/abs/2602.11521) (arXiv, 2026): Tiered PIM for KV-centric LLM serving
- [PIM-AI](https://arxiv.org/abs/2411.17309) (arXiv, 2024): DDR5/LPDDR5 PIM for LLM inference
- [SAIL](https://arxiv.org/abs/2509.25853) (arXiv, 2025): ARM + near-data processors at L3 cache for LLM

### NDP/PIM/DPU 通用系统

- [[fast2025-cui\|PIMLex]] (FAST'25): PIM learned index，"用更多访问换更少计算"适配弱计算 PIM
- [[fast2025-zhu\|HiDPU]] (FAST'25): DPU 23KB 内存做 PB 级索引
- [[atc2025-wu-puqing\|PIMANN]] (ATC'25): UPMEM ANNS 细粒度调度，揭示 host-PIM 总线争用和负载不均问题
- [[osdi25-sun\|Scalio]] (OSDI'25): DPU JBOF 扩展
- [[atc2025-liu-ruili\|DSA-2LM]] (ATC'25): Intel DSA 加速页迁移
- [[osdi25-huang-yibo\|Tigon]] (OSDI'25): CXL pod 数据库
- [[fast2025-park\|SODE]] (FAST'25): 自适应 on-device vs in-kernel 执行
- [[fast2025-chen-weijian-impress\|IMPRESS]] (FAST'25): KV cache importance-aware 三层存储
- [[fast2025-qin\|MOONCAKE]] (FAST'25): 分布式 KV cache pool

### RISC-V + NDP 学术工作

- [NM-Caesar/NM-Carus](https://arxiv.org/abs/2406.14263) (EPFL, 2024): RISC-V NMC with `xvnmc` extension
- [AI-PiM](https://www.frontiersin.org/journals/electronics/articles/10.3389/felec.2022.898273/full) (Frontiers in Electronics, 2022): RISC-V + SRAM PIM functional units
- [PIMSys](https://github.com/SAITPublic/PIMSys) (MEMSYS'24): gem5-based PIM virtual prototype

### 开源硬件平台

- [Chipyard](https://github.com/ucb-bar/chipyard): UCB SoC 生成框架，集成 Rocket/BOOM/Gemmini
- [Rocket Chip](https://github.com/chipsalliance/rocket-chip): 经典 in-order RISC-V 核，适合轻量 NDP 控制器
- [CVA6/Ariane](https://github.com/openhwgroup/cva6): OpenHW 6-stage in-order 核，Linux-capable
- [XiangShan 香山](https://github.com/OpenXiangShan/XiangShan): 高性能开源 RISC-V，Kunminghu 6-wide OoO
- [WD SweRV EH1](https://github.com/westerndigitalcorporation/swerv_eh1): 面向 SSD 控制器的开源 RISC-V

### 开源模拟/EDA 工具

- [gem5](https://github.com/gem5/gem5): 全系统微架构模拟器，RISC-V 支持成熟
- [DRAMSys](https://github.com/tukl-msd/DRAMSys): DRAM 子系统模拟器，支持 DDR5/HBM/LPDDR
- [PIMSys](https://github.com/SAITPublic/PIMSys): Samsung 开源 PIM 模拟框架（gem5 + DRAMSys）
- [Ramulator2](https://github.com/CMU-SAFARI/ramulator2): CMU SAFARI 内存模拟器，支持 PIM 建模

### 开源 AI/系统软件

- [vLLM](https://github.com/vllm-project/vllm): LLM 推理引擎，PagedAttention KV cache 管理
- [SGLang](https://github.com/sgl-project/sglang): LLM 推理引擎，RadixAttention
- [FlashAttention](https://github.com/Dao-AILab/flash-attention): IO-aware attention 算法
- [LLVM](https://github.com/llvm/llvm-project): 编译器基础设施，RISC-V 后端完整支持
