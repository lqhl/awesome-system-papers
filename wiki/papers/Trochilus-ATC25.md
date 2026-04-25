---
type: paper
name: Trochilus
full_title: "Learning-Enhanced High-Throughput Pattern Matching Based on Programmable Data Plane"
authors: [Guanglin Duan, Yucheng Huang, Zhengxin Zhang, Qing Li, Dan Zhao, et al.]
venue: ATC
year: 2025
tags: [programmable-switch, pattern-matching, network-security, knowledge-distillation, p4]
source_pdf: "[[atc2025-duan-guanglin.pdf]]"
source_md: "[[atc2025-duan-guanglin]]"
---

# Learning-Enhanced High-Throughput Pattern Matching Based on Programmable Data Plane (ATC 2025)

> **一句话总结**：把 IDS pattern matching 重构成「DFA → BRNN → 软多视图森林 (SMF)」蒸馏链路，部署到 Tofino programmable switch 上达到多 Tbps 吞吐，并通过半监督训练自动更新规则替代专家手写。

## 问题

NIDS/WAF/审查系统的模式匹配，软件 CPU 优化 < 70 Gbps，GPU/FPGA/NPU 受 PCIe 限制 ≤ 100 Gbps 且更新难。Programmable switch 有 Tbps 但只支持 match-action，不能跑乘除等浮点；现有 switch 方案（[25,52]）只把 NFA 串行化做 multi-string match，因状态转移线性增长不能扩展到正则表达式 + 大规模 pattern set，也无法在线更新（需专家重写）。

## 核心方法

三步把 PCRE pattern 转成 switch 可部署的 match-action 表：

1. **Pattern modelization**：先 Thompson + powerset + 最小化把 PCRE 转 byte-level DFA，然后用「DFA forward 与 RNN forward 等价」的关系把 DFA losslessly 映射成 byte-level RNN (BRNN)，其权重就是状态转移矩阵 W。BRNN 既保留专家规则的初始 accuracy（cold-start），也支持有标签数据继续训练学新模式。
2. **SSKD (Semi-Supervised Knowledge Distillation)**：把 BRNN 输出的 soft label 与 ground-truth hard label 按 β 混合，训练 Soft Multi-view Forest (SMF)：多个 SDT (soft decision tree) 通过加权迭代（类似 AdaBoost）多视角学习，使用 binary feature 避免传统 decimal range matching 在 TCAM 上的 entry 爆炸。
3. **Entry cluster + sliding window**：tree encoding 把 SDT 转 ternary match table，因 90% mask bits 是 0 故把一张大表用 Jaccard-based clustering 切成 k 张小表减 TCAM 占用（NP-hard，启发式 O(lzkn)）；packet payload 用 sliding window (大小 win，步长 s，要求 win-s ≥ pattern 最大长度) 解决跨窗口匹配。

实现细节回 [[atc2025-duan-guanglin]] / [[Tofino]] 代码。

## 关键结果

- 多 Tbps 吞吐量，匹配现代 100 Gbps+ 网络；只用 Tofino 1 上 6.2 MB TCAM。
- Cold start 下与原始 pattern 同等 accuracy；有标签数据训练后再涨约 10%。
- 支持在线更新：增量训练 SMF + 重新生成表项，无需专家手写新规则、不中断服务。
- Snort + Suricata 共约 4000 patterns，覆盖 5 类（info/web/malware/sql/exploit），95% 模式长度 < 50 byte。

## 相关

- **相关概念**：[[Programmable-Switch]]、[[Knowledge-Distillation]]、[[DFA]]、[[TCAM]]、[[P4]]
- **同类系统**：BOLT、Pigasus、HyperScan
- **同会议**：[[ATC-2025]]
