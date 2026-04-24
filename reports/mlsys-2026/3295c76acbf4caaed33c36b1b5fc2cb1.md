---
title: "ParallelKittens: Systematic and Practical Simplification of Multi-GPU AI Kernels"
authors: [Stuart H. Sul, Simran Arora, Benjamin F. Spector, Christopher Ré]
year: 2025
venue: MLSys
tags: [multi-gpu, communication-overlap, cuda-kernel, dsl, nvlink, tensor-parallel]
---

# ParallelKittens: Systematic and Practical Simplification of Multi-GPU AI Kernels

**作者**:Stuart H. Sul, Simran Arora, Benjamin F. Spector, Christopher Ré
**单位**:Stanford University, Department of Computer Science
**会议**:MLSys 2026
**链接**:https://proceedings.mlsys.org/paper_files/paper/2026
**源文件**:[[3295c76acbf4caaed33c36b1b5fc2cb1.pdf]]

---

## 1. 背景

模型规模持续扩张迫使训练/推理跨多卡分布,但硬件演进的不平衡正在让 inter-GPU 通信成为新的性能瓶颈。从 A100 到 B200,BF16 tensor core 算力提升 7.2×、HBM 带宽提升 5.1×,而节点内 NVLink 带宽仅提升 3×、节点间 PCIe/InfiniBand 仅提升 2×。即使在 NVLink 全互联和 prefill 这类计算密集阶段,通信也可能占据 >50% 的执行时间,让 GPU 算力闲置。

为了榨取性能,业界已经在常见算子(GEMM、attention、MoE)上做了大量 compute-communication overlap 工作:Flux、Comet、Ring Attention、DeepEP 等。但这些工作普遍存在三类问题:(i) 实现高度算子专用,依赖 CUTLASS / NVSHMEM / Linux IPC 等复杂底层原语,缺乏可复用抽象;(ii) 编译器路线(Triton Distributed)难以泛化到新硬件,有时甚至慢于 non-overlapped baseline;(iii) 直接套用通信库(NCCL/NVSHMEM)又因库本身的设计开销,落后手调实现 4× 以上。

随着 NVL72 → NVL144 → NVL576 这种"机柜即超级 GPU"的趋势,系统社区急需一组通用、轻量的多卡 kernel 编程原语,让普通 kernel 工程师也能写出 peak-performance 的 overlap 代码。

---

## 2. 要解决的问题

作者把"如何写出最优 multi-GPU kernel"拆成三个被现有方案忽视或简化掉的设计维度,并指出每个维度上现有方案的具体不足:

1. **传输机制选择被简化** —— 现代 GPU 提供三种通信机制:copy engine(host-initiated DMA)、TMA(device-initiated 异步 bulk transfer)、register-level instruction(`ld/st`、`multimem.*`),它们在最大带宽、最小消息粒度、功能支持(in-network reduction)、SM 占用上特性差异极大。例如 Triton Distributed、Flux、CUTLASS 在 intra-node all-gather GEMM 上一律用 copy engine,导致小矩阵下比 non-overlapped baseline 还慢。

2. **调度策略单一化** —— overlap 有两种调度方式:inter-SM(SM 池切分,部分 SM 专做通信)和 intra-SM(SM 内 warp 切分,compute warp 与 communication warp 并行)。两者在不同 workload 下各有优势,但现有工作大多只用一种,或干脆把通信丢回 host stream。例如把 Flux 的 intra-SM GEMM-RS 设计套到 GEMM-AR 会显著变慢,因为 AR 受益于 in-network reduction,而后者只有 inter-SM 路径才能用。

3. **通信库的设计开销被掩盖** —— NCCL 强制双向同步 + intermediate buffer 中转,NVSHMEM 每次 peer 访问都要 `ldg` 取地址 + `__syncthreads`。这些开销在大消息下被掩盖,但在 fine-grained overlap 场景下能造成 1.79× 的纯通信 kernel 减速、4.5× 的 element-wise NVLink 访问延迟。

核心问题:**有没有一组小而通用的原语,能把这三个维度的最优选择暴露给开发者,让 <50 行代码写出 hand-tuned 级别的 overlap kernel?**

---

## 3. 洞察与设计

**关键洞察**:多 GPU kernel 的性能可以用一个 cost model 完整刻画 ——

$$T_{\text{kernel}} = T_{\text{launch}} + \max(T_{\text{comp}}, T_{\text{mem}}, T_{\text{comm}}) + T_{\text{non-overlap}} + T_{\text{sync}}$$

而决定这些项的只有三个独立的设计选择(传输机制、调度策略、抽象设计开销)。一旦 kernel 框架在这三个维度都暴露最优选项,各类 workload(DP/TP/SP/EP)的最优 overlap 实现就退化为"按 workload 特性挑组合"的工程问题,不再需要每个算子从头手调。从这个洞察出发,作者通过微基准量化每个维度的可行选项及其交叉优势区间,得出三条具体设计准则:

- **传输机制**:device-initiated 优于 host-initiated。TMA 仅需 ~15 SM、2 KB 消息粒度即可达 74% peak NVLink 带宽,远胜 copy engine 的 ≥256 MB 粒度门槛;register-level `multimem` 是 in-network reduction 的唯一通道。
- **调度策略**:当通信粒度与计算粒度对齐时(如 GEMM-RS),用 intra-SM,因为 tensor core 在所有 SM 都满载,且 mbarrier 同步只要 64 ns(inter-SM 经 HBM 是 832 ns);当能用 in-network reduction(GEMM-AR)或需要 bulk pre-fetch 缓存(Ring Attention 的远端 KV)时,用 inter-SM,把几个 SM 专门留给通信。
- **抽象设计**:走预分配目标 buffer + 单向直传,跳过 NCCL 的双向 channel + intermediate staging;peer 地址直接放寄存器,跳过 NVSHMEM 的 `ldg` + `__syncthreads`。

**ParallelKittens(PK)框架** 把以上洞察打包成 ThunderKittens 的扩展:

- **数据结构层** 沿 GPU 内存层级一一对应:`rt<M,N>` 寄存器 tile、`st<M,N>` 共享内存 tile、`gl` 全局 layout、新增的 **PGL(Parallel Global Layout)** 表示跨设备同形 HBM 区域,作为 P2P / 多播 / in-fabric reduction 的统一句柄。
- **8 个新原语** 覆盖三类操作:P2P 通信(`store_async`、`store_add_async`)、网络加速通信(`reduce`、`all_reduce`)、跨 SM/设备同步(`signal`、`signal_all`、`wait`、`barrier`)。所有原语 tile-granularity、device-initiated、coord 用 `int4` 索引。
- **LCSC 程序模板**(Loader-Consumer-Storer-Communicator)用四个 worker role 分别封装:loader/storer 处理本地或 peer HBM 访问(intra-SM overlap),consumer 跑 tensor core,communicator 独占若干 SM 跑通信(inter-SM overlap)。模板自动处理 SM/warp 划分搜索、shared memory 与 TMA 配置、barrier 管理,用户只需填四个函数体。

---

## 4. 实现细节

PK 用 C++ embedded DSL 形式扩展 ThunderKittens(TK)框架,而非新做编译器。这一选择保留 CUDA 全部底层控制,同时利用 TK 已有的寄存器/共享内存 tile 抽象与 swizzling、tensor-core friendly layout。

**关键实现层面的几个细节:**

- **Multi-GPU 内存初始化** 抽象掉了三种 mapping 方式:CUDA UVA(单进程)、CUDA IPC(多进程,但不能用 NVSwitch 加速)、手动 VMM(多进程 + 支持 NVSwitch in-network 加速)。PK 的 IPC/PyTorch 工具自动处理 `cuMemCreate` → `cuMemExportToShareableHandle` → 经 Unix domain socket 传 file descriptor → `cuMemImportFromShareableHandle` → `cuMemMap` 的完整 VMM 流程,以及多播对象的 `cuMulticastCreate` + per-device 注册。这是多 GPU 编程里普通开发者最容易踩坑的部分。
- **PGL 与 multicast object** 通过双地址(local address + multicast address)统一暴露:写 multicast address 触发 NVSwitch 广播,读 multicast address 配合 `multimem.ld_reduce` / `multimem.red` PTX 指令实现 in-fabric reduction。
- **LCSC 启动接口** `lcsc::launch_kernel<config, globals, lcsc_template>(G, stream)` 通过 compile-time `config` 指定 SM/线程数,`num_comm_sms` 在 host 端给出 SM 划分,框架自动做 producer-consumer 同步。论文 Appendix D 给出的 fused GEMM+AR 例子里,LCSC 模板下的 communicator 函数主体只有 3 行(wait barrier + `__syncthreads` + `all_reduce`)。
- **代码规模**:每个 PK kernel 在原始 single-GPU GEMM/attention kernel 之上新增 <50 行 device 代码即可完成 overlap;EP 场景的 token dispatch + grouped GEMM 不到 40 行。
- **开源与生产采用**:代码合入 ThunderKittens 仓库(https://github.com/HazyResearch/ThunderKittens),已被 Cursor 用于内部大规模训练。

---

## 5. 实验结果

平台:8×H100 80GB SXM(NVLink Gen4 + NVSwitch),CUDA 12.6,PyTorch 2.8.0,BF16 输入 + FP32 累加;另在 8×B200(NVLink Gen5,900 GB/s)上验证 generality(Appendix A)。

**Microbenchmark 验证三大设计维度:**

| 维度 | 关键发现 |
|------|----------|
| 传输机制 | Copy engine 在 H100 上达 82% NVLink 峰值带宽但需 ≥256 MB 粒度;TMA 达 78%、仅需 2 KB 粒度;register-op 76%。TMA 仅用 ~15 SM 饱和带宽,register-op 需 ~76 SM。 |
| 调度策略 | GEMM-RS 在 intra-SM 比 inter-SM 快 1.2×;GEMM-AR 通过 inter-SM + in-network reduction 比 intra-SM 快 3.62×。 |
| 库开销 | PK pure all-reduce 比 NCCL 快 1.79×(Figure 6);peer-memory 访问延迟比 NVSHMEM 低 4.5×、带宽多 ~20 GB/s。 |

**端到端 kernel 性能(均与最强 baseline 对比):**

| Workload | Baselines | PK 加速比 | 残余 non-overlap 比例 |
|----------|-----------|-----------|------------------------|
| AG+GEMM / GEMM+RS / GEMM+AR(DP+TP) | cuBLAS+NCCL, Triton Distributed, Flux, CUTLASS | 1.06–1.68× vs non-overlap;1.07–5.63× vs Triton-Dist;0.97–2.33× vs Flux;0.90–7.39× vs CUTLASS | <1%(K 足够大时) |
| Ring Attention(SP) | xDiT(NCCL P2P + FA3 split-stream) | 1.07–4.08× | 9% |
| DeepSpeed-Ulysses(SP) | YunChang | 1.01–1.39× | — |
| Token dispatch + grouped GEMM(EP) | Comet | 0.92–1.22× | 15% |

**额外 collective 验证(Appendix B)**:在 tensor-dim AG/RS、4D all-to-all 这种非连续 layout 下,NCCL 必须额外 reshape + copy,PK 直接在原 layout 上跑;具体加速比未在主文中以单一数字给出,但 Figures 15–17 显示 PK 在小到中等规模上拉开数倍差距。

**`K ≥ sR/(2B)` 的隐藏式验证**:作者预测 H100 BF16 GEMM-RS 在 $K \gtrsim 2197$ 时通信完全被算力 hide;Table 3 实测 K=2048 时 comm ratio 降至 26%、K=4096 时 <1%,与公式吻合。

---

## 6. 批判性分析

**强项是设计哲学的清晰度**:把多 GPU kernel 性能拆成"传输机制 × 调度策略 × 抽象开销"三轴,每一轴都有可量化的微基准,这种拆解方式给后续工作提供了非常清晰的对照框架。但仔细审视论文的论证链,有几处值得挑剔:

1. **"少于 50 行 device code"是误导性指标**。PK 之所以能让 kernel 这么"短",是因为底层 ThunderKittens 已经预先封装了 GEMM/attention 的全部寄存器/共享内存编排,以及 LCSC 模板自动管 warp 划分、TMA 描述符、mbarrier。把这些隐藏成本加回来,真实需要理解的代码量与 hand-tuned CUTLASS 不在同一量级是有问题的。论文应直接给出"PK + TK + LCSC infrastructure 总行数"才公平。

2. **跟 Comet 在 EP 上只 0.92–1.22×,且部分点 PK 更慢**。EP 是 MoE 训练/推理里最贵的通信模式之一,PK 给出的是"matches or surpasses",但 0.92× 意味着部分场景反而更慢,paper 没有解释具体在哪些 (TopK, expert count, token shape) 配置下 PK 会输,也没分析输的根因——是 LCSC 模板的 SM 划分搜索粒度不够细,还是 PK 还没用上 DeepEP 那种 token-level packed 通信?

3. **"完全跨架构"被夸大了**。论文反复批评 Triton Distributed 在 H800 上调好的 kernel 拿到 H100 会变慢,但 PK 自己的 LCSC 模板需要 host-side 指定 `num_comm_sms`,且每个 workload 的 SM 划分仍然是 auto-tune 出来的,即从 H100 迁到 B200 仍要重新搜索。文中 B200 实验只覆盖 GEMM-RS 和 DeepSpeed-Ulysses 两类,EP / Ring Attention 在 Blackwell 上的表现完全缺失。

4. **inter-node 完全不在 scope**,但 NVL72/NVL144 趋势之下,intra-node 所谓"机柜即 GPU"和真正跨节点的 InfiniBand/RoCE 边界并非那么清晰。论文用"inter-node 是 future work"一句带过,等于回避了 NCCLX、DeepEP 这类必须处理跨节点的系统的核心难题(链路异构、容错、流控)。

5. **公式 $K \gtrsim sR/(2B) = 2197$ 与 Table 3 K=2048 的 26% comm ratio 实际不严格一致**。作者用"residual due to atomic accumulation"解释,但 26% 离"完全 hide"差距不小,公式作为设计 guideline 的精度其实不高,正文里却被用作 PK 设计原则的核心证据之一。

6. **Pure all-reduce 1.79× 的对比 baseline 是 NCCL,而不是 NVSHMEM 或自研 multimem all-reduce kernel**。NCCL 设计目标本身就不是 fine-grained kernel-fused 场景,这个比较类似拿"重型可移植库"对比"裸金属优化",对 PK 太友好。

---

## 7. AI Infra / MLSys 视角

这篇论文对 AI Infra 研究者的价值非常直接,因为它解决的就是 LLM 训练/推理框架最痛的瓶颈之一:多卡 overlap kernel 的可维护性。几个值得跟进的方向:

**可立即借鉴的设计 idea:**
- **三轴拆解 + 微基准量化** 是设计任何 multi-GPU 系统时都应先做的功课。在自家代码库审视 NCCL/NVSHMEM/Triton-Dist 调用点时,可以套用这个表格快速判断"我们卡在哪一轴"。
- **PGL + multicast 双地址抽象** 是把 NVSwitch in-network compute 暴露给上层最干净的方式,可以反向影响国产 GPU 的 SDK 设计(如华为昇腾的 HCCL、寒武纪的 CNCL),它们目前对 in-network reduction 的暴露还很粗。
- **LCSC 模板** 的 worker role 划分非常适合作为 LLM serving 引擎(vLLM、SGLang、TensorRT-LLM)的下层 kernel infra,可替代当前对 NCCL stream-level overlap 的依赖,尤其在 chunked prefill / speculative decoding 这种细粒度调度下。

**具体 future work 切入点:**
- **inter-node PK**:作者明说不做。但跨节点 IB/RoCE 引入"链路非对称、容错、收敛流控"三大新维度,与 PK 内 NVSwitch 同构对等的假设差距巨大。真正有挑战性的工作是把 LCSC 模板的 communicator role 扩展到能跑 NCCLX-like 的多链路 hash/path-aware 调度。
- **PK + 推理 KV cache 通信**:论文未涉及 disaggregated prefill/decode 场景,但 PK 的 fine-grained TMA + tile-level barrier 极适合替代 Mooncake / DistServe 中粗粒度的 KV cache transfer kernel。一个直接 follow-up 是在 PK 之上写出 KV cache prefill→decode 的 fused transfer kernel。
- **LCSC 自动调优 → cost-model-driven**:目前 SM 划分是 runtime auto-tune,搜索空间不大但每次迁移硬件都要重跑。把论文的 cost model 显式建模成 ILP / 解析公式,可能能消掉 auto-tune,让 PK kernel 真正"一次写,跨架构跑"。
- **MoE EP 场景的胜率提升**:针对 PK 在 Comet 上只有 0.92–1.22× 的部分输点,定位是 SM 划分不够细 vs 缺 DeepEP-style packed 通信,有可能是一个 8-12 周的小论文级别工作。

---

## 8. 总结

ParallelKittens 把 multi-GPU AI kernel 的性能优化系统性地拆成传输机制、调度策略、抽象开销三个正交维度,通过 8 个 tile-级别的原语 + LCSC 编程模板,让 <50 行 device 代码就能写出与 Flux/Comet/CUTLASS 相当甚至更好的 overlap kernel。在 8×H100 上对 DP/TP/SP/EP 四类典型 workload 都展示了显著加速(SP 最高 4.08×),并已被 Cursor 用于生产训练。主要局限是 inter-node 完全未涉及、部分 EP 场景慢于 hand-tuned 基线、以及"少于 50 行"的代码量指标隐藏了大量底层 TK + LCSC infrastructure 成本。从 AI Infra 研究角度,PK 的三轴拆解方法论、PGL/multicast 抽象、LCSC 模板都极具迁移价值,推理引擎和国产 GPU SDK 的下层 kernel 设计都值得参考。
