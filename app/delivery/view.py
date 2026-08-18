"""
外送平台管理 Blueprint（相容入口）
[REFACTOR] 原 795 行路由已拆分至 app/delivery/views/ 套件：
  base.py      — blueprint、adapter 取得、create_sale_for_order
  webhooks.py  — /webhook/ubereats、/webhook/foodpanda
  orders.py    — /orders*、/sync/<platform>
  menu_sync.py — /menu/sync/<platform>
  mappings.py  — /mappings*、/mapping-templates/*
  settings.py  — /settings/<platform>、/store/*
既有 `from app.delivery.view import app_delivery` 匯入路徑維持不變。
"""
from app.delivery.views import app_delivery  # noqa: F401
