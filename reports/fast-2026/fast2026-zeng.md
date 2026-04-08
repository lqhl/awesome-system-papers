# GPU Checkpoint/Restore Made Fast and Lightweight

**作者**：Shaoxun Zeng, Tingxu Ren, Jiwu Shu, Youyou Lu（清华大学）
**会议**：FAST 2026（24th USENIX Conference on File and Storage Technologies）
**链接**：https://www.usenix.org/conference/fast26/presentation/zeng
**源文件**：[[fast2026-zeng.pdf]]

---

## 一、背景

GPU checkpoint/restore (C/R) 是现代 GPU 工作负载的核心系统原语，支撑三大关键场景：(1) 弹性 GPU serverless 扩缩容——通过快速恢复预检查点的实例绕过复杂初始化，降低冷启动延迟；(2) 快速 GPU 任务切换——在推理/训练混部、强化学习等场景中通过快速 checkpoint（switch-out）和 restore（switch-in）提高 GPU 利用率；(3) 容错 GPU 计算——通过周期性 checkpoint 保存 GPU 状态，在故障后恢复以减少重算开销。

系统级 GPU C/R 相比应用级方案具有统一性和应用透明性优势，无需在每个应用中重复实现 C/R 逻辑。现有系统级方案分为两类：driver-integrated C/R（如 NVIDIA cuda-ckpt）和 interception-based C/R（如 PhOS）。

---

## 二、要解决的问题

现有方案存在三个核心限制：

1. **无法同时实现低 C/R 延迟和低运行时开销**。Driver-integrated C/R（cuda-ckpt）对正常 GPU 执行零开销，GPU 控制状态处理高效，但 GPU 数据缓冲区的 checkpoint 带宽利用率极低（仅达 PCIe 理论带宽的 12.0%），导致延迟高。Interception-based C/R（PhOS）数据拷贝带宽较高（24.3 GB/s），但需要拦截和处理所有 GPU driver API 调用，导致控制状态 C/R 延迟分别是 cuda-ckpt 的 3.5× 和 9.2×，且对正常执行引入平均 8.7%、最高 49.6% 的性能下降。

2. **不支持增量 checkpoint**。现有方案每次都全量 checkpoint 所有 GPU 数据缓冲区，即使大部分缓冲区（如只读模型参数）未被修改，导致 7.2× 的 checkpoint 放大。PhOS 虽有 dirty buffer 识别机制，但因运行时开销过高（最高 12% 性能下降）而默认禁用，且粒度粗糙。

3. **运行时开销不可接受**。Interception-based 方案需要拦截所有 GPU driver API，包括资源句柄映射和动态替换，严重拖慢正常执行。

---

## 三、洞察与设计

**关键洞察**：GPU 控制状态和数据缓冲区可以通过选择性拦截 GPU 内存分配/释放操作进行清晰分离，从而对二者分别采用最适合的 C/R 策略；同时，GPU kernel 的 dirty buffer 地址和长度可以表达为 kernel 参数和启动配置的函数，因此可以通过符号执行生成 dirty template，在 CPU 上以微秒级开销并行识别 dirty buffer，而无需在 GPU 执行路径中插桩。

基于上述洞察，GCR 包含两个核心设计：

### 1. Hybrid C/R：控制/数据分离

GCR 将 driver-integrated C/R 用于 GPU 控制状态（零运行时开销、高效控制状态处理），将 interception-based C/R 用于 GPU 数据缓冲区（高数据拷贝带宽）。关键在于只选择性拦截 GPU 内存分配（cuMemAlloc）和释放（cuMemFree），仅记录缓冲区地址和长度（16 bytes/buffer），对正常执行开销 < 1%。

**缓冲区地址一致性问题**：Hybrid C/R 需要显式保证恢复后缓冲区地址一致。GCR 通过解耦虚拟和物理内存管理解决：checkpoint 后仅释放物理内存（cuMemUnmap + cuMemRelease），保留虚拟地址；driver-integrated C/R 随后 checkpoint GPU 页表以保存虚拟地址映射。恢复时，先恢复控制状态（含页表），再创建新物理内存并重映射到保留的虚拟地址。

### 2. 增量 checkpoint：Shadow Execution + Dirty Templates

GCR 通过符号执行离线生成 dirty template——将 kernel 中的 store 指令转化为以 kernel 参数和启动配置为变量的表达式，去除所有计算逻辑。运行时，GCR 拦截 kernel launch，提取参数填充 dirty template，在 CPU 上并行执行 shadow execution（微秒级计算、< 1 MB 内存），实现指令级粒度的 dirty buffer 识别，完全不影响 GPU 执行路径。

---

## 四、实现细节

- **Dirty template 生成**：在 PTX ISA 层面进行符号执行，枚举所有 store 指令，将目标地址和长度转化为 kernel 参数和 launch 配置的表达式，编译为 C++ 函数并链接到 GCR 库。每个 kernel 只需生成一次（离线）。
- **API 分类处理**：(a) 内存分配/释放不需要 dirty template（分配不修改内容，释放丢弃内容）；(b) 闭源库函数（cudaMemcpy、ncclAllReduce、cublasSgemm）根据文档标记 dirty 参数；(c) 开源 kernel 通过 PTX 符号执行生成 template；缺乏文档的闭源 kernel 则保守标记所有非 const 参数为 dirty。
- **模型推理优化**：利用工作负载特征，模型参数标记为只读，KV Cache 选择性应用 dirty template，其他中间缓冲区标记为全脏。实现上只需在推理初始化时为参数和 KV Cache 分配各添加两行代码。
- **Checkpoint 前同步**：使用 cudaDeviceSynchronize 同步所有执行中的 kernel（毫秒级，远低于 C/R 延迟）。
- **增量 checkpoint 存储**：增量 checkpoint 与上一个全量 checkpoint 合并存储在 CPU 内存中，避免恢复时合并开销。
- **CPU 状态 C/R**：使用成熟的 CRIU 方案。
- **页表 checkpoint 开销**：< 0.1%；虚拟地址重映射开销微不足道（27.3 GB 缓冲区仅 432 µs）。

---

## 五、实验结果

**硬件平台**：2× A100-40GB GPU（NVLink，PCIe 4.0）。软件：CUDA 12.6，PyTorch 2.7.1，Transformers 4.53.3/4.30.0，vLLM 0.9.1，DeepSpeed 0.17.5。

**对比系统**：cuda-ckpt（NVIDIA 官方 driver-integrated C/R）、PhOS（SOTA interception-based C/R）。

| 场景 | 指标 | GCR vs cuda-ckpt | GCR vs PhOS |
|------|------|-------------------|-------------|
| 弹性 serverless 恢复 | 冷启动延迟 | 降低 54.2% | 降低 87.1% |
| GPU 任务切换 | 切换延迟 | 降低 71.6% | 降低 74.1% |
| 容错 checkpoint | checkpoint 延迟 | 降低 72.1% | 降低 63.6% |
| 增量 checkpoint | checkpoint 大小 | 降低 86.6%（vs 首次全量） | — |
| 增量 checkpoint | checkpoint 延迟 | 降低 43.8%（vs 首次全量） | — |
| 正常执行开销 | 吞吐下降 | < 1% | PhOS 平均 8.7%，最高 49.6% |

**关键数据**：
- GCR checkpoint 带宽：20.5 GB/s（vs cuda-ckpt 3.0 GB/s，PhOS 11.2 GB/s）
- GCR restore 带宽：23.0 GB/s，达 PCIe 带宽上限的 92.0%（vs cuda-ckpt 7.2 GB/s）
- Shadow execution 开销：14 µs 计算 + < 1 MB CPU 内存
- 5 分钟 checkpoint 间隔下有效训练比例达 99.1%
- 对比应用级 C/R（DeepSpeed、Transformers save_pretrained、ServerlessLLM），GCR 分别降低延迟 87.8%、77.6%、83.3%
- 多 GPU 场景下 GCR 保持高效（各 GPU 独立并行 C/R）

---

## 六、批判性分析

1. **Dirty template 覆盖范围存疑**。论文承认对缺乏文档的闭源 kernel 无法生成 dirty template，此时回退到保守的全参数标脏策略。但文中声称"现代 GPU 应用通常依赖开源 kernel 框架如 PyTorch"来缓解此限制，这一论断过于乐观——许多生产环境依赖 NVIDIA 专有库（cuDNN、TensorRT）中大量闭源 kernel，GCR 在这些场景下增量 checkpoint 的实际收益可能大打折扣。

2. **Dirty template 对 pointer chasing 和复杂计算的局限**。当 dirty 地址依赖于额外的 GPU 内存（如间接寻址）或涉及复杂计算（如哈希函数）时，GCR 同样无法生成 template 而回退到保守策略。论文未量化这类 kernel 在实际工作负载中的占比，也未评估回退策略对增量 checkpoint 放大率的影响。

3. **实验硬件和规模有限**。所有实验仅在 2× A100-40GB 上完成，未涉及大规模多节点场景。对于实际的分布式训练（数百/数千 GPU），checkpoint 的存储后端瓶颈、网络带宽、协调开销等问题未被讨论。论文也承认 checkpoint 目前仅存储在 CPU 内存，SSD 和远程存储作为 future work。

4. **Checkpoint 后需要恢复才能继续训练**。在容错训练场景中，GCR 的 hybrid C/R 设计要求 checkpoint 后释放数据缓冲区的物理内存再恢复，导致额外的 stall time。虽然论文称 3 分钟间隔下仅占 3%，但对频繁 checkpoint 场景（如强化学习）这一开销可能更显著。PhOS 的并发 checkpoint 理论上可以避免此问题，但论文以"并发 C/R 在评估场景中不够高效"为由未做实现，回避了直接对比。

5. **cuda-ckpt 带宽低的原因未解释**。论文多次指出 cuda-ckpt 仅达 PCIe 带宽的 12%，但因其闭源而"原因不明"。这使得 GCR 相对 cuda-ckpt 的优势部分可能来自 cuda-ckpt 自身的实现缺陷而非 GCR 设计的固有优越性——如果 NVIDIA 修复了带宽问题，GCR 的相对优势会显著缩小。

6. **符号执行的可维护性**。Dirty template 需要在 PTX ISA 层面进行符号执行，每当 GPU kernel 更新（框架版本升级、新算子引入）都需要重新生成。论文未讨论这一持续维护成本。

---

## 七、AI Infra / MLSys 视角

1. **LLM 推理 serverless 冷启动优化**。GCR 将 LLM 推理恢复延迟降低至接近 PCIe 带宽上限（23.0 GB/s），这对 serverless LLM serving（如 vLLM + 弹性扩缩容）具有直接价值。结合 KV Cache 感知的增量 checkpoint（86.6% 大小缩减），可以显著降低推理/训练混部场景下的任务切换开销。

2. **训练容错的轻量化方案**。相比 DeepSpeed 等应用级 checkpoint（需要框架深度集成），GCR 的系统级方案提供了应用透明的替代选择。5 分钟间隔下 99.1% 的有效训练比例意味着在中小规模训练中 GCR 可以作为低成本的容错基线。

3. **Shadow execution + dirty template 的思路可迁移**。将 GPU kernel 的写操作模式提取为轻量 CPU 侧可执行的模板，这一方法论可以推广到：(a) GPU 内存去重（识别相同内容的缓冲区）；(b) 内存预取（预测即将被访问的缓冲区）；(c) GPU 内存压缩（识别热点写区域进行差异压缩）。

4. **值得跟进的方向**：
   - 将 checkpoint 后端扩展到 CXL 内存或 RDMA 远程内存，结合 GCR 的高带宽利用率可进一步降低大规模训练的 checkpoint 延迟
   - 探索 GCR 与 pipeline parallelism 的结合——在 pipeline bubble 中执行 checkpoint 可以完全隐藏 stall time
   - 将 dirty template 技术与 GPU 内存 oversubscription 结合，用于精确的页面迁移决策

---

## 八、总结

GCR 是一个系统级 GPU checkpoint/restore 方案，通过 hybrid C/R（控制状态用 driver-integrated、数据缓冲区用 interception-based）实现低延迟和低运行时开销的统一，通过 shadow execution + dirty template 实现高效的增量 checkpoint。在 A100 平台上，GCR 相比 cuda-ckpt 和 PhOS 分别将 checkpoint 延迟降低 72.1% 和 63.6%，恢复延迟降低 54.2% 和 87.1%，运行时开销 < 1%。主要局限在于 dirty template 依赖开源 kernel 和可表达的写模式，对闭源库和复杂间接寻址场景存在覆盖盲区；评估仅限于单机双卡，大规模分布式场景的有效性有待验证。
