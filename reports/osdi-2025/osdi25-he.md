# WaferLLM: Large Language Model Inference at Wafer Scale

## 论文基本信息

| 字段 | 内容 |
|------|------|
| 标题 | WaferLLM: Large Language Model Inference at Wafer Scale |
| 作者 | Congjie He, Yeqi Huang, Pei Mu（爱丁堡大学）；Ziming Miao, Jilong Xue, Lingxiao Ma, Fan Yang（微软研究院）；Luo Mai（爱丁堡大学） |
| 会议 | OSDI 2025 |
| 链接 | https://www.usenix.org/conference/osdi25/presentation/he |

## 研究背景与动机

LLM 推理有两个关键阶段：
1. **Prefill 阶段**：处理输入 tokens，以 GEMM 为主
2. **Decode 阶段**：逐 token 生成，以 GEMV 为主

**Decode 阶段的内存带宽瓶颈**：每次生成需要将整个模型加载到片上内存，但 LLM 权重可达 10-1000GB，而 GPU 片上 SRAM 仅约 100MB。

**Wafer-scale 加速器的优势**：
- 面积是典型 GPU die 的 100×（Cerebras WSE-2：850,000 核心，40GB 片上内存）
- 内存带宽是 GPU 的 7,000×（22PB/s）
- 晶圆级封装提供更低延迟和更高能效的 die-to-die 互联

**现状问题**：
- 现有 LLM 系统（vLLM、SGLang 等）针对共享内存架构（GPU/TPU）优化
- Wafer-scale 加速器采用 mesh NoC 互联的分布式片上内存架构，与共享内存架构有根本性差异
- 直接应用现有设计到晶圆级设备导致极差性能

## 核心问题

如何在晶圆级加速器上高效运行 LLM 推理，需要考虑：
1. **P**（大规模并行）：百万级核心并行计算
2. **L**（高度非均匀内存访问延迟）：核间数据访问延迟差异高达 1000×
3. **M**（受限的每核本地内存）：每个核心仅有几十 KB 到几 MB
4. **R**（受限的硬件路由）：NoC 路由硬件受限（如 Cerebras WSE-2 每核仅支持 <25 条路由路径）

## 主要贡献

1. **PLMR 模型**：捕捉晶圆级加速器的关键硬件特性（P/L/M/R），为系统设计提供理论指导
2. **Wafer-scale LLM 并行策略**：prefill 阶段的细粒度分片、decode 阶段的细粒度复制
3. **MeshGEMM**：首个为晶圆级设备设计的可扩展 GEMM 算法，利用 cyclic shifting + interleaving 满足 PLMR 约束
4. **MeshGEMV**：首个为晶圆级设备设计的可扩展 GEMV 算法，利用 K-tree allreduce 聚合结果
5. **Shift-based KV cache 管理**：相比 PagedAttention 的 concat 方式，支持 360-385× 更多 tokens
6. 开源：https://github.com/MeshInfra/WaferLLM

## 研究方法与设计

### PLMR 模型详解

**P（大规模并行）**：
- 晶圆级加速器可容纳百万级并行核心
- 需要在极细粒度上分片计算和调度

**L（高度非均匀内存访问延迟）**：
- 在 N×N 的 mesh 中，两核间最大跳数为 N_w+N_h
- 延迟公式：α(N_w+N_h)+βr（α=每跳传输延迟，β=每路由延迟）
- 百万核 mesh 最坏延迟是本地的 1000×

**M（受限的每核本地内存）**：
- 每核 SRAM 仅几十 KB 到几 MB
- 计算数据必须细粒度分片以适应每核约束

**R（受限的路由资源）**：
- 每核仅能识别 5 位地址码，支持 <25 条不同路由路径
- 长距离通信需要预先规划路由

### Prefill 并行策略

**问题**：如何利用百万级核心进行矩阵运算，同时满足 L/M/R 约束

**方案**：
1. 在两个维度上细粒度分片输入激活和权重
2. **Transpose-free 并行策略**：避免矩阵转置（晶圆级 NoC 上成本极高）
3. **Cyclic Shifting**：确保算法正确性同时维持有界的本地内存使用
4. **Interleaving**：最小化 mesh NoC 上的通信延迟

### Decode 并行策略

**问题**：decode 阶段张量维度不足，难以有效分片

**方案**：
- 细粒度复制：复制部分计算到多个核心，利用局部性减少通信

### MeshGEMM 算法

针对分布式 GEMM 的关键优化：
1. **Cyclic shifting**：保证正确性的同时有界使用本地内存（M 约束）
2. **Interleaving**：最小化长距离通信延迟（L 约束），有效利用路由资源（R 约束）

**与 SUMMA/Cannon 的比较**：
- SUMMA pipeline broadcast：通信开销随核心数线性增长
- Cannon head-to-tail 传输：可扩展性差
- MeshGEMM interleaving：通信开销有界，保持 >70% 计算效率

### MeshGEMV 算法

**问题**：分布式 GEMV 的 allreduce 聚合结果需要高效的集合通信

**K-tree Allreduce 算法**：
- 将 allreduce 操作组织为 K 叉树结构
- 确保路由资源使用满足硬件限制（R 约束）
- 减少通信延迟（L 约束）

### Shift-based KV Cache 管理

**问题**：PagedAttention 的 concat 方式在晶圆级设备上导致不均衡的核心利用率

**方案**：
- 每个 KV cache 条目按 round-robin 分布到各核心
- 写入新 token 时执行 KV cache shift
- 读取时通过广播获取

**效果**：支持 LLaMA3-8B 360× 和 LLaMA2-13B 385× 更多 tokens（vs concat）

## 关键实现细节

- 约 7000 行 CSL（类 C 编程语言）
- 约 2000 行 Python
- 在 Cerebras WSE-2 引擎上评估
- 支持 LLaMA3-8B、LLaMA2-13B、CodeLLaMA-34B（部分层）、QWen2-72B（部分层）

## 实验结果与分析

### End-to-End 吞吐量（TPR）

**与 SGLang (A100 GPU) 比较**：
- LLaMA3-8B：30-40× 提升
- LLaMA2-13B：10-20× 提升
- **随着模型增大和输出变长，优势更明显**（最长输出场景 48×）

### Prefill 吞吐量

**与 T10（分布式片上内存 SOTA）和 Ladder（共享内存 SOTA）比较**：
- WaferLLM 比 T10 快 **160×**（平均），最快 178×
- WaferLLM 比 Ladder 快 **270-450×**

**关键**：T10 和 Ladder 无法随核心数扩展，吞吐量甚至随核心增加而下降

### Decode 吞吐量

- WaferLLM 比 T10 快 **5.7×**（平均），最快 6.5×
- WaferLLM 比 Ladder 快 **200-500×**

**分析**：prefill 的优势（160×）大于 decode（5.7×），因为 GEMM 的通信模式更规则

### MeshGEMM 微基准

- 比 SUMMA 快 2-3×
- 比 Cannon 快 2-3×
- 在 720×720 核心规模下保持 >70% 计算效率（vs SUMMA/Cannon <50%）

### MeshGEMV 微基准

- 比 Cerebras 优化的 GEMV 快 4-8×
- 比单 A100 GPU 快 **606×**
- 能效比 A100 高 **7.5-16×**

### KV Cache 管理

- Shift-based 比 concat-based 支持 360-385× 更多 tokens
- 比 PagedAttention KVcache 可扩展性高 **400×**

### 能效

- Prefill：相比 A100 GPU 高 2.5×
- Decode：相比 A100 GPU 高 2-7×（取决于模型和 batch size）

## 潜在问题与局限性

1. **GPU 比较的公平性**：与 SGLang (A100) 的比较中，A100 是单卡还是 8 卡集群未明确说明；如果是最优多 GPU 配置，10-20× 的提升可能需要重新评估
2. **跨节点通信**：10 亿+ 参数模型需要跨 WSE 芯片通信，当前系统如何处理尚不清楚
3. **WSE-2 的实际可用性**：Cerebras WSE-2 的商业可用性和成本是实际部署的关键障碍
4. **当前软件的局限性**：论文承认 MeshGEMV 未达到理论 7,000× 提升（仅 606×），原因是 WSE-2 是第二代芯片，存在未充分利用的边缘核心和长距离通信开销
5. **与 H100/H200 的比较**：未与最新 GPU 架构比较，与 A100 的比较可能不够反映当前最优实践
6. **MoE 支持**：当前未处理 MoE 中 all-to-all 通信，论文仅提及可用 NoC 多播操作简化实现

## 未来工作方向

1. 跨 WSE 芯片的 LLM 推理
2. MoE 稀疏注意力优化
3. 故障处理和可靠性

## 个人评注

**优点**：
- PLMR 模型是一个非常有价值的分析工具，四个维度（P/L/M/R）清晰捕捉了晶圆级加速器的关键特性
- MeshGEMM 和 MeshGEMV 的算法设计深入考虑了硬件约束，cyclic shifting 和 interleaving 的组合设计巧妙
- K-tree allreduce 是一个简洁优雅的算法，有效解决了路由资源受限问题
- 对 T10 和 Ladder 的失败分析（未能随核心数扩展）非常有洞察力

**潜在争议**：
- **A100 比较的公平性**：论文的 SGLang baseline 是单 8 GPU 配置（2×8），而最佳性能来自单 8 GPU 节点。考虑到 NVLink 的高带宽，vLLM/SGLang 在最优配置下的实际性能可能高于论文的 baseline，导致 WaferLLM 的实际优势被高估
- **理论 vs 实际**：7,000× 的理论带宽优势 vs 606× 的实际 GEMV 加速，说明 wafer-scale 软件栈远未成熟
- **"首个"wafer-scale LLM 推理系统**：Cerebras 本身提供了商业化的晶圆级 LLM 推理方案（Pythia 模型），论文未与 Cerebras 的现有方案比较
- **能效声称**：虽然单芯片能效比 A100 高，但 WSE-2 的制造成本和良品率问题使总拥有成本比较更加复杂

总体而言，WaferLLM 是一项具有前瞻性的系统工作，为未来晶圆级 AI 计算奠定了重要的算法和系统基础。
