# Bug 修復 / 安全修復記錄

## 2026-10-25 UI 第六輪（`[U1]`–`[U11]` 標記，項目見 OPTIMIZATION_REPORT 第六輪）

| 檔案 | 問題 | 修復說明 |
|---|---|---|
| `src/models/{pos,product,customer_order,invoice,delivery}.py`、對應 view、`components/LoadMore.vue`（新增）、`api/paging.ts`（新增） | [U3] 銷售紀錄、出入庫、顧客訂單、發票、外送訂單只顯示最新 N 筆，更早的資料在畫面上看不到；產品清單（快取、產品頁、菜單選品、快速出入庫）超過 1000 筆後被截斷 | 列表 API 加 `offset`（排序固定 `created_at, _id` 遞減，頁與頁不重疊）；各頁底部加「載入更多」。需要完整產品清單的地方改用 `fetchAllPages()` 逐頁取齊（上限 2 萬筆） |
| `app/product/view.py` `/product/export` | 匯出只含前 1000 個產品 | 改 `find_all(limit=0)` 取全部 |
| 8 個列表 API（product／pos／customer-order／order／inventory×2／delivery／invoice）、`app/log/view.py` | `?limit=0` 在 pymongo 等於「不限筆數」，可繞過上限一次撈全部；操作紀錄 API 完全沒上限 | 一律 `max(1, min(limit, 上限))`；操作紀錄上限 2000 |
| `frontend/src/views/admin/DeliveryOrdersView.vue` | 頁面使用的狀態值（pending 等）與後端（new／confirmed／preparing／ready／picked_up／delivered／cancelled）不符：狀態篩選永遠空白、操作按鈕一律回 400 | 依後端狀態重寫篩選與「下一步」按鈕，取消改用確認框，加分頁 |
| `frontend/src/utils/format.ts` 等 | [U4] 後端回傳不帶時區的 UTC 字串，部分頁面直接 `new Date()` 當本地時間解析，台灣時間差 8 小時 | 新增 `parseServerDate()`：無時區字串補 `Z`；`fmtDate`／`fmtDay` 與顧客訂單紀錄、設定頁清除時間、發票頁、出入庫日期統一使用 |
| 5 個設定／列表頁 | [U8] 深色模式下仍是白底（`bg-light`、`#f8f9fa`、淺色 badge） | 改用 Bootstrap 主題變數類別（`bg-body-tertiary`、`bg-body-secondary text-body`）與 CSS 變數 |
| `composables/useConfirm.ts`、`components/AppConfirm.vue`（新增）、`App.vue`、14 個頁面 | [U5] 26 處瀏覽器原生 `confirm()`、點餐頁 2 處 `alert()`：樣式無法控制、手機上體驗差、無法區分危險操作 | 全站共用確認框 `appConfirm()`／`appAlert()`；刪除、清除、退款、結束等操作確認鈕為紅色 |
| `plugins/modalEnhancer.ts`（新增）、`main.ts`、`style.css` | [U6] 自製彈窗（`.modal.d-block`、POS／點餐頁遮罩）不能按 Esc 關閉、開啟時背景仍可捲動、焦點留在背景 | 全域偵測開啟中的彈窗（含 v-show）：鎖背景捲動、焦點移入並於關閉後還原、Tab 限制在最上層彈窗、Esc 點其關閉鈕（無則觸發遮罩的 @click.self）。各頁不需修改 |
| `config/nav.ts` | [U1] 側欄「開啟收銀台」連 `/pos/`，被 nginx 轉給舊版 Flask 模板 | 改為 `/pos`（Vue 版） |
| 6 個搜尋框（產品、庫存、操作紀錄×2、外送模板×2、POS 商品） | [U2] 搜尋框無法一鍵清除 | 改 `type="search"` 使用原生清除鈕（`style.css` 統一外觀）；產品與操作紀錄清除後自動重新查詢；彈窗內搜尋框有字時 Esc 先清字、不關彈窗。Firefox 桌面版無原生「×」，但 Esc 可清除 |
| 13 個頁面 41 個按鈕 | [U7] 純圖示按鈕（編輯／刪除／移除／查詢等）沒有可讀名稱 | 補 `aria-label` 與 `title`；登入頁顯示密碼鈕依狀態切換文字 |
| `composables/useFieldErrors.ts`（新增）、`ProductsView.vue` | [U9] 表單錯誤只靠 3 秒就消失的 toast，看不出是哪一欄 | 新增欄位錯誤 composable；產品表單先套用（SKU、名稱必填，價格不可負，SKU 重複 409 標在 SKU 欄）。其他表單待逐步套用 |
| 刪除 `components/HelloWorld.vue`、`components/AppSidebar.vue`、`views/admin/InboundView.vue`、`OutboundView.vue` | [U11] 無引用的死檔 | 刪除；CLAUDE.md 的 AppSidebar 說明改為指向 `AdminLayout.vue` |

測試：`tests/unit/test_pagination.py`（offset 不重疊／超出範圍／負數、limit=0 不可不限、匯出不截斷）；彈窗增強器與確認框以 jsdom 驗證 13 項行為（開啟鎖定、焦點移入與還原、Tab 循環、Esc 關閉、v-show 遮罩、搜尋框 Esc、確認框 Promise）。

## 2026-10-24 後台與點餐頁手機版（`[MOBILE]` 標記）

| 檔案 | 問題 | 修復說明 |
|---|---|---|
| `frontend/src/layouts/AdminLayout.vue` | 側欄預設為展開，手機一進後台側欄就蓋住整個畫面；瀏覽器返回換頁時不會收起；側欄展開時背景仍可捲動 | 寬度 < 992px 預設收起、換頁自動收起、展開時鎖住背景捲動；側欄寬度不超過畫面 82%、選單項目加大；手機內容邊距縮小 |
| `frontend/src/directives/stackTable.ts`（新增）、`src/main.ts`、`src/style.css` | 後台列表在手機只能左右捲動表格 | 新增全域指令 `v-stack-table`：自動把表頭欄位名稱寫入每格 `data-label`，寬度 < 768px（僅螢幕，不影響列印）時每列改成卡片；列表變動自動重新標記。已套用到 18 個頁面共 36 個表格（不含已停用的 InboundView／OutboundView，MovementsView 已有專用卡片版） |
| `frontend/src/style.css` | 手機上工具列篩選欄位被頁面固定寬度撐開；輸入框小於 16px 時 iOS 聚焦會放大畫面；大型彈窗在手機上擠成一小塊 | 卡片頭工具列欄位平均分配寬度（覆寫固定寬度）；手機輸入框 16px；`modal-lg`／`modal-xl` 在手機改全螢幕且底部按鈕列固定 |
| `frontend/index.html`、`src/views/OrderView.vue` | 未設 `viewport-fit=cover`，`env(safe-area-inset-*)` 一律為 0，iPhone 底部橫條會擋住浮動購物車與按鈕；點餐頁購物車加減鈕只有 24px | 加上 `viewport-fit=cover`、body 左右安全區；點餐頁浮動購物車與底部操作列避開安全區；觸控裝置加減鈕 36px、輸入框 16px |

## 2026-10-24 多店隔離、電子發票、SSE 心跳、索引（`# [A2]` `# [A3]` `# [A4]` `# [A5]` `# [A6]` `# [A7]` `# [D3]` `# [D5]` 標記）

| 檔案 | 問題 | 修復說明 |
|---|---|---|
| `app/customer_order/view.py` | [D5] SSE 只在資料變動時寫出，客人關頁後偵測不到斷線，執行緒要等到該桌有變動或結帳才釋放；廚房串流不分店家 | 資料沒變時每 15 秒送 `: ping` 心跳，斷線時寫入失敗即結束迴圈；廚房串流依 ticket 內 store_ids 過濾 |
| `src/permissions.py` | [A2] 隔離邏輯散落、只有 4 個模組使用 | 新增 `store_filter_from_claims`、`is_hq`、`require_hq`、`store_allowed`、`allowed_store_ids`、`allowed_warehouse_ids`、`warehouse_allowed`；`get_store_filter` 支援指定欄位（如外送的 `store_ref`） |
| `app/inventory/view.py`、`app/common/order_views.py`、`app/analytics/view.py` | [A2] 庫存、異動、出入庫、儀表板不分店家：A 店可改 B 店庫存、確認／完成 B 店出入庫單 | 依倉庫所屬店家過濾與驗證；他店資料回 404 或空清單 |
| `app/delivery/views/*` | [A2] 外送訂單與店家設定不分店家；全域設定、品項對應、拉單、菜單同步任何店家 admin 都能改 | 訂單依 `store_ref` 過濾（未歸屬分店限總部）；全域設定、對應、模板、拉單、菜單同步限總部（403） |
| `app/log/view.py`、`src/models/log.py` | [A2][A6] 任何角色可看全部店家紀錄；關鍵字直接當正規表達式 | 店家帳號只看本店使用者的紀錄；關鍵字 `re.escape` 後才比對；匯入與清除限總部 |
| `app/invoice/view.py`、`src/models/invoice.py` | [A2] 發票不分店家；[A3] 先查再建無鎖、只擋 issued、`find_by_order` 不排序，可能重複開立；[A4] 開立／作廢永遠用全域金鑰，店家設定與機台覆寫無效 | 依店家過濾（舊發票由銷售單推得店家）；`active_order_id` 唯一索引＋開立中回 409，error／voided 後可重開；依店家（啟用且有商店代號）→ 全域回退＋機台覆寫決定金鑰，發票記錄 `store_id`／`terminal_id`／`merchant_id`，作廢須同一商店代號；設定有誤時不建立發票紀錄 |
| `src/invoice_providers/ecpay.py` | [D3] 品項用折扣前單價，合計 ≠ 發票金額；金額用 `int()` 捨去 | 依比例分攤（最大餘數法）使合計精確等於四捨五入後的發票金額，且數量 × 單價 = 金額皆為整數（無法整除時拆兩行）；2 萬筆隨機案例驗證 |
| `app/__init__.py`、`src/services/delivery_service.py` | [A5] 外送訂單無唯一索引，並發推播可建出兩筆；[A7] 常用查詢缺索引 | `delivery_orders(platform, external_order_id)` 部分唯一索引，建立撞鍵時改走既有單；補 `invoices`、`delivery_mappings`、`warehouse_locations`、`logs.created_at`、`stock_movements.created_at`、`system_settings.key`（unique，失敗降級）索引 |

測試：`test_sse_heartbeat.py`、`test_store_isolation_more.py`、`test_invoice.py`、`test_delivery_race.py`（新增 33 條；隔離 15 條在修改前的程式上全數失敗）。

## 2026-10-23 快速出入庫／庫存移動紀錄手機版（`// [MOBILE]` 標記）

| 檔案 | 問題 | 修復說明 |
|---|---|---|
| `frontend/src/config/nav.ts` | 側欄「快速出入庫」連到 `/quick-io/`（結尾斜線），經 nginx 送到舊版 Flask 模板，該頁強制橫向，手機直拿只顯示「請旋轉」；Vue 版 `/quick-io` 沒有入口 | 改連 `/quick-io`（Vue 版）；舊模板保留不刪 |
| `frontend/src/views/QuickIoView.vue`、`components/BarcodeScanner.vue`（新增） | 手機上無法掃條碼；按鈕小；iOS 長按不會觸發 contextmenu，無法開數量輸入 | 相機掃條碼（原生 BarcodeDetector 優先，不支援才動態載入 `@zxing/browser`，不影響其他頁打包大小）；掃描槍輸入＋Enter；手機版商品／清單分頁＋底部確認鈕、44px 觸控目標、輸入框 16px 防 iOS 放大；長按自行計時開數量視窗（含 +5/+10/+20/+50）；搜尋框清除鈕 |
| `frontend/public/quick-io.webmanifest`、`public/icons/quick-io-*.png`（新增） | 不能加入主畫面 | 本頁掛載時注入 manifest 與 iOS meta，離開時移除（不影響其他頁） |
| `frontend/src/views/admin/MovementsView.vue` | 讀取 `sku`／`before_quantity`／`after_quantity`，但後端欄位是 `product_sku`／`before_qty`／`after_qty`，**SKU 與調整前後一直是空白**；手機上只能左右捲動表格 | 改讀正確欄位；小螢幕改卡片、篩選列可收合 |
| `app/inventory/view.py`、`src/models/inventory.py` | 前端送出 `date_from`／`date_to`，**後端完全忽略，日期篩選沒有作用** | 支援日期區間（含當日），格式錯誤回 400；與其他列表相同以 UTC 日界線判斷（見 OPTIMIZATION_REPORT D4） |

## 2026-10-09 外送狀態轉換與銷售管道扣庫一致（`# [D1]` `# [D2]` 標記，OPTIMIZATION_REPORT 第四輪 D1、D2）

| 檔案 | 問題 | 修復說明 |
|---|---|---|
| `app/delivery/adapters/{__init__,ubereats,foodpanda}.py` | 平台狀態只轉小寫就存入（UberEats `CREATED`/`ACCEPTED`/`CANCELED`），與內部 `new`/`confirmed`/`cancelled` 對不上：新單狀態為未知值，後續更新全被靜默忽略，**平台端取消永遠不同步** | 各 adapter 加 `STATUS_MAP` 轉成內部狀態，原始值存 `platform_status`；無法辨識的值記 warning log。foodpanda 對照依本 adapter 既有用值＋常見別名，**需以實際 payload 核對補齊** |
| `src/constants.py`、`src/models/delivery.py` | 終態以外的轉移不設限（可倒退）；檢查與寫入非原子 | `DeliveryOrderStatus.is_valid_transition`：只能往前（可跳過）、非終態可取消；`DeliveryOrder.transition()` compare-and-set，並發時只有一方成功；修正前存入的未知狀態值視同 `new` |
| `src/services/delivery_service.py`（新增）、`app/delivery/views/{webhooks,orders,base}.py` | 銷售建立只在「手動或自動轉為 confirmed」時觸發；平台端接單、跳過 confirmed、拉單時已確認的訂單都不會建銷售扣庫；取消不回補 | 所有狀態變更入口統一經 service：由未接單進入已接單狀態 → 建銷售扣庫；已接單後轉 cancelled → 作廢銷售並回補。後台改為先驗證轉移合法才呼叫平台 API（非法 400、並發衝突 409） |
| `src/models/pos.py` `refund` | 退款以 `items[].product_id × quantity` 回補訂單倉庫，與結帳依 `linked_products` 扣庫不一致：`consume_qty>1` 少補、跨倉不補、`consume_inventory=False` 品項憑空多補 | 新增 `_restore_stock_by_ledger()`：依 `stock_movements` 把當初扣的原樣補回（冪等）；退款與外送取消共用 |
| `src/models/pos.py` `create_from_cust_order` | 掃碼點餐完成時完全不扣庫存 | 比照 POS 依菜單品項 `consume_inventory`／`linked_products` 扣庫（異動帳 `cust_order_sale`）；預設倉為本店倉庫；庫存不足不阻擋、記錄 `stock_skipped`；先寫銷售單再扣庫確保冪等 |
| `app/__init__.py` 索引 | `pos_delivery_order` 為 unique + **sparse** 複合索引：只要有任一欄位就收錄，掃碼點餐銷售（無 `delivery_order_id`）**從第 2 筆起撞重複鍵、銷售紀錄靜默漏建**；`bulk_import` 多筆同 source 同樣失敗 | 改為 `partialFilterExpression`（只限制有 `delivery_order_id` 的文件）；啟動時偵測舊 sparse 版本自動移除重建；新增 `pos_cust_order` partial 唯一索引防同一點單重複建銷售 |

## 2026-10-08 記憶體優化（`# [OPT-MEM]` 標記）

| 檔案 | 問題 | 修復說明 |
|---|---|---|
| `gunicorn.py`、`conf/config.ini.default` | 預設 `max(2, CPU*2+1)` workers × 2 threads，1 vCPU 主機為 3 程序（每程序約 80MB），且長時間執行記憶體碎片不釋放 | 預設改 `max(2, CPU+1)` × 4 threads（1 vCPU：2 程序 / 8 併發）；`max_requests=1000`＋`jitter=100` 定期回收 worker；`pre_fork` 呼叫 `gc.freeze()` 改善 copy-on-write 共享。實測（mongomock 下載入完整 app）RSS 合計 290MB → 221MB。全部可用 config.ini / `GUNICORN_*` 覆寫 |
| `src/models/log.py`、`app/log/view.py` | 操作紀錄匯出先整批轉 list 再串流；且 `find_all` 的 limit 夾在 1~10000，匯出傳 `limit=0` **實際只匯出 1 筆**（既有 bug） | 新增 `Log.iter_all()` 逐筆讀 cursor（batch 500），匯出不限筆數且記憶體用量固定；日期格式錯誤在串流開始前回 400 |
| `src/models/pos.py`、`app/pos/view.py` | 銷售匯出 `find_all(limit=0)` 把全部訂單（含完整 items）一次載入，實測每 1 萬筆約 57MB，隨資料量線性成長 | 新增 `PosOrder.iter_export()` 逐筆讀 cursor，projection 只取匯出欄位（items 僅 quantity），同時持有約 500 筆精簡文件（約 1MB）；CSV 輸出欄位與內容不變 |
| `src/models/delivery.py` | 外送訂單列表（最多 200 筆）每筆都帶完整平台原始 JSON `raw_payload`，前端完全未使用 | 列表 projection 排除 `raw_payload`；單筆詳情 `find_by_id` 保留完整資料 |
| `docker-compose.api.yml` | api 容器無記憶體上限（OPTIMIZATION_REPORT N8） | `deploy.resources` 上限 `${API_MEM_LIMIT:-512m}`、保底 `${API_MEM_RESERVATION:-128m}` |

## 2026-09-18 運維檢查後修復（對外 apidocs 曝露、容器日誌無上限）

| 檔案 | 問題 | 修復說明 |
|---|---|---|
| `src/__init__.py`、`app/__init__.py`、`conf/config.ini.default` | `/apidocs`（Swagger）對外公開無任何驗證，等同送出完整後台 API 路徑/參數/權限地圖 | 新增 `ENABLE_SWAGGER`：`FLASK_ENV=production` 時預設不初始化 `Swagger(app,...)`（`/apidocs`、`/apidocs/`、`/apispec_*.json` 皆回一般 404，非僅前端隱藏），開發/測試環境預設維持開啟；可用 `conf/config.ini` 的 `ENABLE_SWAGGER` 明確覆寫。`/` 根路由停用時改回傳簡短狀態 JSON，不再轉址 `/apidocs/`。測試：`tests/unit/test_apidocs_gate.py` |
| `docker-compose.{api,nginx,db}.yml`（新增 `conf/logrotate/wms-nginx`） | 容器日誌用預設 `json-file` driver 無上限，長期執行可能吃滿硬碟 | 四個服務（api/nginx/mongo/redis）加 `logging.options`（`max-size: 10m`、`max-file: 3`），效果等同主機層 `/etc/docker/daemon.json` 全域預設，但改為隨 repo 版控、不需重啟整個 Docker daemon。**注意**：nginx 的 access/error log 走 bind mount 直寫主機檔案（`./logs/nginx/*.log`），不經過此 driver，另補主機 logrotate 範本 `conf/logrotate/wms-nginx`（`copytruncate`，14 天保留） |

## 2026-07-08 交易一致性 / 可觀測性 / 熱點快取（`# [OPT-N1]` `# [OPT-N2]` `# [OPT-N3]` 標記）

| 檔案 | 問題 | 修復說明 |
|---|---|---|
| `src/mongo.py`、`src/services/order_service.py`、`src/models/{order_base,inbound,outbound,inventory,log,warehouse}.py` | 出入庫完成流程四步非交易寫入，中途失敗會不一致 | 新增 `supports_transactions()` 探測 + `get_client()`；`order_service` 支援時包 MongoDB transaction，不支援（standalone/mongomock）自動退回原順序寫入；相關 model 方法加可選 `session` 參數 |
| `docker-compose.db.yml`、`conf/config.ini.default` | MongoDB 為 standalone，無法支援 transaction/Change Streams | mongo 服務加 `--replSet rs0` + 冪等 `mongo-init` 容器；`.default` 註記連線字串需加 `?replicaSet=rs0`（需手動遷移，見 OPTIMIZATION_REPORT.md） |
| `app/__init__.py`（新增 `src/observability.py`） | 無 request 追蹤、無結構化日誌、無慢請求告警 | request-id 注入所有 log、`LOG_JSON=1` 結構化日誌、`SLOW_REQUEST_MS` 慢請求 warning（排除 SSE）、`SENTRY_DSN` 選配 Sentry |
| `app/customer_order/view.py`（新增 `src/cache.py`）、`app/menu/view.py` | 顧客掃碼點餐每次都查 menu+settings | menu payload Redis 快取 60 秒；menu 全部 15 個寫入端點成功後失效快取 |
| `frontend/src/api/*.js`（17 檔）、`frontend/src/stores/cache.js` | 前端殘留 .js，vue-tsc 型別檢查無法覆蓋 | 全數遷移 .ts（新增 `api/types.ts` 共用型別），邏輯不變。vue-tsc 0 錯誤、build 成功 |

## 2026-07-08 pydantic 驗證層批次（`# [REFACTOR]` 標記）

| 檔案 | 問題 | 修復說明 |
|---|---|---|
| `src/schemas/`（新增） | 無統一輸入驗證框架 | pydantic 型別/結構防線：`base.py`（ObjectIdStr、validate_payload、apply_coerced）+ `domain.py`（各領域 schema）。必填/業務檢查仍由既有手寫檢查負責，錯誤訊息不變 |
| `app/customer_order/view.py` | 公開建單端點 `float(price)` 對非數字拋 ValueError → 500 | schema 驗證插在兩段手寫檢查之間，畸形輸入回 400 |
| `app/common/order_views.py` | create 對非法 ObjectId 500；add/update_item 字串數量與 0 比較 TypeError → 500 | schema 驗證 + 數值轉型寫回，一處接入 inbound/outbound 兩邊生效 |
| `app/product/view.py`、`app/inventory/view.py`、`app/pos/view.py` | 同類型別漏洞 | create/update、adjust/batch、checkout 接入 schema 驗證 |
| `src/models/user.py` | `check_password(hash=None)` 拋 AttributeError（測試套件抓到） | except 補 AttributeError |
| `app/settings/view.py` | docstring YAML `{key: value}` 未加引號 → flasgger `/apispec_1.json` 500（既有 bug） | 加引號 |


## 2026-07-04 優化批次（修改處均有 `# [OPT]` / `// [OPT]` 註解）

| 檔案 | 問題 | 修復說明 |
|---|---|---|
| `app/warehouse/view.py` | IDOR：update/delete 未驗證店家所有權 | 先以 `find_by_id(wid, store_filter=get_store_filter())` 驗證，非本店回 404 |
| `app/menu/view.py` | IDOR：item/category/option-group 的 PUT/DELETE 共 6 端點未驗證菜單所有權 | 端點開頭以 store_filter 驗證 `mid`，仿照 add_item 既有寫法 |
| `run.py` | 預設帳號 admin/admin | 密碼改 `secrets.token_urlsafe(12)` 隨機產生並印出警告 |
| `app/__init__.py` | 缺索引 | 補 `users.username`（unique）、`products.sku`（unique）、`products.barcode`、`warehouses.code`、`stores.code`；unique 失敗自動降級非 unique，不中斷啟動 |
| `gunicorn.py` | workers 固定預設 2 | 預設改 `max(2, cpu*2+1)`，config/env 覆寫優先權不變 |
| `src/models/pos.py` + `app/pos/view.py` | 銷售報表 `limit=0` 撈全部訂單再 Python groupby | 新增 `PosOrder.summary()` aggregation（$group + $dateToString），輸出格式不變 |
| `app/inventory/view.py` | 庫存列表 N+1 逐筆查 product/warehouse | 新增 `find_by_ids()` 以 `$in` 批次查回建 dict 對照 |
| `app/product/view.py` | 匯入逐筆 `find_by_sku` | 新增 `find_by_skus()` 以 `$in` 批次查詢；保留同批重複 SKU 行為 |
| `app/outbound/view.py` + `src/models/outbound.py` | 列表缺 limit/offset 分頁（inbound 有） | 補齊與 inbound 一致：`limit ≤ 200`、offset、model 加 `.skip()` |
| `src/models/customer_order.py` | `find_active()` 無上限 | 加 `limit=500` 參數 |
| `app/pos/view.py` | ObjectId 轉換 `except Exception` 過寬 | 改 `except (InvalidId, TypeError)` |
| `app/customer_order/view.py`、`app/pos/view.py` | 多處無聲吞例外 | 補 logger.debug/warning 記錄，行為不變 |
| `src/models/user.py` | `check_password` 對格式錯誤 hash 拋例外 | 包 try/except 回 False |
| `app/log/view.py` | 匯入無單欄位大小限制 | 加 10000 字元上限，超過回 400 |
| `src/models/store.py` | `_next_code()` 迴圈逐筆查詢 | 改一次查詢取最大序號 +1，並正確處理 S999→S1000 |
| `app/inventory/view.py` | 批次錯誤只回拼接字串 | 保留 message，加 `errors` 陣列 |
| `app/sample/` | 死程式碼（blueprint 未註冊） | 整個目錄刪除 |
| `requirements.txt` | 部分套件 `>=` 未鎖版本 | 鎖定 cryptography、python-dotenv、flask-limiter、gunicorn |
| `frontend/src/api/index.ts` | 生產環境 console.debug 輸出（含 token 前綴） | 包 `import.meta.env.DEV` |
| `frontend/src/views/KitchenView.vue` | `v-for :key` 用索引，SSE 更新 DOM 錯位 | 改 `itemKey()`/`custKey()` 穩定 key |
| `frontend/src/views/admin/MenusView.vue` | 深層 watch 大物件 | 移除 `deep: true`，改 watch `selectedItemIds.length` + items getter，行為等價 |
| `frontend/src/views/admin/DashboardView.vue` | 重複 fetch products/warehouses | 改用 cache store（computed 保持響應性） |

## 早期修復

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
