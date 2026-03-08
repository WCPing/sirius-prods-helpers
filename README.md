# PDM 智能助手 (基于 LangChain + FastAPI)

一个专门用于解析、索引和查询 PowerDesigner 物理数据模型 (.pdm) 文件的智能助手，支持 **CLI 命令行** 和 **RESTful API** 两种交互方式。

---

## 项目结构

```
sirius-prods-helpers-test1/
├── backend/                        # 后端核心代码
│   ├── core/                       # 核心业务逻辑
│   │   ├── parser.py               # PDM XML 解析器
│   │   ├── indexer.py              # SQLite + ChromaDB 索引器
│   │   ├── db_manager.py           # MySQL / Oracle 连接管理
│   │   ├── tools.py                # LangChain Agent 工具集
│   │   └── conversation_manager.py # 多轮对话会话管理
│   ├── api/                        # FastAPI 接口层
│   │   ├── main.py                 # FastAPI 应用主入口
│   │   ├── routes/
│   │   │   ├── pdm.py              # PDM 查询相关接口
│   │   │   └── conversation.py     # 会话管理接口
│   │   └── models/
│   │       ├── request.py          # Pydantic 请求模型
│   │       └── response.py         # Pydantic 响应模型
│   └── config.py                   # 统一配置管理
├── app.py                          # CLI 命令行入口
├── files/                          # 存放 .pdm 文件
├── data/                           # SQLite 元数据 & Chroma 向量库
├── requirements.txt
├── .env
└── .env_sample
```

---

## 安装与配置

### 1. 环境要求

- **Python 3.10+**

### 2. 虚拟环境与依赖安装

```bash
# 创建虚拟环境
python3.10 -m venv .venv

# 激活虚拟环境 (macOS/Linux)
source .venv/bin/activate

# 安装依赖（包含 FastAPI）
uv pip install -r requirements.txt
```

### 3. 环境变量配置

复制 `.env_sample` 为 `.env` 并填写相关配置：

```bash
cp .env_sample .env
```

主要配置项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `LLM_PROVIDER` | LLM 提供商：`deepseek` 或 `claude` | `deepseek` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | - |
| `ANTHROPIC_AUTH_TOKEN` | Claude API Key | - |
| `API_HOST` | API 服务监听地址 | `127.0.0.1` |
| `API_PORT` | API 服务端口 | `8000` |
| `CORS_ORIGINS` | 允许跨域的前端地址，多个用逗号分隔 | `*` |
| `SQLITE_DB_PATH` | SQLite 数据库路径 | `./data/metadata.db` |
| `CHROMA_DB_PATH` | ChromaDB 向量库路径 | `./data/chroma_db` |
| `PDM_FILES_DIR` | PDM 文件目录 | `./files` |
| `MAX_MESSAGES_PER_SESSION` | 每个会话最大消息数 | `50` |

### 4. 索引 PDM 文件

将 `.pdm` 文件放入 `files/` 目录，然后运行索引器：

```bash
python indexer.py
```

---

## 启动方式

### 方式一：CLI 命令行模式

```bash
python app.py
```

#### CLI 交互命令

| 命令 | 说明 |
|------|------|
| `/new [名称]` | 创建新会话（可选指定名称） |
| `/sessions` | 列出所有会话 |
| `/switch <ID>` | 切换到指定会话（ID 前 8 位即可） |
| `/history [N]` | 查看当前会话的对话历史（可选：只显示最近 N 条） |
| `/clear` | 清空当前会话的对话历史 |
| `/delete <ID>` | 删除指定会话 |
| `/status` | 显示当前会话的详细状态 |
| `/help` | 显示所有可用命令 |

### 方式二：API 服务模式

端口等配置通过 `.env` 文件控制（`API_HOST`、`API_PORT`），**无需硬编码**：

```bash
# 推荐：直接运行快捷启动脚本，自动读取 .env 中的端口配置
python run_api.py
```

启动后根据 `.env` 中配置的端口访问（默认 8000）：
- **Swagger UI 文档**：http://localhost:{API_PORT}/docs
- **ReDoc 文档**：http://localhost:{API_PORT}/redoc
- **健康检查**：http://localhost:{API_PORT}/health

---

## API 接口说明

### PDM 查询接口 `/api/pdm/`

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/pdm/tables` | 列出所有已索引的数据表 |
| `GET` | `/api/pdm/tables/{table_code}` | 获取表结构详情（字段、类型、注释） |
| `POST` | `/api/pdm/search` | 语义搜索表（支持中英文自然语言） |
| `GET` | `/api/pdm/relationships/{table_code}` | 查询表的外键关联关系 |
| `POST` | `/api/pdm/sql/execute` | 在 MySQL / Oracle 上执行 SQL |
| `GET` | `/api/pdm/indexer/status` | 查询当前索引状态 |
| `POST` | `/api/pdm/indexer/reindex` | 后台重建 PDM 文件索引 |

#### 示例：语义搜索

```bash
curl -X POST http://localhost:8000/api/pdm/search \
  -H "Content-Type: application/json" \
  -d '{"query": "用户信息", "n_results": 5}'
```

#### 示例：执行 SQL

```bash
curl -X POST http://localhost:8000/api/pdm/sql/execute \
  -H "Content-Type: application/json" \
  -d '{"db_type": "mysql", "sql": "SELECT * FROM users LIMIT 5"}'
```

---

### 会话管理接口 `/api/conversations/`

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/conversations` | 列出所有会话 |
| `POST` | `/api/conversations` | 创建新会话 |
| `GET` | `/api/conversations/{session_id}` | 获取会话详情 |
| `GET` | `/api/conversations/{session_id}/history` | 获取会话消息历史 |
| `POST` | `/api/conversations/{session_id}/messages` | 发送消息（AI 对话） |
| `DELETE` | `/api/conversations/{session_id}/history` | 清空会话历史 |
| `DELETE` | `/api/conversations/{session_id}` | 删除会话 |

#### 示例：创建会话并对话

```bash
# 1. 创建会话
SESSION=$(curl -s -X POST http://localhost:8000/api/conversations \
  -H "Content-Type: application/json" \
  -d '{"name": "项目分析"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['session_id'])")

# 2. 发送消息
curl -X POST "http://localhost:8000/api/conversations/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "有哪些与用户相关的表？"}'
```

---

## 包含的工具

| 工具 | 说明 |
|------|------|
| `list_tables` | 列出 PDM 中所有的表 |
| `search_tables` | 语义搜索（例如："查找与支付相关的表"） |
| `get_table_schema` | 获取指定表的详细字段信息 |
| `find_relationships` | 追踪外键关联关系 |
| `execute_sql` | 在 MySQL / Oracle 上直接执行 SQL 查询 |

---

## 会话持久化

- 所有会话历史自动保存到 `data/conversations.json`
- 程序重启后自动恢复，无需重新开始对话
- CLI 和 API 模式共享同一个会话存储文件
