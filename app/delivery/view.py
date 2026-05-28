"""
外送平台管理 Blueprint
- /delivery/webhook/ubereats     POST  (UberEats webhook)
- /delivery/webhook/foodpanda    POST  (foodpanda webhook)
- /delivery/orders               GET
- /delivery/orders/<oid>         GET
- /delivery/orders/<oid>/status  PUT
- /delivery/sync/<platform>      POST  (主動拉取訂單)
- /delivery/menu/sync/<platform> POST  (從平台拉取菜單 → 菜單管理)
- /delivery/mappings             GET/POST
- /delivery/mappings/<mid>       DELETE
- /delivery/settings/<platform>  GET/PUT
"""
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.delivery import DeliveryOrder, DeliveryMapping, DeliverySettings
from src.models.log import Log
from src.permissions import require_role

logger = logging.getLogger(__name__)
app_delivery = Blueprint('app_delivery', __name__)


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
#  Webhooks（不需 JWT）
# ─────────────────────────────────────────────
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
    if client and not client.verify_webhook(payload, sig):
        return jsonify({'success': False, 'message': '簽名驗證失敗'}), 403

    try:
        body  = request.get_json(force=True) or {}
        event = body.get('event_type', '')

        if event in ('eats.order.placed', 'eats.order.updated'):
            from app.delivery.adapters.ubereats import UberEatsClient
            normalized = UberEatsClient.normalize_order(body.get('meta', {}).get('resource_href_data', body))
            oid, is_new = DeliveryOrder.upsert_from_normalized(normalized)

            # 自動接單
            settings = DeliverySettings.get('ubereats')
            if is_new and event == 'eats.order.placed' and settings.get('auto_confirm'):
                if client:
                    client.accept_order(normalized.get('external_order_id', ''))
                DeliveryOrder.update_status(oid, 'confirmed', operator='system')
                wid = settings.get('default_warehouse_id', '')
                if wid:
                    try:
                        from src.models.pos import PosOrder
                        confirmed_order = DeliveryOrder.find_by_id(oid)
                        if confirmed_order:
                            PosOrder.create_from_delivery(confirmed_order, wid, 'system')
                    except Exception as _e:
                        logger.warning('auto create_from_delivery (ubereats): %s', _e)

    except Exception as e:
        logger.exception('UberEats webhook processing error: %s', e)

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
    if client and not client.verify_webhook(payload, sig):
        return jsonify({'success': False, 'message': '簽名驗證失敗'}), 403

    try:
        body  = request.get_json(force=True) or {}
        event = body.get('event', '')

        if event in ('order.placed', 'order.status_updated'):
            from app.delivery.adapters.foodpanda import FoodpandaClient
            normalized = FoodpandaClient.normalize_order(body.get('order', body))
            oid, is_new = DeliveryOrder.upsert_from_normalized(normalized)

            settings = DeliverySettings.get('foodpanda')
            if is_new and event == 'order.placed' and settings.get('auto_confirm'):
                if client:
                    client.confirm_order(normalized.get('external_order_id', ''))
                DeliveryOrder.update_status(oid, 'confirmed', operator='system')
                wid = settings.get('default_warehouse_id', '')
                if wid:
                    try:
                        from src.models.pos import PosOrder
                        confirmed_order = DeliveryOrder.find_by_id(oid)
                        if confirmed_order:
                            PosOrder.create_from_delivery(confirmed_order, wid, 'system')
                    except Exception as _e:
                        logger.warning('auto create_from_delivery (foodpanda): %s', _e)

    except Exception as e:
        logger.exception('foodpanda webhook processing error: %s', e)

    return jsonify({'success': True}), 200


# ─────────────────────────────────────────────
#  訂單管理
# ─────────────────────────────────────────────
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
                if status == 'confirmed':
                    client.accept_order(order['external_order_id'])
                elif status == 'cancelled':
                    client.deny_order(order['external_order_id'])
        elif order['platform'] == 'foodpanda':
            client = _get_foodpanda_client()
            if client:
                if status == 'confirmed':
                    client.confirm_order(order['external_order_id'])
                elif status == 'cancelled':
                    client.cancel_order(order['external_order_id'])
    except Exception as e:
        logger.warning('Platform status sync error: %s', e)

    ok = DeliveryOrder.update_status(oid, status, operator=get_jwt_identity())
    if not ok:
        return jsonify({'success': False, 'message': '狀態更新失敗，請確認狀態值'}), 400

    # ── 確認接單時自動建立銷售紀錄 ────────────────────
    sale_info = {}
    if status == 'confirmed':
        settings = DeliverySettings.get(order['platform'])
        wid = settings.get('default_warehouse_id', '')
        if wid:
            try:
                from src.models.pos import PosOrder
                result = PosOrder.create_from_delivery(order, wid, get_jwt_identity())
                sale_info = {
                    'sale_id':       result.get('sale_id'),
                    'skipped_items': result.get('skipped_items', []),
                }
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
               f'platform={platform} new={new_count}')
    return jsonify({
        'success': len(errors) == 0,
        'new_count': new_count,
        'errors': errors,
    })


# ─────────────────────────────────────────────
#  菜單同步（從平台拉回，建立 / 更新菜單管理品項）
# ─────────────────────────────────────────────
_PLATFORM_MENU_LABEL = {
    'ubereats':  'UberEats 菜單',
    'foodpanda': 'foodpanda 菜單',
}


@app_delivery.route('/menu/sync/<platform>', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def sync_menu(platform):
    """
    從外送平台拉取菜單，在「菜單管理」中建立或更新品項。
    - 若尚無該平台菜單 → 自動建立（名稱：「UberEats 菜單」/ 「foodpanda 菜單」）
    - 同名品項（不分大小寫）→ 更新售價 / 描述 / 分類
    - 新品項 → 新增（consume_inventory=False，可事後在菜單管理手動設定）
    ---
    tags:
      - Delivery
    security:
      - Bearer: []
    parameters:
      - {in: path, name: platform, type: string, required: true,
         description: "ubereats / foodpanda"}
    responses:
      200:
        description: "回傳 menu_id / created / updated / skipped 各筆數"
      400:
        description: 平台未設定或 API 呼叫失敗
    """
    from src.models.menu import Menu

    # ── 取得平台菜單 ──────────────────────────────
    try:
        if platform == 'ubereats':
            from app.delivery.adapters.ubereats import parse_menu_items, parse_option_groups
            client = _get_ubereats_client()
            if not client or not client.client_id:
                return jsonify({'success': False,
                                'message': 'UberEats 尚未設定 API 金鑰'}), 400
            raw_menu      = client.get_menu()
            items         = parse_menu_items(raw_menu)
            option_groups = parse_option_groups(raw_menu)

        elif platform == 'foodpanda':
            from app.delivery.adapters.foodpanda import parse_menu_items, parse_option_groups
            client = _get_foodpanda_client()
            if not client or not client.api_key:
                return jsonify({'success': False,
                                'message': 'foodpanda 尚未設定 API 金鑰'}), 400
            raw_menu      = client.get_menu()
            items         = parse_menu_items(raw_menu)
            option_groups = parse_option_groups(raw_menu)

        else:
            return jsonify({'success': False, 'message': '不支援的平台'}), 400

    except Exception as e:
        logger.exception('sync_menu pull error [%s]: %s', platform, e)
        return jsonify({'success': False, 'message': str(e)}), 400

    # ── 找或建立對應菜單 ──────────────────────────
    menu_name = _PLATFORM_MENU_LABEL.get(platform, f'{platform} 菜單')
    all_menus = Menu.find_all()
    platform_menu = next((m for m in all_menus if m['name'] == menu_name), None)

    if platform_menu:
        mid = platform_menu['_id']
        platform_menu = Menu.find_by_id(mid)   # 重新取含品項與選項組的完整資料
    else:
        mid = Menu.create(
            name=menu_name,
            description=f'從 {menu_name} 自動同步',
            sort_order=0,
        )
        platform_menu = Menu.find_by_id(mid)

    # ── 同步選項組（modifier / topping groups）───
    # name.lower() → existing WMS option_group dict
    existing_ogs = {
        og['name'].lower(): og
        for og in (platform_menu.get('option_groups') or [])
    }
    # 平台 external_id → WMS _id 的對照表（供後續品項套用）
    ext_id_to_wms_id: dict = {}
    groups_created = groups_updated = 0

    for og in option_groups:
        og_name = (og.get('name') or '').strip()
        if not og_name:
            continue
        choices = [
            {
                'name':        (ch.get('name') or '').strip(),
                'extra_price': float(ch.get('extra_price', 0)),
                'is_default':  bool(ch.get('is_default', False)),
            }
            for ch in (og.get('choices') or [])
            if (ch.get('name') or '').strip()
        ]
        og_payload = {
            'name':     og_name,
            'type':     og.get('type', 'single'),
            'required': og.get('required', False),
            'choices':  choices,
        }
        ext_id = og.get('external_id', '')

        if og_name.lower() in existing_ogs:
            wms_og = existing_ogs[og_name.lower()]
            wms_id = wms_og['_id']
            Menu.update_option_group(mid, wms_id, og_payload)
            groups_updated += 1
        else:
            new_og = Menu.add_option_group(mid, og_payload)
            wms_id = new_og['_id']
            groups_created += 1
            existing_ogs[og_name.lower()] = new_og  # 避免同批次重複建立

        if ext_id:
            ext_id_to_wms_id[ext_id] = wms_id

    # ── 現有品項：name.lower() → item dict ───────
    existing_items = {
        i['name'].lower(): i
        for i in (platform_menu.get('items') or [])
    }

    # ── 逐一建立 / 更新品項 ───────────────────────
    created = updated = skipped = 0
    operator = get_jwt_identity()

    for item in items:
        name = item.get('name', '').strip()
        if not name:
            skipped += 1
            continue

        price    = float(item.get('price', 0))
        desc     = item.get('description', '').strip()
        category = item.get('category', '').strip()

        # 將平台 modifier_group_ids 轉為 WMS applied_group_ids
        ext_gids   = item.get('modifier_group_ids') or []
        applied_ids = [ext_id_to_wms_id[eid] for eid in ext_gids if eid in ext_id_to_wms_id]

        if name.lower() in existing_items:
            # 更新既有品項：售價必更新；描述 / 分類 / 選項組有值才覆蓋
            existing = existing_items[name.lower()]
            upd = {'price': price}
            if desc:
                upd['description'] = desc
            if category:
                upd['category'] = category
            if applied_ids:
                upd['applied_group_ids'] = applied_ids
            Menu.update_item(mid, existing['_id'], upd)
            updated += 1
        else:
            # 新增品項，預設不消耗庫存（可事後在菜單管理手動開啟）
            Menu.add_item(mid, {
                'name':              name,
                'description':       desc,
                'price':             price,
                'category':          category,
                'consume_inventory': False,
                'sort_order':        0,
                'applied_group_ids': applied_ids,
            })
            created += 1

    Log.create(operator, '菜單從平台同步',
               f'platform={platform} menu={mid} '
               f'items: created={created} updated={updated} skipped={skipped} '
               f'groups: created={groups_created} updated={groups_updated}')
    return jsonify({
        'success':        True,
        'menu_id':        mid,
        'total':          len(items),
        'created':        created,
        'updated':        updated,
        'skipped':        skipped,
        'groups_created': groups_created,
        'groups_updated': groups_updated,
    })


# ─────────────────────────────────────────────
#  商品映射
# ─────────────────────────────────────────────
@app_delivery.route('/mappings', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator')
def list_mappings():
    platform = request.args.get('platform', '')
    data = DeliveryMapping.find_all(platform=platform or None)
    return jsonify({'success': True, 'data': data})


@app_delivery.route('/mappings', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def create_mapping():
    data = request.get_json(silent=True) or {}
    platform             = data.get('platform', '').strip()
    product_id           = data.get('product_id', '').strip()
    external_product_id  = data.get('external_product_id', '').strip()
    product_name         = data.get('product_name', '')

    if not all([platform, product_id, external_product_id]):
        return jsonify({'success': False, 'message': '缺少必要欄位'}), 400

    mid = DeliveryMapping.upsert(platform, product_id, external_product_id, product_name)
    return jsonify({'success': True, '_id': mid}), 201


@app_delivery.route('/mappings/<mid>', methods=['DELETE'])
@jwt_required()
@require_role('admin', 'operator')
def delete_mapping(mid):
    ok = DeliveryMapping.delete(mid)
    return jsonify({'success': ok})


# ─────────────────────────────────────────────
#  平台設定
# ─────────────────────────────────────────────
@app_delivery.route('/settings/<platform>', methods=['GET'])
@jwt_required()
@require_role('admin')
def get_settings(platform):
    """
    取得平台設定（不含 API 金鑰原文）
    ---
    tags:
      - Delivery
    security:
      - Bearer: []
    """
    data = DeliverySettings.get(platform)
    return jsonify({'success': True, 'data': data})


@app_delivery.route('/settings/<platform>', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_settings(platform):
    """
    更新平台設定
    ---
    tags:
      - Delivery
    security:
      - Bearer: []
    parameters:
      - {in: path, name: platform, type: string, required: true}
      - in: body
        name: body
        schema:
          properties:
            enabled:       {type: boolean}
            auto_confirm:  {type: boolean}
            store_id:      {type: string}
            vendor_code:   {type: string}
    """
    data = request.get_json(silent=True) or {}
    kwargs = {}
    for k in ('enabled', 'auto_confirm', 'store_id', 'vendor_code',
              'default_warehouse_id'):
        if k in data:
            kwargs[k] = data[k]

    result = DeliverySettings.upsert(platform, **kwargs)
    Log.create(get_jwt_identity(), '外送平台設定', f'platform={platform}')
    return jsonify({'success': True, 'data': result})
