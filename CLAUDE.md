# Python-ERP_WMS — CLAUDE.md

Flask + MongoDB + Vue 3 的多店家 WMS / POS 系統。

## 制度引用（AI 協作規範）

本專案遵守 `~/Desktop/GitRepository/repo/Other-Note/00_其他(工具_應用程式_網站)/LLM(大型語言模型)/0_制度文件(規章制度)/` 之 A~M 制度文件。衝突序：F > C；token 事宜依 J；跨 session 交接依 K。

- 預設以 W（Sonnet 級）起手；升降級依 B 第 3、4 章
- 完成定義 = C 清單 2 全過；回報用 B 第 5 章格式
- 環境現狀一律引用文件 G，禁止重新探索環境

## 只讀邊界

預設允許讀取：`app/`、`src/`、`conf/`、`docs/`、`tests/`、`scripts/`、`frontend/src/`、根目錄設定檔。
其餘（`frontend-dist/`、`logs/`、`node_modules/`、`.env`、dump/備份檔）非經任務單（文件 D）指定不得讀取，詳見 `.claudeignore`。

## 技術棧指標

- **後端**：Flask Blueprint（`app/` 為 view 層、`src/models/` 為 model 層），JWT 認證，MongoDB + Redis（TableSession）
- **前端**：Vue 3 + Vite（`frontend/`），打包輸出至 `frontend-dist/`，由 nginx 靜態服務
- **API 基底路徑**：nginx 直接代理 `/warehouse/`、`/inbound/` 等，**無 `/api/` 前綴**（錯誤用 `/api/warehouse/` 會 404）
- `FLASK_ENV` 決定 Config：`production`（預設，DEBUG=False）/ `development` / `testing`

## 延伸文件

| 文件 | 內容 |
|---|---|
| `docs/ARCHITECTURE.md` | 模組一覽、資料庫關聯圖、Redis key、索引、實作備忘、k6/seed 測試工具 |
| `docs/API.md` | 全部 API 端點表（方法/路徑/說明/權限）。改動或新增 API 時同步更新 |
| `docs/PAGES.md` | 前端頁面路由與功能對照表 |
| `docs/FIXES.md` | Bug / 安全修復歷史記錄。這些問題已修復，勿重複回報 |
| `docs/OPTIMIZATION_REPORT.md` | 待處理的優化項目清單（P0-P2） |

## Build 與測試

| 情境 | 指令 |
|---|---|
| Docker 生產 | `docker compose build nginx && docker compose up -d nginx`（image 內跑 npm） |
| Docker Dev（快速迭代） | `nvm use 18 && cd frontend && npm run build`，再 `docker compose -f docker-compose.yml -f docker-compose.dev.yml restart nginx` |
| 本機熱更新（最快） | `python run.py`（Flask :5000）+ `cd frontend && npm run dev`（Vite :3000 自動 proxy） |
| 單元測試 | `python3 -m pytest tests/unit -q`（mongomock/fakeredis，無需真 DB；新增後端功能時同步加測試） |

## 專案級硬規則

- **多店家隔離**：資料隔離靠 `get_store_filter()` — 所有依 ID 讀寫的端點都必須帶 store_filter 驗證所有權（新增端點時務必檢查）
- **Flask route 順序**：`/batch` 必須在 `/<pid>` 之前，否則 `batch` 會被當作 pid
- **NAV_CONFIG**：`frontend/src/config/nav.ts` 是側欄與模板設定頁面的唯一資料來源；新增頁面只需在 nav.ts 加一筆（`AppSidebar.vue` 為廢棄空殼）
- 其餘實作備忘（IME/Vue Set/Docker volume/Vite cache 等）見 `docs/ARCHITECTURE.md`
