import { useUserStore } from '@/store/user'

export function hasPermission(code) {
  const userStore = useUserStore()
  return userStore.hasPermission(code)
}
