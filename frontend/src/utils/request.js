import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router/index'

const request = axios.create({
  baseURL: '/',
  timeout: 15000
})

request.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  response => {
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
