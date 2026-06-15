import request from '@/utils/request'

export function listUsers(params) {
  return request.get('/api/users', { params })
}

export function getUserOptions() {
  return request.get('/api/users/options')
}

export function createUser(data) {
  return request.post('/api/users', data)
}

export function updateUser(id, data) {
  return request.put(`/api/users/${id}`, data)
}

export function deleteUser(id) {
  return request.delete(`/api/users/${id}`)
}

export function resetPassword(id, data) {
  return request.post(`/api/users/${id}/reset-password`, data)
}
