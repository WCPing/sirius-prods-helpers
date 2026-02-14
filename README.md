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



```
1. 建立“元数据-数据”的桥梁 🌉
PDM 作为地图：我们解析出的 PDM CODE 通常对应数据库的表名，Comment 对应业务含义。
Text-to-SQL：当用户问“上个月支付成功的订单有哪些”时，Agent 先在 PDM 元数据中找到“订单表”和“状态字段”，然后基于这些信息生成准确的 SQL。
2. 技术栈升级 🛠️
统一接口：引入 SQLAlchemy，它可以一套代码同时适配 MySQL 和 Oracle。
驱动支持：Oracle 需要 oracledb，MySQL 需要 pymysql。
安全沙箱：必须配置只读权限（Read-only User），并在 Agent 中增加 SQL 拦截逻辑，防止产生破坏性操作。
3. 三级查询逻辑 🔍
语义层（现在的能力）：通过 PDM 注释找到“是哪张表”。
结构层（现在的能力）：确认该表有哪些字段、主外键。
数据层（未来的能力）：利用前两步的信息，生成 SQL 并去 MySQL/Oracle 抓取前 10 行数据或统计结果。
4. 解决“模型对不齐”问题 📏
数据库实际环境可能会由于手工修改而导致与 PDM 文档不一致（Schema Drift）。升级后的助手可以对比“PDM 里的定义”和“数据库里的真实定义”，提醒用户哪里的注释缺失或字段已废弃。
如果您准备好进入下一阶段的开发，我们可以从配置数据库连接库和编写第一个 SQL 执行工具开始。期待您的进一步指令！
```