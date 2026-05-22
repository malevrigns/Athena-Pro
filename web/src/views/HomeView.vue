<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, MagicStick, ChatLineRound, Reading, DataAnalysis, Bell, Right, Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import anime from 'animejs'
import { useTaskStore } from '@/stores/task'
import { useSessionStore } from '@/stores/session'
import { miscApi } from '@/api/client'

const router = useRouter()
const task = useTaskStore()
const session = useSessionStore()
const MIN_QUESTION_LENGTH = 8

const question = ref('')
const heroTitleRef = ref<HTMLElement | null>(null)
const heroSubRef = ref<HTMLElement | null>(null)
const heroInputRef = ref<HTMLElement | null>(null)
const kpiRefs = ref<HTMLElement[]>([])
const featureRefs = ref<HTMLElement[]>([])
const suggestionRefs = ref<HTMLElement[]>([])
const recentRefs = ref<HTMLElement[]>([])
const sparkContainer = ref<HTMLElement | null>(null)
const inputFocused = ref(false)

const placeholderText = '把你的研究问题告诉 Athena …  例: 调研 2026 年企业级 RAG 平台的成本结构与评估方法'

const suggestions = [
  { icon: MagicStick, title: '调研 2026 Agent 框架', desc: 'LangGraph / CrewAI / AutoGen 横评',  color: '#6366f1' },
  { icon: ChatLineRound, title: '企业 RAG 落地',      desc: '金融客服场景的架构与评估',         color: '#10b981' },
  { icon: Reading, title: '深度报告',                  desc: 'RAG 评估框架与可观测平台',         color: '#f59e0b' },
  { icon: DataAnalysis, title: '技术对比',             desc: '边缘端轻量模型部署最佳实践',       color: '#ec4899' },
]

const features = [
  { icon: '⚡', title: '并行研究', desc: '多 Agent 同时拆题、检索、综合', accent: '#6366f1' },
  { icon: '🔗', title: '真实引用', desc: 'DuckDuckGo + Gemma 真实信源', accent: '#10b981' },
  { icon: '🧠', title: 'Gemma 驱动', desc: '自托管 vLLM,数据不出网',     accent: '#ec4899' },
]

const overview = computed(() => {
  const ts = task.tasks
  return {
    done:      ts.filter((t) => t.status === 'done').length,
    running:   ts.filter((t) => ['planning','researching','writing','quality_gate','waiting_review','created'].includes(t.status)).length,
    citations: ts.reduce((s, t) => s + (t.final_report?.citations?.length ?? 0), 0),
    cost:      ts.reduce((s, t) => s + (t.cost_usd || 0), 0),
  }
})
const kpiValues = computed(() => ([
  { label: '完成研究', value: overview.value.done,      suffix: '' },
  { label: '进行中',   value: overview.value.running,   suffix: '' },
  { label: '引用累计', value: overview.value.citations, suffix: '' },
  { label: '成本支出', value: overview.value.cost,      suffix: 'USD', prefix: '$', precision: 2 },
]))

const announcements = ref<{ date: string; title: string; desc: string }[]>([])
const recent = computed(() =>
  [...task.tasks].sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')).slice(0, 5),
)

const hasEnoughQuestion = computed(() => question.value.trim().length >= MIN_QUESTION_LENGTH)
const canSubmit = computed(() => !task.loading && !task.isRunning)

async function submit() {
  if (!canSubmit.value) return
  const trimmed = question.value.trim()
  if (!hasEnoughQuestion.value) {
    ElMessage.warning(`请至少输入 ${MIN_QUESTION_LENGTH} 个字符后再开始研究`)
    focusHeroInput()
    return
  }
  if (session.config?.require_auth && !session.hasApiKey) {
    ElMessage.warning('请先到「设置」配置 API Key')
    router.push({ name: 'settings', query: { next: '/' } })
    return
  }
  // Submit button click → ripple
  buttonRipple()
  try {
    await task.start(trimmed, session.userId)
    if (task.error) {
      ElMessage.error(task.error)
      return
    }
    if (task.current?.id) router.push(`/workbench/${task.current.id}`)
  } catch (err) {
    ElMessage.error((err as Error).message)
  }
}

function pickSuggestion(t: typeof suggestions[number], idx: number) {
  question.value = `${t.title}: ${t.desc}`
  ElMessage.info('已填入建议问题')
  // Pulse animation on click
  const el = suggestionRefs.value[idx]
  if (el) {
    anime({
      targets: el,
      scale: [{ value: 0.96, duration: 120 }, { value: 1, duration: 220, easing: 'easeOutBack' }],
    })
  }
  // Focus input + flash glow
  requestAnimationFrame(() => {
    const ta = heroInputRef.value?.querySelector('textarea') as HTMLTextAreaElement | null
    ta?.focus()
  })
}

// ----- anime.js orchestration -----
function splitToSpans(el: HTMLElement, text: string) {
  el.innerHTML = ''
  for (const ch of text) {
    const s = document.createElement('span')
    s.className = 'char'
    s.textContent = ch === ' ' ? ' ' : ch
    el.appendChild(s)
  }
}

function buttonRipple() {
  const btn = document.querySelector('.hero-submit') as HTMLElement | null
  if (!btn) return
  anime({
    targets: btn,
    scale: [{ value: .94, duration: 100 }, { value: 1, duration: 240, easing: 'easeOutElastic(1, .6)' }],
  })
}

function focusHeroInput() {
  const ta = heroInputRef.value?.querySelector('textarea') as HTMLTextAreaElement | null
  ta?.focus()
}

function animateCountUp() {
  document.querySelectorAll<HTMLElement>('.kpi-number').forEach((el) => {
    const targetRaw = el.dataset.value ?? '0'
    const precision = Number(el.dataset.precision ?? '0')
    const target = Number(targetRaw)
    const prefix = el.dataset.prefix ?? ''
    const suffix = el.dataset.suffix ?? ''
    const obj = { v: 0 }
    anime({
      targets: obj,
      v: target,
      duration: 1400,
      easing: 'easeOutExpo',
      update: () => {
        el.textContent = `${prefix}${obj.v.toFixed(precision)}${suffix}`
      },
    })
  })
}

function animateBlobs() {
  // Each blob wanders a long, slow, organic loop — different random path and
  // duration per blob so the gradient backdrop never looks static or synced.
  document.querySelectorAll<HTMLElement>('.hero .blob').forEach((el, i) => {
    anime({
      targets: el,
      translateX: [
        { value: anime.random(-70, 70) },
        { value: anime.random(-70, 70) },
        { value: anime.random(-70, 70) },
      ],
      translateY: [
        { value: anime.random(-55, 55) },
        { value: anime.random(-55, 55) },
        { value: anime.random(-55, 55) },
      ],
      scale: [
        { value: 1.18 },
        { value: 0.86 },
        { value: 1.08 },
      ],
      duration: 16000 + i * 4000,
      easing: 'easeInOutSine',
      direction: 'alternate',
      loop: true,
      delay: i * 800,
    })
  })
  // Slow breathing drift on the grid overlay for extra depth.
  anime({
    targets: '.hero .grid-overlay',
    translateX: [0, 18],
    translateY: [0, 12],
    scale: [1, 1.06],
    duration: 22000,
    easing: 'easeInOutSine',
    direction: 'alternate',
    loop: true,
  })
}

function spawnSpark(x: number, y: number) {
  const el = sparkContainer.value
  if (!el) return
  const dot = document.createElement('span')
  dot.className = 'cursor-spark'
  dot.style.left = `${x}px`
  dot.style.top = `${y}px`
  el.appendChild(dot)
  anime({
    targets: dot,
    translateY: -anime.random(20, 60),
    translateX: anime.random(-30, 30),
    opacity: [{ value: 1, duration: 100 }, { value: 0, duration: 700, easing: 'easeOutQuad' }],
    scale: [1, 0.4],
    duration: 800,
    complete: () => dot.remove(),
  })
}

let lastSpark = 0
function onHeroMouseMove(e: MouseEvent) {
  const t = performance.now()
  if (t - lastSpark < 50) return
  lastSpark = t
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  spawnSpark(e.clientX - rect.left, e.clientY - rect.top)
}

function tiltCard(e: MouseEvent, el: HTMLElement) {
  const r = el.getBoundingClientRect()
  const dx = (e.clientX - r.left) / r.width - 0.5
  const dy = (e.clientY - r.top) / r.height - 0.5
  anime({
    targets: el,
    rotateX: -dy * 8,
    rotateY: dx * 8,
    translateZ: 4,
    duration: 280,
    easing: 'easeOutQuad',
  })
}
function resetTilt(el: HTMLElement) {
  anime({ targets: el, rotateX: 0, rotateY: 0, translateZ: 0, duration: 420, easing: 'easeOutQuad' })
}

function statusType(s: string) {
  if (s === 'done') return 'tag-green'
  if (s === 'cancelled' || s === 'failed') return 'tag'
  if (['planning','researching','writing','quality_gate','waiting_review'].includes(s)) return 'tag-blue'
  return 'tag'
}
function relativeTime(iso?: string) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return `${Math.floor(diff / 86_400_000)} 天前`
}

onMounted(async () => {
  await task.refreshTasks()
  try { const an = await miscApi.announcements(5); announcements.value = an.items } catch {}

  // After data + DOM is mounted, kick the entrance choreography
  await nextTick()
  if (heroTitleRef.value)  splitToSpans(heroTitleRef.value, heroTitleRef.value.textContent || '')
  if (heroSubRef.value)    splitToSpans(heroSubRef.value, heroSubRef.value.textContent || '')

  const timeline = anime.timeline({ easing: 'easeOutCubic' })
  timeline
    .add({
      targets: '.hero-title .char',
      translateY: [40, 0],
      opacity: [0, 1],
      delay: anime.stagger(28),
      duration: 700,
    }, 100)
    .add({
      targets: '.hero-sub .char',
      translateY: [16, 0],
      opacity: [0, 1],
      delay: anime.stagger(10),
      duration: 520,
    }, '-=400')
    .add({
      targets: '.hero-input-wrap',
      translateY: [30, 0],
      opacity: [0, 1],
      duration: 600,
    }, '-=350')
    .add({
      targets: suggestionRefs.value,
      translateY: [24, 0],
      opacity: [0, 1],
      scale: [.96, 1],
      delay: anime.stagger(70),
      duration: 580,
    }, '-=400')
    .add({
      targets: '.kpi-card',
      translateY: [20, 0],
      opacity: [0, 1],
      delay: anime.stagger(80),
      duration: 600,
      complete: () => animateCountUp(),
    }, '-=380')
    .add({
      targets: featureRefs.value,
      translateY: [24, 0],
      opacity: [0, 1],
      delay: anime.stagger(90),
      duration: 620,
    }, '-=300')
    .add({
      targets: recentRefs.value,
      translateX: [-12, 0],
      opacity: [0, 1],
      delay: anime.stagger(60),
      duration: 480,
    }, '-=200')

  animateBlobs()
})

onUnmounted(() => {
  anime.remove('.hero-title .char')
  anime.remove('.hero-sub .char')
  anime.remove('.hero .blob')
  anime.remove('.hero .grid-overlay')
})
</script>

<template>
  <div class="home-anim">
    <!-- HERO -->
    <section class="hero" @mousemove="onHeroMouseMove">
      <div class="hero-bg" aria-hidden="true">
        <div class="blob b1" />
        <div class="blob b2" />
        <div class="blob b3" />
        <div class="grid-overlay" />
      </div>
      <div ref="sparkContainer" class="spark-layer" aria-hidden="true" />

      <div class="hero-inner">
        <div class="hero-eyebrow">
          <span class="dot" /> POWERED BY GEMMA · DUCKDUCKGO · LANGGRAPH
        </div>
        <h1 ref="heroTitleRef" class="hero-title">Athena · 一句话开题, 让 Agent 跑完调研</h1>
        <p ref="heroSubRef" class="hero-sub">Planner 拆题 · Researcher 并发 · Quality Gate · Writer 出引用</p>

        <div ref="heroInputRef" class="hero-input-wrap" :class="{ focused: inputFocused }">
          <ElInput
            v-model="question"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 8 }"
            :placeholder="placeholderText"
            resize="none"
            class="hero-input"
            @focus="inputFocused = true"
            @blur="inputFocused = false"
            @keydown.meta.enter.prevent="submit"
            @keydown.ctrl.enter.prevent="submit"
          />
          <div class="hero-input-bar">
            <span class="hint"><kbd>⌘</kbd><kbd>↵</kbd> 发送</span>
            <button
              class="hero-submit"
              :disabled="!canSubmit"
              :class="{ disabled: !canSubmit }"
              @click="submit"
            >
              <span>{{ task.loading ? '启动中…' : '开始研究' }}</span>
              <ElIcon><ArrowRight /></ElIcon>
            </button>
          </div>
        </div>

        <div class="hero-suggestions">
          <button
            v-for="(s, i) in suggestions" :key="s.title"
            :ref="el => suggestionRefs[i] = (el as HTMLElement)"
            class="suggest-card"
            :style="{ '--accent': s.color } as any"
            @click="pickSuggestion(s, i)"
            @mousemove="e => tiltCard(e, suggestionRefs[i])"
            @mouseleave="resetTilt(suggestionRefs[i])"
          >
            <span class="suggest-ico"><ElIcon><component :is="s.icon" /></ElIcon></span>
            <div>
              <strong>{{ s.title }}</strong>
              <span>{{ s.desc }}</span>
            </div>
            <ElIcon class="suggest-arrow"><ArrowRight /></ElIcon>
          </button>
        </div>
      </div>
    </section>

    <!-- KPI ROW -->
    <section class="kpi-row">
      <article
        v-for="(k, i) in kpiValues" :key="k.label"
        :ref="el => kpiRefs[i] = (el as HTMLElement)"
        class="kpi-card"
      >
        <span class="kpi-label">{{ k.label }}</span>
        <span
          class="kpi-number"
          :data-value="k.value"
          :data-precision="k.precision ?? 0"
          :data-prefix="k.prefix ?? ''"
          :data-suffix="k.suffix ?? ''"
        >{{ k.prefix ?? '' }}0{{ k.suffix ?? '' }}</span>
        <span class="kpi-spark">
          <i v-for="n in 8" :key="n" :style="{ animationDelay: `${n * 80}ms`, height: `${20 + ((n * 53) % 70)}%` }" />
        </span>
      </article>
    </section>

    <!-- FEATURES -->
    <section class="features">
      <h3 class="section-title">为什么是 Athena</h3>
      <div class="feature-grid">
        <article
          v-for="(f, i) in features" :key="f.title"
          :ref="el => featureRefs[i] = (el as HTMLElement)"
          class="feature-card"
          :style="{ '--accent': f.accent } as any"
          @mousemove="e => tiltCard(e, featureRefs[i])"
          @mouseleave="resetTilt(featureRefs[i])"
        >
          <div class="feature-emoji">{{ f.icon }}</div>
          <strong>{{ f.title }}</strong>
          <p>{{ f.desc }}</p>
          <span class="feature-glow" />
        </article>
      </div>
    </section>

    <!-- RECENT -->
    <section v-if="recent.length" class="recent-section">
      <header class="recent-head">
        <h3 class="section-title">最近任务</h3>
        <button class="ghost-link" @click="router.push('/history')">查看全部 →</button>
      </header>
      <div class="recent-list">
        <button
          v-for="(r, i) in recent" :key="r.id"
          :ref="el => recentRefs[i] = (el as HTMLElement)"
          class="recent-row"
          @click="router.push(`/workbench/${r.id}`)"
        >
          <span class="recent-title">{{ r.question }}</span>
          <span class="tag" :class="statusType(r.status)">{{ r.status }}</span>
          <code class="mono">${{ (r.cost_usd || 0).toFixed(4) }}</code>
          <span class="rel">{{ relativeTime(r.updated_at) }}</span>
          <ElIcon class="recent-arrow"><Right /></ElIcon>
        </button>
      </div>
    </section>

    <!-- Empty state when no tasks at all -->
    <section v-else class="empty-state">
      <ElIcon :size="44" color="var(--primary)"><Promotion /></ElIcon>
      <h3>还没有任何研究任务</h3>
      <p>在上面输入一个研究问题, 或选择一个建议卡片开始第一次调研</p>
    </section>
  </div>
</template>

<style scoped>
.home-anim { min-height: 100%; }

/* ---------------- Hero ---------------- */
.hero {
  position: relative;
  padding: 80px 24px 60px;
  border-radius: 24px;
  overflow: hidden;
  isolation: isolate;
  background:
    linear-gradient(180deg, rgba(99,102,241,0.04), transparent 60%),
    var(--surface);
  border: 1px solid var(--border);
  margin-bottom: 24px;
}
.hero-bg {
  position: absolute; inset: 0; z-index: -1;
}
.blob {
  position: absolute;
  width: 460px; height: 460px;
  border-radius: 50%;
  filter: blur(80px);
  opacity: .55;
  will-change: transform;
}
.b1 { background: radial-gradient(circle, #6366f1, transparent 70%); top: -120px; left: -100px; }
.b2 { background: radial-gradient(circle, #10b981, transparent 70%); bottom: -160px; right: -120px; opacity: .35; }
.b3 { background: radial-gradient(circle, #ec4899, transparent 70%); top: 30%; right: 20%; opacity: .25; }
.grid-overlay {
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(99,102,241,.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(99,102,241,.04) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: radial-gradient(ellipse at center, black, transparent 75%);
}

.spark-layer { position: absolute; inset: 0; pointer-events: none; z-index: 1; }
.cursor-spark {
  position: absolute; width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--primary);
  box-shadow: 0 0 12px var(--primary);
  pointer-events: none;
  transform: translate(-50%, -50%);
}

.hero-inner {
  position: relative; z-index: 2;
  max-width: 820px;
  margin: 0 auto;
  text-align: center;
  display: grid;
  gap: 22px;
}
.hero-eyebrow {
  display: inline-flex; align-items: center; gap: 8px;
  justify-self: center;
  padding: 6px 14px;
  border-radius: 999px;
  background: var(--primary-soft);
  color: var(--primary);
  font-family: var(--t-mono);
  font-size: 11px;
  letter-spacing: .14em;
  font-weight: 600;
}
.hero-eyebrow .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--primary);
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: .9; }
  50% { transform: scale(1.6); opacity: .4; }
}

.hero-title {
  font-size: clamp(28px, 4.4vw, 46px);
  font-weight: 800;
  letter-spacing: -.025em;
  line-height: 1.15;
  color: var(--text);
  margin: 0;
  background: linear-gradient(135deg, #1f2937, var(--primary) 60%, #ec4899);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.hero-title .char, .hero-sub .char {
  display: inline-block;
  opacity: 0;
  will-change: transform, opacity;
}
.hero-sub {
  font-size: clamp(14px, 1.6vw, 16px);
  color: var(--muted);
  margin: 0;
  line-height: 1.6;
}

.hero-input-wrap {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15,23,42,.06);
  overflow: hidden;
  transition: box-shadow .25s ease, border-color .25s ease, transform .25s ease;
  text-align: left;
  opacity: 0;
}
.hero-input-wrap.focused {
  border-color: var(--primary);
  box-shadow: 0 0 0 4px var(--primary-soft), 0 16px 36px rgba(99,102,241,.16);
  transform: translateY(-2px);
}
.hero-input :deep(.el-textarea__inner) {
  border: none !important;
  background: transparent !important;
  box-shadow: none !important;
  padding: 18px 20px 8px !important;
  font-size: 15px; line-height: 1.6;
}
.hero-input-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px 12px 18px;
  border-top: 1px solid var(--border);
  background: var(--surface);
}
.hint { font-size: 12px; color: var(--muted); display: inline-flex; align-items: center; gap: 6px; }
.hint kbd {
  font-family: var(--t-mono);
  font-size: 11px;
  padding: 2px 6px;
  border: 1px solid var(--border-strong);
  border-bottom-width: 2px;
  border-radius: 5px;
  background: var(--surface-2);
  color: var(--muted);
}

.hero-submit {
  display: inline-flex; align-items: center; gap: 8px;
  border: none;
  background: linear-gradient(135deg, var(--primary), #7c3aed);
  color: white;
  padding: 9px 18px;
  border-radius: 10px;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 8px 16px rgba(99,102,241,.32);
  transition: filter .2s ease, transform .2s ease;
  position: relative;
}
.hero-submit:not(.disabled):hover { filter: brightness(1.07); transform: translateY(-1px); }
.hero-submit.disabled { opacity: .5; cursor: not-allowed; box-shadow: none; background: var(--muted-soft); }

.hero-suggestions {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.suggest-card {
  position: relative;
  display: flex; align-items: center; gap: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 12px 14px;
  border-radius: 12px;
  text-align: left;
  cursor: pointer;
  font: inherit;
  transform-style: preserve-3d;
  perspective: 600px;
  transition: border-color .2s ease;
  opacity: 0;
}
.suggest-card:hover { border-color: var(--accent, var(--primary)); }
.suggest-card > div { display: grid; flex: 1; }
.suggest-card strong { font-size: 13px; color: var(--text); font-weight: 600; }
.suggest-card span { font-size: 12px; color: var(--muted); margin-top: 2px; }
.suggest-ico {
  display: inline-grid; place-items: center;
  width: 32px; height: 32px;
  border-radius: 9px;
  background: color-mix(in oklab, var(--accent, var(--primary)) 14%, transparent);
  color: var(--accent, var(--primary));
}
.suggest-arrow { color: var(--muted); font-size: 14px; opacity: 0; transition: opacity .2s, transform .2s; }
.suggest-card:hover .suggest-arrow { opacity: 1; transform: translateX(2px); color: var(--accent); }

/* ---------------- KPI ---------------- */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 28px;
}
.kpi-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px 18px;
  overflow: hidden;
  display: grid; gap: 4px;
  opacity: 0;
}
.kpi-card::after {
  content: '';
  position: absolute; left: 0; right: 0; top: 0; height: 3px;
  background: linear-gradient(90deg, var(--primary), #ec4899);
  transform: scaleX(0); transform-origin: left;
  transition: transform .35s ease;
}
.kpi-card:hover::after { transform: scaleX(1); }
.kpi-label { font-size: 12px; color: var(--muted); }
.kpi-number {
  font-family: var(--t-mono);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -.02em;
  color: var(--text);
  line-height: 1.1;
}
.kpi-spark {
  display: flex; align-items: flex-end; gap: 3px;
  height: 24px; margin-top: 6px;
}
.kpi-spark i {
  flex: 1;
  background: var(--primary-soft);
  border-radius: 2px;
  animation: bar-pulse 2s ease-in-out infinite;
}
@keyframes bar-pulse {
  0%, 100% { transform: scaleY(.6); background: var(--primary-soft); }
  50% { transform: scaleY(1.1); background: var(--primary); }
}

/* ---------------- Features ---------------- */
.features { margin-bottom: 36px; }
.section-title {
  font-size: 14px; font-weight: 600; color: var(--text);
  margin: 0 0 16px;
}
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
}
.feature-card {
  position: relative;
  padding: 22px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  transform-style: preserve-3d;
  perspective: 800px;
  cursor: default;
  overflow: hidden;
  opacity: 0;
}
.feature-card .feature-emoji {
  font-size: 28px;
  width: 48px; height: 48px;
  display: grid; place-items: center;
  border-radius: 12px;
  background: color-mix(in oklab, var(--accent) 14%, transparent);
  margin-bottom: 12px;
}
.feature-card strong { display: block; font-size: 15px; font-weight: 700; color: var(--text); }
.feature-card p { margin: 6px 0 0; font-size: 12.5px; color: var(--muted); line-height: 1.55; }
.feature-card .feature-glow {
  position: absolute; right: -40px; bottom: -40px;
  width: 140px; height: 140px;
  background: radial-gradient(circle, var(--accent), transparent 70%);
  filter: blur(30px);
  opacity: 0;
  transition: opacity .35s ease;
}
.feature-card:hover .feature-glow { opacity: .35; }

/* ---------------- Recent ---------------- */
.recent-section { display: grid; gap: 12px; }
.recent-head { display: flex; justify-content: space-between; align-items: center; }
.ghost-link {
  background: none; border: none;
  color: var(--primary); font: inherit; font-size: 13px;
  cursor: pointer; padding: 4px 8px;
  border-radius: 6px;
}
.ghost-link:hover { background: var(--primary-soft); }
.recent-list { display: grid; gap: 8px; }
.recent-row {
  display: grid;
  grid-template-columns: 1fr 90px 90px 90px 18px;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  font: inherit;
  text-align: left;
  cursor: pointer;
  opacity: 0;
  transition: border-color .2s, transform .2s, box-shadow .2s;
}
.recent-row:hover {
  border-color: var(--primary);
  transform: translateY(-1px);
  box-shadow: 0 6px 14px rgba(15,23,42,.05);
}
.recent-title {
  font-size: 13px; color: var(--text); font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.recent-arrow { color: var(--muted-soft); }
.mono { font-family: var(--t-mono); font-size: 12px; color: var(--muted); }
.rel { font-size: 12px; color: var(--muted); }

.empty-state {
  display: grid; place-items: center; gap: 8px;
  padding: 60px 20px;
  text-align: center;
  background: var(--surface);
  border: 1px dashed var(--border-strong);
  border-radius: 14px;
}
.empty-state h3 { margin: 0; font-size: 16px; font-weight: 600; }
.empty-state p { margin: 0; font-size: 13px; color: var(--muted); }

@media (max-width: 700px) {
  .hero { padding: 50px 16px 36px; }
  .recent-row { grid-template-columns: 1fr 80px; gap: 8px; }
  .recent-row code, .recent-row .rel, .recent-row .recent-arrow { display: none; }
}
</style>
