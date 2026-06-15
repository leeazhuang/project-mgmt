import request from '@/utils/request'

export function listMenus(params) {
  return request.get('/api/menus', { params })
}

export function createMenu(data) {
  return request.post('/api/menus', data)
}

export function updateMenu(id, data) {
  return request.put(`/api/menus/${id}`, data)
}

export function deleteMenu(id) {
  return request.delete(`/api/menus/${id}`)
}
