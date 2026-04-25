---
type: paper
name: Orthrus
full_title: "Orthrus: Efficient and Timely Detection of Silent User Data Corruption in the Cloud with Resource-Adaptive Computation Validation"
authors: [Chenxiao Liu, Zhenting Zhu, Quanxi Li, Yanwen Xia, Yifan Qiao, et al.]
venue: SOSP
year: 2025
tags: [silent-data-corruption, reliability, mercurial-cores, validation, llvm, compiler]
source_pdf: "[[3731569.3764832.pdf]]"
source_md: "[[3731569.3764832]]"
---

# Orthrus: Efficient and Timely Detection of Silent User Data Corruption in the Cloud (SOSP 2025)

> **一句话总结**:只对应用的 data path 做异步跨核重执行(靠 versioned memory 解耦 APP 与 VAL),仅 2–6% 运行时开销即可在单核检测出 87% 的 silent data corruption,四核时达 96%。

## 问题

Mercurial cores(Google 2021 年提出)——看起来完好的 CPU 偶尔会悄悄算错,引发 silent data corruption (SDC)。对云银行余额、数据库写入等危害巨大。现有方案要么离线(每季度跑一次 CPU 测试)检测不到实时数据错误;要么开销太大:RBV (replication-based validation) 整机复制、超 100% 资源;ILV (instruction-level validation) 周期级同步、50× 慢、需专用硬件。checksum 只能抓 bit-flip,抓不到计算过程中的错误(比如 hash 算错导致 insert 到错桶)。

## 核心方法

关键观察:云应用通常有清晰的 **data path**(map/reduce/insert/get 等纯数据算子)vs **control path**(网络 IO、调度、解析)分离,Memcached 里 control path 代码是 data path 的 20×。

Orthrus 采用混合策略:

1. **Data path 跨核重执行**:开发者用简单注解声明 user-data 类型和 closure(data operator),LLVM 编译器自动把 closure 转为使用 Orthrus 原语。APP 进程跑原始 closure,VAL 进程在另一核上重跑,比对输出。
2. **Versioned memory**:heap 分 private space 与 user-data space。user 数据必须 `OrthrusNew` 分配、通过 `OrthrusPtr` 访问;每次 store 产生一个新 version,记入 closure log。这样 VAL 可以异步、乱序地在 APP 完成后拿 log 去重放,完全解耦执行,同时保证重放在相同的 memory snapshot 上。
3. **Control path checksum**:为每个 user-data object 在生成时算 checksum,进入 data path 前校验,抓 bit-flip 类错误。
4. **Resource-adaptive sampling**:validation log 进入队列后按采样率挑选验证;scheduler 根据观测到的 validation latency 动态调采样率。优先验证近期未验证过的 operator、以及包含高风险指令(fp、vector)的 operator——因为 CPU 错误高度可复现且与特定指令相关。

## 关键结果

- 运行时开销 **~4%**(2–6% 范围),比 RBV 快 **1.9×**。
- Validation latency **40µs**,比 RBV 低三个数量级。
- 单核验证即可检测 **87%** 数据损坏,双核 **91%**,四核 **96%**。
- 在 4 个真实应用(含 Memcached)上评估,LLVM 注入指令级错误(模式参考 Alibaba、Google 观察)。
- 开源:https://github.com/ICTPLSys/Orthrus。

## 相关

- **相关概念**:[[Silent-Data-Corruption]]、[[Mercurial-Cores]]、[[LLVM]]、[[Versioned-Memory]]、[[Compiler-Instrumentation]]
- **相关工作**:RBV、ILV、checkpoint/recovery
- **同会议**:[[SOSP-2025]]
