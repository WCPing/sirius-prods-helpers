<template>
  <div class="msg-row" :class="isUser ? 'msg-row--user' : 'msg-row--ai'">
    <!-- AI 头像 -->
    <div v-if="!isUser" class="avatar avatar--ai">
      <el-icon><Cpu /></el-icon>
    </div>

    <!-- 消息气泡 -->
    <div class="bubble-wrapper">
      <div class="bubble" :class="isUser ? 'bubble--user' : 'bubble--ai'">
        <!-- 流式光标 -->
        <span v-if="isStreaming && !isUser" class="streaming-cursor" />

        <!-- 内容：AI 消息渲染 Markdown，用户消息纯文本 -->
        <div
          v-if="!isUser"
          class="markdown-body"
          v-html="renderedContent"
        />
        <div v-else class="user-text">{{ message.content }}</div>
      </div>

      <!-- 消息时间（AI 消息显示复制按钮） -->
      <div class="bubble-footer" :class="isUser ? 'footer--right' : 'footer--left'">
        <el-button
          v-if="!isUser && message.content"
          link
          size="small"
          :icon="CopyDocument"
          class="copy-btn"
          @click="copyContent"
        >
          复制
        </el-button>
      </div>
    </div>

    <!-- 用户头像 -->
    <div v-if="isUser" class="avatar avatar--user">
      <el-icon><User /></el-icon>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Cpu, User, CopyDocument } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'

const props = defineProps({
  message: {
    type: Object,
    required: true
    // { role: 'user'|'assistant', content: string, id: string }
  },
  /** 是否正在流式输出（仅最后一条 AI 消息有效） */
  isStreaming: {
    type: Boolean,
    default: false
  }
})

const isUser = computed(() => props.message.role === 'user')

// 将 Markdown 渲染为 HTML（仅 AI 消息）
const renderedContent = computed(() => {
  if (!props.message.content) return '<span class="streaming-placeholder">...</span>'
  try {
    return marked(props.message.content, {
      breaks: true,
      gfm: true
    })
  } catch {
    return props.message.content
  }
})

async function copyContent() {
  try {
    await navigator.clipboard.writeText(props.message.content)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}
</script>

<style scoped>
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

.msg-row--user {
  flex-direction: row-reverse;
}

/* ---- 头像 ---- */
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  margin-top: 2px;
}

.avatar--ai {
  background: linear-gradient(135deg, #409eff 0%, #6c8eff 100%);
  color: #fff;
}

.avatar--user {
  background: linear-gradient(135deg, #67c23a 0%, #42b883 100%);
  color: #fff;
}

/* ---- 气泡容器 ---- */
.bubble-wrapper {
  max-width: 72%;
  display: flex;
  flex-direction: column;
}

.msg-row--user .bubble-wrapper {
  align-items: flex-end;
}

/* ---- 气泡本体 ---- */
.bubble {
  padding: 10px 14px;
  border-radius: 12px;
  word-break: break-word;
  position: relative;
  line-height: 1.7;
}

.bubble--ai {
  background: #ffffff;
  border: 1px solid var(--border-color);
  color: #303133;
  border-radius: 2px 12px 12px 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.bubble--user {
  background: linear-gradient(135deg, #409eff 0%, #337ecc 100%);
  color: #fff;
  border-radius: 12px 2px 12px 12px;
}

.user-text {
  font-size: 14px;
  white-space: pre-wrap;
}

/* ---- 流式光标 ---- */
.streaming-cursor {
  display: inline-block;
  width: 2px;
  height: 16px;
  background: #409eff;
  margin-left: 2px;
  vertical-align: middle;
  animation: blink 0.8s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}

.streaming-placeholder {
  color: #c0c4cc;
  font-style: italic;
  font-size: 14px;
}

/* ---- 底部工具栏 ---- */
.bubble-footer {
  margin-top: 4px;
  min-height: 20px;
}

.footer--left {
  display: flex;
  justify-content: flex-start;
}

.footer--right {
  display: flex;
  justify-content: flex-end;
}

.copy-btn {
  font-size: 12px !important;
  color: #909399 !important;
  padding: 0 4px !important;
  opacity: 0;
  transition: opacity 0.15s;
}

.msg-row:hover .copy-btn {
  opacity: 1;
}
</style>
