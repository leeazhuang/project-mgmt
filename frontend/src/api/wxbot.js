import request from '@/utils/request'

export function getWxGroups() {
  return request.get('/api/wxbot/groups')
}

export function getWxGroupMembers(roomId) {
  return request.get(`/api/wxbot/groups/${encodeURIComponent(roomId)}/members`)
}

export function testWxBot(data) {
  return request.post('/api/wxbot/test', data)
}
