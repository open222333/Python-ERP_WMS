<script setup lang="ts">
// [U10] 2026-11 拆分：四個分頁（含各自彈窗與 CRUD）移至 components/users/，本頁只負責載入共用資料與切換分頁
import { ref, onMounted } from 'vue'
import http from '@/api'
import { storeApi } from '@/api/store'
import { useToastStore } from '@/stores/toast'
import type { User, UserTemplate, Store, StoreRole } from '@/types'
import UsersTab from '@/components/users/UsersTab.vue'
import TemplatesTab from '@/components/users/TemplatesTab.vue'
import StoresTab from '@/components/users/StoresTab.vue'
import StoreRolesTab from '@/components/users/StoreRolesTab.vue'

const toast = useToastStore()

// ── State ────────────────────────────────────────────────
const activeTab = ref<'users' | 'templates' | 'stores' | 'store-roles'>('users')
const loading   = ref(false)

// 四個分頁互相引用（使用者表單選模板與店家、店家表單選角色），由本頁統一載入後以 props 傳入
const users      = ref<User[]>([])
const templates  = ref<UserTemplate[]>([])
const stores     = ref<Store[]>([])
const storeRoles = ref<StoreRole[]>([])

// ── Load ─────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const [uRes, tRes, sRes, srRes] = await Promise.all([
      http.get('/user/'),
      http.get('/user/templates/'),
      storeApi.getAll(),
      storeApi.roleGetAll(),
    ])
    users.value      = uRes.data?.data  || []
    templates.value  = tRes.data?.data  || []
    stores.value     = sRes.data?.data  || []
    storeRoles.value = srRes.data?.data || []
  } catch {
    toast.show('載入失敗', 'danger')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <!-- ── Tabs ─────────────────────────────────────────── -->
  <ul class="nav nav-tabs mb-3">
    <li class="nav-item">
      <a class="nav-link" :class="{ active: activeTab === 'users' }"
         href="#" @click.prevent="activeTab = 'users'">
        <i class="bi bi-people me-1"></i>使用者
      </a>
    </li>
    <li class="nav-item">
      <a class="nav-link" :class="{ active: activeTab === 'templates' }"
         href="#" @click.prevent="activeTab = 'templates'">
        <i class="bi bi-person-badge me-1"></i>使用者模板
      </a>
    </li>
    <li class="nav-item">
      <a class="nav-link" :class="{ active: activeTab === 'stores' }"
         href="#" @click.prevent="activeTab = 'stores'">
        <i class="bi bi-shop me-1"></i>店家
      </a>
    </li>
    <li class="nav-item">
      <a class="nav-link" :class="{ active: activeTab === 'store-roles' }"
         href="#" @click.prevent="activeTab = 'store-roles'">
        <i class="bi bi-tags me-1"></i>店家角色模板
      </a>
    </li>
  </ul>

  <UsersTab v-if="activeTab === 'users'"
            :users="users" :templates="templates" :stores="stores" :loading="loading" @reload="load" />
  <TemplatesTab v-else-if="activeTab === 'templates'"
                :templates="templates" :users="users" @reload="load" />
  <StoresTab v-else-if="activeTab === 'stores'"
             :stores="stores" :store-roles="storeRoles" :loading="loading" @reload="load" />
  <StoreRolesTab v-else-if="activeTab === 'store-roles'"
                 :store-roles="storeRoles" :loading="loading" @reload="load" />
</template>
