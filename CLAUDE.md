# Python-ERP_WMS — CLAUDE.md

## 專案概覽

Flask + MongoDB + Vue 3 的多店家 WMS / POS 系統。

- **後端**：Flask Blueprint，JWT 認證，MongoDB（主資料庫）+ Redis（TableSession）
- **前端**：Vue 3 + Vite，打包輸出至 `frontend-dist/`，由 nginx 靜態服務
- **API 基底路徑**：nginx 直接代理 `/warehouse/`、`/inbound/` 等，**無 `/api/` 前綴**

### 前端 Build 方式

| 情境 | 指令 |
|---|---|
| **Docker 生產** | `docker compose build nginx && docker compose up -d nginx`（Dockerfile.nginx 內部跑 npm，不需本機 Node） |
| **Docker Dev 模式**（快速迭代） | `nvm use 18 && cd frontend && npm run build`，然後 `docker compose -f docker-compose.yml -f docker-compose.dev.yml restart nginx` |
| **本機 Vite 熱更新**（最快） | `python run.py`（Flask port 5000）+ `cd frontend && npm run dev`（Vite port 3000，自動 proxy） |

> `docker-compose.dev.yml`：覆寫 nginx 為 volume mount，`restart nginx` 瞬間生效，無需重 build image。

---

## 資料庫關聯圖

```
stores ──────────────────────────────────────────────────────────────────────┐
  │ store_role_id → store_roles                                              │
  │                                                                          │
users                                                                        │
  │ store_ids[]  → stores                                                    │
  │ template_id  → user_templates                                            │
                                                                             │
product_categories (self-ref: parent_id → product_categories)               │
  │                                                                          │
products                                                                     │
  │ category_id → product_categories                                         │
                                                                             │
menus                                                                        │
  │ store_id → stores                                                        │
  │ items[].linked_products[].product_id  → products                        │
  │ items[].linked_products[].warehouse_id → warehouses                     │
                                                                             │
warehouses                                                                   │
  │ store_id → stores ──────────────────────────────────────────────────────┘
  │
warehouse_locations
  │ warehouse_id → warehouses

inventory
  │ product_id   → products
  │ warehouse_id → warehouses
  │ location_id  → warehouse_locations (optional)

stock_movements
  │ product_id   → products   (+ denormalized name/sku)
  │ warehouse_id → warehouses (+ denormalized name)
  │ reference_id → inbound_orders | outbound_orders | pos_orders | ...

inbound_orders
  │ warehouse_id → warehouses
  │ items[].product_id → products

outbound_orders
  │ warehouse_id → warehouses
  │ items[].product_id → products

customer_orders
  │ store_id → stores

pos_orders
  │ warehouse_id → warehouses (optional)
  │ store_id     → stores (optional)
  │ cust_order_id → customer_orders (optional)
  │ delivery_order_id → delivery_orders (optional)

delivery_orders        (UberEats / foodpanda webhook)
delivery_mappings
  │ product_id → products
delivery_settings
  │ store_ref              → stores
  │ default_warehouse_id   → warehouses
  │ mapping_template_id    → delivery_mapping_templates
delivery_mapping_templates   (品項對應模板，可跨分店共用)

invoices
  │ order_id → pos_orders

logs                   (操作紀錄)
system_settings        (key-value 全域設定)

Redis:
  table_session:{table_no}     → {token, table_no, expires_at}  TTL 6h
  table_session_tok:{token}    → table_no
  table_session_closed:{table_no} → '1'  TTL 300s
```

---

## 頁面功能

### 獨立頁面（無需登入 / 特殊）

| 路由 | 檔案 | 功能 |
|------|------|------|
| `/login` | `LoginView.vue` | 帳密登入，JWT access token（8h）+ refresh token（30d） |
| `/pos` | `PosView.vue` | POS 收銀台（PWA，橫向），支援 LINE Pay / ZPay / 現金 / 刷卡 |
| `/quick-io` | `QuickIoView.vue` | 快速出入庫，不走完整採購單流程，直接批次調整庫存 |
| `/kitchen` | `KitchenView.vue` | 備餐顯示（SSE 即時），無需登入 |
| `/order` | `OrderView.vue` | 顧客點餐頁（掃 QR 進入），session token 驗證桌號 |

### 後台頁面（`/admin/*`，需登入）

| 路由 | 檔案 | 功能 |
|------|------|------|
| `/admin/dashboard` | `DashboardView.vue` | 儀表板：出入庫統計（日/週/月/年）、低庫存警示、待處理訂單數 |
| `/admin/categories` | `CategoriesView.vue` | 產品分類 CRUD，支援 sort_order 排序 |
| `/admin/products` | `ProductsView.vue` | 產品 CRUD，分類篩選，批次啟停/刪除，CSV 匯出/匯入 |
| `/admin/warehouses` | `WarehousesView.vue` | 倉庫 CRUD，含庫位子管理 |
| `/admin/inventory` | `InventoryView.vue` | 庫存查詢（依倉庫篩選），即時盤點調整 |
| `/admin/inbound` | `InOutboundView.vue` | 出入庫管理（tab 切換）：入庫建立 → 確認 → 完成（增庫存）；出庫建立 → 確認（驗庫存）→ 完成（扣庫存）；`/admin/outbound` 自動導向此頁 |
| `/admin/movements` | `MovementsView.vue` | 庫存異動紀錄，依倉庫/類型/日期篩選 |
| `/admin/cust-orders` | `CustOrdersView.vue` | 顧客訂單管理，SSE 即時推送，狀態流轉自動產生 POS 單 |
| `/admin/pos-sales` | `PosSalesView.vue` | POS 銷售紀錄，CSV 匯出/匯入，退款 |
| `/admin/pos-report` | `PosReportView.vue` | POS 銷售報表，日/週/月/年圖表 |
| `/admin/menus` | `MenusView.vue` | 菜單全功能編輯：菜單/分類/選項組/品項，庫存聯動設定，JSON 匯出/匯入 |
| `/admin/delivery-orders` | `DeliveryOrdersView.vue` | 外送平台訂單（UberEats / foodpanda），狀態管理 |
| `/admin/delivery-settings` | `DeliverySettingsView.vue` | 外送平台設定（兩個 Tab：店家設定、品項對應模板 CRUD） |
| `/admin/stores` | `StoresView.vue` | 分店 CRUD 及分店帳號管理 |
| `/admin/users` | `UsersView.vue` | 使用者/範本/分店/店家角色，四個 tab |
| `/admin/logs` | `LogsView.vue` | 操作紀錄查詢，CSV 匯出/匯入，定期清理 |
| `/admin/settings` | `SettingsView.vue` | 系統設定：預設倉庫/店家/菜單，POS 付款方式、折扣預設值，日誌保留天數 |
| `/admin/invoices` | `InvoicesView.vue` | 電子發票列表，作廢，詳情查看 |
| `/admin/invoice-settings` | `InvoiceSettingsView.vue` | ECPay 發票設定，各店家終端機管理 |

---

## 所有 API

> 所有路由均**無 `/api/` 前綴**。JWT 帶於 `Authorization: Bearer <token>` header。

### `/auth` — 認證

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| POST | `/auth/login` | 帳密登入，回傳 access_token（8h）；`remember_me=true` 額外回傳 refresh_token（30d）。Rate limit: 10/min、50/hr | 無 |
| POST | `/auth/refresh` | 用 refresh token 換新 access token | JWT refresh |
| GET | `/auth/me` | 回傳目前使用者資訊（role, store_ids, pages_enabled） | JWT |

### `/store` — 分店管理

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/store/role/` | 列出所有店家角色範本 | admin |
| POST | `/store/role/` | 新增店家角色 | admin |
| PUT | `/store/role/<rid>` | 修改店家角色（非系統預設） | admin |
| DELETE | `/store/role/<rid>` | 刪除店家角色 | admin |
| GET | `/store/` | 列出所有分店 | admin |
| POST | `/store/` | 新增分店（自動建立預設菜單與倉庫） | admin |
| GET | `/store/<store_id>` | 取得單一分店 | admin |
| PUT | `/store/<store_id>` | 修改分店資料 | admin |
| DELETE | `/store/<store_id>` | 刪除分店 | admin |
| GET | `/store/<store_id>/users` | 列出分店帳號 | admin |
| POST | `/store/<store_id>/users` | 在分店下建立帳號 | admin |

### `/user` — 使用者管理

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/user/` | 列出所有使用者 | admin |
| POST | `/user/` | 新增使用者（role 由範本決定） | admin |
| PUT | `/user/<user_id>` | 修改密碼/範本/分店；自動同步 role | admin |
| DELETE | `/user/<user_id>` | 刪除使用者（不可刪自己或鎖定帳號） | admin |
| GET | `/user/templates/` | 列出使用者範本 | admin |
| POST | `/user/templates/` | 新增範本 | admin |
| PUT | `/user/templates/<tid>` | 修改範本；自動同步所有綁定使用者的 role | admin |
| DELETE | `/user/templates/<tid>` | 刪除範本（系統預設不可刪） | admin |

### `/product` — 產品管理

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/product/category/` | 列出分類（依 sort_order） | JWT |
| POST | `/product/category/` | 新增分類 | admin/operator |
| PUT | `/product/category/<cid>` | 修改分類 | admin/operator |
| DELETE | `/product/category/<cid>` | 刪除分類 | admin |
| GET | `/product/` | 列出產品（可篩：keyword/category_id/status） | JWT |
| GET | `/product/barcode/<code>` | 條碼精確查詢 | JWT |
| PUT | `/product/batch` | 批次更新多筆產品（ids + 欄位） | admin/operator |
| DELETE | `/product/batch` | 批次刪除多筆產品（ids） | admin |
| GET | `/product/<pid>` | 取得單一產品 | JWT |
| POST | `/product/` | 新增產品（sku 唯一） | admin/operator |
| PUT | `/product/<pid>` | 修改產品 | admin/operator |
| DELETE | `/product/<pid>` | 刪除產品 | admin |
| GET | `/product/export` | 匯出所有產品 JSON | admin/operator |
| POST | `/product/import` | 匯入產品 JSON（sku 存在則更新） | admin/operator |

### `/menu` — 菜單管理

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/menu/` | 列出菜單（依店家過濾） | JWT |
| GET | `/menu/<mid>` | 取得菜單完整內容（含品項/分類/選項組） | JWT |
| POST | `/menu/` | 新增菜單 | admin/operator |
| PUT | `/menu/<mid>` | 修改菜單基本資料 | admin/operator |
| DELETE | `/menu/<mid>` | 刪除菜單 | admin |
| GET | `/menu/export-all` | 匯出全部菜單 JSON | admin/operator |
| POST | `/menu/import-all` | 匯入全部菜單 JSON | admin/operator |
| POST | `/menu/<mid>/item` | 新增品項 | admin/operator |
| PUT | `/menu/<mid>/item/<item_id>` | 修改品項 | admin/operator |
| DELETE | `/menu/<mid>/item/<item_id>` | 刪除品項 | admin/operator |
| POST | `/menu/<mid>/category` | 新增菜單分類 | admin/operator |
| PUT | `/menu/<mid>/category/<cat_id>` | 修改分類（同步更新品項 category 字串） | admin/operator |
| DELETE | `/menu/<mid>/category/<cat_id>` | 刪除分類 | admin/operator |
| GET | `/menu/<mid>/option-group` | 列出選項組 | JWT |
| POST | `/menu/<mid>/option-group` | 新增選項組 | admin/operator |
| PUT | `/menu/<mid>/option-group/<gid>` | 修改選項組 | admin/operator |
| DELETE | `/menu/<mid>/option-group/<gid>` | 刪除選項組（移除品項關聯） | admin/operator |
| GET | `/menu/<mid>/export` | 匯出單一菜單 JSON | admin/operator |
| POST | `/menu/<mid>/import` | 匯入分類/選項組/品項至指定菜單 | admin/operator |

### `/warehouse` — 倉庫管理

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/warehouse/` | 列出倉庫（依店家過濾） | JWT |
| GET | `/warehouse/<wid>` | 取得單一倉庫 | JWT |
| POST | `/warehouse/` | 新增倉庫 | admin |
| PUT | `/warehouse/<wid>` | 修改倉庫 | admin/operator |
| DELETE | `/warehouse/<wid>` | 刪除倉庫 | admin |
| GET | `/warehouse/<wid>/location/` | 列出庫位 | JWT |
| POST | `/warehouse/<wid>/location/` | 新增庫位 | admin/operator |
| PUT | `/warehouse/location/<lid>` | 修改庫位 | admin/operator |
| DELETE | `/warehouse/location/<lid>` | 刪除庫位 | admin |

### `/inventory` — 庫存

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/inventory/` | 列出庫存（可篩：warehouse_id/product_id） | JWT |
| POST | `/inventory/adjust` | 盤點調整（設定絕對數量，記錄異動） | admin/operator |
| POST | `/inventory/batch` | 批次快速出入庫/消耗 | admin/operator |
| GET | `/inventory/movement/` | 列出庫存異動紀錄 | JWT |

### `/inbound` — 入庫單

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/inbound/` | 列出入庫單（可篩：status/warehouse_id） | JWT |
| GET | `/inbound/<oid>` | 取得單一入庫單 | JWT |
| POST | `/inbound/` | 建立入庫單（status=pending） | admin/operator |
| PUT | `/inbound/<oid>` | 修改供應商/備註/倉庫（pending 限定） | admin/operator |
| POST | `/inbound/<oid>/item` | 新增品項（pending 限定） | admin/operator |
| PUT | `/inbound/<oid>/item/<item_id>` | 修改品項數量/單價 | admin/operator |
| DELETE | `/inbound/<oid>/item/<item_id>` | 移除品項 | admin/operator |
| POST | `/inbound/<oid>/confirm` | 確認：pending → confirmed | admin/operator |
| POST | `/inbound/<oid>/complete` | 完成：confirmed → completed（增加庫存） | admin/operator |
| POST | `/inbound/<oid>/cancel` | 取消（pending/confirmed 限定） | admin/operator |

### `/outbound` — 出庫單

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/outbound/` | 列出出庫單 | JWT |
| GET | `/outbound/<oid>` | 取得單一出庫單 | JWT |
| POST | `/outbound/` | 建立出庫單 | admin/operator |
| PUT | `/outbound/<oid>` | 修改客戶/備註/倉庫 | admin/operator |
| POST | `/outbound/<oid>/item` | 新增品項 | admin/operator |
| PUT | `/outbound/<oid>/item/<item_id>` | 修改品項 | admin/operator |
| DELETE | `/outbound/<oid>/item/<item_id>` | 移除品項 | admin/operator |
| POST | `/outbound/<oid>/confirm` | 確認（驗庫存充足）：pending → confirmed | admin/operator |
| POST | `/outbound/<oid>/complete` | 完成：confirmed → completed（扣庫存） | admin/operator |
| POST | `/outbound/<oid>/cancel` | 取消 | admin/operator |

### `/analytics` — 分析

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/analytics/stock_alerts` | 低庫存（< min_stock）/ 高庫存（> max_stock）警示 | JWT |
| GET | `/analytics/summary` | 儀表板摘要：出入庫統計 + 庫存警示 | JWT |

### `/pos` — POS 收銀

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/pos/` | 渲染 POS SPA HTML | 無 |
| GET | `/pos/manifest.json` | PWA manifest | 無 |
| POST | `/pos/sale` | 結帳：原子庫存扣減 + LINE Pay / ZPay 整合 | admin/operator/cashier |
| GET | `/pos/sales` | 查詢銷售紀錄（可篩：date/cashier/status/source） | admin/operator/cashier |
| GET | `/pos/sales/export` | 匯出銷售 CSV（streaming） | admin/operator/cashier |
| POST | `/pos/sales/import` | 批次匯入歷史銷售（不扣庫存） | admin |
| GET | `/pos/sales/<sid>` | 取得單一銷售 | admin/operator/cashier |
| POST | `/pos/sales/<sid>/refund` | 退款：還庫存 + LINE Pay / ZPay 退款 API | admin/operator |
| GET | `/pos/payment-methods` | 取得 POS 付款方式清單 | JWT |
| PUT | `/pos/payment-methods` | 更新付款方式清單 | admin |
| GET | `/pos/linepay-settings` | 取得 LINE Pay 設定（secret 遮罩） | admin/operator |
| PUT | `/pos/linepay-settings` | 更新 LINE Pay 設定 | admin |
| GET | `/pos/zpay-settings` | 取得全支付設定 | JWT |
| PUT | `/pos/zpay-settings` | 更新全支付設定 | admin |
| GET | `/pos/summary` | 銷售報表（日/週/月/年細分） | admin/operator/cashier |

### `/customer-order` — 顧客點單

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/customer-order/menu` | 公開：取得點餐菜單（QR token 驗證，回傳 session_token） | 無 |
| POST | `/customer-order/` | 公開：顧客建立訂單 | 無 |
| GET | `/customer-order/stream` | SSE：備餐廚房即時推送（JWT via ?token=） | JWT query |
| GET | `/customer-order/` | 管理：列出訂單（可篩：status/date） | JWT |
| GET | `/customer-order/active` | 管理：取得 pending+processing 訂單（廚房 FIFO） | JWT |
| GET | `/customer-order/stats` | 管理：今日訂單統計 | JWT |
| GET | `/customer-order/<oid>` | 管理：取得單一訂單 | JWT |
| PUT/PATCH | `/customer-order/<oid>/status` | 管理：更新訂單狀態（complete 自動產生 POS 單並關閉桌次） | admin/operator |
| GET | `/customer-order/session` | 公開：驗證 session token，回傳桌號資訊 | 無 |
| GET | `/customer-order/customer-stream` | SSE：顧客追蹤訂單狀態 | 無（session token） |
| DELETE | `/customer-order/session/<table_no>` | 管理：手動關閉桌次（觸發 SSE session_closed） | admin/operator |
| GET | `/customer-order/tokens` | 管理：取得所有桌號 QR token + session 狀態 | admin |
| POST | `/customer-order/tokens/refresh` | 管理：重新產生所有桌號 token | admin |
| PUT | `/customer-order/tokens/tables` | 管理：新增/修改/刪除/停用桌號 | admin |

### `/delivery` — 外送平台

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| POST | `/delivery/webhook/ubereats` | UberEats webhook（簽名驗證，auto-confirm） | 無（webhook） |
| POST | `/delivery/webhook/foodpanda` | foodpanda webhook（簽名驗證） | 無（webhook） |
| GET | `/delivery/orders` | 列出外送訂單（可篩：platform/status/date） | admin/operator/cashier |
| GET | `/delivery/orders/<oid>` | 取得單一外送訂單 | admin/operator/cashier |
| PUT | `/delivery/orders/<oid>/status` | 更新狀態（同步至平台；confirmed 自動建立 POS 單） | admin/operator |
| POST | `/delivery/sync/<platform>` | 從平台拉取最新訂單 | admin/operator |
| POST | `/delivery/menu/sync/<platform>` | 同步平台菜單至 WMS 菜單管理 | admin/operator |
| GET | `/delivery/mappings` | 列出平台商品對照（platform_id ↔ product_id） | admin/operator |
| POST | `/delivery/mappings` | 新增/更新對照（upsert） | admin/operator |
| DELETE | `/delivery/mappings/<mid>` | 刪除對照 | admin/operator |
| GET | `/delivery/settings/<platform>` | 取得平台設定 | admin |
| PUT | `/delivery/settings/<platform>` | 更新平台設定 | admin |
| GET | `/delivery/store/` | 列出所有店家的外送設定 | admin |
| GET | `/delivery/store/<store_id>/settings/<platform>` | 取得指定店家平台設定 | admin |
| PUT | `/delivery/store/<store_id>/settings/<platform>` | 更新指定店家平台設定（含 mapping_template_id） | admin |
| GET | `/delivery/mapping-templates/` | 列出所有品項對應模板 | admin |
| POST | `/delivery/mapping-templates/` | 新增品項對應模板 | admin |
| PUT | `/delivery/mapping-templates/<tid>` | 更新品項對應模板 | admin |
| DELETE | `/delivery/mapping-templates/<tid>` | 刪除品項對應模板 | admin |

### `/invoice` — 電子發票

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/invoice/settings` | 取得 ECPay 設定（key 遮罩） | admin/operator |
| PUT | `/invoice/settings` | 更新 ECPay 設定 | admin |
| GET | `/invoice/store/` | 列出各店家發票設定摘要 | admin |
| GET | `/invoice/store/<store_id>/settings` | 取得店家發票設定 | admin |
| PUT | `/invoice/store/<store_id>/settings` | 更新店家發票設定 | admin |
| GET | `/invoice/device-models` | 列出支援的印表機型號 | JWT |
| GET | `/invoice/store/<store_id>/terminals/` | 列出店家終端機 | admin |
| POST | `/invoice/store/<store_id>/terminals/` | 新增終端機（自動產生 ID） | admin |
| PUT | `/invoice/store/<store_id>/terminals/<tid>` | 修改終端機 | admin |
| DELETE | `/invoice/store/<store_id>/terminals/<tid>` | 刪除終端機 | admin |
| POST | `/invoice/issue` | 對已完成 POS 單開立電子發票（ECPay） | admin/operator/cashier |
| POST | `/invoice/<inv_id>/void` | 作廢已開發票（ECPay） | admin/operator |
| GET | `/invoice/` | 列出發票（可篩：status/date） | admin/operator/cashier |
| GET | `/invoice/<inv_id>` | 取得單一發票 | admin/operator/cashier |

### `/log` — 操作紀錄

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/log/` | 列出紀錄（可篩：username/action/date）；觸發自動清理 | JWT |
| GET | `/log/stats` | 紀錄總數 + 超過 N 天的數量 | JWT |
| GET | `/log/export` | 匯出 CSV（streaming） | JWT |
| POST | `/log/import` | 批次匯入 CSV/JSON | admin |
| POST | `/log/cleanup` | 刪除 N 天前的紀錄 | admin |

### `/settings` — 系統設定

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/settings/` | 取得全部系統設定（key-value dict） | JWT |
| PUT | `/settings/` | 批次更新系統設定 | admin |

---

## 環境變數與設定

### FLASK_ENV

`run.py` 以 `FLASK_ENV` 環境變數決定載入哪個 Config 類別：

| `FLASK_ENV` 值 | 使用 Config 類別 | 說明 |
|---|---|---|
| `production`（預設） | `ProductionConfig` | DEBUG=False，正式環境 |
| `development` | `DevelopmentConfig` | DEBUG=True，本機開發 |
| `testing` | `TestingConfig` | TESTING=True，自動化測試 |

```bash
# 啟動方式
FLASK_ENV=development python run.py   # 開發模式
FLASK_ENV=testing python run.py       # 測試模式
python run.py                         # 正式環境（預設）
```

> `conf/config.py` 原本的 `DEBUG/TESTING` tuple bug 已修復（舊版的值永遠為 truthy），現在各環境的旗標設定正確。

---

## 資料庫索引

以下索引已新增，改善高頻查詢的效能：

| Collection | 索引欄位 | 用途 |
|---|---|---|
| `inventory` | `(warehouse_id, product_id)` | 庫存按倉庫/產品查詢 |
| `inbound_orders` | `(status, created_at)` | 入庫單按狀態+時間篩選 |
| `outbound_orders` | `(status, created_at)` | 出庫單按狀態+時間篩選 |
| `pos_orders` | `(cashier, created_at)` | POS 單按收銀員+時間篩選 |
| `customer_orders` | `(status, created_at)` | 顧客訂單按狀態+時間篩選 |

---

## stock_movements 自動清除

`GET /inventory/movement/` 觸發時，會依照系統設定 `movements_retention_days` 自動清除過期的庫存異動紀錄（lazy 觸發）。

於 `/admin/settings` 頁面的「日誌保留天數」欄位調整即可，0 或未設定時不清除。

---

## Bug 修復 / 安全修復記錄

| 檔案 | 問題 | 修復說明 |
|---|---|---|
| `conf/config.py` | `DEBUG`/`TESTING` 設為 tuple，永遠為 truthy | 改為正確的純值；由 `FLASK_ENV` 選擇 Config 類別 |
| `run.py` | 硬寫 Config 類別 | 改用 `FLASK_ENV` 環境變數動態選擇，預設 production |
| `app/auth/view.py` | 登入與 refresh token 端點未檢查帳號鎖定狀態 | 補上 `is_locked` 檢查，鎖定帳號一律拒絕 |
| `app/settings/view.py` | PUT 端點可任意寫入任何 key，無白名單 | 加入 `ALLOWED_SETTINGS_KEYS` 白名單，拒絕未知 key |
| `app/inventory/view.py` | `GET /inventory/movement/` 無需認證；查詢無上限 | 加上 JWT 必要認證；unbounded query 加上結果上限 |
| `src/models/inbound.py` | `complete` 方法在高並發下有雙重完成的 race condition | 改用 `find_one_and_update` 原子操作，確保只能完成一次 |
| `app/outbound/view.py` | `complete` 端點缺少重複確認防護；庫存扣減有超賣風險 | 加入 re-confirm guard；庫存扣減改為原子操作防止超賣 |
| `app/delivery/view.py` | webhook 處理失敗時仍回傳 HTTP 200；`confirm` 狀態在平台 API 呼叫前即寫入 | 失敗回傳適當的非 200 狀態碼；confirm 狀態改為在平台 API 成功後才寫入 |
| `src/models/delivery.py` | `update_status` 未防止對已完成/取消等 terminal state 的更新 | 加入 terminal state guard，拒絕無效的狀態轉移 |
| `app/customer_order/view.py` | 狀態更新無狀態機驗證；建立訂單未驗證品項數量/數量/價格 | 加入狀態機合法轉移驗證；補上品項欄位的數值驗證 |
| `app/product/view.py` | 關鍵字搜尋使用者輸入直接帶入 regex，有 ReDoS 風險；`sort_order` 未驗證；分頁無上限 | 改用 `re.escape()` 轉義；`sort_order` 加型別/範圍驗證；分頁加上最大上限 |
| `app/pos/view.py` | zpay 欄位名稱錯誤；折扣值未設邊界；結果筆數無上限 | 修正欄位名稱；折扣上下界驗證；`limit` 加上最大值 |
| `src/models/pos.py` | 退款時 `warehouse_id=None` 導致 crash | 加入 None 判斷，跳過庫存還原或改用預設倉庫 |
| `app/analytics/view.py` | `stock_alerts` 無結果上限，大庫存量時回應緩慢 | 查詢加上 `limit(200)` |
| `src/mongo.py` | MongoDB 連線單例非 thread-safe，高並發可能建立多餘連線 | 改用 double-checked locking 實作 thread-safe singleton |

---

## 常見注意事項

- **URL 前綴**：axios `baseURL: '/'`，nginx 無 `/api/` 前綴。錯誤用 `/api/warehouse/` 會 404
- **Flask route 順序**：`/batch` 必須在 `/<pid>` 之前，否則 `batch` 會被當作 pid
- **IME 輸入法**：Enter 觸發表單用 `@keydown.enter="e => !e.isComposing && fn()"`
- **Vue Set 響應性**：`Set` 需重新賦值才觸發更新：`selectedIds.value = new Set(selectedIds.value)`
- **Docker Volume**：`docker-compose up -d --force-recreate <service>` 才會套用新掛載
- **Vite Build Cache**：build 不更新時執行 `rm -rf node_modules/.vite` 後重 build
- **NAV_CONFIG**：`frontend/src/config/nav.ts` 是側欄與模板設定頁面的唯一資料來源。`AdminLayout.vue` 從 NAV_CONFIG 動態產生側欄，`AppSidebar.vue` 為廢棄空殼。新增頁面只需在 nav.ts 新增一筆，側欄與使用者模板自動同步
- **出入庫頁面**：`/admin/inbound` 使用 `InOutboundView.vue`（tab 切換），`/admin/outbound` redirect 至 `/admin/inbound`。舊版 `InboundView.vue` / `OutboundView.vue` 已停用（router 不再引用）
- **docker compose build nginx**：`docker-compose.nginx.yml` 已設 `build: docker/Dockerfile.nginx`，此指令會在 Docker 內部執行 npm build，不需本機安裝 Node.js
- **Docker Dev 模式**：`docker-compose.dev.yml` 覆寫 nginx 為 volume mount，搭配本機 `npm run build` + `restart nginx`，比完整 image build 快很多

---

## 測試工具

### Seed 測試資料

```bash
pip install requests
python scripts/seed.py                              # Docker（http://localhost）
python scripts/seed.py --base http://localhost:5000 # 本機 Flask
```

建立：台北倉、台中倉、4 種分類、10 種產品、各倉庫 200 件初始庫存、POS 測試菜單。

### k6 自動化測試

```bash
k6 run tests/k6/smoke.js                    # 基本健康檢查（1 VU）
k6 run tests/k6/flows/inbound_flow.js       # 入庫完整流程壓測
k6 run tests/k6/flows/outbound_flow.js      # 出庫完整流程壓測（含庫存不足 400 驗證）
k6 run tests/k6/load.js                     # 讀取端點負載測試（Stages，預設 10 VU）
```

環境變數：`BASE_URL`（預設 `http://localhost`）、`VUS`、`DURATION`、`ADMIN_PASS`。
