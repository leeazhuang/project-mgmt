import request from '@/utils/request'

export function login(username, password) {
  return request.post('/api/auth/login', { username, password })
}

export function getUserInfo() {
  return request.get('/api/auth/userinfo')
}
