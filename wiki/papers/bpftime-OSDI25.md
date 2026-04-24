---
type: paper
name: bpftime
full_title: "Extending Applications Safely and Efficiently"
authors: [Yusheng Zheng, Tong Yu, Yiwei Yang, Yanpeng Hu, Xiaozheng Lai, Dan Williams, Andi Quinn]
venue: OSDI
year: 2025
tags: [ebpf, extensions, userspace, isolation, mpk]
source_pdf: "[[osdi25-zheng-yusheng.pdf]]"
source_md: "[[osdi25-zheng-yusheng]]"
---

# Extending Applications Safely and Efficiently (OSDI 2025)

> **一句话总结**：bpftime 用 eBPF-style 静态验证 + Intel MPK 硬件隔离 + 二进制重写实现的「concealed extension entry」，把 userspace 扩展（uprobe/SSL 跟踪/FUSE 缓存/Redis 持久化）做到比 eBPF uprobe 快一个数量级，Nginx 上仅 2% 开销。

## 问题

应用需要通过 extension 做可观测性、安全策略、性能优化（Nginx 插件、Redis Lua、FUSE 钩子等），但现有扩展框架在三个关键特性上难以兼顾：

- **细粒度 safety/interconnectedness tradeoff**：extension 需要读/写 host 状态、调 host 函数才能做实事；但同时必须能被限制到只做必要的事，避免像 Bilibili Nginx Lua 那种死循环拖垮生产。Wasm/Lua 把安全交给应用自行检查（易出错），RLBox/XFI 不支持 per-entry 粒度。
- **isolation**：host 不能污染 extension 的状态（安全监控类用例需要），SFI 开销大，子进程隔离（Orbit、Wedge）需要修改应用源码且有 context-switch 开销。
- **efficiency**：扩展往往在 hot path 上，eBPF uprobe 每次触发软中断进内核，单次微基准 ~2.5μs。

## 核心方法

**EIM（Extension Interface Model）**：把「能读某个全局变量」「能调某个 host 函数」「能用多少 CPU 指令/内存」都表达成 **capability**。application developer 在开发期声明 state/function capability 与 extension entry（注解函数）；extension manager 在部署期写 **extension class**，把 allowed capability 绑定到 entry——类似 SELinux / Chrome manifest 的精细化授权，但为扩展场景定制。每个 bug 案例（Table 1 中的 Nginx livelock、httpd lua buffer overflow、Redis Lua RCE）都能用 EIM 禁掉。

**bpftime runtime**：(1) **eBPF-style 静态验证**——把 EIM 的 capability 翻成 eBPF verifier 能理解的 kfunc mock + 类型约束 + 资源界限，复用 Linux 内核 eBPF verifier；运行期零开销。(2) **ERIM-style 进程内硬件隔离**——用 Intel MPK (WRPKRU) 给 extension 独立 protection key，host bug 无法篡改 extension 状态。(3) **Concealed extension entries**——用 Frida + libcapstone 在 extension 加载时做二进制重写（zpoline 处理 syscall），未启用的 entry 零开销；这是和传统 uprobe（软件 breakpoint 触发 kernel trap）的关键差别。与 eBPF 生态兼容，interposed 在 eBPF syscall 接口和 shared map 上——bcc/libbpf 客户端无需修改。

## 关键结果

- Nginx 扩展：2% 开销 vs Lua/Wasm 11–12%、ERIM/RLBox 9–11%（5–6× 更低）。
- DeepFlow 微服务追踪吞吐提升 1.5×（eBPF 下降 54%）。
- Redis delayed-fsync 扩展：相比 alwayson 吞吐 5×，比 everysec 少 5 个数量级的数据丢失。
- FUSE 元数据缓存：fstat/openat 路径快 2 个数量级。
- SSL 流量监控（sslsniff）：比 eBPF 开销低 3.79×。
- Uprobe 微基准：bpftime 190 ns vs eBPF 2561 ns（>13×）。
- 兼容性：17 个 bcc/bpftrace 工具零修改运行；bpf-conformance 仅 1 个 fail（ubpf/rbpf 分别 22/23）。

## 相关

- **相关概念**：[[eBPF]]、capability-based security、[[MPK]]（Memory Protection Keys）、[[SFI]]、binary rewriting、least privilege
- **同类系统**：Lua、WebAssembly、ERIM、RLBox、Orbit、lwC、Wedge、KFlex、ubpf、rbpf
- **同会议**：[[OSDI-2025]]
