<template>
  <div class="layout-container">
    <!-- 顶部 Header -->
    <div class="layout-header">
      <div class="header-left">
        <el-icon class="logo-icon"><DataAnalysis /></el-icon>
        <span class="header-title">PDM 智能助手</span>
      </div>
      <div class="header-right">
        <!-- 流式/普通模式切换 -->
        <div class="stream-toggle">
          <el-icon style="color: #909399; font-size: 13px"><Lightning /></el-icon>
          <span class="toggle-label">流式响应</span>
          <el-tooltip
            :content="store.streamMode ? '当前：流式响应（逐字输出）' : '当前：普通响应（等待完整回复）'"
            placement="bottom"
          >
            <el-switch
              v-model="store.streamMode"
              :active-color="'#409eff'"
              size="small"
              @change="onStreamModeChange"
            />
          </el-tooltip>
        </div>

        <el-divider direction="vertical" />

        <el-tooltip content="API 文档" placement="bottom">
          <el-button
            circle
            size="small"
            :icon="Document"
            @click="openApiDocs"
          />
        </el-tooltip>
      </div>
    </div>

    <!-- 主体内容区：左右分栏 -->
    <div class="layout-body">
      <!-- 左侧：会话列表 -->
      <SessionList class="layout-sidebar" />

      <!-- 分隔线 -->
      <div class="layout-divider" />

      <!-- 右侧：聊天窗口 -->
      <ChatWindow class="layout-main" />
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { Document, Lightning } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useConversationStore } from '@/stores/conversation'
import SessionList from '@/components/SessionList.vue'
import ChatWindow from '@/components/ChatWindow.vue'

const store = useConversationStore()

onMounted(async () => {
  await store.fetchSessions()
  // 自动选中第一个会话
  if (store.sessions.length > 0 && !store.currentSessionId) {
    await store.switchSession(store.sessions[0].session_id)
  }
})

function onStreamModeChange(val) {
  ElMessage.info(val ? '已切换为流式响应模式 ⚡' : '已切换为普通响应模式')
}

function openApiDocs() {
  window.open('http://127.0.0.1:8000/docs', '_blank')
}
</script>

<style scoped>
.layout-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-color);
  overflow: hidden;
}

/* ---- Header ---- */
.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-icon {
  font-size: 24px;
  color: var(--primary-color);
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  letter-spacing: 0.5px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stream-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
}

.toggle-label {
  font-size: 13px;
  color: #606266;
}

/* ---- Body ---- */
.layout-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.layout-sidebar {
  width: var(--sidebar-width);
  flex-shrink: 0;
}

.layout-divider {
  width: 1px;
  background: var(--border-color);
  flex-shrink: 0;
}

.layout-main {
  flex: 1;
  overflow: hidden;
}
</style>
