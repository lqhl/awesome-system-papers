# Learning-Enhanced High-Throughput Pattern Matching Based on Programmable Data Plane

**作者**：Guanglin Duan, Yucheng Huang, Zhengxin Zhang (Peng Cheng Laboratory / Tsinghua SIGS / Cornell), Qing Li, Dan Zhao (Peng Cheng Laboratory), Zili Meng (HKUST), Dirk Kutscher (HKUST-GZ), Ruoyu Li (Shenzhen University / Peng Cheng Laboratory), Yong Jiang (Tsinghua SIGS), Mingwei Xu (Tsinghua University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/duan-guanglin
**源文件**：[atc2025-duan-guanglin.pdf](../../papers/atc-2025/atc2025-duan-guanglin.pdf)

---

## 一、背景

网络模式匹配（Pattern Matching）是网络安全应用的核心功能，广泛用于入侵检测/防御系统（NIDS/NIPS）、Web 应用防火墙、网络审查系统和应用识别系统等场景。这些应用需要扫描数据包的头部和载荷，检查是否匹配给定的规则集（包含字符串和正则表达式）。

随着网络带宽已突破数百 Gbps 甚至迈向 800Gbps 时代，现有的模式匹配方案在**高吞吐、低成本、可维护性**三个维度上难以同时满足需求。基于 CPU 的软件方案吞吐量上限约 70Gbps；GPU/FPGA/NPU 硬件加速方案虽能达到 ~100Gbps，但成本高、管理复杂、更新困难；而可编程交换机虽然天然具备 multi-Tbps 线速处理能力和低成本优势，但受限于计算和存储资源约束（如 Tofino 1 仅有 12 个 MAU stage、120MB SRAM、6.2MB TCAM），现有方案只能支持简单的多字符串匹配，无法处理完整的正则表达式模式匹配。

---

## 二、要解决的问题

1. **吞吐量瓶颈**：CPU 方案无法达到 70Gbps 以上；GPU/FPGA 方案受 PCIe 带宽限制，最高约 100Gbps，且成本高昂。可编程交换机方案受限于自动机状态转换的资源爆炸问题，无法扩展到大规模模式集。

2. **准确性不足**：现有可编程交换机方案（如 BOLT）基于 NFA 的序列化状态转换，面对复杂正则表达式语法（如范围匹配 `[a-f]`）时资源需求线性增长，只能支持有限的多字符串匹配，无法实现完整的模式匹配。

3. **可维护性差**：传统模式匹配系统的规则由专家手工编写或由厂商私有算法离线生成，面对新型攻击和流量模式时更新成本高、响应慢，无法高效地自动适应持续变化的网络威胁。

---

## 三、洞察与设计

**关键洞察**：DFA 的前向计算过程（Forward Algorithm）在数学形式上等价于 RNN 的前向传播——当 RNN 的输入权重 U=0、偏置 b=0、激活函数为恒等函数时，DFA 的状态转移矩阵运算与 RNN 的隐藏状态递推完全一致。这意味着可以将专家知识编码的模式规则无损转换为神经网络模型，从而用模型推理替代传统的自动机匹配，既保留了规则的准确性，又获得了通过训练自动更新的能力。

基于此洞察，Trochilus 框架包含两大模块：

### 数据平面感知模型设计

1. **Pattern Modelization**：将 PCRE 模式 → NFA → DFA → Byte-level RNN (BRNN)。BRNN 在 zero-shot 场景下即可达到与传统模式匹配系统（TPS）相同的准确率（~85%），且有标注数据时可通过训练进一步提升到 ~98.5%。

2. **Semi-Supervised Knowledge Distillation (SSKD)**：将笨重的 BRNN（包含浮点和非线性运算）蒸馏为轻量的 Soft Multi-view Forest (SMF)。SMF 由多棵 Soft Decision Tree (SDT) 组成，使用二进制特征，通过加权迭代训练实现多视角观察。SSKD 机制联合利用有标注数据的真实标签和 BRNN 在全部数据上的软标签（混合标签 Ymix = β·Yhard + (1-β)·Ysoft），解决了标注数据稀缺的问题。

### 模型部署

3. **Tree Encoding**：将 SDT 转换为三元匹配表（ternary match-action table），使用二进制特征避免十进制特征的 range matching 组合爆炸问题。

4. **Entry Cluster 算法**：将 N 条表项按 Jaccard 距离聚类为 k 个子集，每个子集只需匹配特征的一个子集，大幅减少 TCAM 需求（最高减少 92.5%）。这是一个 NP-hard 优化问题，采用类 K-medoids 的启发式算法求解。

5. **Sliding Window 机制**：通过重叠滑动窗口（窗口大小 win=64 bytes，步长 s=30 bytes）检查数据包载荷，确保跨窗口的模式也能被检测到，同时利用多 MAU stage 提高单 pipeline 检查深度。

---

## 四、实现细节

- **数据平面**：约 2000 行 P4_16 代码，部署在 Tofino 交换机上。为每个滑动窗口复制模型表和聚合表，交换机提取不同窗口的载荷段到自定义头部，各模型表并行推理后由聚合表投票得出最终结果。

- **控制平面**：约 4000 行 Python 代码。使用 `automata_tools` 库进行模式到 DFA 的转换，PyTorch 实现 BRNN 训练，NumPy 实现 SSKD 和 SMF。

- **关键超参数**：
  - BRNN：学习率 10⁻⁴，batch size 500，hidden state size 100，训练 200 epochs + early stopping
  - SSKD：β=0.5，SDT 数量 nt=5，权重过滤阈值 tw=0.5，叶节点最小样本数 15
  - Entry Cluster：k=5 个子表
  - Sliding Window：win=64 bytes，s=30 bytes

- **硬件平台**：12-stage 6.4Tb/s EdgeCore wedge100BF-65X Tofino 交换机，Intel Xeon Gold 5218 CPU，两台 Dell R230 服务器（40Gbps NIC，DPDK Pktgen 流量回放）。

- **在线更新**：收集新标注流量 → 离线增量训练 BRNN → 重新蒸馏 SMF → 转换为表项 → 安装到交换机（不中断服务）。

---

## 五、实验结果

### 准确性

| 场景 | 模型 | 0% 训练数据 | 10% 训练数据 | 100% 训练数据 |
|------|------|------------|-------------|--------------|
| Teacher (Snort) | BRNN | 85.2% | 96.3% | 98.5% |
| Teacher (Snort) | TPS | 85.2% | 85.2% | 85.2% |
| Teacher (Snort) | CNN（最佳 baseline） | ~50% | ~93% | ~95% |
| Student (Snort) | SMF | 83.7% | 94.9% | 98.2% |
| Student (Snort) | SRF | 81.7% | 89.6% | 92.9% |
| Multi-string | T-MSM-12 vs BOLT | 持平 TPS | >15% 优于 BOLT | >10% 优于 TPS |

### TCAM 资源

| 方案 | 相对 BOLT 的 TCAM 削减 |
|------|----------------------|
| T-MSM-4 | 减少 97.8% |
| T-MSM-8 | 减少 95.6% |
| T-MSM-12 | 减少 93.4% |

BOLT 的 TCAM 需求随模式数增长急剧上升（500→3500 模式时增长 4 倍），Trochilus 仅增长约 10%。

### 吞吐量

- Trochilus-8 达到 BOLT 的 2.3 倍吞吐量
- Trochilus-12 达到 BOLT 的 2.8 倍吞吐量
- 对短包（~200 bytes）可提供数千 Gbps 吞吐；大包（~1000 bytes）因 recirculation 吞吐量降低但仍显著优于 BOLT

### 30 天持续运行实验

- 第 10、20 天注入 zero-day 攻击流量（占原攻击流量 10%）
- Snort 准确率分别下降 ~4%、~6%，且无法自动恢复
- Trochilus 短暂下降 ~3%、~4%，次日通过自动训练恢复至 ~97%

---

## 六、批判性分析

1. **吞吐量评估存在局限**：论文承认受限于流量生成器能力，无法完全覆盖 Tofino 交换机带宽，因此吞吐量结果是**理论上限的模拟值**（"simulate the theoretical upper limit"），而非实测端到端吞吐量。multi-Tbps 的标题性能宣称缺乏真实流量下的完整验证。

2. **准确率指标可能掩盖问题**：论文使用加权准确率作为主要指标，权重为各类别样本数的交叉乘积。这种加权方式在类别严重不平衡时的行为需要仔细审视——尤其是在安全场景中，漏报率（false negative rate）和误报率（false positive rate）比整体准确率更有实际意义，但论文未报告这些指标。

3. **zero-shot 准确率的参考意义有限**：BRNN 在 zero-shot 下达到 85.2%，与 TPS 持平，这是因为 BRNN 本质上就是 DFA 的等价表示。但 SMF（实际部署的模型）zero-shot 下降到 83.7%，说明蒸馏过程确实存在知识损失。在安全场景中，~16% 的 miss rate 是否可以接受值得商榷。

4. **模式覆盖范围未充分说明**：论文声称支持"complete pattern matching"，但实际支持的 PCRE 语法子集（Table 2）不包含 lookahead/lookbehind、backreference 等高级特性。将此称为"complete"有过度宣称之嫌。

5. **30 天实验设计偏理想化**：zero-day 攻击流量仅占 10%，且假设每天都有标注数据可供训练。实际部署中，新型攻击可能占比更高、标注滞后更严重，Trochilus 的恢复速度可能不如实验所示。

6. **Entry Cluster 算法的最坏情况**：论文承认最坏情况下算法不执行任何合并，TCAM 使用量与原始 SMF 相同。但缺乏对何种模式分布会导致最坏情况的分析，实际部署中的平均性能保证不明确。

7. **仅支持明文载荷**：系统仅处理未加密的明文流量，对于日益普及的 TLS 加密流量需要依赖额外的解密机制。论文仅提及可与已有解密方案结合，但未讨论解密引入的延迟和吞吐量开销。

---

## 七、AI Infra / MLSys 视角

1. **模型-硬件协同设计的范式价值**：Trochilus 展示了一种"先将领域知识编码为神经网络 → 再蒸馏为硬件友好模型"的通用范式。这种思路可以迁移到 AI Infra 中的多个场景：例如将 LLM 推理中的路由决策、负载均衡策略、KV cache 驱逐策略等编码为轻量模型部署到数据平面，实现线速智能决策。

2. **知识蒸馏在资源受限场景的应用**：SSKD 机制结合冷启动（从规则直接转换的 teacher 模型不需要训练数据）和半监督学习的思路，对 edge AI 和 on-device inference 场景有借鉴意义。特别是在标注数据稀缺的工业场景中，从专家规则出发冷启动 teacher 模型是一种实用的策略。

3. **可编程交换机上的模型部署优化**：Entry Cluster 算法将 TCAM 使用量减少 90%+ 的思路，对在网智能（in-network intelligence）的模型压缩与表示方法有参考价值。随着 SmartNIC 和 DPU 的普及，如何在严格的硬件约束下高效部署 ML 模型是一个有价值的研究方向。

4. **潜在延伸方向**：
   - 将此框架扩展到 AI 推理请求的在网分类和路由，实现 LLM serving 的智能负载均衡
   - 探索在可编程交换机上部署更复杂的模型（如 Transformer 的简化变体），突破当前 decision tree 的表达能力限制
   - 研究在网模型的在线增量更新机制，减少模型更新时的服务中断

---

## 八、总结

Trochilus 提出了一种将模式匹配从传统自动机方法转化为可编程交换机上的模型推理的框架，核心创新在于利用 DFA 与 RNN 的数学等价性实现无损模式建模，并通过半监督知识蒸馏将模型压缩为数据平面可部署的轻量级 decision tree 集成模型。系统在 multi-Tbps 吞吐量（模拟值）、高准确率（~98%）和自动更新能力三方面相较于现有方案有显著优势。主要局限在于吞吐量为理论模拟而非实测、仅支持明文流量、PCRE 语法覆盖不完整，以及安全关键场景下 ~16% 的冷启动 miss rate 可能不够理想。该工作适用于大规模网络安全监控场景中对吞吐量和成本有严格要求的部署环境。
