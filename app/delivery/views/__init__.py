"""
外送平台 views 套件：base 定義 blueprint，其餘模組 import 時完成路由註冊。
"""
from app.delivery.views.base import app_delivery  # noqa: F401
from app.delivery.views import (  # noqa: E402,F401 —— 路由註冊
    webhooks, orders, menu_sync, mappings, settings,
)
