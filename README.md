# 统一知识中枢助手 (LangChain + FastAPI + Vue3)

一个集成 **PDM 数据模型**、**代码仓库** 和 **数据库** 的智能问答与链路追踪助手。支持 PDM 文件解析、Java/Spring Boot 代码索引、MyBatis XML 解析、前端模板(hbs/jQuery)分析，以及跨层调用链追踪（Config → Controller → Service → Mapper → Table）。提供 **CLI 命令行**、**RESTful API** 和 **Web 前端界面** 三种交互方式。

---

## 项目结构

```
sirius-prods-helpers-test1/
│
├── backend/                        # 后端核心代码
│   ├── core/                       # 核心业务逻辑
│   │   ├── parser.py               # PDM XML 解析器
│   │   ├── indexer.py              # SQLite + ChromaDB 索引器（PDM）
│   │   ├── unified_indexer.py      # 统一索引器（PDM + 代码 + 配置）
│   │   ├── source_manager.py       # 知识源管理器（注册/同步/删除）
│   │   ├── code_parser.py          # 代码解析器（Java/XML/hbs/JS）
│   │   ├── config_parser.py        # 配置解析器（yml/properties/pom.xml）
│   │   ├── db_manager.py           # MySQL / Oracle 连接管理
│   │   ├── tools.py                # PDM / 数据库 Agent 工具集
│   │   ├── code_tools.py           # 代码搜索 Agent 工具集（含 GrepCodeTool）
│   │   ├── config_tools.py         # 配置查询 Agent 工具集
│   │   ├── trace_tools.py          # 链路追踪 Agent 工具集
│   │   └── conversation_manager.py # 多轮对话会话管理
│   ├── api/                        # FastAPI 接口层
│   │   ├── main.py                 # FastAPI 应用主入口
│   │   ├── routes/
│   │   │   ├── pdm.py              # PDM 查询相关接口
│   │   │   ├── conversation.py     # 会话管理接口
│   │   │   └── knowledge.py        # 知识源管理接口
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
├── run_api.py                      # 仅启动后端 API 服务（配合接口测试使用）
├── run_app.py                      # 前后台一键启动脚本（后端 API + 前台 Web）
├── files/                          # 存放 .pdm 文件
├── data/                           # SQLite 元数据 & Chroma 向量库 & Git 克隆仓库
├── requirements.txt                # Python 依赖
├── .env                            # 环境变量（勿提交）
└── .env_sample                     # 环境变量模板
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **AI / 后端** | Python 3.10+、FastAPI、LangChain、DeepSeek / Claude |
| **向量嵌入** | sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`，支持中英文) |
| **数据存储** | SQLite（元数据 + 代码索引 + 配置索引）、ChromaDB（向量检索）、MySQL / Oracle（业务库） |
| **代码解析** | javalang（Java AST）、lxml（XML/MyBatis）、pyyaml（YAML 配置）、GitPython（仓库同步） |
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
| `REPOS_DIR` | Git 克隆仓库存放目录 | `./data/repos` |
| `CODE_CHUNK_MAX_LINES` | 代码片段最大行数 | `100` |
| `CODE_INDEX_EXTENSIONS` | 索引的文件扩展名（逗号分隔） | `.java,.js,.hbs,.xml,.yml,.yaml,.properties` |
| `LOCAL_CODE_DIR` | 本地 Java 项目路径（用于代码索引） | - |
| `MODEL_NAME` | 嵌入模型名称 | `paraphrase-multilingual-MiniLM-L12-v2` |

### 4. 索引 PDM 文件

将 `.pdm` 文件放入 `files/` 目录，执行索引：

```bash
python indexer.py
```

### 5. 索引代码仓库

先在 `.env` 中配置 `LOCAL_CODE_DIR` 为你的 Java 项目路径，然后执行：

```bash
# 首次索引（增量模式，自动跳过未变化的文件）
python scripts/index_code.py

# 或手动指定路径（不依赖 .env）
python scripts/index_code.py --path /your/java/project/path

# 全量重建索引（清除旧数据后重新索引）
python scripts/index_code.py --reindex

# 查看已注册的知识源列表
python scripts/index_code.py --list
```

> **说明**：索引脚本支持增量更新，通过文件 MD5 自动跳过未变化的文件。日常使用直接运行 `python scripts/index_code.py` 即可，仅处理新增和修改的文件。

### 6. 安装前端依赖

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

提供两种启动脚本，按需选择：

| 脚本 | 用途 |
|------|------|
| `python run_api.py` | 仅启动后端 API，适合配合 `test_api.sh` 做接口测试 |
| `python run_app.py` | 前后台一键启动，日常开发推荐 |

**▸ 仅启动后端（接口调试）**

```bash
source .venv/bin/activate
python run_api.py
```

**▸ 前后台一键启动（日常开发）**

```bash
source .venv/bin/activate
python run_app.py
```

启动后访问：
- **前台 Web 界面**：http://localhost:5173
- **Swagger UI 文档**：http://localhost:8001/docs
- **ReDoc 文档**：http://localhost:8001/redoc
- **健康检查**：http://localhost:8001/health

> 如需单独手动启动前台：

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

### PDM / 数据库工具

| 工具 | 说明 |
|------|------|
| `list_tables` | 列出 PDM 中所有的表 |
| `search_tables` | 语义搜索（例如："查找与支付相关的表"） |
| `get_table_schema` | 获取指定表的详细字段信息 |
| `find_relationships` | 追踪外键关联关系 |
| `execute_sql` | 在 MySQL / Oracle 上直接执行 SQL 查询 |

### 代码搜索工具

| 工具 | 说明 |
|------|------|
| `search_code` | 语义搜索代码片段（类、方法、模板等） |
| `grep_code` | 精确关键词搜索（类似 grep，支持 icon 名、CSS class、变量名等） |
| `get_code_structure` | 获取文件的代码结构（类/方法/字段列表） |
| `get_class_detail` | 获取指定类的详细信息（注解、方法、字段） |
| `search_api_endpoints` | 搜索 Spring REST API 端点 |

### 配置查询工具

| 工具 | 说明 |
|------|------|
| `config_lookup` | 配置项查找（先精确匹配 key，再语义搜索） |
| `list_configs` | 按知识源/文件/profile 聚合查看配置文件概览 |

### 链路追踪工具

| 工具 | 说明 |
|------|------|
| `trace_component` | 追踪组件完整调用链（Config → Controller → Service → Mapper → Table） |
| `find_config_usage` | 查找引用指定配置键的所有代码位置 |
| `find_table_usage` | 查找引用指定数据库表的所有代码（MyBatis/注解等） |

---

## 知识源管理

系统支持三种类型的知识源：

| 类型 | 说明 | 示例 |
|------|------|------|
| `pdm` | PowerDesigner 数据模型文件 | `./files/` 目录下的 `.pdm` 文件 |
| `git` | Git 远程仓库（自动 clone/pull） | Java/Spring Boot 项目的 Git URL |
| `local` | 本地代码目录 | 本地磁盘上的 Java 项目路径 |

### 代码索引支持的文件类型

| 文件类型 | 解析策略 |
|----------|---------|
| `.java` | javalang AST 解析，提取包/类/方法/字段/注解/Spring 路径映射 |
| `.xml` | MyBatis Mapper XML → 提取 SQL 语句及引用的表名；pom.xml → 依赖信息 |
| `.hbs` | Handlebars 模板 → partial 引用、表单 action、模板变量 |
| `.js` | jQuery/JS → AJAX API 调用、函数定义、DOM 事件绑定 |
| `.yml/.yaml` | Spring Boot 配置 → 递归扁平化 key-value（如 `spring.datasource.url`），自动识别 profile |
| `.properties` | Java properties → key=value 解析，支持注释提取 |

### 通过代码注册知识源

```python
from backend.core.source_manager import source_manager
from backend.core.unified_indexer import unified_indexer

# 注册一个本地 Java 项目
source_id = source_manager.register_source(
    name="My Java Project",
    source_type="local",
    location="/path/to/java/project",
)

# 触发索引
unified_indexer.index_source(source_id)
```

---

## 知识源管理 API `/api/knowledge-sources/`

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/knowledge-sources` | 注册知识源 |
| `GET` | `/api/knowledge-sources` | 列出所有知识源 |
| `GET` | `/api/knowledge-sources/{id}` | 知识源详情（含索引统计） |
| `DELETE` | `/api/knowledge-sources/{id}` | 删除知识源及其索引数据 |
| `POST` | `/api/knowledge-sources/{id}/index` | 触发后台索引（全量重建） |
| `POST` | `/api/knowledge-sources/{id}/sync` | 同步代码（Git pull / 验证路径） |
| `GET` | `/api/knowledge-sources/{id}/stats` | 索引统计（chunks / configs / cross-refs / files） |

**示例：注册并索引本地项目**

```bash
# 1. 注册知识源
curl -X POST http://localhost:8001/api/knowledge-sources \
  -H "Content-Type: application/json" \
  -d '{"name": "my-project", "source_type": "local", "location": "/path/to/java/project"}'

# 2. 触发索引
curl -X POST http://localhost:8001/api/knowledge-sources/{source_id}/index

# 3. 查看索引统计
curl http://localhost:8001/api/knowledge-sources/{source_id}/stats
```

---

## 会话持久化

- 所有会话历史自动保存到 `data/conversations.json`
- 程序重启后自动恢复，无需重新开始对话
- CLI、API 和前端 Web 共享同一个会话存储文件

---

## 更新日志

### Phase 2 — v2.0.0（2026-03-18）

**中文搜索优化 + 精确搜索 + 配置解析 + 知识源管理 API**

#### 新功能

- **中文语义搜索支持**：将嵌入模型从 `ONNXMiniLM_L6_V2`（仅英文）切换为 `paraphrase-multilingual-MiniLM-L12-v2`（多语言），中文查询如"查找处理订单的代码"现在可以正确匹配到 `BillOrder*` 等 Java 类
- **精确关键词搜索**（`GrepCodeTool`）：新增 `grep_code` 工具，支持在代码内容中精确搜索 icon 名、CSS class、变量名等关键词。当 SQLite 存储的内容被截断时，自动回退到源文件搜索
- **配置文件结构化解析**（`ConfigParser`）：新增 `config_parser.py`，支持 application.yml/properties 递归扁平化为 key-value、从文件名自动提取 profile（如 `application-dev.yml` → `dev`）、pom.xml 依赖解析
- **配置查询工具**（`ConfigLookupTool` / `ListConfigsTool`）：新增 `config_tools.py`，Agent 可按 key 精确查找或语义搜索配置项
- **知识源管理 REST API**：新增 `knowledge.py` 路由，提供 7 个端点（注册/列表/详情/删除/索引/同步/统计）

#### 改进

- `code_parser.py`：hbs/js 文件 content 存储上限从 3000 提升至 5000 字符
- `unified_indexer.py`：新增 `_get_or_recreate_collection()` 方法，自动处理嵌入模型切换导致的 ChromaDB collection 冲突
- `unified_indexer.py`：新增 SQLite schema 向后兼容迁移（`ALTER TABLE` 添加缺失列）
- `conversation.py`：Agent system_message 更新为四大类工具，新增工具使用指导原则
- 前端标题从"PDM 智能助手"更名为"知识中枢助手"

#### 兼容性备注

> 本次升级因开发机为 **macOS x86_64**，PyTorch 2.4+ 无对应 wheel 包，无法使用最新版 `sentence-transformers`。因此降级使用 **`sentence-transformers==3.0.1`** 搭配 **`transformers<4.46`**，以兼容系统自带的 PyTorch 2.2.2。功能不受影响，嵌入维度同为 384 维。若在 Linux 或 Apple Silicon (arm64) 环境部署，可升级至最新版 `sentence-transformers` 以获得更好性能。

#### 索引统计（Phase 2 重建后）

| 指标 | 数量 |
|------|------|
| 索引文件数 | 5,929 |
| 代码片段（code_chunks） | 48,527 |
| 配置条目（config_entries） | 745 |
| 跨层引用（cross_references） | 11,988 |

### Phase 1 — v1.0.0

**统一知识源框架 + Java/XML/hbs/JS 代码解析索引**

- 统一索引器（`unified_indexer.py`）：管理 SQLite schema 扩展 + ChromaDB 多 Collection
- 代码解析器（`code_parser.py`）：支持 Java/MyBatis XML/hbs/jQuery JS 四类文件
- 链路追踪工具（`trace_tools.py`）：Config → Controller → Service → Mapper → Table 全链路追踪
- 知识源管理器（`source_manager.py`）：注册/同步/删除知识源
- 增量索引：基于文件 MD5 自动跳过未变化文件
