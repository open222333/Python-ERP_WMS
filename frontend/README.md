# WMS Frontend — Vue 3 + Vite + TypeScript

## 技術棧

| 項目 | 版本 |
|------|------|
| Vue  | 3.x  |
| Vite | 5.x  |
| TypeScript | 5.x |
| Vue Router | 4.x |
| Pinia | 2.x |
| Bootstrap | 5.3 |
| Axios | 1.x |

## 目錄結構

```
src/
├── api/          # Axios HTTP 客戶端（JWT 自動帶入 + refresh 攔截）
├── stores/       # Pinia：auth（登入狀態）、toast（通知）
├── router/       # Vue Router（history mode + 路由守衛）
├── types/        # TypeScript 介面定義
├── utils/        # 格式化工具（fmtDate, fmtMoney 等）
├── components/   # 共用元件（AppToast）
├── layouts/      # AdminLayout（側邊欄 + topbar）
└── views/
    ├── LoginView.vue
    ├── PosView.vue         # POS 收銀台
    ├── KitchenView.vue     # 廚房看板（免登入）
    ├── OrderView.vue       # 顧客點餐（QR 掃碼 / ?t=TOKEN）
    ├── QuickIoView.vue     # 快速出入庫
    └── admin/              # 後台管理頁面
        ├── DashboardView.vue
        ├── UsersView.vue
        ├── QrCodesView.vue # QR 碼桌號管理
        └── ...
```

## 本機開發

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
                 # /auth/* /pos/* 等 API 路徑自動代理到 http://localhost:5000（Flask）
```

Flask 同時啟動：
```bash
python run.py    # http://localhost:5000
```

> Vite 開發伺服器的 proxy 設定（`vite.config.ts`）負責將 API 請求轉發到 Flask，避免 CORS 問題。

## 部署（生產）

```bash
cd frontend
npm run build    # 輸出到 ../frontend-dist/
```

`frontend-dist/` 由 nginx 直接 serve 靜態檔案，API 請求透過 nginx `proxy_pass` 轉發到 Flask。

```bash
docker compose up -d
```

> `frontend-dist/` 目錄已在 `docker-compose.yml` 中掛載到 nginx 容器的 `/usr/share/nginx/html`，build 後重啟 nginx 即生效，無需重新 build Docker image。

## 路由結構

| 路徑 | 元件 | 需要登入 | 說明 |
|------|------|---------|------|
| `/login` | LoginView | ✗ | 後台登入 |
| `/admin/*` | AdminLayout + 子頁面 | ✓ | 後台管理 |
| `/pos` | PosView | ✓ | POS 收銀台 |
| `/quick-io` | QuickIoView | ✓ | 快速出入庫 |
| `/kitchen` | KitchenView | ✗ | 廚房看板（免登入） |
| `/order` | OrderView | ✗ | 顧客點餐（QR 掃碼） |

## 顧客點餐（OrderView）說明

| 進入方式 | 行為 |
|---------|------|
| `/order?t=TOKEN` | 驗證 QR Token → 後端建立 / 取回桌號 TableSession → 回傳 `session_token` → 自動載入菜單並建立 SSE 連線 |
| `/order?table=桌號` | 舊式 URL 相容，直接顯示點餐頁 |
| `/order`（無參數） | 顯示空白頁，不載入任何內容 |

**Session 生命週期**：`session_token` 存於 `localStorage`，重整頁面後自動恢復 SSE 連線。訂單狀態變為 `completed` 或 `cancelled` 時，後端關閉 Session，SSE 推播 `session_closed` 事件，頁面顯示「感謝光臨」全螢幕提示。

**即時更新（SSE）**：`GET /customer-order/customer-stream?token=<session_token>` 長連線；推播事件：
- `order_update`：訂單狀態變更，刷新我的訂單列表
- `session_closed`：Session 已關閉，切換至結束畫面

## 後台表單草稿保留

新增模式下（ProductsView、MenusView 的品項 / 分類 / 選項組），關閉 Modal 不儲存會自動保留已填寫的內容；再次點開「新增」時恢復草稿。儲存成功後自動清空，下次從空白開始。編輯模式（傳入既有資料）不受影響，永遠從現有資料載入。

## QR 碼管理（QrCodesView）

後台「QR 碼管理」頁除桌位 Token 管理外，亦整合桌況 Session 狀態：

| 欄位 | 說明 |
|------|------|
| **桌況 Session** 欄 | 顯示各桌目前是否有活躍 Session（顧客正在使用點餐頁），以及 Session 到期時間 |
| **結束 session** 按鈕 | 管理員可手動強制關閉指定桌的 Session，顧客端 SSE 即時收到 `session_closed` 事件並顯示「感謝光臨」提示（用於顧客離席但未結帳時） |
| 標題列統計 | 顯示「N 桌活躍中」綠色計數，一目了然全場使用狀況 |

**資料來源**：頁面載入時呼叫 `GET /customer-order/tokens`，後端同時回傳 `sessions` 欄位（各桌從 Redis 查詢的即時 TableSession 狀態）。關閉 Session 呼叫 `DELETE /customer-order/session/<table_no>`（需 operator+ 權限）。
