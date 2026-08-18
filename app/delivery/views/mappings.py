"""
商品映射與品項對應模板
- GET/POST /delivery/mappings、DELETE /delivery/mappings/<mid>
- GET/POST/PUT/DELETE /delivery/mapping-templates/
映射目標支援：產品（product_id）或菜單品項（menu_id + menu_item_id）。
"""
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.models.delivery import DeliveryMapping, DeliveryMappingTemplate
from src.models.log import Log
from src.permissions import require_role
from app.delivery.views.base import app_delivery


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
    """
    建立/更新平台品項映射。
    目標二擇一：
      - product_id：平台品項 → 產品（於預設倉扣庫存）
      - menu_id + menu_item_id：平台品項 → 菜單品項（依 linked_products 扣庫存）
    """
    data = request.get_json(silent=True) or {}
    platform            = data.get('platform', '').strip()
    product_id          = (data.get('product_id') or '').strip()
    menu_id             = (data.get('menu_id') or '').strip()
    menu_item_id        = (data.get('menu_item_id') or '').strip()
    menu_item_name      = data.get('menu_item_name', '')
    external_product_id = (data.get('external_product_id') or '').strip()
    product_name        = data.get('product_name', '')

    if not platform or not external_product_id:
        return jsonify({'success': False, 'message': '缺少必要欄位'}), 400
    if not product_id and not menu_item_id:
        return jsonify({'success': False,
                        'message': 'product_id 與 menu_item_id 至少須填一項'}), 400
    if product_id and menu_item_id:
        return jsonify({'success': False,
                        'message': '產品對應與菜單品項對應只能擇一'}), 400

    mid = DeliveryMapping.upsert(
        platform, product_id or None, external_product_id, product_name,
        menu_id=menu_id or None, menu_item_id=menu_item_id or None,
        menu_item_name=menu_item_name,
    )
    return jsonify({'success': True, '_id': mid}), 201


@app_delivery.route('/mappings/<mid>', methods=['DELETE'])
@jwt_required()
@require_role('admin', 'operator')
def delete_mapping(mid):
    ok = DeliveryMapping.delete(mid)
    return jsonify({'success': ok})


# ─────────────────────────────────────────────────────────────
#  品項對應模板
# ─────────────────────────────────────────────────────────────

@app_delivery.route('/mapping-templates/', methods=['GET'])
@jwt_required()
@require_role('admin')
def list_mapping_templates():
    return jsonify({'success': True, 'data': DeliveryMappingTemplate.find_all()})


@app_delivery.route('/mapping-templates/', methods=['POST'])
@jwt_required()
@require_role('admin')
def create_mapping_template():
    body = request.get_json(silent=True) or {}
    name = (body.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': '請填寫模板名稱'}), 400
    tid = DeliveryMappingTemplate.create(
        name=name,
        platform=body.get('platform', ''),
        items=body.get('items', []),
    )
    Log.create(get_jwt_identity(), '品項對應模板', f'create name={name}')
    return jsonify({'success': True, 'data': DeliveryMappingTemplate.find_by_id(tid)}), 201


@app_delivery.route('/mapping-templates/<tid>/', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_mapping_template(tid):
    body = request.get_json(silent=True) or {}
    name = (body.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': '請填寫模板名稱'}), 400
    ok = DeliveryMappingTemplate.update(
        tid,
        name=name,
        platform=body.get('platform', ''),
        items=body.get('items', []),
    )
    if not ok:
        return jsonify({'success': False, 'message': '找不到模板'}), 404
    Log.create(get_jwt_identity(), '品項對應模板', f'update tid={tid}')
    return jsonify({'success': True, 'data': DeliveryMappingTemplate.find_by_id(tid)})


@app_delivery.route('/mapping-templates/<tid>/', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_mapping_template(tid):
    ok = DeliveryMappingTemplate.delete(tid)
    if not ok:
        return jsonify({'success': False, 'message': '找不到模板'}), 404
    Log.create(get_jwt_identity(), '品項對應模板', f'delete tid={tid}')
    return jsonify({'success': True, 'message': '已刪除'})
