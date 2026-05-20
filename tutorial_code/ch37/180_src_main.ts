import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/main.css'

const app = createApp(App)

// 1. Pinia · 状态管理
const pinia = createPinia()
app.use(pinia)

// 2. Router · 路由
app.use(router)

// 3. Naive UI:不用全局注册,按需 import,bundle 更小
//    具体组件在用到的 SFC 里 import { NButton, NInput } from 'naive-ui'

app.mount('#app')