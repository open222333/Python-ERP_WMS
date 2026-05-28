import client from './client'

export const analyticsApi = {
  getSummary:   (period) => client.get('/analytics/summary', { params: { period } }),
  getDashboard: ()       => client.get('/analytics/dashboard'),
}
