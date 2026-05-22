<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import {
  HomeFilled, Monitor, EditPen, Document, Notebook, Folder,
  TrendCharts, Histogram, Setting, Bell, QuestionFilled, Plus,
  Sunny, Moon, Fold, Expand, OfficeBuilding,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTaskStore } from '@/stores/task'
import { useSessionStore } from '@/stores/session'
import { miscApi, notificationApi, type NotificationItem } from '@/api/client'
import { useRouteMotion } from '@/composables/useAnime'

const route = useRoute()
const router = useRouter()
const task = useTaskStore()
const session = useSessionStore()
const notifications = ref<NotificationItem[]>([])
const sideCollapsed = ref(false)

useRouteMotion(() => route.fullPath)

interface NavItem {
  path: string
  label: string
  icon: any
  badge?: string
  badgeText?: string
  badgeKind?: 'count' | 'text'
}

const navTop = computed<NavItem[]>(() => {
  const running = task.tasks.filter((t) =>
    ['created', 'planning', 'researching', 'quality_gate', 'writing'].includes(t.status),
  ).length
  const pendingReview = task.tasks.filter((t) => t.status === 'waiting_review').length
  const items: NavItem[] = [
    { path: '/',               label: '首页 / 新任务', icon: HomeFilled },
    { path: '/projects',       label: '研究项目',      icon: OfficeBuilding },
    { path: '/workbench',      label: '任务工作台',    icon: Monitor,   badgeText: '进行中', badge: String(running || ''), badgeKind: 'text' },
    { path: '/plan-review',    label: '计划审查',      icon: EditPen,   badgeText: '待审查', badge: String(pendingReview || ''), badgeKind: 'text' },
    { path: '/citation-check', label: '引用验证',      icon: Document },
    { path: '/reports',        label: '报告与引用',    icon: Notebook },
    { path: '/knowledge',      label: '知识库',        icon: Folder },
    { path: '/cost',           label: '成本看板',      icon: TrendCharts },
    { path: '/history',        label: '历史记录',      icon: Histogram },
  ]
  return items.map((item) => item.badge ? item : { ...item, badge: undefined })
})
const navBottom: NavItem[] = [
  { path: '/settings', label: '设置', icon: Setting },
]

function isActive(path: string) {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(path + '/')
}
function go(path: string) { router.push(path) }
function toggleSidebar() { sideCollapsed.value = !sideCollapsed.value }
function newTask() {
  if (route.path === '/') {
    ElMessage.info('已在新任务页')
    return
  }
  router.push('/')
}

async function openNotifications() {
  try {
    const payload = await notificationApi.list(20)
    notifications.value = payload.items
    if (!payload.items.length) {
      ElMessage.info('当前没有需要处理的通知')
      return
    }
    const first = payload.items[0]
    ElMessage.info(first.title)
    router.push(first.route)
  } catch (err) {
    ElMessage.error((err as Error).message)
  }
}

async function openHelp() {
  try {
    const payload = await miscApi.quickStart()
    const labels = payload.items.map((item) => item.label).join(' / ')
    ElMessage.info(labels || '暂无帮助链接')
  } catch (err) {
    ElMessage.error((err as Error).message)
  }
}

const pageTitle = computed(() => {
  if (route.name === 'task') return `历史记录 / ${route.params.id}`
  const t = String(route.meta.title || '')
  const sub = String(route.meta.subtitle || '')
  return sub ? `${t} / ${sub}` : t
})

// A research plan needs human sign-off before research starts — the run is
// genuinely blocked until the user decides, so prompt them to go review it.
watch(() => task.planReview, (pr) => {
  if (!pr) return
  task.planReview = null
  ElMessageBox.confirm(
    `研究计划已生成(${pr.topicCount} 个研究方向),需要你审批后才会开始检索。现在去审查?`,
    '研究计划待审批',
    { confirmButtonText: '去审查', cancelButtonText: '稍后', type: 'warning' },
  ).then(() => { router.push('/plan-review') }).catch(() => { /* dismissed */ })
})

// When a task reaches the citation-review step, prompt the user (manual mode)
// or report the second model's verdicts (auto mode). Watching the store here
// means the prompt fires no matter which page the user is currently on.
watch(() => task.citationReview, (cr) => {
  if (!cr) return
  task.citationReview = null
  if (cr.mode === 'manual') {
    ElMessageBox.confirm(
      `本次研究生成了 ${cr.total} 条引用,建议人工逐条核对来源。现在前往「引用验证」?`,
      '引用待验证',
      { confirmButtonText: '去验证', cancelButtonText: '稍后', type: 'info' },
    ).then(() => { router.push('/citation-check') }).catch(() => { /* dismissed */ })
  } else if (cr.mode === 'auto') {
    ElMessage.success(
      `第二个模型已自动核对 ${cr.total} 条引用 · 通过 ${cr.counts.pass}`
      + ` / 存疑 ${cr.counts.flag} / 驳回 ${cr.counts.reject}`,
    )
  }
})

onMounted(async () => {
  await Promise.allSettled([session.refreshConfig(), session.refreshHealth(), task.refreshTasks()])
  try {
    notifications.value = (await notificationApi.list(20)).items
  } catch {
    notifications.value = []
  }
})
</script>

<template>
  <div class="app-shell" :class="{ 'side-collapsed': sideCollapsed }">
    <!-- Sidebar -->
    <!-- Kept in the DOM when collapsed so the grid's first track still has an
         occupant; the .side-collapsed CSS shrinks the track to 0 and fades it
         out. Removing it (v-show) would drop .main into the 0-width column. -->
    <aside class="app-side" :aria-hidden="sideCollapsed" :inert="sideCollapsed">
      <div class="brand">
        <div class="brand-logo">A</div>
        <div class="brand-name">Athena</div>
        <button class="side-collapse-btn" aria-label="隐藏导航栏" @click="toggleSidebar">
          <ElIcon><Fold /></ElIcon>
        </button>
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
        <div class="topbar-left">
          <button
            v-if="sideCollapsed"
            class="side-restore"
            aria-label="显示导航栏"
            @click="toggleSidebar"
          >
            <ElIcon><Expand /></ElIcon>
          </button>
          <h1 v-html="pageTitle.replace(/ \/ /g, ' <span class=&quot;crumb-sep&quot;>/</span> <span class=&quot;crumb-light&quot;>')+'</span>'" />
        </div>
        <div class="topbar-right">
          <button class="icon-btn" :aria-label="session.isDark ? '切换浅色主题' : '切换深色主题'" @click="session.toggleTheme()">
            <ElIcon><component :is="session.isDark ? Sunny : Moon" /></ElIcon>
          </button>
          <button class="icon-btn" aria-label="通知" @click="openNotifications">
            <ElIcon><Bell /></ElIcon>
            <span v-if="notifications.length" class="badge-dot" />
          </button>
          <button class="icon-btn" aria-label="帮助" @click="openHelp">
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
