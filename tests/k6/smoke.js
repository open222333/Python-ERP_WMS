/**
 * k6 Smoke Test — WMS API 基本健康檢查
 *
 * 用法：
 *   k6 run tests/k6/smoke.js
 *   k6 run --env BASE_URL=http://your-server tests/k6/smoke.js
 *
 * 目的：確認所有主要端點可正常回應，不做壓力測試（1 VU × 1 iteration）
 */

import http from 'k6/http'
import { check, group } from 'k6'
import { SharedArray } from 'k6/data'

const BASE = __ENV.BASE_URL || 'http://localhost'
const ADMIN_USER = __ENV.ADMIN_USER || 'admin'
const ADMIN_PASS = __ENV.ADMIN_PASS || 'admin'

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    http_req_failed:   ['rate<0.01'],       // 失敗率 < 1%
    http_req_duration: ['p(95)<3000'],      // 95% 請求 < 3s
    checks:            ['rate==1.0'],       // 所有 check 必須全過
  },
}

function headers(token) {
  return {
    headers: {
      'Content-Type':  'application/json',
      'Authorization': token ? `Bearer ${token}` : '',
    },
  }
}

export default function () {
  let token = ''

  // ── 認證 ────────────────────────────────────────────────
  group('Auth', () => {
    const r = http.post(
      `${BASE}/auth/login`,
      JSON.stringify({ username: ADMIN_USER, password: ADMIN_PASS }),
      { headers: { 'Content-Type': 'application/json' } },
    )
    check(r, {
      'login 200':     (r) => r.status === 200,
      'login success': (r) => r.json('success') === true,
      'token exists':  (r) => r.json('token') && r.json('token').length > 10,
    })
    token = r.json('token') || ''

    const me = http.get(`${BASE}/auth/me`, headers(token))
    check(me, {
      'GET /auth/me 200': (r) => r.status === 200,
      '/auth/me username': (r) => r.json('username') === ADMIN_USER,
    })
  })

  // ── 倉庫 ────────────────────────────────────────────────
  group('Warehouse', () => {
    const r = http.get(`${BASE}/warehouse/`, headers(token))
    check(r, {
      'GET /warehouse/ 200':  (r) => r.status === 200,
      '/warehouse/ is array': (r) => Array.isArray(r.json('data')),
    })
  })

  // ── 產品 ────────────────────────────────────────────────
  group('Product', () => {
    const cat = http.get(`${BASE}/product/category/`, headers(token))
    check(cat, { 'GET /product/category/ 200': (r) => r.status === 200 })

    const prod = http.get(`${BASE}/product/`, headers(token))
    check(prod, {
      'GET /product/ 200':  (r) => r.status === 200,
      '/product/ is array': (r) => Array.isArray(r.json('data')),
    })
  })

  // ── 庫存 ────────────────────────────────────────────────
  group('Inventory', () => {
    const r = http.get(`${BASE}/inventory/`, headers(token))
    check(r, { 'GET /inventory/ 200': (r) => r.status === 200 })
  })

  // ── 入出庫 ──────────────────────────────────────────────
  group('Inbound / Outbound', () => {
    const ib = http.get(`${BASE}/inbound/`, headers(token))
    check(ib, { 'GET /inbound/ 200': (r) => r.status === 200 })

    const ob = http.get(`${BASE}/outbound/`, headers(token))
    check(ob, { 'GET /outbound/ 200': (r) => r.status === 200 })
  })

  // ── 菜單 ────────────────────────────────────────────────
  group('Menu', () => {
    const r = http.get(`${BASE}/menu/`, headers(token))
    check(r, { 'GET /menu/ 200': (r) => r.status === 200 })
  })

  // ── POS ─────────────────────────────────────────────────
  group('POS', () => {
    const r = http.get(`${BASE}/pos/sales`, headers(token))
    check(r, { 'GET /pos/sales 200': (r) => r.status === 200 })
  })

  // ── 系統設定 ─────────────────────────────────────────────
  group('Settings', () => {
    const r = http.get(`${BASE}/settings/`, headers(token))
    check(r, { 'GET /settings/ 200': (r) => r.status === 200 })
  })
}
