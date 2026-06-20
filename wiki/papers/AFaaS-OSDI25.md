---
type: paper
name: AFaaS
full_title: "Fork in the Road: Reflections and Optimizations for Cold Start Latency in Production Serverless Systems"
authors: [Xiaohu Chai, Tianyu Zhou, Keyang Hu, Jianfeng Tan, Tiwei Bie, et al.]
venue: OSDI
year: 2025
tags: [serverless, cold-start, faas, containers, production]
source_pdf: "[[osdi25-chai-xiaohu.pdf]]"
source_md: "[[osdi25-chai-xiaohu]]"
---

# Fork in the Road: Reflections and Optimizations for Cold Start Latency in Production Serverless Systems (OSDI 2025)

> **一句话总结**：Ant Group 生产 trace 显示 >50% 函数冷启动概率 >0.75 且 Catalyzer 优化后 control path 仍占 30%–40%；AFaaS 用 FRI、资源池化/共享与树形 seed 把冷启动压到 5.45–9.41 ms（生产 1.80×–8.14× 于 Catalyzer），18 个月稳定运行。

## 问题与动机

Serverless 冷启动常达数百 ms–数秒，而函数体常仅 50–100 ms。Ant Group 5 万+ 函数、日均 1 亿调用，>50% 函数冷启动概率 >0.75，>35% 为 1；热实例缓存 1 分钟限制使冷启动仍占多数。

论文指出三类被忽视的 **E2E** 瓶颈：(1) **control path**（containerd→shim→engine 二进制加载，Catalyzer 下 18–25 ms）；(2) **资源 contention**（clone/netns/seccomp 在高并发下 tail 爆炸）；(3) **user code init**（Node 函数 275 ms 中 238 ms 加载依赖）。

## 关键观察 / 隐含假设

- **观察 1**：fork 类优化只加速 sandbox clone，不缩短 OCI 控制链与用户代码加载，E2E 仍 dominated by 被忽略阶段。
  - **依赖假设**：生产使用 micro-VM 安全容器（Catalyzer/sfork），非普通 runc。
  - **可能失效场景**：极简函数、极短依赖；非 VM 隔离平台。
- **观察 2**：高并发下 IPC namespace、veth、seccomp 编译争用 host 内核锁，导致吞吐从 110 FPS 降至 45 FPS（×24 持续 1h）。
  - **依赖假设**：瓶颈在 host 内核而非 guest；seed 共享 netns/IPC 不破坏安全隔离（用户代码在 guest OS）。
  - **证据强度**：强——分阶段 profiling + 优化后波动下降。
- **假设 1**：OCI 为长运行容器设计，serverless 应专用 **FRI**（插件化函数调用替代每次加载 engine 二进制）。
  - **证据强度**：强——BinaryLoad 18.02 ms 被消除；生产 18 个月部署。

## 核心方法

**FRI**：containerd-faas-package 插件直接 RPC 调 create/fork/activate；root seed 创建后不再加载 AFaaS runtime 二进制。

**资源池化/共享**：veth/cgroup 池；seed 共享 netns/IPC；seccomp 预编译；网络栈 shareable 部分预初始化。

**树形 seed**：level-0（guest OS）→ level-1（语言 runtime）→ level-2（用户代码）；CoW 多级 fork，best-effort 选最近 seed。

## 设计取舍

- **取舍 1**：牺牲 OCI 通用模块化，换 FaaS 特化控制面。
- **取舍 2**：共享 namespace 换 latency；每实例仍从干净 seed fork 并在执行后销毁（安全）。
- **边界条件**：大用户代码 seed 内存收益变小；长执行函数 E2E 优化边际仅 ~1.1×。

## 实验与结果

- E2E vs Catalyzer：1.80×–8.14×；冷启动 5.45–9.41 ms（串行），高并发 6.97–14.55 ms vs 38.39–74.05 ms。
- 高并发 ×24：E2E 16.34–39.56 ms vs 51.32–117.92 ms；吞吐扩展优于 Catalyzer/Kata/gVisor。
- level-2 seed 内存：同代码场景比 Catalyzer 少 28%–85%。
- 生产 18 个月稳定；trace 已开源。

## Critical Analysis

### 论证链条

生产 trace 定位三 gap → FRI/池化/seed 树分别对应 → E2E 与并发稳定性提升。链条在 Ant 安全容器栈上闭合；泛化到其他云厂商需重实现 FRI 与 seed 策略。

### 假设压力测试

- 非 VM 隔离或不同 shim 架构时 FRI 收益未知。
- 多租户恶意 netns 共享若配置错误有隔离风险（论文有安全分析但生产误配仍危险）。
- 极冷函数（无 language seed 命中）回退到 root seed，延迟上升。

### 实验可信度

生产 trace + 18 个月部署是强项；对比含 Catalyzer 变体而非仅开源 stack；缺 AWS Lambda 等跨云对比。

### 系统性缺陷

论文未讨论：跨节点 seed 调度、函数版本滚动时 seed 失效、FRI 与 Kubernetes 生态标准化冲突。

## 局限与 Future Work

- **局限 1**：深度绑定 Catalyzer/安全容器栈。
- **局限 2**：长执行函数 E2E 收益有限。
- **Future work 1**：跨节点 seed 共享（RDMA/CXL 类方案）与成本模型。
- **Future work 2**：FRI 标准化与多 runtime 插件生态。

## 相关

- **相关概念**：[[Continuous-Batching]]（对比：批处理 vs 启动）
- **同类系统**：AWS Lambda、Catalyzer、Firecracker、gVisor、RunD
- **同会议**：[[OSDI-2025]]