---
type: paper
name: bpftime
full_title: "Extending Applications Safely and Efficiently"
authors: [Yusheng Zheng, Tong Yu, Yiwei Yang, Yanpeng Hu, Xiaozheng Lai, Dan Williams, Andi Quinn]
venue: OSDI
year: 2025
tags: [ebpf, extensions, sandboxing, eim, userspace]
source_pdf: "[[osdi25-zheng-yusheng.pdf]]"
source_md: "[[osdi25-zheng-yusheng]]"
review_status: needs-review
evidence_level: full-text
last_reviewed: 2026-07-30
---

# bpftime：安全高效地扩展应用程序（OSDI 2025）

> **原题**：Extending Applications Safely and Efficiently

> **一句话总结**：应用扩展要在互联与安全间细粒度权衡，现有 Wasm/Lua/Orbit 等或缺 per-entry policy 或开销大；EIM 用 resource/capability 描述扩展权限，bpftime 用 eBPF 验证零开销安全 + ERIM 硬件隔离 + concealed entry（二进制重写按需注入 hook），Nginx 扩展开销 **~2%**（Wasm 等 **~10%**），微服务 profiling **1.5×** 于 uprobes eBPF。

## 问题与动机

Nginx/Redis/浏览器等靠扩展定制部署。扩展需读写信 host 状态（互联）又不能拖垮 host（安全）。Least privilege 需 per-extension-entry 不同 policy，但 Wasm/NaCl 难细粒度；Orbit/lwC 要改 OS 且切换重。生产事故：Nginx 扩展死循环、Lua 栈溢出 RCE（表 1）。

## 关键观察 / 隐含假设

- **观察 1**：扩展权限可统一建模为 resource（内存、调用 host 函数等），deployment 时由 extension manager 按 entry 授予 capability（EIM）。
  - **依赖假设**：host 开发者预先声明可用 capability；manager 可信无漏洞。
  - **可能失效场景**：host 暴露过多 capability 则 manager 难收敛最小权限。
- **观察 2**：eBPF 静态验证可零运行时开销 enforcing safety；ERIM（MPK 类）隔离 extension 与 host 低开销；未加载扩展时不注入 hook（concealed entry）避免空 entry 税。
  - **依赖假设**：x86 MPK/ERIM 可用；重写与验证与内核 eBPF 工具链兼容。
  - **证据强度**：强——微基准 + 六用例 §6。
- **假设 1**：与内核 eBPF 生态兼容可加速采用（ uprobes 用户可迁移）。
  - **可能失效场景**：非 Linux/x86 部署需移植 ERIM/重写后端。

## 核心方法

**EIM**：developer 定义 capability；manager 定义 extension class 绑定到 entry。

**bpftime**：加载扩展时验证 bytecode → 重写 host 二进制插入 concealed entry → ERIM 域切换执行；与内核 eBPF 程序共享状态。

## 设计取舍

- **取舍 1**：依赖 eBPF 指令集表达力，极强扩展可能写不出。
- **取舍 2**：二进制重写增加构建/部署复杂度，换 near-native。
- **边界条件**：六用例：微服务 profiling、Redis 持久化、FUSE cache、SSL tracing、syscall 分析、Nginx 防火墙。

## 实验与结果

- 微服务 profiling 吞吐 **1.5×** vs eBPF uprobes。
- Redis 新 durability 配置：crash 丢数据少数量级，吞吐仅 **~10%** 降。
- FUSE metadata cache：操作加速数量级。
- Nginx：**~2%** overhead vs **~10%** Wasm/Lua/ERIM/RLBox。
- SSL 监控：**3.79×** vs native eBPF；可配置不影响未监控进程。

## 批判性分析

### 论证链条

生产扩展事故动机 EIM 细粒度 → bpftime 三件套降开销 → 六场景覆盖，产品化证据（GitHub 1k stars）加强可信度。

### 假设压力测试

MPK 域数量限制？多 extension 同 entry 切换频率？恶意 extension 通过验证器漏洞突破的 threat model 边界需跟内核 eBPF 同样严肃审计。

### 实验可信度

对比 Wasm/Lua/ERIM 等同机；Nginx 2% 为亮点。部分用例（FUSE）极端加速依赖特定 cache 命中。

### 系统性缺陷

论文未讨论 extension 签名/supply chain；跨语言 host 的统一 capability 声明工具链成熟度。

## 局限与后续工作

- **局限 1**：平台绑定（ERIM、重写）限制可移植性。
- **Future work 1**：与 kernel eBPF 统一 policy 语言双向生成。
- **Future work 2**：ARM MTE/PAC 等隔离后端。

## 相关

- **同会议**：[[OSDI-2025]]
