# PDM 智能助手 (LangChain + FastAPI + Vue3)

一个专门用于解析、索引和查询 PowerDesigner 物理数据模型 (.pdm) 文件的智能助手，支持 **CLI 命令行**、**RESTful API** 和 **Web 前端界面** 三种交互方式。

---

## 项目结构

```
sirius-prods-helpers-test1/
│
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
│
├── frontend/                       # 前端 Web 界面 (Vue3 + Vite)
│   ├── index.html                  # HTML 入口
│   ├── package.json                # npm 依赖配置
│   ├── vite.config.js              # Vite 配置（含 API 代理）
│   └── src/
│       ├── main.js                 # Vue 应用入口
│       ├── App.vue                 # 根组件
│       ├── assets/main.css         # 全局样式
│       ├── api/
│       │   ├── index.js            # Axios 实例封装
│       │   └── conversation.js     # 会话 API（含流式接口预留）
│       ├── stores/
│       │   └── conversation.js     # Pinia 状态管理
│       ├── router/index.js         # Vue Router
│       ├── views/
│       │   └── HomeView.vue        # 主布局（顶栏 + 左右分栏）
│       └── components/
│           ├── SessionList.vue     # 左侧：会话列表管理
│           ├── ChatWindow.vue      # 右侧：聊天主窗口
│           ├── MessageBubble.vue   # 消息气泡（Markdown 渲染）
│           └── MessageInput.vue    # 底部输入框
│
├── app.py                          # CLI 命令行入口
├── run_api.py                      # API 服务快捷启动脚本
├── files/                          # 存放 .pdm 文件
├── data/                           # SQLite 元数据 & Chroma 向量库
├── requirements.txt                # Python 依赖
├── .env                            # 环境变量（勿提交）
└── .env_sample                     # 环境变量模板
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **AI / 后端** | Python 3.10+、FastAPI、LangChain、DeepSeek / Claude |
| **数据存储** | SQLite（元数据）、ChromaDB（向量检索）、MySQL / Oracle（业务库） |
| **前端** | Vue 3、Vite、Element Plus、Pinia、Axios |

---

## 安装与配置

### 1. 环境要求

- **Python 3.10+**
- **Node.js 18+**

### 2. Python 环境

```bash
# 创建虚拟环境
python3 -m venv .venv

# 激活虚拟环境（macOS/Linux）
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
# 或使用 uv
uv pip install -r requirements.txt
```

### 3. 环境变量配置

复制 `.env_sample` 为 `.env` 并填写配置：

```bash
cp .env_sample .env
```

主要配置项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `LLM_PROVIDER` | LLM 提供商：`deepseek` 或 `claude` | `deepseek` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | - |
| `ANTHROPIC_AUTH_TOKEN` | Claude API Key | - |
| `ANTHROPIC_BASE_URL` | Claude 代理地址（可选） | - |
| `CLAUDE_MODEL` | Claude 模型名称 | `claude-4.6-sonnet` |
| `API_HOST` | API 监听地址 | `127.0.0.1` |
| `API_PORT` | API 端口 | `8001` |
| `CORS_ORIGINS` | 允许跨域的地址（多个用逗号分隔） | `*` |
| `SQLITE_DB_PATH` | SQLite 数据库路径 | `./data/metadata.db` |
| `CHROMA_DB_PATH` | ChromaDB 向量库路径 | `./data/chroma_db` |
| `PDM_FILES_DIR` | PDM 文件目录 | `./files` |
| `MAX_MESSAGES_PER_SESSION` | 每个会话最大消息数 | `50` |
| `MYSQL_URL` | MySQL 连接串 | - |
| `ORACLE_URL` | Oracle 连接串 | - |

### 4. 索引 PDM 文件

将 `.pdm` 文件放入 `files/` 目录，执行索引：

```bash
python indexer.py
```

### 5. 安装前端依赖

```bash
cd frontend
npm install
```

---

## 启动方式

### 方式一：CLI 命令行模式

```bash
source .venv/bin/activate
python app.py
```

#### CLI 交互命令

| 命令 | 说明 |
|------|------|
| `/new [名称]` | 创建新会话（可选指定名称） |
| `/sessions` | 列出所有会话 |
| `/switch <ID>` | 切换到指定会话（ID 前 8 位即可） |
| `/history [N]` | 查看当前会话对话历史（可选：只显示最近 N 条） |
| `/clear` | 清空当前会话的对话历史 |
| `/delete <ID>` | 删除指定会话 |
| `/status` | 显示当前会话详细状态 |
| `/help` | 显示所有可用命令 |

---

### 方式二：API + 前端 Web 界面（推荐）

**步骤 1**：启动后端 API 服务（端口由 `.env` 的 `API_PORT` 控制，默认 `8001`）

```bash
# 激活虚拟环境
source .venv/bin/activate

# 启动后端
python run_api.py
```

启动后访问：
- **Swagger UI 文档**：http://localhost:8001/docs
- **ReDoc 文档**：http://localhost:8001/redoc
- **健康检查**：http://localhost:8001/health

**步骤 2**：启动前端开发服务器

```bash
cd frontend
npm run dev
```

打开浏览器访问：**http://localhost:5173**

> **说明**：Vite 开发服务器已配置 `/api` → `http://127.0.0.1:8001` 的反向代理，无需配置跨域。

---

## 前端功能介绍

前端采用**左右分栏**布局：

| 区域 | 功能 |
|------|------|
| **左侧 - 会话列表** | 新建 / 重命名 / 删除会话；显示消息数量和更新时间；高亮当前激活会话 |
| **右侧 - 聊天窗口** | 消息历史展示（支持 Markdown + 代码高亮）；快捷问题推荐；自动滚底 |
| **底部 - 输入框** | Enter 发送 / Shift+Enter 换行；AI 回复时显示打字动画；流式模式支持终止 |
| **顶栏** | 流式 / 普通响应模式一键切换；快捷跳转 API 文档 |

### 流式响应说明

- **普通模式**（默认）：等待 AI 完整回复后一次性展示，同时显示打字动画
- **流式模式**：AI 逐字输出，实时展示（需要后端实现 SSE 流式端点 `/messages/stream`）

流式接口已在前端预留（`src/api/conversation.js → sendMessageStream`），后端实现后自动生效。

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

**示例：语义搜索**

```bash
curl -X POST http://localhost:8001/api/pdm/search \
  -H "Content-Type: application/json" \
  -d '{"query": "用户信息", "n_results": 5}'
```

**示例：执行 SQL**

```bash
curl -X POST http://localhost:8001/api/pdm/sql/execute \
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
| `GET` | `/api/conversations/{session_id}/history` | 获取消息历史 |
| `POST` | `/api/conversations/{session_id}/messages` | 发送消息（AI 对话） |
| `DELETE` | `/api/conversations/{session_id}/history` | 清空会话历史 |
| `DELETE` | `/api/conversations/{session_id}` | 删除会话 |

**示例：创建会话并对话**

```bash
# 1. 创建会话
SESSION=$(curl -s -X POST http://localhost:8001/api/conversations \
  -H "Content-Type: application/json" \
  -d '{"name": "项目分析"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['session_id'])")

# 2. 发送消息
curl -X POST "http://localhost:8001/api/conversations/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"message": "有哪些与用户相关的表？"}'
```

---

## Agent 工具集

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
- CLI、API 和前端 Web 共享同一个会话存储文件
