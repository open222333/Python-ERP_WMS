"""
外送訂單管理
- GET /delivery/orders
- GET /delivery/orders/<oid>
- PUT /delivery/orders/<oid>/status
- POST /delivery/sync/<platform>（主動拉取訂單）
"""
from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.models.delivery import DeliveryOrder, DeliverySettings
from src.models.log import Log
from src.permissions import require_role
from src.constants import DeliveryOrderStatus
from app.delivery.views.base import (
    app_delivery, logger, _get_ubereats_client, _get_foodpanda_client,
    create_sale_for_order,
)


@app_delivery.route('/orders', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator', 'cashier')
def list_orders():
    """
    查詢外送訂單列表
    ---
    tags:
      - Delivery
    security:
      - Bearer: []
    parameters:
      - {in: query, name: platform,   type: string, description: "ubereats / foodpanda"}
      - {in: query, name: status,     type: string}
      - {in: query, name: date_from,  type: string, description: "YYYY-MM-DD"}
      - {in: query, name: date_to,    type: string, description: "YYYY-MM-DD"}
      - {in: query, name: limit,      type: integer}
    responses:
      200:
        description: 成功
    """
    platform     = request.args.get('platform', '')
    status       = request.args.get('status', '')
    date_from_s  = request.args.get('date_from', '')
    date_to_s    = request.args.get('date_to', '')
    limit        = int(request.args.get('limit', 200))

    date_from = datetime.strptime(date_from_s, '%Y-%m-%d') if date_from_s else None
    date_to   = datetime.strptime(date_to_s + ' 23:59:59', '%Y-%m-%d %H:%M:%S') if date_to_s else None

    data = DeliveryOrder.find_all(
        platform=platform or None,
        status=status or None,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return jsonify({'success': True, 'data': data})


@app_delivery.route('/orders/<oid>', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator', 'cashier')
def get_order(oid):
    """
    查詢單筆外送訂單
    ---
    tags:
      - Delivery
    security:
      - Bearer: []
    parameters:
      - {in: path, name: oid, type: string, required: true}
    responses:
      200:
        description: 成功
      404:
        description: 不存在
    """
    try:
        oid = ObjectId(oid)
    except (InvalidId, Exception):
        return jsonify({'success': False, 'message': 'ID 格式無效'}), 400
    order = DeliveryOrder.find_by_id(oid)
    if not order:
        return jsonify({'success': False, 'message': '訂單不存在'}), 404
    return jsonify({'success': True, 'data': order})


@app_delivery.route('/orders/<oid>/status', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_order_status(oid):
    """
    更新外送訂單狀態
    ---
    tags:
      - Delivery
    security:
      - Bearer: []
    parameters:
      - {in: path, name: oid, type: string, required: true}
      - in: body
        name: body
        schema:
          required: [status]
          properties:
            status: {type: string, enum: [confirmed, preparing, ready, cancelled]}
    responses:
      200:
        description: 成功
      400:
        description: 失敗
    """
    try:
        oid = ObjectId(oid)
    except (InvalidId, Exception):
        return jsonify({'success': False, 'message': 'ID 格式無效'}), 400

    data   = request.get_json(silent=True) or {}
    status = data.get('status', '').strip()
    if not status:
        return jsonify({'success': False, 'message': '請指定狀態'}), 400

    order = DeliveryOrder.find_by_id(oid)
    if not order:
        return jsonify({'success': False, 'message': '訂單不存在'}), 404

    # 同步更新到原平台
    try:
        if order['platform'] == 'ubereats':
            client = _get_ubereats_client()
            if client:
                if status == DeliveryOrderStatus.CONFIRMED:
                    client.accept_order(order['external_order_id'])
                elif status == DeliveryOrderStatus.CANCELLED:
                    client.deny_order(order['external_order_id'])
        elif order['platform'] == 'foodpanda':
            client = _get_foodpanda_client()
            if client:
                if status == DeliveryOrderStatus.CONFIRMED:
                    client.confirm_order(order['external_order_id'])
                elif status == DeliveryOrderStatus.CANCELLED:
                    client.cancel_order(order['external_order_id'])
    except Exception as e:
        logger.warning('Platform status sync error: %s', e)

    ok = DeliveryOrder.update_status(oid, status, operator=get_jwt_identity())
    if not ok:
        return jsonify({'success': False, 'message': '狀態更新失敗，請確認狀態值'}), 400

    # ── 確認接單時自動建立銷售紀錄（店家設定優先、回退全域）──
    sale_info = {}
    if status == DeliveryOrderStatus.CONFIRMED:
        try:
            sale_info = create_sale_for_order(order, get_jwt_identity())
        except Exception as e:
            logger.warning('create_from_delivery error: %s', e)

    Log.create(get_jwt_identity(), '外送訂單狀態',
               f'order_id={oid} status={status}')
    return jsonify({'success': True, **sale_info})


# ─────────────────────────────────────────────
#  主動拉取訂單
# ─────────────────────────────────────────────
@app_delivery.route('/sync/<platform>', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def sync_orders(platform):
    """
    主動從平台拉取最新訂單
    ---
    tags:
      - Delivery
    security:
      - Bearer: []
    parameters:
      - {in: path, name: platform, type: string, required: true, description: "ubereats / foodpanda"}
    responses:
      200:
        description: 成功，回傳新增筆數
      400:
        description: 平台未設定或錯誤
    """
    new_count = 0
    errors    = []

    try:
        if platform == 'ubereats':
            from app.delivery.adapters.ubereats import UberEatsClient
            client = _get_ubereats_client()
            if not client or not client.client_id:
                return jsonify({'success': False, 'message': 'UberEats 尚未設定 API 金鑰'}), 400
            raw_orders = client.list_orders(status='active')
            for raw in raw_orders:
                normalized       = UberEatsClient.normalize_order(raw)
                _, is_new        = DeliveryOrder.upsert_from_normalized(normalized)
                if is_new:
                    new_count += 1

        elif platform == 'foodpanda':
            from app.delivery.adapters.foodpanda import FoodpandaClient
            client = _get_foodpanda_client()
            if not client or not client.api_key:
                return jsonify({'success': False, 'message': 'foodpanda 尚未設定 API 金鑰'}), 400
            # 傳給 foodpanda 平台 API 的查詢參數（非本系統內部狀態，維持字面值）
            for status in ('new', 'confirmed'):
                raw_orders = client.list_orders(status=status)
                for raw in raw_orders:
                    normalized = FoodpandaClient.normalize_order(raw)
                    _, is_new  = DeliveryOrder.upsert_from_normalized(normalized)
                    if is_new:
                        new_count += 1

        else:
            return jsonify({'success': False, 'message': '不支援的平台'}), 400

    except Exception as e:
        errors.append(str(e))
        logger.exception('sync_orders error [%s]: %s', platform, e)

    DeliverySettings.upsert(platform, last_sync=datetime.utcnow().isoformat())
    Log.create(get_jwt_identity(), '外送訂單同步',
               f'platform={platform} new={new_count} errors={len(errors)}')
    return jsonify({
        'success':   True,
        'new_count': new_count,
        'errors':    errors,
    })
