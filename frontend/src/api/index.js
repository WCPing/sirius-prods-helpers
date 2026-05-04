/**
 * src/api/index.js
 * Axios 实例封装 + 统一请求/响应拦截
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '/api',
  timeout: 300000, // AI 响应可能较慢，设置 300s（5分钟）
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    // 标记了 skipGlobalError 的请求不弹全局错误提示（由调用方自行处理）
    if (!error.config?.skipGlobalError) {
      const msg =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        '请求失败'
      ElMessage.error(msg)
    }
    return Promise.reject(error)
  }
)

export default request
