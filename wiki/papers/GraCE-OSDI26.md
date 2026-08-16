---
type: paper
name: GraCE
full_title: "GraCE: Unlocking CUDA Graphs with Compiler Support for ML Workloads"
authors: [Abhishek Ghosh, Ajay Nayak, Ashish Panwar, Arkaprava Basu]
venue: OSDI
year: 2026
tags: [ml-systems, gpu, cuda-graph, compiler, pytorch]
source_pdf: "[[osdi26-ghosh.pdf]]"
source_md: "[[osdi26-ghosh]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-08-14
---

# 用编译器充分利用 CUDA Graph（OSDI 2026）

> **原题**：GraCE: Unlocking CUDA Graphs with Compiler Support for ML Workloads

> **一句话总结**：一处 CPU tensor、replay 时的大块参数复制，或一个本来就不值得 capture 的小 graph，都可能抵消 [[CUDA-Graph]] 的 kernel-launch 收益；GraCE 在 [[PyTorch]] 编译链中分别做代码变换、参数间接寻址和逐 graph profiling，在 25 个固定配置的 H100 workload 上相对 PyTorch2-CG 平均快 29%、最高快 3.36 倍，并避免了这组实验中的性能退化，代价是平均 2.21 倍的编译时间和更复杂的跨层改写。

## 问题与动机

现代 ML 程序一次 iteration 会发射几百到几千个 GPU kernel。单次 CPU launch 约需 5–10 μs，而新 GPU 上许多 kernel 本身也只运行几微秒；tensor parallelism 又会把单卡计算切得更短，并增加 collective kernel。论文以 DALLE2 为例：740 多个 kernel 的 GPU 执行合计只有 3.4 ms，端到端却要 14 ms，约四分之三时间落在 launch gap（§1、§2.1）。

CUDA Graph（CG）把一串 kernel capture 成 DAG，replay 时只需一次 CPU dispatch。困难不在于 API 不存在，而在于高层程序和底层 capture 规则相距很远：graph 会按值记录 kernel 参数，不允许同步 copy、allocation 等会同步 GPU 的操作，replay 时又必须处理变化的输入。错误处理可能得到 stale value、silent corruption 或 crash；保守处理则会放弃整个 FxGraph。

论文对 60 多个 PyTorch workload 的分析还发现两个反直觉现象。第一，一处 CPU scalar 或 CPU↔GPU copy 可以让周围数百个 kernel 全部失去 capture 机会。第二，CG 本身并非总是更快：116 个 graph 中有 29 个变慢，最差退化 397%，而且一个应用里可以同时存在有益和有害的 graph（图 3–4）。因此 GraCE 的目标不是“尽量多 capture”，而是让更多合适区域可 capture、减少 replay 成本，并拒绝负收益 graph。

## 关键观察 / 隐含假设

- **观察 1：一处高层数据放置决定的影响范围远大于它自身。** XLNET-I 只因一个 CPU tensor，使含 413 个 kernel 的 FxGraph 完全不能使用 CG；对 XLNET、Speech Transformer 做很小的人工放置修改后，启用 CG 时分别快 3.17 倍、2.28 倍，而不开 CG 时四个示例平均只改善 6.29%（图 3、§2.3.1）。
  - **依赖假设**：CPU tensor 可以移到 GPU，或者 copy 可以提前到 constructor，而不改变 host 可见更新、alias、lifetime 和显存预算。
  - **可能失效场景**：input-dependent CPU control、CPU/GPU 共享 tensor、动态创建对象，或显存已经接近上限。
- **观察 2：PyTorch2 为可变输入保留静态 placeholder，会把数据复制放到每次 replay 的关键路径。** DALLE2 和 Deep Recommender 中，这部分分别占 graph 执行时间的 24% 和 17%（§2.3.2）。
  - **依赖假设**：把 data copy 换成 8-byte pointer copy，再在 kernel 中解引用，其成本比原来的 GPU 内复制低。
  - **可能失效场景**：参数很小、数量很多，H2D pointer copy 或 vendor prelude 已经比 D2D data copy 更贵；论文在 DALLE2 上就没有看到 PI 收益。
- **观察 3：是否使用 CG 必须按 graph 决定。** 初始分析中 25% graph 变慢；主评测里 PyTorch2-CG 又让 25 个应用中的 4 个至少慢 3%，EOS 最差慢 29%（图 4、图 10）。
  - **依赖假设**：编译时用固定 shape、batch 和目标 GPU 得到的 profile，能代表之后的 replay。
  - **可能失效场景**：shape、数据路径、GPU contention 或软件版本变化后，旧选择可能不再正确。
- **观察 4：GPU 越快、模型切得越细，launch gap 越重要。** 四卡 TP 会让每卡 kernel 更短；论文在四个 workload 上看到 GraCE 相对 PyTorch2-CG 的收益扩大（图 12）。
  - **依赖假设**：CPU launch 而非通信、长 kernel 或输入准备仍是主要空洞。
- **假设 1：编译成本能被长期、重复执行摊薄。**
  - **证据强度**：中。训练和常驻 serving 通常成立，但最高 506 s 的编译对 notebook、短任务和频繁 recompile 很重。

## 核心方法

**1. 先定位为什么不能 capture。** GraCE 嵌入 TorchDynamo 和 TorchInductor 的 slow path（图 6）。InductorIR 已带 shape、device placement 和回到 TorchIR/bytecode 的 debug mapping；当 PyTorch2 判定某个 FxGraph 不可 capture 时，GraCE 沿这条映射追到 CPU scalar、CPU↔GPU copy、CPU output 或 input mutation，而不是只返回“不可 graph 化”。

**2. CUDA Graph-aware Code Transformation（CGCT）改写高层语义。** 对 CPU scalar，系统重写 Dynamo bytecode，让它构造 GPU tensor；对 CPU-to-GPU copy，则把 tensor 搬到 GPU，并把 copy 提前到对象 constructor；对 CPU output，系统修改对应 TorchIR metadata，再重新 lower。这样只修一处阻塞点，就能让整个 FxGraph 进入 capture（图 7、§4.1）。这是扩大覆盖率的来源，也是 correctness 风险最大的部分。

**3. Parameter Indirection（PI）只复制地址。** 对 [[Triton]] JIT kernel，GraCE 把需要变化的 pointer 参数改为 pointer-to-pointer，并通过自定义 LLVM/PTX pass 在 kernel 入口解引用；每轮只把新地址 H2D 写到稳定 placeholder。对 cuBLAS 等不可改 binary 的 vendor kernel，GraCE 在 graph 开头插入 NVRTC 编译的 prelude kernel，再用 CUDA 12.4 的 device-side graph-node update API 修改真正 kernel 的参数（图 5、8）。后一路径参数多时会超过 10 μs，所以只作为 fallback（图 9）。

**4. Graph-capture 层维护新的 placeholder。** 原 PyTorch2 为数据分配静态 placeholder，并在 replay 前复制内容；GraCE 只为 pointer 分配 placeholder，把 pointer copy 和随后 graph replay 放在同一 stream，利用 stream 顺序保证正确性。这样还不必在 graph 生命周期内保留重复输入 storage（§4.2.2）。

**5. Selective CUDA Graph（SCG）拒绝负优化。** 每个候选 FxGraph 在编译期最多实测三种 module：不用 CG、用 CG 但不用 PI、同时用 CG 和 PI。系统缓存最快的一种，fast path 不再做在线选择。分开测试后两种很重要，因为小对象的 [[PCIe|PCIe]] pointer copy 可能比 HBM 内 data copy 更慢（§4.3）。

**6. 实现边界。** GraCE 依赖 PyTorch2 的 Dynamo、Inductor、Triton codegen 和 CUDA graph capture，但思路也可移植到有类似 IR 和 JIT backend 的 JAX/XLA。论文没有把它集成到只部分支持 `torch.compile` 的 [[vLLM|vLLM]]，也没有与手工修改 kernel/driver 的 Grape 做量化对比（§4.4、§6）。

## 设计取舍

- **覆盖率换语义与显存风险。** 把 host tensor 变成 device tensor 可解锁数百个 kernel，也可能改变 host observation、对象 lifetime 或 HBM 使用。
- **少复制换一层间接寻址。** Triton rewrite 较轻，但 vendor prelude 依赖 CUDA 12.4 API、parameter-buffer offset 查找和额外 kernel；参数多时成本会明显上升。
- **无测得 regression 换 profiling。** SCG 对每个固定配置尝试多个版本，运行时简单，编译时间和临时内存却更高。
- **硬件定制换可预测性。** H2D、HBM、kernel launch 和 graph 管理成本随 GPU/PCIe 改变，因此 profile 必须在目标机器上进行，cache 也要按硬件与软件版本管理。
- **适用边界。** 短 kernel 多、shape 稳定、replay 次数多、GPU 较快时最合适；长 GEMM 主导、动态控制频繁或任务寿命很短时收益会缩小。

## 实验设置

- 主实验选择 25 个对 CUDA Graph 敏感的 TorchBench、HuggingFace 和 TIMM workload，覆盖 vision、NLP、HPC、training 与 inference；它们不是上述 60 多个初始分析 workload 的无偏全集（表 1、§5）。
- H100 主机使用 94 GB H100 NVL、64-core Xeon 8462Y+、PyTorch 2.4 和 CUDA 12.8；四卡 TP 实验另用 4×80 GB H100/NVLink 和 CUDA 12.4。A6000 是额外硬件检查。
- 指标是固定 batch 下的每 iteration 时间；每项报告 100 个不同 input 的平均值。基线是同版 PyTorch2-No-CG 与 PyTorch2-CG，没有 JAX/XLA、专用 serving runtime 或手工调优上界。
- 论文主要评测固定配置，没有 production shape trace、并发 GPU tenant、长时间 allocator 行为或 recompile rate。

## 实验与结果

- **端到端 H100 性能**：25 个固定 workload 上，GraCE 相对 PyTorch2-CG 的 geomean 改善为 29%，最高为 XLNET-I 的 3.36 倍；相对 PyTorch2-No-CG，图 10 的 geomean 为 1.56 倍，而 PyTorch2-CG 为 1.27 倍。PyTorch2-CG 有 4 项至少退化 3%，GraCE 在这 25 项上都不差于 No-CG 与 CG 两个选择中的较好者（图 10、§5.1）。
- **扩大 capture 覆盖**：CGCT 使 XLNET-I、MMC、Speech Transformer 相对 PyTorch2-CG 分别快 3.14、2.31、2.00 倍。六个受影响应用中，MMC、XLNET-I 的覆盖率从 0 提到 99.32% 和 99.28%；Speech Transformer 从 5.14% 提到 74.22%（图 11、表 2）。
- **减少 replay copy**：PI 让 TKE、Deep Recommender inference 分别再快 23% 和 18%；MTCG-T 的每轮参数复制从 1 GB 降到 312 B，其他所测应用在 PI 后最多只剩 336 B。PI 并非总有益，DALLE2 就因 pointer 路径成本没有改善（表 3、§5.2）。
- **选择性部署**：SCG 在主评测的 123 个候选 graph 中启用 97 个；Vision Mask R-CNN 的 21 个候选只启用 4 个，端到端因此再改善 6%，EOS 则直接关闭唯一 graph，避免 PyTorch2-CG 的 29% 退化（图 11、§5.2）。
- **多 GPU 与跨硬件**：四个 TP workload、1/2/4 张 H100 上，论文汇总 GraCE 相对 PyTorch2-CG 最高快 3.56 倍、平均快 75%；XLNET 在 TP=4 时相对同 TP 的 No-CG 为 3.48 倍（图 12、§5.3）。A6000 上相对 No-CG 的平均加速为 1.18 倍，PyTorch2-CG 为 1.06 倍；GraCE 仍未在所测配置退化。
- **编译与内存成本**：GraCE 编译时间平均是 PyTorch2-CG 的 2.21 倍，BSCG 最差为 3.2 倍，绝对最长是 TEFD 的 506 s；编译峰值内存平均高 12%。作为回报，replay 阶段没有新增峰值内存，并因不保留 data placeholder 最多节省 15%（图 13、§5.3）。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| 编译器修复少量高层阻塞点可大幅扩大 CG 覆盖 | 表 2：两项从 0 到约 99%，其余四项也明显上升 | 六个 PyTorch workload、固定 shape/device placement | 强 |
| 参数间接寻址能消除大块 replay copy | 表 3：1 GB 降到 312 B，最大剩余 336 B | PyTorch2 CG placeholder；H100；小参数可能无收益 | 强 |
| 按 graph profiling 能避免测得的负优化 | 图 10–11：4 个 PyTorch2-CG regression 被避免；97/123 graph 被启用 | 25 个 CG-sensitive 固定配置，不代表动态生产负载 | 强 |
| GPU 更快或 TP 更高时 GraCE 更有价值 | 图 12：TP 上相对 PyTorch2-CG 最高 3.56 倍、平均 75% | 四个 workload、最多 4×H100/NVLink | 中到强 |
| GraCE 对任意 PyTorch 程序都保持语义和性能 | §4 的设计说明与 25 项性能测试 | 无系统化 differential correctness、动态 shape 或全 PyTorch corpus 结果 | 弱 |

## 批判性分析

### 论证链条

论文把三个独立失败模式分别映射到 CGCT、PI 和 SCG，再以 capture coverage、copy bytes 和 selective-deployment 消融逐项闭环，论证很清楚。双基线也很重要：它防止系统把“关掉有害 CG”包装成相对一个坏默认值的纯加速。最需要收窄的是“没有 regression”——实验只证明 25 个固定配置上没有，SCG 的决定随 shape、硬件和 contention 漂移后仍可能过时。

### 假设压力测试

若线上 batch、sequence length 或控制路径不断变化，同一个 FxGraph 可能反复重编译，或者旧 profile 不能代表新 workload。将 CPU tensor 移到 GPU 还可能改变 host 读取时机和显存压力。PI 把 HBM copy 换成 PCIe pointer copy，并非天然更快；vendor kernel 的 prelude 又随参数数目增长。长 kernel、通信或 input preprocessing 成为主瓶颈时，launch gap 也不再主导。

### 实验可信度

25 个真实 suite workload、training/inference、两类 GPU 和 TP=1/2/4 提供了较好的内部证据，且 ablation 与机制直接对应。外部有效性较弱：作者主动筛选了 CG-sensitive 应用，结果不能解释整个 TorchBench 的总体收益；基线只比较 PyTorch2 自身的两个开关；没有 P95/P99 iteration、动态 shape trace、数值 differential、能耗或并发 tenant。多 GPU 最多四卡，也不足以证明更大 TP 会继续放大收益。

### 系统性缺陷

GraCE 跨 Dynamo bytecode、TorchIR、InductorIR、Triton LLVM/PTX 和 CUDA runtime 五层改写，PyTorch 或 CUDA API 更新都可能破坏它。vendor prelude 通过 parameter buffer 的 byte pattern 找 offset，兼容性和诊断成本较高。论文没有讨论 profile cache invalidation、失败后 fallback、编译隔离、graph 数量增长和在线 observability；最高 506 s 的 compile latency 也会拖慢 autoscaling 与短任务。

## 局限与后续工作

- **局限 1**：主要结果来自 25 个预先筛选的 CG-sensitive、固定配置 workload，不能外推为全部 ML 程序的平均收益。
- **局限 2**：SCG 是离线 profile 决策，没有验证动态 shape、batch drift、GPU contention 和软件升级后的稳定性。
- **局限 3**：CGCT 修改 device placement 与 bytecode，论文未给系统化数值等价、alias/lifetime 或 host-observability 测试。
- **局限 4**：只与 PyTorch2-No-CG/CG 比较，未测专用 serving runtime、JAX/XLA 实现或手工优化上界。
- **后续工作 1**：重放 production shape/batch trace，记录 graph cache hit、recompile 次数、profile drift、P99 iteration 和错误选择率，并在 drift 后自动 reprofile。
- **后续工作 2**：对 CGCT 生成 CPU/GPU alias 与 lifetime obligation，用随机 input differential test 比较改写前后的输出、exception 和 host-visible tensor。
- **后续工作 3**：在 8–64 GPU TP、mixed compute/communication 和 background tenant 下，测 launch gap、collective gap、goodput 与每个 profile 的有效期。
- **后续工作 4**：按 PyTorch/CUDA/Triton 版本构造兼容矩阵，注入 node-update 失败、stale pointer 和 compile crash，测安全 fallback 与 cache invalidation。

## 相关

- **相关概念**：[[CUDA-Graph]]、[[GPU-Kernel-Launch]]、[[Tensor-Parallelism]]、[[ML-Compiler]]
- **同类系统**：[[PyTorch]]、[[TorchInductor]]、[[Triton]]、[[Grape]]
- **同会议**：[[OSDI-2026]]
