"""
菜單同步（從平台拉回，建立 / 更新菜單管理品項）
- POST /delivery/menu/sync/<platform>
"""
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.models.log import Log
from src.permissions import require_role
from app.delivery.views.base import (
    app_delivery, logger, _get_ubereats_client, _get_foodpanda_client,
)

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
        choices = []
        for ch in (og.get('choices') or []):
            ch_name = (ch.get('name') or '').strip()
            if not ch_name:
                continue
            try:
                extra_price = float(ch.get('extra_price', 0))
            except (ValueError, TypeError):
                extra_price = 0.0
            choices.append({
                'name':        ch_name,
                'extra_price': extra_price,
                'is_default':  bool(ch.get('is_default', False)),
            })
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

        try:
            price = float(item.get('price', 0))
        except (ValueError, TypeError):
            price = 0.0
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
