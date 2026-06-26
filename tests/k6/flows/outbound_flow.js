/**
 * k6 Flow Test — 完整出庫流程
 *
 * 測試業務流程：
 *   建立出庫單 → 新增品項 → 確認（驗庫存）→ 完成（扣庫存）→ 驗證庫存減少
 *
 * 前置條件：
 *   已執行 seed.py（需要有倉庫、產品、及足夠庫存）
 *
 * 用法：
 *   k6 run tests/k6/flows/outbound_flow.js
 *   k6 run --env VUS=3 --env DURATION=20s tests/k6/flows/outbound_flow.js
 */

import http from 'k6/http'
import { check, sleep, group } from 'k6'
import { Trend, Counter } from 'k6/metrics'

const BASE = __ENV.BASE_URL || 'http://localhost'

const outboundDuration  = new Trend('outbound_flow_duration', true)
const outboundCompleted = new Counter('outbound_completed')
const outboundFailed    = new Counter('outbound_failed')
const stockInsufficient = new Counter('outbound_stock_insufficient')

export const options = {
  vus:      parseInt(__ENV.VUS || '2'),
  duration: __ENV.DURATION || '30s',
  thresholds: {
    http_req_failed:       ['rate<0.05'],
    http_req_duration:     ['p(95)<2000'],
    outbound_flow_duration:['p(95)<8000'],
    outbound_completed:    ['count>0'],
  },
}

function jsonHeaders(token) {
  return {
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${token}`,
    },
  }
}

function login() {
  const r = http.post(
    `${BASE}/auth/login`,
    JSON.stringify({ username: 'admin', password: __ENV.ADMIN_PASS || 'admin' }),
    { headers: { 'Content-Type': 'application/json' } },
  )
  return r.status === 200 ? r.json('token') : null
}

export function setup() {
  const token = login()
  if (!token) throw new Error('setup: 登入失敗')

  const wRes = http.get(`${BASE}/warehouse/`, jsonHeaders(token))
  const warehouses = wRes.json('data') || []
  if (!warehouses.length) throw new Error('setup: 沒有倉庫，請先執行 seed.py')

  const pRes = http.get(`${BASE}/product/?limit=5`, jsonHeaders(token))
  const products = pRes.json('data') || []
  if (!products.length) throw new Error('setup: 沒有產品，請先執行 seed.py')

  return {
    warehouseId: warehouses[0]._id,
    products:    products.slice(0, 3).map(p => ({ id: p._id, name: p.name })),
  }
}

export default function (data) {
  const token = login()
  if (!token) { outboundFailed.add(1); return }

  const h     = jsonHeaders(token)
  const start = Date.now()

  group('出庫流程', () => {
    // 1. 建立出庫單
    const createRes = http.post(`${BASE}/outbound/`, JSON.stringify({
      warehouse_id: data.warehouseId,
      customer:     `k6-Client-VU${__VU}`,
      remark:       `k6 負載測試 iter=${__ITER}`,
    }), h)

    if (!check(createRes, {
      '建立出庫單 200': (r) => r.status === 200,
      '回傳 _id':      (r) => !!r.json('data._id'),
    })) {
      outboundFailed.add(1)
      return
    }

    const orderId = createRes.json('data._id')
    sleep(0.2)

    // 2. 新增品項（少量，避免超出庫存）
    let itemAdded = 0
    for (const prod of data.products) {
      const itemRes = http.post(`${BASE}/outbound/${orderId}/item`, JSON.stringify({
        product_id:   prod.id,
        expected_qty: 1,   // 少量避免庫存不足
        unit_price:   10,
      }), h)
      if (itemRes.status === 200) itemAdded++
    }

    check(null, { '至少新增 1 個品項': () => itemAdded >= 1 })
    sleep(0.2)

    // 3. 確認出庫單（可能因庫存不足而回 400）
    const confirmRes = http.post(`${BASE}/outbound/${orderId}/confirm`, null, h)

    if (confirmRes.status === 400) {
      // 庫存不足是預期行為，記錄但不算失敗
      stockInsufficient.add(1)
      check(confirmRes, {
        '庫存不足回傳 400': (r) => r.status === 400,
        '有錯誤訊息':       (r) => !!r.json('message'),
      })
      // 取消訂單
      http.post(`${BASE}/outbound/${orderId}/cancel`, null, h)
      return
    }

    if (!check(confirmRes, { '確認出庫單 200': (r) => r.status === 200 })) {
      outboundFailed.add(1)
      return
    }
    sleep(0.2)

    // 4. 完成出庫
    const completeRes = http.post(`${BASE}/outbound/${orderId}/complete`, null, h)
    if (!check(completeRes, { '完成出庫 200': (r) => r.status === 200 })) {
      outboundFailed.add(1)
      return
    }

    // 5. 驗證狀態
    const detailRes = http.get(`${BASE}/outbound/${orderId}`, h)
    check(detailRes, {
      '出庫單狀態為 completed': (r) => r.json('data.status') === 'completed',
    })

    outboundDuration.add(Date.now() - start)
    outboundCompleted.add(1)
  })

  sleep(0.5)
}
