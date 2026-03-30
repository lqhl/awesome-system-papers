# bpftime: Extending Applications Safely and Efficiently

## 论文基本信息

- **标题**: Extending Applications Safely and Efficiently
- **作者**: Yusheng Zheng, Tong Yu (eunomia-bpf Community), Yiwei Yang (UC Santa Cruz), Yanpeng Hu (ShanghaiTech), Xiaozheng Lai (SCUT), Dan Williams (Virginia Tech), Andi Quinn (UC Santa Cruz)
- **会议**: OSDI 2025
- **链接**: https://www.usenix.org/conference/osdi25/presentation/zheng-yusheng

## 研究背景与动机

软件扩展（Software Extensions）是定制化应用行为的核心手段，但扩展的安全性始终是难题。历史上因扩展 bug 导致的故障屡见不鲜：
- **BiliBili/Nginx**：扩展中的死循环导致生产故障
- **CVE-2021-44790 (Apache Lua)**：缓冲区溢出导致应用崩溃
- **CVE-2024-31449 (Redis Lua)**：栈溢出导致远程代码执行

现有扩展框架的三个核心挑战：
1. **互连性 vs 安全性权衡**（Interconnectedness vs Safety）：扩展需要读写宿主状态，但又不能因此危害宿主
2. **隔离性**（Isolation）：宿主不能破坏扩展，也不能被恶意宿主代码通过扩展漏洞攻击
3. **效率**（Efficiency）：扩展在热路径（hot path）执行，不能有显著性能损失

现有方案的局限：
- **LD_PRELOAD 等原生执行**：无隔离、无细粒度安全控制
- **SFI 工具（Wasm、NaCl、RLBox）**：运行时验证，效率低（通常比原生慢 10-50%）
- **子进程隔离（lwC、Shreds、Orbit）**：需要上下文切换，效率低
- **eBPF uprobes**：精度低，不支持细粒度安全权衡

## 要解决的核心问题

如何设计一个扩展框架，在**不引入运行时验证开销**的前提下，支持**细粒度的互连性/安全性权衡**，同时提供**进程内高效隔离**？

## 主要贡献

1. **EIM（Extension Interface Model）**：将扩展所需功能抽象为"资源"（Resource），包括具体资源（内存）和抽象资源（调用宿主函数的能力），用能力（Capability）描述权限
2. **bpftime**：基于 eBPF 风格验证 + ERIM 风格硬件隔离 + 动态二进制重写的高效扩展运行时
3. **Concealed Extension Entries**：二进制重写使未使用的扩展入口零开销
4. **与 eBPF 生态兼容**：复用现有 eBPF 工具链，无需重新学习
5. **6 个真实用例**：Nginx 安全扩展、FUSE 加速、Redis 持久化调优、分布式追踪等
6. **Nginx 扩展仅 2% 开销**：比 Wasm（12%）、Lua（11%）、ERIM（11%）、RLBox（9%）低 5-6 倍

## 研究方法与设计

### EIM 架构

```
应用开发者：定义开发时 EIM 规范（state capabilities、function capabilities、extension entries）
                        ↓
扩展管理器：创建部署时 EIM 规范（为每个入口点分配具体的 capability 组合）
                        ↓
宿主应用 + bpftime 运行时：执行时强制执行 EIM 规范
```

**State Capability**：`read(pid)` 允许读取某变量，`write(pid)` 允许写入某变量

**Function Capability**：函数调用的能力和约束（如 `{rtn > 0}` 后置条件）

**Resource Capability**：`instructions < inf`（无限指令）、`memory < X`（内存上限）

**Extension Entry**：宿主代码中的扩展点（uprobe、uretprobe、sysenter、sysexit）

### bpftime 的三个设计约束

1. **分离验证**：eBPF 风格验证负责安全性（EIM Capability 约束），ERIM 风格隔离负责内存保护
2. **Concealed Extension Entries**：未使用的扩展入口不注入重写代码，实现零开销
3. **bpftime Maps**：进程内高效共享数据结构（零系统调用）

### ERIM 风格进程内隔离

使用 Intel MPK（Memory Protection Keys）保护扩展内存：
- 加载扩展时分配一个 memory protection key
- 使用 WRPKRU 指令设置 key 权限（扩展页：不可写；宿主页：扩展不可读）
- Key 本身的值对扩展不可读（扩展页设为不可读）

### 二进制重写（Concealed Entries）

使用 Frida + Capstone 进行二进制插桩：
- 对 uprobes/uretprobes：标准指令跳板（trampoline）
- 对 sysenter：使用 zpoline 技术（利用零页）处理 sysenter 比 trampoline 小的特殊情况

## 关键实现细节

- **13,000 行代码**（C/C++、Go）
- **Trusted Computing Base**：内核 eBPF verifier + 二进制重写器 + 操作系统 + MPK 硬件
- **当前仅支持 Intel x86**（ARM Memory Domains 可扩展）
- **GitHub 1,000+ stars，20+ 贡献者，活跃维护**

### 与 eBPF 生态的兼容策略

论文详细分析了为何先前用户空间 eBPF 实现（如 UBI BPF）失败：通过拦截 eBPF 相关系统调用、用标准 POSIX 抽象（文件、Unix socket）重新实现，而非重建整个 eBPF 技术栈。

## 实验结果与分析

### Nginx 插件（wrk benchmark, 8 threads, 64 connections）

| 框架 | 吞吐量（RPS） | 相对原生开销 |
|------|------------|------------|
| 原生 | 4,536 | — |
| bpftime | 4,461 | **2%** |
| ERIM | 4,024 | 11% |
| RLBox | 4,148 | 9% |
| Lua | 3,982 | 11% |
| WebAssembly | 4,007 | 12% |

### DeepFlow 追踪（分布式追踪工具）

- **原生 eBPF**：最高 50% 吞吐量下降
- **bpftime**：HTTP 仅 2% 下降，HTTPS 仅 3.79 倍降低

### Redis 持久化调优

- **every-sec 配置**：每 1 秒 fsync，约 6 倍吞吐量下降
- **bpftime Batch-1**：吞吐量与 every-sec 相当，但最多丢失 1 条更新（而非数千条）
- **bpftime Delayed-fsync**：最多丢失 2 条更新，吞吐量介于 always-on 和 every-sec 之间

## 潜在问题与局限性

1. **仅 Intel x86**：ARM Memory Domains 等效技术存在但尚未集成
2. **ERIM 的 syscall 攻击**：论文坦承当前 bpftime 可能受 ERIM 的 syscall 攻击（通过 sysret 等指令泄露 key），需要 Jenny 的 syscall 过滤防御
3. **单扩展入口限制**：当前每个入口点仅支持一个扩展，多扩展需要 dispatcher，论文未详细评估 dispatcher 性能开销
4. **Concealed Entries 的安全性**：二进制重写注入 trampoline，若重写器本身有 bug 可能引入安全漏洞
5. **eBPF 验证的局限性**：依赖内核 eBPF verifier，若 verifier 有 bug 可能导致安全违规逃逸
6. **扩展间共享状态**：多个扩展间共享状态的能力（通过 bpftime maps）可能引入新的一致性问题

## 未来工作方向

- ARM 平台支持
- 更强的隔离机制（防 syscall 攻击）
- 多扩展 dispatcher 优化
- 与更多现有工具集成

## 个人评注

1. **EIM 的概念贡献突出**：将"扩展功能需求"抽象为资源+能力模型，使得安全/互连性权衡可配置化，是本文最具概念价值的部分。类比 OS 的 capability 系统但针对扩展场景定制。

2. **工程实现扎实**：13,000 行代码、支持多个真实用例、GitHub 1,000+ stars 说明项目有真实的用户基础，而非纯学术演示。

3. **Nginx 2% 开销的选取条件重要**：benchmark 配置（wrk 64 连接）是相对轻量负载，在极端高并发或极小文件场景下结果可能不同。

4. **与 eBPF 生态兼容性的讨论有洞见**：详细分析了为何先前用户空间 eBPF 实现失败，并给出了 bpftime 的解决策略。但"通过拦截 syscall 而非重建 eBPF 栈"这一策略的完整性值得质疑——eBPF verifier 的演进和 eBPF 程序类型的快速扩展意味着 bpftime 需要持续跟进。

5. **Syscall 攻击坦承诚实**：论文主动坦承了 ERIM syscall 攻击的潜在风险，这是加分项。

6. **用例丰富但深度不均**：Nginx 和 Redis 用例分析深入，但 FUSE 用例篇幅较短，部分用例细节不足。
