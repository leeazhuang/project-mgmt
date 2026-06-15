import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

const Layout = () => import('@/layout/index.vue')

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录' }
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '工作台' }
      },
      {
        path: 'project',
        name: 'Project',
        component: () => import('@/views/project/index.vue'),
        meta: { title: '项目列表', permission: 'project:list' }
      },
      {
        path: 'project/:id',
        name: 'ProjectDetail',
        component: () => import('@/views/project/detail.vue'),
        meta: { title: '项目详情', permissionAny: ['project:list'] }
      },
      {
        path: 'requirement',
        name: 'Requirement',
        component: () => import('@/views/requirement/index.vue'),
        meta: { title: '需求列表', permission: 'requirement:list' }
      },
      {
        path: 'requirement/:id',
        name: 'RequirementDetail',
        component: () => import('@/views/requirement/detail.vue'),
        meta: { title: '需求详情', permissionAny: ['requirement:list', 'requirement:create'] }
      },
      {
        path: 'task',
        name: 'Task',
        component: () => import('@/views/task/index.vue'),
        meta: { title: '任务列表', permission: 'task:list' }
      },
      {
        path: 'task/board',
        name: 'TaskBoard',
        component: () => import('@/views/task/board.vue'),
        meta: { title: '任务看板', permission: 'task:list' }
      },
      {
        path: 'task/mytasks',
        name: 'MyTasks',
        component: () => import('@/views/task/mytasks.vue'),
        meta: { title: '我的任务', permission: 'task:mytasks' }
      },
      {
        path: 'task/:id',
        name: 'TaskDetail',
        component: () => import('@/views/task/detail.vue'),
        meta: { title: '任务详情', permissionAny: ['task:list', 'task:mytasks'] }
      },
      {
        path: 'bug',
        name: 'Bug',
        component: () => import('@/views/bug/index.vue'),
        meta: { title: 'Bug列表', permission: 'bug:list' }
      },
      {
        path: 'bug/mybugs',
        name: 'MyBugs',
        component: () => import('@/views/bug/mybugs.vue'),
        meta: { title: 'Bug跟踪', permission: 'bug:mybugs' }
      },
      {
        path: 'bug/:id',
        name: 'BugDetail',
        component: () => import('@/views/bug/detail.vue'),
        meta: { title: 'Bug详情', permissionAny: ['bug:list', 'bug:mybugs', 'bug:create'] }
      },
      {
        path: 'system/user',
        name: 'SystemUser',
        component: () => import('@/views/system/user/index.vue'),
        meta: { title: '用户管理', permission: 'user:list' }
      },
      {
        path: 'system/role',
        name: 'SystemRole',
        component: () => import('@/views/system/role/index.vue'),
        meta: { title: '角色管理', permission: 'role:list' }
      },
      {
        path: 'system/menu',
        name: 'SystemMenu',
        component: () => import('@/views/system/menu/index.vue'),
        meta: { title: '菜单管理', permission: 'menu:list' }
      },
      {
        path: 'system/config',
        name: 'SystemConfig',
        component: () => import('@/views/system/config/index.vue'),
        meta: { title: '系统设置', permission: 'config:list' }
      },
      {
        path: 'log',
        name: 'Log',
        component: () => import('@/views/log/index.vue'),
        meta: { title: '操作日志', permission: 'log:list' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')

  if (to.path !== '/login' && !token) {
    next('/login')
    return
  }

  if (to.path === '/login' && token) {
    next('/dashboard')
    return
  }

  if (!token) {
    next()
    return
  }

  const permissions = JSON.parse(localStorage.getItem('permissions') || '[]')
  const roles = JSON.parse(localStorage.getItem('userInfo') || '{}')?.roles || []
  const isSuperAdmin = roles.includes('super_admin') || roles.some(r => r?.code === 'super_admin')

  if (isSuperAdmin) {
    next()
    return
  }

  // 精确匹配：需要某一个特定权限
  const requiredPermission = to.meta?.permission
  if (requiredPermission && !permissions.includes(requiredPermission)) {
    ElMessage.error('没有访问权限')
    next('/dashboard')
    return
  }

  // 模糊匹配：需要任意一个权限（用于详情页）
  const permissionAny = to.meta?.permissionAny
  if (permissionAny && permissionAny.length) {
    const hasAny = permissionAny.some(p => permissions.includes(p))
    if (!hasAny) {
      ElMessage.error('没有访问权限')
      next('/dashboard')
      return
    }
  }

  next()
})

export default router
