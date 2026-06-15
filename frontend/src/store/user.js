import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '@/utils/request'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || 'null'))
  const permissions = ref(JSON.parse(localStorage.getItem('permissions') || '[]'))
  const menus = ref(JSON.parse(localStorage.getItem('menus') || '[]'))

  const isLoggedIn = computed(() => !!token.value)

  async function login(username, password) {
    // 拦截器已解包，res 就是 {access_token, user_id, ...}
    const res = await request.post('/api/auth/login', { username, password })
    token.value = res.access_token
    localStorage.setItem('token', res.access_token)
    return res
  }

  async function fetchUserInfo() {
    // 拦截器已解包，res 就是 {id, username, permissions, menus, ...}
    const res = await request.get('/api/auth/userinfo')
    userInfo.value = res
    permissions.value = res.permissions || []
    menus.value = res.menus || []
    localStorage.setItem('userInfo', JSON.stringify(res))
    localStorage.setItem('permissions', JSON.stringify(res.permissions || []))
    localStorage.setItem('menus', JSON.stringify(res.menus || []))
    return res
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    permissions.value = []
    menus.value = []
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
    localStorage.removeItem('permissions')
    localStorage.removeItem('menus')
  }

  function hasPermission(code) {
    if (!userInfo.value) return false
    const roles = userInfo.value.roles || []
    if (roles.some(r => (typeof r === 'string' ? r : r.code) === 'super_admin')) return true
    return permissions.value.includes(code)
  }

  return {
    token,
    userInfo,
    permissions,
    menus,
    isLoggedIn,
    login,
    fetchUserInfo,
    logout,
    hasPermission
  }
})
