import request from '@/utils/request'

export function listNotifications(params) {
  return request.get('/api/notifications', { params })
}

export function getUnreadCount() {
  return request.get('/api/notifications/unread-count')
}

export function markRead(id) {
  return request.post(`/api/notifications/${id}/read`)
}

export function markAllRead() {
  return request.post('/api/notifications/read-all')
}
