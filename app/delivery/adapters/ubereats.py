"""
UberEats Marketplace API 串接 (OAuth 2.0 client_credentials)
API Docs: https://developer.uber.com/docs/eats/introduction
"""
import hmac, hashlib, time, json, logging
from datetime import datetime, timedelta
from typing import Optional
import requests

logger = logging.getLogger(__name__)

TOKEN_URL    = 'https://auth.uber.com/oauth/v2/token'
API_BASE     = 'https://api.uber.com'


class UberEatsClient:
    """UberEats API 客戶端 — 自動管理 access_token 生命週期"""

    def __init__(self, client_id: str, client_secret: str, store_id: str,
                 webhook_secret: str = ''):
        self.client_id      = client_id
        self.client_secret  = client_secret
        self.store_id       = store_id
        self.webhook_secret = webhook_secret
        self._token: Optional[str] = None
        self._token_expiry: float  = 0

    # ─────────────────────────────────────────────
    #  Auth
    # ─────────────────────────────────────────────
    def _ensure_token(self):
        if self._token and time.time() < self._token_expiry - 60:
            return
        last_exc = None
        for attempt in range(3):
            try:
                resp = requests.post(TOKEN_URL, data={
                    'client_id':     self.client_id,
                    'client_secret': self.client_secret,
                    'grant_type':    'client_credentials',
                    'scope':         'eats.order eats.store.menu.write eats.store.menu.read',
                }, timeout=10)
                resp.raise_for_status()
                body = resp.json()
                self._token        = body['access_token']
                self._token_expiry = time.time() + body.get('expires_in', 3600)
                return
            except Exception as e:
                last_exc = e
                logger.warning('UberEats token refresh attempt %d failed: %s', attempt + 1, e)
                time.sleep(2 ** attempt)
        raise RuntimeError(f'UberEats token refresh failed after 3 attempts: {last_exc}')

    def _headers(self) -> dict:
        self._ensure_token()
        return {'Authorization': f'Bearer {self._token}',
                'Content-Type': 'application/json'}

    # ─────────────────────────────────────────────
    #  Orders
    # ─────────────────────────────────────────────
    def list_orders(self, status: str = 'active') -> list:
        """列出指定狀態的訂單（active / completed / cancelled）"""
        url = f'{API_BASE}/v1/eats/stores/{self.store_id}/orders'
        r = requests.get(url, headers=self._headers(),
                         params={'status': status}, timeout=10)
        r.raise_for_status()
        return r.json().get('orders', [])

    def get_order(self, order_id: str) -> dict:
        """取得單筆訂單詳情"""
        url = f'{API_BASE}/v1/eats/orders/{order_id}'
        r = requests.get(url, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    def accept_order(self, order_id: str) -> bool:
        """接受訂單"""
        url = f'{API_BASE}/v1/eats/orders/{order_id}/accept_pos_order'
        r = requests.post(url, headers=self._headers(),
                          json={'reason': 'READY_FOR_PICKUP'}, timeout=10)
        return r.status_code == 200

    def deny_order(self, order_id: str, reason: str = 'OUT_OF_ITEMS') -> bool:
        """拒絕 / 取消訂單"""
        url = f'{API_BASE}/v1/eats/orders/{order_id}/deny_pos_order'
        r = requests.post(url, headers=self._headers(),
                          json={'reason': reason}, timeout=10)
        return r.status_code == 200

    # ─────────────────────────────────────────────
    #  Menu
    # ─────────────────────────────────────────────
    def get_menu(self) -> dict:
        """取得目前菜單"""
        url = f'{API_BASE}/v2/eats/stores/{self.store_id}/menu'
        r = requests.get(url, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    def upsert_menu(self, menu_payload: dict) -> dict:
        """全量更新菜單（POST = 完整覆蓋）"""
        url = f'{API_BASE}/v2/eats/stores/{self.store_id}/menu'
        r = requests.post(url, headers=self._headers(),
                          json=menu_payload, timeout=15)
        r.raise_for_status()
        return r.json()

    def update_item_price(self, menu_item_id: str, price_cents: int) -> bool:
        """修改單品價格（PATCH）"""
        url = f'{API_BASE}/v2/eats/stores/{self.store_id}/menu/items/{menu_item_id}'
        r = requests.patch(url, headers=self._headers(),
                           json={'price_info': {'price': price_cents}}, timeout=10)
        return r.status_code == 200

    def set_item_availability(self, menu_item_id: str, available: bool) -> bool:
        """下架 / 上架品項"""
        url = f'{API_BASE}/v2/eats/stores/{self.store_id}/menu/items/{menu_item_id}/availability'
        r = requests.post(url, headers=self._headers(),
                          json={'is_suspended': not available}, timeout=10)
        return r.status_code == 200

    # ─────────────────────────────────────────────
    #  Webhook 驗簽
    # ─────────────────────────────────────────────
    def verify_webhook(self, payload_bytes: bytes, signature: str) -> bool:
        """
        驗證 UberEats webhook X-Uber-Signature header。
        signature = HMAC-SHA256(secret, payload)
        """
        if not self.webhook_secret:
            logger.error('UberEats webhook_secret 未設定，所有 webhook 請求將被拒絕（請在設定檔加入 [UBEREATS] WEBHOOK_SECRET）')
            return False
        expected = hmac.new(
            self.webhook_secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ─────────────────────────────────────────────
    #  正規化：UberEats 訂單 → 標準格式
    # ─────────────────────────────────────────────
    @staticmethod
    def normalize_order(raw: dict) -> dict:
        """將 UberEats 原始訂單轉成系統內部通用格式"""
        cart = raw.get('cart', {})
        items = []
        for item in cart.get('items', []):
            items.append({
                'external_id':   item.get('id', ''),
                'product_name':  item.get('title', ''),
                'quantity':      item.get('quantity', 1),
                'unit_price':    item.get('price', {}).get('unit_price', {}).get('amount', 0) / 100,
                'subtotal':      item.get('price', {}).get('total_price', {}).get('amount', 0) / 100,
                'options':       [o.get('title','') for g in item.get('selected_modifier_groups',[])
                                  for o in g.get('selected_items', [])],
            })
        payment = raw.get('payment', {})
        _sub_amt = payment.get('charges', {}).get('sub_total', {}).get('amount')
        subtotal = (_sub_amt / 100 if _sub_amt is not None else
                    sum(i.get('price', {}).get('total_price', {}).get('amount', 0)
                        for i in cart.get('items', [])) / 100)
        return {
            'platform':         'ubereats',
            'external_order_id': raw.get('id', ''),
            'order_no':         raw.get('display_id', ''),
            'status':           raw.get('current_state', '').lower(),
            'customer_name':    raw.get('eater', {}).get('first_name', ''),
            'items':            items,
            'subtotal':         subtotal,
            'total_amount':     payment.get('charges', {}).get('total', {}).get('amount', 0) / 100,
            'payment_method':   payment.get('payment_method_info', [{}])[0].get('payment_method_family', 'online'),
            'note':             cart.get('special_instructions', ''),
            'placed_at':        raw.get('placed_at', ''),
            'estimated_pickup_at': raw.get('estimated_ready_for_pickup_at', ''),
            'raw':              raw,
        }


def parse_menu_items(menu: dict) -> list:
    """
    將 UberEats GET /menu 回應解析成統一格式：
    [{'external_id', 'name', 'description', 'price', 'available', 'category',
      'modifier_group_ids'}]
    """
    # 建立 item_id → 分類名稱 的反向對應
    item_category: dict = {}
    for cat in menu.get('categories', []):
        cat_name = cat.get('title', '').strip()
        for entity in cat.get('entities', []):
            eid = entity.get('id', '') if isinstance(entity, dict) else (entity or '')
            if eid:
                item_category[eid] = cat_name

    items = []
    for item in menu.get('items', []):
        price_info  = item.get('price_info', {})
        price_cents = price_info.get('price') or price_info.get('core_price') or 0
        suspension  = item.get('suspension_info', {}).get('suspension', {})
        item_id     = item.get('id', '')
        # 抽取本品項連結的 modifier group external_id 清單
        mg_refs = item.get('modifier_group_ids_sorted_with_type') or []
        modifier_group_ids = [
            r['id'] for r in mg_refs if isinstance(r, dict) and r.get('id')
        ]
        items.append({
            'external_id':        item_id,
            'name':               item.get('title', '').strip(),
            'description':        item.get('description', ''),
            'price':              round(price_cents / 100, 2),
            'available':          not suspension.get('suspend', False),
            'category':           item_category.get(item_id, ''),
            'modifier_group_ids': modifier_group_ids,
        })
    return items


def parse_option_groups(menu: dict) -> list:
    """
    將 UberEats GET /menu 中的 modifier_groups 解析為 WMS option_group 格式：
    [{'external_id', 'name', 'type', 'required', 'choices':[{name, extra_price, is_default}]}]
    UberEats 的 quantity_info 結構較複雜，預設解析為 single/optional；
    使用者可在菜單管理介面手動調整。
    """
    groups = []
    for mg in menu.get('modifier_groups', []):
        choices = []
        for it in mg.get('items', []):
            pi = it.get('price_info') or {}
            price_cents = pi.get('price') or pi.get('core_price') or 0
            label = (it.get('title') or '').strip()
            if label:
                choices.append({
                    'name':        label,
                    'extra_price': round(price_cents / 100, 2),
                    'is_default':  False,
                })
        if not choices:
            continue
        groups.append({
            'external_id': mg.get('id', ''),
            'name':        (mg.get('title') or '').strip(),
            'type':        'single',   # 預設單選；如需多選可在 WMS 手動改
            'required':    False,      # 預設選填
            'choices':     choices,
        })
    return groups


def build_menu_from_products(products: list, category_name: str = '商品') -> dict:
    """
    將系統 products 列表轉成 UberEats Menu API v2 格式。
    price 單位：分（新台幣 × 100）
    """
    items = []
    for p in products:
        if p.get('status', 1) != 1:
            continue
        items.append({
            'id':    p['_id'],
            'title': p['name'],
            'description': p.get('description', ''),
            'price_info': {
                'price': int(float(p.get('sell_price', 0)) * 100),
                'core_price': int(float(p.get('sell_price', 0)) * 100),
            },
            'quantity_info': {'overrides': []},
            'suspension_info': {'suspension': {'suspend': False}},
        })

    return {
        'menus': [{
            'id':         'main-menu',
            'title':      '主選單',
            'service_availability': [
                {'day_of_week': d, 'time_periods': [{'start_time': '00:00', 'end_time': '23:59'}]}
                for d in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
            ],
            'category_ids_sorted_with_type': [
                {'id': 'cat-default', 'type': 'DEFAULT_MENU_CATEGORY'}
            ],
        }],
        'categories': [{
            'id':       'cat-default',
            'title':    category_name,
            'entities': [{'id': i['id'], 'type': 'ITEM'} for i in items],
        }],
        'items': items,
        'modifier_groups': [],
    }
