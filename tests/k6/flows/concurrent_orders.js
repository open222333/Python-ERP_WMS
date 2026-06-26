/**
 * k6 並發訂單測試 — 驗證庫存原子扣減不超賣
 *
 * 場景：N 個 VU 同時對同一產品下單（POS 結帳）
 *       庫存只剩 STOCK_LIMIT 件，驗證成功筆數不超過庫存
 *
 * 前置條件：已執行 seed.py（需要有倉庫、產品、初始庫存）
 *
 * 用法：
 *   k6 run tests/k6/flows/concurrent_orders.js
 *   k6 run --env VUS=20 --env STOCK_LIMIT=10 tests/k6/flows/concurrent_orders.js
 *
 * 關鍵指標：
 *   - pos_success_count  不得超過 STOCK_LIMIT
 *   - pos_fail_count     超賣失敗（庫存不足 → 400）是預期行為
 *   - 完成後手動查庫存，確認數量 >= 0
 */

import http from 'k6/http'
import { check, sleep } from 'k6'
import { Counter, Rate } from 'k6/metrics'

const BASE        = __ENV.BASE_URL    || 'http://localhost'
const VUS         = parseInt(__ENV.VUS         || '15')
const STOCK_LIMIT = parseInt(__ENV.STOCK_LIMIT || '10')  // 測試前設定的庫存量

// 自訂 Metrics
const posSuccess = new Counter('pos_success_count')   // 成功結帳筆數
const posFail    = new Counter('pos_fail_count')      // 庫存不足失敗筆數
const posError   = new Counter('pos_error_count')     // 其他錯誤

export const options = {
  // 所有 VU 在同一時間點啟動（真正的並發衝突）
  scenarios: {
    concurrent_spike: {
      executor:  'shared-iterations', // 所有 VU 共用一個 iteration pool
      vus:        VUS,
      iterations: VUS,                // 每個 VU 跑一次（模擬 VUS 人同時下單）
      maxDuration: '30s',
    },
  },
  thresholds: {
    // 核心驗證：成功筆數不可超過庫存上限（超賣代表原子保護失效）
    'pos_success_count': [`count<=${STOCK_LIMIT}`],
    // 系統本身不應回傳 5xx
    'http_req_failed':   ['rate<0.01'],
    'pos_error_count':   ['count==0'],
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

export function setup() {
  // 以 admin 登入
  const loginRes = http.post(
    `${BASE}/auth/login`,
    JSON.stringify({ username: 'admin', password: __ENV.ADMIN_PASS || 'admin' }),
    { headers: { 'Content-Type': 'application/json' } },
  )
  if (loginRes.status !== 200) throw new Error('setup 登入失敗')
  const token = loginRes.json('token')
  const h = jsonHeaders(token)

  // 取得第一個倉庫
  const whRes = http.get(`${BASE}/warehouse/`, h)
  const warehouses = whRes.json('data') || []
  if (!warehouses.length) throw new Error('setup: 無倉庫，請先執行 seed.py')

  // 取得第一個產品
  const pRes = http.get(`${BASE}/product/?limit=1`, h)
  const products = pRes.json('data') || []
  if (!products.length) throw new Error('setup: 無產品，請先執行 seed.py')

  const warehouseId = warehouses[0]._id
  const product     = products[0]

  // 將庫存設定為 STOCK_LIMIT（盤點調整，確保測試條件一致）
  http.post(`${BASE}/inventory/adjust`, JSON.stringify({
    warehouse_id: warehouseId,
    product_id:   product._id,
    quantity:     STOCK_LIMIT,
    remark:       `k6 並發測試前設定庫存 ${STOCK_LIMIT}`,
  }), h)

  console.log(`✓ 庫存設定完成：${product.name} × ${STOCK_LIMIT} 件`)
  console.log(`✓ 即將啟動 ${VUS} 個 VU 同時搶購`)

  return { warehouseId, product, token }
}

export default function (data) {
  const h = jsonHeaders(data.token)

  // 所有 VU 同時對同一產品結帳 1 件
  const res = http.post(`${BASE}/pos/sale`, JSON.stringify({
    warehouse_id: data.warehouseId,
    items: [{
      product_id:   data.product._id,
      product_name: data.product.name,
      product_sku:  data.product.sku || '',
      quantity:     1,
      unit_price:   data.product.sell_price || 10,
    }],
    payment: { type: 'cash', cash_amount: data.product.sell_price || 10 },
  }), h)

  if (res.status === 200 && res.json('success')) {
    posSuccess.add(1)
    check(res, { 'POS 結帳成功 200': () => true })
  } else if (res.status === 400) {
    // 庫存不足：預期行為，代表原子保護正常運作
    posFail.add(1)
    check(res, { '庫存不足 400（正常）': () => res.status === 400 })
  } else {
    // 非預期錯誤（5xx 等）
    posError.add(1)
    console.error(`非預期錯誤 ${res.status}: ${res.body}`)
  }
}

export function teardown(data) {
  // 查詢最終庫存，印出結果供人工確認
  const h = jsonHeaders(data.token)
  const invRes = http.get(
    `${BASE}/inventory/?warehouse_id=${data.warehouseId}&product_id=${data.product._id}`,
    h,
  )
  const inv = (invRes.json('data') || [])[0]
  const remaining = inv ? inv.quantity : '無法取得'

  console.log(`\n── 並發測試結果 ──────────────────────`)
  console.log(`  庫存上限（測試前設定）：${STOCK_LIMIT}`)
  console.log(`  並發 VU 數：          ${VUS}`)
  console.log(`  結帳成功筆數：         ${data.successCount || '見 pos_success_count'}`)
  console.log(`  庫存不足被拒筆數：     ${data.failCount   || '見 pos_fail_count'}`)
  console.log(`  最終剩餘庫存：         ${remaining}`)
  console.log(`  ✅ 若剩餘庫存 >= 0 且成功筆數 <= ${STOCK_LIMIT}，代表原子保護正常`)
  console.log(`──────────────────────────────────────\n`)
}
