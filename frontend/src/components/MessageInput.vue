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
          <span class="hint-text">Enter 发送 &middot; Shift+Enter 换行 &middot; 可粘贴图片或上传日志</span>
        </div>
      </div>

      <!-- 图片预览条 -->
      <div v-if="imageList.length > 0" class="image-preview-bar">
        <div
          v-for="(img, idx) in imageList"
          :key="idx"
          class="preview-item"
        >
          <img :src="img.preview" class="preview-thumb" />
          <span class="preview-name">{{ img.filename }}</span>
          <el-icon class="preview-remove" @click="removeImage(idx)"><Close /></el-icon>
        </div>
        <div
          v-if="imageList.length < maxImages"
          class="preview-add"
          @click="triggerImageUpload"
        >
          <el-icon><Plus /></el-icon>
        </div>
      </div>

      <!-- 日志文件预览条 -->
      <div v-if="logFile" class="file-preview-bar">
        <div class="preview-item preview-item--file">
          <el-icon class="preview-file-icon"><Document /></el-icon>
          <span class="preview-name">{{ logFile.filename }}</span>
          <span class="preview-meta">{{ formatFileSize(logFile.size) }}</span>
          <el-icon class="preview-remove" @click="removeLogFile"><Close /></el-icon>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-row">
        <!-- 上传图片按钮 -->
        <el-tooltip content="上传图片" placement="top">
          <el-button
            :icon="PictureFilled"
            link
            class="upload-btn"
            @click="triggerImageUpload"
          />
        </el-tooltip>
        <input
          ref="imageInputRef"
          type="file"
          accept="image/png,image/jpg,image/jpeg,image/gif,image/bmp,image/webp"
          multiple
          style="display: none"
          @change="onImageChange"
        />

        <!-- 上传日志按钮 -->
        <el-tooltip content="上传日志文件" placement="top">
          <el-button
            :icon="Document"
            link
            class="upload-btn"
            @click="triggerLogUpload"
          />
        </el-tooltip>
        <input
          ref="logInputRef"
          type="file"
          accept=".log,.txt,text/plain"
          style="display: none"
          @change="onLogChange"
        />

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
          @paste="onPaste"
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
            :disabled="disabled || (!inputText.trim() && imageList.length === 0 && !logFile)"
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
import { Promotion, VideoPause, Loading, PictureFilled, Document, Close, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const MAX_IMAGE_SIZE = 5 * 1024 * 1024 // 5MB
const MAX_LOG_SIZE = 5 * 1024 * 1024 // 5MB
const ALLOWED_IMAGE_TYPES = ['image/png', 'image/jpg', 'image/jpeg', 'image/gif', 'image/bmp', 'image/webp']
const ALLOWED_LOG_EXTENSIONS = ['.log', '.txt']

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false
  },
  sending: {
    type: Boolean,
    default: false
  },
  streaming: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['send', 'abort'])

const inputRef = ref(null)
const imageInputRef = ref(null)
const logInputRef = ref(null)
const inputText = ref('')
const imageList = ref([]) // [{data, preview, filename, mime_type}]
const logFile = ref(null) // {data, filename, mime_type, size}
const maxImages = 5

function triggerImageUpload() {
  imageInputRef.value?.click()
}

function triggerLogUpload() {
  logInputRef.value?.click()
}

function onImageChange(e) {
  const files = Array.from(e.target.files || [])
  addImages(files)
  e.target.value = ''
}

function onLogChange(e) {
  const [file] = Array.from(e.target.files || [])
  if (file) addLogFile(file)
  e.target.value = ''
}

function onPaste(e) {
  const items = e.clipboardData?.items
  if (!items) return

  const imageFiles = []
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) imageFiles.push(file)
    }
  }

  if (imageFiles.length > 0) {
    e.preventDefault()
    addImages(imageFiles)
  }
}

function addImages(files) {
  for (const file of files) {
    if (imageList.value.length >= maxImages) {
      ElMessage.warning(`最多上传 ${maxImages} 张图片`)
      break
    }
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      ElMessage.warning(`不支持的图片格式: ${file.name}`)
      continue
    }
    if (file.size > MAX_IMAGE_SIZE) {
      ElMessage.warning(`图片 ${file.name} 过大（最大 5MB）`)
      continue
    }

    const reader = new FileReader()
    reader.onload = (ev) => {
      const dataUrl = ev.target.result
      const base64 = dataUrl.split(',')[1]
      imageList.value.push({
        data: base64,
        preview: dataUrl,
        filename: file.name,
        mime_type: file.type,
      })
    }
    reader.readAsDataURL(file)
  }
}

function addLogFile(file) {
  if (logFile.value) {
    ElMessage.warning('每次只能上传 1 个日志文件')
    return
  }

  const lowerName = file.name.toLowerCase()
  const isAllowed = ALLOWED_LOG_EXTENSIONS.some((ext) => lowerName.endsWith(ext))
  if (!isAllowed) {
    ElMessage.warning(`不支持的日志格式: ${file.name}`)
    return
  }

  if (file.size > MAX_LOG_SIZE) {
    ElMessage.warning(`日志文件 ${file.name} 过大（最大 5MB）`)
    return
  }

  const reader = new FileReader()
  reader.onload = (ev) => {
    const dataUrl = ev.target.result
    const base64 = dataUrl.split(',')[1]
    logFile.value = {
      data: base64,
      filename: file.name,
      mime_type: file.type || 'text/plain',
      size: file.size,
    }
  }
  reader.readAsDataURL(file)
}

function removeImage(idx) {
  imageList.value.splice(idx, 1)
}

function removeLogFile() {
  logFile.value = null
}

function formatFileSize(size) {
  if (!size) return '0 B'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function onKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    onSend()
  }
}

async function onSend() {
  const text = inputText.value.trim()
  const hasImages = imageList.value.length > 0
  const hasLogFile = !!logFile.value
  if ((!text && !hasImages && !hasLogFile) || props.disabled || props.sending) return

  const payload = {
    text,
    images: hasImages ? [...imageList.value] : null,
    logFile: hasLogFile ? { ...logFile.value } : null,
  }

  inputText.value = ''
  imageList.value = []
  logFile.value = null

  emit('send', payload)

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

/* ---- 附件预览条 ---- */
.image-preview-bar,
.file-preview-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  overflow-x: auto;
  border-bottom: 1px solid #f5f7fa;
}

.preview-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: #f5f7fa;
  border-radius: 6px;
  flex-shrink: 0;
}

.preview-item--file {
  gap: 6px;
}

.preview-thumb {
  width: 36px;
  height: 36px;
  object-fit: cover;
  border-radius: 4px;
}

.preview-file-icon {
  font-size: 16px;
  color: #606266;
}

.preview-name {
  font-size: 12px;
  color: #606266;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-meta {
  font-size: 12px;
  color: #909399;
}

.preview-remove {
  cursor: pointer;
  color: #909399;
  font-size: 14px;
  transition: color 0.15s;
}

.preview-remove:hover {
  color: #f56c6c;
}

.preview-add {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed #c0c4cc;
  border-radius: 6px;
  cursor: pointer;
  color: #909399;
  flex-shrink: 0;
  transition: border-color 0.15s, color 0.15s;
}

.preview-add:hover {
  border-color: var(--primary-color);
  color: var(--primary-color);
}

/* ---- 输入行 ---- */
.input-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 6px 12px 10px;
}

.upload-btn {
  font-size: 20px !important;
  color: #909399 !important;
  padding: 4px !important;
  flex-shrink: 0;
}

.upload-btn:hover {
  color: var(--primary-color) !important;
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
