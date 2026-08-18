"""
外送平台 Webhooks（不需 JWT）
- POST /delivery/webhook/ubereats
- POST /delivery/webhook/foodpanda
自動接單時依訂單 store_ref 取有效設定（店家優先、回退全域）。
"""
from flask import request, jsonify

from src.models.delivery import DeliveryOrder, DeliverySettings
from src.constants import DeliveryOrderStatus
from app.delivery.views.base import (
    app_delivery, logger, _get_ubereats_client, _get_foodpanda_client,
    create_sale_for_order,
)


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
            normalized = UberEatsClient.normalize_order(body.get('meta', {}).get('resource_href_data', body))
            oid, is_new = DeliveryOrder.upsert_from_normalized(normalized)

            # 自動接單（依訂單所屬店家的有效設定）
            order    = DeliveryOrder.find_by_id(oid)
            settings = DeliverySettings.effective(
                'ubereats', (order or {}).get('store_ref'))
            if is_new and event == 'eats.order.placed' and settings.get('auto_confirm'):
                try:
                    ok = client.accept_order(normalized.get('external_order_id', ''))
                    if ok:
                        DeliveryOrder.update_status(oid, DeliveryOrderStatus.CONFIRMED, operator='system')
                        try:
                            confirmed_order = DeliveryOrder.find_by_id(oid)
                            if confirmed_order:
                                create_sale_for_order(confirmed_order, 'system')
                        except Exception as _e:
                            logger.warning('auto create_from_delivery (ubereats): %s', _e)
                except Exception as _ae:
                    logger.error('UberEats accept_order failed: %s', _ae)

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
            oid, is_new = DeliveryOrder.upsert_from_normalized(normalized)

            order    = DeliveryOrder.find_by_id(oid)
            settings = DeliverySettings.effective(
                'foodpanda', (order or {}).get('store_ref'))
            if is_new and event == 'order.placed' and settings.get('auto_confirm'):
                try:
                    ok = client.confirm_order(normalized.get('external_order_id', ''))
                    if ok:
                        DeliveryOrder.update_status(oid, DeliveryOrderStatus.CONFIRMED, operator='system')
                        try:
                            confirmed_order = DeliveryOrder.find_by_id(oid)
                            if confirmed_order:
                                create_sale_for_order(confirmed_order, 'system')
                        except Exception as _e:
                            logger.warning('auto create_from_delivery (foodpanda): %s', _e)
                except Exception as _ce:
                    logger.error('foodpanda confirm_order failed: %s', _ce)

    except Exception as e:
        logger.exception('foodpanda webhook processing error: %s', e)
        return jsonify({'success': False, 'message': 'internal error'}), 500

    return jsonify({'success': True}), 200
