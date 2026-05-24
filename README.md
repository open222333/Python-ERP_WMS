# WMS 倉儲管理系統

基於 Flask + MongoDB 建置的倉儲管理系統（WMS），整合 POS 收銀、分析報表、外送平台串接，提供從倉儲入出庫到前台銷售的完整業務流程。

- **後台管理**：JWT 認證 + 角色權限（admin / operator / cashier / viewer）
- **產品管理**：分類、SKU 自動生成、EAN-13 條碼、成本/售價、庫存警示
- **倉庫管理**：多倉庫、貨架位置、倉庫代碼自動生成（WH-XXX）
- **庫存管理**：即時查詢、盤點調整、低庫存 / 超量警示
- **入庫單**：建立 → 確認 → 完成（自動入帳庫存）+ 條碼掃描新增品項
- **出庫單**：建立 → 確認（自動驗證庫存）→ 完成（自動扣減）+ 條碼掃描
- **庫存移動紀錄**：完整異動歷史
- **POS 收銀**：觸控友善 UI（PWA 橫向鎖定）、現金/刷卡/混合付款、找零、印收據、退款管理
- **分析報表**：日 / 週 / 月 / 年度用量與毛利、庫存警示儀表板
- **外送平台**：串接 UberEats（OAuth2）與 foodpanda（API Key）— 即時訂單推播（Webhook）+ 主動拉取 + 菜單同步
- **Swagger UI**：自動產生 API 文件
- **Docker 部署**：一鍵啟動

測試環境：Python 3.11

---

## 目錄

- [專案結構](#專案結構)
- [快速開始（本機）](#快速開始本機)
- [Docker 部署](#docker-部署)
- [API 端點總覽](#api-端點總覽)
- [業務流程說明](#業務流程說明)
- [角色與權限](#角色與權限)
- [設定檔說明](#設定檔說明)
- [MongoDB Collections](#mongodb-collections)
- [注意事項](#注意事項)

---

## 專案結構

```
Python-ERP_WMS/
├── run.py                              # 啟動入口（自動產生 SECRET_KEY、建立預設 admin）
├── requirements.txt
├── Dockerfile
├── docker-compose.yml.default
├── .env.default
│
├── app/                                # Flask 應用程式（Blueprint 模組）
│   ├── __init__.py                     # 初始化、JWT / Swagger、藍圖註冊
│   ├── auth/view.py                    # POST /auth/login  GET /auth/me
│   ├── user/view.py                    # 使用者 CRUD（admin）
│   ├── admin/view.py                   # GET /admin/ → 後台 UI
│   ├── log/view.py                     # GET /log/ → 操作紀錄
│   ├── product/view.py                 # 產品分類 + 產品 CRUD + 條碼查詢
│   ├── warehouse/view.py               # 倉庫 + 倉庫位置 CRUD
│   ├── inventory/view.py               # 庫存查詢、盤點調整、移動紀錄
│   ├── inbound/view.py                 # 入庫單管理
│   ├── outbound/view.py                # 出庫單管理
│   ├── analytics/view.py               # 分析報表 + 庫存警示
│   ├── pos/view.py                     # POS 收銀（銷售、退款、日結報表）
│   ├── delivery/                       # 外送平台整合
│   │   ├── view.py                     # Webhook + 訂單 + 菜單 + 設定端點
│   │   └── adapters/
│   │       ├── ubereats.py             # UberEats Marketplace API client
│   │       └── foodpanda.py            # foodpanda Vendor API client
│   └── templates/
│       ├── admin/index.html            # 後台管理 SPA（Bootstrap 5）
│       └── pos/index.html              # POS 收銀 PWA（橫向鎖定）
│
├── conf/
│   ├── config.py                       # Flask Config 類別
│   ├── config.ini.default              # 設定範本 ← 複製為 config.ini
│   ├── flask.json.default              # SECRET_KEY 範本 ← 複製為 flask.json
│   └── nginx/
│       ├── nginx.conf                  # nginx 主設定（worker、gzip、log 格式）
│       └── conf.d/
│           ├── default.conf            # 生效站台設定（HTTP only，本機 / Docker 均可用）
│           └── default.conf.https-example  # HTTPS 範本（啟用域名時複製覆蓋 default.conf）
│
└── src/
    ├── __init__.py                     # 全域設定參數（含外送平台設定讀取）
    ├── mongo.py                        # MongoDB singleton
    ├── permissions.py                  # @require_role 裝飾器
    └── models/
        ├── user.py                     # 使用者（bcrypt）
        ├── log.py                      # 操作紀錄
        ├── product.py                  # ProductCategory、Product
        ├── warehouse.py                # Warehouse、WarehouseLocation
        ├── inventory.py                # Inventory、StockMovement
        ├── inbound.py                  # InboundOrder（含 embedded items）
        ├── outbound.py                 # OutboundOrder（含 embedded items）
        ├── pos.py                      # PosOrder（POS 銷售單）
        └── delivery.py                 # DeliveryOrder、DeliveryMapping、DeliverySettings
```

---

## 快速開始（本機）

### 前置需求

- Python 3.11+
- MongoDB（本機或遠端，預設 `localhost:27017`）

### 步驟一：複製設定檔

```bash
cp conf/config.ini.default conf/config.ini
cp conf/flask.json.default conf/flask.json
```

> `flask.json` 的 `SECRET_KEY` 留空即可，`run.py` 啟動時會自動產生並寫入。

### 步驟二：設定 MongoDB 連線

編輯 `conf/config.ini`，調整 MongoDB 連線資訊：

```ini
[SETTING]
ADMIN_TITLE=WMS 倉儲管理系統

[MONGO]
MONGO_URI=mongodb://localhost:27017
MONGO_DB=wms
```

> 資料庫名稱建議設為 `wms`，系統會在首次使用時自動建立所需 collection。

### 步驟三：安裝套件

```bash
pip install -r requirements.txt
```

### 步驟四：啟動服務

```bash
python run.py
```

首次啟動會自動輸出：

```
[init] 已自動產生 SECRET_KEY 並寫入 conf/flask.json
[init] 已建立預設帳號 admin / admin，請登入後台後立即修改密碼
```

### 步驟五：開啟後台

> 本機開發模式不含 nginx，直接連 Flask。

| 服務 | 網址 |
|---|---|
| **後台管理** | http://127.0.0.1:5000/admin/ |
| **POS 收銀** | http://127.0.0.1:5000/pos/ |
| Swagger UI | http://127.0.0.1:5000/apidocs |
| 健康檢查 | http://127.0.0.1:5000/ |

預設帳號：`admin` / `admin`　**→ 請立即登入修改密碼**

### 環境變數（選用）

可建立 `.env` 或直接匯出：

| 變數 | 說明 | 預設值 |
|---|---|---|
| `FLASK_PORT` | Flask 內部埠號（本機直接存取用） | `5000` |
| `JWT_ACCESS_TOKEN_EXPIRES_HOURS` | Token 有效時數 | `8` |

> macOS 的 AirPlay Receiver 預設佔用 port 5000，本機開發建議改為 `FLASK_PORT=5001`。

---

## Docker 部署

架構：`nginx（對外）→ app（Flask）→ mongo（MongoDB）`

```
使用者 → nginx:80 → Flask:5000 → MongoDB:27017
```

### 步驟一：準備設定檔

```bash
cp docker-compose.yml.default docker-compose.yml
cp .env.default .env
cp conf/config.ini.default conf/config.ini
cp conf/flask.json.default conf/flask.json
```

### 步驟二：調整 .env

```env
APP_PORT=80          # nginx 對外 port（使用者實際連線的 port）
FLASK_PORT=5000      # Flask 內部 port（容器內 nginx → app 通訊用，不對外）
JWT_ACCESS_TOKEN_EXPIRES_HOURS=8
```

> `FLASK_PORT` 在 nginx 架構下僅影響容器內部通訊，不影響對外網址。

### 步驟三：調整 config.ini（MongoDB 主機名稱）

```ini
[SETTING]
ADMIN_TITLE=WMS 倉儲管理系統

[MONGO]
MONGO_URI=mongodb://mongo:27017
MONGO_DB=wms
```

### 步驟四：首次啟動（建置 image）

```bash
docker compose up -d --build
```

> 首次啟動需要 `--build` 以建置 Flask image。之後若只修改 Python / HTML 程式碼，**不需重新 build**，直接重啟即可：
>
> ```bash
> docker compose restart app
> ```
>
> 只有異動 `requirements.txt` 或 `Dockerfile` 時，才需要再加 `--build`。

### 服務一覽

| 服務 | 映像 | 對外 Port | 說明 |
|---|---|---|---|
| `nginx` | nginx:1.26-alpine | `APP_PORT`（預設 80） | 反向代理，對外唯一入口 |
| `app` | 本地建置 | 僅內部 5000（不對外） | Flask WMS API |
| `mongo` | mongo:7 | 僅內部 | MongoDB |

### 開啟後台（Docker）

| 服務 | 網址 |
|---|---|
| **後台管理** | http://127.0.0.1/admin/ |
| **POS 收銀** | http://127.0.0.1/pos/ |
| Swagger UI | http://127.0.0.1/apidocs |
| 健康檢查 | http://127.0.0.1/ |

> `APP_PORT` 若改為非 80，例如 `APP_PORT=8080`，則網址改為 `http://127.0.0.1:8080/...`

### 部署自訂域名（含 HTTPS）

#### 1. DNS 設定

在域名商後台新增 A Record，指向伺服器 IP：

```
類型   名稱   值
A      @      你的伺服器 IP
A      www    你的伺服器 IP   ← 若需要 www
```

#### 2. 伺服器開放 Port

```bash
# Ubuntu/Debian
ufw allow 80 && ufw allow 443

# CentOS/Rocky
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --reload
```

#### 3. 申請 Let's Encrypt SSL 憑證

```bash
# 安裝 certbot
apt install certbot   # Ubuntu/Debian

# 暫停 nginx（讓 certbot 使用 80 port 驗證）
docker compose stop nginx

# 申請憑證（替換成你的域名）
certbot certonly --standalone -d your.domain.com

# 憑證位置
# /etc/letsencrypt/live/your.domain.com/fullchain.pem
# /etc/letsencrypt/live/your.domain.com/privkey.pem
```

#### 4. 更新 nginx 設定

將 HTTPS 範本複製為生效設定，並替換 **4 處** `your.domain.com`：

```bash
cp conf/nginx/conf.d/default.conf.https-example conf/nginx/conf.d/default.conf
```

編輯 `conf/nginx/conf.d/default.conf`，將所有 `your.domain.com` 改為實際域名。

#### 5. 啟動

```bash
docker compose up -d
```

#### 6. 憑證自動續約（cron）

```bash
crontab -e
```

加入（替換專案路徑）：

```
30 2 * * * certbot renew --quiet && docker compose -f /path/to/Python-ERP_WMS/docker-compose.yml restart nginx
```

> 憑證有效期 90 天，cron 每日凌晨 2:30 檢查，到期前 30 天自動更新。

### 常用指令

```bash
docker compose ps                    # 查看運行狀態
docker compose logs -f app           # 即時查看 Flask 日誌
docker compose logs -f nginx         # 即時查看 nginx 日誌
docker compose exec app bash         # 進入 Flask 容器
docker compose restart nginx         # 重載 nginx 設定
docker compose restart app           # 重啟應用
docker compose down                  # 停止所有服務
docker compose down -v               # 停止並清除資料（不可逆）
docker compose build --no-cache app  # 重新建置 Flask 映像
```

---

## API 端點總覽

所有受保護端點需帶 Header：`Authorization: Bearer <token>`

### Base URL

| 環境 | Base URL |
|---|---|
| 本機開發（直接跑 Flask） | `http://127.0.0.1:5000` |
| Docker 部署（經 nginx） | `http://127.0.0.1`（預設 80，不需加 port） |

以下 curl 範例均以 Docker 環境（`http://127.0.0.1`）為準。

---

### 認證 `/auth`

| 方法 | 路徑 | 說明 |
|---|---|---|
| POST | `/auth/login` | 帳號密碼登入，回傳 JWT token 與角色 |
| GET | `/auth/me` | 驗證 Token 有效性，回傳目前使用者資訊 |

```bash
curl -X POST http://127.0.0.1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
# → {"success": true, "token": "<jwt>", "role": "admin"}
```

---

### 產品管理 `/product`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/product/category/` | 已登入 | 列出所有分類 |
| POST | `/product/category/` | operator+ | 新增分類 |
| PUT | `/product/category/<id>` | operator+ | 更新分類 |
| DELETE | `/product/category/<id>` | admin | 刪除分類 |
| GET | `/product/` | 已登入 | 列出產品（支援 `keyword` / `category_id` 搜尋） |
| GET | `/product/<id>` | 已登入 | 取得單一產品 |
| GET | `/product/barcode/<code>` | 已登入 | 以 EAN-13 條碼查詢產品 |
| POST | `/product/` | operator+ | 新增產品 |
| PUT | `/product/<id>` | operator+ | 更新產品 |
| DELETE | `/product/<id>` | admin | 刪除產品 |

**產品欄位說明**

| 欄位 | 說明 |
|---|---|
| `sku` | 唯一識別碼，建立時可自動生成（`SKU-YYYYMMDD-XXXX`） |
| `barcode` | EAN-13 條碼，建立時可自動生成（前綴 `200` 內部用） |
| `cost_price` | 成本價（用於毛利計算） |
| `sell_price` | 售價 |
| `min_stock` | 最低庫存警示（0 = 不限制） |
| `max_stock` | 最高庫存警示（0 = 不限制） |

---

### 倉庫管理 `/warehouse`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/warehouse/` | 已登入 | 列出倉庫 |
| POST | `/warehouse/` | admin | 新增倉庫（`code` 可自動生成 `WH-XXX`） |
| PUT | `/warehouse/<id>` | operator+ | 更新倉庫 |
| DELETE | `/warehouse/<id>` | admin | 刪除倉庫 |
| GET | `/warehouse/<id>/location/` | 已登入 | 列出倉庫位置 |
| POST | `/warehouse/<id>/location/` | operator+ | 新增位置 |
| PUT | `/warehouse/location/<id>` | operator+ | 更新位置 |
| DELETE | `/warehouse/location/<id>` | admin | 刪除位置 |

---

### 庫存管理 `/inventory`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/inventory/` | 已登入 | 查詢庫存（可篩選倉庫/產品） |
| POST | `/inventory/adjust` | operator+ | 盤點調整（直接設定數量） |
| GET | `/inventory/movement/` | 已登入 | 庫存移動紀錄 |

---

### 入庫管理 `/inbound`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/inbound/` | 已登入 | 列出入庫單（可篩選 `status`、`warehouse_id`） |
| POST | `/inbound/` | operator+ | 建立入庫單 |
| GET | `/inbound/<id>` | 已登入 | 查看入庫單詳情（含明細） |
| PUT | `/inbound/<id>` | operator+ | 更新基本資料（pending 狀態限定） |
| POST | `/inbound/<id>/item` | operator+ | 新增明細（支援 `barcode` 快速帶入產品） |
| PUT | `/inbound/<id>/item/<item_id>` | operator+ | 更新明細數量/單價 |
| DELETE | `/inbound/<id>/item/<item_id>` | operator+ | 移除明細 |
| POST | `/inbound/<id>/confirm` | operator+ | 確認入庫單 |
| POST | `/inbound/<id>/complete` | operator+ | 完成入庫（自動入帳庫存，可帶 `received_qtys`） |
| POST | `/inbound/<id>/cancel` | operator+ | 取消入庫單 |

#### POST `/inbound/<id>/item` — 新增明細（支援條碼掃描）

```bash
# 以 product_id 新增
curl -X POST http://127.0.0.1/inbound/<id>/item \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"product_id": "<id>", "expected_qty": 10, "unit_price": 500.0}'

# 以條碼掃描新增（自動查詢 product）
curl -X POST http://127.0.0.1/inbound/<id>/item \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"barcode": "2001234567890", "expected_qty": 10}'
```

#### POST `/inbound/<id>/complete` — 完成入庫

```bash
# 以 expected_qty 入庫
curl -X POST http://127.0.0.1/inbound/<id>/complete \
  -H "Authorization: Bearer <token>"

# 指定各明細實收數量
curl -X POST http://127.0.0.1/inbound/<id>/complete \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"received_qtys": {"<item_id_1>": 9, "<item_id_2>": 5}}'
```

---

### 出庫管理 `/outbound`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/outbound/` | 已登入 | 列出出庫單 |
| POST | `/outbound/` | operator+ | 建立出庫單 |
| GET | `/outbound/<id>` | 已登入 | 查看出庫單詳情 |
| PUT | `/outbound/<id>` | operator+ | 更新基本資料（pending 限定） |
| POST | `/outbound/<id>/item` | operator+ | 新增明細（支援 `barcode`） |
| PUT | `/outbound/<id>/item/<item_id>` | operator+ | 更新明細 |
| DELETE | `/outbound/<id>/item/<item_id>` | operator+ | 移除明細 |
| POST | `/outbound/<id>/confirm` | operator+ | 確認出庫（自動驗證庫存充足） |
| POST | `/outbound/<id>/complete` | operator+ | 完成出庫（自動扣減庫存，可帶 `shipped_qtys`） |
| POST | `/outbound/<id>/cancel` | operator+ | 取消出庫單 |

確認出庫單時庫存不足會回傳 `400`：

```json
{"success": false, "message": "產品 商品A 庫存不足 (現有:3, 需求:10)"}
```

---

### 分析報表 `/analytics`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/analytics/summary` | 已登入 | 日/週/月/年用量 + 毛利 + 庫存警示 |
| GET | `/analytics/stock_alerts` | 已登入 | 僅庫存警示列表 |

#### GET `/analytics/summary`

回傳四個時段（`day` / `week` / `month` / `year`）的統計：

```json
{
  "success": true,
  "data": {
    "day": {
      "inbound":  {"orders": 2, "completed": 1, "qty": 50, "amount": 25000.0},
      "outbound": {"orders": 1, "completed": 1, "qty": 20, "amount": 10000.0},
      "gross_profit": 3500.0
    },
    "week":  { ... },
    "month": { ... },
    "year":  { ... },
    "stock_alerts": [
      {"product_name": "商品A", "sku": "...", "warehouse_name": "台北倉",
       "quantity": 3, "min_stock": 10, "alert_type": "low"}
    ],
    "stock_alert_count": 1
  }
}
```

**毛利計算**：`(出庫售價 − 對應產品成本價) × 出庫數量` 之加總（僅計算已完成出庫單）

---

### POS 收銀 `/pos`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/pos/` | 任何人 | POS 收銀頁面（PWA） |
| GET | `/pos/manifest.json` | - | PWA Manifest（橫向鎖定） |
| POST | `/pos/sale` | cashier+ | 建立銷售單（結帳 + 原子扣庫存） |
| GET | `/pos/sales` | cashier+ | 查詢銷售記錄 |
| GET | `/pos/sales/<id>` | cashier+ | 查詢單筆銷售 |
| POST | `/pos/sales/<id>/refund` | operator+ | 退款（回補庫存） |
| GET | `/pos/summary` | cashier+ | 日結報表 |

#### POST `/pos/sale` — 結帳

```bash
curl -X POST http://127.0.0.1/pos/sale \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "warehouse_id": "<wid>",
    "items": [
      {"product_id": "<pid>", "product_name": "商品A",
       "product_sku": "SKU-001", "quantity": 2, "unit_price": 150.0}
    ],
    "payment": {"type": "cash", "cash_amount": 400},
    "discount": 50,
    "remark": ""
  }'
```

| `payment.type` | 說明 |
|---|---|
| `cash` | 純現金（需帶 `cash_amount`） |
| `card` | 純刷卡（需帶 `card_amount`） |
| `mixed` | 混合（同時帶 `cash_amount` 與 `card_amount`） |

Response `201`：

```json
{
  "success": true,
  "order": {
    "order_no": "POS-20260523-A1B2",
    "total_amount": 250.0,
    "change_amount": 150.0,
    "status": "completed"
  }
}
```

> **庫存扣減**採用 `findOneAndUpdate + $gte` 原子操作，並發失敗時自動 rollback，確保資料一致性。

#### GET `/pos/summary?date=YYYY-MM-DD` — 日結報表

```json
{
  "success": true,
  "data": {
    "date": "2026-05-23",
    "total_orders": 15,
    "total_amount": 8750.0,
    "total_discount": 200.0,
    "cash_total": 5500.0,
    "card_total": 3250.0,
    "orders": [ ... ]
  }
}
```

---

### 外送平台 `/delivery`

#### Webhook（不需 JWT）

| 方法 | 路徑 | 說明 |
|---|---|---|
| POST | `/delivery/webhook/ubereats` | 接收 UberEats 推播（驗 HMAC-SHA256 簽名） |
| POST | `/delivery/webhook/foodpanda` | 接收 foodpanda 推播（驗 HMAC-SHA256 簽名） |

Webhook URL 請填入各平台 Developer Dashboard：
- UberEats：`https://你的域名/delivery/webhook/ubereats`
- foodpanda：`https://你的域名/delivery/webhook/foodpanda`

#### 訂單管理

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/delivery/orders` | cashier+ | 查詢外送訂單（platform / status / date） |
| GET | `/delivery/orders/<id>` | cashier+ | 單筆訂單詳情 |
| PUT | `/delivery/orders/<id>/status` | operator+ | 更新狀態（同步回原平台） |

**訂單狀態**：`new` → `confirmed` → `preparing` → `ready` → `picked_up` → `delivered`，或 `cancelled`

#### 主動拉取 & 菜單同步

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| POST | `/delivery/sync/<platform>` | operator+ | 主動從平台拉取最新訂單 |
| POST | `/delivery/menu/sync/<platform>` | operator+ | 推送系統商品目錄至平台菜單 |

```bash
# 拉取 UberEats 訂單
curl -X POST http://127.0.0.1/delivery/sync/ubereats \
  -H "Authorization: Bearer <token>"
# → {"success": true, "new_count": 3, "errors": []}

# 同步菜單到 foodpanda
curl -X POST http://127.0.0.1/delivery/menu/sync/foodpanda \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"category_name": "全部商品"}'
# → {"success": true, "synced_products": 42}
```

#### 商品映射 & 平台設定

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/delivery/mappings` | operator+ | 列出系統商品 ↔ 平台商品 ID 映射 |
| POST | `/delivery/mappings` | operator+ | 新增/更新映射 |
| DELETE | `/delivery/mappings/<id>` | operator+ | 刪除映射 |
| GET | `/delivery/settings/<platform>` | admin | 取得平台設定 |
| PUT | `/delivery/settings/<platform>` | admin | 更新平台設定（啟用、自動接單、store_id 等） |

---

### 使用者管理 `/user`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/user/` | admin | 列出使用者 |
| POST | `/user/` | admin | 新增使用者 |
| PUT | `/user/<id>` | admin | 更新密碼或角色 |
| DELETE | `/user/<id>` | admin | 刪除使用者 |

---

### 操作紀錄 `/log`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/log/` | 已登入 | 查詢操作紀錄（可篩選 `username`、`action`） |

---

## 業務流程說明

### 入庫流程

```
1. 建立入庫單（POST /inbound/）
      ↓ 指定供應商、倉庫
2. 新增明細（POST /inbound/<id>/item）
      ↓ 指定產品（或掃描條碼自動帶入）、預計數量、單價
3. 確認入庫單（POST /inbound/<id>/confirm）
      ↓ pending → confirmed
4. 完成入庫（POST /inbound/<id>/complete）
      ↓ confirmed → completed
      ↓ 自動 +庫存（inventory）
      ↓ 自動記錄庫存移動（stock_movements）
```

### 出庫流程

```
1. 建立出庫單（POST /outbound/）
      ↓ 指定客戶、倉庫
2. 新增明細（POST /outbound/<id>/item）
      ↓ 指定產品（或掃描條碼）、預計出庫數量、單價
3. 確認出庫單（POST /outbound/<id>/confirm）
      ↓ 自動檢查各產品庫存是否充足（不足 → 400）
      ↓ pending → confirmed
4. 完成出庫（POST /outbound/<id>/complete）
      ↓ confirmed → completed
      ↓ 自動 -庫存
      ↓ 自動記錄庫存移動
```

### 入/出庫單狀態機

```
pending（待處理）
    ↓ confirm
confirmed（已確認）
    ↓ complete
completed（已完成）  ← 終態

pending / confirmed
    ↓ cancel
cancelled（已取消）  ← 終態
```

### POS 收銀流程

```
1. 開啟 /pos/（觸控友善 PWA，建議橫向使用）
2. 登入（JWT 存至 localStorage，重整不需重登）
3. 選擇出貨倉庫
4. 加入購物車（搜尋商品 / 掃描條碼）
5. 點擊「結帳」→ 選擇付款方式（現金 / 刷卡 / 混合）
      ↓ 系統自動原子扣減庫存
      ↓ 建立 pos_orders 紀錄
      ↓ 建立 stock_movements 紀錄
6. 顯示找零金額
7. 列印收據（window.print()）
```

**退款**：後台「POS 銷售記錄」→ 查看詳情 → 退款（operator+ 限定）  
退款時自動回補庫存並記錄移動紀錄。

### 外送訂單流程

```
A. 即時推播（Webhook，推薦）
   平台發送訂單 → POST /delivery/webhook/<platform>
       ↓ 驗 HMAC-SHA256 簽名
       ↓ 正規化訂單格式
       ↓ 儲存至 delivery_orders
       ↓ （若啟用自動接單）回呼平台確認 API

B. 主動拉取（Polling，備用）
   POST /delivery/sync/<platform>
       ↓ 呼叫平台 API 取得訂單列表
       ↓ Upsert（相同 external_order_id 不重複建立）

C. 後台操作
   後台「外送訂單」→ 查看 → 確認接單 / 拒絕 / 更新進度
       ↓ 系統同步呼叫平台 API 更新訂單狀態
```

### POS 銷售單狀態

```
completed（已完成）
    ↓ refund（operator+）
refunded（已退款）   ← 終態
```

### 外送訂單狀態機

```
new（新訂單）
    ↓ confirm
confirmed（已確認）
    ↓ preparing
preparing（備餐中）
    ↓ ready
ready（待取餐）
    ↓ picked_up
picked_up（已取餐）
    ↓ delivered
delivered（已送達）  ← 終態

new / confirmed
    ↓ cancel
cancelled（已取消）  ← 終態
```

---

## 角色與權限

| 角色 | 說明 | 主要權限 |
|---|---|---|
| `admin` | 管理員 | 完整權限：使用者管理、刪除資料、新增倉庫、外送平台設定 |
| `operator` | 操作員 | 建立/更新產品、倉庫位置、入出庫單、盤點調整、POS 退款、訂單狀態更新 |
| `cashier` | 收銀員 | POS 結帳、查詢銷售紀錄、查詢外送訂單 |
| `viewer` | 唯讀 | 僅查詢，無法新增/修改/刪除任何資料 |

```python
from src.permissions import require_role

@require_role('admin')                       # 僅 admin
@require_role('admin', 'operator')           # admin 或 operator
@require_role('admin', 'operator', 'cashier')# admin、operator 或 cashier
```

---

## 設定檔說明

### conf/config.ini

| 區塊 | 參數 | 說明 | 預設值 |
|---|---|---|---|
| `[LOG]` | `LOG_DISABLE` | 關閉 log（1=關閉） | `False` |
| | `LOG_PATH` | log 目錄 | `logs` |
| | `LOG_LEVEL` | 等級 DEBUG/INFO/WARNING/ERROR | `WARNING` |
| | `LOG_FILE_DISABLE` | 關閉寫入檔案 | `False` |
| `[SETTING]` | `ADMIN_TITLE` | 後台頁面標題 | `WMS 倉儲管理系統` |
| `[MONGO]` | `MONGO_URI` | MongoDB 連線 URI | `mongodb://localhost:27017` |
| | `MONGO_DB` | 資料庫名稱 | `wms` |
| `[UBEREATS]` | `CLIENT_ID` | UberEats OAuth2 Client ID | _(空)_ |
| | `CLIENT_SECRET` | UberEats OAuth2 Client Secret | _(空)_ |
| | `STORE_ID` | UberEats 餐廳 Store ID | _(空)_ |
| | `WEBHOOK_SECRET` | Webhook HMAC 驗簽密鑰 | _(空)_ |
| `[FOODPANDA]` | `API_KEY` | foodpanda Vendor API Key | _(空)_ |
| | `VENDOR_CODE` | foodpanda Vendor Code | _(空)_ |
| | `BASE_URL` | foodpanda API Base URL | `https://tw.fd-api.com` |
| | `WEBHOOK_SECRET` | Webhook HMAC 驗簽密鑰 | _(空)_ |

> 外送平台 API 金鑰**僅填入 config.ini**，不存入資料庫，確保不外洩。

### conf/flask.json

```json
{ "SECRET_KEY": "" }
```

`SECRET_KEY` 留空時，`run.py` 啟動會自動產生並寫入，無需手動填寫。

---

## MongoDB Collections

| Collection | 說明 |
|---|---|
| `users` | 使用者帳號（bcrypt 加密密碼） |
| `logs` | 所有操作紀錄 |
| `product_categories` | 產品分類 |
| `products` | 產品主檔（SKU、EAN-13 條碼、成本/售價、庫存警示） |
| `warehouses` | 倉庫資料（含自動生成代碼 WH-XXX） |
| `warehouse_locations` | 倉庫內位置/貨架 |
| `inventory` | 即時庫存（product × warehouse） |
| `stock_movements` | 庫存移動完整歷史（入庫/出庫/POS/盤點/退款均記錄） |
| `inbound_orders` | 入庫單（含 embedded items array） |
| `outbound_orders` | 出庫單（含 embedded items array） |
| `pos_orders` | POS 銷售單（含 embedded items、付款資訊） |
| `delivery_orders` | 外送平台訂單（UberEats / foodpanda） |
| `delivery_mappings` | 系統商品 ID ↔ 平台商品 ID 映射表 |
| `delivery_settings` | 各平台啟用狀態、自動接單設定 |

---

## 外送平台申請

### UberEats

1. 前往 [developer.uber.com](https://developer.uber.com) 建立應用程式
2. 申請 `eats.order`、`eats.store.menu.read`、`eats.store.menu.write` scope
3. 取得 `Client ID` 與 `Client Secret`
4. 取得餐廳 `Store ID`（在 Uber Eats Manager 後台）
5. 填入 `conf/config.ini` 的 `[UBEREATS]` 段落
6. 後台「平台設定」→ 複製 Webhook URL → 貼至 Uber Developer Dashboard

### foodpanda

1. 聯繫 foodpanda 商業夥伴（[vendor.foodpanda.tw](https://vendor.foodpanda.tw)）申請 Vendor API 存取
2. 取得 `API Key` 與 `Vendor Code`
3. 填入 `conf/config.ini` 的 `[FOODPANDA]` 段落
4. 後台「平台設定」→ 複製 Webhook URL → 提供給 foodpanda 技術支援

---

## 注意事項

| 項目 | 說明 |
|---|---|
| `conf/flask.json` | 含 `SECRET_KEY`，**勿提交至版控**（已加入 .gitignore） |
| `conf/config.ini` | 含資料庫連線與外送平台 API 金鑰，**勿提交至版控** |
| 預設帳號 | `admin / admin`，**首次啟動後立即至後台修改密碼** |
| POS 庫存扣減 | 採 `findOneAndUpdate + $gte` 原子操作，並發失敗自動 rollback，不依賴 MongoDB Transactions（單節點相容） |
| 出庫確認 | 確認出庫單時自動驗證庫存，庫存不足拒絕確認 |
| 庫存更新時機 | 庫存變更僅在「完成入/出庫」及「POS 結帳/退款」時觸發 |
| Webhook 安全 | 建議設定 `WEBHOOK_SECRET`，系統會驗證 HMAC-SHA256 簽名；留空則略過驗簽（僅開發用） |
| debug 模式 | 預設開啟，正式部署請改用 `ProductionConfig` 並設定 `debug=False` |
| 正式部署 | 建議使用 gunicorn + nginx，不直接暴露 Flask 開發伺服器 |
| POS PWA | `/pos/` 支援「加入主畫面」（PWA），加入後可從手機桌面直接啟動並自動鎖定橫向 |
