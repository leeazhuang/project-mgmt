import request from '@/utils/request'

export function getDashboardOverview(params) {
  return request.get('/api/dashboard/overview', { params })
}

export function getMyTodo(params) {
  return request.get('/api/dashboard/my-todo', { params })
}
