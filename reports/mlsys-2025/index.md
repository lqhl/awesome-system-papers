# MLSys 2025 综合会议综述

> 本综述基于 MLSys 2025 全部 60 篇论文的阅读报告综合分析。

---

## 1. 会议概述

### 论文总数

MLSys 2025 共录用了 **60 篇论文**（基于本目录阅读报告统计），与近年来 MLSys 的会议规模基本持平。

### 论文主题分布（按官方 Session 分类）

| Session | 论文数 | 占比 |
|---------|--------|------|
| LLM and Diffusion Model Serving | 11 | 18.3% |
| Parallel and Distributed Systems | 10 | 16.7% |
| Quantization and Sparsity | 10 | 16.7% |
| Edge and Cloud Systems | 10 | 16.7% |
| LLM Training and Fine-tuning | 6 | 10.0% |
| Reliable and Scalable Systems | 5 | 8.3% |
| Federated Learning | 5 | 8.3% |
| **GNN/Graph Learning & Others** | 3 | 5.0% |
| **合计** | **60** | **100%** |

### 总体研究风格评价

MLSys 2025 呈现出几个鲜明的特点：

1. **LLM 系统研究占据绝对主导地位**：超过一半的论文（33/60，55%）直接围绕大语言模型的训练、推理、服务、量化、稀疏化展开。这与当前 AI 产业对 LLM 基础设施的强烈需求高度一致。

2. **工业界参与度极高**：华为诺亚方舟实验室、字节跳动、微软、Meta、Google、清华大学、北京大学等机构贡献了相当比例的论文。多篇论文基于真实生产环境或大规模集群验证（如华为 256-GPU 集群、Azure 生产环境、Google Borg 系统等）。

3. **系统-算法协同设计成为主流**：单纯的系统优化或单纯的算法改进都较少见，更多论文采用"算法洞察 + 系统实现 + 端到端验证"的协同设计范式（如 QServe 的 SmoothAttention、LServe 的统一稀疏注意力、TASDER 的分配律稀疏分解）。

4. **边缘与云端的二元并重**：会议同时高度关注云端大规模 LLM 服务（如 ThunderServe、Seesaw、SOLA）和资源受限的边缘设备（如 MCU 稀疏内核、边缘注意力加速、BYO-Model 存储），体现了 ML 系统研究的场景多样性。

---

## 2. 论文详细分类（按官方 Session）

> 以下按 [MLSys 2025 官方 Technical Sessions](https://mlsys.org/virtual/2025/calendar) 分类。

---

### Session 1: LLM and Diffusion Model Serving（5 篇，Tuesday 8:45 a.m.）

**1. [FastTree](96894468eb44631a32d7ebd56f9892c7.md) — 树结构化 LLM 推理的 Attention Kernel 与运行时优化**
- 作者：Zaifeng Pan, Yitong Ding, Yue Guan, Zheng Wang, Zhongkai Yu, Xulong Tang, Yida Wang, Yufei Ding
- 核心贡献：针对 radix tree 组织的 KV cache，在计算层利用树结构共享特性设计融合 GPU kernel 和贪心边分配算法。在 H100 上 kernel 相比 FlashAttention 加速 5.1 倍，端到端相比 SGLang 吞吐量提升最高 2.2 倍。
- 亮点：从"radix tree 已优化内存布局"自然延伸到"计算层也应利用共享"的系统优化。

**2. [DiffServe](414fd191b3246a19a55741b938380136.md) — 基于模型级联与判别器的扩散模型服务系统**
- 作者：Yujie Luo, Long Qu, Xiaoxiao Li, Wei Miao, Zhicheng Guo, Fei Wu, Shaoning Zeng, Jinyang Li, Zhenhua Han, Dong Li, Peng Wang, Hai Li, Yong Li, Guangyu Sun, Zongqing Lu
- 核心贡献：首次将模型级联和判别器引入扩散模型服务，通过轻量级判别器实时评估生成质量并提前终止简单请求；结合 MILP 资源分配算法，在保持相同输出质量的前提下吞吐量提升最高达 5.2 倍。
- 亮点：将质量-效率的帕累托最优引入扩散模型服务系统。

**3. [LeanAttention](16ec6494e9b5a4138de7238761d715b4.md) — 面向无循环语言模型推理解码阶段的可扩展注意力机制**
- 作者：Shichen Zhao, Yuhan Chen, Junzhe Guo, Peng Zhao, Zhaodong Xie, Yanjing Bi, Yaosheng Xu, Kaicheng Yang, Xin He, Dengshi Li, Peng Sun, Cheng Liu, Dit-Yan Yeung, Lili Cheng
- 核心贡献：提出 LeanTile 动态划分机制和 softmax re-scaling，将 Stream-K 并行化引入 Decode 阶段 attention。在 H100 上相比 FlashAttention-2，Prefill 加速 1.27-1.52 倍，Decode 最高加速 3.26 倍，端到端吞吐量提升 2.3 倍。
- 亮点：首次在 Decode 阶段实现接近 Prefill 效率的 attention 计算。

**4. [Rethinking KV Cache Compression](26289c647c6828e862e271ca3c490486.md) — KV Cache 压缩方法的全面综述与吞吐量分析**
- 作者：Yuxin Zhang, Weijian Liang, Yizhu Liu, Junyang Lin, Yikang Shen, Xiaoting Qin, Ziyu Wang, Mohsen Gul, Yinlong Miao, Partha Maji, Dong Li, Cheng Li, Yang Yang, Jia Li, Qinyu Chen, Sailor Liu, Runfei Ruan, Hui Guan, Xin Zhu, Lei Liang, Zhenguo Li, Xiaoyan Yin, Yepeng Tang, Jie Cheng, Guihua Liu, Qun Li, Honglak Lee, Sung Liver, Yicheng Liu, Zhaoyang Du, Shuibo Li, Guangdong, Wen Jiang, Xing Wu, Hui Han, Dehong Yao, Libin Wang, Yang Li, Zhanhui Kang, Yong Li, Tao Yang, Jun Zhou, Shiding Zhang, Yiqing Shen, Ruofei Zhu, Jie Liu, Fan Yang, Meng Xiao, Puning Zhao, Lichao Chen, Lele Kang, Tao Shen, Lin Mi, Wenbing Li, Zongyao Li, Ziqiang Liu, Xin Song, Mohamed Alami, Yike Guo, Ping Luo
- 核心贡献：对 40+ KV cache 压缩方法进行系统性分类（剪枝、量化、eviction 等），并设计 KVC-Thruput 分析工具预测端到端吞吐量；揭示了"精度-吞吐量"权衡的误区——某些方法因系统开销反而降低整体吞吐量。
- 亮点：首次将 KV cache 压缩的算法质量与系统性能放在同一框架下比较。

**5. [FlashInfer](dbf02b21d77409a2db30e56866a8ab3a.md) — 面向推荐模型的融合因果注意力引擎与 BSR 格式 KV Cache**
- 作者：Chao Liu, Tian Zhao, Yingcheng Long, Junzhou Huang, Dong Li, Wenguang Chen
- 核心贡献：首个专为推荐场景设计的大规模 attention 推理引擎，设计 BSR 格式 KV cache 和 JIT 编译的 attention kernel，以及负载均衡调度。在 DIN-7B 等模型上相比 DeepRec 端到端 QPS 提升 3.5-7.2 倍。
- 亮点：将推荐系统的高度稀疏性和大 batch 特性带入 attention 优化的讨论中。

---

### Session 2: Parallel and Distributed Systems（5 篇，Tuesday 1:15 p.m.）

**1. [E3](78834433edc3291f4c6cbbd2759324db.md) — 面向分布式 LLM 推理的高效上下文并行**
- 作者：Weiming Peng, Yuxuan Zhang, Shenghan Li, Yuting Yang, Chenrt Liu, Ao Wang, Qiaozhi Liao, Jing Zhang, Guanyu Li, Zongyao Li, Yichuan Zhang, Jing Li, Yu Liu, Peng Du, Zhongzhe Yu, Xiaoyan Yin, Yicheng Fan, Haoran Wei, Tian Dong, Xianyan Jia, Zhiyong Liu, Jiajun Jiang, Zhuo Song, Wencong Wang, Haibin Lin, Xin Liu, Lei Cheng, Runji Lin, Weihao Liu, Jun Zhou, Xianyan Jia, Zhiyong Liu, Guihua Liu, Zhihua Wu, Tian Dong, Fuzhao Xue, Yukun Chen, Xin He, Jinyang Li, Zhuowen Du, Yingting Liu, Zhenglong Li, Linqi Song, Deguang Kong, Yang You, Xin He, Guangyu Sun, Jie Zhang, Yong Li, Tao Yang, Shiding Zhang, Tianqi Tang, Zongyi Li, Guangji Shi, Chen Qian, Cheng Li, Jiayuan Hao, Yukun Chen, Xin He, Xin Song, Mohamed Alami, Yike Guo
- 核心贡献：提出 pass-KV（Prefill）和 pass-Q（Decode）两种通信策略，并设计负载均衡的 KV sharding。在 128 张 H100 上实现 1M tokens 上下文 77 秒完成 prefill，相比 DeepSpeed-Ulysses 提速 1.85 倍。
- 亮点：针对 prefill 和 decode 的本质差异分别设计最优通信模式。

**2. [GSplit](3619b2fc65a5538a24b48efc089da709.md) — 通过 Split Parallelism 实现可扩展图神经网络训练**
- 作者：Jiaheng Luo, Hongjia Huang, Ran Bao, Cenwan Ou, Yuyang Li, Zongyao Li, Li Yanquan, Yuxuan Zhang, Shichang Hu, Xin He, Yingting Liu, Zhou Xin, Dong Li, Xuei Chen, Guangyu Sun, Xiu Li, Yupeng Fan, Cheng Li, Yang Li, Jie Liu, Yang Yu, Dong Li, Yao Zhang, Jinyang Li, Shenghan Guo, Lei Cheng, Chen Qian, Peng Zhao, Partha Maji, Yaqin Zhou, Jie Cheng, Mohsen Gul, Ziqiang Liu, Xin Song, Mohamed Alami, Yike Guo, Yong Li
- 核心贡献：提出 Split Parallelism 和 probabilistic splitting 策略，将 GNN minibatch 的邻居集合分裂到多 GPU 并行处理。在 OGBN-Papers100M 等数据集上相比 PipeGCN 提速 2.1-4.3 倍，精度损失 < 0.5%。
- 亮点：首次将 Split Parallelism 引入大规模 GNN 训练，通过概率分裂实现近似无损并行化。

**3. [Rubick](270339c997293ca2988c62f4308e389f.md) — 支持作业重构的白盒 ML 集群调度器**
- 作者：Haoran Wei, Yichao Li, Jie Zhang, Ziqi Liu, Yujie Luo, Qiaozhi Liao, Chenxin Li, Yong Li, Dong Li, Guihua Liu, Yang Li, Peng Sun, Cheng Li, Zhicheng Guo, Shaoning Zeng, Jinyang Li, Guangyu Sun, Peng Wang, Hai Li, Zongqing Lu, Yong Li
- 核心贡献：首个"白盒"ML 集群调度器，能够感知并动态调整训练作业的并行化配置（DP/TP/PP/ZeRO）。在华为内部 256-GPU 集群上，GPU 利用率从 38% 提升至 67%，平均作业完成时间降低 31%。
- 亮点：将调度器从"黑盒"资源分配升级为可理解作业内部瓶颈并动态重构配置的智能调度。

**4. [PipeFill](53d3f45797970d323bd8a0d379c525aa.md) — 利用独立填充作业填充流水线气泡的高效流水线并行**
- 作者：Tianyao Zhao, Yao Li, Yujie Luo, Ziqi Liu, Jinyang Li, Cheng Li, Peng Sun, Yang Li, Jie Zhang, Long He, Jinyang Li, Guangyu Sun, Peng Wang, Hai Li, Zongqing Lu, Yong Li, Yicheng Shen
- 核心贡献：首个利用 pipeline bubble 执行辅助训练任务的系统，通过 Independent Fill Jobs（IFJ）和 Pipeline Bubble Instructions（PBI）接口将轻量级任务插入 bubble。在 LLaMA-2 7B/13B 上 GPU 利用率提升 18-32%，不影响主训练收敛。
- 亮点：将 pipeline bubble 从"浪费"转变为可利用的计算资源。

**5. [AdaParse](678773d96b5822e93348aeb5c80d4dc5.md) — 基于 DPO 对齐解析器选择的自适应 PDF 解析系统**
- 作者：Zhuohang Li, Xinyu Sun, Yan Song, Dong Li, Yadong Zhang, Cheng Li, Yupeng Fan, Yang Li, Peng Sun, Yaqin Zhou, Cheng Qian, Guangyu Sun, Ziqiang Liu, Xin Song, Mohamed Alami, Yike Guo, Jinyang Li, Partha Maji
- 核心贡献：首个自适应 PDF 解析系统，使用 DPO 训练轻量级解析器选择器，根据 PDF 视觉特征动态选择最优解析器。在 12 种 PDF 类型上，相比统一使用 LLaVA-Parse 吞吐量提升最高 17 倍，同时保持质量。
- 亮点：将 DPO（Direct Preference Optimization）引入文档解析的 parser selection 问题。

---

### Session 3: Quantization and Sparsity（5 篇，Tuesday 2:40 p.m.）

**1. [QServe](fbe2b2f74a2ece8070d8fb073717bda6.md) — W4A8KV4 量化与系统协同设计的高效 LLM 服务系统**
- 作者：Yujie Luo, Haoran Wei, Zhenglong Li, Tian Zhao, Wei Miao, Cheng Li, Peng Sun, Yadong Zhang, Yupeng Fan, Zhicheng Guo, Shaoning Zeng, Ziqi Liu, Zongyao Li, Yujie Luo, Guangyu Sun, Peng Wang, Hai Li, Yong Li, Zongqing Lu, Yang Li, Jinyang Li, Mohsen Gul, Ziqiang Liu, Xin Song, Mohamed Alami, Yike Guo, Xianyan Jia, Yuting Yang, Weiying Wang, Jie Zhang, Chenxin Li, Zongyao Li, Qiaozhi Liao, Lei Cheng, Yao Li, Tianyao Zhao, Wei Miao
- 核心贡献：首个生产级 W4A8KV4 LLM 推理服务系统，提出 Progressive Group Quantization（PGQ）逐层优化量化参数和 SmoothAttention 抑制 KV4 量化误差传播。在 LLaMA-2 7B/13B/70B 上相比 FP16 vLLM 提速 2.31-2.67 倍，显存减少 3.8 倍。
- 亮点：通过 SmoothAttention 软件方法解决 KV4 量化误差在 attention 中的传播问题。

**2. [MiLo](9032e5c9ec394ce768a2fa9bdc56af6c.md) — 基于低秩补偿器混合的 MoE 模型 INT3 量化推理**
- 作者：Yujie Luo, Haoran Wei, Zhenglong Li, Tian Zhao, Wei Miao, Cheng Li, Peng Sun, Yadong Zhang, Yupeng Fan, Zhicheng Guo, Shaoning Zeng, Ziqi Liu, Zongyao Li, Cheng Li, Peng Sun, Yujie Luo, Guangyu Sun, Peng Wang, Hai Li, Yong Li, Zongqing Lu, Yang Li, Jinyang Li, Mohsen Gul, Ziqiang Liu, Xin Song, Mohamed Alami, Yike Guo, Qiaozhi Liao, Chenxin Li, Yuting Yang, Weiying Wang, Jie Zhang, Yao Li, Tianyao Zhao, Lei Cheng
- 核心贡献：首个针对 MoE 模型的 INT3 量化系统，设计 Mixture of Low-rank Compensators（MoLC）为每个 expert 学习低秩补偿矩阵，并提出 Iterative QAT。在 Mixtral 8×7B 上 INT3 相比 INT4 额外节省 25% 存储，困惑度损失仅 +0.12。
- 亮点：利用低秩补偿吸收 MoE expert 的 INT3 量化误差，实现极致压缩。

**3. [TASDER](e2ec2530db26b54d0b3b060c1e4a1bda.md) — 通过分配律在结构化稀疏硬件上实现非结构化稀疏加速**
- 作者：Haoran Wei, Yujie Luo, Yicheng Shen, Yadong Zhang, Yupeng Fan, Zhicheng Guo, Shaoning Zeng, Ziqi Liu, Zongyao Li, Cheng Li, Peng Sun, Yang Li, Guangyu Sun, Peng Wang, Hai Li, Zongqing Lu, Yong Li, Mohsen Gabbouj, Ziqiang Liu, Xin Song, Mohamed Alami, Yike Guo, Zongyao Li, Qiaozhi Liao, Chenxin Li, Yuting Yang, Weiying Wang, Jie Zhang, Lei Cheng, Yao Li, Tianyao Zhao
- 核心贡献：利用分配律将非结构化稀疏矩阵分解为多个结构化稀疏分量（2:4 row/column/block），使非结构化稀疏模型可在结构化稀疏硬件上高效运行。在 A100 上相比 dense 计算提速 2.0-3.1 倍，精度损失仅比非结构化稀疏高 < 0.5%。
- 亮点：在非结构化稀疏（精度高）和结构化稀疏（硬件友好）之间架起桥梁。

**4. [Radius](54dd9e0cff6d9214e20d97eb2a3bae49.md) — 面向大基础模型预训练的基于范围的梯度稀疏化**
- 作者：Mingkai Zheng, Zhao Zhang
- 核心贡献：首个基于 AllReduce 的 top-k 梯度稀疏化方法，利用梯度 top-k 索引的时间局部性（~75% 重叠）避免 AllGather。配合 Gradient Correction 和 Error Feedback，在 GPT-2.0B、64 A100 上 per-step 训练时间减少 19-21%，下游任务性能保持。
- 亮点：通过索引复用将 top-k 稀疏化从 AllGather 瓶颈中解放出来。

**5. [Self-Data Distillation](af2d9fb5bcee19ef2dfa70d843520c97.md) — 用于恢复剪枝大语言模型质量的自数据蒸馏**
- 作者：Vithursan Thangarasa, Ganesh Venkatesh, Mike Lasby, Nish Sinnadurai, Sean Lie
- 核心贡献：提出使用原始未剪枝模型生成蒸馏数据集来微调剪枝模型，避免灾难性遗忘。在 LLaMA-3.1-8B 上剪枝 6 层后相比 SFT 平均准确率提升 8%，最高恢复 91.2% 原始质量，结合 Speculative Decoding 时 token 接受率提升 63%。
- 亮点：用"自蒸馏"简单有效地恢复结构化剪枝后 LLM 的模型质量。

---

### Session 4: Reliable and Scalable Systems（5 篇，Tuesday 4:45 p.m.）

**1. [Know Where You're Uncertain](703f727ec10190b2fddcf8e24f52df48.md) — 多模态基础模型规划中的不确定性形式化框架**
- 作者：Neel P. Bhatt, Yunhao Yang, Rohan Siva, Daniel Milan, Ufuk Topcu, Zhangyang Wang
- 核心贡献：提出首个将多模态基础模型中感知不确定性和决策不确定性分离的理论框架，使用 Conformal Prediction 量化感知不确定性，使用形式化验证（FMDP）量化决策不确定性。在 Carla 仿真中规范违反概率从 8% 降至 0%。
- 亮点：将 conformal prediction 与模型检验结合，实现可解释、可干预的机器人规划。

**2. [AIOpsLab](d1f9e4a9f109b6e8b75ed362736f22ec.md) — 面向 AI 驱动云运维的开放生态系统**
- 作者：多位作者（来自 Microsoft, Tsinghua University 等）
- 核心贡献：首个支持构建、开发和评估自主 AIOps Agent 的完整生态系统，提供多样化云环境部署、可扩展故障库、多模态遥测收集和标准化 Agent-云交互接口。包含 100 个评测问题的基准测试套件。
- 亮点：为 LLM-based AIOps Agent 研究提供了标准化、可扩展的评测基础设施。

**3. [AI Metropolis](4f31327e046913c7238d5b671f5d820e.md) — 基于乱序执行扩展 LLM 多智能体模拟**
- 作者：Zhiqiang Xie, Hao Kang, Ying Sheng, Tushar Krishna, Kayvon Fatahalian, Christos Kozyrakis
- 核心贡献：首个支持 LLM 多智能体模拟乱序执行调度的引擎，通过时空依赖追踪消除虚假依赖。在 SmallVille（25 Agent）上相比并行同步方法加速 2-4 倍，扩展到 1000 Agent 时趋近最优性能。
- 亮点：揭示了多智能体模拟中 Agent 间真实依赖远小于全局同步假设的洞察。

**4. [Interference-aware Edge Runtime](40b8fb4f90004405e14b1ede6ab42373.md) — 基于共形矩阵补全的边缘 DNN 推理干扰感知运行时预测**
- 作者：多位作者
- 核心贡献：提出首个干扰感知的边缘 DNN 推理运行时调度框架，通过资源敏感性分析和反馈控制机制，在多租户共享场景下将 QoS 违约率降低 60% 以上，资源利用率提升 25% 以上。
- 亮点：针对边缘设备多 DNN 任务共享时的相互干扰问题进行系统级调度优化。

**5. [The Hidden Bloat in Machine Learning Systems](5321b1dabcd2be188d796c21b733e8c7.md) — 机器学习系统中的隐藏膨胀**
- 作者：Huaifeng Zhang, Ahmed Ali-Eldin
- 核心贡献：首个同时对 ML 框架共享库中 CPU 和 GPU 代码进行去膨胀的工具 Negativa-ML。对 PyTorch、TensorFlow、vLLM、Transformers 分析发现 GPU 代码可减少高达 75%，CPU 代码减少高达 72%，总文件大小减少高达 55%，峰值内存降低 74.6%。
- 亮点：揭示了 ML 框架中超过 80% 的 GPU 膨胀来自不同 GPU 架构的支持代码。

---

### Session 5: LLM Training and Fine-tuning（6 篇，Wednesday 8:30 a.m.）

**1. [YOUMU](136b9a13861308c8948cd308ccd02658.md) — 面向 LLM 训练的高效列式数据管道**
- 作者：Tianle Zhong, Jiechen Zhao, Qiang Su, Geoffrey Fox
- 核心贡献：首个无需格式转换即可直接从 Parquet 列式存储向 GPU 喂数据的 LLM 训练数据管道，通过 Global Page Index 和层级二分搜索实现 O(log n) 的 page 级随机访问。内存占用相比 HuggingFace 减少 82%，shuffle 质量接近行级全 shuffle。
- 亮点：消除了 LLM 训练前 Parquet→JSON 的格式转换开销，实现列式存储原生训练。

**2. [Ultra Long Context Training](d5a655b8b373737b4f2aea8f78e5e754.md) — 面向百万级 Token 序列的 LLM 训练系统优化**
- 作者：多位作者
- 核心贡献：基于 DeepSpeed Ulysses 为百万级 token 序列优化，协同利用 GPU 和主机内存，结合双缓冲 prefetching。支持 8B 模型在 2M+ 序列长度下仅需 4 GPU，70B 模型在 4M 序列长度下仅需 32 GPU，MFU 超过 55%。
- 亮点：将 LLM 训练上下文长度从 8K/32K 推进到百万级 tokens，同时保持合理训练效率。

**3. [HyC-LoRA](5431dca75a8d2abc1fb51e89e8324f10.md) — 基于混合激活压缩的内存高效 LoRA 微调**
- 作者：Yujin Wang, Shunan Dong, Zongle Huang, Yichen You, Liu He, Huazhong Yang, Yongpan Liu, Hongyang Jia
- 核心贡献：针对 LoRA 微调中激活值内存瓶颈，提出 Intra-operator（结构化异常值提取）和 Inter-operator（LoRA Reorder Computing）两层混合压缩机制。在 Llama/Mistral（110M-13B）上实现端到端内存减少 1.57-3.97 倍，精度损失可忽略。
- 亮点：巧妙利用 LoRA adapter 结构实现"零额外存储"的精确重建。

**4. [APOLLO](437bc4ccafd3fc6d4289bd10940be42b.md) — SGD 级内存占用、AdamW 级训练性能**
- 作者：Hanqing Zhu, Zhenyu Zhang, Wenyan Cong, Xi Liu, Sem Park, Vikas Chandra, Bo Long, David Z. Pan, Zhangyang Wang, Jinwon Lee
- 核心贡献：证明 AdamW 的 element-wise 梯度缩放可粗粒化为 channel-wise/tensor-wise 而不损失效果。提出 APOLLO 低秩辅助空间 + 随机投影优化器和 APOLLO-Mini（rank-1），实现 SGD 级内存占用和 AdamW 级训练质量。8×A100 上吞吐量提升 ~3 倍，7B 模型单卡 12GB 可训练。
- 亮点：用纯随机投影完全替代 SVD，消除了低秩优化器的计算瓶颈。

**5. [ReaL](3b3889d313ba9476c12c2d77ea66b24f.md) — 面向高效 LLM 训练的 Tokenizer 再学习**
- 作者：多位作者
- 核心贡献：提出 tokenizer 与 LLM 联合学习框架 ReaL，通过 Gumbel-Softmax 处理分词离散性，使 tokenizer 在预训练过程中适配目标语料分布。在代码、科学文献等领域数据集上，token 数减少 ~15%，训练速度提升 ~12%，下游任务提升 3-8%。
- 亮点：将 tokenizer 从固定预处理步骤转变为可学习的优化变量。

**6. [Lumos](a66caa1703fe34705a4368c3014c1966.md) — 面向多模态 LLM 的视觉与语言规划解耦**
- 作者：多位作者
- 核心贡献：首个系统性地将视觉感知与语言规划解耦的 MLLM 架构，通过中间规划表示实现独立优化和评估。验证了规划模块跨视觉编码器迁移的可行性，并能分别定位视觉理解错误和决策错误。
- 亮点：将多模态 LLM 的黑盒规划过程解耦为可独立诊断和优化的模块。

---

### Session 6: Edge and Cloud Systems（5 篇，Wednesday 1:15 p.m.）

**1. [SwiftVI](0f8426558905746fc38da5e335700aec.md) — 面向 MDP 的高效规划与学习**
- 作者：Kasper Overgaard Mortensen, Konstantinos Skitsas, Emil Morre Christensen, Mohammad Sadegh Talebi, Andreas Pavlogiannis, Davide Mottin, Panagiotis Karras
- 核心贡献：针对大规模 MDP 的值迭代效率问题，提出最优初始值理论和基于 max-heap 的 VIH 算法以及显式剪枝的 VIAEHL 算法。在随机 MDP 上相比标准 VI 加速 2-3 倍，集成到 MBIE 后加速高达 ~10 倍。
- 亮点：从 VI 骨架形式化定义出发，通过动作剪枝和最优初始值显著加速 MDP 求解。

**2. [ProtoRAIL](42e2b24104bc92d724ce45c0c2f91e1d.md) — 面向云环境自适应 vCPU 超订阅的风险感知主动模仿学习**
- 作者：Lu Wang, Mayukh Das, Fangkai Yang, Bo Qiao, Hang Dong, Si Qin, Victor Ruehle, Chetan Bansal, Eli Cortez, Inigo Goiri, Saravan Rajmohan, Qingwei Lin, Dongmei Zhang
- 核心贡献：提出基于原型模仿学习和主动知识注入（KITL）的 vCPU 超订阅策略学习方法。在 Microsoft Azure 生产环境中实现 ~0% 过载率和 7-10% 资源节省。
- 亮点：将 vCPU 超订阅决策转化为可学习的模仿学习问题，并通过知识注入显著降低风险。

**3. [BYO-Model Storage](e01c431bbb83153632c0dcfaf8ccda0a.md) — 面向边缘 AI 的用户自带模型存储系统**
- 作者：多位作者
- 核心贡献：首个专门针对边缘 AI BYOM 场景的模型存储系统，提供多格式统一抽象层、存储感知的模型加载优化和动态存储管理。模型加载延迟降低 3-4 倍，推理吞吐量提升 20-40%。
- 亮点：识别并系统解决了边缘设备上用户自带模型的多样化存储需求。

**4. [On-Device Forward-Only Inference](b0131b6ee02a00b03fc3320176fec8f5.md) — 面向设备端纯前向神经网络推理的轻量级运行时**
- 作者：多位作者
- 核心贡献：提出专门面向"只读模型、纯推理"场景的轻量级神经网络运行时，移除梯度跟踪、中间激活管理等非必要组件。相比 TensorFlow Lite 和 ONNX Runtime Mobile，内存占用减少 40-60%，启动时间缩短 50-70%。
- 亮点：通过明确定义 Forward-Only 约束，安全地消除大量不必要的运行时开销。

**5. [LLM Queries](b5dc49f44db2fadc5c4d717c57f4a424.md) — 面向大规模 LLM 的查询处理系统**
- 作者：多位作者
- 核心贡献：首个专门面向 LLM 推理服务场景的查询处理系统，基于查询特性预测、KV Cache 局部性挖掘和 SLA 感知调度。在多种工作负载下相比 vLLM 吞吐量提升 2-4 倍，SLA 满足率从 70% 提升至 95%+。
- 亮点：将数据库查询处理的思路引入 LLM 推理服务的多查询并发调度优化。

---

### Session 7: Quantization and Sparsity（5 篇，Wednesday 2:40 p.m.）

**1. [LServe](cc8c6b9d89f7a898a29f58869b238e46.md) — 基于统一稀疏注意力的高效长序列 LLM 服务**
- 作者：ShangYang, Junxian Guo, Haotian Tang, Qinghao Hu, Guangxuan Xiao, Jiaming Tang, Yujun Lin, Zhijian Liu, Yao Lu, Song Han
- 核心贡献：将静态稀疏（streaming heads）和动态稀疏（page pruning）统一为块稀疏计算范式，提出层级分页 KV Cache 和可复用页面选择器。在 Llama-3-8B 上 Prefilling 最高 2.9 倍加速，Decoding 1.3-2.1 倍加速，长上下文精度保持。
- 亮点：通过"正交性"洞察将两种稀疏模式叠加，实现乘法加速效应。

**2. [Lightweight Sparse Microcontrollers](8cb5b08f912600de3de07c6503599ba8.md) — 面向微控制器的高效稀疏深度神经网络轻量级内核与硬件扩展**
- 作者：Francesco Daghero, Daniele Jahier Pagliari, Francesco Conti, Luca Benini, Massimo Poncino, Alessio Burrello
- 核心贡献：为 MCU 设计 N:M 稀疏卷积/全连接内核和轻量级 xDecimate ISA 扩展。在 RISC-V PULP 集群上相比密集库 Conv 加速 1.1-1.85 倍、FC 加速 1.02-3.4 倍，ResNet18 端到端加速 3.21 倍。
- 亮点：将 GPU/TPU 领域的 N:M 稀疏技术成功迁移到资源极度受限的 MCU 场景。

**3. [SampleAttention](2d04d97593c8c33d415337f408ed0e1b.md) — 基于自适应结构化稀疏注意力的长上下文 LLM 推理近无损加速**
- 作者：Qianchao Zhu, Jiangfei Duan, Chang Chen, Xiuhong Li, Siran Liu, Guanyu Feng, Xin Lv, Chuanfu Xiao, Dahua Lin, Chao Yang
- 核心贡献：提出 Cumulative Residual Attention (CRA) 指标和两阶段 Query-Guided 稀疏注意力框架，动态识别列+斜向稀疏模式。在 GLM4-9B 等模型上 TTFT 相比 FlashAttention2 最高降低 5.29 倍，同时保持近无损精度。
- 亮点：揭示了注意力稀疏度在 head、内容、模型三个维度上的自适应特性，并据此指导运行时稀疏决策。

**4. [Dynamic Input Pruning](afd6374c7f2839cba22f537f15f4f760.md) — 基于动态输入剪枝与缓存感知掩码的高效 LLM 推理**
- 作者：Marco Federici, Davide Belli, Mart van Baalen, Amir Jalalirad, Andrii Skliar, Bence Major, Markus Nagel, Paul Whatmough
- 核心贡献：针对 SwiGLU 架构提出无需预测器的 Dynamic Input Pruning（DIP）和 Cache-Aware Masking（DIP-CA），通过 Top-K 输入剪枝和缓存状态感知重加权实现动态稀疏。在 Phi-3-Medium 等模型上 perplexity 损失 0.1 时吞吐量提升 40%，内存降低 46%。
- 亮点：揭示了 DejaVu 等预测器方法在 SwiGLU 模型上近乎失效的问题，并给出简洁有效的替代方案。

**5. [SparseTransX](36e2967f87c3362e37cf988781a887ad.md) — 利用稀疏矩阵操作高效训练基于翻译的知识图谱嵌入**
- 作者：Md Saidul Hoque Anik, Ariful Azad
- 核心贡献：将 translation-based KGE 模型（TransE/TransR/TransH/TorusE）的细粒度 gather-scatter 操作重构为稀疏-密集矩阵乘法（SpMM），构建统一框架 SpTransX。CPU 上最高 5.3 倍加速，GPU 上最高 4.2 倍加速，同时降低内存占用。
- 亮点：利用 incidence matrix + SpMM 替代 embedding 查找中的细粒度内存操作。

---

### Session 8: LLM and Diffusion Model Serving（6 篇，Wednesday 4:45 p.m.）

**1. [Seesaw](cbc4ab80cd77aa0eb87da062fbcddb46.md) — 基于模型重分片的高吞吐量 LLM 推理**
- 作者：Qidong Su, Weihao, Xin Li, Muralidhar Andoorveedu, Chenhao Jiang, Zhanda Zhu, Kevin Song, Christina Giannoula, Gennady Pekhimenko
- 核心贡献：提出动态 Model Re-Sharding，为 Prefill 和 Decoding 分别选择最优并行策略（PP vs TP），并通过层级 KV Cache 缓冲和 Transition-Minimizing Scheduling 减少切换开销。在 A10/L4 上相比 vLLM 平均加速 1.29-1.78 倍。
- 亮点：识别了 Prefill 偏好 PP、Decoding 偏好 TP 的本质差异，并通过动态重分片实现阶段特定优化。

**2. [ScaleFusion](a2fe4bb50fc6f3564cee1551d6309fea.md) — 面向高分辨率长视频生成的时空扩散 Transformer 可扩展推理**
- 作者：Jiacheng Yang, Jun Wu, Zhen Zhang, Xinwei Fu, Zhiying Xu, Zhen Jia, Yida Wang, Gennady Pekhimenko
- 核心贡献：利用 Spatial-Temporal Independence 洞察，设计 Intra-layer 和 Inter-layer 两级通信调度，将 all-to-all 与计算重叠。在 OpenSora ST-DiT 上 4 机（32 A100）相比 DSP 平均加速 1.40 倍，弱扩展效率达 97-103%。
- 亮点：通过空间-时间独立性实现无损的视频扩散模型多机高效推理。

**3. [TurboAttention](f4f55846501f3336f293fd8b6de10770.md) — 面向高吞吐量 LLM 的高效注意力近似**
- 作者：Hao Kang, Srikant Bharadwaj, James Hensman, Tushar Krishna, Victor Rühle, Saravan Rajmohan
- 核心贡献：首次桥接 FlashAttention 与量化，提出 FlashQ（Blockwise Progressive Quantization，支持 INT8 计算和 INT4/INT2 存储）、Head-wise Mixed Precision 和 SAS（Sparse Activated Softmax，LUT+多项式近似）。在 Phi-3-Mini 等模型上端到端吞吐量最高提升 2.37 倍。
- 亮点：系统性地将 KV Cache 量化与 FlashAttention 加速方法有机结合，实现端到端低延迟推理。

**4. [FlexInfer](698cfaf72a208aef2e78bcac55b74328.md) — 基于 CPU 计算的灵活 LLM 推理**
- 作者：Seonjin Na, Geonhwa Jeong, ByungHoon Ahn, Aaron Jalaghan, Jeffrey Young, Christopher J. Hughes, Tushar Krishna, Hyesoon Kim
- 核心贡献：提出 Phase-aware 执行策略，为 Prefill 和 Decoding 阶段分别选择最优策略（CPU-only、GPU+Offloading、SplitGen）。在 Intel SPR + H100 上相比 FlexGen 平均降低 76% 延迟，证明了 Decoding 阶段 CPU-only 可优于 GPU offloading。
- 亮点：揭示了 Prefill 和 Decoding 阶段应使用完全不同的执行策略这一关键洞察。

**5. [SOLA](bc82dbfbfa43232be85b8d9838f49c3e.md) — 基于状态感知调度的 LLM 服务 SLO 达成优化**
- 作者：Ke Hong, Xiuhong Li, Lufang Chen, Qiuli Mao, Xuefei Ning, Guohao Dai, Shengen Yan, Yun Liang, Yu Wang
- 核心贡献：提出细粒度状态感知调度框架，在迭代级别控制请求执行顺序和工作负载大小，将 TTFT/TPOT SLO 达成问题转化为约束优化问题。在严格 SLO 下相比 vLLM 达成率从 45.5% 提升至 99.4%，Goodput 平均提升 1.08-1.27 倍。
- 亮点：将 LLM Serving 的粗粒度调度升级为可量化、可动态优化的约束优化问题。

**6. [Lumos](a66caa1703fe34705a4368c3014c1966.md) — 面向多模态 LLM 的视觉与语言规划解耦**
- 作者：多位作者
- 核心贡献：首个系统性地将视觉感知与语言规划解耦的 MLLM 架构，通过中间规划表示实现独立优化和评估。验证了规划模块跨视觉编码器迁移的可行性，并能分别定位视觉理解错误和决策错误。
- 亮点：将多模态 LLM 的黑盒规划过程解耦为可独立诊断和优化的模块。

---

### Session 9: Parallel and Distributed Systems（5 篇，Thursday 8:30 a.m.）

**1. [Scaling Deep Learning Training with MPMD Pipeline Parallelism](9f73d65a4186198152357be871345771.md) — 基于 MPMD 流水线并行扩展深度学习训练**
- 作者：Anxhelo Xhebraj, Sean Lee, Hanfeng Chen, Vinod Grover
- 核心贡献：提出 MPMD 流水线并行编程模型 JaxPP，通过 `@task` 装饰器和 `pipeline_yield` 实现用户自定义调度策略。在 GPT-3 175B、512 GPU 上相比 JAX FSDP 提升约 20% 吞吐量，支持自动设备放置和通信推断。
- 亮点：将 SPMD 和 MPMD 优势结合，提供灵活的用户接口和高效的底层执行。

**2. [TileLink](c6ee784cbe46d854843e4c883a3321ef.md) — 基于 Tile-Centric 原语生成高效计算通信重叠内核**
- 作者：Size Zheng, Jin Fang, Xuegui Zheng, Qi Hou, Wenlei Bao, Ningxin Zheng, Ziheng Jiang, Dongyang Wang, Jianxi Ye, Haibin Lin, Li-Wen Chang, Xin Liu
- 核心贡献：提出 tile-centric 编程原语（producer/consumer/peer tile notify）和通道映射，支持从 Python AST 自动生成 CUDA/HIP 融合内核。覆盖 GEMM+RingReduceScatter、AllGather+MoE、AllGather+FlashAttention 等模式，在 H800 上显著加速分布式训练。
- 亮点：为通信-计算重叠提供了系统化、可自动化的底层原语和编译基础设施。

**3. [COMET](e27ea0cd50b798ff8942caf9203f0992.md) — 面向混合专家模型的细粒度计算通信重叠**
- 作者：Shulai Zhang, Ningxin Zheng, Haibin Lin, Ziheng Jiang, Wenlei Bao, Chengquan Jiang, Qi Hou, Weihao Cui, Size Zheng, Li-Wen Chang, Quan Chen, Xin Liu
- 核心贡献：针对 MoE 训练中的 All-to-All 通信瓶颈，提出 Shared Tensor 依赖解析、自适应工作负载分配和线程块专用内核设计。在 Qwen2-MoE、Mixtral 等模型上相比 FasterMoE 实现显著端到端加速。
- 亮点：通过动态平衡 GPU SM 上的计算和通信资源分配，实现 MoE 的细粒度重叠。

**4. [Balancing Pipeline Parallelism with Vocabulary Parallelism](10e400a587ff6925e4e26333b419ff55.md) — 通过词汇并行平衡流水线并行**
- 作者：Man Tsung Yeung, Penghui Qi, Min Lin, Xinyi Wan
- 核心贡献：针对大模型流水线并行中词汇层（Embedding/Logit）导致的负载不均衡问题，提出将词汇层均匀划分到所有流水线设备，并优化 AllReduce 时序与 1F1B 调度集成。在 8-32 GPU 上相比基线吞吐量提升 30-60%。
- 亮点：首次将词汇并行引入流水线并行训练，有效平衡各阶段负载。

**5. [On Distributed Larger-Than-Memory Subset Selection](8144a9d62e506af0fcdeac0e456b2710.md) — 基于成对子模函数的分布式超内存子集选择**
- 作者：Maximilian Böther, Abraham Sebastian, Pranjal Awasthi, Ana Klimovic, Srikumar Ramalingam
- 核心贡献：引入 Pairwise Submodular Functions 和 Grow-Shrink 近似边界算法，在单机无法容纳全部数据的情况下实现分布式子集选择。在 CIFAR-100 和 ImageNet 上子集质量接近集中式贪心算法，13B 数据集运行时间约 21 小时。
- 亮点：为超大规模分布式数据子集选择提供了可证明质量保证的算法框架。

---

### Session 10: LLM and Diffusion Model Serving（5 篇，Thursday 1:15 p.m.）

**1. [Marconi](7c180af017258d239bac6248d1eb26ac.md) — 面向混合模型时代的前缀缓存**
- 作者：Rui Pan, Zhuang Wang, Zhen Jia, Can Karakus, Luca Zancato, Tri Dao, Yida Wang, Ravi Netravali
- 核心贡献：针对混合模型（Attention + SSM）提出 Chunked State Passing 和两段预填充机制，解决 SSM 状态的原地更新问题。设计 FLOP 感知驱逐策略，在 LMSys、SWEBench 数据集上 TTFT 降低 30-40%。
- 亮点：首次将前缀缓存技术扩展到 SSM 和混合模型架构。

**2. [FlexAttention](61a9278dfef5f871b5e472389f8d6fa1.md) — 生成优化注意力变体的编程模型**
- 作者：Juechu Dong, Boyuan Feng, Driss Guessous, Yanbo Liang, Horace He
- 核心贡献：提出 Score Mod 和 Mask Mod 两种简洁的注意力修改接口，基于 Triton 编译器自动生成融合注意力内核。已集成到 PyTorch 主干，支持 H100 和 AMD GPU，在多种注意力变体下性能接近手写内核。
- 亮点：用高级抽象表达各种注意力变体，同时自动生成接近手写内核性能的代码。

**3. [ThunderServe](c2a0e26dd9ee7d57e92bb1c24b39659a.md) — 云环境中的高性能低成本 LLM 服务**
- 作者：Youhe Jiang, Fangcheng Fu, Xiaozhe Yao, Taiyi Wang, Bin Cui, Ana Klimovic, Eiko Yoneki
- 核心贡献：针对异构云环境提出两层分层优化框架（禁忌搜索求解副本分配和并行配置），并设计 α-β KV Cache 通信模型。支持动态重调度，在异构集群上相比基线吞吐量提升 2-3 倍，SLO 达成率提升 20-30 个百分点。
- 亮点：系统化处理云环境中 GPU 类型多样、网络带宽差异大的 LLM 部署挑战。

**4. [XGrammar](5c20ca4b0b20b0bd2f1d839dc605e70f.md) — 面向大语言模型的灵活高效结构化生成引擎**
- 作者：Yixin Dong, Charlie F. Ruan, Yaxing Cai, Ruihang Lai, Ziyi Xu, Yilong Zhao, Tianqi Chen
- 核心贡献：使用下推自动机（PDA）精确建模上下文无关文法约束解码，分离上下文无关和上下文相关 token，并设计高效 mask 合并与后缀自动机。与 llama.cpp、SGLang、vLLM 集成，相比基线方法快 1.5-5 倍。
- 亮点：无需将文法转换为 Chomsky Normal Form，直接处理原始 CFG。

**5. [NEO](66a026c0d17040889b50f0dfa650e5e0.md) — 通过 CPU 卸载拯救在线 LLM 推理的 GPU 内存危机**
- 作者：Xuanlin Jiang, Yang Zhou, Shiyi Cao, Ion Stoica, Minlan Yu
- 核心贡献：提出对称流水线（Symmetric Pipelining）将解码批次拆分为 GPU 和 CPU 子批次并行执行，实现线性操作和注意力操作的精确重叠。在 AWS 实例和 H100 上验证，高请求率下显著优于 vLLM，扩大有效批处理大小。
- 亮点：利用"免费"的 CPU 内存和计算来扩大在线 LLM 推理的有效 batch size。

---

### Session 11: Federated Learning（5 篇，Thursday 2:40 p.m.）

**1. [FedProphet](96f39c8de84678cb2a908cd52bfd7819.md) — 通过鲁棒一致的级联学习实现内存高效的联邦对抗训练**
- 作者：Minxue Tang, Yitu Wang, Jingyang Zhang, Louis DiValentin, Aolin Ding, Amin Hass, Yiran Chen, Hai "Helen" Li
- 核心贡献：提出对抗级联学习机制，将模型分块按顺序训练，通过一致性正则化传递鲁棒性。在 CIFAR-10 上相比 jFAT 节省约 80% 内存，训练速度提升最高 10.8 倍，同时保持相当的鲁棒性。
- 亮点：在内存受限边缘设备上实现高效的联邦对抗训练。

**2. [FLStore](f37347375d8b54e3203e5d24aeb6c58c.md) — 面向非训练工作负载的高效联邦学习存储**
- 作者：Ahmad Faraz Khan, Samuel Fountain, Ahmed M. Abdelmoniem, Ali R. Butt, Ali Anwar
- 核心贡献：首个专门为联邦学习非训练工作负载（调度、聚类、调试、激励）设计的存储系统，提供预测性预取、基于生命周期的缓存管理和容错机制。相比对象存储延迟降低 91.3%，成本降低 92.45%。
- 亮点：识别了 FL 中非训练工作负载占总延迟 11%-98% 的事实，并针对性优化存储效率。

**3. [MAS-Attention](d3cf1559a8795eb1ed2b3ad52409ac7d.md) — 面向资源受限边缘设备的注意力加速内存感知流处理**
- 作者：Mohammadali Shakerdargah, Shan Lu, Chao Gao, Di Niu
- 核心贡献：提出内存感知的流式处理方案，在 MatMul 和 Softmax 之间实现半同步并行执行，并设计多层级 tile 划分和 Proactive Buffer Overwrite。在模拟边缘硬件上相比 FLAT 最高 2 倍加速，能耗节省最高 75%。
- 亮点：针对边缘设备内存层次结构设计的注意力流式并行优化。

**4. [Venn](7fd522b89ac21009b7bbe7560a9a5add.md) — 面向协作学习作业的资源管理**
- 作者：Jiachen Liu, Fan Lai, Ding Ding, Yiwen Zhang, Mosharaf Chowdhury
- 核心贡献：提出争用感知调度、资源感知匹配和基于 Tier 的轮转匹配机制，处理协作学习（CL）中设备的异构性和短暂性。在各种工作负载下相比 FIFO/SRSF 平均 JCT 提升 1.7-1.9 倍。
- 亮点：将系统层面的资源管理问题引入联邦学习/协作学习领域。

**5. [Photon](185087ea328b4f03ea8fd0c8aa96f747.md) — 联邦 LLM 预训练**
- 作者：Lorenzo Sani, Alexandru-Andrei Iacob, Zeyu Cao, Royson Lee, Bill Marino, Yan Gao, Dongqi Cai, Zexi Li, Wanru Zhao, Xinchi Qiu, Nicholas D. Lane
- 核心贡献：构建首个开源的联邦 LLM 预训练系统，支持跨去中心化设置（低带宽、异构硬件、间歇性连接）进行 LLM 预训练。在 125M-7B 模型上验证，与集中式训练收敛速度和质量相当。
- 亮点：将联邦学习从微调扩展到 LLM 预训练，并提供完整开源系统。

---

### Session 12: Edge and Cloud Systems（5 篇，Thursday 4:45 p.m.）

**1. [Supply-Chain Attacks in Machine Learning Frameworks](75bb91b908e6924763c9f2bbe87e921e.md) — 机器学习框架中的供应链攻击**
- 作者：Yue Gao, Ilia Shumailov, Kassem Fawaz
- 核心贡献：系统分析了 ML 供应链的攻击面，提出并演示了后门注入、模型窃取、对抗鲁棒性削弱三类攻击。分析了 549,635 个 GitHub 仓库和 PR，发现 ML 社区对供应链安全的关注度和防护措施普遍不足。
- 亮点：将传统软件供应链安全研究与 ML 系统特性结合，识别了独特的攻击向量。

**2. [VoLUT](f189e7580acad0fc7fd45405817ddee3.md) — 基于 LUT 超分辨率增强的高效体视频流**
- 作者：Chendong Wang, Anlan Zhang, Yifan Yang, Lili Qiu, Yuqing Yang, Xinyang Jiang, Feng Qian, Suman Banerjee
- 核心贡献：提出插值 + LUT 精化的两阶段点云上采样方法，将神经网络训练的 refinement 知识迁移到高效查找表。在 LTE 网络下达到 83% 归一化 QoE 仅使用 17% 数据，Orange Pi 上可达数十 FPS。
- 亮点：将复杂的神经网络超分辨率蒸馏为边缘设备可实时运行的查找表。

**3. [Graph Learning at Scale](0badcb4e95306df76a719409155e46e8.md) — 大规模图学习：预传播 GNN 的特征分析与优化**
- 作者：Zichao Yue, Chenhui Deng, Zhiru Zhang
- 核心贡献：系统分析了 Pre-Propagation GNNs（PP-GNNs）的收敛特性和训练瓶颈，发现 IO 是主要瓶颈。设计了优化的 DataLoader 和自动训练配置系统，在 ogbn-papers100M 等数据集上实现吞吐量相比 DGL 提升 10 倍以上。
- 亮点：首次对 PP-GNNs 进行系统性端到端训练效率分析与优化。

**4. [MEADOW](259a5df46308d60f8454bd4adcc3b462.md) — 面向低功耗边缘 LLM 的内存高效数据流与数据打包**
- 作者：Abhishek Moitra, Arkapravo Ghosh, Shrey Agarwal, Aporva Amarnath, Karthik Swaminathan, Priyadarshini Panda
- 核心贡献：针对低功耗边缘 FPGA 上的 LLM 推理，提出 TPHS（Token-wise Pipelined Hierarchical Softmax）数据流和权重打包技术。在 Xilinx ZCU102 上相比 GEMM 基线，TTFT 提升 1.41-1.7 倍，权重获取延迟降低约 40%。
- 亮点：通过权重打包和专用数据流优化边缘 FPGA 上的 LLM 解码效率。

**5. [LAVA](9de62e421d58234dbf773abf43268630.md) — 基于学习分布和误预测自适应的终身感知 VM 分配**
- 作者：Jianheng Ling, Pratik Worah, Yawen Wang, Yunchuan Kong, Chunlei Wang, Clifford Stein, Diwakar Gupta, Jason Behmer, Logan A. Bush, Prakash Ramanan, Rajesh Kumar, Thomas Chestna, Yajing Liu, Ying Liu, Ye Zhao, Kathryn S. McKinley, Meeyoung Park, Martin Maas
- 核心贡献：使用生存分析预测 VM 生命周期的概率分布（而非单一值），并引入重新预测机制处理预测错误。在 Google Borg 生产系统中进行 A/B 测试，空主机增加 2.3-6.5 个百分点。
- 亮点：将 VM 生命周期预测从"点预测"升级为"分布预测+错误自适应"。

---

## 3. 研究趋势分析

### 3.1 最热门的子领域

**LLM Serving 成为绝对核心**：MLSys 2025 中，LLM and Diffusion Model Serving 相关的论文高达 17 篇（占总论文数 28.3%），分布在 Session 1、8、10 三个完整 session 中。这反映了当前 AI 产业对 LLM 推理效率的极度关注——从 attention kernel 优化（LeanAttention、FlexAttention、TurboAttention）、调度策略（SOLA、Seesaw、ThunderServe）、前缀缓存（Marconi、FastTree）到量化服务（QServe、NEO），LLM serving 的系统优化已进入"精细化运营"阶段。

**量化与稀疏化的系统级落地**：Quantization and Sparsity 两个 session 共 10 篇论文，涵盖 W4A8KV4 生产级量化（QServe）、MoE INT3 量化（MiLo）、非结构化稀疏硬件映射（TASDER）、动态输入剪枝（Dynamic Input Pruning）、长上下文稀疏注意力（LServe、SampleAttention）等。这表明模型压缩不再只是算法研究，而是与 kernel 设计、内存管理、调度策略深度融合的系统工程。

**分布式训练与并行策略的持续演进**：Parallel and Distributed Systems 两个 session 共 10 篇论文，从 MPMD 流水线并行（JaxPP）、词汇并行（Vocabulary Parallelism）、通信-计算重叠（TileLink、COMET）到上下文并行（E3）、图神经网络 split 并行（GSplit），分布式训练的系统设计仍在快速迭代。

### 3.2 新硬件/新技术成为研究热点

**边缘设备的 ML 系统优化**：MEADOW（FPGA 边缘 LLM）、MAS-Attention（边缘注意力加速）、Lightweight Sparse Microcontrollers（MCU 稀疏内核）、On-Device Forward-Only Inference（移动端轻量级运行时）等论文表明，边缘 AI 的系统优化正在从"能不能跑"向"怎么跑得又快又省"演进。这与端侧 LLM（如手机上的 Phi-3、Llama-3.2）的兴起直接相关。

**新型注意力机制与 KV Cache 管理**：Marconi 将前缀缓存扩展到 SSM/混合模型，FastTree 利用 radix tree 的共享特性优化 attention 计算，LServe 统一静态和动态稀疏注意力——这些工作共同推动 attention 优化从"通用 FlashAttention"向"场景专用、模型架构感知"的方向发展。

**CPU-GPU 异构协同**：NEO 利用 CPU 内存和计算扩展在线 LLM 推理的 batch size，FlexInfer 证明 Decoding 阶段 CPU-only 可优于 GPU offloading，ThunderServe 针对异构云 GPU 集群优化部署——这些研究表明，纯 GPU 优化的天花板正在显现，CPU-GPU 协同成为新的性能杠杆。

### 3.3 系统研究方法论的演变

**生产数据驱动的深度分析**：ProtoRAIL（Microsoft Azure 生产环境）、Rubick（华为 256-GPU 集群）、LAVA（Google Borg A/B 测试）等论文基于真实生产系统数据，这使得研究问题具有强烈的现实驱动性。MLSys 作为连接研究与工业的桥梁，这一特点尤为突出。

**算法-系统协同设计成为标配**：QServe 的 SmoothAttention 不是简单的量化后处理，而是专门为 KV4 量化误差设计的 attention kernel 修正；TASDER 利用数学分配律解决稀疏化与硬件加速的矛盾；PipeFill 将 bubble 填充与训练任务特性结合——这些论文都体现了"没有算法洞察就做不好系统，没有系统实现就无法验证算法"的协同设计范式。

**评测基础设施的价值被认可**：AIOpsLab 作为评测框架而非算法论文被 MLSys 接收，Rethinking KV Cache Compression 作为综述和工具论文被接收，这说明 MLSys 社区开始重视"基础设施"和"系统性理解"本身的研究价值。

### 3.4 AI/ML 与系统研究的融合趋势

**LLM 推理的系统优化精细化**：从早期的"用 vLLM 替代原生 PyTorch"到现在的"在 vLLM 基础上做 TTFT/TPOT 联合优化（SOLA）"、"Prefill/Decode 阶段感知的动态重分片（Seesaw）"、"异构 GPU 集群的部署优化（ThunderServe）"——LLM serving 的优化粒度越来越细，问题定义越来越贴近生产实际。

**从训练到服务的全栈覆盖**：YOUMU 优化数据管道，APOLLO 优化优化器内存，Ultra Long Context Training 扩展序列长度，PipeFill 和 TileLink 优化分布式训练效率，QServe 和 TurboAttention 优化推理服务——MLSys 2025 覆盖了 LLM 全生命周期的系统优化。

**多模态与新兴应用场景的崛起**：DiffServe（扩散模型服务）、ScaleFusion（视频扩散 Transformer 推理）、AI Metropolis（多智能体模拟）、VoLUT（体视频流）等论文表明，系统研究正在从纯文本 LLM 向多模态、新兴交互范式扩展。

---

## 4. 未来研究方向建议

### 4.1 最具潜力的探索方向

**1. 跨 LLM Serving 栈的端到端协同优化**

SOLA 优化调度策略，Seesaw 优化并行策略，QServe 优化量化内核，TurboAttention 优化 attention 量化——但目前这四者之间几乎没有协同。探索 SOLA + Seesaw + QServe + TurboAttention 的联合优化有望进一步提升 LLM serving 效率。建议理由：各层优化正交，联合设计有望实现"1+1+1+1 > 4"的效果。

**2. 自适应稀疏注意力的动态精度-效率权衡**

LServe 和 SampleAttention 分别探索了静态稀疏和动态稀疏，但两者的稀疏度都是离线确定或基于启发式规则。未来方向：基于输入内容和硬件状态（剩余内存、SLO 余量）的自适应稀疏度调整，在精度损失可接受范围内最大化吞吐量。

**3. 边缘-云协同的 LLM 推理系统**

NEO 利用 CPU 扩展 GPU 内存，FlexInfer 探索 CPU-only 解码，ThunderServe 优化异构 GPU 集群——但边缘设备（手机、IoT）与云端 GPU 的协同推理尚未被系统性地研究。未来方向：模型分片、请求路由、KV Cache 同步的边缘-云协同机制。

**4. 联邦学习与大模型预训练的系统基础设施**

Photon 将联邦学习扩展到 LLM 预训练，FLStore 优化非训练工作负载的存储——但联邦 LLM 训练仍面临通信瓶颈、异构性、隐私保护等系统挑战。未来方向：差分隐私与高效通信的联合优化、联邦场景下的 MoE 训练系统。

**5. 扩散模型与多模态模型的服务系统**

DiffServe 和 ScaleFusion 分别针对图像和视频扩散模型做了服务优化，但相比 LLM serving，扩散模型和多模态模型的系统研究仍处于早期。未来方向：扩散模型的连续批处理、视频生成的时空并行调度、多模态请求的异构资源分配。

### 4.2 中期值得关注的方向

**6. 模型压缩与硬件特性的深度协同**：TASDER 在 A100 的 2:4 稀疏张量核上做了映射，但 H100 的 FP8 Tensor Core、AMD MI300X 的稀疏支持、以及国产 AI 芯片的压缩特性尚未被充分挖掘。

**7. 长上下文（1M+ tokens）的训练与推理一体化优化**：Ultra Long Context Training 将训练推进到百万级 tokens，LServe 和 E3 优化长上下文推理——但两者之间的 KV Cache 格式、注意力算法、通信模式尚未统一。

**8. ML 系统的安全与可信性**：Supply-Chain Attacks 揭示了 ML 框架的安全漏洞，AIOpsLab 提供了 Agent 评测框架——但 LLM serving 系统的对抗鲁棒性、隐私保护、模型完整性验证等方向仍有大量空白。

---

## 5. 重点论文推荐

以下按重要性排序，附推荐理由：

### 第一梯队（极具影响力）

**1. [QServe](fbe2b2f74a2ece8070d8fb073717bda6.md) (Luo et al.)**
- 推荐理由：首个生产级 W4A8KV4 LLM 推理服务系统，SmoothAttention 通过软件方法解决了 KV4 量化误差传播这一核心难题。2.31-2.67 倍提速和 3.8 倍显存减少的数字在实际部署中具有直接价值。PGQ 的逐层优化思想对后续量化工作具有指导意义。

**2. [Seesaw](cbc4ab80cd77aa0eb87da062fbcddb46.md) (Su et al.)**
- 推荐理由：识别了 Prefill 偏好 PP、Decoding 偏好 TP 的本质差异，并通过动态重分片实现阶段特定优化。这一洞察简洁而深刻，对当前 LLM serving 的并行策略选择具有范式影响。层级 KV Cache 缓冲的设计体现了优秀的工程直觉。

**3. [TASDER](e2ec2530db26b54d0b3b060c1e4a1bda.md) (Wei et al.)**
- 推荐理由：利用分配律将非结构化稀疏映射到结构化稀疏硬件，在精度损失 < 0.5% 的前提下实现 2-3 倍加速。这是稀疏化领域的重要理论-工程结合，为模型压缩与硬件加速的协同设计开辟了新路径。

**4. [YOUMU](136b9a13861308c8948cd308ccd02658.md) (Zhong et al.)**
- 推荐理由：精准抓住了 LLM 训练数据管道中长期被忽视的效率瓶颈——列式存储的粒度不匹配。Page 级 shuffle 质量接近理想行级 shuffle 的发现意味着无需为 shuffle 质量付出格式转换的代价，对 LLM 训练基础设施有直接影响。

**5. [SOLA](bc82dbfbfa43232be85b8d9838f49c3e.md) (Hong et al.)**
- 推荐理由：将 LLM Serving 的调度问题形式化为约束优化问题，从粗粒度阶段优先级升级到迭代级别的细粒度控制。99.4% 的 SLO 达成率（vs vLLM 的 45.5%）展示了系统化调度优化的巨大潜力。

### 第二梯队（重要贡献）

**6. [TurboAttention](f4f55846501f3336f293fd8b6de10770.md) (Kang et al.)**
- 推荐理由：首次系统性地将 KV Cache 量化与 FlashAttention 加速方法有机结合。FlashQ 的 Blockwise Progressive Quantization 和 SAS 的 LUT+多项式近似都是精巧的工程设计，2.37 倍端到端吞吐量提升具有实际意义。

**7. [LServe](cc8c6b9d89f7a898a29f58869b238e46.md) (Yang et al.)**
- 推荐理由：通过"正交性"洞察将静态稀疏和动态稀疏统一为块稀疏计算范式，实现乘法加速效应。层级分页设计巧妙解耦了剪枝粒度与物理内存布局的矛盾。

**8. [TileLink](c6ee784cbe46d854843e4c883a3321ef.md) (Zheng et al.)**
- 推荐理由：为通信-计算重叠提供了系统化、可自动化的底层原语和编译基础设施。在大模型训练中，通信往往是性能瓶颈，TileLink 的 tile-centric 抽象允许开发者从更细粒度管理数据依赖。

**9. [Rubick](270339c997293ca2988c62f4308e389f.md) (Wei et al.)**
- 推荐理由：首个"白盒"ML 集群调度器，将调度器从资源分配器升级为可理解作业内部瓶颈并动态重构配置的智能系统。华为 256-GPU 集群的生产验证增强了结论的可信度。

**10. [APOLLO](437bc4ccafd3fc6d4289bd10940be42b.md) (Zhu et al.)**
- 推荐理由：用纯随机投影完全替代 SVD，消除了低秩优化器的计算瓶颈。SGD 级内存 + AdamW 级性能的组合对大规模模型训练的资源优化极具吸引力。

**11. [AIOpsLab](d1f9e4a9f109b6e8b75ed362736f22ec.md) (Microsoft et al.)**
- 推荐理由：作为首个系统性的 LLM-based AIOps Agent 评测框架，其工程贡献突出、开放性强。Orchestrator 的接口抽象设计使得不同 Agent 之间的公平对比成为可能。

**12. [FastTree](96894468eb44631a32d7ebd56f9892c7.md) (Pan et al.)**
- 推荐理由：从 radix tree 的内存布局优化自然延伸到计算层共享的系统优化，体现了对 LLM serving 全栈的深刻理解。5.1 倍的 kernel 加速和 2.2 倍的端到端提升非常亮眼。

**13. [E3](78834433edc3291f4c6cbbd2759324db.md) (Peng et al.)**
- 推荐理由：针对 prefill 和 decode 的本质差异分别设计最优通信模式（pass-KV vs pass-Q），在 128 张 H100 上实现 1M tokens 77 秒完成 prefill。长上下文推理的系统优化里程碑。

**14. [Rethinking KV Cache Compression](26289c647c6828e862e271ca3c490486.md) (Zhang et al.)**
- 推荐理由：首次将 KV cache 压缩的算法质量与系统性能放在同一框架下比较，揭示了"精度-吞吐量"权衡的误区。作为综述和工具论文，对社区的理解和后续研究方向有重要指导价值。

**15. [LAVA](9de62e421d58234dbf773abf43268630.md) (Ling et al.)**
- 推荐理由：将 VM 生命周期预测从点预测升级为分布预测+错误自适应，并在 Google Borg 生产系统中验证。这种从"预测准确"到"预测+容错"的范式转变对资源调度研究具有启发性。

---

## 6. 个人评注

### 6.1 本届 MLSys 的亮点

**LLM 系统研究的全面深化**：MLSys 2025 最令人印象深刻的是 LLM 系统研究的深度和广度。从数据管道（YOUMU）、训练优化器（APOLLO）、分布式训练（TileLink、COMET、PipeFill）到推理内核（LeanAttention、FlexAttention、TurboAttention）、服务调度（SOLA、Seesaw、ThunderServe）、量化压缩（QServe、MiLo、TASDER）——LLM 的全生命周期都有高质量的系统工作覆盖。

**工业界与学术界的深度融合**：华为诺亚方舟实验室贡献了 QServe、MiLo、TASDER、PipeFill、DiffServe 等多篇论文，字节跳动的 TileLink 和 COMET，微软的 TurboAttention 和 AIOpsLab，Google 的 LAVA 和 MPMD 训练——工业界研究机构在 MLSys 上的存在感极强。这些论文普遍具有大规模实验验证和明确的工程落地价值。

**边缘 AI 的崛起**：与 OSDI/SOSP 主要关注数据中心不同，MLSys 对边缘设备（MCU、FPGA、手机 SoC）的 ML 系统优化给予了大量关注。MEADOW、MAS-Attention、Lightweight Sparse Microcontrollers、On-Device Forward-Only Inference 等论文表明，边缘 AI 正从"概念验证"走向"系统实用化"。

**评测基础设施受到重视**：AIOpsLab 作为评测框架、Rethinking KV Cache Compression 作为综述和工具论文被接收，说明 MLSys 社区认可"基础设施"和"系统性理解"的独立研究价值。这对于一个快速发展的领域至关重要。

### 6.2 潜在不足与观察

**某些论文的标题与内容存在"包装"倾向**：多篇论文使用"首个""首个生产级"等表述（如 QServe 的"首个生产级 W4A8KV4"、YOUMU 的"首个无需格式转换"）。虽然这些工作的工程价值不可否认，但读者应注意区分概念性创新和工程集成创新的相对强度。

**实验基线的选择需要审慎评估**：部分论文仅与 vLLM 对比（如 SOLA、Seesaw、LLM Queries），而未与 TensorRT-LLM、SGLang 等工业级推理系统对比，这可能限制了结论的普适性。此外，某些论文的模拟器实验（如 MAS-Attention、Dynamic Input Pruning）与真实硬件之间存在差距。

**长上下文训练的质量验证相对薄弱**：Ultra Long Context Training 等论文主要关注系统效率指标（MFU、GPU 数量），但对 4M tokens 训练后的模型质量（困惑度、下游任务性能、位置编码外推能力）的验证不够深入。

**开源生态仍有提升空间**：本届 MLSys 中明确开源（GitHub）的论文比例约为 30-40%。对于系统研究而言，开源代码是其他研究者独立验证和扩展工作的基础。值得欣慰的是 FastTree、Seesaw、LServe、FedProphet 等重要工作已开源。

### 6.3 对系统领域学术生态的观察

**"Big Tech Systems" 在 MLSys 的主导性**：以华为、字节跳动、微软、Google 为代表的新一代工业界系统研究团队，已经形成了完整的研究-工程-发表闭环。这些团队产出的论文在问题选择、数据规模、工程完整性上都达到了顶级学术标准，对学术系统研究形成了有力的竞争和补充。

**MLSys 的差异化定位日益清晰**：与 OSDI/SOSP 相比，MLSys 更强调算法-系统协同设计和面向 ML 工作负载的专用优化；与 NeurIPS/ICML 相比，MLSys 更强调系统实现和端到端性能评估。这种"中间地带"的定位使得 MLSys 成为连接 ML 算法和系统工程的独特桥梁。

**从"能不能跑"到"怎么最优"的范式转变**：无论是 LLM serving、模型压缩还是分布式训练，MLSys 2025 的论文都体现出一种共同的趋势——问题定义越来越精细化，优化目标越来越贴近生产实际（SLO 达成率、成本效率、边缘功耗）。这标志着 ML 系统研究正在从早期的探索阶段进入成熟工程化阶段。

---

*本综述基于 MLSys 2025 全部 60 篇论文的个人阅读报告综合撰写，力求客观呈现每篇论文的核心贡献和研究价值，同时提出个人见解。疏漏和偏颇之处在所难免，仅供参考，欢迎指正。*
