# API 參考

> 所有路由均**無 `/api/` 前綴**。JWT 帶於 `Authorization: Bearer <token>` header。

## `/auth` — 認證

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| POST | `/auth/login` | 帳密登入，回傳 access_token（8h）；`remember_me=true` 額外回傳 refresh_token（30d）。Rate limit: 10/min、50/hr | 無 |
| POST | `/auth/refresh` | 用 refresh token 換新 access token | JWT refresh |
| GET | `/auth/me` | 回傳目前使用者資訊（role, store_ids, pages_enabled） | JWT |

## `/store` — 分店管理

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

## `/user` — 使用者管理

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

## `/product` — 產品管理

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

## `/menu` — 菜單管理

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

## `/warehouse` — 倉庫管理

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

## `/inventory` — 庫存

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/inventory/` | 列出庫存（可篩：warehouse_id/product_id） | JWT |
| POST | `/inventory/adjust` | 盤點調整（設定絕對數量，記錄異動） | admin/operator |
| POST | `/inventory/batch` | 批次快速出入庫/消耗 | admin/operator |
| GET | `/inventory/movement/` | 列出庫存異動紀錄 | JWT |

## `/inbound` — 入庫單

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

## `/outbound` — 出庫單

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

## `/analytics` — 分析

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/analytics/stock_alerts` | 低庫存（< min_stock）/ 高庫存（> max_stock）警示 | JWT |
| GET | `/analytics/summary` | 儀表板摘要：出入庫統計 + 庫存警示 | JWT |

## `/pos` — POS 收銀

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

## `/customer-order` — 顧客點單

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/customer-order/menu` | 公開：取得點餐菜單（QR token 驗證，回傳 session_token） | 無 |
| POST | `/customer-order/` | 公開：顧客建立訂單 | 無 |
| POST | `/customer-order/stream-ticket` | 取得 SSE 一次性 ticket（TTL 30s，一次性） | JWT |
| GET | `/customer-order/stream` | SSE：備餐廚房即時推送（`?ticket=` 一次性 ticket；舊 `?token=` JWT 為 deprecated 過渡） | ticket query |
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

## `/delivery` — 外送平台

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| POST | `/delivery/webhook/ubereats` | UberEats webhook（簽名驗證；依平台店家代號歸屬分店，auto-confirm 用店家有效設定） | 無（webhook） |
| POST | `/delivery/webhook/foodpanda` | foodpanda webhook（簽名驗證；歸屬邏輯同上） | 無（webhook） |
| GET | `/delivery/orders` | 列出外送訂單（可篩：platform/status/date） | admin/operator/cashier |
| GET | `/delivery/orders/<oid>` | 取得單一外送訂單 | admin/operator/cashier |
| PUT | `/delivery/orders/<oid>/status` | 更新狀態（同步至平台；confirmed 依店家有效設定建 POS 單並扣庫存） | admin/operator |
| POST | `/delivery/sync/<platform>` | 從平台拉取最新訂單 | admin/operator |
| POST | `/delivery/menu/sync/<platform>` | 同步平台菜單至 WMS 菜單管理 | admin/operator |
| GET | `/delivery/mappings` | 列出平台品項對照 | admin/operator |
| POST | `/delivery/mappings` | 新增/更新對照（upsert）；目標二擇一：`product_id` 或 `menu_id`+`menu_item_id`（菜單品項對應，依 linked_products 扣庫存） | admin/operator |
| DELETE | `/delivery/mappings/<mid>` | 刪除對照 | admin/operator |
| GET | `/delivery/settings/<platform>` | 取得平台設定 | admin |
| PUT | `/delivery/settings/<platform>` | 更新平台設定 | admin |
| GET | `/delivery/store/` | 列出所有店家的外送設定 | admin |
| GET | `/delivery/store/<store_id>/settings/<platform>` | 取得指定店家平台設定 | admin |
| PUT | `/delivery/store/<store_id>/settings/<platform>` | 更新指定店家平台設定（mapping_template_id / item_mappings / store_id / vendor_code） | admin |
| GET | `/delivery/mapping-templates/` | 列出所有品項對應模板 | admin |
| POST | `/delivery/mapping-templates/` | 新增品項對應模板 | admin |
| PUT | `/delivery/mapping-templates/<tid>/` | 更新品項對應模板 | admin |
| DELETE | `/delivery/mapping-templates/<tid>/` | 刪除品項對應模板 | admin |

## `/invoice` — 電子發票

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

## `/log` — 操作紀錄

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/log/` | 列出紀錄（可篩：username/action/date）；觸發自動清理 | JWT |
| GET | `/log/stats` | 紀錄總數 + 超過 N 天的數量 | JWT |
| GET | `/log/export` | 匯出 CSV（streaming） | JWT |
| POST | `/log/import` | 批次匯入 CSV/JSON | admin |
| POST | `/log/cleanup` | 刪除 N 天前的紀錄 | admin |

## `/settings` — 系統設定

| 方法 | 路徑 | 說明 | Auth |
|------|------|------|------|
| GET | `/settings/` | 取得全部系統設定（key-value dict） | JWT |
| PUT | `/settings/` | 批次更新系統設定 | admin |
