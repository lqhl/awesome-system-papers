# Poby: SmartNIC-accelerated Image Provisioning for Coldstart in Clouds

**作者**：Zihao Chang, Jiaqi Zhu (ICT, CAS; UCAS), Haifeng Sun (Peking University), Yunlong Xie, Kan Shi, Ninghui Sun, Yungang Bao, Sa Wang (ICT, CAS; UCAS)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/chang
**源文件**：[[atc2025-chang.pdf]]

---

## 一、背景

云计算的核心承诺之一是按需弹性伸缩（on-demand scaling），但冷启动（coldstart）问题是实现这一目标的主要性能障碍。当一个新的容器实例被触发创建时，完整的冷启动流程包括：（1）容器镜像准备（下载、解压、解包），（2）容器启动，（3）应用初始化。其中，镜像准备（image provisioning）占据了冷启动总延迟的 72% 以上。

现有的冷启动优化主要有三类方向：
- **Warm start**：预启动容器并保持运行，但资源开销大，违背按需付费原则
- **Fast recovery**：基于快照/checkpoint 快速恢复，但存储开销大且要求容器无状态
- **Fast download**：P2P 加速镜像下载，但忽略了镜像解压（extraction）这一关键瓶颈

阿里云的生产数据显示，平均每个容器每天仍会经历超过 130 次冷启动，冷启动问题不可能被完全回避。

---

## 二、要解决的问题

1. **镜像解压被忽视**：现有工作主要优化镜像下载，但实验表明镜像解压（decompression + unpacking）占据镜像准备时间的 68.8% 以上，是真正的性能瓶颈
2. **解压导致严重的性能干扰**：镜像解压是 CPU 密集型操作，会导致同机部署的 Redis 等应用尾延迟增加 110 倍以上
3. **串行执行带来的等待延迟**：传统镜像准备流程是串行的 store-and-forward 模式（下载→解压→解包），各阶段之间存在大量等待
4. **集中式镜像仓库的可扩展性瓶颈**：当多节点并发拉取同一镜像时，中心化 registry 成为瓶颈（8 节点并发下延迟增加 6-10 倍）

---

## 三、洞察与设计

**关键洞察**：镜像准备流程中的不同操作（下载、解压、传输、解包）各自适合不同的硬件执行单元——RDMA 网卡适合高带宽下载，SmartNIC 上的硬件加速器适合解压，PCIe 适合大块数据传输，Host CPU 适合文件解包。通过将这些操作解耦并分派到最合适的硬件上，同时以流水线方式并行执行，可以大幅加速整个镜像准备流程。

基于这一洞察，Poby 设计了三个核心机制：

### 1. Disaggregated Architecture（解耦架构）

将传统的单体镜像准备流程拆分为四个独立操作，分别卸载到最优硬件：
- **Image download**：通过 RDMA 下载到 SmartNIC 内存（利用零拷贝高带宽）
- **Image decompression**：在 SmartNIC 硬件解压加速器上执行（比 host zlib 快 7 倍）
- **Image transmission**：将解压后的大块数据通过 PCIe 传输到 host 内存（避免传输大量小文件）
- **Image unpacking**：在 Host CPU 上执行文件解包

关键设计决策：先解压再传输，而非先传输再解压。这样 PCIe 上传输的是少量大块数据而非大量小文件，避免了 PCIe 事务开销。

### 2. Pipeline-based Data-driven Workflow（流水线数据驱动工作流）

- 将镜像按 16MB 块（block）切分，不同块的下载/解压/传输/解包可同时进行
- 采用冗余硬件流水线（redundant pipelines）解决流水线气泡问题：当本地加速器繁忙时，让发送端先解压再传输
- 数据驱动：控制命令嵌入数据块中，各组件根据收到数据块中的控制信息自主执行，减少控制开销

### 3. Distributed Image Download（分布式镜像下载）

- 设计 Image Metadata Index（IMI）记录镜像在集群中的分布位置
- 采用 best-effort 策略从已有镜像的节点分布式下载，无需主动缓存
- 缓解中心化 registry 的带宽瓶颈和 RDMA 连接扩展性问题

---

## 四、实现细节

- **硬件平台**：基于 NVIDIA BlueField-2 SmartNIC（8 个 ARMv8 A72 CPU + 硬件解压加速器 + RDMA）
- **控制路径**：Host 上运行 API agent（兼容 Docker 接口），SmartNIC 上运行 on-NIC controller 管理整个流程
- **数据路径**：基于两侧 RDMA verb 的 RPC 框架，使用 epoll 监控流水线事件
- **线程池**：Host 端使用 Facebook folly 库的线程池进行并发解包
- **IMI 服务**：集成在 registry 服务器上，使用 LevelDB 存储镜像元数据索引
- **RDMA 连接管理**：on-NIC controller 采用 lazy destruction 策略复用连接
- **块大小选择**：经验值 16MB，兼顾加速器启动开销摊销（启动延迟 6.9ms）和流水线并行度
- **内存池配置**：Host 端预分配 3 个 16MB block 的内存池接收解压数据
- **镜像格式**：假设 gzip 格式（占 Docker Hub 96.3% 的镜像），设计正交于压缩格式

---

## 五、实验结果

**实验平台**：2 台服务器（Intel Xeon Gold 6226R, 256GB 内存, BlueField-2 SmartNIC），1 台 registry 服务器（ConnectX-5 100Gbps NIC），Ubuntu 22.04, Linux 5.15.0

**基线**：containerd（Docker 运行时）、iSulad（华为轻量级容器方案）

| 实验 | 关键结果 |
|------|---------|
| E2E 性能（Exp#1） | Poby 比 containerd 平均快 11.5×，比 iSulad 平均快 7.1×；大镜像（2.45GB）上最高 13.2×/8.0× |
| 并发性能（Exp#2） | 8 并发冷启动下 Poby 比 Kraken 快 4.8× |
| 可扩展性（Exp#3） | 10% 分布式下载命中率即超越 Kraken，70% 命中率可比 FaaSNET |
| 延迟分解（Exp#4） | 解压时间降低 76.1%，2 线程解包额外降低 11.0% |
| CPU 使用（Exp#5） | 比 iSulad 减少 87.5% 的 Host CPU 使用；用户态 CPU 从 59.4% 降至 14.1% |
| 内存配置（Exp#6） | 3 个 16MB block 为最优内存池配置 |
| 远程解压（Exp#7） | 网络级解压卸载仅增加 18.0% 延迟，网络带宽开销仅 2.2Gbps |

工作负载覆盖：DeathStarBench 微服务镜像、OpenWhisk FaaS 镜像、FunctionBench 镜像，涵盖小（39.6MB）、中（281.6MB）、大（2.45GB）三种规模。

---

## 六、批判性分析

1. **硬件依赖性过强**：Poby 的核心优势来自 BlueField-2 SmartNIC 的硬件解压加速器。论文没有讨论如果加速器不可用（或被其他任务占用）的降级方案，也没有在其他 SmartNIC 平台上验证通用性。整个设计的可移植性存疑。

2. **实验规模太小**：仅 2 台服务器 + 1 台 registry 的 testbed，分布式下载实验最多 5 个节点。论文声称解决了"集群级"的冷启动问题，但实验规模远不足以验证这一声明。生产环境中的数百上千节点并发场景完全未涉及。

3. **基线比较不够公平**：
   - containerd 和 iSulad 是通用容器运行时，没有 RDMA 或硬件加速器支持，将它们与专门优化的 SmartNIC 方案比较，13.2× 的加速比更多反映的是硬件差异而非设计优越性
   - FaaSNET 由于没有开源，作者自行"模拟简化版本"进行比较，公平性存疑

4. **解包瓶颈未根本解决**：实验数据（Exp#4）显示解包（unpacking）仍占 Poby 总时间的 71.6%，这一瓶颈并未被消除，仅通过 2 线程略微改善了 11%。论文将此归因于存储带宽瓶颈，但未深入探讨更激进的优化方案（如内存文件系统、延迟解包等）。

5. **on-NIC CPU 负载评估不充分**：论文报告 on-NIC CPU 峰值使用率为 16.3%，平均 3.0%，但这是在仅一个容器冷启动的场景下。真实环境中 SmartNIC CPU 可能同时承担网络虚拟化、存储卸载等多种任务，资源竞争情况未被评估。

6. **与 lazy loading 方案的关系含糊**：论文在 Discussion 中声称可以与 on-demand download 方案结合，但没有任何实验验证。考虑到 lazy loading 改变了整个数据流模式，与 Poby 的 block-based pipeline 的兼容性并不显然。

---

## 七、AI Infra / MLSys 视角

1. **ML 容器镜像的冷启动问题更严重**：ML 模型容器镜像通常极大（论文中 ML Model 镜像为 2.45GB，实际生产中更大），Poby 在大镜像上的加速效果（13.2×）对 AI Infra 场景特别有价值。Serverless ML inference 和 spot instance 恢复等场景都面临严重的冷启动问题。

2. **SmartNIC 卸载思路对 AI 系统的启发**：Poby 的核心思路——将数据处理流水线中的不同阶段卸载到最适合的硬件单元——可以迁移到 AI 推理系统中。例如，KV cache 的压缩/解压、模型参数的传输和预处理，都可以考虑类似的 SmartNIC 卸载方案。

3. **数据驱动流水线设计**：Poby 的 block-based redundant pipeline 设计思路（将控制信息嵌入数据流，各阶段根据数据自主执行）值得在分布式训练/推理的通信管道中借鉴，特别是在异构硬件环境下的流水线调度。

4. **可跟进的研究方向**：
   - 将 Poby 的镜像加速方案扩展到 ML model checkpoint 的加载场景（checkpoint 加载是训练容错和弹性伸缩的关键路径）
   - 探索 SmartNIC 在模型推理中 KV cache 管理（压缩存储、RDMA 传输）中的应用
   - 研究 GPU 容器镜像（包含 CUDA 运行时、大模型权重）的专用加速方案

---

## 八、总结

Poby 是首个利用 SmartNIC 硬件加速完整容器镜像准备流程的系统。通过解耦架构将下载/解压/传输/解包分派到 RDMA 网卡、硬件解压加速器和 Host CPU 上，结合 block-based 冗余流水线和分布式镜像下载，在各类容器镜像上实现了平均 7-11 倍的冷启动加速，同时减少 87.5% 的 Host CPU 使用。主要局限在于强依赖特定 SmartNIC 硬件、实验规模较小、解包瓶颈未根本解决。适用于部署了 SmartNIC 的数据中心，特别是对冷启动延迟敏感的 FaaS 和微服务平台。
