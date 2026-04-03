# Torpor: GPU-Enabled Serverless Computing for Low-Latency, Resource-Efficient Inference

**作者**：Minchen Yu (CUHK-Shenzhen, HKUST), Ao Wang (Alibaba Group), Dong Chen, Haoxuan Yu, Xiaonan Luo, Zhuohao Li, Wei Wang (HKUST), Ruichuan Chen (Nokia Bell Labs), Dapeng Nie, Haoran Yang, Yu Ding (Alibaba Group)
**会议**：USENIX ATC 2025
**链接**：[USENIX](https://www.usenix.org/conference/atc25/presentation/yu)
**源文件**：[[atc2025-yu.pdf]]

---

## 一、背景

随着机器学习推理服务在云端的广泛部署，Serverless computing 因其按需付费、自动扩缩容、免运维等特性，成为部署推理服务的理想模式。然而，当前主流 serverless 平台（如 AWS Lambda、阿里云函数计算）对 GPU 的支持极为低效：它们沿用 serverful 模式的 early binding 方法，在函数创建时就将其绑定到特定 GPU 上，模型常驻 GPU 内存。

阿里云生产环境数据显示，85% 的推理函数平均每分钟被调用不超过一次，97% 不超过每秒一次。这种低频访问模式下，early binding 导致 GPU 资源大量空闲浪费。若为节省成本频繁回收 GPU 资源，则会导致冷启动延迟（数十秒级），远超推理 SLO 要求。

---

## 二、要解决的问题

1. **GPU 资源浪费与高成本**：Early binding 使低频函数长期占据 GPU 内存，用户需为空闲 GPU 付费，云厂商 GPU 利用率低下且负载不均衡
2. **冷启动延迟过高**：回收 GPU 后重新启动函数需数十秒（包含容器创建、ML 框架初始化、GPU runtime 创建、模型加载），远超毫秒级 SLO 要求
3. **缺乏 SLO 感知调度**：现有系统要么不考虑延迟 SLO，要么假设推理延迟稳定（不适用于存在 PCIe 带宽竞争的 model swapping 场景）
4. **模型无关性要求**：商业环境中出于知识产权和业务机密考虑，平台不能检查模型内部结构

---

## 三、洞察与设计

**关键洞察**：主机内存相比 GPU 内存容量大得多（TB vs. 数十 GB）且成本更低，可以作为空闲模型的理想存储位置。通过 late binding——将空闲模型保持在主机内存，仅在请求到达时动态 swap 到 GPU——可以同时实现按 GPU 使用付费、高 GPU 利用率和快速函数恢复。

基于此洞察，Torpor 的核心设计包括：

**GPU Pooling 架构**：每个 worker node 将本地所有 GPU 作为资源池统一管理，推理函数通过 CUDA API 重定向透明地访问任意可用 GPU，实现无缝的模型 swap 和负载均衡。

**异步 API 重定向**：利用推理计算的特性——中间步骤在 GPU 上异步执行、中间数据不需要回传主机——将 CUDA API 分为同步（如 cudaMalloc）和异步（如 cudaLaunchKernel）两类，异步 API 可批量重定向而无需等待结果，大幅降低通信开销。

**流水线模型执行**：将模型参数分组，使后续层的传输与前序层的计算重叠。采用 model-agnostic 的方式确定分组大小——寻找传输吞吐量随分组大小增加而趋于平稳的"拐点"（约 2MB），无需模型结构知识。

**干扰感知请求调度**：将模型按 PCIe 带宽需求分为 heavy 和 light 两类。优先使用 NVLink 进行 GPU 间模型传输以避免 PCIe 竞争；当必须使用 PCIe 时，避免同时加载 heavy 模型。

**SLO 感知请求排队**：定义 Required Request Count (RRC) 指标衡量函数达成 SLO 的难度，优先服务 RRC 较小（更可能达成 SLO）的函数。

**模型驱逐策略**：全局管理 GPU 内存池，优先驱逐 light 模型（swap 开销可忽略），heavy 模型之间采用 LRU 策略。

---

## 四、实现细节

- **GPU Server + GPU Client 架构**：GPU Server（4k 行 C++ 代码）管理 GPU 池中的 executor 和内存；GPU Client（1.5k 行 C++）替换函数容器中的原始 CUDA 库（如 libcudart.so），透明地将 CUDA 调用重定向到 GPU Server
- **内存地址管理**：在 block 级别维护内存映射，模型参数地址 = block 地址 + 偏移量，避免逐指针维护的开销
- **Buddy 内存分配**：预留全部 GPU 内存，扩展 Buddy allocation 方案，合并同模型的内存块以减少碎片，支持跨模型的相同大小 block 共享
- **Pinned Memory Pool**：在主机端使用 pinned memory 加速 host-to-GPU 数据传输
- **隔离模式**：提供 runtime sharing（单 runtime 多模型，适用于可信环境）和 runtime isolation（每模型独立 runtime，适用于生产环境）两种模式
- **容错**：函数失败时重启，executor 失败时将模型迁移到其他 GPU；GPU Server 将 runtime 状态持久化到本地存储以支持快速恢复

---

## 五、实验结果

**实验环境**：阿里云集群，最多 6 个 worker node，每节点 48 vCPU、384GB 内存、4× NVIDIA V100 (32GB)。8 种模型（DenseNet-169/201、Inception-v3、EfficientNet、ResNet-50/101/152、Bert-qa）。

| 指标 | 结果 |
|------|------|
| GPU Remoting 延迟 | CV 模型与 Native 持平甚至更优（CPU workload 分布效应），Bert-qa 约等于 Native |
| 相比 GVirtuS | ResNet-152 延迟降低 88%，Bert-qa 降低 37% |
| Model Swap (PCIe) | Pinned memory 减少约 35% 延迟，pipeline 再减 15%，分组再减 22% |
| 低频函数效率 | 10 r/m 时吞吐量超 Native 10×，tail latency 仍低于 50ms |
| 负载均衡 | 40 个高频函数在 4 GPU 上，GPU 间负载方差远低于 Native |
| 单节点 SLO | 480 个函数下仍满足所有 SLO（Native 仅支持 72 个，INFless-KA 仅 7 个 SLO 达标） |
| 集群扩展 | 6 节点 1000+ 函数下持续满足 SLO，Native/NonSwap/SimpleSwap 均严重违反 SLO |

**生产部署**（阿里云 pilot）：

| 指标 | 数值 |
|------|------|
| 用户数 | >150 |
| GPU 数量 | >350 |
| 日请求量 | 最高 465k |
| 用户成本节省 | 平均 70% |
| 平台 GPU 节省 | 65% |
| Llama2-13B 启动时间 | 4.4s（vs 冷启动 61s） |

---

## 六、批判性分析

1. **评估模型规模偏小**：主要实验使用的 8 个模型中 7 个是 CV 模型（ResNet、DenseNet 等），参数量和显存占用很小（1.6GB-2.4GB）。虽然 Table 1 展示了 LLM 的启动时间，但缺乏 LLM 场景下的端到端性能和 SLO 达标率评估。对于 LLama3-8B、Qwen-14B 等模型，swap 延迟可达数秒，但论文未给出这些模型在多函数共享场景下的表现

2. **不支持模型并行**：论文坦承不支持跨 GPU 的模型并行，这意味着 Torpor 无法处理单 GPU 装不下的大模型——而这恰恰是当前 LLM 推理的主流场景。将 late binding 与 tensor/pipeline parallelism 结合是一个未解决的核心问题

3. **V100 实验平台的代表性**：所有实验在 V100 (32GB) 上进行，而当前生产环境主流已是 A100/H100 (80GB+)。PCIe 带宽、NVLink 拓扑、GPU 内存容量的变化可能显著影响 Torpor 设计决策的有效性（如 heavy/light 分类阈值、管线分组大小等）

4. **RRC 指标的假设**：SLO 感知排队基于 RRC 指标，其核心假设是通过优先服务"接近达标"的函数可以最大化 SLO 达标函数数。但这实质上是在牺牲已经落后的函数，可能导致某些函数持续饥饿——论文未讨论公平性问题

5. **Runtime isolation 开销未充分评估**：生产环境使用 runtime isolation 模式，但性能评估（§7）全部使用 runtime sharing 模式。Table 1 显示 runtime isolation 的 runtime resumption 需要 0.19s-1.9s，这个开销在高频场景下是否可接受缺乏实验验证

6. **与 LLM 推理系统的比较缺失**：论文未与 vLLM、TGI 等 LLM serving 系统进行比较。对于 LLM 场景，KV cache 管理是关键瓶颈，论文仅简单提到"将 KV cache 作为模型的一部分处理"，但未给出具体方案和性能数据

---

## 七、AI Infra / MLSys 视角

**启发价值**：
- Late binding + model swapping 的范式为低频 LLM 推理服务（如企业内部的多租户 fine-tuned 模型）提供了一种全新的资源共享思路，与当前 LLM serving 系统中 prefill/decode 分离、PagedAttention 等优化正交互补
- 异步 CUDA API 重定向的技术可以推广到其他需要 GPU 虚拟化的场景，如多租户 GPU 集群管理

**可迁移的技术**：
- 基于模型"重量"（PCIe 带宽敏感度）的分类和调度思路，可应用于 LLM serving 中不同大小模型的混合部署
- Buddy memory allocation + block 级地址管理的设计，与 vLLM 的 PagedAttention 在内存管理层面有异曲同工之处，可探索两者的结合

**值得跟进的方向**：
1. **Torpor + Model Parallelism**：将 late binding 扩展到跨 GPU 的大模型推理，需要设计 swap-aware 的 tensor/pipeline parallelism 策略
2. **多层存储架构**：论文提到但未实现的 host memory → SSD → 远端存储的多级缓存体系，对于管理数千个 fine-tuned LLM 变体很有价值
3. **与 Prefill-Decode 分离的结合**：Torpor 的 GPU pooling 机制可能与 DistServe 等 prefill/decode 分离系统结合，用 late binding 处理低频请求的 prefill 阶段

---

## 八、总结

Torpor 提出了一种面向 serverless 推理的 GPU 高效共享平台，核心思想是 late binding——将空闲模型保持在主机内存，请求到达时动态 swap 到 GPU 池中执行。通过异步 API 重定向、流水线模型加载、干扰感知调度和 SLO 感知排队等技术，Torpor 在单节点上可支持数百个推理函数同时满足毫秒级 SLO。该系统已在阿里云生产环境部署，实现用户成本降低 70%、平台 GPU 节省 65%。主要局限在于当前不支持模型并行，且核心实验以小型 CV 模型为主，在 LLM 大模型场景下的表现有待验证。
