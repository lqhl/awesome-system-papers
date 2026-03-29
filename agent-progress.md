# Agent Progress Log

## 2025-03-27

### 任务: 创建 MLSys 论文下载脚本

**完成内容:**
1. 创建了 `scripts/download_mlsys_papers.py` 脚本
2. 成功下载了 MLSys 2025 全部 61 篇论文到 `mlsys-2025/` 目录
3. 总大小: 112 MB

**脚本特性:**
- 自动检测并使用环境变量中的 HTTP/HTTPS 代理 (`http_proxy`/`https_proxy`)
- 支持并行下载（默认 5 个线程，可通过命令行参数调整）
- 自动跳过已存在的文件
- 验证 PDF 文件完整性（检查文件头和大小）

**使用方法:**
```bash
# 基本用法
python3 scripts/download_mlsys_papers.py 2025 mlsys-2025

# 使用 10 个并行线程
python3 scripts/download_mlsys_papers.py 2025 mlsys-2025 10
```

**遇到的问题与解决方案:**
- 问题: 单个线程下载速度慢
- 解决: 使用 `concurrent.futures.ThreadPoolExecutor` 实现并行下载

- 问题: 需要翻墙访问 proceedings.mlsys.org
- 解决: 脚本自动检测并使用环境变量中的代理配置

**MLSys 2025 URL 格式:**
- 论文列表: `https://proceedings.mlsys.org/paper_files/paper/{year}`
- PDF 下载: `https://proceedings.mlsys.org/paper_files/paper/{year}/file/{hash}-Paper-Conference.pdf`

## 2025-03-29

### 任务: 使用 browser-tools 下载 SOSP 2025 论文

**完成内容:**
1. 使用 `browser-tools` skill 通过 Chrome 浏览器访问 ACM Digital Library
2. 成功下载 SOSP 2025 全部 60 篇论文到 `sosp-2025/` 目录
3. 总大小: 108 MB

**关键步骤:**
1. 启动 Chrome with user profile: `browser-start.js --profile`
2. 导航到 ACM proceedings 页面: `https://dl.acm.org/doi/proceedings/10.1145/3731569`
3. 点击 "Show All (+36)" 按钮加载全部论文
4. 提取所有 DOI: 使用 `browser-eval.js` 获取 `.issue-item` 中的链接
5. 批量下载: 对每个 DOI，构造 PDF URL (`https://dl.acm.org/doi/pdf/{doi}?download=true`)
6. 浏览器会自动下载 PDF 到 Downloads 目录
7. 移动文件: 将 Downloads 中的 PDF 移动到 `sosp-2025/` 目录

**重要发现:**
- ACM Digital Library 直接访问 PDF URL 会返回 403 Forbidden（需要认证）
- 使用 Chrome 浏览器（with user profile）可以绕过限制，通过 Cloudflare 验证
- Cloudflare 验证流程:
  1. 访问 PDF URL 会显示 "请稍候..." 验证页面
  2. 页面自动通过 JavaScript 提交表单
  3. 浏览器开始下载 PDF 文件
- PDF 文件默认下载到 `~/Downloads/` 目录，文件名格式: `3731569.xxxxxx.pdf`

**脚本位置:** `scripts/download_sosp_papers.py`

**使用方法:**
```bash
# 确保 Chrome 已在运行 (with profile)
~/.agents/skills/browser-tools/browser-start.js --profile

# 运行下载脚本
python3 scripts/download_sosp_papers.py sosp-2025
```

**ACM DL URL 格式:**
- Proceedings 页面: `https://dl.acm.org/doi/proceedings/10.1145/3731569`
- PDF 下载: `https://dl.acm.org/doi/pdf/{doi}?download=true`
  - 例: `https://dl.acm.org/doi/pdf/10.1145/3731569.3764818?download=true`

**遇到的问题与解决方案:**
- 问题: ACM proceedings 页面默认只显示 30 篇论文
- 解决: 需要点击 "Show All (+36)" 按钮加载全部 60 篇论文

- 问题: browser-nav.js 有时会返回 ERR_ABORTED 错误
- 解决: 这个错误通常意味着 PDF 下载已经开始，可以忽略错误并检查 Downloads 目录

- 问题: 下载的 PDF 文件散落在 ~/Downloads 目录
- 解决: 脚本自动检测并移动文件到目标目录

**browser-tools 使用技巧:**
1. 始终使用 `--profile` 模式启动 Chrome 以保留登录状态
2. 使用 `browser-eval.js` 执行 JavaScript 来提取页面数据
3. 对于动态加载的内容，使用 `sleep` 等待页面加载完成
4. 使用 `window.scrollTo(0, document.body.scrollHeight)` 触发懒加载

### 任务: 使用 browser-tools 下载 SOSP 2024 论文

**完成内容:**
1. 成功下载 SOSP 2024 全部 43 篇论文到 `sosp-2024/` 目录
2. 总大小: 76 MB

**关键信息:**
- SOSP 2024 (第30届) Proceedings DOI: `10.1145/3694715`
- 论文数量: 43 篇（比 SOSP 2025 少 17 篇）
- 会议地点: Austin, TX, USA
- 会议时间: November 4-6, 2024

**下载方法:**
使用与 SOSP 2025 相同的方法:
1. 访问 ACM proceedings 页面: `https://dl.acm.org/doi/proceedings/10.1145/3694715`
2. 点击 "Show All (+13)" 按钮加载全部论文
3. 提取 DOI 并批量下载

**脚本位置:** `scripts/download_sosp_2024_papers.py`

**ACM DL URL 格式:**
- Proceedings 页面: `https://dl.acm.org/doi/proceedings/10.1145/3694715`
- PDF 下载: `https://dl.acm.org/doi/pdf/{doi}?download=true`
  - 例: `https://dl.acm.org/doi/pdf/10.1145/3694715.3695942?download=true`

**SOSP 2024 论文主题分布:**
- ML/AI 系统: 10+ 篇 (大模型训练/推理、并行计算)
- 分布式系统: 8+ 篇 (容错、一致性、存储)
- Serverless/云原生: 6+ 篇
- 安全/验证: 5+ 篇
- 内核/OS: 5+ 篇
- 隐私: 3+ 篇
