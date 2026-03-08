/**
 * src/api/conversation.js
 * 会话管理相关 API 封装
 *
 * 对应后端路由：
 *   GET    /api/conversations                        - 列出所有会话
 *   POST   /api/conversations                        - 创建新会话
 *   GET    /api/conversations/{session_id}           - 获取会话详情
 *   GET    /api/conversations/{session_id}/history   - 获取消息历史
 *   POST   /api/conversations/{session_id}/messages  - 发送消息（AI 对话）
 *   DELETE /api/conversations/{session_id}/history   - 清空历史
 *   DELETE /api/conversations/{session_id}           - 删除会话
 */

import request from './index'

/**
 * 列出所有会话
 * @returns {Promise<ListSessionsResponse>}
 */
export function listSessions() {
  return request.get('/conversations')
}

/**
 * 创建新会话
 * @param {string} name - 会话名称（可选）
 * @returns {Promise<SessionDetailResponse>}
 */
export function createSession(name = '') {
  return request.post('/conversations', { name })
}

/**
 * 获取会话详情
 * @param {string} sessionId
 * @returns {Promise<SessionDetailResponse>}
 */
export function getSession(sessionId) {
  return request.get(`/conversations/${sessionId}`)
}

/**
 * 获取会话消息历史
 * @param {string} sessionId
 * @returns {Promise<SessionHistoryResponse>}
 */
export function getSessionHistory(sessionId) {
  return request.get(`/conversations/${sessionId}/history`)
}

/**
 * 发送消息（普通模式）
 * @param {string} sessionId
 * @param {string} message - 用户消息内容
 * @returns {Promise<ChatResponse>}
 */
export function sendMessage(sessionId, message) {
  return request.post(`/conversations/${sessionId}/messages`, { message })
}

/**
 * 发送消息（流式模式 - 预留接口）
 * 后端需要实现 SSE 流式响应端点 /api/conversations/{session_id}/messages/stream
 *
 * @param {string} sessionId
 * @param {string} message
 * @param {function} onChunk - 每次收到 chunk 时的回调 (chunk: string) => void
 * @param {function} onDone  - 流结束时的回调 () => void
 * @param {function} onError - 错误时的回调 (error: Error) => void
 * @returns {() => void} abort 函数，用于提前终止流
 */
export function sendMessageStream(sessionId, message, onChunk, onDone, onError) {
  const controller = new AbortController()

  fetch(`/api/conversations/${sessionId}/messages/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal: controller.signal
  })
    .then(async (response) => {
      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || err.message || `HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')

      const read = async () => {
        while (true) {
          const { done, value } = await reader.read()
          if (done) {
            onDone?.()
            break
          }
          // SSE 格式：data: <json>\n\n
          const text = decoder.decode(value, { stream: true })
          const lines = text.split('\n')
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6).trim()
              if (data === '[DONE]') {
                onDone?.()
                return
              }
              try {
                const parsed = JSON.parse(data)
                onChunk?.(parsed.content || parsed.delta || data)
              } catch {
                onChunk?.(data)
              }
            }
          }
        }
      }

      await read()
    })
    .catch((error) => {
      if (error.name !== 'AbortError') {
        onError?.(error)
      }
    })

  // 返回终止函数
  return () => controller.abort()
}

/**
 * 清空会话历史
 * @param {string} sessionId
 * @returns {Promise<BaseResponse>}
 */
export function clearSessionHistory(sessionId) {
  return request.delete(`/conversations/${sessionId}/history`)
}

/**
 * 删除会话
 * @param {string} sessionId
 * @returns {Promise<BaseResponse>}
 */
export function deleteSession(sessionId) {
  return request.delete(`/conversations/${sessionId}`)
}
