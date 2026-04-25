---
type: paper
name: SyzMini
full_title: Optimizing Input Minimization in Kernel Fuzzing
authors: [Hui Guo, Hao Sun, Shan Huang, Ting Su, Geguang Pu, Shaohua Li]
venue: ATC
year: 2025
tags: [fuzzing, kernel, syzkaller, input-minimization, security]
source_pdf: "[[atc2025-guo.pdf]]"
source_md: "[[atc2025-guo]]"
---

# Optimizing Input Minimization in Kernel Fuzzing (ATC 2025)

> **一句话总结**：[[Syzkaller]] 把 57.5% 的 fuzzing 资源耗在 minimization stage；SyzMini 用 influence-guided call removal + type-informed argument simplification 把 minimization 程序执行数砍 60.7%、分支覆盖率提 12.5%、找 bug 数 1.7–2×。

## 问题

Coverage-guided kernel fuzzing 的 minimization 阶段把 interesting program（一段 syscall 序列）压缩成保留新覆盖的最小输入，对后续 mutation 至关重要——去掉 minimization 会导致覆盖降 27.5%、bug 数降 40.4%。但 Syzkaller 的 one-by-one minimization 每删一个 call 或简化一个参数都要 dynamic 执行整个 program 验证覆盖是否保留，48h fuzzing 中 57.5% 的 program execution 都耗在这上面。之前没有工作系统优化它。

## 核心方法

两个 general 策略减少需要验证执行的次数：

1. **Influence-guided call removal**：基于 syscall 间的 influence relation（call A 修改 kernel 全局状态 → call B 走不同路径）。对 target call $c_n$，先静态（资源类型 + pointer 数据流方向）+ 动态（minimization 历史）收集 74,865 条 influence 关系，再用 worklist 算法找出对 $c_n$ 没直接也没传递影响的 irrelevant calls，**一次性整批删除**。如果验证通过，n-1 个 call 被一次执行去掉；否则回退到 one-by-one 兜底。
2. **Type-informed argument simplification**：识别参数是 fixed-size（Integer/Flag/Protocol/Resource）还是 variable-size（Array/Buffer，及递归 Pointer/Struct）。fixed-size 参数简化后 mutation space 不变，**直接跳过**；只对 variable-size 用 binary search 砍元素数量。

集成进 Syzkaller commit 1759857fa9bd 得到 SyzMini。

## 关键结果

- Linux 5.15/6.1/6.11 上 24h 重复 10 轮：分支覆盖 +13.3%/+12.2%/+12.1%，达到同覆盖速度 1.69×。
- bug 数 v5.15 14→28、v6.1 12→20、v6.11 6→12，总共 27→50 unique bugs。
- 在最新 upstream Linux 6.11 三天 fuzzing 找到 13 个 previously unknown bug，全部 confirmed，4 个已 fix。
- 把策略移植到 SyzVegas / CountDown / SyzDirect 都有显著提升：SyzVegas +14.5% 覆盖、CountDown +66.7% memory bug、SyzDirect 1.5× 复现速率。

## 相关

- **相关概念**：fuzzing、coverage-guided-fuzzing、kernel-testing
- **同类系统**：[[Syzkaller]]、SyzVegas、Healer、CountDown、SyzDirect
- **同会议**：[[ATC-2025]]
