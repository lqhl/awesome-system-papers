---
type: paper
name: Koala
full_title: "The Koala Benchmarks for the Shell: Characterization and Implications"
authors: [Evangelos Lamprou, Ethan Williams, Georgios Kaoukis, Zhuoxuan Zhang, Michael Greenberg, et al.]
venue: ATC
year: 2025
tags: [benchmark, shell, posix, characterization, reproducibility]
source_pdf: "[[atc2025-lamprou.pdf]]"
source_md: "[[atc2025-lamprou]]"
---

# The Koala Benchmarks for the Shell: Characterization and Implications (ATC 2025)

> **一句话总结**：发布 Koala，包含 126 个真实世界 shell 程序、3 档输入（min/small/full，full 最大 146GB）、自动化 setup/validation 基础设施，已作为评估 PASH/Shark/parallel/hS 等 shell 加速系统的统一 benchmark suite。

## 问题

shell（POSIX/Bash）在 CI/CD、数据分析、自动化、bioinformatics 等场景仍非常普遍，最近 PASH、Shark、hS 等 shell 加速系统不断出现。但 shell 研究领域**没有共识 benchmark suite**：每篇论文要么自己手写 microbenchmark，要么用残缺的开源仓库片段。Shark 作者甚至在论文里说「我们不知道有 shell benchmark，只能用我们自己写的几个 microbenchmark」。

现有选项均不够：

- **microbenchmark**：合成的、与实际 workload 差距大
- **POSIX 测试套**：只测行为正确性不是性能
- **开源仓库**：噪音大、缺输入、依赖不明
- **用户研究语料**：偏开发者模式而非生产 workload

## 核心方法

**Koala 设计**：14 个 benchmark set，126 个 shell 程序，覆盖数据分析（DA）、系统管理（SA）、CI/CD、机器学习（ML）、自动化（AN）、bioinformatics（B）等多个域。

每个 benchmark 配套五个 infrastructure 脚本：

- `install.sh`：装依赖
- `fetch.sh`：下载或生成输入（支持 min/small/full 三档）
- `execute.sh`：跑 benchmark 并采集时间/资源
- `validate.sh`：哈希输出与已知正确值比对
- `clean.sh`：清理

**输入两层存储**：主层在 Brown 大学副本集群（1Gbps switched ether）+ Stevens/UCLA 副本，秒级响应；归档层在 Zenodo（50GB 限制内分割），保证永久可访问。

**特征分析**：覆盖所有 POSIX shell 主要语法 feature（pipeline、redirect、loop、subshell 等）；既有计算密集、内存密集，也有 I/O 密集和短/长任务；用 PCA 在静态/动态特征空间和 LLM embedding 空间证明 benchmark 多样性分布。

**Application**：用 Koala 重新评估 Shark / GNU parallel / hS / PASH 四个加速系统，得到比原论文更全面的 trade-off 视图。例如 weather benchmark 上 Shark 平均 2.3×、parallel 2.7×、hS 1.64×、PASH 1.08× 加速。

一键运行：

```
curl -s up.kben.sh | sh && ./koala/main.sh --min --bare
```

t3.large 上 min 模式约 20 分钟跑完，full 输入约 24 小时。深度细节回 [[atc2025-lamprou]]。

## 关键结果

- 126 个 benchmark 程序、3 档输入大小（最大 146GB weather）
- 在 14 个领域均有覆盖（DA/SA/CI/ML/AN/B 等）
- 用 Koala 评估 Shark/parallel/hS/PASH 的实际 speedup（2.3× / 2.7× / 1.64× / 1.08×），与作者原论文 microbenchmark 数字差异显著
- MIT license 开源，https://kben.sh

## 相关

- **相关概念**：[[Benchmark-Suite]]、[[POSIX-Shell]]、[[Reproducibility]]
- **被评估系统**：PASH、Shark、hS、GNU parallel
- **同会议**：[[ATC-2025]]
