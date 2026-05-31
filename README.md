# WMS 倉儲管理系統

基於 Flask + MongoDB 建置的倉儲管理系統（WMS），整合 POS 收銀、多期間銷售報表、操作紀錄管理、外送平台串接，提供從倉儲入出庫到前台銷售的完整業務流程。

- **後台管理**：JWT 認證 + 角色權限（admin / operator / cashier / viewer）+ 使用者頁面模板控制
- **產品管理**：分類、SKU 自動生成、EAN-13 條碼、成本/售價、庫存警示
- **倉庫管理**：多倉庫、貨架位置、倉庫代碼自動生成（WH-XXX）
- **庫存管理**：即時查詢、盤點調整、低庫存 / 超量警示
- **入庫單**：建立 → 確認 → 完成（自動入帳庫存）+ 條碼掃描新增品項
- **出庫單**：建立 → 確認（自動驗證庫存）→ 完成（自動扣減）+ 條碼掃描
- **庫存移動紀錄**：完整異動歷史
- **POS 收銀**：觸控友善 UI（PWA 橫向鎖定）、現金/刷卡/混合付款、計算機數字鍵盤（1000/500/100/50 面額快鍵、+/− 模式、符合金額）、找零、印收據、退款管理、預設菜單設定
- **銷售報表**：日 / 週 / 月 / 年多期間銷售統計、每日/每月明細、付款方式分析
- **銷售記錄**：查詢、篩選、CSV 匯出 / 歷史資料匯入
- **操作紀錄**：查詢、CSV 匯出、批次匯入、自動清除（保留天數設定）
- **分析報表**：日 / 週 / 月 / 年度用量與毛利、庫存警示儀表板
- **外送平台**：串接 UberEats（OAuth2）與 foodpanda（API Key）— 即時訂單推播（Webhook）+ 主動拉取 + 菜單同步（含客製化選項群組）
- **菜單管理**：菜單 / 分類 / 品項 CRUD、客製化選項組（single / multiple）、JSON 批次匯出 / 匯入（跨菜單帶 ID 重映射）
- **顧客點餐頁**：時效 Token QR Code（`/order/?t=TOKEN`）自動帶入桌號；向下相容舊式 `?table=` URL；客製化選項、購物車結帳
- **QR 碼管理**：後台設定各桌 Token TTL（小時）、手動刷新、啟用 / 停用個別桌號；Token 懶觸發自動刷新
- **廚房看板**：即時顯示待處理 / 處理中訂單（先進先出），無需後台登入
- **系統設定**：POS 預設菜單、操作紀錄保留天數、手動清除
- **Swagger UI**：自動產生 API 文件
- **Docker 部署**：一鍵啟動；純主機部署（gunicorn + nginx）

測試環境：Python 3.11

---

## 目錄

- [專案結構](#專案結構)
- [快速開始（本機）](#快速開始本機)
- [Docker 部署](#docker-部署)
- [主機 nginx 部署](#主機-nginx-部署)（Docker app + 主機 nginx）
- [純主機部署（不使用 Docker）](#純主機部署不使用-docker)
- [API 端點總覽](#api-端點總覽)
  - [菜單管理 /menu](#菜單管理-menu)
  - [顧客點餐 /customer-order](#顧客點餐-customer-order)
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
│   ├── log/view.py                     # 操作紀錄（查詢/匯出/匯入/清除）
│   ├── settings/view.py                # 系統設定 CRUD
│   ├── product/view.py                 # 產品分類 + 產品 CRUD + 條碼查詢
│   ├── warehouse/view.py               # 倉庫 + 倉庫位置 CRUD
│   ├── inventory/view.py               # 庫存查詢、盤點調整、移動紀錄
│   ├── inbound/view.py                 # 入庫單管理
│   ├── outbound/view.py                # 出庫單管理
│   ├── analytics/view.py               # 分析報表 + 庫存警示
│   ├── pos/view.py                     # POS 收銀（銷售、退款、CSV 匯出入、銷售報表）
│   ├── menu/view.py                    # 菜單管理（菜單/分類/品項/選項組 CRUD + JSON 匯出入）
│   ├── customer_order/
│   │   ├── page.py                     # GET /order/ → 顧客點餐前端頁面
│   │   └── view.py                     # 公開：取得菜單 / 建立訂單；登入：查詢 / 狀態更新
│   ├── kitchen/view.py                 # GET /kitchen/ → 廚房看板頁面（免登入）
│   ├── quick_io/view.py                # GET /quick-io/ → 快速出入庫頁面
│   ├── delivery/                       # 外送平台整合
│   │   ├── view.py                     # Webhook + 訂單 + 菜單同步 + 設定端點
│   │   └── adapters/
│   │       ├── ubereats.py             # UberEats Marketplace API client（含選項群組解析）
│   │       └── foodpanda.py            # foodpanda Vendor API client（含選項群組解析）
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
│       ├── certs/cloudflare/           # Cloudflare 憑證放置目錄（預設空，http 模式不需要）
│       ├── templates/
│       │   ├── http/
│       │   │   └── default.conf.template               # HTTP 模式 template
│       │   └── cloudflare/
│       │       └── default.conf.template               # Cloudflare SSL 模式 template
│       └── conf.d/                     # 舊版靜態設定檔（參考用，已由 templates 取代）
│
└── src/
    ├── __init__.py                     # 全域設定參數（含外送平台設定讀取）
    ├── mongo.py                        # MongoDB singleton
    ├── permissions.py                  # @require_role 裝飾器
    └── models/
        ├── user.py                     # 使用者（bcrypt）
        ├── log.py                      # 操作紀錄（含 bulk_insert / cleanup_old）
        ├── settings.py                 # 系統設定（key-value 儲存）
        ├── product.py                  # ProductCategory、Product
        ├── warehouse.py                # Warehouse、WarehouseLocation
        ├── inventory.py                # Inventory、StockMovement
        ├── inbound.py                  # InboundOrder（含 embedded items）
        ├── outbound.py                 # OutboundOrder（含 embedded items）
        ├── pos.py                      # PosOrder（POS 銷售單 + bulk_import）
        ├── menu.py                     # Menu（菜單/分類/品項/選項組，全 embedded）
        ├── customer_order.py           # CustomerOrder（顧客點餐訂單）
        ├── user_template.py            # UserTemplate（頁面權限模板）
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
| **快速出入庫** | http://127.0.0.1:5000/quick-io/ |
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
| **顧客點餐** | http://127.0.0.1/order/ |
| **廚房看板** | http://127.0.0.1/kitchen/ |
| **快速出入庫** | http://127.0.0.1/quick-io/ |
| Swagger UI | http://127.0.0.1/apidocs |
| 健康檢查 | http://127.0.0.1/ |

> `APP_PORT` 若改為非 80，例如 `APP_PORT=8080`，則網址改為 `http://127.0.0.1:8080/...`

### 部署自訂域名（含 HTTPS）

nginx 模式透過 `.env` 的 `NGINX_MODE` 控制，**不需要手動換設定檔**，只要改 `.env` 再重啟即可。

| `NGINX_MODE` | 說明 | 適用情境 |
|---|---|---|
| `http` | 純 HTTP（預設） | 本機、無域名、內網 |
| `cloudflare` | Cloudflare Origin CA SSL | 域名走 Cloudflare 代理 |

---

#### 模式一：HTTP（預設，無需額外設定）

`.env` 保持預設即可：

```env
NGINX_MODE=http
DOMAIN=_
```

---

#### 模式二：Cloudflare SSL

##### 1. DNS 設定

Cloudflare Dashboard → 你的域名 → DNS → 新增 A Record：

```
類型   名稱   值              Proxy
A      @      伺服器 IP       ☁ Proxied
```

##### 2. 伺服器開放 Port

```bash
ufw allow 80 && ufw allow 443
```

##### 3. 建立 Cloudflare Origin CA 憑證

Cloudflare Dashboard → **SSL/TLS → Origin Server → Create Certificate**

- 選 RSA，有效期 15 年
- 複製 **Origin Certificate** 和 **Private Key**

```bash
# 存放到伺服器
mkdir -p /etc/ssl/cloudflare
nano /etc/ssl/cloudflare/origin.pem   # 貼上 Origin Certificate
nano /etc/ssl/cloudflare/origin.key   # 貼上 Private Key
chmod 600 /etc/ssl/cloudflare/origin.key
```

##### 4. 更新 `.env`

```env
NGINX_MODE=cloudflare
DOMAIN=your.domain.com
CF_CERT_DIR=/etc/ssl/cloudflare
```

##### 5. 啟動

```bash
docker compose up -d
```

> Cloudflare SSL/TLS 模式記得設為 **Full (Strict)**，確保 Cloudflare ↔ 伺服器端對端加密。

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

## 主機 nginx 部署

> **適用情境**：主機上已安裝 nginx（或已有其他服務佔用 80/443 port），不希望在 Docker 中額外跑一個 nginx 容器。

```
使用者 → 主機 nginx:80/443 → 127.0.0.1:5000（Docker app 容器）→ MongoDB 容器
                ↓ 靜態檔
         /opt/wms/frontend-dist/（主機本地目錄）
```

設定檔位置：

| 檔案 | 說明 |
|---|---|
| `conf/nginx/host/http.conf` | 純 HTTP（IP 直連或 Cloudflare 代理） |
| `conf/nginx/host/cloudflare.conf` | Cloudflare Origin CA SSL |
| `conf/nginx/host/https-letsencrypt.conf` | Let's Encrypt 免費 SSL |

---

### Step 0：建置前端（在開發機或伺服器上執行）

```bash
# 於開發機建置後上傳
cd frontend
npm ci && npm run build          # 產物輸出至 ../frontend-dist/

# 同步至伺服器（以 /opt/wms 為例）
rsync -av --delete frontend-dist/ user@server:/opt/wms/frontend-dist/
```

> 若直接在伺服器上 build，需先安裝 Node.js 18+（`apt install -y nodejs npm` 或 nvm）。
> Build 完成後即可解除安裝，nginx 只需要 `frontend-dist/` 目錄。

---

### Step 1：調整 docker-compose.yml

移除 `nginx` 服務，並讓 `app` 容器將 port 暴露至主機 localhost：

```yaml
services:
  # nginx:          ← 整段刪除或 comment out
  #   image: ...

  app:
    # ... 其他設定不變 ...
    ports:
      - "127.0.0.1:5000:5000"   # 只綁 localhost，不直接對外暴露
```

### Step 2：安裝 nginx（Ubuntu / Debian）

```bash
sudo apt update && sudo apt install -y nginx
sudo systemctl enable --now nginx
```

### Step 3：建立 nginx 站台設定

選擇其中一種模式：

```bash
# ── 模式一：HTTP（IP 直連或 Cloudflare 代理） ──────────────
sudo cp conf/nginx/host/http.conf /etc/nginx/sites-available/flask-app
sudo nano /etc/nginx/sites-available/flask-app
# 替換兩個佔位符：
#   YOUR_DOMAIN       → 實際域名，或 _ 接受所有請求
#   YOUR_PROJECT_PATH → 專案根目錄，例如 /opt/wms

# ── 模式二：Cloudflare Origin CA SSL ──────────────────────
# 前置：建立 Cloudflare 憑證（參見檔案頂部說明）
sudo cp conf/nginx/host/cloudflare.conf /etc/nginx/sites-available/flask-app
sudo nano /etc/nginx/sites-available/flask-app
# 替換兩個佔位符：
#   YOUR_DOMAIN       → 實際域名（共 2 處）
#   YOUR_PROJECT_PATH → 專案根目錄，例如 /opt/wms

# ── 模式三：Let's Encrypt SSL ──────────────────────────────
sudo apt install -y certbot python3-certbot-nginx
# 先用 http.conf 啟動 nginx 後，再申請憑證：
sudo certbot certonly --nginx -d your.domain.com
# 憑證申請成功後換用 letsencrypt 設定：
sudo cp conf/nginx/host/https-letsencrypt.conf /etc/nginx/sites-available/flask-app
sudo nano /etc/nginx/sites-available/flask-app
# 替換兩個佔位符：
#   YOUR_DOMAIN       → 實際域名（共 4 處）
#   YOUR_PROJECT_PATH → 專案根目錄，例如 /opt/wms
```

### Step 4：啟用站台並重載

```bash
sudo ln -sf /etc/nginx/sites-available/flask-app /etc/nginx/sites-enabled/flask-app
sudo rm -f /etc/nginx/sites-enabled/default   # 移除預設站台（若存在）
sudo nginx -t                                  # 驗證設定語法
sudo systemctl reload nginx
```

### Step 5：啟動 Docker 容器（不含 nginx）

```bash
docker compose up -d --build app mongo
```

### 常用指令

```bash
sudo nginx -t                                       # 驗證設定語法
sudo systemctl reload nginx                         # 重載（不中斷連線）
sudo systemctl restart nginx                        # 完整重啟
sudo tail -f /var/log/nginx/flask-app-error.log    # 錯誤日誌
sudo tail -f /var/log/nginx/flask-app-access.log   # 訪問日誌
sudo certbot renew --dry-run                        # 測試 Let's Encrypt 自動續約
```

---

## 純主機部署（不使用 Docker）

> **適用情境**：伺服器上不安裝 Docker，直接以 Python + gunicorn 跑 Flask，再以 nginx 作為反向代理。

```
使用者 → nginx:80/443 → 127.0.0.1:5000（gunicorn）→ MongoDB（本機或遠端）
```

### 前置需求

| 項目 | 版本建議 |
|---|---|
| Python | 3.11+ |
| MongoDB | 6.0 / 7.0 |
| nginx | 1.18+ |
| gunicorn | 21+ |

---

### Step 1：安裝系統套件

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx

# 安裝 MongoDB（官方 repo，以 Ubuntu 22.04 為例）
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
  sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] \
  https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | \
  sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update && sudo apt install -y mongodb-org
sudo systemctl enable --now mongod
```

---

### Step 2：建立專案目錄與虛擬環境

> **注意：請勿將專案放在 `/root/` 下。**  
> nginx 以 `www-data` 執行，`/root/` 權限為 `700`，nginx 無法讀取靜態檔，會出現 `(13: Permission denied)` 錯誤。  
> 若已部署在 `/root/`，請先搬移：
> ```bash
> sudo mv /root/erp_wms /opt/wms
> sudo chown -R www-data:www-data /opt/wms
> ```

```bash
# 建議放在 /opt/wms（可自訂）
sudo mkdir -p /opt/wms
sudo chown -R www-data:www-data /opt/wms

# 上傳或 git clone 專案（以 www-data 身份，或 clone 後再 chown）
cd /opt/wms
git clone <你的倉庫網址> .   # 或 scp / rsync 上傳
sudo chown -R www-data:www-data /opt/wms

# 建立虛擬環境並安裝套件
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn          # 正式部署用 WSGI 伺服器
```

---

### Step 2.5：建置前端（Vue SPA）

```bash
# 在開發機 build 後 rsync 上傳（推薦）
cd frontend
npm ci && npm run build        # 輸出至 ../frontend-dist/
rsync -av --delete ../frontend-dist/ user@server:/opt/wms/frontend-dist/

# 或直接在伺服器上 build（需 Node.js 18+）
# curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
# sudo apt install -y nodejs
cd /opt/wms/frontend && npm ci && npm run build
```

> `frontend-dist/` 為純靜態檔案，build 後 Node.js 可以移除，不影響 nginx serving。

---

### Step 3：複製並調整設定檔

```bash
cp conf/config.ini.default conf/config.ini
cp conf/flask.json.default conf/flask.json
```

編輯 `conf/config.ini`：

```ini
[SETTING]
ADMIN_TITLE=WMS 倉儲管理系統

[MONGO]
MONGO_URI=mongodb://127.0.0.1:27017   # 本機 MongoDB
MONGO_DB=wms
```

> `flask.json` 的 `SECRET_KEY` 留空，`run.py` 啟動時自動產生並寫入。

---

### Step 4：建立 systemd 服務（gunicorn）

建立服務檔 `/etc/systemd/system/wms.service`：

```ini
[Unit]
Description=WMS Flask App (gunicorn)
After=network.target mongod.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/wms
Environment="PATH=/opt/wms/venv/bin"
ExecStart=/opt/wms/venv/bin/gunicorn \
    --workers 4 \
    --bind 127.0.0.1:5000 \
    --timeout 120 \
    --access-logfile /var/log/wms/access.log \
    --error-logfile  /var/log/wms/error.log \
    "run:app"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# 建立 log 目錄並設定權限
sudo mkdir -p /var/log/wms
sudo chown www-data:www-data /var/log/wms

# 也需要讓 www-data 能讀取專案（包含 conf/）
sudo chown -R www-data:www-data /opt/wms

# 啟用並啟動服務
sudo systemctl daemon-reload
sudo systemctl enable --now wms

# 確認狀態
sudo systemctl status wms
```

> **workers 數量建議**：`2 × CPU 核心數 + 1`，例如 2 核心建議設 `--workers 5`。

---

### Step 5：設定 nginx

三種 SSL 模式的 nginx 設定邏輯相同：API 路徑（帶 trailing slash）proxy 到 gunicorn，其餘路徑由 nginx 直接 serve Vue SPA 靜態檔並做 SPA fallback。

**模式一：HTTP（無 SSL）**

建立 `/etc/nginx/sites-available/wms`：

```nginx
server {
    listen 80;
    server_name _;   # 或填入你的域名 / IP

    client_max_body_size 20M;

    # ── Flask API（trailing slash 區分 API vs SPA 路由）──────
    location ~* ^/(auth|user|log|product|warehouse|inventory|inbound|outbound|analytics|pos|delivery|menu|settings|customer-order|apidocs)/ {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location = /apidocs {
        return 301 /apidocs/;
    }

    # ── Vue SPA 靜態檔案 ─────────────────────────────────────
    location / {
        root  /opt/wms/frontend-dist;
        try_files $uri $uri/ /index.html;
    }
}
```

**模式二：Cloudflare SSL**

```nginx
upstream gunicorn {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name your.domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your.domain.com;

    ssl_certificate     /etc/ssl/cloudflare/origin.pem;
    ssl_certificate_key /etc/ssl/cloudflare/origin.key;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_cache   shared:SSL:10m;

    client_max_body_size 20M;

    # Cloudflare 真實 IP 還原（略，參見 conf/nginx/host/cloudflare.conf）

    location ~* ^/(auth|user|log|product|warehouse|inventory|inbound|outbound|analytics|pos|delivery|menu|settings|customer-order|apidocs)/ {
        proxy_pass         http://gunicorn;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    location = /apidocs {
        return 301 /apidocs/;
    }

    location / {
        root  /opt/wms/frontend-dist;
        try_files $uri $uri/ /index.html;
    }
}
```

**模式三：Let's Encrypt SSL**

```bash
# 先以 HTTP 模式（模式一）啟動 nginx，再申請憑證
sudo certbot --nginx -d your.domain.com
# certbot 自動加入 HTTPS block 後，手動補上 API regex location 與 Vue root（同模式二邏輯）
```

**啟用站台**：

```bash
sudo ln -sf /etc/nginx/sites-available/wms /etc/nginx/sites-enabled/wms
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t      # 驗證語法
sudo systemctl reload nginx
```

---

### Step 6：初次啟動與確認

```bash
# 手動執行一次以產生 SECRET_KEY 並建立預設 admin（需在虛擬環境中）
cd /opt/wms
source venv/bin/activate
python run.py   # 看到 [init] 訊息後 Ctrl+C，交由 systemd 管理

# 重啟 gunicorn 服務
sudo systemctl restart wms

# 檢查是否正常
curl http://127.0.0.1/
```

| 服務 | 網址 |
|---|---|
| **後台管理** | http://你的IP或域名/admin/ |
| **POS 收銀** | http://你的IP或域名/pos/ |
| **顧客點餐** | http://你的IP或域名/order/ |
| Swagger UI | http://你的IP或域名/apidocs |

---

### 常用維運指令

```bash
# Flask 應用
sudo systemctl status wms           # 查看狀態
sudo systemctl restart wms          # 重啟（更新程式碼後）
sudo systemctl stop wms             # 停止
sudo journalctl -u wms -f           # 即時 log（journald）
sudo tail -f /var/log/wms/error.log # gunicorn error log

# nginx
sudo nginx -t                       # 驗證設定語法
sudo systemctl reload nginx         # 重載（不中斷連線）
sudo tail -f /var/log/nginx/error.log

# MongoDB
sudo systemctl status mongod
mongosh wms --eval "db.users.countDocuments()"   # 快速確認資料
```

### 更新程式碼

```bash
cd /opt/wms
git pull                           # 拉取最新版本

# 若有新套件
source venv/bin/activate
pip install -r requirements.txt

# ── 若有前端變更 ──────────────────────────────────────────────
# 方式一：直接在伺服器上 build（需已安裝 Node.js 18+）
cd /opt/wms/frontend
npm ci && npm run build            # 產物輸出至 ../frontend-dist/
cd /opt/wms

# 方式二：在開發機 build 後 rsync 上傳（不需伺服器安裝 Node.js）
# rsync -av --delete frontend-dist/ user@server:/opt/wms/frontend-dist/

sudo systemctl restart wms         # 重啟 gunicorn（後端程式碼變更後必做）
```

> **注意**：前端（Vue）程式碼修改後，**必須重新 build** 才會生效。`git pull` 只更新原始碼，不會自動套用到使用者看到的頁面。

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

---

### POS 收銀 `/pos`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/pos/` | 任何人 | POS 收銀頁面（PWA） |
| GET | `/pos/manifest.json` | - | PWA Manifest（橫向鎖定） |
| POST | `/pos/sale` | cashier+ | 建立銷售單（結帳 + 原子扣庫存） |
| GET | `/pos/sales` | cashier+ | 查詢銷售記錄（支援日期/收銀員/狀態/來源篩選） |
| GET | `/pos/sales/export` | cashier+ | 依篩選條件匯出全部銷售記錄為 CSV |
| POST | `/pos/sales/import` | admin | 批次匯入歷史銷售記錄（CSV/JSON，不扣庫存） |
| GET | `/pos/sales/<id>` | cashier+ | 查詢單筆銷售 |
| POST | `/pos/sales/<id>/refund` | operator+ | 退款（回補庫存） |
| GET | `/pos/payment-methods` | 已登入 | 取得 POS 付款方式清單 |
| PUT | `/pos/payment-methods` | admin | 更新 POS 付款方式 |
| GET | `/pos/summary` | cashier+ | 銷售報表（日/週/月/年） |

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

#### GET `/pos/summary` — 銷售報表

支援 `period` 參數切換多種統計粒度：

| `period` | 參數 | 說明 |
|---|---|---|
| `day`（預設） | `date=YYYY-MM-DD` | 單日；回傳 `orders` 個別訂單列表 |
| `week` | `date=YYYY-MM-DD` | 指定日期所在週（週一起始）；回傳 `breakdown` 每日彙總 |
| `month` | `month=YYYY-MM` | 指定月份；回傳 `breakdown` 每日彙總 |
| `year` | `year=YYYY` | 指定年份；回傳 `breakdown` 每月彙總 |

**日模式回傳範例（`period=day`）：**

```json
{
  "success": true,
  "data": {
    "period": "day",
    "date": "2026-05-28",
    "total_orders": 15,
    "total_amount": 8750.0,
    "total_discount": 200.0,
    "cash_total": 5500.0,
    "card_total": 3250.0,
    "orders": [
      {"_id": "...", "order_no": "POS-20260528-A1B2",
       "total_amount": 350.0, "payment_type": "cash", "status": "completed", ...}
    ]
  }
}
```

**週/月模式回傳範例（`period=week`）：**

```json
{
  "success": true,
  "data": {
    "period": "week",
    "date_from": "2026-05-25",
    "date_to": "2026-05-31",
    "total_orders": 87,
    "total_amount": 52300.0,
    "breakdown": [
      {"period": "2026-05-25", "orders": 12, "amount": 7200.0, "discount": 100.0},
      {"period": "2026-05-26", "orders": 15, "amount": 9500.0, "discount": 200.0}
    ]
  }
}
```

#### GET `/pos/sales/export` — 匯出 CSV

依目前篩選條件匯出全部銷售記錄，不受筆數限制。支援 `date_from`、`date_to`、`cashier`、`status`、`source` 篩選參數。

CSV 欄位：`order_no, source, warehouse_name, cashier, items_count, subtotal, discount, total_amount, payment_type, cash_amount, change_amount, status, remark, created_at`

#### POST `/pos/sales/import` — 匯入 CSV/JSON（admin）

從 CSV 或 JSON 檔案批次匯入歷史銷售記錄，**不執行庫存扣減**，僅寫入 `pos_orders` collection。

```bash
curl -X POST http://127.0.0.1/pos/sales/import \
  -H "Authorization: Bearer <admin-token>" \
  -F "file=@/path/to/sales.csv"
# → {"success": true, "inserted": 120}
```

---

### 操作紀錄 `/log`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/log/` | 已登入 | 查詢操作紀錄（支援 `username`/`action`/日期範圍/`limit`） |
| GET | `/log/export` | 已登入 | 依篩選條件匯出全部紀錄為 CSV（不限筆數） |
| POST | `/log/import` | admin | 從 CSV 或 JSON 批次匯入操作紀錄 |
| GET | `/log/stats` | 已登入 | 取得統計（總筆數 + 超齡筆數） |
| POST | `/log/cleanup` | admin | 立即清除超齡紀錄 |

**自動清除機制**：每次讀取操作紀錄頁時，若「系統設定」已設定保留天數且距上次清除 ≥ 24 小時，系統自動觸發清除，無需額外排程器。

---

### 系統設定 `/settings`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/settings/` | 已登入 | 取得所有系統設定 |
| PUT | `/settings/` | admin | 批次更新系統設定（key-value） |

**已支援的設定鍵值**

| 鍵 | 說明 | 預設 |
|---|---|---|
| `pos_default_menu_id` | POS 收銀台預設載入的菜單 ID | _(空)_ |
| `log_retention_days` | 操作紀錄保留天數（0 = 不自動清除） | `0` |
| `log_last_cleanup_at` | 上次清除操作紀錄的 UTC 時間（ISO 格式） | _(空)_ |
| `pos_payment_methods` | POS 付款方式清單（JSON） | 見 POS 端點說明 |
| `table_tokens` | 各桌號 Token 資料（`{table_no: {token, label, enabled, expires_at}}`），由 QR 碼管理頁維護 | _(空)_ |
| `qr_token_ttl_hours` | QR Token 有效時數（最小 1） | `24` |
| `qr_token_last_refresh` | 上次刷新 Token 的 UTC 時間（ISO 格式），用於懶觸發自動刷新判斷 | _(空)_ |

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
| POST | `/delivery/menu/sync/<platform>` | operator+ | 從平台拉取菜單並同步至 WMS（含客製化選項群組） |

```bash
# 拉取 UberEats 訂單
curl -X POST http://127.0.0.1/delivery/sync/ubereats \
  -H "Authorization: Bearer <token>"
# → {"success": true, "new_count": 3, "errors": []}

# 從 foodpanda 同步菜單與客製化選項
curl -X POST http://127.0.0.1/delivery/menu/sync/foodpanda \
  -H "Authorization: Bearer <token>"
# → {"success": true, "synced": 42, "groups_created": 5, "groups_updated": 3}
```

**菜單同步說明**：從外送平台拉回菜單時，會一併同步客製化選項群組（UberEats `modifier_groups` / foodpanda `topping_groups`）至 WMS 菜單的 `option_groups`，並自動建立品項與選項群組的連結。

#### 商品映射 & 平台設定

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/delivery/mappings` | operator+ | 列出系統商品 ↔ 平台商品 ID 映射 |
| POST | `/delivery/mappings` | operator+ | 新增/更新映射 |
| DELETE | `/delivery/mappings/<id>` | operator+ | 刪除映射 |
| GET | `/delivery/settings/<platform>` | admin | 取得平台設定 |
| PUT | `/delivery/settings/<platform>` | admin | 更新平台設定（啟用、自動接單、store_id 等） |

---

### 菜單管理 `/menu`

#### 菜單 CRUD

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/menu/` | 已登入 | 列出菜單（`?status=1` 只取啟用） |
| GET | `/menu/<mid>` | 已登入 | 取得單一菜單（含品項、分類、選項組） |
| POST | `/menu/` | operator+ | 建立菜單（`name`、`description`、`sort_order`） |
| PUT | `/menu/<mid>` | operator+ | 更新菜單基本資料 |
| DELETE | `/menu/<mid>` | admin | 刪除菜單 |

#### 品項 CRUD

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| POST | `/menu/<mid>/item` | operator+ | 新增品項（`name`、`price`、`category`、`consume_inventory`、`applied_group_ids` 等） |
| PUT | `/menu/<mid>/item/<item_id>` | operator+ | 更新品項 |
| DELETE | `/menu/<mid>/item/<item_id>` | operator+ | 刪除品項 |

#### 分類 CRUD

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| POST | `/menu/<mid>/category` | operator+ | 新增分類 |
| PUT | `/menu/<mid>/category/<cat_id>` | operator+ | 更新分類（改名時同步更新品項 `category` 欄位） |
| DELETE | `/menu/<mid>/category/<cat_id>` | operator+ | 刪除分類（品項 `category` 字串保留，不清除） |

#### 客製化選項組

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/menu/<mid>/option-group` | 已登入 | 列出所有選項組 |
| POST | `/menu/<mid>/option-group` | operator+ | 新增選項組（`name`、`type: single\|multiple`、`required`、`choices`） |
| PUT | `/menu/<mid>/option-group/<gid>` | operator+ | 更新選項組 |
| DELETE | `/menu/<mid>/option-group/<gid>` | operator+ | 刪除選項組（自動從品項 `applied_group_ids` 移除） |

**選項組結構**：
```json
{
  "name": "辣度",
  "type": "single",
  "required": true,
  "choices": [
    {"name": "不辣", "extra_price": 0, "is_default": true},
    {"name": "小辣", "extra_price": 0},
    {"name": "大辣", "extra_price": 10}
  ]
}
```

#### 菜單匯出 / 匯入

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/menu/<mid>/export` | operator+ | 匯出單一菜單（含分類、選項組、品項）為 JSON 檔 |
| POST | `/menu/<mid>/import` | operator+ | 匯入 JSON 至指定菜單（分類/選項組同名略過，品項同名更新）；選項組 ID 自動重映射 |
| GET | `/menu/export-all` | operator+ | 匯出**全部**菜單為 JSON 檔（適合整機備份） |
| POST | `/menu/import-all` | operator+ | 從 JSON 批次匯入全部菜單（菜單同名沿用，不覆蓋基本資料） |

---

### 顧客點餐 `/customer-order`

| 方法 | 路徑 | 登入 | 說明 |
|---|---|---|---|
| GET | `/customer-order/menu` | 不需要 | 取得點餐用菜單；帶 `?t=TOKEN` 時驗證 Token 並自動帶入桌號，同時觸發 Token 懶觸發刷新 |
| POST | `/customer-order/` | 不需要（帶 JWT 則以帳號識別） | 建立訂單；Token 模式時必須帶 `qr_token`，非 Token 模式帶 `table_no` |
| GET | `/customer-order/` | 需要 | 查詢訂單列表（可篩選 `status`、`date`） |
| GET | `/customer-order/active` | 需要 | 廚房用：取得待處理 + 處理中訂單（先進先出） |
| GET | `/customer-order/stats` | 需要 | 今日各狀態訂單數量與金額 |
| GET | `/customer-order/<oid>` | 需要 | 取得單筆訂單 |
| PUT | `/customer-order/<oid>/status` | operator+ | 更新訂單狀態（`pending→processing→completed\|cancelled`） |
| GET | `/customer-order/tokens` | admin | 取得桌號 Token 清單、TTL 設定、上次刷新時間 |
| POST | `/customer-order/tokens/refresh` | admin | 立即刷新所有桌號 Token（可同時更新 TTL） |
| PUT | `/customer-order/tokens/tables` | admin | 新增 / 更新桌號清單，保留現有 Token；`enabled` 欄位可啟停個別桌號 |

**POST `/customer-order/` — 建立訂單**：

```bash
curl -X POST http://127.0.0.1/customer-order/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "table_no": "A1",
    "items": [
      {
        "item_id": "<item_id>",
        "item_name": "珍珠奶茶",
        "qty": 2,
        "price": 55,
        "customizations": [
          {"group_id": "<gid>", "group_name": "甜度", "choice_id": "<cid>", "choice_name": "七分", "extra_price": 0}
        ]
      }
    ],
    "total": 110,
    "remark": "少冰",
    "menu_id": "<mid>"
  }'
# → {"success": true, "order_id": "...", "order_no": "20260530-0001"}
```

> 若攜帶有效 JWT，`table_no` 可省略（以登入帳號 username 作識別碼）。

**訂單狀態流程**：`pending（待處理）→ processing（處理中）→ completed（已完成）| cancelled（已取消）`

---

### 使用者管理 `/user`

| 方法 | 路徑 | 角色 | 說明 |
|---|---|---|---|
| GET | `/user/` | admin | 列出使用者 |
| POST | `/user/` | admin | 新增使用者 |
| PUT | `/user/<id>` | admin | 更新密碼或角色 |
| DELETE | `/user/<id>` | admin | 刪除使用者（系統預設 admin 不可刪） |

**使用者模板（page_permissions）**：admin 可為每位非 admin 使用者指定「頁面顯示模板」，控制側邊欄可見的功能頁面。模板設定存於 `users` collection 的 `page_permissions` 陣列，可包含任意頁面鍵（如 `pos-sales`、`pos-report`、`menus`、`settings` 等）。

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
3. 選擇出貨倉庫（系統設定可預設倉庫與菜單）
4. 加入購物車（搜尋商品 / 掃描條碼 / 選擇菜單品項）
   └─ 品項含客製化選項時，彈出選項選擇視窗
5. 點擊「結帳」→ 選擇付款方式（現金 / 刷卡 / 混合）
      ↓ 系統自動原子扣減庫存
      ↓ 建立 pos_orders 紀錄
      ↓ 建立 stock_movements 紀錄
6. 顯示找零金額
7. 列印收據（window.print()）
```

**退款**：後台「銷售記錄」→ 查看詳情 → 退款（operator+ 限定）  
退款時自動回補庫存並記錄移動紀錄。

**銷售記錄匯出 / 匯入**：後台「銷售記錄」右上角可匯出 CSV（依目前篩選條件），或匯入 CSV/JSON 歷史資料（僅 admin，不執行庫存扣減）。

### 銷售報表多期間切換

後台「銷售報表」支援四種統計粒度，直接點擊按鈕切換：

| 模式 | 選擇器 | 顯示內容 |
|---|---|---|
| 日 | 日期選擇器 | 當日摘要 + 個別訂單列表 + 付款方式分析 |
| 週 | 日期選擇器（取所在週） | 本週摘要 + 每日銷售明細 |
| 月 | 月份選擇器（YYYY-MM） | 本月摘要 + 每日銷售明細 |
| 年 | 年份下拉（近 5 年） | 全年摘要 + 每月銷售明細 |

### 操作紀錄管理

```
自動清除（懶觸發）：
  每次開啟「操作紀錄」頁面時 → 檢查系統設定的 log_retention_days
  若已設定且距上次清除 ≥ 24 小時 → 自動刪除超齡紀錄

手動操作（系統設定頁面）：
  ├─ 設定保留天數（0 = 不自動清除）
  ├─ 查看統計：總筆數 + 超齡筆數
  └─ 立即清除（按鈕 → confirm → 刪除超齡紀錄）

匯出 CSV：
  支援 username / action / 日期範圍 篩選，不受顯示筆數限制

匯入（admin）：
  支援 CSV 或 JSON 格式批次匯入歷史操作紀錄
```

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

D. 菜單同步（含客製化選項群組）
   後台「平台設定」→「匯入菜單」
       ↓ 從平台拉回菜單品項
       ↓ 同步 option_groups（modifier_groups / topping_groups）
       ↓ 建立品項與選項群組的 applied_group_ids 連結
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
| `admin` | 管理員 | 完整權限：使用者管理、刪除資料、新增倉庫、外送平台設定、系統設定、操作紀錄清除/匯入、銷售匯入 |
| `operator` | 操作員 | 建立/更新產品、倉庫位置、入出庫單、盤點調整、POS 退款、訂單狀態更新 |
| `cashier` | 收銀員 | POS 結帳、查詢銷售紀錄、查詢外送訂單、匯出銷售 CSV |
| `viewer` | 唯讀 | 僅查詢，無法新增/修改/刪除任何資料 |

```python
from src.permissions import require_role

@require_role('admin')                       # 僅 admin
@require_role('admin', 'operator')           # admin 或 operator
@require_role('admin', 'operator', 'cashier')# admin、operator 或 cashier
```

**使用者頁面模板**：admin 可在「使用者管理」為非 admin 帳號設定頁面顯示模板，僅開放指定功能頁面的側邊欄連結，不影響 API 權限。

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
| `users` | 使用者帳號（bcrypt 加密密碼）+ `page_permissions` 頁面模板 |
| `logs` | 所有操作紀錄（支援自動清除） |
| `system_settings` | 系統設定 key-value（POS 預設菜單、紀錄保留天數等） |
| `product_categories` | 產品分類 |
| `products` | 產品主檔（SKU、EAN-13 條碼、成本/售價、庫存警示） |
| `warehouses` | 倉庫資料（含自動生成代碼 WH-XXX） |
| `warehouse_locations` | 倉庫內位置/貨架 |
| `inventory` | 即時庫存（product × warehouse） |
| `stock_movements` | 庫存移動完整歷史（入庫/出庫/POS/盤點/退款均記錄） |
| `inbound_orders` | 入庫單（含 embedded items array） |
| `outbound_orders` | 出庫單（含 embedded items array） |
| `pos_orders` | POS 銷售單（含 embedded items、付款資訊、`source` 欄位區分 POS/外送） |
| `menus` | POS 菜單（含 `categories`、`option_groups`、`items`，全 embedded） |
| `customer_orders` | 顧客點餐訂單（`table_no` / 帳號識別，含品項、客製化選項、狀態） |
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
| nginx 設定 | `conf/nginx/conf.d/default.conf` 不納入版控；從 `*.default` 範本複製後修改 |
| 預設帳號 | `admin / admin`，**首次啟動後立即至後台修改密碼** |
| POS 庫存扣減 | 採 `findOneAndUpdate + $gte` 原子操作，並發失敗自動 rollback，不依賴 MongoDB Transactions（單節點相容） |
| 銷售匯入 | 批次匯入歷史銷售記錄不執行庫存扣減，僅寫入 `pos_orders`，避免影響現有庫存數量 |
| 操作紀錄清除 | 自動清除為懶觸發（每次打開紀錄頁面時檢查），無需額外排程器；保留天數設為 0 則永不自動清除 |
| 出庫確認 | 確認出庫單時自動驗證庫存，庫存不足拒絕確認 |
| 庫存更新時機 | 庫存變更僅在「完成入/出庫」及「POS 結帳/退款」時觸發 |
| Webhook 安全 | 建議設定 `WEBHOOK_SECRET`，系統會驗證 HMAC-SHA256 簽名；留空則略過驗簽（僅開發用） |
| debug 模式 | 預設開啟，正式部署請改用 `ProductionConfig` 並設定 `debug=False` |
| 正式部署 | 建議使用 gunicorn + nginx，不直接暴露 Flask 開發伺服器 |
| POS PWA | `/pos/` 支援「加入主畫面」（PWA），加入後可從手機桌面直接啟動並自動鎖定橫向 |
