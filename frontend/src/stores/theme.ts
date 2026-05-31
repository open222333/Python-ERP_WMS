import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Theme {
  id:          string
  name:        string
  sidebarBg:   string
  sidebarHover: string
  accent:      string
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

export const useThemeStore = defineStore('theme', () => {
  const themeId = ref(localStorage.getItem('admin_theme') || 'midnight')

  function applyTheme(id: string) {
    const t = THEMES.find(t => t.id === id) ?? THEMES[0]
    const root = document.documentElement
    root.style.setProperty('--sidebar-bg',    t.sidebarBg)
    root.style.setProperty('--sidebar-hover', t.sidebarHover)
    root.style.setProperty('--accent',        t.accent)
    themeId.value = id
    localStorage.setItem('admin_theme', id)
  }

  return { themeId, applyTheme }
})
