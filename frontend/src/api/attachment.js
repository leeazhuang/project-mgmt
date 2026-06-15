import request from '@/utils/request'

export function listAttachments(params) {
  return request.get('/api/attachments', { params })
}

export function uploadAttachment(data) {
  return request.post('/api/attachments', data, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function deleteAttachment(id) {
  return request.delete(`/api/attachments/${id}`)
}

export function bindAttachments(data) {
  return request.post('/api/attachments/bindTarget', data)
}

export function getDownloadUrl(id) {
  const token = localStorage.getItem('token')
  return `/api/attachments/${id}/download?token=${token}`
}
