"""
菜單管理 Blueprint  /menu
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.menu import Menu
from src.models.log import Log
from src.permissions import require_role

app_menu = Blueprint('app_menu', __name__)


# ─────────────────────────────────────────────
#  菜單 CRUD
# ─────────────────────────────────────────────
@app_menu.route('/', methods=['GET'])
@jwt_required()
def list_menus():
    """
    列出菜單
    ---
    tags:
      - Menu
    security:
      - Bearer: []
    parameters:
      - {in: query, name: status, type: integer, description: "1=啟用 0=停用，留空=全部"}
    responses:
      200:
        description: 成功
    """
    status_str = request.args.get('status', '')
    status = int(status_str) if status_str.isdigit() else None
    data = Menu.find_all(status=status)
    return jsonify({'success': True, 'data': data})


@app_menu.route('/<mid>', methods=['GET'])
@jwt_required()
def get_menu(mid):
    """
    取得單一菜單（含品項）
    ---
    tags:
      - Menu
    security:
      - Bearer: []
    """
    m = Menu.find_by_id(mid)
    if not m:
        return jsonify({'success': False, 'message': '菜單不存在'}), 404
    return jsonify({'success': True, 'data': m})


@app_menu.route('/', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def create_menu():
    """
    建立菜單
    ---
    tags:
      - Menu
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [name]
          properties:
            name:        {type: string}
            description: {type: string}
            sort_order:  {type: integer}
    responses:
      201:
        description: 建立成功
    """
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '請填寫菜單名稱'}), 400

    mid = Menu.create(
        name=name,
        description=data.get('description', ''),
        sort_order=int(data.get('sort_order', 0)),
    )
    Log.create(get_jwt_identity(), '建立菜單', f'name={name}')
    return jsonify({'success': True, '_id': mid}), 201


@app_menu.route('/<mid>', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_menu(mid):
    """
    更新菜單基本資料
    ---
    tags:
      - Menu
    security:
      - Bearer: []
    """
    data = request.get_json(silent=True) or {}
    ok = Menu.update(mid, **data)
    if not ok:
        return jsonify({'success': False, 'message': '菜單不存在'}), 404
    Log.create(get_jwt_identity(), '更新菜單', f'id={mid}')
    return jsonify({'success': True})


@app_menu.route('/<mid>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_menu(mid):
    """
    刪除菜單
    ---
    tags:
      - Menu
    security:
      - Bearer: []
    """
    ok = Menu.delete(mid)
    if not ok:
        return jsonify({'success': False, 'message': '菜單不存在'}), 404
    Log.create(get_jwt_identity(), '刪除菜單', f'id={mid}')
    return jsonify({'success': True})


# ─────────────────────────────────────────────
#  品項 CRUD
# ─────────────────────────────────────────────
@app_menu.route('/<mid>/item', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def add_item(mid):
    """
    新增菜單品項
    ---
    tags:
      - Menu
    security:
      - Bearer: []
    parameters:
      - {in: path, name: mid, type: string, required: true}
      - in: body
        name: body
        required: true
        schema:
          required: [name, price]
          properties:
            name:               {type: string}
            description:        {type: string}
            price:              {type: number}
            category:           {type: string, description: "POS 顯示分類"}
            consume_inventory:  {type: boolean, description: "結帳時是否扣庫存"}
            product_id:         {type: string,  description: "連結的系統商品（選填）"}
            warehouse_id:       {type: string,  description: "扣庫存倉庫（consume_inventory=true 時有效）"}
            sort_order:         {type: integer}
    responses:
      201:
        description: 成功
      400:
        description: 缺少欄位
    """
    if not Menu.find_by_id(mid):
        return jsonify({'success': False, 'message': '菜單不存在'}), 404

    data = request.get_json(silent=True) or {}
    if not data.get('name', '').strip():
        return jsonify({'success': False, 'message': '請填寫品項名稱'}), 400
    if data.get('price') is None:
        return jsonify({'success': False, 'message': '請填寫售價'}), 400

    item = Menu.add_item(mid, data)
    Log.create(get_jwt_identity(), '新增菜單品項',
               f'menu={mid} name={item["name"]}')
    return jsonify({'success': True, 'item': item}), 201


@app_menu.route('/<mid>/item/<item_id>', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_item(mid, item_id):
    """
    更新菜單品項
    ---
    tags:
      - Menu
    security:
      - Bearer: []
    """
    data = request.get_json(silent=True) or {}
    ok = Menu.update_item(mid, item_id, data)
    if not ok:
        return jsonify({'success': False, 'message': '品項不存在'}), 404
    Log.create(get_jwt_identity(), '更新菜單品項',
               f'menu={mid} item={item_id}')
    return jsonify({'success': True})


@app_menu.route('/<mid>/item/<item_id>', methods=['DELETE'])
@jwt_required()
@require_role('admin', 'operator')
def delete_item(mid, item_id):
    """
    刪除菜單品項
    ---
    tags:
      - Menu
    security:
      - Bearer: []
    """
    ok = Menu.delete_item(mid, item_id)
    if not ok:
        return jsonify({'success': False, 'message': '品項不存在'}), 404
    Log.create(get_jwt_identity(), '刪除菜單品項',
               f'menu={mid} item={item_id}')
    return jsonify({'success': True})


# ─────────────────────────────────────────────
#  分類 CRUD
# ─────────────────────────────────────────────
@app_menu.route('/<mid>/category', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def add_category(mid):
    """
    新增菜單分類
    ---
    tags:
      - Menu
    security:
      - Bearer: []
    parameters:
      - {in: path, name: mid, type: string, required: true}
      - in: body
        name: body
        required: true
        schema:
          required: [name]
          properties:
            name:       {type: string}
            sort_order: {type: integer}
    responses:
      201:
        description: 成功
      404:
        description: 菜單不存在
    """
    if not Menu.find_by_id(mid):
        return jsonify({'success': False, 'message': '菜單不存在'}), 404

    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '請填寫分類名稱'}), 400

    cat = Menu.add_category(mid, data)
    Log.create(get_jwt_identity(), '新增菜單分類',
               f'menu={mid} name={name}')
    return jsonify({'success': True, 'category': cat}), 201


@app_menu.route('/<mid>/category/<cat_id>', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_category(mid, cat_id):
    """
    更新菜單分類（改名時同步更新所有品項的 category 字串）
    ---
    tags:
      - Menu
    security:
      - Bearer: []
    """
    data = request.get_json(silent=True) or {}
    ok = Menu.update_category(mid, cat_id, data)
    if not ok:
        return jsonify({'success': False, 'message': '分類不存在'}), 404
    Log.create(get_jwt_identity(), '更新菜單分類',
               f'menu={mid} cat={cat_id}')
    return jsonify({'success': True})


@app_menu.route('/<mid>/category/<cat_id>', methods=['DELETE'])
@jwt_required()
@require_role('admin', 'operator')
def delete_category(mid, cat_id):
    """
    刪除菜單分類（品項的 category 欄位保留原字串，不自動清除）
    ---
    tags:
      - Menu
    security:
      - Bearer: []
    """
    ok = Menu.delete_category(mid, cat_id)
    if not ok:
        return jsonify({'success': False, 'message': '分類不存在'}), 404
    Log.create(get_jwt_identity(), '刪除菜單分類',
               f'menu={mid} cat={cat_id}')
    return jsonify({'success': True})
