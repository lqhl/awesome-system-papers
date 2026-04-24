---
type: paper
name: AFaaS
full_title: "Fork in the Road: Reflections and Optimizations for Cold Start Latency in Production Serverless Systems"
authors: [Xiaohu Chai, Tianyu Zhou, Keyang Hu, Jianfeng Tan, Tiwei Bie, et al.]
venue: OSDI
year: 2025
tags: [serverless, faas, cold-start, container-runtime, production-systems]
source_pdf: "[[osdi25-chai-xiaohu.pdf]]"
source_md: "[[osdi25-chai-xiaohu]]"
---

# Fork in the Road: Reflections and Optimizations for Cold Start Latency in Production Serverless Systems (OSDI 2025)

> **一句话总结**：蚂蚁集团 AFaaS 从工业生产视角重新审视 serverless 冷启动，通过 FRI 控制面接口、资源池/共享、层次化 seed 树，把冷启动从几百 ms–秒级降到 ms 级，生产部署 18 个月。

## 问题

尽管学术界对 serverless 冷启动做了大量研究（Catalyzer、SAND、SOCK、SnapStart、Firecracker、MITOSIS 等），蚂蚁集团 FaaS 平台（50,000+ 函数、日 1 亿调用）实际部署下来冷启动仍高达数百 ms 到数秒。原因是现有工作过度简化了生产环境：

- **Gap-1 控制面延迟**：高层 runtime（containerd）经 shim + RPC + binary load 调起低层 runtime（Catalyzer）的链路长，每次调用都要加载运行时二进制，光这一步就 18–25 ms，占冷启动 30–40%。
- **Gap-2 资源争用延迟**：高并发下 clone() 创建 net/IPC namespace 争抢 `sb_lock`、`mount_lock`，延迟从 1.45 ms 爆到 418 ms；seccomp 规则编译安装、网络准备、网络栈初始化也都扛不住高并发。×24 并发下吞吐从 110 FPS 慢慢降到 45 FPS。
- **Gap-3 用户代码初始化**：JIT 编译、Spring/Django 这类框架的大依赖加载、库导入轻易占 200+ ms，缓存全部 hot 又内存吃不消。

## 核心方法

AFaaS 分别针对三个 gap：

**FRI（Function Runtime Interface）替换 OCI**。观察到 OCI 里大量 cross-runtime 交互是 shim-call（只是转发），可以安全折叠成 plugin-based 的函数调用。AFaaS 给 containerd 写了 `containerd-faas-package` 插件，只暴露 `create() / fork() / activate()`，其中 create() 只在 root seed 准备时跑一次，后续调用避开 binary load 和 shim 转发。

**资源池化 + 共享消除争用**：

- **Pooling**：提前创建一批 veth pair 和 cgroup，实例起停时从池里取/还，避免动态创建的锁争用。
- **Sharing**：把不需要实例级隔离的状态（网络/IPC namespace、编译好的 seccomp 规则、网络栈的 clock/协议 handler/ARP 等共享部分）集成到 seed 里，fork 出来的实例直接继承；非共享部分（IP/MAC、raw socket）再单独分配。

**树状 seed + 多级 fork** 处理用户代码初始化：

- Level-0 root seed（每节点一个，含 guest OS）。
- Level-1 language seed（已加载 Node.js/Python/JVM runtime）。
- Level-2 user-code seed（已做过 framework init、库加载、JIT warmup）。

CoW 让子 seed 复用父 seed 的物理页，显著压内存；多级 fork 做 best-effort——找得到 level-2 就用，没有就降级到 level-1 或 level-0，保证请求始终能被服务。

## 关键结果

- 端到端冷启动从 Catalyzer 的百 ms–秒级降到 **5.45–9.41 ms**，加速 **1.80–8.14×**。
- 高并发（×24 持续 1 小时）下延迟 **6.97–14.55 ms**，Catalyzer 对照是 38.39–74.05 ms；保持稳定而不降频。
- 内存占用降最多 **84.9%**。
- 生产环境稳定运行 **18+ 个月**，支撑蚂蚁 50k+ 函数、日 1 亿级调用。
- 论文开源了生产 trace：https://github.com/antgroup/AFaaS

## 相关

- **相关概念**：Cold-Start、Copy-on-Write、Secure-Containers、OCI、Seccomp
- **同类系统**：Catalyzer、Firecracker、gVisor、SOCK、RainbowCake、MITOSIS
- **同会议**：[[OSDI-2025]]
