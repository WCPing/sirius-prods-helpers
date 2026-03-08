<template>
  <div class="chat-window">
    <!-- 聊天头部 -->
    <div class="chat-header">
      <div class="chat-header-left">
        <template v-if="store.currentSession">
          <el-icon class="chat-icon"><ChatLineRound /></el-icon>
          <span class="chat-title">{{ store.currentSession.name || '未命名会话' }}</span>
          <el-tag size="small" type="info" class="msg-count-tag">
            {{ store.messages.length }} 条消息
          </el-tag>
        </template>
        <template v-else>
          <span class="chat-title placeholder">请从左侧选择或新建会话</span>
        </template>
      </div>

      <div class="chat-header-right" v-if="store.currentSession">
        <!-- 流式模式指示 -->
        <el-tag
          v-if="store.streamMode"
          size="small"
          type="primary"
          effect="light"
        >
          <el-icon><Lightning /></el-icon>
          流式模式
        </el-tag>

        <el-tooltip content="清空历史" placement="bottom">
          <el-button
            size="small"
            :icon="Delete"
            link
            :disabled="store.messages.length === 0 || store.sending"
            @click="store.clearHistory"
          />
        </el-tooltip>
      </div>
    </div>

    <!-- 无会话时的引导页 -->
    <div v-if="!store.currentSession" class="chat-empty">
      <div class="empty-illustration">
        <el-icon style="font-size: 64px; color: #dcdfe6"><DataAnalysis /></el-icon>
      </div>
      <h3>欢迎使用 PDM 智能助手</h3>
      <p>基于 AI 的数据库模型分析助手</p>
      <ul class="feature-list">
        <li>📊 查询表结构和字段信息</li>
        <li>🔗 分析表间关联关系</li>
        <li>🔍 语义搜索相关数据表</li>
        <li>⚡ 直接执行 SQL 查询</li>
      </ul>
      <el-button type="primary" :icon="Plus" @click="onNewSession">
        新建会话，开始提问
      </el-button>
    </div>

    <!-- 消息区域 -->
    <div
      v-else
      ref="messagesContainer"
      class="chat-messages"
      v-loading="store.loadingHistory"
    >
      <!-- 历史消息为空时的提示 -->
      <div v-if="store.messages.length === 0 && !store.loadingHistory" class="messages-empty">
        <el-icon style="font-size: 40px; color: #dcdfe6"><ChatDotRound /></el-icon>
        <p>暂无消息，开始提问吧</p>
        <!-- 快捷问题推荐 -->
        <div class="quick-questions">
          <p class="quick-title">快速提问：</p>
          <div class="quick-list">
            <el-button
              v-for="q in quickQuestions"
              :key="q"
              size="small"
              plain
              round
              @click="onQuickQuestion(q)"
            >
              {{ q }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- 消息列表 -->
      <div v-else class="messages-list">
        <MessageBubble
          v-for="(msg, idx) in store.messages"
          :key="msg.id"
          :message="msg"
          :isStreaming="store.isStreaming && idx === store.messages.length - 1 && msg.role === 'assistant'"
        />

        <!-- AI 正在输入中提示（普通模式） -->
        <div v-if="store.sending && !store.streamMode" class="typing-indicator">
          <div class="avatar avatar--ai">
            <el-icon><Cpu /></el-icon>
          </div>
          <div class="typing-bubble">
            <span class="dot" />
            <span class="dot" />
            <span class="dot" />
          </div>
        </div>
      </div>

      <!-- 滚动到底部按钮 -->
      <transition name="fade">
        <div v-if="showScrollBtn" class="scroll-to-bottom" @click="scrollToBottom">
          <el-icon><ArrowDown /></el-icon>
        </div>
      </transition>
    </div>

    <!-- 消息输入框 -->
    <MessageInput
      v-if="store.currentSession"
      @send="handleSend"
      :disabled="store.sending"
      :sending="store.sending"
      :streaming="store.isStreaming"
      @abort="store.abortStream"
    />
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted, onUnmounted } from 'vue'
import {
  ChatLineRound,
  Delete,
  Lightning,
  DataAnalysis,
  Plus,
  ChatDotRound,
  Cpu,
  ArrowDown
} from '@element-plus/icons-vue'
import { useConversationStore } from '@/stores/conversation'
import MessageBubble from './MessageBubble.vue'
import MessageInput from './MessageInput.vue'

const store = useConversationStore()
const messagesContainer = ref(null)
const showScrollBtn = ref(false)

// 快捷问题
const quickQuestions = [
  '列出所有数据表',
  '查找与用户相关的表',
  '分析订单表的结构',
  '查询最近创建的 10 条记录'
]

function onNewSession() {
  // 触发左侧新建按钮逻辑（通过 store 直接创建）
  store.createNewSession()
}

function onQuickQuestion(q) {
  handleSend(q)
}

// 发送消息
async function handleSend(content) {
  await store.sendUserMessage(content)
  await nextTick()
  scrollToBottom()
}

// 滚动到底部
function scrollToBottom(smooth = true) {
  if (!messagesContainer.value) return
  messagesContainer.value.scrollTo({
    top: messagesContainer.value.scrollHeight,
    behavior: smooth ? 'smooth' : 'instant'
  })
}

// 监听滚动，显示"回到底部"按钮
function onScroll() {
  if (!messagesContainer.value) return
  const el = messagesContainer.value
  const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  showScrollBtn.value = distFromBottom > 200
}

// 监听消息变化，自动滚到底部
watch(
  () => store.messages.length,
  async () => {
    await nextTick()
    // 如果用户未上翻，则自动滚底
    if (!showScrollBtn.value) {
      scrollToBottom(false)
    }
  }
)

// 流式输出时也自动滚底
watch(
  () => store.streamingContent,
  async () => {
    if (!showScrollBtn.value) {
      await nextTick()
      scrollToBottom(false)
    }
  }
)

// 切换会话时滚到底部
watch(
  () => store.currentSessionId,
  async () => {
    await nextTick()
    scrollToBottom(false)
  }
)

onMounted(() => {
  if (messagesContainer.value) {
    messagesContainer.value.addEventListener('scroll', onScroll)
  }
})

onUnmounted(() => {
  if (messagesContainer.value) {
    messagesContainer.value.removeEventListener('scroll', onScroll)
  }
})
</script>

<style scoped>
.chat-window {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--chat-bg);
  overflow: hidden;
}

/* ---- 聊天头部 ---- */
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 52px;
  background: #fff;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.chat-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-icon {
  color: var(--primary-color);
  font-size: 18px;
}

.chat-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.chat-title.placeholder {
  color: #c0c4cc;
  font-weight: 400;
}

.msg-count-tag {
  border-radius: 10px;
}

.chat-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ---- 无会话引导页 ---- */
.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px;
  color: #606266;
}

.empty-illustration {
  margin-bottom: 8px;
}

.chat-empty h3 {
  font-size: 20px;
  color: #303133;
  margin: 0;
}

.chat-empty p {
  font-size: 14px;
  color: #909399;
  margin: 0;
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: 8px 0 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  text-align: left;
}

.feature-list li {
  font-size: 14px;
  color: #606266;
  padding: 4px 0;
}

/* ---- 消息区域 ---- */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  position: relative;
}

/* ---- 空消息提示 ---- */
.messages-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding-top: 60px;
  color: #909399;
  font-size: 14px;
}

.quick-questions {
  margin-top: 8px;
  text-align: center;
}

.quick-title {
  font-size: 13px;
  color: #c0c4cc;
  margin-bottom: 10px;
}

.quick-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

/* ---- 消息列表 ---- */
.messages-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* ---- AI 打字中动画 ---- */
.typing-indicator {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 8px 0;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.avatar--ai {
  background: linear-gradient(135deg, #409eff 0%, #6c8eff 100%);
  color: #fff;
}

.typing-bubble {
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 2px 12px 12px 12px;
  padding: 12px 16px;
  display: flex;
  gap: 5px;
  align-items: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.dot {
  width: 8px;
  height: 8px;
  background: #c0c4cc;
  border-radius: 50%;
  animation: typing 1.2s ease-in-out infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 80%, 100% { transform: scale(1); opacity: 0.5; }
  40%           { transform: scale(1.2); opacity: 1; }
}

/* ---- 滚动到底部按钮 ---- */
.scroll-to-bottom {
  position: absolute;
  bottom: 16px;
  right: 24px;
  width: 36px;
  height: 36px;
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  color: #606266;
  font-size: 16px;
  transition: all 0.2s;
}

.scroll-to-bottom:hover {
  background: var(--primary-color);
  color: #fff;
  border-color: var(--primary-color);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
