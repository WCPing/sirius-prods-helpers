/**
 * src/stores/conversation.js
 * 会话状态管理（Pinia Store）
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listSessions,
  createSession,
  getSessionHistory,
  sendMessage,
  sendMessageStream,
  clearSessionHistory,
  deleteSession
} from '@/api/conversation'

export const useConversationStore = defineStore('conversation', () => {
  // ---------------------------------------------------------------
  // State
  // ---------------------------------------------------------------

  /** 所有会话列表 */
  const sessions = ref([])

  /** 当前选中的会话 ID */
  const currentSessionId = ref(null)

  /** 当前会话的消息列表 [{ role: 'user'|'assistant', content: string, id: string }] */
  const messages = ref([])

  /** 是否正在加载会话列表 */
  const loadingSessions = ref(false)

  /** 是否正在加载消息历史 */
  const loadingHistory = ref(false)

  /** 是否正在等待 AI 回复 */
  const sending = ref(false)

  /** 流式模式开关（true = 流式，false = 普通）*/
  const streamMode = ref(false)

  /** 当前流式输出的临时内容（仅流式模式使用） */
  const streamingContent = ref('')

  /** 流式终止函数（预留） */
  let _abortStream = null

  // ---------------------------------------------------------------
  // Getters
  // ---------------------------------------------------------------

  /** 当前会话对象 */
  const currentSession = computed(() =>
    sessions.value.find((s) => s.session_id === currentSessionId.value) || null
  )

  /** 是否正在流式输出 */
  const isStreaming = computed(() => streamMode.value && sending.value)

  // ---------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------

  /**
   * 加载所有会话列表
   */
  async function fetchSessions() {
    loadingSessions.value = true
    try {
      const res = await listSessions()
      sessions.value = res.data || []
    } catch (e) {
      console.error('fetchSessions error:', e)
    } finally {
      loadingSessions.value = false
    }
  }

  /**
   * 创建新会话
   * @param {string} name
   */
  async function createNewSession(name = '') {
    try {
      const res = await createSession(name)
      const newSession = res.data
      sessions.value.unshift(newSession)
      await switchSession(newSession.session_id)
      return newSession
    } catch (e) {
      console.error('createNewSession error:', e)
    }
  }

  /**
   * 切换会话并加载历史
   * @param {string} sessionId
   */
  async function switchSession(sessionId) {
    if (currentSessionId.value === sessionId) return

    // 中断当前流
    _abortStream?.()
    _abortStream = null
    streamingContent.value = ''
    sending.value = false

    currentSessionId.value = sessionId
    await fetchHistory(sessionId)
  }

  /**
   * 加载会话消息历史
   * @param {string} sessionId
   */
  async function fetchHistory(sessionId) {
    loadingHistory.value = true
    messages.value = []
    try {
      const res = await getSessionHistory(sessionId)
      messages.value = (res.messages || []).map((m, i) => ({
        ...m,
        id: `hist-${i}-${Date.now()}`
      }))
    } catch (e) {
      console.error('fetchHistory error:', e)
    } finally {
      loadingHistory.value = false
    }
  }

  /**
   * 发送消息（根据 streamMode 自动选择普通/流式）
   * @param {string} content
   */
  async function sendUserMessage(content) {
    if (!currentSessionId.value) {
      ElMessage.warning('请先选择或创建一个会话')
      return
    }
    if (sending.value) {
      ElMessage.warning('AI 正在回复中，请稍候...')
      return
    }

    // 先把用户消息追加到本地
    const userMsg = { role: 'user', content, id: `user-${Date.now()}` }
    messages.value.push(userMsg)

    sending.value = true

    if (streamMode.value) {
      // ---- 流式模式 ----
      await _sendStream(content)
    } else {
      // ---- 普通模式 ----
      await _sendNormal(content)
    }
  }

  /** 普通（非流式）发送 */
  async function _sendNormal(content) {
    try {
      const res = await sendMessage(currentSessionId.value, content)
      const aiMsg = {
        role: 'assistant',
        content: res.reply || '',
        id: `ai-${Date.now()}`
      }
      messages.value.push(aiMsg)
      // 刷新会话列表（更新 message_count）
      await _refreshCurrentSessionInList()
    } catch (e) {
      console.error('_sendNormal error:', e)
    } finally {
      sending.value = false
    }
  }

  /** 流式发送（预留，后端支持后自动生效） */
  async function _sendStream(content) {
    // 预先添加一个空的 AI 消息占位
    const aiMsgId = `ai-stream-${Date.now()}`
    const aiMsg = { role: 'assistant', content: '', id: aiMsgId }
    messages.value.push(aiMsg)
    streamingContent.value = ''

    const aiMsgIndex = messages.value.length - 1

    _abortStream = sendMessageStream(
      currentSessionId.value,
      content,
      // onChunk
      (chunk) => {
        streamingContent.value += chunk
        messages.value[aiMsgIndex].content = streamingContent.value
      },
      // onDone
      async () => {
        sending.value = false
        _abortStream = null
        streamingContent.value = ''
        await _refreshCurrentSessionInList()
      },
      // onError
      (error) => {
        ElMessage.error(`流式请求失败: ${error.message}`)
        // 回退到普通模式重试
        messages.value.splice(aiMsgIndex, 1)
        sending.value = false
        ElMessage.info('已自动切换为普通模式重试...')
        streamMode.value = false
        _sendNormal(content)
      }
    )
  }

  /**
   * 刷新当前会话在列表中的信息
   */
  async function _refreshCurrentSessionInList() {
    if (!currentSessionId.value) return
    try {
      const idx = sessions.value.findIndex(
        (s) => s.session_id === currentSessionId.value
      )
      if (idx !== -1) {
        sessions.value[idx].message_count = messages.value.length
        sessions.value[idx].updated_at = new Date().toISOString()
      }
    } catch (e) {
      // 忽略
    }
  }

  /**
   * 清空当前会话历史
   */
  async function clearHistory() {
    if (!currentSessionId.value) return
    try {
      await ElMessageBox.confirm('确认清空当前会话的所有历史记录？', '提示', {
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
        type: 'warning'
      })
      await clearSessionHistory(currentSessionId.value)
      messages.value = []
      const idx = sessions.value.findIndex(
        (s) => s.session_id === currentSessionId.value
      )
      if (idx !== -1) sessions.value[idx].message_count = 0
      ElMessage.success('历史已清空')
    } catch (e) {
      // 用户取消或请求失败均忽略
    }
  }

  /**
   * 删除指定会话
   * @param {string} sessionId
   */
  async function removeSession(sessionId) {
    try {
      await ElMessageBox.confirm('确认删除该会话？此操作不可恢复。', '提示', {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning'
      })
      await deleteSession(sessionId)
      const idx = sessions.value.findIndex((s) => s.session_id === sessionId)
      if (idx !== -1) sessions.value.splice(idx, 1)

      // 如果删除的是当前会话，切换到第一个
      if (currentSessionId.value === sessionId) {
        currentSessionId.value = null
        messages.value = []
        if (sessions.value.length > 0) {
          await switchSession(sessions.value[0].session_id)
        }
      }
      ElMessage.success('会话已删除')
    } catch (e) {
      // 用户取消均忽略
    }
  }

  /**
   * 终止当前流式输出
   */
  function abortStream() {
    _abortStream?.()
    _abortStream = null
    sending.value = false
    streamingContent.value = ''
  }

  /**
   * 切换流式/普通模式
   */
  function toggleStreamMode() {
    streamMode.value = !streamMode.value
    ElMessage.info(streamMode.value ? '已切换为流式响应模式' : '已切换为普通响应模式')
  }

  return {
    // state
    sessions,
    currentSessionId,
    messages,
    loadingSessions,
    loadingHistory,
    sending,
    streamMode,
    streamingContent,
    // getters
    currentSession,
    isStreaming,
    // actions
    fetchSessions,
    createNewSession,
    switchSession,
    fetchHistory,
    sendUserMessage,
    clearHistory,
    removeSession,
    abortStream,
    toggleStreamMode
  }
})
