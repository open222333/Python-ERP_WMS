/**
 * k6 Load Test — 讀取端點壓力測試
 *
 * 模擬多名員工同時查詢庫存、產品、訂單等場景
 * 採 Stages 階段式負載（ramp-up → 穩定 → ramp-down）
 *
 * 用法：
 *   k6 run tests/k6/load.js
 *   k6 run --env PEAK_VUS=20 tests/k6/load.js
 *
 * 輸出至 InfluxDB（搭配 Grafana 視覺化）：
 *   k6 run --out influxdb=http://localhost:8086/k6 tests/k6/load.js
 */

import http from 'k6/http'
import { check, sleep, group } from 'k6'
import { Rate } from 'k6/metrics'

const BASE     = __ENV.BASE_URL  || 'http://localhost'
const PEAK_VUS = parseInt(__ENV.PEAK_VUS || '10')

const errorRate = new Rate('errors')

export const options = {
  stages: [
    { duration: '30s', target: PEAK_VUS },      // Ramp-up
    { duration: '1m',  target: PEAK_VUS },      // 穩定負載
    { duration: '30s', target: 0         },      // Ramp-down
  ],
  thresholds: {
    http_req_failed:   ['rate<0.02'],            // 失敗率 < 2%
    http_req_duration: ['p(50)<500', 'p(95)<1500', 'p(99)<3000'],
    errors:            ['rate<0.02'],
  },
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
  if (!token) throw new Error('setup 登入失敗')
  return { token }
}

export default function (data) {
  // 每個 VU iteration 隨機模擬一種使用者行為
  const scenario = Math.floor(Math.random() * 5)
  const h = {
    headers: {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${data.token}`,
    },
  }

  switch (scenario) {
    case 0:
      group('查詢庫存列表', () => {
        const r = http.get(`${BASE}/inventory/?limit=50`, h)
        const ok = check(r, {
          '200':        (r) => r.status === 200,
          '回傳 data':   (r) => Array.isArray(r.json('data')),
        })
        errorRate.add(!ok)
      })
      break

    case 1:
      group('查詢產品列表', () => {
        const r = http.get(`${BASE}/product/?limit=50`, h)
        const ok = check(r, { '200': (r) => r.status === 200 })
        errorRate.add(!ok)
      })
      break

    case 2:
      group('查詢入庫單', () => {
        const r = http.get(`${BASE}/inbound/?limit=20`, h)
        const ok = check(r, { '200': (r) => r.status === 200 })
        errorRate.add(!ok)
      })
      break

    case 3:
      group('查詢出庫單', () => {
        const r = http.get(`${BASE}/outbound/?limit=20`, h)
        const ok = check(r, { '200': (r) => r.status === 200 })
        errorRate.add(!ok)
      })
      break

    case 4:
      group('查詢 POS 銷售記錄', () => {
        const r = http.get(`${BASE}/pos/sales?limit=20`, h)
        const ok = check(r, { '200': (r) => r.status === 200 })
        errorRate.add(!ok)
      })
      break
  }

  sleep(Math.random() * 1 + 0.5)   // 0.5s ~ 1.5s 思考時間（think time）
}
