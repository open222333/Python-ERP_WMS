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
| `/order?t=TOKEN` | 驗證 QR Token → 後端簽發 4 小時訪客 JWT → 自動載入菜單 |
| `/order?table=桌號` | 舊式 URL 相容，直接顯示點餐頁（需手動登入） |
| `/order`（無參數） | 顯示空白頁，不載入任何內容 |

訪客 JWT（`session_token`）僅存於 Vue 元件的記憶體變數，不寫入 `localStorage`，重整頁面後需重新掃碼。
