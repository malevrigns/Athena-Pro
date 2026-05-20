import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useSessionStore } from '@/stores/session'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    children: [
      {
        path: '',
        name: 'home',
        component: () => import('@/views/HomeView.vue'),
        meta: { title: '新研究' },
      },
      {
        path: 'task/:id',
        name: 'task',
        component: () => import('@/views/TaskView.vue'),
        meta: { title: '研究任务' },
        props: true,                  // 让 :id 作为 prop 传进 TaskView
      },
      {
        path: 'history',
        name: 'history',
        component: () => import('@/views/HistoryView.vue'),
        meta: { title: '历史会话' },
      },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '成本仪表盘' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: { title: '偏好设置' },
      },
    ],
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { requiresAuth: false },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 全局守卫 · 登录检查 + 标题设置
router.beforeEach(async (to) => {
  // 1. 设置浏览器标签页标题
  if (to.meta.title) {
    document.title = `${to.meta.title} · Athena`
  }
  
  // 2. 登录检查(login 页本身除外)
  if (to.meta.requiresAuth !== false) {
    const session = useSessionStore()
    if (!session.isAuthenticated) {
      await session.tryAutoLogin()
      if (!session.isAuthenticated) {
        return { name: 'login', query: { redirect: to.fullPath } }
      }
    }
  }
})

export default router