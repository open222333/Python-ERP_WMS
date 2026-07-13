# Bug 修復 / 安全修復記錄

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
