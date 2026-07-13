# 前端頁面功能

## 獨立頁面（無需登入 / 特殊）

| 路由 | 檔案 | 功能 |
|------|------|------|
| `/login` | `LoginView.vue` | 帳密登入，JWT access token（8h）+ refresh token（30d） |
| `/pos` | `PosView.vue` | POS 收銀台（PWA，橫向），支援 LINE Pay / ZPay / 現金 / 刷卡 |
| `/quick-io` | `QuickIoView.vue` | 快速出入庫，不走完整採購單流程，直接批次調整庫存 |
| `/kitchen` | `KitchenView.vue` | 備餐顯示（SSE 即時），無需登入 |
| `/order` | `OrderView.vue` | 顧客點餐頁（掃 QR 進入），session token 驗證桌號 |

## 後台頁面（`/admin/*`，需登入）

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
