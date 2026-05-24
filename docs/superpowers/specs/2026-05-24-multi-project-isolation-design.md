# 多项目隔离方案设计

- 日期：2026-05-24
- 范围：在现有"知识中枢助手"中引入"项目（Project）"作为顶层概念，使代码索引、向量库、数据库连接、会话上下文按项目隔离
- 状态：Approved（待 writing-plans 阶段拆解为实现计划）

---

## 1. 背景与目标

当前实现已支持多个 PDM 文件解析，但代码 / 数据库 / 配置层面只支持单一项目：

- `.env` 仅能配置一条 `MYSQL_URL`、`ORACLE_URL`、`LOCAL_CODE_DIR`
- `code_chunks`、`config_entries` 等表已带 `source_id`，但检索工具（`SearchCodeTool`、`GrepCodeTool` 等）查询时**未按 source_id 或 project 过滤**，跨项目串扰
- 会话与项目无绑定关系，无法限定"在项目 A 下问问题"

目标：

1. 同一套部署可同时管理 1~3 个项目（短期），架构上不阻塞未来扩到 10+
2. **默认隔离**：当前会话只查当前项目；通过显式开关允许单次跨项目查询
3. PDM 文件保持全局共享（不归属项目）
4. 老数据零损失，重启一次自动迁移到新模型

非目标（暂不在本 spec 范围）：

- DB 连接 URL 加密存储
- 项目间权限 / 多租户用户体系
- 项目导入导出

---

## 2. 关键决策（已与用户对齐）

| # | 决策 | 备注 |
|---|---|---|
| 1 | 项目数预期 1~3 个 | 不引入物理隔离，采用"共享存储 + metadata 过滤" |
| 2 | 默认隔离，可手动跨查 | 跨查通过单次消息粒度的开关触发 |
| 3 | 1 项目 = 最多 1 个 MySQL + 1 个 Oracle | 直接挂在 `projects` 表字段 |
| 4 | PDM 全局共享 | 现有 PDM 4 张表不动，PDM 工具不改 |
| 5 | 会话级项目绑定 | 新建会话强制选项目，绑定后不可改 |
| 6 | 工具过滤通过 ContextVar 隐式注入 | LLM 不可见、不可绕过 |
| 7 | 删除项目硬删除 + 级联清理 | 二次确认告知影响范围 |
| 8 | 会话存储从 JSON 迁移到 SQLite | 与 projects 外键关联，便于过滤 |
| 9 | 不自动备份 metadata.db | 通过 SQL 幂等 + Chroma 字段追加保证可回滚 |

---

## 3. 数据模型变更

### 3.1 新增表：`projects`

```sql
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    mysql_url   TEXT DEFAULT '',
    oracle_url  TEXT DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 新增表：`conversations`（替代 `conversations.json`）

```sql
CREATE TABLE IF NOT EXISTS conversations (
    session_id   TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL,
    name         TEXT DEFAULT '新的聊天',
    messages     TEXT DEFAULT '[]',
    max_messages INTEGER DEFAULT 50,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_conversations_project ON conversations(project_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at);
```

### 3.3 已有表加列

下列 5 张表加 `project_id TEXT DEFAULT ''` 及索引：

| 表 |
|---|
| `knowledge_sources` |
| `code_chunks` |
| `config_entries` |
| `cross_references` |
| `indexed_files` |

```sql
ALTER TABLE knowledge_sources ADD COLUMN project_id TEXT DEFAULT '';
ALTER TABLE code_chunks       ADD COLUMN project_id TEXT DEFAULT '';
ALTER TABLE config_entries    ADD COLUMN project_id TEXT DEFAULT '';
ALTER TABLE cross_references  ADD COLUMN project_id TEXT DEFAULT '';
ALTER TABLE indexed_files     ADD COLUMN project_id TEXT DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_knowledge_sources_project ON knowledge_sources(project_id);
CREATE INDEX IF NOT EXISTS idx_code_chunks_project       ON code_chunks(project_id);
CREATE INDEX IF NOT EXISTS idx_config_entries_project    ON config_entries(project_id);
CREATE INDEX IF NOT EXISTS idx_cross_references_project  ON cross_references(project_id);
CREATE INDEX IF NOT EXISTS idx_indexed_files_project     ON indexed_files(project_id);
```

ALTER 语句包裹 try/except 以兼容已有列（与现有 `unified_indexer._init_sqlite` 风格一致）。

### 3.4 ChromaDB metadata

`code_chunks`、`config_entries` 两个 collection 写入时 metadata 多写：

```python
{"project_id": "<uuid>", "source_id": ..., ...}  # 其他字段保留
```

集合本身**不拆**，靠 `where={"project_id": pid}` 过滤。PDM collection (`pdm_metadata`) 不动。

### 3.5 文件目录归类

```
data/
├── chroma_db/                  共享，metadata 过滤
├── metadata.db                 共享，project_id 列过滤
├── repos/{project_id}/{source_id}/    git clone 子目录隔离
└── conversations.json.migrated.bak    迁移后的旧 JSON 备份
files/                          PDM 全局共享，不变
```

`SourceManager._sync_git` 中 clone 路径从 `repos/{source_id}` 改为 `repos/{project_id}/{source_id}`。

---

## 4. 后端组件改造

### 4.1 新增模块：`backend/core/project_manager.py`

```python
class ProjectManager:
    def __init__(self): ...
    def create_project(name, description="", mysql_url="", oracle_url="") -> str
    def update_project(project_id, **fields) -> bool
    def delete_project(project_id) -> bool          # 级联删除
    def list_projects() -> List[dict]
    def get_project(project_id) -> dict | None
    def ensure_default_project() -> str             # 启动时调用
    def run_migration_if_needed() -> None           # 启动时调用
    def test_db_connection(project_id, db_type) -> tuple[bool, str]

# 模块级单例
project_manager = ProjectManager()
```

`delete_project` 实现：

1. 取出该项目下所有 `knowledge_sources.id`
2. 对每个 source 调 `source_manager.remove_source(sid)`（已实现：清理索引 + 注册记录 + clone 目录）
3. 删除该项目下所有 `conversations` 记录
4. 调 `db_manager.invalidate_project(project_id)` 释放 engine
5. `DELETE FROM projects WHERE id = ?`

### 4.2 改造 `backend/core/db_manager.py`

去掉启动时的全局 engine 初始化，改为按项目按需创建并缓存。

```python
class DBConnectionManager:
    def __init__(self):
        self._engines: Dict[str, Engine] = {}     # key = "{project_id}:{db_type}"

    def get_engine(self, project_id: str, db_type: str) -> Engine | None: ...
    def execute_query(self, project_id: str, db_type: str, sql: str, params: dict = None): ...
    def get_preview(self, project_id: str, db_type: str, table_name: str, limit: int = 5): ...
    def invalidate_project(self, project_id: str): ...
    def test_connection(self, db_type: str, url: str) -> tuple[bool, str]: ...   # 用于"测试连接"

db_manager = DBConnectionManager()
```

### 4.3 新增模块：`backend/core/agent_context.py`

```python
from contextvars import ContextVar
current_project_id: ContextVar[str | None] = ContextVar("current_project_id", default=None)
allow_cross_project: ContextVar[bool] = ContextVar("allow_cross_project", default=False)

def project_filter() -> str | None:
    """返回当前应过滤的 project_id，None 表示不过滤。"""
    if allow_cross_project.get():
        return None
    return current_project_id.get()
```

### 4.4 改造 Tool（强制过滤）

涉及文件：
- `backend/core/code_tools.py`
- `backend/core/config_tools.py`
- `backend/core/trace_tools.py`
- `backend/core/tools.py` 中的 `ExecuteSQLTool`

每个 Tool 内部统一引用 `agent_context.project_filter()`，对 SQLite 查询拼接 `AND project_id = ?`，对 Chroma 查询追加 `where={"project_id": pid}`。

`ExecuteSQLTool` 改为从 ContextVar 取 `project_id` 后调 `db_manager.execute_query(project_id, db_type, sql)`；不再依赖 `db_manager` 的全局 engine。

PDM 工具（`ListTablesTool`、`TableSchemaTool`、`SearchTablesTool`、`RelationshipTool`）**不改**。

### 4.5 改造 `unified_indexer.py`

写入侧：
- `index_source(source_id)` 内部先查 `knowledge_sources.project_id`，向下传给 `_store_chunks` / `_store_config_entries`
- 所有 SQLite INSERT 语句多写 `project_id`
- ChromaDB metadata 多写 `"project_id": pid`
- `_clear_source_data` 不变（仍按 source_id 清理）

### 4.6 改造 `source_manager.py`

- `register_source(name, source_type, location, project_id, branch="main", patterns="")` 增加 `project_id` 必填参数
- `_sync_git` 的 clone 目录使用 `repos/{project_id}/{source_id}`
- `ensure_pdm_source_registered` 不依赖 project_id（PDM 全局，project_id 留空）

### 4.7 改造 `conversation_manager.py`

- 持久化层从 JSON 改为 SQLite（操作 `conversations` 表）
- `new_session(project_id: str, name: str = "")` 必填 project_id
- `list_sessions(project_id: str | None = None)` 可按项目过滤
- `ConversationSession.to_dict()` / `from_dict()` 增加 `project_id` 字段

### 4.8 路由与请求/响应模型

新增路由 `backend/api/routes/projects.py`：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/projects` | 列出 |
| POST | `/api/projects` | 创建 |
| GET | `/api/projects/{id}` | 详情 |
| PATCH | `/api/projects/{id}` | 更新 name/desc/mysql_url/oracle_url |
| DELETE | `/api/projects/{id}` | 级联删除（二次确认在前端） |
| POST | `/api/projects/{id}/test-db` | 测试 DB 连接，请求体 `{db_type: "mysql"|"oracle"}` |

调整现有路由：

- `POST /api/conversations` 请求体加 `project_id: str`（必填）
- `POST /api/conversations/{id}/messages` 与 `.../messages/stream` 请求体加 `cross_project_query: bool = False`
- `POST /api/knowledge-sources` 请求体加 `project_id: str`（必填）
- `GET /api/knowledge-sources?project_id=xxx` 增加查询参数过滤
- `GET /api/conversations?project_id=xxx` 增加查询参数过滤

会话路由 `send_message` / `send_message_stream` 进入 Agent 调用前：

```python
session = conv_manager.sessions[session_id]
token1 = current_project_id.set(session.project_id)
token2 = allow_cross_project.set(body.cross_project_query)
try:
    response = agent.invoke(...)
finally:
    current_project_id.reset(token1)
    allow_cross_project.reset(token2)
```

---

## 5. 前端改造

### 5.1 新增页面：`views/ProjectsView.vue`（路由 `/projects`）

表格列：名称、描述、MySQL（已配置 / 未配置）、Oracle（已配置 / 未配置）、知识源数、会话数、操作（编辑、删除、测试连接）。

新增 / 编辑弹窗：name / description / mysql_url / oracle_url。
删除弹窗：二次确认，提示将清空 N 个知识源、M 个会话、所有索引数据。

### 5.2 改造 `views/KnowledgeView.vue`

顶部加项目筛选下拉。新增知识源弹窗强制选择项目（必填）。

### 5.3 改造会话相关组件

#### `components/SessionList.vue`
每个会话项显示项目徽章（项目名 + 颜色），颜色由 `project.id` hash 到固定调色板。

新建会话按钮改为弹窗：必选项目 + 可选名称。本次浏览器记住最近一次选择的项目（localStorage），下次默认选中。

#### `components/ChatWindow.vue`
顶部一行展示：
- 左：当前会话所属项目徽章（只读不可点）
- 右：跨查开关（红色样式 + ⓘ tooltip 解释作用）

#### `components/MessageInput.vue`
发送消息时附带 `cross_project_query` 字段，发送成功后**前端自动复位开关回 false**（单次粒度）。
该消息气泡上加 "🌐 跨项目" 标签便于区分。

### 5.4 新增 API client：`api/projects.js`

`listProjects` / `createProject` / `updateProject` / `deleteProject` / `testDb`。

### 5.5 Pinia store

新增 `stores/project.js`：缓存项目列表、提供 `getProjectName(id)`、`getProjectColor(id)`。

调整 `stores/conversation.js`：
- `currentProjectId` 派生自当前会话
- `createSession({ project_id, name })`
- `sendMessage(content, { crossProject = false })`

### 5.6 `views/HomeView.vue`

Header 右侧新增"📁 项目管理"入口按钮，与"知识源管理"、"API 文档"平级。

### 5.7 路由

`router/*` 注册 `/projects` 路由。

---

## 6. 迁移与初始化

### 6.1 启动序列

`backend/api/main.py` 启动时按序执行：

```
1. unified_indexer 单例初始化 → 建/迁移 SQLite schema（含 projects、conversations 表）
2. project_manager.ensure_default_project()
3. project_manager.run_migration_if_needed()
4. source_manager 单例初始化（已存在）
5. conversation_manager 加载（从 SQLite 读取）
```

任意一步失败 fail-fast，不掩盖错误。

### 6.2 一次性数据迁移

触发条件：`projects` 表为空。

步骤：
1. 创建 `Default Project`，从 `.env` 读取 `MYSQL_URL` / `ORACLE_URL` 作为种子值
2. 回填 SQLite 5 张表的 `project_id`：`UPDATE <table> SET project_id = ? WHERE project_id IS NULL OR project_id = ''`
3. ChromaDB metadata 回填：分批（1000/批）`get → update`，对 `code_chunks` / `config_entries` 两个 collection 操作。若某个 chunk 的 metadata 已有非空 `project_id` 则跳过（支持中断后重启续跑）
4. `conversations.json` 迁移：逐条插入 `conversations` 表，原文件改名 `.migrated.bak`

幂等性：再次启动时 `projects` 表非空，跳过整个迁移流程。

### 6.3 `.env` 兼容

迁移后：
- `MYSQL_URL` / `ORACLE_URL` / `LOCAL_CODE_DIR` 保留作为"default 项目种子"
- 新建项目不再依赖 `.env`，全部走 UI/API
- README 增加"建议新部署直接用 UI 管理项目"说明

### 6.4 回滚

- ChromaDB：仅追加 metadata 字段，未删除任何数据；旧版代码不读 `project_id` 也能正常工作
- conversations.json：保留 `.migrated.bak`，必要时手动还原
- SQLite：不自动备份。若极端需要回滚，丢弃 `projects` / `conversations` 表 + `project_id` 列即可

---

## 7. 测试策略

### 7.1 单元测试（`tests/unit/`）

| 文件 | 覆盖 |
|---|---|
| `test_project_manager.py` | CRUD + 级联删除验证 |
| `test_db_manager.py` | 按 project_id 取 engine / 缓存 / invalidate |
| `test_agent_context.py` | ContextVar 设置、重置、嵌套 |
| `test_conversation_manager.py` | SQLite 持久化、加 project_id、按项目过滤 |
| `test_unified_indexer_filter.py` | 索引时写入 project_id、查询时过滤生效 |

工具关键路径（`SearchCodeTool`、`GrepCodeTool`、`ExecuteSQLTool`）每个加 1~2 用例，验证：
- 设置项目 A 时不会命中项目 B
- 打开 cross_project 时跨项目命中
- ContextVar 未设置时不过滤（向后兼容）

### 7.2 集成测试

`tests/integration/test_multi_project_isolation.py`：
1. 创建项目 A、B
2. 各注册一个 local 知识源（fixture 提供小代码片段）
3. 触发索引
4. 设置 `current_project_id=A`，断言 `SearchCodeTool` 只返回 A
5. 切换到 B，断言只返回 B
6. 打开 `allow_cross_project`，断言两者都能命中
7. 删除 A，断言 B 完整、A 完全清空

### 7.3 迁移幂等性

`tests/integration/test_migration.py`：
- fixture 准备旧版 metadata.db + conversations.json
- 调 `unified_indexer` + `ProjectManager.run_migration_if_needed()`
- 断言 default 项目存在、各表 project_id 已填、conversations 表已有数据、JSON 已改名 `.migrated.bak`
- 二次调 `run_migration_if_needed()` → 断言无任何变化（幂等）

### 7.4 前端手动验证清单

写入 PR 描述供 reviewer 走查：

1. 新建项目 → 配 DB URL → 测试连接 → 提示成功
2. 在项目 A 下注册 local 源 → 索引 → 状态变 indexed
3. 新建会话选项目 A → 提问 "列出所有 controller" → 只返回 A 结果
4. 同一会话开"跨项目"开关 → 提问相同问题 → 包含 B 结果，开关自动复位
5. 删除项目 A → 二次确认显示影响范围 → 删除成功 → A 的源/会话/索引清空，B 完好

### 7.5 性能烟雾测试

`tests/perf/test_chroma_filter_overhead.py`：
- A、B 各 5000 chunk
- 测带/不带 `where={"project_id":...}` 的 `SearchCodeTool` P95 延迟
- 阈值：过滤后增长 < 30%（不达标则在 spec 里标注，不阻塞 PR）

---

## 8. PR 拆分建议

建议分 3 个 PR 提交，便于 review：

1. **PR-1：数据模型 + 迁移 + ProjectManager + DBManager 改造**
   - 后端不暴露任何新行为，所有 Tool 暂未启用过滤
   - 启动时自动迁移到 default 项目，老用户无感
2. **PR-2：ContextVar + Tool 过滤 + 路由调整**
   - 引入 agent_context、改造工具、路由请求体加 project_id / cross_project_query
   - 自动化测试覆盖隔离逻辑
3. **PR-3：前端项目管理页 + 会话级绑定 + 跨查开关**
   - 完整 UI 落地

---

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| Chroma metadata 回填中断 | 分批 + 进度日志；中断后重启可继续（已写入的不会被重置） |
| 用户保留多个老会话突然全部归到 default 项目，不符合预期 | UI 上允许"会话改属项目"作为后续增强（本次不实现，但 spec 中标注） |
| ContextVar 被异步任务漏传 | 流式响应中 `event_generator` 内部已在 `try/finally` 中 reset；新增的异步路径需在 PR review 时检查 |
| 用户删项目误操作 | 二次确认弹窗显式列出"将清空 N 源 / M 会话" |
| `.env` 老用户改 URL 后期望生效 | 迁移后 `.env` 仅在 default 项目首次创建时读；后续改需在 UI 修改。README 中说明 |

---

## 10. 验收标准

- [ ] 启动现有部署，无需任何手动操作，老数据全部归到 "Default Project"
- [ ] UI 能创建项目 B，并在项目 B 下注册代码源、索引、提问
- [ ] 在项目 A 的会话中提问，Agent 不会命中项目 B 的代码
- [ ] 打开"跨项目"开关后单次消息能跨查，下条消息自动复位
- [ ] 删除项目能正确级联清理所有相关数据
- [ ] 单元 + 集成测试全部通过
- [ ] 迁移函数幂等（连续启动两次行为一致）
