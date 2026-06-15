import request from '@/utils/request'

export function login(username, password) {
  return request.post('/api/auth/login', { username, password })
}

export function getUserInfo() {
  return request.get('/api/auth/userinfo')
}

export function changePassword(data) {
  return request.post('/api/auth/change-password', data)
}
