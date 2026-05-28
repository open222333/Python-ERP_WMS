import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router'
import App from '@/App.vue'

// Bootstrap CSS + Icons
import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap-icons/font/bootstrap-icons.min.css'
// Bootstrap JS (for dropdowns, modals via data-bs-*)
import 'bootstrap/dist/js/bootstrap.bundle.min.js'
// WMS 全域樣式（CSS variables, .table-card, .stat-card, order badges…）
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
