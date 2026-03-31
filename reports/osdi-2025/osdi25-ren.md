# Enabling Efficient GPU Communication over Multiple NICs with FuseLink

**作者**：Zhenghang Ren, Yuxuan Li, Zilong Wang, Xinyang Huang, Wenxue Li, Kaiqiang Xu, Xudong Liao, Yijun Sun, Bowen Liu（香港科技大学 iSINGLab）；Han Tian（中国科学技术大学）；Junxue Zhang（香港科技大学）；Mingfei Wang（壁仞科技 MetaX）；Zhizhen Zhong（MIT）；Guyue Liu（北京大学）；Ying Zhang（Meta）；Kai Chen（香港科技大学，通讯作者）
**会议**：OSDI 2025（第 19 届 USENIX 操作系统设计与实现研讨会），2025 年 7 月，波士顿
**DOI**：https://www.usenix.org/conference/osdi25/presentation/ren
**源文件**：[osdi25-ren.pdf](../../papers/osdi-2025/osdi25-ren.pdf)

---

## 一、背景

分布式 ML 任务（大模型训练、推理、推荐系统）的规模不断扩张，GPU 间通信带宽已成为主要瓶颈。GPU 集群通过两种途径提升带宽：

1. **惯性服务器内连接（intra-server）**：NVLink / NVSwitch，提供 Tbps 级带宽；
2. **跨服务器网络（inter-server）**：RDMA NIC（如 400 Gbps InfiniBand）。

由于单块 NIC 的带宽远低于 NVLink，业界通行做法是在每台服务器上安装多块 NIC（通常与 GPU 数量相同，如 8 GPU + 8 NIC），并通过 PCIe 把每块 GPU "静态绑定"到一块 NIC，保证该 GPU 的跨服务器通信能获得最优 PCIe 路径下的全 NIC 带宽。

然而，这种"静态 GPU-NIC 绑定"在 **流量不均衡** 场景下会造成严重浪费：某些 NIC 满载而其他 NIC 闲置，导致整体跨服务器带宽远低于理论峰值。

---

## 二、要解决的问题

### 2.1 动态流量 ML 任务中的 NIC 利用率低

作者对三类典型 ML 任务进行了实测（8× Hopper GPU + 8× 400 Gbps NIC）：

| 任务 | 实测 NIC 平均利用率 | 通信占总耗时比 |
|------|-------------------|--------------|
| 分解式 LLM 推理（prefill-decode 分离） | 13%–53% | 11%–82% |
| Expert-Parallel MoE 训练（Mixtral 8×7B） | 29%–65% | 15%–42% |
| DLRM 推荐模型训练（embedding 传输） | 59%–82% | 28%–55% |

流量不均衡的根本原因：
- **LLM 推理**：请求到达随机，不同 GPU 的通信量差异悬殊；
- **MoE 训练**：稀疏激活导致 expert 间 all-to-all 流量严重不均；
- **DLRM**：不同 GPU 的 embedding 缓存命中率不同，fetch 量差异大。

### 2.2 现有方案的不足

- **NCCL PXN**：允许通过中间 GPU 转发以绕开次优 PCIe 路径，但仍静态绑定到单块 NIC，无法聚合多 NIC 带宽，且不支持接收端 NVLink 路由；
- **MP-RDMA / NetChannel** 等多路径协议：面向主机内存和通用网络路径，未针对 GPU 内存与 PCIe 拓扑优化；
- 所有现有方案均无法 **动态感知 NIC 空闲状态** 并在运行时将流量切换到空闲 NIC。

---

## 三、核心设计

FuseLink 的核心思路：**将高速 intra-server NVLink 连接延伸为 inter-server 网络的一部分**，通过运行时流量路由动态利用服务器内所有 NIC，将"直连 NIC"和"间接 NIC"（需经其他 GPU 中继）统一抽象为可调度的网络资源。

### 3.1 整体架构

```
GPU Workers    Relay Buffers    NICs
  W0 ──NVLink──► GPU1 ──PCIe──► NIC1 ──► Remote
  W0 ──PCIe──────────────────► NIC0 ──► Remote
```

FuseLink 在发送端拦截 NCCL proxy 线程的网络操作，根据 NIC 实时负载动态决定通过哪块 NIC 发送数据，并配置必要的 intra-server 中继路径。

### 3.2 高效 Intra-server 中继（§4.1）

间接 NIC 的访问路径需经过 PCIe root complex 或 NUMA，吞吐远低于直连 NIC。FuseLink 利用 GPU 统一虚拟地址（Unified Addressing）的**内存重映射**机制：

- 将发送 GPU（GPU0）的网络 buffer 虚拟地址重映射到中继 GPU（GPU1）的物理内存；
- GPU0 的线程写入 buffer 时，数据通过 NVLink 直接落到 GPU1；
- NIC 从 GPU1 读取数据时走直连 PCIe 路径，获得全带宽。

四种候选方案（D1–D4）中，D1（直接重映射）在 400 Gbps NIC 测试中达到最高间接 NIC 吞吐，原因是：无额外数据复制、无 CPU 介入、少设备同步，且可将 intra-server 中继延迟与 pipeline 传输重叠。

### 3.3 无干扰中继（§4.2）

多 NIC 传输会占用中继 GPU 的 NVLink 带宽和 GPU 内存，有打断其他 GPU 工作负载的风险。FuseLink 应对策略：

- **仅在空闲期中继**：仅当间接 NIC 对应的 peer GPU 无 inter-server 流量时才启用中继，避免"流量喷洒"式的 NIC 争用；
- **内存上限 + 优先释放**：设置可配置的中继内存上限；当中继 GPU 内存不足时，优先释放中继 buffer 以满足正在运行任务的内存需求；
- **TP 通信隔离**：Tensor Parallel 的 intra-server 通信期间，将相关 NIC 标记为 busy，防止中继流量与其竞争。

### 3.4 NIC 争用缓解（§4.3）

**Worker-aware NIC 监控**：FuseLink 通过检测高优先级 GPU Worker 在 RDMA 连接上的新 completion，判断 NIC 是否空闲（而非读取硬件计数器），以支持细粒度的 per-worker 隔离。

**Load-aware 调度**：接收端将 NIC 负载状态编码进 RDMA credit，发送端综合双侧负载选择最优 NIC：
1. 优先选择直连且空闲的 NIC；
2. 其次选择空闲的间接 NIC（限制 outstanding 请求数以降低争用风险）；
3. 均繁忙时回退到直连 NIC。

一旦检测到 NIC 发生争用，FuseLink 将后续操作切换回优先级更高 worker 的直连 NIC，并通过 credit 通知发送端重新配置路由。

### 3.5 高效调度（§4.4）

FuseLink 做了三处关键权衡以降低控制平面开销：

1. **延迟 NIC 状态标记**：基于 completion 事件而非实时 TX/RX 计数器，在一批操作后统一更新状态；
2. **有界次优传输**：允许在 NIC 路由切换时有一次走次优路径的操作，避免严格同步；
3. **利用 ML 流量的 on-off 特性**：ML 任务的通信间隔较长（计算-通信交替），NIC 状态变化频率低，使路由重配开销可接受。

---

## 四、实现细节

- **代码量**：约 3000 行 C++；
- **集成方式**：作为 NCCL 网络插件，拦截 NCCL proxy 线程的 `connect`、`regMr`、`isend`/`irecv` 等函数调用；ML 应用无需修改代码；
- **FuseLink 调度器**以 daemon 进程运行，ML Worker 进程通过共享内存（shmem）与调度器交互；
- **连接建立**：FuseLink 探测服务器内 PCIe 拓扑，为每对（GPU, NIC）确定最优中继 GPU，预先建立全量 RDMA QP；
- **buffer 注册**：为避免重复注册，FuseLink 同时在中继 GPU 和原始 GPU 上注册网络 buffer，根据当前路由选择对应的 Memory Region；
- **实验平台**：Intel 8480C CPU + 8× Nvidia Hopper GPU（8 Lane NVLink，~200 GB/s）+ 8× ConnectX-7 400 Gbps NIC。

---

## 五、实验结果

### 5.1 微基准：跨服务器带宽

| 方案 | 单 GPU 最高跨服务器带宽 | 较基线提升 |
|------|----------------------|-----------|
| NCCL（PXN 启用） | ~49 GBps（单 NIC） | 1× |
| FuseLink（6 NIC） | **212 GBps** | **4.31×** |

带宽随使用 NIC 数增加而提升，上限由 NVLink 带宽（~200 GB/s）与 NIC 带宽之和决定。

### 5.2 调度开销（Table 3）

| 操作 | 平均延迟 |
|------|---------|
| 提交/拉取网络操作 | 0.8–1.4 µs |
| 查询 NIC 负载 | 0.9–1.6 µs |
| 处理 send | 2.8–3.5 µs |
| 处理 recv | 4.9–5.6 µs |
| 路由切换（含 flush + remap） | 95–193 µs（低频触发） |

### 5.3 端到端：LLM 推理（OPT-30B，disaggregated serving）

| 并发实例数 | NCCL P50 TTFT | FuseLink P50 TTFT | 加速比 |
|-----------|--------------|------------------|------|
| 8（TP=1） | 684.54 ms | 308.48 ms | **2.22×** |
| 4（TP=2） | 174.46 ms | 122.61 ms | **1.42×** |
| 2（TP=4） | 98.09 ms | 81.97 ms | **1.20×** |

TTFT 改善范围：**1.04–2.73×**，实例数越多（流量越不均衡）效果越显著。

### 5.4 端到端：MoE 训练（Mixtral 8×22B，EP=8）

训练吞吐提升约 **1.3×**；注意后期迭代由于 gate layer 负载均衡效果逐渐显现，提升幅度有所下降。

### 5.5 端到端：DLRM 训练（DeepFM，Avazu）

- 32 GPU workers + 专用 embedding server；
- cache size 越小（cache miss 越多）效果越明显，平均训练迭代时间降低 **~1.2×**。

---

## 六、批判性分析

**1. 实验规模有限，工程挑战被低估**

所有实验在 1–2 台服务器间进行，最多涉及 32 个 GPU workers。现实生产集群动辄数百至数千 GPU，FuseLink 的 credit 机制和 NIC 监控调度在大规模、高并发连接下的扩展性未被验证。论文虽提及"调度开销由 NIC 数量和并发连接数决定，受硬件限制"，但并未在大规模场景下测量控制平面开销。

**2. MoE 加速效果前后期落差被轻描淡写**

Figure 12 明确显示后期迭代 FuseLink 的优势大幅收窄——这恰恰说明 FuseLink 的收益高度依赖于流量不均衡程度。论文将此解释为"gate layer 自然平衡"，但未讨论这对实际收益持续性的影响，且在摘要中仍以"1.3×"的峰值数字作为宣传。

**3. 中继内存 OOM 问题的解决方案不完整**

作者承认无法精确估计中继 GPU 的内存占用，只提供了"上限 + 优先释放"的 best-effort 方案。在极端场景下（多个 Worker 同时大量中继），OOM 风险仍然存在，且论文未给出此类场景下系统行为的实测数据。

**4. 对集体通信（AllReduce 等）的适用性被回避**

FuseLink 对 point-to-point 通信（MoE、disaggregated serving、DLRM）效果好，但标准数据并行的 ring-allreduce 流量是均衡的，无法直接受益。论文在 Discussion 节提到"需要调整 worker 布局才能在集体通信中使用"，但未给出具体方案或实验，实际上回避了这一重要场景。

**5. 基线选择争议**

基线仅与 NCCL+PXN 比较，未与 MP-RDMA[38] 或 ECMP 等多路径方案对比。这些方案的适用场景不同，但作者未充分论证为何这些方案不能作为公平基线。

---

## 七、AI Infra / MLSys 视角

**核心 insight 的迁移价值**

FuseLink 的最关键 insight 是：**intra-server 高速互连（NVLink）可以作为 inter-server 网络的"延伸基础设施"**，通过内存重映射将 GPU 变成透明的流量中继节点，而无需修改上层 ML 框架。这一思路对以下 AI Infra 方向有直接启发：

1. **异构集群通信优化**：在 NVLink 带宽持续增长（Blackwell NVLink 5.0 达 1800 GB/s）而 NIC 带宽增速相对滞后的背景下，NVLink-NIC 协同聚合是一条可行的低成本扩容路径，无需升级网络硬件。

2. **Disaggregated LLM 推理**：prefill-decode 分离是当前主流推理优化方向，其 KV cache 传输呈现强烈的突发性和不均衡性——正是 FuseLink 最对口的场景。未来可探索与 PD 分离框架（如 Mooncake、DistServe）的深度集成。

3. **MoE 通信优化**：随着 MoE 模型（DeepSeek-V3、Mixtral）在生产中大规模部署，all-to-all 的流量不均衡是持续存在的工程问题。FuseLink 的动态 NIC 调度机制可与 expert routing 策略联动（例如感知当前 NIC 负载来辅助 expert placement 或 token 调度）。

**值得跟进的 future work 方向**

- **与 KV cache 迁移协同设计**：在 disaggregated serving 中，KV cache 的迁移调度（选择哪个 prefill 实例向哪个 decode 实例发送）可以与 FuseLink 的 NIC 调度联动，实现端到端的流量感知推理调度；
- **跨 Rail 集群的多路径扩展**：当前 FuseLink 聚焦于 intra-server 多 NIC，在 rail-optimized（如 NVL72）拓扑下跨 rail 流量需经 spine 交换机，能否将 FuseLink 思路延伸到 intra-pod NVLink 聚合值得研究；
- **AMD / 国产 GPU 适配**：FuseLink 依赖 Nvidia 统一虚拟地址和 NVLink，在 AMD ROCm（Infinity Fabric）或国产加速卡（MetaX、摩尔线程）平台上的等价实现路径尚待探索，具有较大工程价值。

---

## 八、总结

FuseLink 针对分布式 ML 任务中静态 GPU-NIC 绑定导致 NIC 利用率低下的问题，提出通过内存重映射将 NVLink 融入 inter-server 数据路径，配合动态 NIC 负载感知调度，实现多 NIC 带宽聚合。系统以 NCCL 插件形式集成，无需修改 ML 应用代码。在 disaggregated LLM 推理、MoE 训练、DLRM 训练三类典型动态流量场景下，分别实现 1.04–2.73×、1.3×、1.2× 的端到端加速。主要局限在于：实验规模较小（≤2 台服务器），对集体通信场景的适用性有限，中继内存 OOM 风险未完全解决，且收益高度依赖于流量不均衡程度。
