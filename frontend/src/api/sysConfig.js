import request from '@/utils/request'

export function getAllConfig() {
  return request.get('/api/system/config')
}

export function getConfig(key) {
  return request.get(`/api/system/config/${key}`)
}

export function updateConfig(data) {
  return request.put('/api/system/config', data)
}

export function testWebhook() {
  return request.post('/api/system/config/test-webhook')
}

export function testOss() {
  return request.post('/api/system/config/test-oss')
}
