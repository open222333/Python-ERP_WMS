#!/usr/bin/env python3
"""
WMS 測試資料 Seed 腳本

用法：
  python scripts/seed.py                              # Docker（預設 http://localhost）
  python scripts/seed.py --base http://localhost:5000 # 本機直連 Flask
  python scripts/seed.py --reset                      # 清除後重建（僅開發用）

注意：需先確認 Flask API 已啟動。
"""
import argparse
import sys

try:
    import requests
except ImportError:
    print("缺少 requests：pip install requests")
    sys.exit(1)


# ── 種子資料 ────────────────────────────────────────────────

WAREHOUSES = [
    {"name": "台北倉", "address": "台北市中山區南京東路一段"},
    {"name": "台中倉", "address": "台中市西區台灣大道二段"},
]

CATEGORIES = ["飲料", "食品", "生活用品", "電子配件"]

PRODUCTS = [
    {"name": "礦泉水 500ml",      "category": "飲料",   "sell_price": 20,  "cost_price": 8,   "unit": "瓶", "min_stock": 20},
    {"name": "綠茶 600ml",        "category": "飲料",   "sell_price": 25,  "cost_price": 12,  "unit": "瓶", "min_stock": 20},
    {"name": "可樂 355ml",        "category": "飲料",   "sell_price": 30,  "cost_price": 14,  "unit": "罐", "min_stock": 15},
    {"name": "餅乾（原味）",       "category": "食品",   "sell_price": 45,  "cost_price": 22,  "unit": "包", "min_stock": 10},
    {"name": "洋芋片（起司）",     "category": "食品",   "sell_price": 50,  "cost_price": 26,  "unit": "包", "min_stock": 10},
    {"name": "泡麵（醬油）",       "category": "食品",   "sell_price": 35,  "cost_price": 16,  "unit": "包", "min_stock": 10},
    {"name": "洗手乳 250ml",      "category": "生活用品", "sell_price": 89, "cost_price": 42,  "unit": "瓶", "min_stock": 5},
    {"name": "衛生紙 抽取式 10包", "category": "生活用品", "sell_price": 120,"cost_price": 62,  "unit": "袋", "min_stock": 5},
    {"name": "USB-C 充電線 1m",   "category": "電子配件", "sell_price": 199,"cost_price": 78,  "unit": "條", "min_stock": 5},
    {"name": "有線耳機",           "category": "電子配件", "sell_price": 350,"cost_price": 148, "unit": "支", "min_stock": 3},
]

MENU = {
    "name": "測試菜單",
    "description": "Seed 自動建立的示範菜單",
}

MENU_ITEMS = [
    {"name": "礦泉水",  "price": 20, "category": "飲料"},
    {"name": "綠茶",    "price": 25, "category": "飲料"},
    {"name": "可樂",    "price": 30, "category": "飲料"},
    {"name": "餅乾",    "price": 45, "category": "食品"},
    {"name": "洋芋片",  "price": 50, "category": "食品"},
]

SEED_QTY = 200  # 每個產品在每個倉庫的初始入庫數量


# ── Helper ──────────────────────────────────────────────────

def ok(r, label):
    if r.ok and r.json().get("success"):
        return r.json().get("data") or r.json()
    # 409 / 重複建立視為成功（idempotent）
    if r.status_code == 409:
        return None
    print(f"  ✗ {label} 失敗 [{r.status_code}]: {r.text[:200]}")
    return None


# ── Main ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="WMS Seed 腳本")
    parser.add_argument("--base", default="http://localhost", help="API base URL")
    parser.add_argument("--admin-pass", default="admin", help="admin 密碼")
    args = parser.parse_args()

    BASE = args.base.rstrip("/")
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})

    print(f"→ 連線至 {BASE}")

    # ── 登入 ────────────────────────────────────────────────
    r = s.post(f"{BASE}/auth/login",
               json={"username": "admin", "password": args.admin_pass})
    if not r.ok:
        print(f"登入失敗：{r.status_code} {r.text}")
        sys.exit(1)
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    print("✓ 登入成功\n")

    # ── 倉庫 ────────────────────────────────────────────────
    print("【倉庫】")
    warehouse_ids = {}
    r = s.get(f"{BASE}/warehouse/")
    existing_wh = {w["name"]: w["_id"] for w in r.json().get("data", [])} if r.ok else {}

    for w in WAREHOUSES:
        if w["name"] in existing_wh:
            warehouse_ids[w["name"]] = existing_wh[w["name"]]
            print(f"  ○ 已存在：{w['name']}")
            continue
        data = ok(s.post(f"{BASE}/warehouse/", json=w), w["name"])
        if data:
            warehouse_ids[w["name"]] = data["_id"]
            print(f"  ✓ 建立：{w['name']}")

    # ── 產品分類 ─────────────────────────────────────────────
    print("\n【產品分類】")
    category_ids = {}
    r = s.get(f"{BASE}/product/category/")
    existing_cat = {c["name"]: c["_id"] for c in r.json().get("data", [])} if r.ok else {}

    for cat in CATEGORIES:
        if cat in existing_cat:
            category_ids[cat] = existing_cat[cat]
            print(f"  ○ 已存在：{cat}")
            continue
        data = ok(s.post(f"{BASE}/product/category/", json={"name": cat}), cat)
        if data:
            category_ids[cat] = data["_id"]
            print(f"  ✓ 建立：{cat}")

    # ── 產品 ─────────────────────────────────────────────────
    print("\n【產品】")
    product_ids = []
    r = s.get(f"{BASE}/product/", params={"limit": 200})
    existing_prod = {p["name"]: p["_id"] for p in r.json().get("data", [])} if r.ok else {}

    for p in PRODUCTS:
        if p["name"] in existing_prod:
            product_ids.append(existing_prod[p["name"]])
            print(f"  ○ 已存在：{p['name']}")
            continue
        payload = {
            "name":        p["name"],
            "category_id": category_ids.get(p["category"], ""),
            "sell_price":  p["sell_price"],
            "cost_price":  p["cost_price"],
            "unit":        p["unit"],
            "min_stock":   p["min_stock"],
        }
        data = ok(s.post(f"{BASE}/product/", json=payload), p["name"])
        if data:
            product_ids.append(data["_id"])
            print(f"  ✓ 建立：{p['name']}")

    # ── 初始庫存（入庫單） ────────────────────────────────────
    print("\n【初始庫存（入庫單）】")
    for wname, wid in warehouse_ids.items():
        # 檢查是否已有庫存
        r = s.get(f"{BASE}/inventory/", params={"warehouse_id": wid, "limit": 1})
        if r.ok and r.json().get("data"):
            print(f"  ○ {wname} 已有庫存，跳過")
            continue

        # 建立入庫單
        r = s.post(f"{BASE}/inbound/", json={
            "warehouse_id": wid,
            "supplier":     "Seed 供應商",
            "remark":       "自動建立初始庫存",
        })
        if not r.ok:
            print(f"  ✗ {wname} 建立入庫單失敗")
            continue
        oid = r.json()["data"]["_id"]

        # 新增品項
        for pid in product_ids:
            s.post(f"{BASE}/inbound/{oid}/item", json={
                "product_id":   pid,
                "expected_qty": SEED_QTY,
                "unit_price":   10,
            })

        # 確認 → 完成
        s.post(f"{BASE}/inbound/{oid}/confirm")
        s.post(f"{BASE}/inbound/{oid}/complete")
        print(f"  ✓ {wname}：{len(product_ids)} 種產品各 {SEED_QTY} 件")

    # ── 測試菜單 ─────────────────────────────────────────────
    print("\n【POS 菜單】")
    r = s.get(f"{BASE}/menu/")
    existing_menus = [m["name"] for m in r.json().get("data", [])] if r.ok else []

    if MENU["name"] in existing_menus:
        print(f"  ○ 已存在：{MENU['name']}")
    else:
        data = ok(s.post(f"{BASE}/menu/", json=MENU), MENU["name"])
        if data:
            mid = data["_id"]
            # 建分類
            for cat in set(i["category"] for i in MENU_ITEMS):
                s.post(f"{BASE}/menu/{mid}/category", json={"name": cat})
            # 建品項
            for item in MENU_ITEMS:
                s.post(f"{BASE}/menu/{mid}/item", json={
                    "name":     item["name"],
                    "price":    item["price"],
                    "category": item["category"],
                })
            print(f"  ✓ 建立：{MENU['name']}（{len(MENU_ITEMS)} 個品項）")

    print("\n🌱 Seed 完成！")
    print(f"   後台：{BASE}/admin/")
    print(f"   Swagger：{BASE}/apidocs/")


if __name__ == "__main__":
    main()
