<template>
  <div class="message-input-wrap">
    <div class="input-container">
      <!-- 工具栏 -->
      <div class="input-toolbar">
        <div class="toolbar-left">
          <el-tooltip content="支持 Markdown 格式" placement="top">
            <el-tag size="small" type="info" effect="plain">Markdown</el-tag>
          </el-tooltip>
        </div>
        <div class="toolbar-right">
          <span class="hint-text">Enter 发送 &nbsp;·&nbsp; Shift+Enter 换行</span>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-row">
        <el-input
          ref="inputRef"
          v-model="inputText"
          type="textarea"
          :rows="3"
          :autosize="{ minRows: 2, maxRows: 6 }"
          placeholder="输入您的问题，例如：查找与订单相关的所有表..."
          resize="none"
          :disabled="disabled"
          class="chat-textarea"
          @keydown="onKeyDown"
        />

        <div class="send-area">
          <!-- 正在流式输出时显示终止按钮 -->
          <el-button
            v-if="streaming"
            type="danger"
            :icon="VideoPause"
            round
            @click="$emit('abort')"
          >
            停止
          </el-button>

          <!-- 发送按钮 -->
          <el-button
            v-else
            type="primary"
            :icon="sending ? Loading : Promotion"
            :loading="sending"
            :disabled="disabled || !inputText.trim()"
            round
            @click="onSend"
          >
            {{ sending ? '等待回复...' : '发送' }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { Promotion, VideoPause, Loading } from '@element-plus/icons-vue'

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false
  },
  sending: {
    type: Boolean,
    default: false
  },
  /** 是否正在流式输出 */
  streaming: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['send', 'abort'])

const inputRef = ref(null)
const inputText = ref('')

function onKeyDown(e) {
  // Enter 发送（Shift+Enter 换行）
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    onSend()
  }
}

async function onSend() {
  const content = inputText.value.trim()
  if (!content || props.disabled || props.sending) return

  inputText.value = ''
  emit('send', content)

  // 聚焦输入框
  await nextTick()
  inputRef.value?.focus()
}
</script>

<style scoped>
.message-input-wrap {
  flex-shrink: 0;
  padding: 12px 20px 16px;
  background: #fff;
  border-top: 1px solid var(--border-color);
}

.input-container {
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;
  transition: border-color 0.2s, box-shadow 0.2s;
  background: #fff;
}

.input-container:focus-within {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.12);
}

/* ---- 工具栏 ---- */
.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px 4px;
  border-bottom: 1px solid #f5f7fa;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.hint-text {
  font-size: 12px;
  color: #c0c4cc;
}

/* ---- 输入行 ---- */
.input-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 6px 12px 10px;
}

.chat-textarea {
  flex: 1;
}

/* 覆盖 el-input 的边框 */
:deep(.chat-textarea .el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  padding: 6px 4px;
  font-size: 14px;
  line-height: 1.6;
  resize: none;
  background: transparent;
}

:deep(.chat-textarea .el-textarea__inner:focus) {
  border: none !important;
  box-shadow: none !important;
}

/* ---- 发送区 ---- */
.send-area {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  padding-bottom: 2px;
}
</style>
