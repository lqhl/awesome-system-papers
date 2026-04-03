# The Koala Benchmarks for the Shell: Characterization and Implications

**作者**：Evangelos Lamprou, Ethan Williams (Brown University); Georgios Kaoukis (National Technical University of Athens); Zhuoxuan Zhang (Brown University); Michael Greenberg (Stevens Institute of Technology); Konstantinos Kallas (UCLA); Lukas Lazarek, Nikos Vasilakis (Brown University)
**会议**：USENIX ATC 2025
**链接**：https://www.usenix.org/conference/atc25/presentation/lamprou
**源文件**：[[atc2025-lamprou.pdf]]

---

## 一、背景

Shell 编程在当今依然极为普遍，在编程语言流行度排名中持续位居前十，近年来的流行度增长甚至超过了 C 和 Python 等老牌语言。学术界近年来也涌现出大量针对 shell 程序加速的研究，包括并行化（PaSh、PASH）、分布化（DiSh）、推测执行（hS）和语法变换（Shark）等方向。

然而，shell 领域长期缺乏一个标准化的 benchmark suite。这导致研究者在评估系统性能时面临严重困难：不同系统使用不同的基线和评测程序，结果缺乏可比性；研究者不得不手写微基准测试，无法反映真实工作负载；可复现性和公平对比无从谈起。正如 Shark 的作者所坦言："据我们所知，不存在一套 shell 语言的 benchmark。我们展示的只是我们自己编写的几个微基准测试的初步结果。"

---

## 二、要解决的问题

1. **缺乏标准 benchmark suite**：shell 性能优化领域没有一个被广泛认可、可复用的基准测试集合，研究者各自为政，评测结果不具备横向可比性。

2. **现有评测方式的局限性**：
   - **微基准测试**：手写的小型代码片段，与真实工作负载差异大，无法推广结论
   - **标准测试套件**（如 POSIX test suite）：关注行为正确性而非性能，缺乏真实规模的工作负载
   - **开源代码仓库**：缺少输入数据、依赖声明和 setup 脚本，代码质量参差不齐
   - **用户研究语料**：为控制变量而牺牲了程序多样性和真实性

3. **缺乏系统性的特征分析**：社区对 shell 程序的静态和动态特征缺乏全面理解，难以判断优化系统的适用范围和局限性。

---

## 三、洞察与设计

**关键洞察**：真实世界的 shell 程序在语法特征、计算域、运行时行为（CPU/内存/IO 密集度）等维度上存在极大的多样性，而现有的微基准测试和临时收集的脚本完全无法覆盖这种多样性。一个有价值的 benchmark suite 必须系统性地从真实场景中采集程序，并配备多尺度的真实输入数据，才能揭示优化系统在不同工作负载下的真实表现。

基于这一洞察，KOALA 的设计包含四个核心组件：

1. **Benchmark 程序集合**：126 个真实世界 shell 程序，分为 14 个集合（analytics、bio、ci-cd、covid、file-mod、inference、ml、nlp、oneliners、pkg、repl、unixfun、weather、web-search），覆盖数据分析、系统管理、CI/CD、机器学习、文本处理、生物信息等多个计算领域。

2. **多尺度输入数据**：每个 benchmark 提供三种输入规模——minimal（快速验证）、small（小规模评测）和 full（完整真实数据）。输入数据托管在两级存储基础设施上：大学管理的高可用集群（主）+ Zenodo 永久归档存储（备）。

3. **自动化基础设施**：每个 benchmark 遵循统一的五脚本规范（install.sh / fetch.sh / execute.sh / validate.sh / clean.sh），支持 Docker 容器化隔离执行、多轮运行聚合、输出哈希校验，以及可配置的 shell 解释器（通过 KOALA_SHELL 变量）。

4. **静态与动态特征分析框架**：使用 libdash 进行 AST 级静态分析，统计语法构造和命令使用频率；通过 /proc 采集 CPU 时间、内存、IO 等动态指标，并进行 PCA 分析验证多样性。

---

## 四、实现细节

**静态分析**：使用 libdash 解析 shell 脚本 AST（基于 SMOOSH 的 POSIX shell 抽象语法定义），分别统计 shell 层面（所有 AST 节点）和命令层面（仅命令、built-in、函数节点）的构造出现次数。KOALA 覆盖了 POSIX shell 的所有语法构造，包括 pipeline、background operator、subshell、expansion、redirection 等关键特性。

**动态分析**：在 32GB RAM + 8 核 Ryzen 7 9700X + 1TB NVMe SSD 环境下，以 `bash --posix` 执行。通过探测 `/proc/<pid>/{stat,io}` 收集 CPU 和 IO 数据；用 Python 的 `time.perf_counter` 和 `psutil`（0.01 秒间隔）测量 wall-clock time 和内存高水位。

**命令统计**：KOALA 包含 248 个不同命令，分为四类——GNU Coreutils（54 个）、标准 Linux 工具（39 个）、shell built-in（20 个）、自定义二进制/函数（135 个，占 54%）。

**集成工作量**：集成一个新 benchmark 需要 10-80 人时不等，总计约 520 人时。简单的如 oneliners、unixfun 约 10 小时，复杂的如 ci-cd、file-mod 需 60-80 小时。

**输入数据规模**：small 输入范围 1.05MB–24.3GB，full 输入范围 44.9MB–146GB（总计约 0.5TB）。

---

## 五、实验结果

论文将 KOALA 应用于四个 shell 优化系统进行评测，实验环境为 AWS c6i.4xlarge（32GB RAM，16 核 3.5GHz CPU，Ubuntu 24.04，bash v5.2.21 --posix）。

### 四个系统的加速效果

| 系统 | 加速原理 | 加速范围 | 最佳 benchmark | 受限场景 |
|------|---------|---------|---------------|---------|
| Shark | 语法变换（消除 cat、并行化循环体） | 1.01×–13.43× | weather (13.43×), nlp (6.46×) | IO 密集或已用 pipeline 的脚本 (1.01×) |
| GNU parallel | 手动包装为 parallel 调用 | 0.95×–6.46× | nlp (6.46×), file-mod (3.84×) | 有阶段依赖的脚本，如 unixfun (1.02×) |
| hS | 推测式乱序执行 | 0.47×–4.97× | unixfun (4.97×), weather, bio | 有依赖的脚本会减速 (web-search 0.47×) |
| PaSh | 命令感知的 JIT 并行化（4× 并行度） | ~1×–2.14× | oneliners (2.14×), covid (1.82×) | 缺少命令注解的脚本无加速 |

### KOALA 整体特征

| 指标 | 最小值 | 平均值 | 中位数 | 最大值 |
|------|-------|-------|-------|-------|
| 程序数 (#.sh) | 1 | 9 | 4 | 36 |
| 代码行数 (LoC) | 34 | 349.9 | 65.5 | 2592 |
| Full 输入大小 | 44.9MB | 38.0GB | 13.5GB | 146GB |
| CPU 时间 | 5.4s | 955.7s | 218.2s | 6720.9s |
| 内存高水位 | 9.62MB | 3.17GB | 398MB | 25.1GB |
| IO 总量 | 1.21GB | 67.9GB | 20.1GB | 352GB |

---

## 六、批判性分析

1. **评测系统选择有限且不均衡**：只评测了 4 个系统，且其中 hS 是"早期原型"，多个 benchmark 直接运行失败或产生错误结果（ci-cd、file-mod、llm、nlp、oneliners、pkg、repl 整体被排除）。这使得 hS 的评测结果说服力大打折扣，但论文仍据此给出了总结性结论。

2. **缺乏端到端公平对比**：四个系统的应用方式差异巨大——Shark 和 GNU parallel 需要手动改写脚本，而 PaSh 和 hS 是 drop-in replacement。论文虽然提到了这一点，但在展示加速比时未充分讨论人力成本与加速效果之间的 trade-off，读者容易误以为这些数字具有可比性。

3. **benchmark 代表性的自证循环**：论文声称 KOALA 的语法特征分布与真实世界 shell 脚本一致（引用 [22]），但 KOALA 只有 126 个程序，且选择过程并非随机抽样而是人工策划的。PCA 分析展示了多样性，但"多样"不等于"代表性"。

4. **集成成本被低估**：总计 520 人时的集成工作量（某些 benchmark 需要 60-80 人时）对于一个号称可复用的 benchmark suite 来说是相当高的门槛，但论文对此轻描淡写，未讨论如何降低后续 benchmark 的集成成本。

5. **动态特征分析的硬件依赖**：所有动态指标基于特定硬件平台（桌面级 Ryzen 9700X），而实际实验在 AWS c6i.4xlarge 上进行。论文未讨论不同硬件平台对动态特征分布的影响，而这对于声称"硬件无关"的特征分析来说是一个疏漏。

6. **输入数据的可持续性风险**：虽然有两级存储，但 full 规模输入总计约 0.5TB，依赖三所大学的服务器和 Zenodo。长期来看，大学服务器的可用性和 Zenodo 的 50GB 限制都是潜在风险，论文对此的"永久可用"承诺过于乐观。

---

## 七、总结

KOALA 填补了 shell 性能优化领域缺乏标准 benchmark suite 的空白，提供了 126 个真实世界程序、多尺度输入数据和完善的自动化基础设施。通过对四个优化系统的评测，展示了不同系统在不同类型工作负载上的差异化表现，验证了 benchmark suite 的实用价值。主要局限在于程序规模仍然有限（126 个）、集成新 benchmark 的成本较高，且对某些评测系统（如 hS）的覆盖不够完整。KOALA 最适合作为 shell 加速系统的标准化评测平台，但研究者仍需根据自身系统的特点补充针对性的微基准测试。
