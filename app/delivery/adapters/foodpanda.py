"""
foodpanda / Delivery Hero Vendor API 串接 (API Key auth)
API 文件需向 foodpanda 商業夥伴申請存取
TW base URL: https://tw.fd-api.com
"""
import hmac, hashlib, json, logging
import requests

logger = logging.getLogger(__name__)


class FoodpandaClient:
    """foodpanda Vendor API 客戶端"""

    def __init__(self, api_key: str, vendor_code: str,
                 base_url: str = 'https://tw.fd-api.com',
                 webhook_secret: str = ''):
        self.api_key        = api_key
        self.vendor_code    = vendor_code
        self.base_url       = base_url.rstrip('/')
        self.webhook_secret = webhook_secret

    # ─────────────────────────────────────────────
    #  Auth headers
    # ─────────────────────────────────────────────
    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type':  'application/json',
            'Accept':        'application/json',
        }

    # ─────────────────────────────────────────────
    #  Orders
    # ─────────────────────────────────────────────
    def list_orders(self, status: str = 'confirmed', limit: int = 50) -> list:
        """
        列出訂單
        status: new / confirmed / delivered / cancelled
        """
        url = f'{self.base_url}/api/v5/vendors/{self.vendor_code}/orders'
        r = requests.get(url, headers=self._headers(),
                         params={'status': status, 'limit': limit}, timeout=10)
        r.raise_for_status()
        return r.json().get('data', {}).get('items', [])

    def get_order(self, order_code: str) -> dict:
        """取得單筆訂單詳情"""
        url = f'{self.base_url}/api/v5/orders/{order_code}'
        r = requests.get(url, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json().get('data', {})

    def confirm_order(self, order_code: str, prep_time_minutes: int = 20) -> bool:
        """接受訂單並設定備餐時間"""
        url = f'{self.base_url}/api/v5/orders/{order_code}/status'
        r = requests.put(url, headers=self._headers(), json={
            'status': 'confirmed',
            'preparation_time': prep_time_minutes,
        }, timeout=10)
        return r.status_code in (200, 204)

    def cancel_order(self, order_code: str, reason_code: str = 'VENDOR_BUSY') -> bool:
        """取消訂單"""
        url = f'{self.base_url}/api/v5/orders/{order_code}/status'
        r = requests.put(url, headers=self._headers(), json={
            'status':       'cancelled',
            'reason_code':  reason_code,
        }, timeout=10)
        return r.status_code in (200, 204)

    # ─────────────────────────────────────────────
    #  Menu
    # ─────────────────────────────────────────────
    def get_menu(self) -> dict:
        """取得完整菜單"""
        url = f'{self.base_url}/api/v5/vendors/{self.vendor_code}/menu'
        r = requests.get(url, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json().get('data', {})

    def update_menu(self, menu_payload: dict) -> dict:
        """全量更新菜單"""
        url = f'{self.base_url}/api/v5/vendors/{self.vendor_code}/menu'
        r = requests.put(url, headers=self._headers(),
                         json=menu_payload, timeout=15)
        r.raise_for_status()
        return r.json()

    def update_product_availability(self, product_id: str,
                                    available: bool) -> bool:
        """更新單品上架 / 下架狀態"""
        url = f'{self.base_url}/api/v5/vendors/{self.vendor_code}/menu/products/{product_id}'
        r = requests.patch(url, headers=self._headers(), json={
            'active': available,
        }, timeout=10)
        return r.status_code in (200, 204)

    def update_product_price(self, product_id: str, price: float) -> bool:
        """更新單品售價（原幣，非分）"""
        url = f'{self.base_url}/api/v5/vendors/{self.vendor_code}/menu/products/{product_id}'
        r = requests.patch(url, headers=self._headers(), json={
            'price': price,
        }, timeout=10)
        return r.status_code in (200, 204)

    # ─────────────────────────────────────────────
    #  Webhook 驗簽
    # ─────────────────────────────────────────────
    def verify_webhook(self, payload_bytes: bytes, signature: str) -> bool:
        """
        驗證 foodpanda webhook X-FP-Signature header。
        signature = HMAC-SHA256(secret, payload)
        """
        if not self.webhook_secret:
            return True
        expected = hmac.new(
            self.webhook_secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ─────────────────────────────────────────────
    #  正規化：foodpanda 訂單 → 標準格式
    # ─────────────────────────────────────────────
    @staticmethod
    def normalize_order(raw: dict) -> dict:
        """將 foodpanda 原始訂單轉成系統內部通用格式"""
        products = raw.get('products', [])
        items = []
        for p in products:
            items.append({
                'external_id':  str(p.get('id', '')),
                'product_name': p.get('name', ''),
                'quantity':     p.get('quantity', 1),
                'unit_price':   float(p.get('unit_price', 0)),
                'subtotal':     float(p.get('unit_price', 0)) * p.get('quantity', 1),
                'options':      [t.get('name', '') for t in p.get('topping_ids', [])],
            })
        customer = raw.get('customer', {})
        order_total = raw.get('order_total', {})
        return {
            'platform':          'foodpanda',
            'external_order_id': raw.get('code', ''),
            'order_no':          raw.get('code', ''),
            'status':            raw.get('status', {}).get('code', '').lower(),
            'customer_name':     f"{customer.get('first_name','')} {customer.get('last_name','')}".strip(),
            'customer_phone':    customer.get('mobile_number', ''),
            'items':             items,
            'subtotal':          float(order_total.get('subtotal', 0)),
            'delivery_fee':      float(order_total.get('delivery_fee', 0)),
            'total_amount':      float(order_total.get('grand_total', 0)),
            'payment_method':    raw.get('payment', {}).get('type', 'online'),
            'note':              raw.get('customer_comment', ''),
            'placed_at':         raw.get('placed_at', ''),
            'estimated_pickup_at': raw.get('estimated_delivery_time', ''),
            'raw':               raw,
        }


def parse_menu_items(menu: dict) -> list:
    """
    將 foodpanda GET /menu 回應解析成統一格式：
    [{'external_id', 'name', 'description', 'price', 'available', 'category',
      'modifier_group_ids'}]
    """
    items = []
    for cat in menu.get('categories', []):
        cat_name = cat.get('name', '').strip()
        for p in cat.get('products', []):
            # 取得此品項連結的 topping group ID 清單
            modifier_group_ids = [
                str(tg.get('id', ''))
                for tg in p.get('topping_groups', [])
                if tg.get('id')
            ]
            items.append({
                'external_id':        str(p.get('id', '')),
                'name':               p.get('name', '').strip(),
                'description':        p.get('description', ''),
                'price':              float(p.get('price', 0)),
                'available':          bool(p.get('active', True)),
                'category':           cat_name,
                'modifier_group_ids': modifier_group_ids,
            })
    return items


def parse_option_groups(menu: dict) -> list:
    """
    將 foodpanda GET /menu 中各 product 的 topping_groups 抽取並去重（依 topping group ID），
    解析為 WMS option_group 格式：
    [{'external_id', 'name', 'type', 'required', 'choices':[{name, extra_price, is_default}]}]
    同一 topping group ID 跨多個品項只保留一份；name 衝突時以先出現者為準。
    """
    seen_ids: set = set()
    groups = []
    for cat in menu.get('categories', []):
        for p in cat.get('products', []):
            for tg in p.get('topping_groups', []):
                tg_id = str(tg.get('id', ''))
                if not tg_id or tg_id in seen_ids:
                    continue
                seen_ids.add(tg_id)
                choices = []
                for t in tg.get('toppings', []):
                    label = (t.get('name') or '').strip()
                    if label:
                        choices.append({
                            'name':        label,
                            'extra_price': float(t.get('price', 0)),
                            'is_default':  bool(t.get('is_default', False)),
                        })
                if not choices:
                    continue
                max_t = tg.get('max_toppings', 1) or 1
                groups.append({
                    'external_id': tg_id,
                    'name':        (tg.get('name') or '').strip(),
                    'type':        'multiple' if max_t != 1 else 'single',
                    'required':    bool(tg.get('is_mandatory', False)),
                    'choices':     choices,
                })
    return groups


def build_menu_from_products(products: list,
                              category_name: str = '全部商品') -> dict:
    """
    將系統 products 列表轉成 foodpanda Menu API 格式。
    """
    fp_products = []
    for p in products:
        if p.get('status', 1) != 1:
            continue
        fp_products.append({
            'id':          p['_id'],
            'name':        p['name'],
            'description': p.get('description', ''),
            'price':       float(p.get('sell_price', 0)),
            'active':      True,
        })

    return {
        'categories': [{
            'id':      'cat-default',
            'name':    category_name,
            'products': fp_products,
        }],
    }
