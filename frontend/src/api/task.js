import request from '@/utils/request'

export function listTasks(params) {
  return request.get('/api/tasks', { params })
}

export function getBoard(params) {
  return request.get('/api/tasks/board', { params })
}

export function createTask(data) {
  return request.post('/api/tasks', data)
}

export function updateTask(id, data) {
  return request.put(`/api/tasks/${id}`, data)
}

export function getTask(id) {
  return request.get(`/api/tasks/${id}`)
}

export function getTaskLogs(id) {
  return request.get(`/api/tasks/${id}/logs`)
}

export function delayTask(id, data) {
  return request.post(`/api/tasks/${id}/delay`, data)
}

export function voidTask(id, data) {
  return request.post(`/api/tasks/${id}/void`, data)
}
