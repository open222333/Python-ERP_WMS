# ARCHITECTURE — 模組、資料庫關聯與實作備忘

> 本檔為 `CLAUDE.md` 外部化的架構原文（依制度文件 L：CLAUDE.md 只留指標，原文進 docs/）。
> 架構有變動時直接修改本檔，不建副本。

## 模組一覽

後端 Blueprint（各端點詳見 `docs/API.md`）：`/auth` 認證、`/store` 分店、`/user` 使用者/範本、`/product` 產品/分類、`/menu` 菜單、`/warehouse` 倉庫/庫位、`/inventory` 庫存、`/inbound` `/outbound` 出入庫單（pending → confirmed → completed 狀態機）、`/analytics` 儀表板、`/pos` 收銀、`/customer-order` 顧客點單（SSE）、`/delivery` 外送平台（UberEats/foodpanda webhook）、`/invoice` 電子發票（ECPay）、`/log` 操作紀錄、`/settings` 系統設定。

角色權限：`admin` > `operator` > `cashier`。

## 資料庫關聯圖

```
stores ──────────────────────────────────────────────────────────────────────┐
  │ store_role_id → store_roles                                              │
users                                                                        │
  │ store_ids[] → stores；template_id → user_templates                       │
product_categories (self-ref: parent_id)                                     │
  │                                                                          │
products ── category_id → product_categories                                 │
menus ── store_id → stores；items[].linked_products[] → products/warehouses  │
warehouses ── store_id → stores ─────────────────────────────────────────────┘
  │
warehouse_locations ── warehouse_id → warehouses
inventory ── product_id / warehouse_id / location_id(optional)
stock_movements ── product_id / warehouse_id（含 denormalized name/sku）
  │ reference_id → inbound_orders | outbound_orders | pos_orders | ...
inbound_orders / outbound_orders ── warehouse_id；items[].product_id
customer_orders ── store_id
pos_orders ── warehouse_id / store_id / cust_order_id / delivery_order_id（皆 optional）
delivery_orders（webhook 來源）── store_ref（依平台店家代號自動歸屬）
delivery_mappings ── product_id 或 menu_id + menu_item_id（菜單品項對應，扣庫存走品項 linked_products）
delivery_settings ── store_ref / default_warehouse_id / mapping_template_id / store_id / vendor_code
delivery_mapping_templates（品項對應模板，可跨分店共用）
invoices ── order_id → pos_orders
logs（操作紀錄）；system_settings（key-value）

Redis:
  table_session:{table_no}        → {token, table_no, expires_at}  TTL 6h
  table_session_tok:{token}       → table_no
  table_session_closed:{table_no} → '1'  TTL 300s
```

已建索引：`inventory(warehouse_id, product_id)`、`inbound_orders(status, created_at)`、`outbound_orders(status, created_at)`、`pos_orders(cashier, created_at)`、`customer_orders(status, created_at)`。

`GET /inventory/movement/` 會依系統設定 `movements_retention_days` lazy 清除過期異動紀錄（0 或未設定則不清）。

## 外送訂單對應解析順序（PosOrder.create_from_delivery）

1. **external_id 對應**（`delivery_mappings`）：菜單品項對應（`menu_item_id`，依品項 linked_products 扣庫存，可多原料/跨倉）優先；否則產品對應（`product_id`，於預設倉扣庫存）
2. **名稱式對應**：店家設定 `item_mappings`（依 `platform_item_name` 不分大小寫比對）；為空且有綁 `mapping_template_id` → 用模板內容。`system_items` 支援 `type: 'menu_item'` 與產品型（無 type 視為產品，向下相容）
3. **無對應** → 僅記錄銷售、不扣庫存（`skipped_items` 回報）

設定取用 `DeliverySettings.effective(platform, store_ref)`：店家設定優先、空值欄位回退全域。訂單歸屬店家依 webhook payload 的平台店家代號（UberEats store id / foodpanda vendor code）比對店家設定的 `store_id` / `vendor_code`。

## 實作備忘（常見坑）

- **IME 輸入法**：Enter 觸發表單用 `@keydown.enter="e => !e.isComposing && fn()"`
- **Vue Set 響應性**：`Set` 需重新賦值才觸發更新：`selectedIds.value = new Set(selectedIds.value)`
- **Docker Volume**：`docker-compose up -d --force-recreate <service>` 才會套用新掛載
- **Vite Build Cache**：build 不更新時執行 `rm -rf node_modules/.vite` 後重 build
- **出入庫頁面**：`/admin/inbound` 使用 `InOutboundView.vue`（tab 切換），`/admin/outbound` redirect 至此。舊版 `InboundView.vue` / `OutboundView.vue` 已停用（router 不再引用）
- **Docker Dev 模式**：`docker-compose.dev.yml` 覆寫 nginx 為 volume mount，本機 `npm run build` + `restart nginx` 即生效，比重 build image 快很多

## 測試工具

```bash
# Seed 測試資料（台北/台中倉、4 分類、10 產品、各倉 200 件初始庫存、POS 菜單）
python scripts/seed.py                              # Docker（http://localhost）
python scripts/seed.py --base http://localhost:5000 # 本機 Flask

# k6 自動化測試
k6 run tests/k6/smoke.js                    # 基本健康檢查（1 VU）
k6 run tests/k6/flows/inbound_flow.js       # 入庫完整流程壓測
k6 run tests/k6/flows/outbound_flow.js      # 出庫完整流程壓測（含庫存不足 400 驗證）
k6 run tests/k6/load.js                     # 讀取端點負載測試（預設 10 VU）
```

k6 環境變數：`BASE_URL`（預設 `http://localhost`）、`VUS`、`DURATION`、`ADMIN_PASS`。
