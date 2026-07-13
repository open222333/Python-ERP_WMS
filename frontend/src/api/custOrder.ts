// [OPT-N4] .js → .ts 遷移（原內容不變，僅補型別）
import client from './client'
import type { Data, Id, Params } from './types'

export const custOrderApi = {
  // Admin 訂單管理
  getOrders:    (params?: Params) => client.get('/customer-order/', { params }),
  getOrder:     (id: Id)          => client.get(`/customer-order/${id}`),
  updateStatus: (id: Id, s: string) => client.patch(`/customer-order/${id}/status`, { status: s }),
  deleteOrder:  (id: Id)          => client.delete(`/customer-order/${id}`),

  // Kitchen 廚房顯示
  getActive:    ()                => client.get('/customer-order/active'),
  getStats:     ()                => client.get('/customer-order/stats'),
  // [REFACTOR] SSE 一次性 ticket：連 /customer-order/stream 前先取得，避免 JWT 進 query string
  getStreamTicket: ()             => client.post('/customer-order/stream-ticket'),

  // 顧客點餐
  getMenu:           ()               => client.get('/customer-order/menu'),
  createOrder:       (data: Data)     => client.post('/customer-order/', data),
  getSession:        (token: string)  => client.get('/customer-order/session', { params: { token } }),
  closeTableSession: (tableNo: Id)    => client.delete(`/customer-order/session/${tableNo}`),
}
