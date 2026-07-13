// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data, Id, Params } from './types'

export const posApi = {
  // 銷售
  getSales:      (params?: Params) => client.get('/pos/sales', { params }),
  createSale:    (data: Data)      => client.post('/pos/sales', data),
  refundSale:    (id: Id)          => client.post(`/pos/sales/${id}/refund`),
  getDailyReport:(params?: Params) => client.get('/pos/report/daily', { params }),

  // 設定
  getDiscounts:   ()          => client.get('/pos/discounts'),
  createDiscount: (data: Data) => client.post('/pos/discounts', data),
  deleteDiscount: (id: Id)     => client.delete(`/pos/discounts/${id}`),
  getPayMethods:  ()           => client.get('/pos/pay-methods'),
  createPayMethod:(data: Data) => client.post('/pos/pay-methods', data),
  deletePayMethod:(id: Id)     => client.delete(`/pos/pay-methods/${id}`),
}
