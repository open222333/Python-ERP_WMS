import json
from datetime import datetime
from urllib.parse import quote
from flask import Blueprint, request, jsonify, Response
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


# ─────────────────────────────────────────────────────────────
#  菜單匯出 / 匯入
# ─────────────────────────────────────────────────────────────

@app_product.route('/export', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator')
def export_menu():
    """匯出全部分類與產品為 JSON 檔"""
    categories = ProductCategory.find_all()
    products   = Product.find_all()

    # 建立 id → name 對照表（讓產品使用分類名稱，跨系統可攜）
    cat_id_to_name = {c['_id']: c['name'] for c in categories}

    payload = {
        'version': '1.0',
        'exported_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'categories': [
            {
                'name':        c['name'],
                'description': c.get('description', ''),
            }
            for c in categories
        ],
        'products': [
            {
                'sku':           p['sku'],
                'name':          p['name'],
                'barcode':       p.get('barcode', ''),
                'category_name': cat_id_to_name.get(p.get('category_id', ''), ''),
                'unit':          p.get('unit', '個'),
                'cost_price':    p.get('cost_price', 0),
                'sell_price':    p.get('sell_price', 0),
                'min_stock':     p.get('min_stock', 0),
                'max_stock':     p.get('max_stock', 0),
                'description':   p.get('description', ''),
            }
            for p in products
        ],
    }

    filename = f"product_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    Log.create(get_jwt_identity(), '匯出菜單',
               f"分類 {len(categories)} 筆，產品 {len(products)} 筆")

    encoded_filename = quote(filename, safe='')
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={
            'Content-Disposition':
                f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


@app_product.route('/import', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def import_menu():
    """
    匯入菜單 JSON
    - 分類：名稱不存在則新建，已存在則略過
    - 產品：SKU 不存在則新建，已存在則更新
    """
    data = request.get_json(silent=True) or {}
    categories = data.get('categories', [])
    products   = data.get('products',   [])

    result = {
        'created_categories': 0,
        'skipped_categories': 0,
        'created_products':   0,
        'updated_products':   0,
        'errors':             [],
    }

    # ── 處理分類 ──────────────────────────────────────────────
    # 先取得現有分類名稱對照表
    existing_cats  = {c['name']: c['_id'] for c in ProductCategory.find_all()}
    cat_name_to_id = dict(existing_cats)   # 將持續更新

    for cat in categories:
        name = (cat.get('name') or '').strip()
        if not name:
            continue
        if name in existing_cats:
            result['skipped_categories'] += 1
        else:
            cid = ProductCategory.create(name=name,
                                         description=cat.get('description', ''))
            cat_name_to_id[name] = cid
            existing_cats[name]  = cid
            result['created_categories'] += 1

    # ── 處理產品 ──────────────────────────────────────────────
    user = get_jwt_identity()
    for prod in products:
        sku  = (prod.get('sku')  or '').strip()
        name = (prod.get('name') or '').strip()
        if not sku or not name:
            result['errors'].append(f'缺少 sku 或 name（已略過）：{prod}')
            continue

        cat_name = (prod.get('category_name') or '').strip()
        cat_id   = cat_name_to_id.get(cat_name)   # None 表示未分類

        prod_data = {
            'sku':         sku,
            'name':        name,
            'barcode':     prod.get('barcode', ''),
            'category_id': cat_id,
            'unit':        prod.get('unit', '個'),
            'cost_price':  float(prod.get('cost_price', 0)),
            'sell_price':  float(prod.get('sell_price', 0)),
            'min_stock':   int(prod.get('min_stock', 0)),
            'max_stock':   int(prod.get('max_stock', 0)),
            'description': prod.get('description', ''),
        }

        existing = Product.find_by_sku(sku)
        if existing:
            Product.update(existing['_id'], prod_data)
            result['updated_products'] += 1
        else:
            Product.create(prod_data, created_by=user)
            result['created_products'] += 1

    Log.create(user, '匯入菜單',
               f"分類 +{result['created_categories']} 略過{result['skipped_categories']}；"
               f"產品 +{result['created_products']} 更新{result['updated_products']}")

    return jsonify({'success': True, 'result': result})
