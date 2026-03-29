/**
 * src/api/knowledge.js
 * 知识源管理相关 API 封装
 *
 * 对应后端路由：
 *   POST   /api/knowledge-sources              - 注册知识源
 *   GET    /api/knowledge-sources              - 列出所有知识源
 *   GET    /api/knowledge-sources/{id}         - 知识源详情
 *   DELETE /api/knowledge-sources/{id}         - 删除知识源
 *   POST   /api/knowledge-sources/{id}/index   - 触发索引
 *   POST   /api/knowledge-sources/{id}/sync    - 同步代码
 *   GET    /api/knowledge-sources/{id}/stats   - 索引统计
 */

import request from './index'

export function listSources() {
  return request.get('/knowledge-sources')
}

export function registerSource(data) {
  return request.post('/knowledge-sources', data)
}

export function getSource(id) {
  return request.get(`/knowledge-sources/${id}`)
}

export function deleteSource(id) {
  return request.delete(`/knowledge-sources/${id}`)
}

export function triggerIndex(id) {
  return request.post(`/knowledge-sources/${id}/index`)
}

export function syncSource(id) {
  return request.post(`/knowledge-sources/${id}/sync`)
}

export function getSourceStats(id) {
  return request.get(`/knowledge-sources/${id}/stats`)
}
