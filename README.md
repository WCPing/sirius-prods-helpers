# PDM 智能助手 (基于 LangChain)

一个专门用于解析、索引和查询 PowerDesigner 物理数据模型 (.pdm) 文件的智能助手。

## 项目结构
- `files/`: 存放您的 `.pdm` 文件。
- `data/`: 存储 SQLite 元数据和 Chroma 向量数据库。
- `parser.py`: 用于提取 PDM 结构的 XML 解析逻辑。
- `indexer.py`: 将数据持久化到 SQLite 和 Chroma。
- `tools.py`: 为 Agent 提供的 LangChain 查询工具。
- `app.py`: 智能助手的交互主程序入口。

## 安装与配置指引

### 1. 环境要求
- **Python 3.10+** (LangChain 和 ChromaDB 的必要要求)。
- 您当前系统的 Python 3.7 版本过低，请务必在 3.10+ 的虚拟环境中运行。

### 2. 虚拟环境设置
```bash
# 创建虚拟环境
python3.10 -m venv venv

# 激活虚拟环境 (macOS/Linux)
source .venv/bin/activate

# 安装依赖
uv pip install -r requirements.txt
```

### 3. 配置
1. 打开 `.env` 文件。
2. 填写您的 `DEEPSEEK_API_KEY`（用于 Agent 对话）和 `OPENAI_API_KEY`（目前用于向量嵌入 Embeddings）。
3. (可选) 根据需要调整数据库路径。

> [!NOTE]
> 为了兼容 Intel Mac 并减小安装体积，项目已从本地 PyTorch 切换为 OpenAI 嵌入模型（text-embedding-3-small）。

### 4. 索引 PDM 文件
运行索引器处理 `files/` 文件夹下的所有 PDM 文件：
```bash
python indexer.py
```

### 5. 启动助手
```bash
python app.py
```

## 包含的工具
- `list_tables`: 概览模型中所有的表。
- `search_tables`: 概念搜索 (例如：“查找与支付相关的表”)。
- `get_table_schema`: 获取指定表的详细字段信息。
- `find_relationships`: 追踪外键关联关系。
