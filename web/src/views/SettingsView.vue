<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Connection, Refresh, Key, View, Hide, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useSessionStore } from '@/stores/session'
import { useTaskStore } from '@/stores/task'
import { getConfig, getHealth } from '@/api/client'
import { useEntrance } from '@/composables/useAnime'

useEntrance('.settings-section', { delay: (_el, i) => 100 + i * 90 })

const session = useSessionStore()
const task = useTaskStore()
const showKey = ref(false)
const testing = ref(false)

onMounted(async () => {
  await Promise.allSettled([session.refreshConfig(), session.refreshHealth()])
})

const formatOptions = [
  { label: 'Markdown', value: 'md' },
  { label: 'HTML', value: 'html' },
  { label: 'PDF', value: 'pdf' },
  { label: 'DOCX', value: 'docx' },
]
const themeOptions = [
  { label: '浅色', value: 'light' },
  { label: '深色', value: 'dark' },
]

const formats = computed(() => session.config?.export_formats || {})

async function testConnection() {
  testing.value = true
  try {
    const [health, cfg] = await Promise.all([getHealth(), getConfig()])
    session.health = health
    session.config = cfg
    ElMessage.success(`OK · 版本 ${health.version} · LLM=${cfg.llm_provider}`)
  } catch (err) {
    ElMessage.error(`无法连接 API: ${(err as Error).message}`)
  } finally {
    testing.value = false
  }
}

function saveAll() {
  session.save()
  ElMessage.success('已保存')
}

async function refreshTasks() {
  await task.refreshTasks()
  ElMessage.info(`已同步 ${task.tasks.length} 条任务`)
}
</script>

<template>
  <div class="settings-page">
    <ElAlert
      v-if="!session.hasApiKey && session.config?.require_auth"
      type="warning" :closable="false" show-icon
      title="尚未配置 API Key"
      description="服务端启用了鉴权(ATHENA_REQUIRE_AUTH=true)。请在下方填入 API Key 并保存。"
      class="alert-bar"
    />
    <ElAlert
      v-if="session.lastConnectionError"
      type="error" :closable="false" show-icon
      title="连接 API 失败"
      :description="session.lastConnectionError"
      class="alert-bar"
    />

    <!-- API connection -->
    <section class="settings-section">
      <header>
        <h3>API 连接</h3>
        <p>客户端 → 后端的 Bearer Token 与基础地址</p>
      </header>
      <div class="form">
        <div class="row">
          <label>API Key</label>
          <ElInput
            v-model="session.apiKey"
            :type="showKey ? 'text' : 'password'"
            placeholder="服务端 ATHENA_API_KEY"
            clearable
          >
            <template #prefix><ElIcon><Key /></ElIcon></template>
            <template #append>
              <ElButton :icon="showKey ? Hide : View" @click="showKey = !showKey" />
            </template>
          </ElInput>
        </div>
        <div class="row">
          <label>API 基础地址</label>
          <ElInput v-model="session.apiBase" placeholder="留空走当前域名" clearable />
        </div>
        <div class="row actions">
          <ElButton type="primary" :icon="Check" @click="saveAll">保存</ElButton>
          <ElButton :loading="testing" :icon="Connection" @click="testConnection">测试连接</ElButton>
          <ElButton :icon="Refresh" @click="refreshTasks">同步任务列表</ElButton>
        </div>
      </div>
    </section>

    <!-- Server config -->
    <section class="settings-section">
      <header>
        <h3>服务端配置</h3>
        <p>只读,由 <code>.env</code> 决定,修改后需重启后端</p>
      </header>
      <div class="kv-grid" v-if="session.config">
        <div class="kv"><span>运行环境</span><b>{{ session.config.env }}</b></div>
        <div class="kv"><span>LLM 提供方</span><b>{{ session.config.llm_provider }}</b></div>
        <div class="kv"><span>默认模型</span><code>{{ session.config.default_model }}</code></div>
        <div class="kv"><span>搜索提供方</span><b>{{ session.config.search_provider }}</b></div>
        <div class="kv"><span>质量阈值</span><b>{{ session.config.quality_threshold }}</b></div>
        <div class="kv"><span>最大迭代轮</span><b>{{ session.config.max_research_iterations }}</b></div>
        <div class="kv"><span>预算上限</span><b>${{ session.config.max_budget_usd }}</b></div>
        <div class="kv"><span>鉴权</span>
          <ElTag size="small" :type="session.config.require_auth ? 'warning' : 'success'">
            {{ session.config.require_auth ? '启用' : '关闭' }}
          </ElTag>
        </div>
        <div class="kv">
          <span>OpenAI Key</span>
          <ElTag size="small" :type="session.config.has_openai_key ? 'success' : 'info'" effect="plain">
            {{ session.config.has_openai_key ? '已配置' : '未配置' }}
          </ElTag>
        </div>
        <div class="kv">
          <span>Anthropic Key</span>
          <ElTag size="small" :type="session.config.has_anthropic_key ? 'success' : 'info'" effect="plain">
            {{ session.config.has_anthropic_key ? '已配置' : '未配置' }}
          </ElTag>
        </div>
        <div class="kv">
          <span>Tavily Key</span>
          <ElTag size="small" :type="session.config.has_tavily_key ? 'success' : 'info'" effect="plain">
            {{ session.config.has_tavily_key ? '已配置' : '未配置' }}
          </ElTag>
        </div>
        <div class="kv">
          <span>支持导出格式</span>
          <div class="chip-row">
            <ElTag v-for="(ok, fmt) in formats" :key="fmt" size="small" :type="ok ? 'success' : 'info'" effect="plain" round>{{ fmt }}</ElTag>
          </div>
        </div>
      </div>
      <ElText v-else type="info">尚未获取到服务端配置,点击「测试连接」。</ElText>
    </section>

    <!-- Preferences -->
    <section class="settings-section">
      <header>
        <h3>个人偏好</h3>
        <p>保存在浏览器 localStorage</p>
      </header>
      <div class="form">
        <div class="row">
          <label>用户 ID</label>
          <ElInput v-model="session.userId" placeholder="任务来源标识" clearable />
        </div>
        <div class="row">
          <label>默认导出格式</label>
          <ElRadioGroup v-model="session.exportFormat">
            <ElRadioButton v-for="o in formatOptions" :key="o.value" :value="o.value">{{ o.label }}</ElRadioButton>
          </ElRadioGroup>
        </div>
        <div class="row">
          <label>预算上限 (USD)</label>
          <ElInputNumber v-model="session.budgetUsd" :min="0" :step="0.5" :precision="2" />
        </div>
        <div class="row">
          <label>界面主题</label>
          <ElRadioGroup v-model="session.theme">
            <ElRadioButton v-for="o in themeOptions" :key="o.value" :value="o.value">{{ o.label }}</ElRadioButton>
          </ElRadioGroup>
        </div>
        <div class="row actions">
          <ElButton type="primary" :icon="Check" @click="saveAll">保存偏好</ElButton>
        </div>
      </div>
    </section>

    <!-- Health -->
    <section v-if="session.health" class="settings-section">
      <header>
        <h3>健康状态</h3>
        <p>来自 <code>/health</code>,刷新时间 {{ new Date().toLocaleTimeString() }}</p>
      </header>
      <div class="kv-grid">
        <div class="kv"><span>状态</span><ElTag type="success" size="small" round>OK</ElTag></div>
        <div class="kv"><span>版本</span><b>{{ session.health.version }}</b></div>
        <div class="kv"><span>运行时长</span><b>{{ session.health.uptime_sec.toFixed(1) }}s</b></div>
        <div class="kv"><span>LLM</span><b>{{ session.health.llm_provider }}</b></div>
        <div class="kv"><span>搜索</span><b>{{ session.health.search_provider }}</b></div>
        <div class="kv"><span>SQLite</span><code>{{ session.health.db_path }}</code></div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.settings-page { display: grid; gap: 16px; max-width: 760px; margin: 0 auto; }
.alert-bar { border-radius: var(--r-2) !important; }

.settings-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-3);
  box-shadow: var(--shadow-1);
  overflow: hidden;
}
.settings-section header {
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.settings-section header h3 {
  margin: 0; font-size: var(--t-15); font-weight: 600;
  color: var(--text); letter-spacing: -.005em;
}
.settings-section header p {
  margin: 4px 0 0; font-size: 12px; color: var(--muted);
}
.settings-section header code {
  font-family: var(--t-mono); font-size: 11px;
  padding: 1px 5px; background: var(--surface-2); border-radius: 4px;
  border: 1px solid var(--border);
}

.form { padding: 16px 18px; display: grid; gap: 14px; }
.row { display: grid; grid-template-columns: 140px 1fr; gap: 14px; align-items: center; }
.row label { font-size: 12px; color: var(--muted); font-weight: 500; }
.row.actions { grid-template-columns: 140px 1fr; }
.row.actions :nth-child(2) { display: flex; gap: 8px; flex-wrap: wrap; }

.kv-grid {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  padding: 8px 0;
}
.kv {
  display: flex; justify-content: space-between; align-items: center; gap: 8px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--border);
  font-size: var(--t-13);
}
.kv:nth-last-child(-n+2) { border-bottom: none; }
.kv span { color: var(--muted); }
.kv b { color: var(--text); font-weight: 600; }
.kv code { font-family: var(--t-mono); font-size: 11.5px; color: var(--text); }
.chip-row { display: flex; gap: 4px; flex-wrap: wrap; }

@media (max-width: 700px) {
  .row { grid-template-columns: 1fr; }
  .kv-grid { grid-template-columns: 1fr; }
}
</style>
