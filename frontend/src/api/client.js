// ── 相容性 re-export ──────────────────────────────────────
// 舊有 .js api 模組（warehouse.js, product.js, …）均 import from './client'
// 統一轉接至 TypeScript 主實例（帶 JWT 攔截 + refresh 邏輯），
// 避免 wms_token / token 不一致導致 401。
export { default } from './index'
