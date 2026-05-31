import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Theme {
  id:           string
  name:         string
  sidebarBg:    string
  sidebarHover: string
  accent:       string
}

export const THEMES: Theme[] = [
  { id: 'midnight', name: '午夜藍',  sidebarBg: '#1a1d2e', sidebarHover: '#2d3250', accent: '#5c7cfa' },
  { id: 'forest',   name: '深林綠',  sidebarBg: '#0f1f15', sidebarHover: '#1a3328', accent: '#10b981' },
  { id: 'purple',   name: '暗紫',    sidebarBg: '#1a0d2e', sidebarHover: '#2d1a45', accent: '#8b5cf6' },
  { id: 'slate',    name: '石板灰',  sidebarBg: '#1c2333', sidebarHover: '#2a3448', accent: '#94a3b8' },
  { id: 'crimson',  name: '深紅',    sidebarBg: '#1f0d12', sidebarHover: '#331a24', accent: '#ef4444' },
  { id: 'amber',    name: '琥珀橙',  sidebarBg: '#1a1409', sidebarHover: '#2d2212', accent: '#f59e0b' },
  { id: 'teal',     name: '青藍',    sidebarBg: '#0d1f25', sidebarHover: '#1a333c', accent: '#06b6d4' },
  { id: 'rose',     name: '玫瑰粉',  sidebarBg: '#1f0d1a', sidebarHover: '#33152a', accent: '#f43f5e' },
]

function _parseCustom() {
  try {
    const s = localStorage.getItem('admin_custom_theme')
    return s ? JSON.parse(s) : null
  } catch { return null }
}

export const useThemeStore = defineStore('theme', () => {
  const themeId    = ref(localStorage.getItem('admin_theme') || 'midnight')
  const darkMode   = ref(localStorage.getItem('admin_dark') === '1')
  const customColors = ref<{ sidebarBg: string; sidebarHover: string; accent: string }>(
    _parseCustom() ?? { sidebarBg: '#1a1d2e', sidebarHover: '#2d3250', accent: '#5c7cfa' }
  )

  function applyTheme(id: string) {
    const root = document.documentElement
    let bg: string, hover: string, accent: string
    if (id === 'custom') {
      bg     = customColors.value.sidebarBg
      hover  = customColors.value.sidebarHover
      accent = customColors.value.accent
    } else {
      const t = THEMES.find(t => t.id === id) ?? THEMES[0]
      bg     = t.sidebarBg
      hover  = t.sidebarHover
      accent = t.accent
    }
    root.style.setProperty('--sidebar-bg',    bg)
    root.style.setProperty('--sidebar-hover', hover)
    root.style.setProperty('--accent',        accent)
    themeId.value = id
    localStorage.setItem('admin_theme', id)
  }

  function applyDarkMode(dark: boolean) {
    darkMode.value = dark
    localStorage.setItem('admin_dark', dark ? '1' : '0')
  }

  function setCustomColors(colors: { sidebarBg: string; sidebarHover: string; accent: string }) {
    customColors.value = { ...colors }
    localStorage.setItem('admin_custom_theme', JSON.stringify(colors))
    if (themeId.value === 'custom') applyTheme('custom')
  }

  return { themeId, darkMode, customColors, applyTheme, applyDarkMode, setCustomColors }
})
