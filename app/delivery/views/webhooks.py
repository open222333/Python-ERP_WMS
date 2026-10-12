"""
外送平台 Webhooks（不需 JWT）
- POST /delivery/webhook/ubereats
- POST /delivery/webhook/foodpanda

[D1][D2] 訂單寫入與狀態推進一律經 src/services/delivery_service：
平台狀態先由 adapter 轉成內部狀態；平台端取消會作廢銷售並回補庫存；
平台端已接單（不論是否由本系統接單）會建立銷售並扣庫存。
自動接單時依訂單 store_ref 取有效設定（店家優先、回退全域）。
"""
from flask import request, jsonify

from src.models.delivery import DeliveryOrder, DeliverySettings
from src.constants import DeliveryOrderStatus
from src.services import delivery_service
from app.delivery.views.base import (
    app_delivery, logger, _get_ubereats_client, _get_foodpanda_client,
)


def _auto_confirm(platform: str, oid: str, accept_fn) -> None:
    """新單且店家設定自動接單：先呼叫平台接單 API，成功才在本系統轉為 confirmed。"""
    order = DeliveryOrder.find_by_id(oid)
    if not order or order['status'] != DeliveryOrderStatus.NEW:
        return
    settings = DeliverySettings.effective(platform, order.get('store_ref'))
    if not settings.get('auto_confirm'):
        return
    try:
        if accept_fn(order.get('external_order_id', '')):
            delivery_service.change_status(oid, DeliveryOrderStatus.CONFIRMED, 'system')
    except Exception as e:
        logger.error('%s 自動接單失敗 order=%s：%s', platform, oid, e)


@app_delivery.route('/webhook/ubereats', methods=['POST'])
def webhook_ubereats():
    """
    接收 UberEats 推播通知
    ---
    tags:
      - Delivery
    responses:
      200:
        description: 已接收
    """
    payload = request.get_data()
    sig     = request.headers.get('X-Uber-Signature', '')

    client = _get_ubereats_client()
    if not client:
        return jsonify({'success': False, 'message': 'UberEats 未設定'}), 503
    if not client.verify_webhook(payload, sig):
        return jsonify({'success': False, 'message': '簽名驗證失敗'}), 403

    try:
        body  = request.get_json(force=True) or {}
        event = body.get('event_type', '')

        if event in ('eats.order.placed', 'eats.order.updated'):
            from app.delivery.adapters.ubereats import UberEatsClient
            normalized = UberEatsClient.normalize_order(
                body.get('meta', {}).get('resource_href_data', body))
            oid, is_new, _ = delivery_service.ingest_normalized(normalized)
            if is_new and event == 'eats.order.placed':
                _auto_confirm('ubereats', oid, client.accept_order)

    except Exception as e:
        logger.exception('UberEats webhook processing error: %s', e)
        return jsonify({'success': False, 'message': 'internal error'}), 500

    return jsonify({'success': True}), 200


@app_delivery.route('/webhook/foodpanda', methods=['POST'])
def webhook_foodpanda():
    """
    接收 foodpanda 推播通知
    ---
    tags:
      - Delivery
    responses:
      200:
        description: 已接收
    """
    payload = request.get_data()
    sig     = request.headers.get('X-FP-Signature', '')

    client = _get_foodpanda_client()
    if not client:
        return jsonify({'success': False, 'message': 'foodpanda 未設定'}), 503
    if not client.verify_webhook(payload, sig):
        return jsonify({'success': False, 'message': '簽名驗證失敗'}), 403

    try:
        body  = request.get_json(force=True) or {}
        event = body.get('event', '')

        if event in ('order.placed', 'order.status_updated'):
            from app.delivery.adapters.foodpanda import FoodpandaClient
            normalized = FoodpandaClient.normalize_order(body.get('order', body))
            oid, is_new, _ = delivery_service.ingest_normalized(normalized)
            if is_new and event == 'order.placed':
                _auto_confirm('foodpanda', oid, client.confirm_order)

    except Exception as e:
        logger.exception('foodpanda webhook processing error: %s', e)
        return jsonify({'success': False, 'message': 'internal error'}), 500

    return jsonify({'success': True}), 200
