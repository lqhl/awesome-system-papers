# CacheSlide: Unlocking Cross Position-Aware KV Cache Reuse for Accelerating LLM Serving

**作者**：Yang Liu, Yunfei Gu (Shanghai Jiao Tong University), Liqiang Zhang (Jinan Inspur Data Technology Co., Ltd), Chentao Wu, Guangtao Xue, Jie Li, Minyi Guo (Shanghai Jiao Tong University), Junhao Hu (Peking University), Jie Meng (Huawei Cloud)
**会议**：FAST 2026 (24th USENIX Conference on File and Storage Technologies)
**链接**：https://www.usenix.org/conference/fast26/presentation/liu-yang
**源文件**：[[fast2026-liu-yang.pdf]]

---

## 一、背景

大语言模型（LLM）在 agent 应用中日益普及，这些应用涉及复杂的 prompt 结构，包含不变的固定段（如 system prompt、历史记忆）和动态更新段（如当前推理步骤、函数调用内容）。每次推理时，即使大部分 prompt 内容不变，LLM 仍需对整个输入序列从头计算 KV cache，导致 prefill 阶段计算量巨大、Time-to-First-Token（TTFT）显著增加。

KV cache 复用是解决这一问题的关键策略。现有方法分为两类：Position-Dependent Caching（PDC）要求复用段在固定绝对位置（如 prefix），限制了灵活性；Position-Independent Caching（PIC）允许在任意位置复用，但由于位置编码失配（Positionally Misaligned KV Drift, PMKD），导致精度下降和系统开销增大。

---

## 二、要解决的问题

1. **PDC 的位置刚性**：ContextCache 只能复用 prompt 前缀的 KV cache；PromptCache 虽支持非前缀段，但需为每个位置存储独立 KV cache 副本，存储开销巨大。在 agent 场景中，固定段并非总在前缀位置，且无法简单通过重排段序解决（会破坏语义依赖）。

2. **PIC 的精度与系统问题**：CacheBlend、EPIC 等方法将复用段的位置索引重置为零，引发位置编码失配。它们通过预选部分 token 重算来弥补，但 prefill 阶段无法准确预判哪些 token 对输出最关键，精度不稳定。系统层面，layer-wise 的 load-before-write 锁消除了层内并行机会；KV cache 溢出到 SSD 时，缺乏 dirty-aware 淘汰策略导致随机写和高写放大（WAF）。

3. **Window Padding 的局限**：固定更新段长度虽可限制位置漂移，但实际 agent 场景中更新段长度波动大且不可预测，过小的窗口丢失关键信息，过大的窗口增加 PMKD。

---

## 三、洞察与设计

**关键洞察**：在 agent 工作流中，可复用段之间的相对顺序始终固定，仅绝对位置因动态段长度变化而偏移——这构成一种独立于 PDC 和 PIC 的第三类缓存模式（Relative-Position-Dependent Caching, RPDC）。只要保持相对顺序，使用低位置敏感性的编码（如 CoPE），固定段之间的位置偏差可被控制在极小范围内，从而实现段内注意力和跨固定段注意力的近无损复用。

基于 RPDC 范式，CacheSlide 设计了三个核心组件：

### 1. Chunked Contextual Position Encoding (CCPE)

将 prompt 按模板划分为 reuse chunk 和 recompute chunk。通过在单任务类型上对 CoPE 编码做预训练，提取 reuse chunk 最常见的编码模式并固定为缓存时的位置编码。推理时，缓存的位置编码与实际位置编码之间的 ∆pos 极小（例如从 (10,21) 变为 (9,20)），从而最大化 CKSim。

### 2. Weighted Correction Attention

固定段内及固定段之间的注意力可直接复用；固定段与更新段之间的交叉注意力需恢复。方法为：
- 在 layer 1 对全部 token 重算 KV，计算与缓存 KV 的偏差，选出偏差最大的 top-k token（约 26%）
- 从 layer 2 起，仅对 top-k token 重算 KV 并与缓存 KV 做加权融合（权重 α 基于偏差大小）
- 每 4 层评估一次 CKSim，若 token 已收敛（CKSim < 阈值 τ≈0.12）则替换为偏差次大的 token

### 3. SLIDE（Spill-aware, Load–write decoupling Intra-layer, Dirty-page Eviction）

- **Load-Write 解耦**：重算与 KV cache 加载并行执行；若重算先完成，将结果写入新分配的页面而非阻塞等待加载
- **Dirty-page 标记与淘汰**：含有 selected token 的页面标记为 dirty，附带 selected-token 计数。存储压力下优先淘汰 clean page；dirty page 按 selected-token 计数降序淘汰并合并写入，减少随机写和 WAF
- **Decode 阶段覆写**：优先将新 KV 写入 selected token 的原始 slot，减少存储浪费

---

## 四、实现细节

- 基于 vLLM 0.8.5 实现
- CoPE 支持通过 LoRA adapter 持续预训练获得，保留原始 backbone 权重，可随时切换回 RoPE/ALiBi
- CCPE 预训练阶段：对同一任务类型的 prompt 集合执行 CoPE 编码，用直方图统计最频繁编码模式 e*，存储备用
- Prefill 初始化：在 `PagedAttention._init_cache` 中为 layer 2...n 预分配额外 KV page（数量与 layer 1 选出的 selected token 数成比例），注册到 BlockTable 和 slot_mapping
- Relocate 阶段：调用 `KVcacheManager.promote` 将 selected token 的 KV 写入新页面并更新 block_tables/slot_mapping
- Dirty-page 标记从 layer 2 开始，维护 per-page selected-token counter
- Spill 策略：先淘汰 clean page，再按 selected-token 计数降序淘汰 dirty page，dirty extent 合并为顺序写回

---

## 五、实验结果

**实验平台**：单卡 NVIDIA A100 80GB（70B 模型用两卡），500GB DRAM，2TB NVMe SSD，PCIe Gen 4，Ubuntu 20.04，CUDA 12.6

**模型**：Mistral-7B、MPT-30B、Llama-3 70B

**Agent 基准**：Reflexion (HotPotQA)、MemGPT (Multi-Session Chat)、SWE-Agent (SWE-Agent-Bench)

**基线**：ContextCache（Kimi 实现）、PromptCache（OpenAI 实现）、CacheBlend（LMCache）、EPIC（LMCache）

| 指标 | CacheSlide vs 最佳基线 |
|------|----------------------|
| TTFT 降低 | 3.11–4.3× |
| 吞吐量提升 | 3.5–5.8× |
| SSD 写放大降低 | 3.11–3.62× |
| GPU 存储降低 vs PromptCache | 1.63–1.9× |
| vs ContextCache TTFT | 2.4–3.3× 降低，精度无明显损失 |
| vs CacheBlend TTFT / 精度 | 1.21–2.11× 降低 / 1.97–2.28× 提升 |
| vs PromptCache TTFT / 精度 | 1.12–2.45× 降低 / 1.41–3.95× 提升 |
| SLIDE 层内并行延迟降低 | 26.7–51.5% |
| SLIDE 写阻塞降低 | 66.9–73.5% |
| 吞吐量标准差降低 | 58.6–77.4% |

**最优超参数**：top-k ≈ 26%，CKSim 阈值 τ ≈ 0.12

并行推理（batch size 2→6）和 beam search 场景下，CacheSlide 的 TTFT 增长显著小于基线，表现出更强的鲁棒性。

---

## 六、批判性分析

1. **CoPE 预训练成本被轻描淡写**：CCPE 依赖 LoRA adapter 持续预训练来获得 CoPE 支持，论文声称这是"backward-compatible"的，但未报告预训练数据量、训练时间和计算成本。对于每种新模型或新任务类型都需要额外预训练，部署门槛比纯系统优化方案高得多。

2. **"negligible accuracy loss"的定义模糊**：论文反复声称精度损失可忽略，但 Figure 10 中各方法精度差异的绝对数值难以从散点图精确读取，也未提供置信区间或统计显著性检验。

3. **超参数敏感性存疑**：top-k=26% 和 CKSim=0.12 的最优值来自有限的 grid search（Figure 14），论文声称这些值在不同模型和数据集间具有一致性，但仅测试了 3 个模型和 3 个 agent 基准。是否对更长上下文、更复杂的多 agent 场景仍然稳健未可知。

4. **单任务模式假设过强**：CCPE 的编码模式 e* 是在单一任务类型上统计得出的，论文明确说明"most KV cache reused in agentic scenarios occurs under a single-task mode"。然而实际部署中，同一服务实例常服务多任务混合请求，此时 CCPE 的预训练编码可能不再有效。

5. **基线选择**：CacheBlend 和 EPIC 的 recompute 比例是固定的（18% 和 boundary 64 tokens），而 CacheSlide 使用自适应 top-k + CKSim gating，这是方法层面的优势但也使得对比不完全公平。若 CacheBlend 也采用自适应策略，差距可能缩小。

6. **SSD 溢出场景的实际覆盖面**：SLIDE 的优势在存储受限时才显现（需要 KV cache 溢出到 SSD），但论文中大部分实验在单卡 A100 80GB 上完成。对于配备充足 HBM 的部署场景，SLIDE 的收益有限。

---

## 七、AI Infra / MLSys 视角

1. **RPDC 范式的普适性**：论文提出的 RPDC 不仅适用于 agent 场景，任何具有"固定段相对顺序不变、绝对位置漂移"特征的推理模式都可受益——例如 RAG 系统中检索文档段的缓存、多轮对话中历史消息的复用。这为 KV cache 管理提供了 PDC/PIC 之外的第三条路线。

2. **位置编码与缓存友好性的协同设计**：论文揭示了位置编码（RoPE vs CoPE）对 KV cache 复用的决定性影响。这启示未来位置编码设计应将"cache-friendliness"作为评估维度——如果新的编码方案在精度相当的前提下具有更低的位置敏感性，将显著提升推理系统效率。

3. **Weighted Correction Attention 的可迁移性**：layer 1 全量重算 + 后续层自适应 top-k 融合 + CKSim gating 的策略，可推广到 Speculative Decoding 的 verification 阶段、KV cache compression 的精度恢复等场景。

4. **值得跟进的方向**：
   - 多任务混合部署下的 CCPE 泛化：能否用 task-agnostic 的预训练策略替代 per-task 预训练？
   - RPDC + Disaggregated Serving：将 RPDC 与 prefill-decode 分离架构（如 DistServe）结合，在 prefill 节点间共享固定段 KV cache
   - 动态 top-k 调度：根据实时 workload 特征（如 batch size、SSD 带宽利用率）自适应调整 top-k 比例和 CKSim 阈值

---

## 八、总结

CacheSlide 针对 agent 场景中 KV cache 复用的位置编码失配问题，提出了 RPDC 范式，通过 CCPE 降低位置敏感性、Weighted Correction Attention 恢复跨段注意力、SLIDE 优化系统层面的 load-write 并行和 SSD 溢出管理。在三种模型和三个 agent 基准上实现了 3.11–4.3× TTFT 降低和 3.5–5.8× 吞吐量提升。主要局限在于依赖 CoPE 预训练引入额外部署成本、单任务模式假设在多任务混合场景下的适用性有待验证。
