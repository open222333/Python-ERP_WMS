from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.warehouse import Warehouse, WarehouseLocation
from src.models.log import Log
from src.permissions import require_role

app_warehouse = Blueprint('app_warehouse', __name__)


# ─────────────────────────────────────────────────────────────
#  倉庫
# ─────────────────────────────────────────────────────────────

@app_warehouse.route('/', methods=['GET'])
@jwt_required()
def list_warehouses():
    return jsonify({'success': True, 'data': Warehouse.find_all()})


@app_warehouse.route('/<wid>', methods=['GET'])
@jwt_required()
def get_warehouse(wid):
    w = Warehouse.find_by_id(wid)
    if not w:
        return jsonify({'success': False, 'message': '倉庫不存在'}), 404
    return jsonify({'success': True, 'data': w})


@app_warehouse.route('/', methods=['POST'])
@jwt_required()
@require_role('admin')
def create_warehouse():
    data = request.get_json(silent=True) or {}
    if not data.get('code') or not data.get('name'):
        return jsonify({'success': False, 'message': 'code 與 name 不得為空'}), 400
    if Warehouse.find_by_code(data['code']):
        return jsonify({'success': False, 'message': '倉庫代碼已存在'}), 409
    wid = Warehouse.create(data)
    Log.create(get_jwt_identity(), '新增倉庫', f"code={data['code']} name={data['name']}")
    return jsonify({'success': True, 'id': wid}), 201


@app_warehouse.route('/<wid>', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_warehouse(wid):
    data = request.get_json(silent=True) or {}
    if not Warehouse.update(wid, data):
        return jsonify({'success': False, 'message': '倉庫不存在'}), 404
    Log.create(get_jwt_identity(), '更新倉庫', f'id={wid}')
    return jsonify({'success': True})


@app_warehouse.route('/<wid>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_warehouse(wid):
    if not Warehouse.delete(wid):
        return jsonify({'success': False, 'message': '倉庫不存在'}), 404
    Log.create(get_jwt_identity(), '刪除倉庫', f'id={wid}')
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  倉庫位置
# ─────────────────────────────────────────────────────────────

@app_warehouse.route('/<wid>/location/', methods=['GET'])
@jwt_required()
def list_locations(wid):
    return jsonify({'success': True, 'data': WarehouseLocation.find_by_warehouse(wid)})


@app_warehouse.route('/<wid>/location/', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def create_location(wid):
    data = request.get_json(silent=True) or {}
    if not data.get('code') or not data.get('name'):
        return jsonify({'success': False, 'message': 'code 與 name 不得為空'}), 400
    lid = WarehouseLocation.create(wid, data)
    Log.create(get_jwt_identity(), '新增倉庫位置', f"warehouse={wid} code={data['code']}")
    return jsonify({'success': True, 'id': lid}), 201


@app_warehouse.route('/location/<lid>', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_location(lid):
    data = request.get_json(silent=True) or {}
    if not WarehouseLocation.update(lid, data):
        return jsonify({'success': False, 'message': '位置不存在'}), 404
    Log.create(get_jwt_identity(), '更新倉庫位置', f'id={lid}')
    return jsonify({'success': True})


@app_warehouse.route('/location/<lid>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_location(lid):
    if not WarehouseLocation.delete(lid):
        return jsonify({'success': False, 'message': '位置不存在'}), 404
    Log.create(get_jwt_identity(), '刪除倉庫位置', f'id={lid}')
    return jsonify({'success': True})
