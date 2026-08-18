# 專案優化分析報告

> 產出日期：2026-07-04。涵蓋後端效能、安全性、程式碼品質、前端效能四個面向。
> CLAUDE.md「Bug 修復記錄」中已修復的問題不在此列。

## 修復狀態（2026-07-05 更新）

**定點修復（2026-07-04）**：本報告所有定點問題已修復，修改處以 `# [OPT]` / `// [OPT]` 標記，詳見 `docs/FIXES.md`。

**大型重構已完成（2026-07-05，修改處以 `# [REFACTOR]` / `// [REFACTOR]` 標記）**：

| 項目 | 成果 |
|---|---|
| 單元測試套件 | `tests/unit/` 共 14 檔、139 tests（137 passed + 2 skip）。執行：`python3 -m pytest tests/unit -q`。mongomock 取代 MongoDB、fakeredis 取代 Redis。2 個 skip 係 mongomock 不支援 `$dateToString onNull` |
| 狀態常數化 | `src/constants.py`：OrderStatus / CustomerOrderStatus / PosOrderStatus / DeliveryOrderStatus / InvoiceStatus + 合法轉移表。app/、src/ 共 84 處替換；delivery adapters 傳給外部平台的字串刻意不動 |
| inbound/outbound 合併 | `src/models/order_base.py`（共用基類）+ `app/common/order_views.py`（共用 handler）+ `src/services/order_service.py`。url_map 與 swagger docstring 前後 byte-identical。附帶強化：OutboundOrder.complete 改原子轉移（原有並發雙重完成競態） |
| POS Service 層 | `src/services/pos_service.py`（checkout/refund）。view 646 行（-163）。注意：service 依賴 request context（get_jwt），非 HTTP 情境呼叫需先注入 claims |
| SSE 一次性 ticket | `POST /customer-order/stream-ticket`（TTL 30s，Redis GETDEL 一次性）+ `src/models/sse_ticket.py`；KitchenView 改自管重連（3s，取新 ticket 重建）。舊 `?token=` JWT 路徑保留為 deprecated 過渡 |
| PosView 拆分 | 1649 → 328 行。`frontend/src/components/pos/` 9 檔（含 usePosPayment composable）。vue-tsc 0 錯、build 成功 |

## 未完成項目與未來調整細項

### 1. ~~pydantic 驗證層~~（✅ 2026-07-08 完成）

- `src/schemas/base.py`：`ObjectIdStr` / `LooseObjectIdStr`（空值放行給手寫必填檢查）、`validate_payload()`（錯誤回 `{'success': False, 'message', 'errors': [{'field','message'}]}` 400）、`apply_coerced()`（轉型寫回原 dict）
- `src/schemas/domain.py`：InOutOrder / CustomerOrder / Product / Inventory / PosCheckout schemas。原則：**只驗型別與結構、欄位全 Optional**，必填與業務規則留給既有手寫檢查（原錯誤訊息不變）
- 已接入：customer_order 顧客建單（插在兩段手寫檢查之間，封掉 `float(price)` 500 crash）、order_views create/add_item/update_item（封掉非法 ObjectId 500 與字串數字比較 TypeError）、product create/update、inventory adjust/batch、pos checkout
- 測試：`tests/unit/test_schemas.py` 9 tests；全套 148 tests 綠。pydantic==2.13.4 已入 requirements.txt
- **後續可收緊**（目前為不破壞相容的最鬆驗證）：欄位改必填並統一移除手寫檢查（需同步前端錯誤處理）、qty/price 加範圍上限、status 欄位以 constants 枚舉驗證

### 1b. 同批完成的小收尾（2026-07-08）
- `app/settings/view.py:35` flasgger YAML bug 已修（`/apispec_1.json` 恢復可用，建議部署後開 `/apidocs` 確認）
- `docs/API.md` 已補 `POST /customer-order/stream-ticket` 與 `/stream` 認證方式變更

### 2. SSE 改 MongoDB Change Streams（被基礎架構阻擋）
- 前置條件：MongoDB 需 replica set。現行 docker-compose 為 standalone（已查證無 replSet 設定）
- 若要做：mongo 服務加 `--replSet rs0` + 初始化 `rs.initiate()` + 連線字串加 `?replicaSet=rs0`，再把 `app/customer_order/view.py` 兩個 stream 的 2 秒輪詢改 `collection.watch()`
- 現況可接受：輪詢已有 hash 去重與 find_active limit=500，低優先

### 3. 大列表虛擬滾動（依原判準延後）
- 觸發條件：單列表資料 >1000 筆才做。標的：ProductsView、MovementsView、LogsView。建議 `vue-virtual-scroller`。目前有分頁，非急迫

### 4. 收尾與部署注意（下次調整時處理）
- `docs/API.md` 待補：`POST /customer-order/stream-ticket`；`GET /customer-order/stream` 認證改 ticket、`?token=` 標 deprecated；前端全面換版後可移除舊路徑（搜 `# [REFACTOR]` deprecated 標記）
- **既有 bug（非本次造成，未修）**：`app/settings/view.py:35` swagger docstring 的 `{key: value}` 未加引號 → `/apispec_1.json` 整體 500。修法：該行加引號即可
- requirements.txt 尚未加 pydantic（驗證層未做）；新鎖版本（cryptography==44.0.1 等）建議乾淨環境 `pip install -r` 驗證
- 部署前檢查：`python3 -m pytest tests/unit -q` 全綠 → `k6 run tests/k6/smoke.js` → 人工點 POS 報表頁（sales_summary 已改 aggregation）與廚房頁（SSE ticket 新流程）→ 首次啟動記下隨機 admin 密碼（run.py 只印一次）
- 沙箱曾在 `frontend/node_modules/@esbuild/` 補 linux-arm64 binary 供驗證 build，未動 package.json/lockfile；本機 `npm ci` 會自動清掉，無需處理
- 監控留意：POS 結帳/退款的 log 改以 `src.services.pos_service` logger 名稱輸出（訊息文字不變）
- 行為強化點（已測試覆蓋，留意即可）：OutboundOrder.complete 原子化；`OutboundOrder.find_by_id` 對非法 ObjectId 仍拋例外（維持原行為，未順手改 404——未來可統一）
- 測試維護：新增後端功能時同步加 tests/unit 測試；aggregation 相關測試受 mongomock 限制可 skip 並註明

## 新一輪優化盤點（2026-07-08）

**已完成（N1-N3，`# [OPT-N1]` / `# [OPT-N2]` / `# [OPT-N3]` 標記）**：

| # | 項目 | 成果 |
|---|---|---|
| N1 | 交易一致性 | `src/mongo.py` 新增 `supports_transactions()`（探測 replica set 能力，程序生命週期內快取一次；mongomock/standalone 自動偵測為 False）+ `get_client()`。`src/services/order_service.py` 的 `_run_complete()` 支援時把「狀態轉移→庫存調整→movement→log」四步包進 MongoDB transaction（中途例外自動 abort，退回重試非交易路徑一次）；不支援時直接走原順序寫入，行為完全一致。相關 model 方法（`OrderBase.complete`、`Inventory.adjust`、`StockMovement.create`、`Log.create`、`Warehouse.find_by_id`）加 `session=None` 可選參數，向下相容。`docker-compose.db.yml` 新增 `--replSet rs0` 與冪等的 `mongo-init` 一次性初始化容器；`conf/config.ini.default` 註記連線字串需加 `?replicaSet=rs0`。**未動使用者本機 `conf/config.ini`**（gitignored 的實際部署設定，避免在使用者未執行遷移步驟前默默改變連線行為導致連不上）。測試：`tests/unit/test_order_service_transaction.py`（探測快取、session 全路徑透傳、交易失敗自動 fallback 仍完成） |
| N2 | 可觀測性 | `src/observability.py`：request-id（沿用/產生 `X-Request-ID`，注入所有 log record）、結構化 JSON 日誌（`LOG_JSON=1`）、慢請求記錄（`SLOW_REQUEST_MS` 預設 1000ms，排除 SSE `/stream` 路徑）、Sentry 選配（`SENTRY_DSN` 有值才載入，未安裝套件不中斷啟動）。`app/__init__.py` 一行 `init_observability(app)` 掛載。測試：`tests/unit/test_observability.py` |
| N3 | 熱點快取 | `src/cache.py`（`cached_json`/`invalidate`，Redis 故障一律 fallback 直接執行，不影響點餐主流程）。`GET /customer-order/menu` 的 menu payload 快取 60 秒（QR token 驗證與 session token 發放不快取，每請求照跑）。`app/menu/view.py` 全部 15 個寫入端點（create/update/delete menu、item、category、option-group、import-all、import）成功後呼叫失效。測試：`tests/unit/test_menu_cache.py`（快取命中、更新/新增失效、Redis 故障 fallback） |

**部署前置動作（N1 需要，非自動生效）**：現有 standalone MongoDB 部署要啟用交易保護，需：① `docker compose up -d mongo mongo-init` 讓 replica set 初始化 ② 手動把 `conf/config.ini` 的 `MONGO_URI` 加上 `?replicaSet=rs0` ③ 重啟應用。未執行這些步驟不影響現狀（自動 fallback），只是沒有交易保護。

**N4 前端 JS→TS（✅ 2026-07-08 完成）**：`frontend/src` 全部 17 個 .js 檔（`stores/cache.js`、`api/client.js` 與其餘 15 個 `api/*.js`）遷移為 .ts，內容邏輯逐字不變，僅補參數型別（新增 `api/types.ts` 共用型別：`Params`/`Data`/`Id`，刻意用 `Record<string, any>` 而非為每個端點手刻精確 interface，避免與後端 shape 不同步）。`tsconfig` 未設 `allowJs`，無需改動。`npx vue-tsc --noEmit` exit 0（零錯誤）、`npm run build` 成功。至此前端已無 .js 檔，vue-tsc 型別檢查全覆蓋。

**所有 N1-N4 項目已全數完成。**

## 第三輪盤點（2026-07-10，新發現，均已驗證非重複）

| # | 項目 | 說明 |
|---|---|---|
| N5 | 死程式碼／未用套件 | `src/mysql.py`（PyMySQL 連線池）全專案無任何 import；`requirements.txt` 的 `fake-useragent`、`opencv-python-headless`（~90MB）、`PyMySQL` 三個套件同樣無任何 import。專案純用 MongoDB（CLAUDE.md 從未提及 MySQL），這是留下的樣板殘留，拖慢 build 並放大 image 體積。建議：刪除 `src/mysql.py`、`conf/config.ini(.default)` 的 `[MYSQL]` 區段、三個套件 |
| N6 | 無健康檢查端點與容器 healthcheck | 專案無 `/health`／`/healthz` 端點；`docker-compose.api.yml`／`docker-compose.nginx.yml` 的 api、nginx、redis 服務都沒 healthcheck（只有 N1 新增的 mongo 有），`depends_on` 也沒用 `condition: service_healthy`，服務未就緒時仍可能被路由進來（nginx → api 502） |
| N7 | nginx 安全 headers 不完整 | `conf/nginx/conf.d/default.conf.{cloudflare,https-letsencrypt}.template` 的 HSTS header **已寫好但被註解掉**；全站缺 X-Frame-Options / X-Content-Type-Options / Referrer-Policy。已驗證閒置的靜態資源快取、gzip 皆正確，僅安全 header 這塊缺 |
| N8 | api 容器無資源限制 | `docker-compose.api.yml` 的 api 服務沒有 `deploy.resources`（mongo/redis 都有），單一服務異常吃記憶體會拖垮同機資料庫容器 |
| N9 | 死的日誌檔設定 | `src/__init__.py` 的 `LOG_PATH`（建立 `logs/` 資料夾）與對應的 docker volume mount，目前完全沒有 FileHandler 寫入——gunicorn 的 `accesslog/errorlog='-'` 輸出到 stdout（Docker 慣例，這部分正確），但 `logs/` 資料夾本身從未被使用，屬死設定，可清除或補上實際用途 |
| N10 | 金流／webhook 模組零測試覆蓋（**delivery 部分已完成 2026-07-17**） | ~~`delivery`~~ 已補 `tests/unit/test_delivery.py` 22 條（webhook 歸屬/自動接單、對應解析三層順序、linked_products 跨倉扣庫存、庫存不足、防重複、API 權限），並同批完成 view 拆分（`app/delivery/views/` 套件）與菜單品項對應功能。**尚缺**：`invoice`（598 行 view + 132 行 model，ECPay 電子發票開立/作廢）、`analytics`（240 行，儀表板統計）仍無測試，invoice 涉稅務合規，風險最高 |

**查證後排除的疑似項目**（避免誤導，記錄於此供参考）：
- ~~JWT secret（`conf/flask.json`）被提交進 git~~ — 已用 `git ls-files` 與 `git check-ignore` 驗證，該檔案有被 `conf/.gitignore` 正確排除，**不是真實問題**
- ~~OrderView SSE 事件監聽未清除造成記憶體洩漏~~ — 已讀原始碼確認：重連前已呼叫 `sseConn.close()` 並釋放參考，舊物件連同其 listener 可被 GC，**不是真實問題**
- PosView 缺 `onUnmounted` 空樁 — 純風格建議，非缺陷，未列入

**Backlog（依價值排序，未排程）**：

- **B1 CI/CD**：GitHub Actions 跑 pytest + vue-tsc + build（測試保護網自動化，最高價值）
- **B2 公開端點 rate limit**：`POST /customer-order/`、webhook 無限流，惡意灌單風險
- **B3 MongoDB 備份**：mongodump cron + 保留策略（生產必備）
- **B4 nginx 靜態資源**：gzip/brotli、frontend-dist cache headers（檔名已 hash 可長快取）
- B5 E2E 測試：Playwright 跑 POS 結帳、掃碼點餐流程
- B6 依賴弱點掃描：pip-audit / npm audit 進 CI
- B7 swagger docstring 抽 YAML：view 檔案大半行數是文件
- B8 驗證層收緊 / Change Streams / 虛擬滾動（見前述章節）

**經查證不需修**：
- CORS：Flask 預設不回 CORS header，跨來源 JS 本就無法讀取回應，且前後端同源部署，非漏洞
- menu export-all N+1：實查無逐筆查詢，僅 1 次 DB 查詢
- 日期時區混用：全專案已統一 `utcnow()`

## P0 — 高優先（建議立即修復）

### 安全性

| # | 問題 | 位置 | 說明 |
|---|------|------|------|
| S1 | **IDOR：倉庫更新/刪除無店家隔離** | `app/warehouse/view.py:47-73` | `update_warehouse` / `delete_warehouse` 未用 `get_store_filter()` 驗證所有權，知道 ID 即可改/刪別店倉庫。對比：GET 端點有正確過濾 |
| S2 | **IDOR：菜單品項/分類編輯無店家驗證** | `app/menu/view.py:390-496` | `update_item` / `delete_item` / `update_category` / `delete_category` 未先驗證 `mid` 屬於當前店家。對比：`add_item`（:375）有檢查 |

### 後端效能

| # | 問題 | 位置 | 說明 |
|---|------|------|------|
| B1 | POS 報表在 Python 端統計 | `app/pos/view.py:775-820` | `sales_summary` 以 `limit=0` 撈全部訂單再用迴圈 groupby，應改 MongoDB aggregation（`$group`/`$sum`） |
| B2 | `users.username` 無索引 | `src/models/user.py:48` | 每次登入都全表掃描，應建 unique index |
| B3 | 庫存列表 N+1 查詢 | `app/inventory/view.py:52-64` | 逐筆查 product/warehouse 名稱，應改 `$lookup` 或 `$in` 批次查詢 |

### 程式碼品質

| # | 問題 | 位置 | 說明 |
|---|------|------|------|
| Q1 | inbound/outbound 300+ 行重複 | `app/inbound/view.py`、`app/outbound/view.py`（各 471 行） | 10 個端點結構完全相同，僅文案不同。抽共用工廠函式/基類 |
| Q2 | 無 schema 驗證層 | 全 `app/` 70+ 處 | 手寫 `request.get_json().get()` 鏈，建議導入 pydantic 統一驗證 |

### 前端效能

| # | 問題 | 位置 | 說明 |
|---|------|------|------|
| F1 | KitchenView `v-for :key` 用索引 | `KitchenView.vue:187,191` | SSE 更新時 DOM 錯誤復用，廚房畫面閃爍/資料錯位。改用穩定 ID 作 key |
| F2 | 生產環境 console.debug | `frontend/src/api/index.ts:13-16` | 每個 API 呼叫都輸出 log（含 token 前綴），包 `import.meta.env.DEV` 判斷 |

## P1 — 中優先

**安全性**
- 無 CORS 設定（`app/__init__.py`），建議應用層明確設定允許來源
- SSE 端點 JWT 走 query string（`app/customer_order/view.py:264-276`），token 會進 nginx log；考慮短期一次性 token
- 啟動時建立預設帳號 `admin/admin`（`run.py:40-46`），改為隨機密碼並印出

**後端效能**
- `products.sku` / `products.barcode` 無索引（`src/models/product.py:183,194`）；sku 應為 unique
- 產品匯入逐筆 `find_by_sku`（`app/product/view.py:253`），改 `$in` 批次
- `CustomerOrder.find_active()` 無 limit（`src/models/customer_order.py:101`）
- gunicorn 預設 workers=2/threads=2，依核心數調整
- menu export-all 逐筆重查（`app/menu/view.py:241`）

**程式碼品質**
- ⚠️ **outbound 列表分頁疑似缺失/未定義變數**（`app/outbound/view.py:46-48`）— 修復前先驗證
- 狀態字串 magic string 89 處，建 `OrderStatus` 常數 + 合法轉移表
- `except Exception: pass` 無聲吞錯（`app/customer_order/view.py:174,275,294,401,414,474`、`app/pos/view.py:377,450`）
- ObjectId 驗證不一致：pos 未 import `InvalidId`（`app/pos/view.py:449`）
- View 層混入業務邏輯（inbound complete、pos checkout 400+ 行），建議抽 Service 層
- 錯誤回傳格式不一致（errors 字串拼接 vs 陣列）
- 無單元測試（tests/ 只有 k6）

**前端效能**
- MenusView 深層 watch（`MenusView.vue:127`），移除 `deep: true`
- PosView 1400+ 行，拆為 Topbar / ProductPanel / CartPanel / PaymentModal / CustomizeModal

## P2 — 低優先

- `check_password` 對格式錯誤 hash 會拋例外（`src/models/user.py:139`），包 try/except 回傳 False
- log import 無單欄位大小限制（`app/log/view.py:189-248`）
- `warehouses.code` / `stores.code` 無索引
- `Store._next_code()` 迴圈逐筆查詢（`src/models/store.py:29`）
- SSE 輪詢固定 2 秒，可考慮 MongoDB Change Streams
- `app/sample/` 死程式碼（未註冊 blueprint），可刪除
- requirements.txt 部分套件未鎖版本（cryptography、python-dotenv、flask-limiter）
- DashboardView 未使用 cache store 快取 products/warehouses
- 大列表無虛擬滾動（資料量 >1000 時再處理）

## 已驗證安全的部分

Product regex 已 `re.escape()`、webhook 用 `hmac.compare_digest()`、bcrypt 密碼雜湊、登入 rate limit、帳號鎖定檢查、設定白名單、庫存原子扣減、inbound/outbound complete race condition 修復——均確認到位。前端 router code splitting、Pinia、Vite manualChunks、SSE/timer 清理均正確。
