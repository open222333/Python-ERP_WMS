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
    ├── KitchenView.vue     # 備餐顯示
    ├── OrderView.vue       # 顧客點單
    ├── QuickIoView.vue     # 快速出入庫
    └── admin/              # 後台管理頁面
        ├── DashboardView.vue
        ├── UsersView.vue
        └── ...
```

## 本機開發

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
                 # /api/* 自動代理到 http://localhost:5000（Flask）
```

Flask 同時啟動：
```bash
python run.py    # http://localhost:5000
```

## 部署（生產）

```bash
cd frontend
npm run build    # 輸出到 ../dist/
```

`dist/` 由 Nginx 靜態 serve，`/api/*` 反向代理到 Flask。

```bash
docker-compose up -d
```

## API 路由對應

所有 Flask API 都加了 `/api` 前綴：

| Vue 呼叫 | Flask Blueprint |
|----------|-----------------|
| `/api/auth/*` | app_auth |
| `/api/user/*` | app_user |
| `/api/product/*` | app_product |
| `/api/inventory/*` | app_inventory |
| `/api/pos/*` | app_pos |
| ... | ... |

## 路由結構

| 路徑 | 元件 | 需要登入 |
|------|------|---------|
| `/login` | LoginView | ✗ |
| `/admin/*` | AdminLayout + 子頁面 | ✓ |
| `/pos` | PosView | ✓ |
| `/quick-io` | QuickIoView | ✓ |
| `/kitchen` | KitchenView | ✗ |
| `/order` | OrderView | ✗ |
