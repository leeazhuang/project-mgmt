import request from '@/utils/request'

export function listRequirements(params) {
  return request.get('/api/requirements', { params })
}

export function createRequirement(data) {
  return request.post('/api/requirements', data)
}

export function updateRequirement(id, data) {
  return request.put(`/api/requirements/${id}`, data)
}

export function submitRequirement(id) {
  return request.post(`/api/requirements/${id}/submit`)
}

export function approveRequirement(id, data) {
  return request.post(`/api/requirements/${id}/approve`, data)
}

export function listRequirementLogs(id) {
  return request.get(`/api/requirements/${id}/approval-logs`)
}

export function getRequirement(id) {
  return request.get(`/api/requirements/${id}`)
}

export function changeRequirementStatus(id, data) {
  return request.post(`/api/requirements/${id}/change-status`, data)
}

export function setEstimatedDeadline(id, data) {
  return request.post(`/api/requirements/${id}/set-estimated-deadline`, data)
}

export function delayRequirement(id, data) {
  return request.post(`/api/requirements/${id}/delay`, data)
}
