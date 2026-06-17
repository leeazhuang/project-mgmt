import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router/index'

const request = axios.create({
  baseURL: '/',
  timeout: 15000
})

// ============ 写操作请求去重（防连点重复提交）============
// 同一写请求（method+url+params+body）在未返回前再次发起，直接取消重复的那个，
// 只让第一个打到后端。请求返回（成功/失败）即解锁。
const pendingRequests = new Map()

function stableStringify(obj) {
  if (obj === null || obj === undefined) return ''
  if (typeof obj !== 'object') return JSON.stringify(obj)
  if (typeof obj === 'string') return obj
  if (Array.isArray(obj)) return '[' + obj.map(stableStringify).join(',') + ']'
  const keys = Object.keys(obj).sort()
  return '{' + keys.map(k => JSON.stringify(k) + ':' + stableStringify(obj[k])).join(',') + '}'
}

function dedupKeyOf(config) {
  const method = (config.method || 'get').toLowerCase()
  // 只对写操作去重；文件上传(FormData)无法稳定序列化，跳过
  if (!['post', 'put', 'delete', 'patch'].includes(method)) return ''
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) return ''
  const data = typeof config.data === 'string' ? config.data : stableStringify(config.data)
  return `${method}:${config.url}:${stableStringify(config.params)}:${data}`
}

function removePending(config) {
  const key = config && config.__dedupKey
  if (key && pendingRequests.has(key)) pendingRequests.delete(key)
}

request.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    const key = dedupKeyOf(config)
    if (key) {
      config.__dedupKey = key
      const controller = new AbortController()
      config.signal = controller.signal
      if (pendingRequests.has(key)) {
        // 重复请求：取消当前这个，不再打到后端
        controller.abort()
      } else {
        pendingRequests.set(key, true)
      }
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  response => {
    removePending(response.config)
    const res = response.data
    // 后端统一返回 {code, message, data}
    if (res.code !== undefined && res.code !== 200) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message))
    }
    // 直接返回 data 字段，简化页面调用
    return res.data !== undefined ? res.data : res
  },
  error => {
    // 被去重取消的重复请求：静默丢弃，不报错、不重复弹提示
    if (axios.isCancel(error)) {
      return new Promise(() => {})
    }
    removePending(error.config)
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        // 登录接口的401是密码错误，不是过期
        if (error.config?.url?.includes('/api/auth/login')) {
          ElMessage.error(data?.detail || '用户名或密码错误')
        } else {
          localStorage.removeItem('token')
          localStorage.removeItem('userInfo')
          router.push('/login')
          ElMessage.error('登录已过期，请重新登录')
        }
      } else if (status === 403) {
        ElMessage.error(data?.detail || '权限不足')
        // 页面加载类请求（GET）越权 → 跳回首页，避免停留在无权限页面看到残留数据
        if ((error.config?.method || '').toLowerCase() === 'get') {
          router.push('/')
        }
      } else if (status === 422) {
        ElMessage.error(data?.detail?.[0]?.msg || '参数验证失败')
      } else {
        ElMessage.error(data?.detail || data?.message || '请求失败')
      }
    } else {
      ElMessage.error('网络连接失败，请检查网络')
    }
    return Promise.reject(error)
  }
)

export default request
