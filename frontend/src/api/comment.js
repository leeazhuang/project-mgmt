import request from '@/utils/request'

export function listComments(params) {
  return request.get('/api/comments', { params })
}

export function createComment(data) {
  return request.post('/api/comments', data)
}
