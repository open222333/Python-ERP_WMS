"""
外送平台設定（全域 + Per-Store）
- GET/PUT /delivery/settings/<platform>
- GET     /delivery/store/
- GET/PUT /delivery/store/<store_id>/settings/<platform>
"""
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.models.delivery import DeliverySettings
from src.models.log import Log
from src.permissions import require_role
from app.delivery.views.base import app_delivery, DELIVERY_PLATFORMS


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


# ─────────────────────────────────────────────────────────────
#  Per-Store 外送平台設定
# ─────────────────────────────────────────────────────────────

@app_delivery.route('/store/', methods=['GET'])
@jwt_required()
@require_role('admin')
def list_store_delivery_settings():
    from src.models.store import Store
    stores = Store.find_all()
    result = []
    for s in stores:
        platforms = DeliverySettings.get_store_platforms(s['_id'])
        result.append({
            'store_id':   s['_id'],
            'store_name': s['name'],
            'store_code': s.get('code', ''),
            'platforms':  platforms,
        })
    return jsonify({'success': True, 'data': result})


@app_delivery.route('/store/<store_id>/settings/<platform>', methods=['GET'])
@jwt_required()
@require_role('admin')
def get_store_delivery_settings(store_id, platform):
    if platform not in DELIVERY_PLATFORMS:
        return jsonify({'success': False, 'message': '不支援的平台'}), 400
    data = DeliverySettings.get(platform, store_ref=store_id)
    return jsonify({'success': True, 'data': data})


@app_delivery.route('/store/<store_id>/settings/<platform>', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_store_delivery_settings(store_id, platform):
    """
    更新店家專屬平台設定。
    store_id / vendor_code 為平台端店家代號，供 webhook 依訂單來源自動歸屬分店。
    """
    if platform not in DELIVERY_PLATFORMS:
        return jsonify({'success': False, 'message': '不支援的平台'}), 400
    data = request.get_json(silent=True) or {}
    kwargs = {}
    for k in ('enabled', 'auto_confirm', 'default_warehouse_id', 'item_mappings',
              'mapping_template_id', 'store_id', 'vendor_code'):
        if k in data:
            kwargs[k] = data[k]
    result = DeliverySettings.upsert(platform, store_ref=store_id, **kwargs)
    Log.create(get_jwt_identity(), '店家外送平台設定',
               f'store={store_id} platform={platform}')
    return jsonify({'success': True, 'data': result})
