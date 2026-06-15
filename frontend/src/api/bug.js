import request from '@/utils/request'

export function listBugs(params) {
  return request.get('/api/bugs', { params })
}

export function getBug(id) {
  return request.get(`/api/bugs/${id}`)
}

export function createBug(data) {
  return request.post('/api/bugs', data)
}

export function assignBug(id, data) {
  return request.post(`/api/bugs/${id}/assign`, data)
}

export function rejectBug(id, data) {
  return request.post(`/api/bugs/${id}/reject`, data)
}

export function startFix(id) {
  return request.post(`/api/bugs/${id}/start-fix`)
}

export function markFixed(id, data) {
  return request.post(`/api/bugs/${id}/fixed`, data)
}

export function reopenBug(id, data) {
  return request.post(`/api/bugs/${id}/reopen`, data)
}

export function reassignBug(id, data) {
  return request.post(`/api/bugs/${id}/reassign`, data)
}

export function getBugLogs(id) {
  return request.get(`/api/bugs/${id}/logs`)
}
