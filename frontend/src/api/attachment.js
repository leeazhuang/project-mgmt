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

// 在线预览链接：后端 inline=1 时浏览器内联展示（图片/PDF/视频/文本等）
export function getPreviewUrl(id) {
  const token = localStorage.getItem('token')
  return `/api/attachments/${id}/download?token=${token}&inline=1`
}
