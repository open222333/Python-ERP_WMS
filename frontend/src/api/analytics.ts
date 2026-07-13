// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'

export const analyticsApi = {
  getSummary:   (period?: string) => client.get('/analytics/summary', { params: { period } }),
  getDashboard: ()                => client.get('/analytics/dashboard'),
}
