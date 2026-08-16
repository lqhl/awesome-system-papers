---
type: paper
name: MuShell
full_title: "μShell: A Microkernel-based FPGA Shell Architecture"
authors: [Jiyang Chen, Anubhav Panda, Harshavardhan Unnibhavi, Atsushi Koshiba, Pramod Bhatotia]
venue: OSDI
year: 2026
tags: [fpga, microkernel, accelerator, isolation, scheduling]
source_pdf: "[[osdi26-chen-jiyang.pdf]]"
source_md: "[[osdi26-chen-jiyang]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 基于微内核思想的 FPGA Shell（OSDI 2026）

> **原题**：μShell: A Microkernel-based FPGA Shell Architecture

> **一句话总结**：μShell 把原本整体部署的 FPGA accelerator 拆成可跨 vFPGA 连接的模块，用硬件 capability 检查、直接流式 IPC 和“优先复用已驻留模块”的调度来动态组装应用；U280 原型的平均吞吐损失为 3.3%，调度实验的总完成时间降低 24%–35%，但共享仅支持无状态模块，而且 partial reconfiguration 在调度实验中是用预先测得的延迟模拟的。

## 问题与动机

常见云 FPGA 把芯片分成静态 shell 和多个可部分重配置的虚拟 FPGA（vFPGA）。现有 shell 通常假设：一个应用已经被综合成一个单体 accelerator，再把它放进一个 vFPGA。这个接口容易隔离，却和真实应用的结构不一致。图像、音频、安全和压缩 pipeline 往往由 FFT、AES、RSA、RLE 等独立模块串起来，不同应用还会复用相同模块。

论文对 Vitis Vision 应用的分析发现，最多 93% 的应用对共享至少一个函数，超过 20% 的应用对相关度大于 0.5；共享部分最高可占一个应用 80% 的 FPGA 资源（图 2、5）。如果仍把整条 pipeline 固化成单体 bitstream，改一个模块便要重新综合整个应用，相同模块会重复占资源，切换应用还要重新配置整块 vFPGA。

另一个要求是保留硬件模块之间的直接数据通路。图 3 中，相比让 CPU 依次调用每个模块，直接连接对 Audio 和 Speech 分别快 3.7 倍和 2.7 倍；其余三个应用只有 1.0–1.1 倍。也就是说，模块化不能以所有数据都绕回 host 为代价。论文正文前面写“最高 2.63 倍”，图 3 和 §2.2 写“最高 3.7 倍”，两处数字不一致；这里按具体实验图使用 3.7 倍。

## 关键观察 / 隐含假设

- **观察 1：应用之间存在可复用的硬件组件。** 模块级部署可以只更新发生变化的部分，并让多个应用复用已驻留模块。
  - **隐含假设**：相同功能的模块具有兼容的端口宽度、时钟、顺序和状态语义。
  - **可能失效**：应用高度定制，或跨模块综合优化比模块复用更重要。
- **观察 2：模块之间应走直接流式通路。** Audio 和 Speech 的 CPU-mediated 版本明显较慢（图 3）。
  - **隐含假设**：应用能表达成事先建立好的流式 dataflow，组件间不需要频繁 host 参与或动态 RPC。
- **观察 3：复用已驻留模块可以少做 partial reconfiguration（PR）。** 实测单次 PR 约 58 ms，而更新一个 object 或 memory capability 只需 2–3 μs（图 13）。
  - **隐含假设**：所需模块经常已经驻留；缺失模块仍然必须 PR。
- **假设 1：capability 检查足以支持安全共享。** CEU 能拒绝越权 endpoint 和越界 DMA。
  - **证据强度**：中等偏弱。论文描述并实现了检查路径，但没有恶意模块、撤销竞态、侧信道、拒绝服务或形式化验证实验。
- **假设 2：模块可以安全地跨租户复用。** 当前实现只共享无状态 accelerator；切换前等待不可抢占任务结束，并依赖 HLS reset 清除残留状态。
  - **证据强度**：中。边界写得明确，但没有验证 BRAM、寄存器和流水线中所有残留状态都能可靠清除。

## 核心方法

**1. 每个 vFPGA 前放一个 Capability Enforcement Unit。** 图 8–9 中，μShell 的静态区域包含 PR controller、DMA scheduler、中央 data interconnect，以及每个 vFPGA 独立的 CEU。CEU 有 send、receive 和 memory 三类 gateway；endpoint 保存 object capability 或 memory capability，validator 检查目标 vFPGA、端口、地址范围和读写权限。非法发送或内存请求会被丢弃并通知 OS；收到的非法 stream 会被 drain，以免其他组件卡住。

**2. 用中央交换机建立直接 IPC。** CEU 为合法 stream 生成包含源、目的 vFPGA 和端口的 route ID，AXI Stream Switch 依据它转发，不让数据回到 CPU。共享同一源或目的的 stream 用 round-robin 仲裁。I/O wrapper 负责端口复用和数据宽度转换，因此用户逻辑不必理解 shell 内部路由。所有模块和 channel 必须在任务开始前准备好；运行时 OS 不在数据路径上。

**3. OS 管理 capability、地址空间与模块生命周期。** 每个应用拥有独立 capability space 和地址空间。Capability Control Manager 支持 create、delegate、revoke，并用树保证子 capability 的权限不超过父节点；每个应用的 MMU/TLB 也相互独立。应用完成后，系统回收 endpoint、页表和 capability。当前共享对象必须是无状态模块；stateful accelerator 可以独占、不共享。由于 FPGA 任务不可抢占，系统等当前执行结束后才切 capability，并依赖 HLS reset 清理 accelerator 状态（§4.1–4.2）。

**4. component-aware scheduler 优先避免 PR。** 调度器先选最高优先级应用；同优先级时，选与空闲 vFPGA 上已有逻辑重合最多的应用。等待过久的应用会提升优先级，避免完全饿死。策略是 non-preemptive，并要求开发者把 pipeline 各阶段切得足够均衡。工具链仍要求为每个“逻辑模块—目标 vFPGA”组合分别生成 bitstream；两个模块、两个 vFPGA 就可能需要四份 bitstream（§4.2、§8）。

**5. API 让应用只描述 dataflow。** 用户用 `dataflow()` 建图，`create_task()` 和 `create_buffer()` 建节点，`connect()` 建边，再用 `execute()` 提交。library 根据边自动委派最小所需 capability；OS 负责选择 vFPGA、加载缺失逻辑、分配 buffer、设置 CEU/MMU，并启动整条 pipeline（表 3、Listing 1）。

**6. 原型基于 Coyote v2。** 实现在 AMD Alveo U280 上，中央 AXI Stream Switch 最多提供 16 对接口，其中一对留给 host，因此最多连接 15 个 vFPGA；实验最多使用 8 个。机器为 AMD EPYC 7413 2.65 GHz、NixOS 23.0、Linux 6.9（§6）。artifact 附录另写 NixOS 25.11 和 Linux 6.9.0-rc7，环境描述存在版本差异。

## 设计取舍

- **模块化换少量数据路径开销。** CEU 检查和动态路由使平均吞吐比 Coyote v2 低 3.3%。
- **复用换状态约束。** 当前只共享无状态模块；如果把 stateful accelerator 也共享，必须增加可靠的保存、恢复或清零机制。
- **任意点对点连接换互连资源。** CEU 和 MMU 随 vFPGA 数量线性增长，近似 full-mesh 的 interconnect 约按平方增长。
- **少 PR 换 bitstream 管理复杂度。** scheduler 可以复用驻留模块，但工具链仍要求每个逻辑针对每个 PR region 单独综合。
- **高层 API 换显式控制。** 应用代码更简单，但开发者仍需设计 RTL/HLS 模块、接口兼容性和均衡 pipeline；API 不能消除硬件验证成本。
- **适用边界。** 模块重合高、任务足够长、PR 占比明显、数据天然流式时收益最大。低复用、极短任务、强状态依赖或跨模块全局优化场景收益会减弱。

## 实验设置

五个 benchmark 都是来自开源库的**内核级 pipeline**，不是完整 end-to-end 应用（表 4）：

| 应用 | 组件 |
|---|---|
| Audio processing | FFT、Quantization、RLE |
| Digital signature | SHA256、RSA |
| Secure storage | RLE、AES-CTR |
| Signed compression | RLE、RSA |
| Speech recognition | FFT、SVM |

性能实验使用 8 KiB、256 KiB 和 1 MiB 输入，每个点运行 10 次。baseline 是同一 U280 上的 Coyote v2；其他开源 shell 不支持该硬件，论文没有移植比较。调度实验使用 Digital signature、Signed compression 和 Audio processing，每 20 ms 注入 8、12 或 16 个实例，并随机赋予三个优先级。

## 实验与结果

### 数据通路与部署开销

- 图 11 中，模块分散在多个 vFPGA 的 μShell 比 Coyote v2 平均少 3.3% 吞吐；Audio、Digital signature、Secure storage、Signed compression、Speech recognition 的开销分别为 2.9%、2.9%、4.2%、2.8%、3.9%。作为控制组，单体 μShell 与 Coyote v2 的差异在 ±1.4% 内，说明主要开销来自 CEU endpoint 检查和跨 vFPGA 路由，而不是 memory gateway。
- 图 13 的部署比较假设所有所需组件已经驻留。Coyote 要做约 58 ms 的 PR；μShell 只更新 capability，每个 object 或 memory update 为 2–3 μs，另有约 350 μs 的 buffer allocation。若组件缺失，μShell 同样要做 PR，因此这个结果是理想复用场景，不是所有部署的固定延迟。

### 调度效果及其重要边界

论文无法让 Coyote 的 PR 在多个 vFPGA 上正常工作，原因是 interrupt handling。于是作者预先放置 SHA256、RSA、RLE、FFT 各两份，只把四个组件标为 active；当 scheduler 选择 idle 组件时，再**注入预先测得的 PR 延迟**。因此图 12 测的是调度器加 PR 延迟模型，而非真实并发 PR 控制路径。两种策略都允许复用已经空闲且逻辑匹配的 vFPGA，区别主要是 μShell 按优先级和组件重合度选任务，Coyote 使用 FIFO。

- 总完成时间降低 24%–35%，μShell 的 reconfiguration 数保持在 5–7 次，Coyote 约多 3–5 倍；论文摘要把最大减少量写为 79%（图 12a–b）。
- 平均响应时间降低 21%–33%，P95 响应时间降低 28%–39%，deadline miss 数减少 46%–64%（图 12c–e）。deadline 是按每个组件的平均响应时间、优先级和 40–80 的随机量合成，并非真实应用 SLO；一个双组件应用还可能记两次 miss。

### 可编程性与资源

- 表 5 中，相比 Coyote host code，μShell 的 cyclomatic complexity 降低 25.0%–51.2%，SLoC 则变化 -2.0% 至 +23.4%。这说明控制流更简单，但没有测开发时长、bug 数或硬件代码复杂度。
- 按表 6 的绝对数量重算，三个 vFPGA 时，μShell 独有的 CEU 和 interconnect 合计使用约 1.4% LUT、0.7% register、1.1% BRAM；§6.5 正文所写的 0.9% register 与表格计数不一致。八个 vFPGA 时，对应占比约为 6.7% LUT、2.0% register、3.0% BRAM，而不是所有资源都为 6.6%。interconnect LUT 约随 vFPGA 数平方增长；原型虽然最多可连接 15 个 vFPGA，却没有报告 15 个时的 frequency 或 timing closure。

## 论断—证据表

| 论断 | 证据 | 证据边界 | 置信度 |
|---|---|---|---|
| 动态跨 vFPGA IPC 的吞吐代价较小 | 图 11：平均吞吐损失 3.3%，单应用为 2.8%–4.2% | 单张 U280、五个内核级 pipeline | 强 |
| 复用组件能减少排队与 PR | 图 12：总完成时间低 24%–35%，PR 数少约 3–5 倍 | 合成到达和优先级；PR 用延迟注入模拟 | 中 |
| 已驻留组件可快速重新组合 | 图 13：capability update 为 2–3 μs，PR 约 58 ms | 所有组件已驻留的理想场景 | 中 |
| capability 能阻止越权 IPC 和 DMA | §4.1 的 CEU validator 实现 | 没有攻击实验、形式化证明或撤销竞态测试 | 弱到中 |
| 互连开销在八个 vFPGA 内可接受 | 表 6：按绝对数量重算，CEU 与 interconnect 合计约占 6.7% LUT、2.0% register、3.0% BRAM | 未覆盖 15 个 vFPGA、multi-FPGA 和 timing closure | 中 |

## 批判性分析

### 论证链条

论文从“应用是模块化的”“直接连接有价值”“PR 很慢”三个观察，推导出 CEU、IPC 和 component-aware scheduler，设计与动机对应得很清楚。μShell_mono 也能隔离 gateway 与跨 vFPGA 路由的成本。最明显的跳步是把五个内核级组合外推为完整云应用，并把模拟 PR 的调度结果表述成原型端到端改进。

### 假设压力测试

模块存在内部状态、可变长度 stream 或 backpressure cycle 时，任务结束和“状态已清空”都不容易判断。一个恶意模块可以长时间不结束，使 non-preemptive scheduler 无法撤销；也可以持续制造合法但拥塞的 stream。不同 clock、port width、ordering 和版本还会形成兼容矩阵，使“同名模块可复用”不再简单。

### 实验可信度

Coyote v2 是同硬件、同基础 shell 的直接 baseline；吞吐、调度、部署、代码复杂度和资源都给了量化结果，artifact 也公开。局限同样明确：只有一张 U280；应用不是完整系统；没有真实多租户 arrival trace；调度中的 PR 没有实际执行；deadline 是合成的；没有安全、故障恢复、deadlock 或公平性实验。因而吞吐 overhead 的证据较强，调度和隔离结论只能算中等或较弱。

### 系统性缺陷

capability 只约束“谁能访问哪里”，不能自动解决模块是否正确终止、是否泄露时序、是否占满链路、是否清掉所有内部状态。论文还没有覆盖 bitstream 签名与认证、capability 撤销时在途数据、组件 crash、共享模块公平性、循环 dataflow 的 deadlock，以及版本升级时的接口兼容。每个逻辑—vFPGA 对一份 bitstream，也会造成编译、存储和发布组合爆炸。

## 局限与后续工作

- **局限 1**：共享只支持无状态 accelerator；stateful 模块只能独占，reset 的完整性没有实验验证。
- **局限 2**：调度实验的 PR 是延迟注入，不包含真实 reconfiguration controller、interrupt 和失败路径。
- **局限 3**：只有单 U280、最多八个 vFPGA 的测量，没有 multi-FPGA 或 15-vFPGA 实验。
- **后续工作 1**：在修复真实多-vFPGA PR 后重复图 12，报告 PR 成功率、interrupt 开销、P99 响应时间和故障恢复时间。
- **后续工作 2**：注入越界 DMA、stale capability、模块 hang、残留 BRAM 数据和 backpressure cycle，测数据泄露、撤销延迟、隔离故障与 deadlock recovery。
- **后续工作 3**：在 8、12、15、32 个跨单卡或多卡 vFPGA 下比较 mesh、分层交换机和 NoC 的 LUT、频率、吞吐与 timing-closure 成功率。
- **后续工作 4**：运行至少三个完整多租户应用，使用真实到达和 SLO，测模块实际复用率、bitstream 数量、PR 次数和端到端成本。

## 相关

- **相关概念**：[[FPGA-Virtualization]]、[[Microkernel]]、[[Capability-Based-Security]]、[[Partial-Reconfiguration]]
- **同类系统**：[[Coyote]]、[[AmorphOS]]
- **同会议**：[[OSDI-2026]]
