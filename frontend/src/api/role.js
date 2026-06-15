import request from '@/utils/request'

export function listRoles(params) {
  return request.get('/api/roles', { params })
}

export function createRole(data) {
  return request.post('/api/roles', data)
}

export function updateRole(id, data) {
  return request.put(`/api/roles/${id}`, data)
}

export function deleteRole(id) {
  return request.delete(`/api/roles/${id}`)
}
