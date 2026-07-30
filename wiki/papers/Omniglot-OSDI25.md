---
type: paper
name: Omniglot
full_title: "Building Bridges: Safe Interactions with Foreign Languages through Omniglot"
authors: [Leon Schuermann, Jack Toubes, Tyler Potyondy, Pat Pannuto, Mae Milano, Amit Levy]
venue: OSDI
year: 2025
tags: [rust, ffi, memory-safety, type-safety, sandboxing]
source_pdf: "[[osdi25-schuermann.pdf]]"
source_md: "[[osdi25-schuermann]]"
review_status: complete
evidence_level: full-text
last_reviewed: 2026-07-30
---

# 搭建桥梁：通过 Omniglot 与外语进行安全交互（OSDI 2025）

> **原题**：Building Bridges: Safe Interactions with Foreign Languages through Omniglot

> **一句话总结**：Omniglot 是首个对未修改 C 库保持 Rust 全部 soundness 不变式（内存、类型、别名、并发）的 FFI 框架，用「弱化类型 + 延迟验证」避免 copy/serialization，性能接近 unchecked FFI，远优于同安全级别 copy 方案。

## 问题与动机

Rust 系统仍需调用 OpenSSL、lwIP 等 C 库。rust-bindgen 生成 `extern "C"` 把安全证明推给开发者——C 返回非法 bool、违反 aliasing XOR mutability、破坏 UTF-8 等即可让 Rust 出现本被类型系统禁止的 UB（如 enum niche filling 把 slice 当 CString）。隔离 alone 不够：语义差异在「正确」C 库上也会破坏 Rust soundness。

## 关键观察 / 隐含假设

- **观察 1**：维持 Rust soundness 不必证明整个 host+foreign 组合，只需 foreign 返回时用弱化类型（?bool）+ runtime validation 再 downcast——Figure 2 示例。
  - **依赖假设**：Rust 不变式目录（内存、别名、类型合法值、并发）可枚举且可运行时检查。
  - **可能失效场景**：高阶类型状态（typestate）写入 foreign 内存后不可验证——需符号句柄留在 Rust 侧。
- **观察 2**：内存隔离 + 仅当对象 wholly in foreign region 才允许 Rust 解引用 foreign 指针，可阻断 foreign 破坏 host 内存安全。
  - **依赖假设**：强 runtime（RISC-V PMP / x86 MPK）+ 限制 foreign 并发执行。
  - **可能失效场景**：弱 runtime（仅部分 MPK）时 threat model 降级为信任库不绕过隔离。
- **假设 1**：修改 rust-bindgen 生成 Omniglot binding 可让开发者几乎零改动接入。
  - **证据强度**：强；OpenSSL、zlib、lwIP 等案例。

## 核心方法

**弱化类型 + 验证**：foreign 返回 ?T，wrapper 验证 size/alignment/bit-pattern/高级不变式后 cast 为 T。

**Scopes**：编译期捕获 temporal 不变式（验证后 foreign 不得并发改写）。

**Sandbox runtime API**：OGRt::new、stack_alloc、setup_callback、invoke——foreign 调用后保证无残留 foreign 线程。

**实现**：嵌入式内核（PMP）+ Linux userspace（MPK）；rust-bindgen Omniglot 后端。

## 设计取舍

- **取舍 1**：runtime 验证开销换 compile-time 无法跨越 FFI 的证明——热路径仍低于 copy-based sandbox。
- **取舍 2**：不保证 C 库业务正确性，只保证 Rust soundness。
- **边界条件**：unmodified C 二进制；强 runtime 下对抗恶意库。

## 实验与结果

**指标与基线**：端到端执行时间与 foreign-call validation cost；对比 isolation-only、unsafe FFI 与 Sandcrust，限定为 Table 2/3 的 PMP/MPK 平台与任务（§6）。

**结果**：PMP 的 LittleFS 任务为 3742.8→3764µs，MPK 的 libpng 为 397.93→401.25µs，均相对 isolation-only（§6.1–6.2，Table 2）。

- vs 内存隔离 alone：Omniglot 开销可忽略。
- vs unchecked FFI：接近（具体 benchmark §6）。
- vs copy/serialize 同安全级别方案：显著更快。
- 案例：crypto、压缩、图像解码、TCP/IP、嵌入式内核组件。

## 论断—证据表

| 论断 | 证据 | 评测边界 | 置信度 |
|---|---|---|---|
| Soundness claim depends on strong runtime assumptions | threat model limits foreign concurrency and assumes strong memory protection (§4.1) | OGPMP-like strong runtime; OGMPK is weak against malicious mmap/syscall use | high |
| PMP validation adds little in stated tasks | Crypto 9145→9145µs, LittleFS 3742.8→3764µs, LwIP 78.71→81.4µs (§6.1, Table 2) | OpenTitan EarlGrey, named tasks | high |
| MPK validation adds little in listed one-shot tasks | Brotli 3.12→3.14ms, libsodium 51.61→53.41µs, libpng 397.93→401.25µs (§6.2, Table 2) | CloudLab single core, named inputs | high |
| Foreign-call invoke cost is bounded in microbenchmark | OGMPK 98.90ns vs unsafe FFI 13.74ns and Sandcrust 10.87µs (§6.3, Table 3) | immediate-return MPK microbenchmark | high |
| Validation cost depends on data/type | 8KB str: PMP 161.5µs, MPK 70.94µs (§6.3, Table 3) | u8/UTF-8 str only, not arbitrary invariants | high |

## 批判性分析

### 论证链条

「FFI 是 soundness 黑洞→弱化类型推迟证明→隔离+scopes」理论清晰，Listing 2 bool/enum 例子说服力强。首个 claim「all Rust soundness invariants」范围大，但 threat model 与 limitations 写得较诚实。

### 假设压力测试

- **已证明**：多库、双平台（embedded+Linux）性能与安全案例。
- **可能失效**：复杂回调生命周期 scopes 误用（unsafe 绕过）；validation 漏检新型 Rust 不变式；C++ exception 跨 FFI。
- **论文未覆盖**：timing side-channel（明确排除）；大规模 C++（非 C）语义。

### 实验可信度

与弱/强 baseline 分层对比合理。缺 formal 证明 validation 充分性；生产 OpenSSL 全 API 覆盖度未知。

### 系统性缺陷

开发者仍可能写 unsafe 绕过 Omniglot；bindgen 对复杂宏/泛型 C API 生成质量依赖上游；MPK 页粒度限制；验证失败 panic 的可用性策略论文未细讲。

## 局限与后续工作

- **局限 1**：弱 runtime 不能对恶意库保持同等保证。
- **局限 2**：typestate/复杂引用类型不可放 foreign 内存。
- **Future work 1**：C++ / ObjC bridge 与自动验证生成。
- **Future work 2**：formal 化 ?T→T 验证规则与 Miri/FFI 测试套件集成。

## 相关

- **相关概念**：FFI、memory safety、capability
- **同类系统**：rust-bindgen、RLBox、SWIG、NIF/NEVE 类隔离
- **同会议**：[[OSDI-2025]]
