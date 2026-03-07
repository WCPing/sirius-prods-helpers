# CLAUDE.md

## 开发环境说明

本项目使用 [uv](https://github.com/astral-sh/uv) 作为 Python 包管理工具。

## 重要规范

### 安装 Python 包

**必须使用 `uv pip` 安装所有 Python 包，禁止直接使用 `pip` 命令。**

```bash
# ✅ 正确方式
uv pip install <package-name>
uv pip install -r requirements.txt

# ❌ 错误方式（禁止使用）
pip install <package-name>
pip install -r requirements.txt
```

### 常用 uv 命令

```bash
# 安装单个包
uv pip install requests

# 安装多个包
uv pip install requests pandas numpy

# 从 requirements.txt 安装依赖
uv pip install -r requirements.txt

# 卸载包
uv pip uninstall <package-name>

# 列出已安装的包
uv pip list

# 查看包信息
uv pip show <package-name>
```

### 环境初始化

```bash
# 创建虚拟环境
uv venv

# 激活虚拟环境（macOS/Linux）
source .venv/bin/activate

# 激活虚拟环境（Windows）
.venv\Scripts\activate
```
