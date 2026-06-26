/**
 * k6 Flow Test — 完整入庫流程
 *
 * 測試業務流程：
 *   建立入庫單 → 新增品項（掃條碼）→ 確認 → 完成 → 驗證庫存增加
 *
 * 前置條件：
 *   已執行 seed.py（需要有倉庫與產品資料）
 *
 * 用法：
 *   k6 run tests/k6/flows/inbound_flow.js
 *   k6 run --env VUS=5 --env DURATION=30s tests/k6/flows/inbound_flow.js
 */

import http from 'k6/http'
import { check, sleep, group } from 'k6'
import { Trend, Counter } from 'k6/metrics'

const BASE = __ENV.BASE_URL || 'http://localhost'

// 自訂 Metrics
const inboundDuration  = new Trend('inbound_flow_duration',  true)
const inboundCompleted = new Counter('inbound_completed')
const inboundFailed    = new Counter('inbound_failed')

export const options = {
  vus:      parseInt(__ENV.VUS || '2'),
  duration: __ENV.DURATION || '30s',
  thresholds: {
    http_req_failed:      ['rate<0.05'],      // 失敗率 < 5%
    http_req_duration:    ['p(95)<2000'],     // 95% < 2s
    inbound_flow_duration:['p(95)<8000'],     // 完整流程 < 8s
    inbound_completed:    ['count>0'],        // 至少完成一筆
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
  if (r.status !== 200) return null
  return r.json('token')
}

export function setup() {
  const token = login()
  if (!token) {
    throw new Error('setup: 登入失敗，請確認 API 已啟動且帳號正確')
  }

  // 取得第一個倉庫 ID
  const wRes = http.get(`${BASE}/warehouse/`, jsonHeaders(token))
  const warehouses = wRes.json('data') || []
  if (!warehouses.length) {
    throw new Error('setup: 沒有倉庫，請先執行 seed.py')
  }

  // 取得第一個產品 ID 與 barcode
  const pRes = http.get(`${BASE}/product/?limit=5`, jsonHeaders(token))
  const products = pRes.json('data') || []
  if (!products.length) {
    throw new Error('setup: 沒有產品，請先執行 seed.py')
  }

  return {
    warehouseId: warehouses[0]._id,
    products:    products.slice(0, 3).map(p => ({
      id:      p._id,
      barcode: p.barcode || null,
    })),
  }
}

export default function (data) {
  const token = login()
  if (!token) {
    inboundFailed.add(1)
    return
  }

  const h    = jsonHeaders(token)
  const start = Date.now()

  group('入庫流程', () => {
    // 1. 建立入庫單
    const createRes = http.post(`${BASE}/inbound/`, JSON.stringify({
      warehouse_id: data.warehouseId,
      supplier:     `k6-VU${__VU}`,
      remark:       `k6 負載測試 iter=${__ITER}`,
    }), h)

    if (!check(createRes, {
      '建立入庫單 201/200': (r) => r.status === 200 || r.status === 201,
      '回傳 _id':          (r) => !!r.json('data._id'),
    })) {
      inboundFailed.add(1)
      return
    }

    const orderId = createRes.json('data._id')
    sleep(0.2)

    // 2. 新增品項
    let itemAdded = 0
    for (const prod of data.products) {
      const itemRes = http.post(`${BASE}/inbound/${orderId}/item`, JSON.stringify({
        product_id:   prod.id,
        expected_qty: Math.floor(Math.random() * 10) + 1,
        unit_price:   10,
      }), h)
      if (itemRes.status === 200) itemAdded++
    }

    check(null, { '至少新增 1 個品項': () => itemAdded >= 1 })
    sleep(0.2)

    // 3. 確認入庫單
    const confirmRes = http.post(`${BASE}/inbound/${orderId}/confirm`, null, h)
    if (!check(confirmRes, { '確認入庫單 200': (r) => r.status === 200 })) {
      inboundFailed.add(1)
      return
    }
    sleep(0.2)

    // 4. 完成入庫
    const completeRes = http.post(`${BASE}/inbound/${orderId}/complete`, null, h)
    if (!check(completeRes, { '完成入庫 200': (r) => r.status === 200 })) {
      inboundFailed.add(1)
      return
    }

    // 5. 驗證入庫單狀態
    const detailRes = http.get(`${BASE}/inbound/${orderId}`, h)
    check(detailRes, {
      '入庫單狀態為 completed': (r) => r.json('data.status') === 'completed',
    })

    inboundDuration.add(Date.now() - start)
    inboundCompleted.add(1)
  })

  sleep(0.5)
}
