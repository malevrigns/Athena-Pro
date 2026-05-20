import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useSessionStore } from '@/stores/session'

const routes: RouteRecordRaw[] = [
  { path: '/',               name: 'home',       component: () => import('@/views/HomeView.vue'),         meta: { title: '首页', subtitle: '新任务' } },
  { path: '/workbench',      name: 'workbench',  component: () => import('@/views/WorkbenchView.vue'),    meta: { title: '任务工作台' } },
  { path: '/workbench/:id',  name: 'workbench-detail', component: () => import('@/views/WorkbenchView.vue'), props: true, meta: { title: '任务工作台' } },
  { path: '/plan-review',    name: 'plan-review', component: () => import('@/views/PlanReviewView.vue'),  meta: { title: '计划审查' } },
  { path: '/citation-check', name: 'citation-check', component: () => import('@/views/CitationCheckView.vue'), meta: { title: '引用验证' } },
  { path: '/reports',        name: 'reports',     component: () => import('@/views/ReportsView.vue'),     meta: { title: '报告与引用' } },
  { path: '/knowledge',      name: 'knowledge',   component: () => import('@/views/KnowledgeView.vue'),   meta: { title: '知识库' } },
  { path: '/cost',           name: 'cost',        component: () => import('@/views/CostView.vue'),        meta: { title: '成本看板' } },
  { path: '/history',        name: 'history',     component: () => import('@/views/HistoryView.vue'),     meta: { title: '历史记录' } },
  { path: '/settings',       name: 'settings',    component: () => import('@/views/SettingsView.vue'),    meta: { title: '设置' } },
  { path: '/tasks/:id',      name: 'task',        component: () => import('@/views/TaskView.vue'),        props: true, meta: { title: '任务详情' } },
]

const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach((to) => {
  document.title = `${String(to.meta.title || 'Athena Pro')} · Athena Pro`
  if (to.name !== 'settings') {
    try {
      const session = useSessionStore()
      if (session.config && session.config.require_auth && !session.hasApiKey) {
        return { name: 'settings', query: { next: to.fullPath } }
      }
    } catch {
      /* pinia not ready yet — let through */
    }
  }
  return true
})
export default router
