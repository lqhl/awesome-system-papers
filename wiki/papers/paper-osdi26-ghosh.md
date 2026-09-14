---
type: paper
name: GraCE
full_title: "GraCE: Unlocking CUDA Graphs with Compiler Support for ML Workloads"
authors: [Abhishek Ghosh, Ajay Nayak, Ashish Panwar, Arkaprava Basu]
venue: OSDI
year: 2026
tags: [cuda-graphs, ml-compiler, pytorch, gpu-utilization, kernel-launch]
source_pdf: "[[osdi26-ghosh.pdf]]"
source_md: "[[osdi26-ghosh]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-06-24
---

# 用编译器释放 CUDA Graph 的覆盖范围与收益（OSDI 2026）

> **原题**：GraCE: Unlocking CUDA Graphs with Compiler Support for ML Workloads

> **一句话总结**：ML 工作负载中 CPU kernel launch 已成为瓶颈，但 CUDA Graph 会受 CPU 张量、参数拷贝和盲目部署影响；GraCE 用图感知代码变换、参数间接寻址和选择性 profiling 修复这些问题，在 25 个 workload 上相对 PyTorch2-CG 平均快 29%、最高 3.36×，且不引入回归。

## 问题与动机

现代 ML 迭代通常发射数百个短 GPU kernel。H100 上 GPU 计算变快后，CPU 逐个发射 kernel 的 5–10 微秒开销进入关键路径。论文以 DALLE2 为例：740 多个 kernel 的 GPU 执行合计 3.4 ms，但端到端耗时 14 ms（§2.1）。CUDA Graph 可把一串发射压缩为一次 dispatch，但它按值记录 kernel 参数，并禁止部分同步操作，因此普通 PyTorch 程序并不天然适配。

现有 PyTorch2-CG 还会把变化的参数复制进静态 placeholder。该复制在 DALLE2 和 Deep Recommender 中分别占端到端时间的 24% 和 17%（§2.3.2）。此外，框架对所有可捕获 graph 盲目启用 CUDA Graph；116 个 graph 中有 29 个变慢，最差退化 397%。

## 关键观察 / 隐含假设

- **观察 1：一个 CPU 张量或 scalar 就能阻断很长的 graph。** XLNET inference 中单个 CPU tensor 使 413-kernel FxGraph 完全无法捕获；简单的设备放置修改可带来 3.17× 加速（§2.3.1、表 2）。
  - **依赖假设**：编译器的 IR 能把低层失败节点映射回 Python 对象并安全改写。
  - **可能失效场景**：输入依赖控制流、外部副作用或必须保留 CPU 输出时，设备搬移可能改变语义或无法完成。
- **观察 2：参数数据拷贝是 graph replay 的主要额外成本。** 参数可能达到数百 MB，而地址只有 8 B；MTCG-T 的拷贝从 1 GB 降至 312 B（表 3）。
  - **可能失效场景**：小参数集合中 PCIe 指针拷贝可能反而比 HBM 内的短数据拷贝更慢；论文因此不能把参数间接寻址视为普适最优。
- **观察 3：CUDA Graph 的收益依赖 graph 粒度和硬件。** EOS 的短 kernel 使 replay、RNG 和内存管理开销占约一半，PyTorch2-CG 退化 29%（§5.1）。
  - **隐含假设**：编译阶段 profiling 的结果能代表之后重复 replay 的成本；输入形状和硬件在缓存生命周期内相对稳定。

## 核心方法

GraCE 构建在 PyTorch2 的 Torch Dynamo 与 Torch Inductor 上。CUDA Graph-aware Code Transformation（CGCT）检查 InductorIR 的 graph eligibility 失败原因：把 CPU scalar 改成 GPU tensor，把 CPU-to-GPU copy 提前到 graph 区域之前，并修正相关设备元数据。它用 debug mapping 追溯到生成对象的字节码，再让 Dynamo 重新生成 IR（§4.1）。这把 [[PyTorch2]] 的高层语义与 CUDA Graph 的底层限制连接起来。

Parameter Indirection（PI）把 kernel 的 pointer 参数替换成 pointer-to-pointer。每次 replay 只更新指针，而不是复制参数数据。对 Triton JIT kernel，GraCE 修改 PTX 签名并插入解引用指令；对 cuBLAS 等不可改写的 vendor kernel，则插入 prelude kernel，利用 CUDA 12.4 的 device-side graph management API 更新参数（§4.2）。

Selective CUDA Graphs（SCG）在编译和捕获阶段分别测量无 graph、带 graph、带 PI 的三种模块，缓存最快配置。这样把选择成本放入 slow path，避免 fast path 中动态决策，也承认 PCIe 与 GPU memory bandwidth 的硬件差异（§4.3）。

## 设计取舍

- **收益与编译成本**：SCG 需要运行多个候选模块，GraCE 平均使编译时间增加 2.21×，最高 506 s；作者认为重复执行时可摊销（§5.3）。
- **通用性与实现复杂度**：Triton kernel 可直接重写，vendor kernel 需要 NVRTC、参数缓冲区模式匹配和 prelude kernel。后者随参数数量增长较慢（图 9）。
- **边界条件**：PI replay 阶段减少峰值内存最多 15%，但编译阶段峰值内存平均增加 12%。SCG 在 123 个候选 graph 中只启用 97 个，说明“可捕获”与“值得捕获”是两个问题。

## 实验与结果

- H100 NVL、PyTorch 2.4、CUDA 12.8 上的 25 个 TorchBench、HuggingFace 和 TIMM workload 中，GraCE 相对 PyTorch2-CG 平均快 29%，最高为 XLNET inference 的 3.36×；GraCE 部署了 413 个原本未捕获的 kernel（图 10）。
- CGCT 使 XLNET-I、MMC、ST 相对 PyTorch2-CG 分别达到 3.14×、2.31×、2×；XLNET-I 和 MMC 原先没有 graph，部分 workload 的 graph kernel 覆盖率超过 99%（图 11、表 2）。
- PI 让 TKE 和 DR-I 分别快 23% 和 18%；多项 workload 的参数拷贝降至几百字节以内（图 11、表 3）。
- SCG 在 EOS 中关闭有害 graph，避免 29% 退化；在 VM 的 21 个候选 graph 中只启用 4 个，端到端快 6%（§5.2）。
- 四卡 NVLink tensor parallel 实验中，XLNET 在 TP-4 达到相对 PyTorch2-No-CG 的 3.48×，不同 TP 设置平均 2.41×（图 12）；A6000 上 GraCE 也未出现回归。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| GraCE 扩大 CUDA Graph 覆盖并改善性能 | 图 10、表 2；XLNET-I 最高 3.36× | 25 个 workload，H100，PyTorch 2.4 | 强 |
| 参数间接寻址降低 replay 拷贝成本 | 表 3；1 GB 降至 312 B | 参数变化通过 pointer 更新，vendor kernel 走 prelude | 强 |
| 选择性部署避免 graph 回归 | §5.2；EOS 关闭 graph，VM 仅启用 4/21 | profiling 假定运行环境和形状稳定 | 中 |
| 分布式 TP 放大 GraCE 的价值 | 图 12；XLNET TP-4 达 3.48× | 四卡 H100 NVLink，4 个 workload | 中 |

## 批判性分析

### 论证链条

论文的链条基本闭合：CPU launch 与 graph 约束造成覆盖和成本问题，CGCT 修复覆盖，PI 减少参数搬运，SCG 处理剩余成本。主要跳步是把编译期样本 profiling 当作长期最优选择；动态 batch、shape 或 GPU 竞争下的决策稳定性没有实验覆盖。

### 假设压力测试

结果主要来自 H100、A6000 和固定 batch 配置。真实 serving 中请求形状、并发度、GPU 时钟和多租户干扰会变化，SCG 缓存的 winner 可能过时。PI 把 host-to-device 指针拷贝引入 replay；在 PCIe 拥塞或大量小参数时，其优势可能消失。论文未验证故障恢复、graph invalidation 和多租户隔离。

### 实验可信度

基线是同版本 PyTorch2-No-CG 与 PyTorch2-CG，且报告了消融、覆盖率、拷贝量、单卡和 TP 结果。工作负载覆盖面较广，但只选取对 CUDA Graph 敏感的 25 个程序，不能直接代表全部 PyTorch 应用。编译时间最高 506 s，生产部署的冷启动代价仍需按服务生命周期评估。

### 系统性缺陷

实现依赖 CUDA 12.4+ 的 device-side API、Triton/PTX 改写和 vendor kernel 参数布局。升级 CUDA、Triton 或外部库可能破坏这些接口。论文未讨论 graph 捕获失败后的诊断、动态 shape 的缓存膨胀、服务滚动升级和跨进程资源回收。

## 局限与后续工作

- **局限 1**：SCG 是静态选择，尚未证明在动态请求和资源争用下仍保持最优。
- **局限 2**：实验规模主要是单机单卡与四卡 TP；更大规模通信拓扑和多租户场景未覆盖。
- **后续工作 1**：按 shape、并发和硬件状态维护可淘汰的 graph 配置，并测量在线切换成本与 P99。
- **后续工作 2**：在 CUDA、Triton 和 vendor library 多版本矩阵上验证 PI 的兼容性与正确性。

## 相关

- **相关概念**：[[CUDA Graphs]]、[[ML Compiler]]、[[Kernel Launch]]
- **同类系统**：[[PyTorch2]]、[[Triton]]、[[Grape]]
- **同会议**：[[OSDI-2026]]
