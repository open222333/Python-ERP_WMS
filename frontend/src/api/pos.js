import client from './client'

export const posApi = {
  // 銷售
  getSales:      (params) => client.get('/pos/sales', { params }),
  createSale:    (data)   => client.post('/pos/sales', data),
  refundSale:    (id)     => client.post(`/pos/sales/${id}/refund`),
  getDailyReport:(params) => client.get('/pos/report/daily', { params }),

  // 設定
  getDiscounts:   ()      => client.get('/pos/discounts'),
  createDiscount: (data)  => client.post('/pos/discounts', data),
  deleteDiscount: (id)    => client.delete(`/pos/discounts/${id}`),
  getPayMethods:  ()      => client.get('/pos/pay-methods'),
  createPayMethod:(data)  => client.post('/pos/pay-methods', data),
  deletePayMethod:(id)    => client.delete(`/pos/pay-methods/${id}`),
}
