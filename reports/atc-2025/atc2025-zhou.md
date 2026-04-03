# Accelerating Model Training on Ascend Chips: An Industrial System for Profiling, Analysis and Optimization

**作者**：Yuhang Zhou, Zibo Wang, Zhibin Wang, Ruyi Zhang, Chen Tian, Xiaoliang Wang, Wanchun Dou, Guihai Chen (Nanjing University); Bingqiang Wang, Yonghong Tian, Yan Zhang, Hui Wang (Peng Cheng Laboratory); Fuchun Wei, Boquan Sun, Jingyi Zhang, Bin She, Teng Su, Yifan Yao, Chunsheng Li, Ziyang Zhang, Yaoyuan Wang (Huawei); Bin Zhou (Shandong University); Guyue Liu (Peking University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/zhou
**源文件**：[[atc2025-zhou.pdf]]

---

## 一、背景

大规模深度学习模型训练极其耗费资源和时间（如 GPT-3 100B 参数在 3072 张 A100 上训练 84 天，BLOOM-176B 在 384 张 A100 上训练约 3.5 个月）。训练优化涉及多种角色：开发者需精确定位瓶颈并设计针对性优化，部署者需在不断演变的模型和硬件上高效部署，维护者需监控长期训练中的随机性能波动。

华为 Ascend NPU 作为替代 NVIDIA GPU 的国产 AI 加速芯片，虽然训练范式与 GPU 类似（HCCL 对应 NCCL，CANN 对应 CUDA，HCCS 对应 NVLink），但存在特有的架构差异：AICore 负责矩阵/向量运算（类似 CUDA Core + Tensor Core），AICPU 处理 AICore 不支持的非矩阵计算任务，且存在私有数据格式和 HCCS 字节对齐等特有约束。

---

## 二、要解决的问题

现有训练性能优化方案面临三大不足：

1. **Profiling 开销过高**：捕捉长期训练中的瞬态性能波动需要持续监控，但 PyTorch Profiler 等主流工具开销巨大（8B Llama-3 在 8 NPU 上单步 profiling 开销为原始成本的 1.77×），且需手动调整 profiling 粒度，频繁中断训练。
2. **瓶颈分析碎片化**：现有分析工具只针对特定瓶颈类型（PRESTO 仅分析 I/O，R-Pingmesh 仅分析 RDMA），即使 NVIDIA Nsight System 的 Expert Analysis 也仅覆盖 6 条规则。孤立分析容易遗漏瓶颈间的相互依赖关系（如通信瓶颈可能源于不均衡的计算负载）。
3. **优化选择缺乏指导**：DayDream、dPRO 等工具仅适用于数据并行场景，大多数情况下用户在不知道瓶颈根因的前提下选择优化策略，导致效果不佳。

---

## 三、洞察与设计

**关键洞察**：训练流水线天然呈层次化结构——框架将程序转为计算图，由 HCCL 组织并行策略，再通过 CANN 编译为硬件可执行算子。不同类型的瓶颈发生在对应的层次组件中（host/device/network），且算子间的并行性和算子内的实现效率是两个可分离的分析维度。因此，可以构建层次化的分析框架，先分析算子间并行性（inter-operator），再深入算子内实现（intra-operator），系统性地覆盖所有瓶颈类型。

基于此洞察，论文提出 **Hermes** 系统，包含三个核心模块：

### 1. Coarse-to-Fine Profiling（粗到细 Profiling）

- **轻量监控器**：在整个训练过程中仅收集少量关键指标（每步执行时间、吞吐量、MFU、通信带宽），用于检测性能波动。通过集群分析两步定位问题：(i) 将当前步与历史步对比识别异常步；(ii) 比较同一步内各设备的执行时间定位问题设备。
- **细粒度 Profiler**：仅对识别出的问题步/设备进行详细 profiling，捕获每个算子的性能数据。
- **动态 Profiling 机制**：通过共享内存传递 profiling 配置，无需中断训练即可动态启动/停止 profiling。

### 2. 层次化瓶颈分析框架

**Inter-operator 分析**：
- 将每步时间分解为计算时间、非重叠通信时间和 host 时间
- 当 overlap 不足时识别并行瓶颈
- 当 overlap 充分时通过 critical path 分析找出瓶颈算子

**Intra-operator 分析**：
- **I/O 瓶颈**：基于队列的分析（数据队列/host 队列/device 队列），定位数据读取、处理还是传输环节
- **CPU 瓶颈**：检查算子编译（JIT 重编译）、算子调度、同步操作、GC、环境配置等
- **计算瓶颈**：基于 Roofline 模型分类为 compute bound、memory bound 或 underutilization，针对性处理（如消除 AICPU 算子、替换亲和性更好的 API、禁止私有格式）
- **通信瓶颈**：将 AllReduce 执行分解为同步和传输，分别分析等待时间浪费比率和带宽利用率（带宽争用、RDMA 重传、小包、字节对齐、网络配置）

### 3. 瓶颈原因-优化匹配

基于 3 年 135 个典型案例总结的映射表（Table 4），将不同瓶颈原因匹配到可行的优化策略。开发了自动化工具 mstt advisor，输入 profiling 数据后自动生成 HTML 分析报告。

---

## 四、实现细节

- **Profiling 实现**：轻量监控器通过 callback 在每步训练前后收集时间戳；细粒度 profiler 通过 CANN 的 msprof 接口采集算子级数据；两者通过共享内存中的配置文件协调，支持动态切换。profiling 数据通过解析生成 timeline（类似 Chrome Trace Event 格式），分为 host/device/network 三个维度。
- **Roofline 分析**：为每个算子计算算术强度（FLOPs/Byte），与硬件峰值性能和带宽画出 roofline 线，设置 bandwidth utilization 和 arithmetic utilization 两个阈值来判断瓶颈类型。
- **同步分析**：对 AllReduce 等集合通信算子，计算等待时间浪费比率 $R_{wait} = 1 - T_{avg} / T_{max}$，超过阈值则判定为同步瓶颈。
- **自适应梯度融合**：建模为优化问题——最大化带宽利用、最小化尾延迟。收集每个梯度大小、算子依赖关系和计算时间，使用贪心前向搜索算法找到融合方案。
- **mstt advisor**：内置规则引擎，覆盖 Table 4 中所有瓶颈类型，自动检测并输出优化建议。
- **支持框架**：PyTorch 和 MindSpore。

---

## 五、实验结果

### 经典瓶颈案例

| 案例 | 瓶颈类型 | 优化措施 | 加速比 |
|------|----------|----------|--------|
| ResNet50 单卡 | I/O（数据处理慢，num_worker=1） | 增加并发线程到 12 | 5.34× |
| GPT-3 单节点 8 NPU | CPU（Prometheus 误部署占 4000% CPU） | 终止异常进程 | 1.19×（波动步从 128 降到 4） |
| VGG16 8 卡 | 通信（HCCS 小包，带宽利用率 53%） | 自适应梯度融合 | 1.35× |

### 100B PanGu-α 迭代优化（128 NPU）

| 优化阶段 | 步时间 | 总训练时间 | 吞吐量 | 加速比 |
|----------|--------|-----------|--------|--------|
| Baseline | 98.01s | 2856h | 4839 tokens/s | 1× |
| +Operator 优化 | 48.16s | 1392h | 9930 tokens/s | 2.05× |
| +Auto hybrid parallelism | 42.21s | 1128h | 12264 tokens/s | 2.53× |
| +Multi-shard parallelism | 31.94s | 984h | 14023 tokens/s | 2.90× |
| +Gradient fusion | 26.43s | 936h | 14436 tokens/s | 3.05× |

### MobileNetV1-SSD 部署优化（GPU→NPU 迁移）

从 GPU 直接迁移后性能仅为 GPU 的 43%，经过禁用 JIT 编译、消除同步操作、替换亲和性 API、解绑 CPU 进程等优化后，达到 GPU 性能的 90%，整体加速 1.91×。

### MoE 大规模训练波动（9000+ NPU）

25% 的性能波动案例归因于 Python GC。通过提高 GC 阈值 + 周期性手动 gc.collect()，训练加速 1.19×。

### 模型部署综合结果（Table 6）

覆盖 ResNet50、VGG16、MobileNetV1-SSD、Bert-Large、PanGu-α 1.3B、GPT3-13B、DeepFM、DLRM 等模型，加速比从 1.08× 到 5.34×。

---

## 六、批判性分析

1. **加速比数字具有误导性**：5.34× 的 ResNet50 加速来自将 num_worker 从 1 调到 12，GPT-3 的 1.19× 来自终止误部署的 Prometheus 进程。这些本质上是配置错误修复，不是系统性优化。将配置修复的收益归功于 Hermes 系统夸大了系统的实际价值。

2. **硬件通用性存疑**：论文声称"硬件无关的瓶颈"优化可迁移到其他平台，但整个系统围绕 Ascend 特有的 CANN/msprof 接口构建，AICPU 算子替换、HCCS 字节对齐、私有格式禁止等优化完全不可迁移。层次化分析框架的概念虽通用，但实现高度耦合于 Ascend 生态。

3. **缺乏与 NVIDIA 生态的公平对比**：论文将 Hermes 与 Nsight System 的 Expert Analysis（仅 6 条规则）对比来突显优势，但没有对比 NVIDIA 完整的性能分析工具链（Nsight Compute + Nsight Systems + 第三方工具）。Hermes 的 135 条规则 vs Nsight 的 6 条规则是不公平的比较维度。

4. **自动化程度有限**：mstt advisor 本质上是规则引擎，论文也承认在复杂场景（如 MoE AlltoAll 不均衡、外部环境导致的 CPU 瓶颈）下仍需人工介入。论文在 Discussion 中提到计划引入 LLM-based agents，但目前系统高度依赖专家经验编码为规则。

5. **实验规模和多样性**：PanGu-α 实验使用 128 NPU，MoE 案例用了 9000+ NPU，但详细的迭代优化流程仅展示了 PanGu-α 一个案例。其他模型的优化过程被压缩为 Table 6 的一行数字，无法验证方法的普适性。

6. **时间跨度带来的问题**：系统经验积累跨越 2022-2024 三年，期间 Ascend 硬件和软件栈经历多次迭代。早期案例的优化经验是否适用于当前硬件版本并不清楚。

---

## 七、AI Infra / MLSys 视角

1. **层次化瓶颈分析框架的通用价值**：将训练瓶颈分为 inter-operator（并行效率）和 intra-operator（执行效率）两层分析的思路，对任何加速器平台上的性能调优都有借鉴意义。特别是先判断 overlap 是否充分，再决定是优化并行策略还是单算子性能的决策树，可以直接应用于 GPU 训练优化。

2. **CPU 瓶颈被严重低估的启示**：37% 的案例涉及 CPU 瓶颈（算子编译、调度、GC、进程争用等），这个比例远超直觉。当前 AI Infra 研究高度关注 GPU/NPU 端的计算和通信优化，但 host 端的 CPU 调度开销在实际生产中可能是更常见的瓶颈来源。这对 vLLM、SGLang 等推理系统的性能调优同样有参考价值。

3. **计算-通信 overlap 的负面效应**：论文指出 overlap 可能因 HBM 带宽争用导致 20%-40% 的性能下降。这与当前 AI Infra 社区普遍追求最大化 overlap 的趋势形成对比，提示需要更精细的 overlap 调度策略（如基于 HBM 带宽的优先级控制）。Flux、Centauri 等工作已在探索这个方向。

4. **自适应梯度融合**：论文提出的基于贪心搜索的梯度融合策略，考虑了带宽利用和尾延迟两个目标，比 PyTorch/Horovod 的固定 bucket size 更灵活。这个思路可以推广到推理场景中的 KV cache 传输、tensor parallel 通信等场景。

5. **可跟进的研究方向**：
   - 基于 LLM 的自动瓶颈诊断和优化推荐（论文 Discussion 中提到但未实现）
   - 跨硬件平台的统一瓶颈分析框架（目前 Ascend 和 GPU 的工具链完全独立）
   - 大规模训练中性能波动的实时在线诊断（当前轻量监控 + 按需 profiling 的方案仍有延迟）

---

## 八、总结

Hermes 是一个面向华为 Ascend NPU 的端到端训练性能优化系统，基于 3 年 135 个实际案例的经验，提供从粗到细的 profiling、层次化瓶颈分析和原因-优化自动匹配三个核心能力。其层次化分析框架（inter-operator 并行 + intra-operator 实现）的设计思路具有通用价值，CPU 瓶颈占比高达 37% 的发现对业界有警示意义。主要局限在于系统深度耦合 Ascend 生态、自动化程度依赖规则引擎、部分"加速"实为配置错误修复。
