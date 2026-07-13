// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
// ── 相容性 re-export ──────────────────────────────────────
// 舊有 api 模組（warehouse.ts, product.ts, …）均 import from './client'
// 統一轉接至 TypeScript 主實例（帶 JWT 攔截 + refresh 邏輯），
// 避免 wms_token / token 不一致導致 401。
import type { AxiosInstance } from 'axios'
import http from './index'

const client: AxiosInstance = http
export default client
