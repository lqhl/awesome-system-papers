---
type: paper
name: TimesFM-Fin
full_title: "Financial Fine-tuning a Large Time Series Model"
authors: [Xinghong Fu, Masanori Hirano, Kentaro Imajo]
venue: arXiv
year: 2024
tags: [finance, time-series, foundation-model, fine-tuning, price-prediction, quant-trading]
source_pdf: "[[2412.09880v1.pdf]]"
source_md: "[[2412.09880v1]]"
---

# Financial Fine-tuning a Large Time Series Model (arXiv 2024)

> **一句话总结**:MIT + Preferred Networks 用 **100M 金融时间点**(S&P500/TOPIX500/外汇/crypto 多粒度)对 Google 的 TimesFM(200M 参数时间序列 foundation model)做 continual pre-training;关键修改是 **log-transform MSE loss** + **动态 mask**,在 S&P500 的 128-horizon market-neutral 模拟交易中把 Sharpe 从原始 TimesFM 的 0.42 推到 **1.68**。

## 问题

TimesFM(Google 2024)是 decoder-only time-series foundation model,在 Google Trends、Wiki 浏览量等规则/季节性序列上 SOTA。但金融价格序列具有 non-stationarity、heavy tail、跨 asset 尺度差 6 个数量级(指数 $\approx 10^3$ vs crypto $\approx 10^{-4}$)——**原始 TimesFM 直接用在价格预测上 4/7 horizon 低于随机猜测**。研究问题:time-series foundation model 能否通过金融数据 fine-tune 变得可用?

## 核心方法

**continual pre-training**,不改架构(20 层 1280 dim),从 TimesFM 公开 checkpoint 继续 SGD。关键改动两处:

1. **Log-transform loss**:先 $z = \log(y)$ 再算 MSE。直接 MSE 有两个病:(a) 大尺度资产权重主导训练,(b) 极端崩盘(>99% 跌幅)导致 NaN loss。小变动下 MSE-of-log ≈ 百分比 MSE;大变动下 log 自然 taper 稳住梯度。
2. **动态 mask**:训练时每 batch 在 $[128, 512]$ 随机选 context 长度 $t_{end}$,再在 $[0, t_{end}-128]$ 选 $t_{start}$,预测后 128 点。让模型学会从各种 context 长度 forecast,抑制过拟合。

训练开销:8×V100 跑 1 小时完成 80M 点 continual,100 epoch 后 loss 稳在原始 70%,无 NaN。

## 关键结果

**accuracy / F1**(2023 年起的测试集,7 个 horizon 从 2 到 128):

- 原始 TimesFM:4/7 horizon 低于 chance rate
- fine-tuned:**全部 7 个 horizon 高于 chance rate,且全部高于原始 TimesFM**

**market-neutral mock trading on S&P500**(horizon=128):

| 模型 | Ann Sharpe |
|---|---|
| fine-tuned TimesFM | **1.68** |
| 原始 TimesFM | 0.42 |
| Random | 0.03 |
| AR(1) | 1.58 |

- ARR 3.6%,MDD -0.1%,neutral cost 0.6%
- 但在 Currencies / Crypto Daily 上 fine-tuned 不及 AR(1) — fine-tuned TimesFM 是**唯一在所有 4 个市场都正收益**的,但并非每个市场都最优

## 局限

- 未做 synthetic data、未对不同粒度 reweight
- 在 currency / crypto 上 AR(1) 更好,提示 financial price 里**短时均值回归可能已耗尽**,大模型对 highly noisy regime 无优势
- 训练只到 100M 点,远低于 TimesFM 原始 100B 点

## 相关

- 基础模型:**TimesFM**(Google 2024,200M decoder-only TS foundation model)
- 上游/对照路线:符号回归 / formulaic alpha(如 [[101-Alphas-arXiv15|101 Alphas]])、iTransformer、PatchTST
- 同 topic 互补:[[RD-Agent-Quant-arXiv25|R&D-Agent(Q)]] 走的是「agent 自动合成 factor + 训练小模型」而非「foundation model 直接 fine-tune」,两条路线在 quant 领域并存

## 代码与数据

- 代码与权重:<https://github.com/pfnet-research/timesfm_fin>
