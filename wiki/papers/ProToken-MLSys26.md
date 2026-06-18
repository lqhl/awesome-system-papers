---
type: paper
name: ProToken
full_title: "ProToken: Token-Level Attribution for Federated Large Language Models"
authors: [Waris Gill, Ahmad Humayun, Ali Anwar, Muhammad Ali Gulzar]
venue: MLSys
year: 2026
tags: [federated-learning, llm, provenance, attribution, privacy]
source_pdf: "[[3988c7f88ebcb58c6ce932b957b6f332.pdf]]"
source_md: "[[3988c7f88ebcb58c6ce932b957b6f332]]"
---

# ProToken: Token-Level Attribution for Federated Large Language Models (MLSys 2026)

> **一句话总结**：ProToken 在联邦 LLM 上对自回归每个 token 做 client-level 归因，借 FedAvg 线性分解 + 后期层梯度加权，在 16 组配置上平均归因准确率 **98.62%**，55 client 规模仍 **>92%**。

## 问题

联邦 fine-tune 的 global LLM 生成响应时，无法判断哪些 client 数据影响了输出，阻碍调试、公平激励与恶意 client 识别。分类模型 provenance 无法处理变长自回归生成与 LLM 预训练先验混淆；全层全 neuron 追踪在 1B×5 client×100 token 下需 **5000 亿**次计算，不可行。

## 核心方法

**线性分解**：FedAvg 等聚合使 global neuron 输出可写为 client 输出的加权和，支持 per-layer 归因。

**Layer selection**：仅追踪后期 transformer block 的 attention output projection 与 MLP 末层，捕获 task-specific 信号并降维。

**Gradient weighting**：用 token logit 对 hidden state 的梯度与 client 激活内积，过滤无关 neuron；跨 token 累加后 softmax 得 client 分布。

**评估**：backdoor trigger→sentinel response 构造可验证 ground truth（评估专用，非攻击方案）。

## 关键结果

- 4 模型 × 4 领域 16 配置平均归因准确率 **98.62%**
- 55 clients（9.2× 扩展）准确率 **>92%**，contributing/non-contributing 分离清晰
- 仅操作 model update/activation/gradient，不访问 raw data

## 相关

- **相关概念**：[[LoRA]]、[[Quantization]]
- **同类系统**：FedAvg、FlowerTune
- **同会议**：[[MLSys-2026]]