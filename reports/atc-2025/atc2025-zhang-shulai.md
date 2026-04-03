# Efficient Performance-Aware GPU Sharing with Compatibility and Isolation through Kernel Space Interception

**作者**：Shulai Zhang, Ao Xu, Quan Chen, Han Zhao, Weihao Cui (Shanghai Jiao Tong University); Zhen Wang, Yan Li, Limin Xiao (Lenovo); Minyi Guo (Shanghai Jiao Tong University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/zhang-shulai
**源文件**：[[atc2025-zhang-shulai.pdf]]

---

## 一、背景

GPU 被广泛用于 AI 推理/训练、科学计算、视频渲染等多种工作负载。许多任务是轻量级的，只需要 GPU 的一小部分资源即可达到性能目标，因此在同一 GPU 上共置（co-locate）多个任务可以大幅提升资源效率。Amazon 已经开始使用分数 GPU 来交付视频内容和 AI 推理服务。

GPU 共享的核心需求有三个：**兼容性**（支持不同运行时，如 CUDA、Vulkan、OpenGL）、**隔离性**（性能隔离和故障隔离，一个应用的崩溃不影响其他应用）、**高利用率**（减少 GPU 碎片，最大化资源使用）。

---

## 二、要解决的问题

现有 GPU 共享方案存在以下不足：

1. **兼容性差**：API-remoting 方案（如 TGS、Orion、GaiaGPU）在用户态拦截 API 调用，需要为每种运行时和版本适配大量接口。CUDA 已发布 70+ 版本，维护成本极高。MPS 和 MIG 也仅限 CUDA 应用，不支持 Vulkan/OpenGL 等图形运行时。

2. **隔离性弱**：API-remoting 无法拦截隐式 GPU 操作（如 CUDA context 创建时隐式分配 ~400MB 显存），导致恶意进程可以耗尽显存使其他应用 OOM。MPS 将多进程 kernel 合并到同一 GPU context 中，一个进程的越界内存访问会导致所有共置进程全部崩溃。

3. **性能保障不足**：API-remoting 和 MPS 的时间/空间共享存在共享资源争用（如全局内存带宽），导致实际吞吐量低于目标。MIG 虽能隔离但资源粒度太粗，造成大量 GPU 碎片和低利用率。

4. **缺乏高效编排**：现有方案要么只做时间共享要么只做空间共享，无法在两个维度上联合优化，导致 GPU 碎片严重。

---

## 三、洞察与设计

**关键洞察**：

- **Insight-1**：在 GPU 软件栈中，所有运行时（CUDA、Vulkan 等）最终都通过 UMD 将命令写入 command buffer，再由 KMD 通过系统调用通知 GPU 执行。在内核态拦截 command buffer 和系统调用，可以绕过对不同用户态运行时 API 的适配需求，天然获得跨运行时兼容性；同时每个进程在独立的 GPU context 中运行，context 之间地址空间隔离，内核态可精确控制所有内存操作，实现故障隔离。
- **Insight-2**：单独的时间共享或空间共享都会产生大量 GPU 碎片（时间共享时 SM 未充分利用，空间共享时时间片未充分利用），将两个维度联合调整可以找到更优的资源配置来满足性能目标，同时显著减少碎片。

基于这两个洞察，KRYPTON 的整体设计包含四个组件：

1. **离线 Profiler**：在不同 IGPU（Isolated GPU）配置下测量应用的吞吐量，建立性能模型。IGPU 由硬件单元（MIG 实例）、时间片配额和显存配额三个维度定义。吞吐量与时间片配额成正比：$Thr(s,t,m) = Thr(s,100\%,m) \times t$。

2. **内核态拦截模块**：不解析具体命令内容，而是通过拦截 command buffer 的访问权限来实现时间共享；同时拦截内存相关 ioctl 系统调用实现显存管理。

3. **反馈控制器**：利用 GPU 硬件的实时利用率信号（NVML/DCGM），自适应调整各应用的 CPU token 分配，补偿实际 GPU 利用率与目标之间的偏差。

4. **时空编排器**：两阶段 bin-packing 算法，先在时间维度合并相同空间配置的 IGPU，再跨空间配置迁移工作负载以减少碎片，最后将 MIG 实例装箱到物理 GPU 上。

---

## 四、实现细节

**内核态 Command Buffer 拦截**：
- 通过拦截 `ioctl` 系统调用识别 command buffer 地址（在 GPU context 创建时分配）
- 使用 `do_mprotect_pkey`（内核内部的 mprotect 实现）将 command buffer 对应的内存页设为只读来"锁定"进程
- 进程试图写入被锁定的 command buffer 时触发 segfault，由预注册的用户态 signal handler 捕获，阻塞等待内核态调度器授权后恢复执行
- 只拦截 command buffer 写入，不影响进程的其他 CPU 计算

**显存管理**：内核态中央内存分配器拦截所有设备内存相关的 ioctl 请求（包括 GPU context 创建时的隐式分配），精确记录和控制每个工作负载的显存用量。

**自适应 Token 控制**：
- CPU token 长度默认 100ms，同一时刻只有一个应用持有 token
- 调度器选择相对 GPU 利用率最低的应用（`util/quota` 最小）激活
- 通过移动平均平滑利用率数据，避免因轻负载应用反复被选中

**时空编排算法**（复杂度 $O(MP)$）：
1. 初始化：每个工作负载分配最小可行 MIG 实例
2. 时间维度合并：相同空间配置的 IGPU 融合以减少空闲时间片
3. 碎片缩减：将小实例上的工作负载迁移到大实例以消除时间碎片
4. 实例装箱：将 MIG 实例分配到物理 GPU 上

**实现规模**：内核态拦截和反馈控制器 3K 行 C 代码（Linux 可加载内核模块），时空编排器 1K 行 Python 代码。不修改 GPU 驱动或应用代码。

---

## 五、实验结果

**实验平台**：Intel Xeon Silver 4216 64-core CPU，Nvidia A100 40GB + 2× RTX 4090，Ubuntu 20.04，CUDA 12.1，Vulkan 1.3，PyTorch 2.2.1。

**工作负载**：ResNet50、MobileNet_V2、BERT-Large、Transformer-XL 的推理和训练，以及 3 个 Vulkan 渲染应用。

| 指标 | 结果 |
|------|------|
| GPU 数量减少（vs Temporal） | 32.1% |
| GPU 数量减少（vs Best-fit-MIG） | 23.1% |
| GPU 数量减少（vs GPUlet-MIG） | 20.5% |
| 平均性能相对误差 | 3.3% |
| 自适应控制性能相对误差 | ≤ 0.9% |
| 无反馈控制性能相对误差 | 5.3% |
| Vulkan 应用性能相对误差 | < 3.4% |
| 分布式训练性能相对误差 | 1.8% |
| QoS 违反率（平均） | 1.23% |
| 内核模块内存开销 | 4.8 MB CPU memory |

**弹性共享**：当新任务到达或离开时，KRYPTON 可以即时调整资源分配，利用率突发仅持续数秒后即稳定。固定时间片分配下 Transformer-XL 推理任务与不同应用共置时吞吐量相对误差仅 1.3%。

**延迟 QoS**：不同 token 长度下平均 QoS 违反率 1.23%。小 batch 偏好长 token（减少切换开销），大 batch 偏好短 token（减少等待时间）。

---

## 六、批判性分析

1. **离线 Profiling 假设过于理想**：论文假设吞吐量与时间片配额严格成正比（$Thr(s,t,m) = Thr(s,100\%,m) \times t$），但这只在"强隔离"条件下成立。实际上 MIG 实例之间仍共享 L2 cache、内存带宽等资源，线性模型在资源争用场景下的准确性未充分验证。论文仅展示了固定 workload 组合的结果，缺乏对 profiling 精度的系统性分析。

2. **工作负载多样性不足**：评估仅涵盖 4 个 AI 模型（且都是较老的模型——ResNet50、MobileNet_V2、BERT-Large、Transformer-XL）和 3 个简单 Vulkan demo。缺少 LLM 推理（如 vLLM serving with continuous batching）、扩散模型、GNN 等当前主流 AI 工作负载的评估。这些工作负载的 GPU 使用模式（动态 batch、变长序列、不规则计算图）可能严重影响反馈控制器的效果。

3. **MIG 依赖限制了适用范围**：KRYPTON 的空间共享完全依赖 MIG，而 MIG 仅在 A100/A30/H100 等少数高端 GPU 上可用，且空间配置有限（A100 最多 7 个实例，仅几种预定义分割方式）。论文标题宣称通用的"GPU Sharing"，但实际上空间维度的灵活性受到严重限制。RTX 4090 实验只评估了时间共享，没有时空联合编排。

4. **不支持动态空间重配置**：论文在 Discussion 中承认 KRYPTON 不支持 MIG 的实时重配置，这在动态负载场景（如 LLM serving 的请求量波动）中是重大限制。编排结果一旦确定，工作负载的空间配置就是固定的。

5. **安全性论证薄弱**：论文声称内核态拦截"等价于其他 LKM 方案的安全保证"，且"未报告安全风险"。但 KRYPTON 通过 kallsyms 查找未导出的内核函数并调用，这本身就是一种脆弱的实现方式，可能在内核版本升级时 break，且绕过了内核 API 稳定性保证。

6. **100ms Token 粒度的影响**：默认 100ms 的 token 长度意味着延迟敏感型应用（如实时推理）可能面临最高 100ms 的额外等待。虽然论文评估了不同 token 长度，但 QoS 实验的工作负载（Transformer-XL 推理）的绝对延迟本身就较高，无法反映对低延迟场景的影响。

---

## 七、AI Infra / MLSys 视角

1. **内核态拦截的思路值得借鉴**：在 GPU 软件栈中选择正确的拦截层对系统设计至关重要。KRYPTON 选择在 UMD-KMD 边界拦截 command buffer，而非在用户态拦截 API 或在硬件层模拟 MMIO，这个设计取舍展示了"找到最佳抽象层"的工程智慧。对于 AI Infra 中的 GPU 虚拟化、多租户共享等场景，这种内核态拦截方案可以作为 vGPU 解决方案的基础。

2. **反馈控制的性能保障机制**：利用 NVML/DCGM 的实时利用率信号做闭环控制，将性能目标从"分配固定资源"转变为"动态保障吞吐量"。这个思路可以迁移到 LLM serving 系统中——当前 vLLM/SGLang 等系统在多模型共置时缺乏有效的性能隔离机制，基于反馈的动态调度可能是一个有价值的方向。

3. **时空联合编排的碎片优化**：单一维度的资源分配必然产生碎片，两个维度的联合优化显著扩大了编排空间。这个思路可以推广到 GPU 集群调度器（如 Kubernetes GPU 调度），通过同时考虑 MIG 分割和时间片分配来提升集群级别的 GPU 利用率。

4. **值得跟进的方向**：
   - 将内核态拦截扩展到 AMD GPU（论文提到 AMD GPU 也使用 command buffer 机制，但未实现）
   - 支持 MIG 动态重配置，结合预测式调度处理动态负载
   - 将反馈控制机制与 LLM serving 系统（continuous batching、prefix caching）结合，在保证 SLO 的同时最大化共置密度
   - 探索 KRYPTON 在 MoE 模型推理场景下的应用——MoE 的 expert 级别负载不均衡天然适合细粒度的时空共享

---

## 八、总结

KRYPTON 通过在内核态拦截 GPU command buffer 实现了跨运行时（CUDA + Vulkan）的 GPU 共享，结合基于反馈的自适应时间片控制和两阶段时空编排算法，在保障应用性能目标（平均误差 3.3%）的同时减少了 32.1% 的 GPU 需求。其核心价值在于选择了正确的拦截抽象层以同时解决兼容性和隔离性问题，并通过时空联合优化减少 GPU 碎片。主要局限在于空间共享依赖 MIG 硬件支持、不支持动态空间重配置、评估工作负载较老且缺乏当前主流 LLM/扩散模型场景的验证。
