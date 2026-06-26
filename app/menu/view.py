"""
菜單管理 Blueprint  /menu
"""
import json
from datetime import datetime
from urllib.parse import quote
from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.menu import Menu
from src.models.log import Log
from src.permissions import require_role, get_store_filter, get_current_store_id

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
    data = Menu.find_all(status=status, store_filter=get_store_filter())
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
    m = Menu.find_by_id(mid, store_filter=get_store_filter())
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

    try:
        sort_order = int(data.get('sort_order', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'sort_order 必須為整數'}), 400

    store_id = data.get('store_id') or get_current_store_id()
    mid = Menu.create(
        name=name,
        description=data.get('description', ''),
        sort_order=sort_order,
        store_id=store_id or None,
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
    if not Menu.find_by_id(mid, store_filter=get_store_filter()):
        return jsonify({'success': False, 'message': '菜單不存在'}), 404
    body = request.get_json(silent=True) or {}
    ALLOWED_MENU_FIELDS = {'name', 'description', 'status', 'sort_order', 'is_default'}
    data = {k: v for k, v in body.items() if k in ALLOWED_MENU_FIELDS}
    Menu.update(mid, **data)
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
    if not Menu.find_by_id(mid, store_filter=get_store_filter()):
        return jsonify({'success': False, 'message': '菜單不存在'}), 404
    Menu.delete(mid)
    Log.create(get_jwt_identity(), '刪除菜單', f'id={mid}')
    return jsonify({'success': True})


# ─────────────────────────────────────────────
#  菜單列表 匯出 / 匯入（全部菜單）
# ─────────────────────────────────────────────

@app_menu.route('/export-all', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator')
def export_all_menus():
    """匯出全部菜單（含分類、選項組、品項）為 JSON 檔"""
    all_menus = Menu.find_all(store_filter=get_store_filter())

    menus_payload = []
    for menu in all_menus:
        categories = [
            {'name': c['name'], 'sort_order': c.get('sort_order', 0)}
            for c in (menu.get('categories') or [])
            if c.get('status', 1) == 1
        ]
        option_groups = [
            {
                '_id':      og['_id'],
                'name':     og['name'],
                'type':     og.get('type', 'single'),
                'required': og.get('required', True),
                'choices':  og.get('choices', []),
            }
            for og in (menu.get('option_groups') or [])
        ]
        items = [
            {
                'name':              it['name'],
                'category':          it.get('category', ''),
                'price':             it.get('price', 0),
                'description':       it.get('description', ''),
                'consume_inventory': it.get('consume_inventory', False),
                'sort_order':        it.get('sort_order', 0),
                'status':            it.get('status', 1),
                'customizations':    it.get('customizations', []),
                'applied_group_ids': it.get('applied_group_ids', []),
            }
            for it in (menu.get('items') or [])
        ]
        menus_payload.append({
            'name':          menu['name'],
            'description':   menu.get('description', ''),
            'sort_order':    menu.get('sort_order', 0),
            'status':        menu.get('status', 1),
            'categories':    categories,
            'option_groups': option_groups,
            'items':         items,
        })

    payload = {
        'version':     '1.0',
        'exported_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'menus':       menus_payload,
    }
    filename = f"menus_all_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    Log.create(get_jwt_identity(), '匯出全部菜單', f"共 {len(menus_payload)} 份菜單")

    encoded_filename = quote(filename, safe='')
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={
            'Content-Disposition':
                f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


@app_menu.route('/import-all', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def import_all_menus():
    """
    匯入全部菜單 JSON
    - 菜單：名稱不存在則新建，已存在則沿用（不覆蓋基本資料）
    - 各菜單內：分類 / 選項組 / 品項同名略過或更新（與單菜單匯入邏輯相同）
    """
    data = request.get_json(silent=True) or {}
    menus_data = data.get('menus', [])
    user = get_jwt_identity()

    total = {
        'created_menus':         0,
        'skipped_menus':         0,
        'created_categories':    0,
        'created_option_groups': 0,
        'created_items':         0,
        'updated_items':         0,
        'errors':                [],
    }

    # 取得現有菜單名稱對照表（限目前分店）
    existing_menus = {m['name']: m['_id']
                      for m in Menu.find_all(store_filter=get_store_filter())}

    for md in menus_data:
        mname = (md.get('name') or '').strip()
        if not mname:
            total['errors'].append('缺少菜單名稱（已略過）')
            continue

        # 菜單不存在則新建
        if mname not in existing_menus:
            try:
                sort_order = int(md.get('sort_order', 0))
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': f'菜單 {mname} 的 sort_order 必須為整數'}), 400
            mid = Menu.create(
                name=mname,
                description=md.get('description', ''),
                sort_order=sort_order,
                store_id=get_current_store_id(),
            )
            existing_menus[mname] = mid
            total['created_menus'] += 1
        else:
            mid = existing_menus[mname]
            total['skipped_menus'] += 1

        menu = Menu.find_by_id(mid)

        # ── 分類 ──────────────────────────────────
        existing_cat_names = {c['name'] for c in (menu.get('categories') or [])}
        for cat in (md.get('categories') or []):
            cname = (cat.get('name') or '').strip()
            if not cname or cname in existing_cat_names:
                continue
            Menu.add_category(mid, {'name': cname,
                                    'sort_order': cat.get('sort_order', 0)})
            existing_cat_names.add(cname)
            total['created_categories'] += 1

        # ── 選項組 ────────────────────────────────
        menu = Menu.find_by_id(mid)
        existing_og_names = {og['name']: og['_id']
                             for og in (menu.get('option_groups') or [])}
        og_id_map = {}
        for og in (md.get('option_groups') or []):
            og_name = (og.get('name') or '').strip()
            old_id  = og.get('_id', '')
            if not og_name:
                continue
            if og_name in existing_og_names:
                og_id_map[old_id] = existing_og_names[og_name]
            else:
                new_og = Menu.add_option_group(mid, og)
                og_id_map[old_id] = new_og['_id']
                existing_og_names[og_name] = new_og['_id']
                total['created_option_groups'] += 1

        # ── 品項 ──────────────────────────────────
        menu = Menu.find_by_id(mid)
        existing_items = {it['name']: it['_id']
                         for it in (menu.get('items') or [])}
        for it in (md.get('items') or []):
            iname = (it.get('name') or '').strip()
            if not iname:
                total['errors'].append(f'缺少品項名稱（已略過）：{it}')
                continue

            raw_gids = it.get('applied_group_ids') or []
            remapped_gids = [og_id_map[gid] for gid in raw_gids if gid in og_id_map]

            item_data = {
                'name':              iname,
                'category':          it.get('category', ''),
                'price':             float(it.get('price', 0)),
                'description':       it.get('description', ''),
                'consume_inventory': bool(it.get('consume_inventory', False)),
                'sort_order':        int(it.get('sort_order', 0)),
                'status':            int(it.get('status', 1)),
                'customizations':    it.get('customizations', []),
                'applied_group_ids': remapped_gids,
            }
            if iname in existing_items:
                Menu.update_item(mid, existing_items[iname], item_data)
                total['updated_items'] += 1
            else:
                new_item = Menu.add_item(mid, item_data)
                existing_items[iname] = new_item['_id']
                total['created_items'] += 1

    Log.create(user, '匯入全部菜單',
               f"菜單+{total['created_menus']} 略過{total['skipped_menus']}；"
               f"分類+{total['created_categories']}；"
               f"選項組+{total['created_option_groups']}；"
               f"品項+{total['created_items']} 更新{total['updated_items']}")

    return jsonify({'success': True, 'result': total})


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
    if not Menu.find_by_id(mid, store_filter=get_store_filter()):
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
    if not Menu.find_by_id(mid, store_filter=get_store_filter()):
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


# ─────────────────────────────────────────────
#  選項組 CRUD
# ─────────────────────────────────────────────

@app_menu.route('/<mid>/option-group', methods=['GET'])
@jwt_required()
def list_option_groups(mid):
    """列出菜單的所有選項組"""
    menu = Menu.find_by_id(mid, store_filter=get_store_filter())
    if not menu:
        return jsonify({'success': False, 'message': '菜單不存在'}), 404
    return jsonify({'success': True, 'data': menu.get('option_groups', [])})


@app_menu.route('/<mid>/option-group', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def add_option_group(mid):
    """新增選項組"""
    if not Menu.find_by_id(mid, store_filter=get_store_filter()):
        return jsonify({'success': False, 'message': '菜單不存在'}), 404
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': '請填寫選項組名稱'}), 400
    og = Menu.add_option_group(mid, data)
    Log.create(get_jwt_identity(), '新增選項組', f'menu={mid} name={name}')
    return jsonify({'success': True, 'option_group': og}), 201


@app_menu.route('/<mid>/option-group/<gid>', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_option_group(mid, gid):
    """更新選項組"""
    data = request.get_json(silent=True) or {}
    ok = Menu.update_option_group(mid, gid, data)
    if not ok:
        return jsonify({'success': False, 'message': '選項組不存在'}), 404
    Log.create(get_jwt_identity(), '更新選項組', f'menu={mid} gid={gid}')
    return jsonify({'success': True})


@app_menu.route('/<mid>/option-group/<gid>', methods=['DELETE'])
@jwt_required()
@require_role('admin', 'operator')
def delete_option_group(mid, gid):
    """刪除選項組（同時從品項的 applied_group_ids 中移除）"""
    ok = Menu.delete_option_group(mid, gid)
    if not ok:
        return jsonify({'success': False, 'message': '選項組不存在'}), 404
    Log.create(get_jwt_identity(), '刪除選項組', f'menu={mid} gid={gid}')
    return jsonify({'success': True})


# ─────────────────────────────────────────────
#  菜單品項 匯出 / 匯入
# ─────────────────────────────────────────────

@app_menu.route('/<mid>/export', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator')
def export_menu(mid):
    """匯出菜單分類與品項為 JSON 檔"""
    menu = Menu.find_by_id(mid, store_filter=get_store_filter())
    if not menu:
        return jsonify({'success': False, 'message': '菜單不存在'}), 404

    # 只保留可攜欄位（去除 _id、linked_products 的 ObjectId）
    categories = [
        {'name': c['name'], 'sort_order': c.get('sort_order', 0)}
        for c in (menu.get('categories') or [])
        if c.get('status', 1) == 1
    ]

    # 選項組模組：保留 _id 以供品項 applied_group_ids 對照
    option_groups = [
        {
            '_id':      og['_id'],
            'name':     og['name'],
            'type':     og.get('type', 'single'),
            'required': og.get('required', True),
            'choices':  og.get('choices', []),
        }
        for og in (menu.get('option_groups') or [])
    ]

    items = []
    for it in (menu.get('items') or []):
        items.append({
            'name':               it['name'],
            'category':           it.get('category', ''),
            'price':              it.get('price', 0),
            'description':        it.get('description', ''),
            'consume_inventory':  it.get('consume_inventory', False),
            'sort_order':         it.get('sort_order', 0),
            'status':             it.get('status', 1),
            'customizations':     it.get('customizations', []),
            'applied_group_ids':  it.get('applied_group_ids', []),
        })

    payload = {
        'version':       '1.0',
        'exported_at':   datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'menu_name':     menu['name'],
        'categories':    categories,
        'option_groups': option_groups,
        'items':         items,
    }

    safe_name = menu['name'].replace('/', '-').replace(' ', '_')
    filename  = f"menu_{safe_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    Log.create(get_jwt_identity(), '匯出菜單',
               f"menu={mid} 分類{len(categories)}筆 品項{len(items)}筆")

    # RFC 5987：中文/特殊字元檔名需 percent-encode，否則 latin-1 encode 失敗
    encoded_filename = quote(filename, safe='')
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        mimetype='application/json',
        headers={
            'Content-Disposition':
                f"attachment; filename*=UTF-8''{encoded_filename}"
        },
    )


@app_menu.route('/<mid>/import', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def import_menu(mid):
    """
    匯入分類與品項至指定菜單
    - 分類：名稱不存在則新建，已存在略過
    - 品項：名稱不存在則新建，已存在則更新（price、description、category 等）
    """
    menu = Menu.find_by_id(mid, store_filter=get_store_filter())
    if not menu:
        return jsonify({'success': False, 'message': '菜單不存在'}), 404

    data          = request.get_json(silent=True) or {}
    categories    = data.get('categories',    [])
    option_groups = data.get('option_groups', [])
    items         = data.get('items',         [])
    user          = get_jwt_identity()

    result = {
        'created_categories':    0,
        'skipped_categories':    0,
        'created_option_groups': 0,
        'skipped_option_groups': 0,
        'created_items':         0,
        'updated_items':         0,
        'errors':                [],
    }

    # ── 處理分類 ──────────────────────────────────
    existing_cat_names = {c['name'] for c in (menu.get('categories') or [])}

    for cat in categories:
        name = (cat.get('name') or '').strip()
        if not name:
            continue
        if name in existing_cat_names:
            result['skipped_categories'] += 1
        else:
            Menu.add_category(mid, {'name': name,
                                    'sort_order': cat.get('sort_order', 0)})
            existing_cat_names.add(name)
            result['created_categories'] += 1

    # ── 處理選項組模組 ────────────────────────────
    # 重新 fetch（含剛建立的分類）
    menu = Menu.find_by_id(mid)
    existing_og_names = {og['name']: og['_id']
                         for og in (menu.get('option_groups') or [])}
    # old_id（匯出時的 _id）→ new_id（目標菜單實際 _id）
    og_id_map = {}

    for og in option_groups:
        og_name  = (og.get('name') or '').strip()
        old_id   = og.get('_id', '')
        if not og_name:
            continue
        if og_name in existing_og_names:
            # 已存在：直接對照舊 ID → 現有 ID
            og_id_map[old_id] = existing_og_names[og_name]
            result['skipped_option_groups'] += 1
        else:
            new_og = Menu.add_option_group(mid, og)
            og_id_map[old_id] = new_og['_id']
            existing_og_names[og_name] = new_og['_id']
            result['created_option_groups'] += 1

    # ── 處理品項 ──────────────────────────────────
    # 重新 fetch（含剛建立的選項組）
    menu = Menu.find_by_id(mid)
    existing_items = {it['name']: it['_id']
                      for it in (menu.get('items') or [])}

    for it in items:
        name = (it.get('name') or '').strip()
        if not name:
            result['errors'].append(f'缺少品項名稱（已略過）：{it}')
            continue

        # 將匯出時的 applied_group_ids 透過對照表轉換為目標系統 ID
        raw_gids = it.get('applied_group_ids') or []
        remapped_gids = [og_id_map[gid] for gid in raw_gids if gid in og_id_map]

        item_data = {
            'name':              name,
            'category':          it.get('category', ''),
            'price':             float(it.get('price', 0)),
            'description':       it.get('description', ''),
            'consume_inventory': bool(it.get('consume_inventory', False)),
            'sort_order':        int(it.get('sort_order', 0)),
            'status':            int(it.get('status', 1)),
            'customizations':    it.get('customizations', []),
            'applied_group_ids': remapped_gids,
        }

        if name in existing_items:
            Menu.update_item(mid, existing_items[name], item_data)
            result['updated_items'] += 1
        else:
            new_item = Menu.add_item(mid, item_data)
            existing_items[name] = new_item['_id']
            result['created_items'] += 1

    Log.create(user, '匯入菜單品項',
               f"menu={mid} 分類+{result['created_categories']} "
               f"選項組+{result['created_option_groups']} "
               f"品項+{result['created_items']} 更新{result['updated_items']}")

    return jsonify({'success': True, 'result': result})
