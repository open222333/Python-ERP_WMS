"""
外送平台 Blueprint 基底：blueprint 實例、adapter 取得、共用 helper。
路由分檔：webhooks / orders / menu_sync / mappings / settings（見同目錄）。
"""
import logging

from flask import Blueprint

from src.models.delivery import DeliverySettings

logger = logging.getLogger('app.delivery')
app_delivery = Blueprint('app_delivery', __name__)

DELIVERY_PLATFORMS = ('ubereats', 'foodpanda')


# ─────────────────────────────────────────────
#  內部：取得 adapter 實例
# ─────────────────────────────────────────────
def _get_ubereats_client():
    try:
        from src import UBEREATS_CLIENT_ID, UBEREATS_CLIENT_SECRET, UBEREATS_STORE_ID, UBEREATS_WEBHOOK_SECRET
        from app.delivery.adapters.ubereats import UberEatsClient
        return UberEatsClient(
            client_id      = UBEREATS_CLIENT_ID,
            client_secret  = UBEREATS_CLIENT_SECRET,
            store_id       = UBEREATS_STORE_ID,
            webhook_secret = UBEREATS_WEBHOOK_SECRET,
        )
    except Exception as e:
        logger.error('UberEats client init error: %s', e)
        return None


def _get_foodpanda_client():
    try:
        from src import FOODPANDA_API_KEY, FOODPANDA_VENDOR_CODE, FOODPANDA_BASE_URL, FOODPANDA_WEBHOOK_SECRET
        from app.delivery.adapters.foodpanda import FoodpandaClient
        return FoodpandaClient(
            api_key        = FOODPANDA_API_KEY,
            vendor_code    = FOODPANDA_VENDOR_CODE,
            base_url       = FOODPANDA_BASE_URL,
            webhook_secret = FOODPANDA_WEBHOOK_SECRET,
        )
    except Exception as e:
        logger.error('foodpanda client init error: %s', e)
        return None


# ─────────────────────────────────────────────
#  共用：confirm 後建立銷售紀錄
# ─────────────────────────────────────────────
def create_sale_for_order(order: dict, operator: str) -> dict:
    """
    依訂單 store_ref 取「有效設定」（店家設定優先、空值回退全域），
    有 default_warehouse_id 才建立銷售紀錄並依對應扣庫存。
    回傳 {'sale_id', 'skipped_items'} 或空 dict。
    """
    settings = DeliverySettings.effective(order['platform'], order.get('store_ref'))
    wid = settings.get('default_warehouse_id', '')
    if not wid:
        return {}
    from src.models.pos import PosOrder
    result = PosOrder.create_from_delivery(order, wid, operator, settings=settings)
    return {
        'sale_id':       result.get('sale_id'),
        'skipped_items': result.get('skipped_items', []),
    }
