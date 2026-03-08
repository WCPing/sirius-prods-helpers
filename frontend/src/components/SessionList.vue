<template>
  <div class="session-list">
    <!-- 顶部工具栏 -->
    <div class="session-toolbar">
      <span class="toolbar-title">会话列表</span>
      <el-tooltip content="新建会话" placement="right">
        <el-button
          type="primary"
          :icon="Plus"
          size="small"
          round
          @click="onNewSession"
          :loading="creating"
        >
          新建
        </el-button>
      </el-tooltip>
    </div>

    <!-- 会话列表 -->
    <div class="session-scroll" v-loading="store.loadingSessions">
      <div v-if="store.sessions.length === 0 && !store.loadingSessions" class="empty-tip">
        <el-icon style="font-size: 32px; color: #c0c4cc"><ChatDotRound /></el-icon>
        <p>暂无会话，点击「新建」开始</p>
      </div>

      <div
        v-for="session in store.sessions"
        :key="session.session_id"
        class="session-item"
        :class="{ 'is-active': session.session_id === store.currentSessionId }"
        @click="onSelectSession(session.session_id)"
      >
        <!-- 会话图标 + 内容 -->
        <div class="session-icon">
          <el-icon><ChatLineRound /></el-icon>
        </div>
        <div class="session-info">
          <div class="session-name text-ellipsis">
            {{ session.name || '未命名会话' }}
          </div>
          <div class="session-meta">
            <span class="meta-count">{{ session.message_count }} 条消息</span>
            <span class="meta-time">{{ formatTime(session.updated_at) }}</span>
          </div>
        </div>

        <!-- 操作按钮（悬浮显示） -->
        <div class="session-actions" @click.stop>
          <el-dropdown trigger="click" @command="(cmd) => onAction(cmd, session.session_id)">
            <el-button
              size="small"
              :icon="MoreFilled"
              link
              class="action-btn"
            />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="rename" :icon="Edit">重命名</el-dropdown-item>
                <el-dropdown-item command="delete" :icon="Delete" divided class="danger-item">
                  删除会话
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>

    <!-- 新建会话弹窗 -->
    <el-dialog
      v-model="showNewDialog"
      title="新建会话"
      width="360px"
      :close-on-click-modal="false"
      @open="newSessionName = ''"
    >
      <el-input
        v-model="newSessionName"
        placeholder="会话名称（可留空）"
        maxlength="50"
        show-word-limit
        clearable
        autofocus
        @keyup.enter="confirmNewSession"
      />
      <template #footer>
        <el-button @click="showNewDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmNewSession" :loading="creating">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 重命名弹窗 -->
    <el-dialog
      v-model="showRenameDialog"
      title="重命名会话"
      width="360px"
      :close-on-click-modal="false"
    >
      <el-input
        v-model="renameValue"
        placeholder="请输入新名称"
        maxlength="50"
        show-word-limit
        clearable
        autofocus
        @keyup.enter="confirmRename"
      />
      <template #footer>
        <el-button @click="showRenameDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmRename">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Plus, MoreFilled, Edit, Delete, ChatDotRound, ChatLineRound } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useConversationStore } from '@/stores/conversation'

const store = useConversationStore()

// ---- 新建会话 ----
const showNewDialog = ref(false)
const newSessionName = ref('')
const creating = ref(false)

function onNewSession() {
  showNewDialog.value = true
}

async function confirmNewSession() {
  creating.value = true
  try {
    await store.createNewSession(newSessionName.value.trim())
    showNewDialog.value = false
    ElMessage.success('会话已创建')
  } finally {
    creating.value = false
  }
}

// ---- 选择会话 ----
async function onSelectSession(sessionId) {
  await store.switchSession(sessionId)
}

// ---- 操作菜单 ----
const showRenameDialog = ref(false)
const renameValue = ref('')
let renamingSessionId = null

function onAction(cmd, sessionId) {
  if (cmd === 'delete') {
    store.removeSession(sessionId)
  } else if (cmd === 'rename') {
    renamingSessionId = sessionId
    const session = store.sessions.find((s) => s.session_id === sessionId)
    renameValue.value = session?.name || ''
    showRenameDialog.value = true
  }
}

function confirmRename() {
  if (!renameValue.value.trim()) {
    ElMessage.warning('名称不能为空')
    return
  }
  // 本地更新（后端暂未提供重命名接口，直接更新本地状态）
  const idx = store.sessions.findIndex((s) => s.session_id === renamingSessionId)
  if (idx !== -1) {
    store.sessions[idx].name = renameValue.value.trim()
    ElMessage.success('已重命名')
  }
  showRenameDialog.value = false
}

// ---- 时间格式化 ----
function formatTime(isoStr) {
  if (!isoStr) return ''
  try {
    const date = new Date(isoStr)
    const now = new Date()
    const diffMs = now - date
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 1) return '刚刚'
    if (diffMin < 60) return `${diffMin} 分钟前`
    const diffHour = Math.floor(diffMin / 60)
    if (diffHour < 24) return `${diffHour} 小时前`
    const diffDay = Math.floor(diffHour / 24)
    if (diffDay < 7) return `${diffDay} 天前`
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  } catch {
    return ''
  }
}
</script>

<style scoped>
.session-list {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--sidebar-bg);
  overflow: hidden;
}

/* ---- 工具栏 ---- */
.session-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.toolbar-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

/* ---- 滚动区域 ---- */
.session-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

/* ---- 空状态 ---- */
.empty-tip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 40px 20px;
  color: #c0c4cc;
  font-size: 13px;
  text-align: center;
}

/* ---- 会话条目 ---- */
.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px 10px 16px;
  cursor: pointer;
  border-radius: 0;
  transition: background 0.15s;
  position: relative;
}

.session-item:hover {
  background: #f5f7fa;
}

.session-item.is-active {
  background: #ecf5ff;
  border-right: 3px solid var(--primary-color);
}

.session-item.is-active .session-name {
  color: var(--primary-color);
  font-weight: 600;
}

.session-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  flex-shrink: 0;
  font-size: 16px;
}

.session-item.is-active .session-icon {
  background: #d9ecff;
  color: var(--primary-color);
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-name {
  font-size: 14px;
  color: #303133;
  line-height: 1.4;
}

.session-meta {
  display: flex;
  justify-content: space-between;
  margin-top: 3px;
}

.meta-count {
  font-size: 12px;
  color: #c0c4cc;
}

.meta-time {
  font-size: 12px;
  color: #c0c4cc;
}

/* ---- 操作按钮 ---- */
.session-actions {
  opacity: 0;
  transition: opacity 0.15s;
}

.session-item:hover .session-actions {
  opacity: 1;
}

.action-btn {
  color: #909399 !important;
  padding: 4px !important;
}

:deep(.danger-item) {
  color: #f56c6c !important;
}
</style>
