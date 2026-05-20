<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import {
  HomeFilled, Monitor, EditPen, Document, Notebook, Folder,
  TrendCharts, Histogram, Setting, Bell, QuestionFilled, Plus,
  Sunny, Moon,
} from '@element-plus/icons-vue'
import { useTaskStore } from '@/stores/task'
import { useSessionStore } from '@/stores/session'

const route = useRoute()
const router = useRouter()
const task = useTaskStore()
const session = useSessionStore()

interface NavItem {
  path: string
  label: string
  icon: any
  badge?: string
  badgeText?: string
  badgeKind?: 'count' | 'text'
}

const navTop: NavItem[] = [
  { path: '/',               label: '首页 / 新任务', icon: HomeFilled },
  { path: '/workbench',      label: '任务工作台',    icon: Monitor,   badgeText: '进行中', badge: '3', badgeKind: 'text' },
  { path: '/plan-review',    label: '计划审查',      icon: EditPen,   badgeText: '待审查', badge: '1', badgeKind: 'text' },
  { path: '/citation-check', label: '引用验证',      icon: Document,  badgeText: '需要处理', badge: '2', badgeKind: 'text' },
  { path: '/reports',        label: '报告与引用',    icon: Notebook },
  { path: '/knowledge',      label: '知识库',        icon: Folder },
  { path: '/cost',           label: '成本看板',      icon: TrendCharts },
  { path: '/history',        label: '历史记录',      icon: Histogram },
]
const navBottom: NavItem[] = [
  { path: '/settings', label: '设置', icon: Setting },
]

function isActive(path: string) {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(path + '/')
}
function go(path: string) { router.push(path) }
function newTask() { router.push('/') }

const pageTitle = computed(() => {
  if (route.name === 'task') return `历史记录 / ${route.params.id}`
  const t = String(route.meta.title || '')
  const sub = String(route.meta.subtitle || '')
  return sub ? `${t} / ${sub}` : t
})

onMounted(async () => {
  await Promise.allSettled([session.refreshConfig(), session.refreshHealth(), task.refreshTasks()])
})
</script>

<template>
  <div class="app-shell">
    <!-- Sidebar -->
    <aside class="app-side">
      <div class="brand">
        <div class="brand-logo">A</div>
        <div class="brand-name">Athena</div>
      </div>

      <div class="nav-group">
        <div
          v-for="item in navTop"
          :key="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          @click="go(item.path)"
        >
          <ElIcon><component :is="item.icon" /></ElIcon>
          <span class="label">{{ item.label }}</span>
          <template v-if="item.badge">
            <span class="nav-badge-text">{{ item.badgeText }}</span>
            <span class="nav-badge">{{ item.badge }}</span>
          </template>
        </div>
      </div>

      <div class="nav-divider" />

      <div class="nav-group">
        <div
          v-for="item in navBottom"
          :key="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          @click="go(item.path)"
        >
          <ElIcon><component :is="item.icon" /></ElIcon>
          <span class="label">{{ item.label }}</span>
        </div>
      </div>
    </aside>

    <!-- Main -->
    <main class="main">
      <header class="topbar">
        <h1 v-html="pageTitle.replace(/ \/ /g, ' <span class=&quot;crumb-sep&quot;>/</span> <span class=&quot;crumb-light&quot;>')+'</span>'" />
        <div class="topbar-right">
          <button class="icon-btn" :aria-label="session.isDark ? '切换浅色主题' : '切换深色主题'" @click="session.toggleTheme()">
            <ElIcon><component :is="session.isDark ? Sunny : Moon" /></ElIcon>
          </button>
          <button class="icon-btn" aria-label="通知">
            <ElIcon><Bell /></ElIcon>
            <span class="badge-dot" />
          </button>
          <button class="icon-btn" aria-label="帮助">
            <ElIcon><QuestionFilled /></ElIcon>
          </button>
          <button class="primary-btn" @click="newTask">
            <ElIcon><Plus /></ElIcon>
            <span>新建研究任务</span>
          </button>
        </div>
      </header>

      <section class="main-body">
        <RouterView v-slot="{ Component }">
          <Transition name="fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </section>
    </main>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity .15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
:deep(.crumb-light) { color: var(--muted); font-weight: 500; }
</style>
