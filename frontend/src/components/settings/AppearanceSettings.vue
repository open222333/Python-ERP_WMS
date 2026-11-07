<!-- [U10] 自 views/admin/SettingsView.vue 拆出 -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import http from '@/api'
import { useToastStore } from '@/stores/toast'
import { useThemeStore, THEMES } from '@/stores/theme'

/** SettingsView 載入的 /settings/ 內容；有伺服器端儲存的外觀設定時套用（換裝置登入也能保持一致） */
const props = defineProps<{ settings: Record<string, any> | null }>()

const toast      = useToastStore()
const themeStore = useThemeStore()

const adminTheme  = ref(themeStore.themeId)
const savingTheme = ref(false)
const customEdit  = ref({ ...themeStore.customColors.value })

watch(() => props.settings, s => {
  if (!s) return
  if (s.admin_theme) {
    adminTheme.value = s.admin_theme
    themeStore.applyTheme(s.admin_theme)
  }
  if (s.admin_dark !== undefined) {
    themeStore.applyDarkMode(s.admin_dark === '1')
  }
  if (s.admin_custom_theme) {
    try {
      const colors = JSON.parse(s.admin_custom_theme)
      themeStore.setCustomColors(colors)
      customEdit.value = { ...colors }
    } catch {}
  }
}, { immediate: true })

function selectTheme(id: string) {
  adminTheme.value = id
  themeStore.applyTheme(id)
}

function onCustomColorChange() {
  themeStore.setCustomColors(customEdit.value)
  adminTheme.value = 'custom'
}

function setDark(v: boolean) {
  themeStore.applyDarkMode(v)
}

async function saveTheme() {
  savingTheme.value = true
  try {
    const payload: Record<string, string> = {
      admin_theme: adminTheme.value,
      admin_dark:  themeStore.darkMode ? '1' : '0',
    }
    if (adminTheme.value === 'custom') {
      payload.admin_custom_theme = JSON.stringify(themeStore.customColors.value)
    }
    await http.put('/settings/', payload)
    toast.show('外觀設定已儲存', 'success')
  } catch (e: any) {
    toast.show(e?.response?.data?.message || '儲存失敗', 'danger')
  } finally {
    savingTheme.value = false
  }
}
</script>

<template>
  <!-- ── 後台外觀配色 ──────────────────────────────── -->
  <div class="col-12">
    <div class="table-card">
      <div class="table-header">
        <h6><i class="bi bi-palette me-1 text-primary"></i>後台外觀配色</h6>
      </div>
      <div class="p-4">

        <!-- 深淺色模式 -->
        <div class="mb-4">
          <div class="fw-semibold small mb-2">色調模式</div>
          <div class="d-flex gap-2">
            <button
              class="btn btn-sm d-flex align-items-center gap-1"
              :class="!themeStore.darkMode ? 'btn-primary' : 'btn-outline-secondary'"
              @click="setDark(false)"
            >
              <i class="bi bi-sun-fill"></i>淺色
            </button>
            <button
              class="btn btn-sm d-flex align-items-center gap-1"
              :class="themeStore.darkMode ? 'btn-primary' : 'btn-outline-secondary'"
              @click="setDark(true)"
            >
              <i class="bi bi-moon-stars-fill"></i>深色
            </button>
          </div>
        </div>

        <!-- 側欄主題 -->
        <div class="fw-semibold small mb-2">側欄主題</div>
        <p class="text-muted small mb-3">點擊即時預覽，儲存後下次開啟自動套用。</p>
        <div class="theme-grid mb-3">
          <!-- 預設主題 -->
          <div
            v-for="t in THEMES" :key="t.id"
            class="theme-card"
            :class="{ active: adminTheme === t.id }"
            @click="selectTheme(t.id)"
          >
            <div class="theme-preview" :style="{ background: t.sidebarBg }">
              <div class="tp-row">
                <div class="tp-dot" :style="{ background: t.accent }"></div>
                <div class="tp-line" :style="{ background: t.accent, opacity: .9 }"></div>
              </div>
              <div class="tp-row opacity-30">
                <div class="tp-dot"></div>
                <div class="tp-line"></div>
              </div>
              <div class="tp-row opacity-20">
                <div class="tp-dot"></div>
                <div class="tp-line"></div>
              </div>
              <div class="tp-accent-bar" :style="{ background: t.accent }"></div>
              <div v-if="adminTheme === t.id" class="tp-check">
                <i class="bi bi-check-lg"></i>
              </div>
            </div>
            <div class="theme-label">{{ t.name }}</div>
          </div>

          <!-- 自訂主題 -->
          <div
            class="theme-card"
            :class="{ active: adminTheme === 'custom' }"
            @click="selectTheme('custom')"
          >
            <div class="theme-preview" :style="{ background: customEdit.sidebarBg }">
              <div class="tp-row">
                <div class="tp-dot" :style="{ background: customEdit.accent }"></div>
                <div class="tp-line" :style="{ background: customEdit.accent, opacity: .9 }"></div>
              </div>
              <div class="tp-row opacity-30">
                <div class="tp-dot"></div>
                <div class="tp-line"></div>
              </div>
              <div class="tp-row opacity-20">
                <div class="tp-dot"></div>
                <div class="tp-line"></div>
              </div>
              <div class="tp-accent-bar" :style="{ background: customEdit.accent }"></div>
              <div v-if="adminTheme === 'custom'" class="tp-check">
                <i class="bi bi-check-lg"></i>
              </div>
              <div v-else class="tp-edit-icon"><i class="bi bi-pencil-fill"></i></div>
            </div>
            <div class="theme-label">自訂</div>
          </div>
        </div>

        <!-- 自訂主題顏色選擇器 -->
        <div v-if="adminTheme === 'custom'" class="custom-color-editor mb-4">
          <div class="fw-semibold small mb-2">自訂側欄顏色</div>
          <div class="d-flex flex-wrap gap-3">
            <div class="color-pick-item">
              <label class="form-label form-label-sm mb-1">側欄底色</label>
              <div class="d-flex align-items-center gap-2">
                <input
                  v-model="customEdit.sidebarBg"
                  type="color"
                  class="form-control form-control-color"
                  @input="onCustomColorChange"
                />
                <input
                  v-model="customEdit.sidebarBg"
                  type="text"
                  class="form-control form-control-sm color-hex"
                  maxlength="7"
                  placeholder="#1a1d2e"
                  @change="onCustomColorChange"
                />
              </div>
            </div>
            <div class="color-pick-item">
              <label class="form-label form-label-sm mb-1">側欄 Hover</label>
              <div class="d-flex align-items-center gap-2">
                <input
                  v-model="customEdit.sidebarHover"
                  type="color"
                  class="form-control form-control-color"
                  @input="onCustomColorChange"
                />
                <input
                  v-model="customEdit.sidebarHover"
                  type="text"
                  class="form-control form-control-sm color-hex"
                  maxlength="7"
                  placeholder="#2d3250"
                  @change="onCustomColorChange"
                />
              </div>
            </div>
            <div class="color-pick-item">
              <label class="form-label form-label-sm mb-1">強調色</label>
              <div class="d-flex align-items-center gap-2">
                <input
                  v-model="customEdit.accent"
                  type="color"
                  class="form-control form-control-color"
                  @input="onCustomColorChange"
                />
                <input
                  v-model="customEdit.accent"
                  type="text"
                  class="form-control form-control-sm color-hex"
                  maxlength="7"
                  placeholder="#5c7cfa"
                  @change="onCustomColorChange"
                />
              </div>
            </div>
          </div>
        </div>

        <button class="btn btn-primary" :disabled="savingTheme" @click="saveTheme">
          <span v-if="savingTheme" class="spinner-border spinner-border-sm me-1"></span>
          <i v-else class="bi bi-palette me-1"></i>儲存外觀設定
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── 主題選擇器 ── */
.theme-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
@media (max-width: 768px) { .theme-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 480px) { .theme-grid { grid-template-columns: repeat(2, 1fr); } }

.theme-card {
  cursor: pointer;
  border-radius: 10px;
  border: 2.5px solid #e2e8f0;
  overflow: hidden;
  transition: border-color .15s, transform .12s, box-shadow .15s;
  box-shadow: 0 1px 4px rgba(0,0,0,.07);
  user-select: none;
}
.theme-card:hover  { border-color: #94a3b8; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,.12); }
.theme-card.active { border-color: #22c55e; box-shadow: 0 0 0 3px rgba(34,197,94,.2); }

.theme-preview {
  height: 72px;
  padding: 10px 12px 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
}
.tp-row  { display: flex; align-items: center; gap: 5px; }
.tp-dot  { width: 7px; height: 7px; border-radius: 50%; background: rgba(255,255,255,.25); flex-shrink: 0; }
.tp-line { height: 5px; flex: 1; border-radius: 3px; background: rgba(255,255,255,.25); }

.tp-accent-bar {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 8px;
}
.tp-check {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -55%);
  width: 26px; height: 26px;
  background: rgba(255,255,255,.92);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #16a34a; font-size: .95rem; font-weight: 800;
}

.theme-label {
  padding: 7px 8px;
  font-size: .77rem;
  font-weight: 600;
  text-align: center;
  background: var(--card-bg, #fff);
  color: var(--text-main, #374151);
}

.tp-edit-icon {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -55%);
  width: 26px; height: 26px;
  background: rgba(255,255,255,.2);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: .8rem;
}

/* Custom color editor */
.custom-color-editor {
  background: var(--table-th-bg, #f8f9fa);
  border: 1px solid var(--card-border, #e2e8f0);
  border-radius: 10px;
  padding: 16px;
}
.color-pick-item { min-width: 180px; }
.color-hex { width: 90px; font-family: monospace; font-size: .8rem; }
.form-control-color { width: 40px; height: 34px; padding: 2px; cursor: pointer; }
</style>
