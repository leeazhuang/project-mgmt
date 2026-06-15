import request from '@/utils/request'

export function listProjects(params) {
  return request.get('/api/projects', { params })
}

export function getProject(id) {
  return request.get(`/api/projects/${id}`)
}

export function createProject(data) {
  return request.post('/api/projects', data)
}

export function updateProject(id, data) {
  return request.put(`/api/projects/${id}`, data)
}

export function listMembers(projectId) {
  return request.get(`/api/projects/${projectId}/members`)
}

export function addMembers(projectId, data) {
  return request.post(`/api/projects/${projectId}/members`, data)
}

export function removeMember(projectId, userId) {
  return request.delete(`/api/projects/${projectId}/members/${userId}`)
}
