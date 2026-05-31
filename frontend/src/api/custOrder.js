import client from './client'

export const custOrderApi = {
  // Admin 訂單管理
  getOrders:    (params) => client.get('/customer-order/', { params }),
  getOrder:     (id)     => client.get(`/customer-order/${id}`),
  updateStatus: (id, s)  => client.patch(`/customer-order/${id}/status`, { status: s }),
  deleteOrder:  (id)     => client.delete(`/customer-order/${id}`),

  // Kitchen 廚房顯示
  getActive:    ()       => client.get('/customer-order/active'),
  getStats:     ()       => client.get('/customer-order/stats'),

  // 顧客點餐
  getMenu:           ()          => client.get('/customer-order/menu'),
  createOrder:       (data)      => client.post('/customer-order/', data),
  getSession:        (token)     => client.get('/customer-order/session', { params: { token } }),
  closeTableSession: (tableNo)   => client.delete(`/customer-order/session/${tableNo}`),
}
