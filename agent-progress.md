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
