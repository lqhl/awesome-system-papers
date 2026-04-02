# On-Demand Container Partitioning for Distributed ML

**作者**：Giovanni Bartolomeo*, Navidreza Asadi* (Technical University of Munich), Wolfgang Kellerer, Jörg Ott (Technical University of Munich), Nitinder Mohan (TU Delft)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/bartolomeo
**源文件**：[atc2025-bartolomeo.pdf](../../papers/atc-2025/atc2025-bartolomeo.pdf)

---

## 一、背景

随着 ML 模型规模和复杂度的增长，分布式部署已成为保证性能和扩展性的关键手段。在边缘计算环境中，设备硬件配置异构、资源受限，大模型需要被切分（split）为多个部分分布在不同设备上进行流水线式推理（split computing）。同时，模型需要频繁重训练和更新（如每 30-50 秒一次），对部署效率提出了极高要求。

目前，几乎所有主流 MLOps 框架（MLflow、Flower、SkyPilot 等）都依赖容器（Docker/OCI）来打包和部署 ML 模型。容器提供了运行环境隔离和跨平台可移植性，是事实上的标准。

---

## 二、要解决的问题

OCI 容器的分层文件系统（layered filesystem）设计适合代码和依赖管理，但**不适合 ML 模型的分布式部署场景**，主要痛点包括：

1. **构建开销爆炸**：将模型切分为 N 个 split 后，需要为每个 split 构建独立的 Docker 镜像。以 EfficientNet-V2L（82 splits）为例，构建时间从 81s（1 split）增长到 242s（82 splits），且可能组合的镜像数量呈指数增长（2^n）。
2. **缓存失效传播**：Docker 的层级结构是链式的——更新底层 layer 会导致其上所有 layer 缓存失效并重建，即使它们内容未变。模型频繁更新时，重建代价极高。
3. **无法按需获取子集**：传统容器镜像不支持只拉取部分内容，设备必须下载整个（臃肿的）镜像。
4. **替代方案的局限**：用 volume 挂载模型参数需要手动配置外部存储，在边缘环境不可行；运行时下载参数则绕过了容器运行时的缓存机制。

---

## 三、洞察与设计

**关键洞察**：ML 模型的各个 split/partition 之间天然是独立的——它们可以被独立构建、缓存和更新，无需像传统容器层那样维护链式依赖关系。容器注册中心（registry）通过 digest 寻址提供了优秀的对象检索机制，可以被复用来分发模型分片。

基于此洞察，作者提出 **2DFS（Two-Dimensional Filesystem）**，核心设计包括：

- **2dfs.field 层类型**：扩展 OCI 镜像规范，引入新的 media type `2dfs.field`。该层是一个稀疏矩阵（二维平面），每个单元格称为 **allotment**，包含独立的文件集合（如一个模型 split 的权重和架构）。Allotment 之间互不依赖、可交换（commutative），可并行构建。
- **2DFS Builder**：无需挂载到构建容器中——allotment 在本地直接计算 DiffID 和压缩 blob，全部并行执行。多层缓存层级（文件→目录→压缩 blob→field 定义）确保只有变更的 allotment 需要重建。
- **按需镜像分区（On-Demand Partitioning）**：通过语义化 tag（如 `image:tag--1.0.2.5`）向 2DFS 兼容的 registry 请求任意子集的 allotment。Registry 在 manifest 层面操作预构建的 allotment，将其序列化为标准 OCI layers 返回——无需重新构建镜像。
- **完全 OCI 兼容**：生成的分区镜像是标准 OCI 镜像，任何 OCI 运行时（containerd、Docker）无需修改即可使用。

---

## 四、实现细节

- **描述文件**：用户通过 `2dfs.json` 定义 allotment 的源文件、目标路径及二维坐标 `<row, col>`。
- **Builder CLI**：命令 `tdfs build [base-image] [target-image] [flags]`，基于 `2dfs.json` 扩展标准 OCI 镜像。
- **缓存层级**（C₀ → Cⱼ）：Key Cache 存储中间键和哈希指针，Blob Cache 存储所有压缩对象（以 sha256 命名），Index Cache 存储镜像索引。任何 allotment 变更只触发局部缓存失效。
- **Registry 扩展**：基于开源 OCI distribution 实现，新增 Partitioner（序列化分区为 OCI manifest）、语义 tag 解析器、2dfs.field 反序列化器。
- **模型切分策略**：使用 Keras API，按三原则切分——最小化 split 输出大小（在 aggregation 层后切分）、最大化灵活性（尽可能多 split）、均衡推理时间。将模型架构（计算图）与权重解耦，分别存储。
- **OCI 运行时兼容限制**：传统运行时最多支持 127 层，因此每个 partition 的 allotment 数需 ≤ 127。
- 开源项目：https://github.com/2DFS

---

## 五、实验结果

**实验平台**：构建服务器为 2× AMD EPYC 7302（16 核）+ 256GB RAM + 2TB SSD；Registry 服务器为 Intel i9-9820X + 128GB RAM + 1TB NVMe；边缘设备为 10 台 Raspberry Pi 4B（4× ARM Cortex-A72 + 8GB RAM），1Gb/s 以太网互联。

**模型集**：14 个真实 ML 模型（ResNet50/101/152、MobileNetV2、EfficientNet-V2 系列、YOLOv3、DeepLabv3+），split 数量从 18 到 82 不等。

| 实验 | 关键结果 |
|------|---------|
| 单镜像构建 | 2DFS 平均 **16× 快于** Docker；ENv2L 在 100% split capacity 时 **120× 快** |
| 多分区镜像构建 | 2DFS 平均 **56× 快于** Docker（Docker 需为每个 split 分别构建镜像） |
| 镜像下载 + 分区 | 按需分区仅增加约 **20ms** 延迟，带宽使用与预构建镜像相当 |
| 模型更新（Top-down） | 2DFS 平均 **25× 快于** Docker |
| 模型更新（Bottom-up） | 2DFS 最高 **75× 快于** Docker（Docker bottom-up 更新比从头重建还慢） |
| 镜像大小 | OCI+2DFS 与标准 OCI 镜像大小**基本一致**，无额外空间开销 |
| 端到端部署（MNv2L） | 10 台 RPi 部署：吞吐从 1.3 → 7.6 req/s；部署时间随 split 数对数递减 |

资源消耗方面，2DFS 构建时 CPU 使用率更高（并行计算 DiffID 和 blob），但总 CPU 时间更低（构建时间平均缩短 16×）。Registry 侧 CPU 开销仅增加约 1%。

---

## 六、批判性分析

1. **模型规模偏小，说服力不足**：14 个评估模型最大为 EfficientNet-V2L（119M 参数 / 454MB），在当今 LLM 时代属于极小模型。论文在 Discussion 中声称可以与 vLLM、DeepSpeed 集成处理 LLM，但未提供任何 LLM 规模的实验验证。对于数十 GB 甚至数百 GB 的 LLM，allotment 的构建和传输特性可能与小模型截然不同。

2. **比较基线过于简化**：与 Docker 的直接比较本质上是"为每个 split 单独构建完整 Docker 镜像" vs "一个 2DFS 镜像"。实际工程中，很少有人这样使用 Docker——更常见的做法是用共享基础镜像 + volume/S3 分发权重，或者使用多阶段构建。论文虽在 §2.3 讨论了这些替代方案的缺点，但未在实验中量化比较。

3. **127 层限制被轻描淡写**：OCI 运行时的 127 层限制意味着每个 partition 最多包含约 127 个 allotment。对于需要细粒度分片的大模型（如 LLM 的 tensor parallelism），这可能是实质性瓶颈。论文仅在 Discussion 中简单提及"未来工作"解决。

4. **边缘场景的假设偏理想化**：实验使用 1Gb/s 以太网互联的 10 台 RPi，远非真实边缘环境（异构网络、不稳定连接、NAT/防火墙）。论文声称解决边缘部署问题，但实验环境更接近局域网集群。

5. **端到端延迟增长被低估**：Figure 14c 显示端到端响应时间随设备数线性增长，10 台设备时已接近 1000ms。论文将此归因于"model fragmentation and networking overhead"，但没有深入分析通信瓶颈在不同网络条件下的变化。

6. **缺少与容器优化工作的对比**：如 Stargz/eStargz（lazy pulling）、SOCI（seekable OCI）等已有的容器镜像优化技术也致力于解决按需获取问题，论文未与之比较。

---

## 七、AI Infra / MLSys 视角

**对 LLM Serving 的潜在价值**：2DFS 的按需分区机制天然契合 LLM 的 tensor parallelism 和 pipeline parallelism 场景——不同 shard 可作为 allotment 独立管理，根据集群拓扑动态分配。这比当前主流方案（模型权重存 S3/HDFS + 运行时下载）多了容器级别的缓存和版本管理能力。

**与 Splitwise/DistServe 的结合**：PD（prefill-decode）分离架构中，prefill 和 decode 阶段使用不同的模型分片配置。2DFS 可以为同一模型生成不同的分区镜像，简化异构部署的镜像管理。

**模型更新场景**：对于需要频繁热更新权重的在线学习/微调场景（如 Ekya、RECL），2DFS 的独立 allotment 缓存机制可以将更新范围精确限定到变更的层，避免全量重建。

**值得跟进的方向**：
- 在 LLM 规模（7B-405B）上验证 2DFS 的性能，特别是 allotment 为 GB 级别时的构建和传输效率
- 将 2DFS 与 Kubernetes GPU operator 集成，实现基于 GPU 拓扑的自动分区调度
- 探索 2DFS 在模型版本管理（A/B testing、canary deployment）中的应用——不同版本的模型共享不变的 allotment

---

## 八、总结

2DFS 提出了一种扩展 OCI 容器格式的二维文件系统方案，通过将 ML 模型的各个 split 封装为独立的 allotment，实现了独立构建、缓存和按需分区。在 14 个模型上的实验表明构建速度提升 56×、缓存效率提升 25×，且完全兼容现有 OCI 生态。主要局限在于仅在小模型上验证、127 层上限限制，以及边缘实验环境过于理想化。该工作为容器化 ML 部署提供了一个有价值的新思路，但距离在大模型和真实生产环境中落地还需要进一步验证。
