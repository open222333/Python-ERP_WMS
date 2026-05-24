from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.product import Product, ProductCategory
from src.models.log import Log
from src.permissions import require_role

app_product = Blueprint('app_product', __name__)


# ─────────────────────────────────────────────────────────────
#  產品分類
# ─────────────────────────────────────────────────────────────

@app_product.route('/category/', methods=['GET'])
@jwt_required()
def list_categories():
    return jsonify({'success': True, 'data': ProductCategory.find_all()})


@app_product.route('/category/', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def create_category():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '分類名稱不得為空'}), 400
    cid = ProductCategory.create(
        name=name,
        parent_id=data.get('parent_id'),
        description=data.get('description', '')
    )
    Log.create(get_jwt_identity(), '新增產品分類', f'name={name}')
    return jsonify({'success': True, 'id': cid}), 201


@app_product.route('/category/<cid>', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_category(cid):
    data = request.get_json(silent=True) or {}
    if not ProductCategory.update(cid, **data):
        return jsonify({'success': False, 'message': '分類不存在'}), 404
    Log.create(get_jwt_identity(), '更新產品分類', f'id={cid}')
    return jsonify({'success': True})


@app_product.route('/category/<cid>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_category(cid):
    if not ProductCategory.delete(cid):
        return jsonify({'success': False, 'message': '分類不存在'}), 404
    Log.create(get_jwt_identity(), '刪除產品分類', f'id={cid}')
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  產品
# ─────────────────────────────────────────────────────────────

@app_product.route('/', methods=['GET'])
@jwt_required()
def list_products():
    keyword = request.args.get('keyword', '')
    category_id = request.args.get('category_id', '')
    status_str = request.args.get('status', '')
    status = int(status_str) if status_str.isdigit() else None
    data = Product.find_all(keyword=keyword, category_id=category_id, status=status)
    return jsonify({'success': True, 'data': data})


@app_product.route('/barcode/<code>', methods=['GET'])
@jwt_required()
def get_by_barcode(code):
    """
    以條碼查詢產品
    ---
    tags:
      - 產品管理
    security:
      - Bearer: []
    parameters:
      - in: path
        name: code
        type: string
        required: true
        description: 條碼值
    responses:
      200:
        description: 找到產品
        schema:
          properties:
            success: {type: boolean}
            data:
              $ref: '#/definitions/Product'
      404:
        description: 找不到對應產品
    """
    p = Product.find_by_barcode(code)
    if not p:
        return jsonify({'success': False, 'message': '找不到對應產品'}), 404
    return jsonify({'success': True, 'data': p})


@app_product.route('/<pid>', methods=['GET'])
@jwt_required()
def get_product(pid):
    p = Product.find_by_id(pid)
    if not p:
        return jsonify({'success': False, 'message': '產品不存在'}), 404
    return jsonify({'success': True, 'data': p})


@app_product.route('/', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def create_product():
    data = request.get_json(silent=True) or {}
    if not data.get('sku') or not data.get('name'):
        return jsonify({'success': False, 'message': 'sku 與 name 不得為空'}), 400
    if Product.find_by_sku(data['sku']):
        return jsonify({'success': False, 'message': 'SKU 已存在'}), 409
    pid = Product.create(data, created_by=get_jwt_identity())
    Log.create(get_jwt_identity(), '新增產品', f"sku={data['sku']} name={data['name']}")
    return jsonify({'success': True, 'id': pid}), 201


@app_product.route('/<pid>', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_product(pid):
    data = request.get_json(silent=True) or {}
    if not Product.update(pid, data):
        return jsonify({'success': False, 'message': '產品不存在'}), 404
    Log.create(get_jwt_identity(), '更新產品', f'id={pid}')
    return jsonify({'success': True})


@app_product.route('/<pid>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_product(pid):
    if not Product.delete(pid):
        return jsonify({'success': False, 'message': '產品不存在'}), 404
    Log.create(get_jwt_identity(), '刪除產品', f'id={pid}')
    return jsonify({'success': True})
