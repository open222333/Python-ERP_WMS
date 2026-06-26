import logging
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.inventory import Inventory, StockMovement, MOVEMENT_TYPES, MOVEMENT_LABEL
from src.models.product import Product
from src.models.warehouse import Warehouse
from src.models.log import Log
from src.models.settings import SystemSettings
from src.permissions import require_role

app_inventory = Blueprint('app_inventory', __name__)
logger = logging.getLogger(__name__)


def _maybe_auto_cleanup_movements():
    """懶觸發：若設定保留天數且距上次清除 ≥ 1 天則自動清除庫存移動紀錄。"""
    try:
        s = SystemSettings.get_all()
        days = int(s.get('movements_retention_days', 0) or 0)
        if days <= 0:
            return
        last_str = s.get('movements_last_cleanup_at', '')
        if last_str:
            last_dt = datetime.fromisoformat(last_str)
            if (datetime.utcnow() - last_dt).total_seconds() < 86400:
                return
        deleted = StockMovement.cleanup_old(days)
        SystemSettings.set('movements_last_cleanup_at', datetime.utcnow().isoformat())
        if deleted:
            logger.info('auto-cleanup: removed %d stock_movements older than %d days', deleted, days)
    except Exception as e:
        logger.warning('movements auto-cleanup error: %s', e)


@app_inventory.route('/', methods=['GET'])
@jwt_required()
def list_inventory():
    """查詢庫存（含產品名稱、倉庫名稱）"""
    warehouse_id = request.args.get('warehouse_id', '')
    product_id = request.args.get('product_id', '')
    limit = min(int(request.args.get('limit', 500)), 2000)
    rows = Inventory.find_all(
        warehouse_id=warehouse_id or None,
        product_id=product_id or None,
        limit=limit,
    )
    # 補充 product / warehouse 名稱
    product_cache = {}
    warehouse_cache = {}
    for row in rows:
        pid = row.get('product_id')
        wid = row.get('warehouse_id')
        if pid and pid not in product_cache:
            p = Product.find_by_id(pid)
            product_cache[pid] = {'name': p['name'], 'sku': p['sku'], 'unit': p['unit']} if p else {}
        if wid and wid not in warehouse_cache:
            w = Warehouse.find_by_id(wid)
            warehouse_cache[wid] = w['name'] if w else ''
        row['product_name'] = product_cache.get(pid, {}).get('name', '')
        row['product_sku'] = product_cache.get(pid, {}).get('sku', '')
        row['product_unit'] = product_cache.get(pid, {}).get('unit', '')
        row['warehouse_name'] = warehouse_cache.get(wid, '')
    return jsonify({'success': True, 'data': rows})


@app_inventory.route('/adjust', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def adjust_inventory():
    """手動調整庫存（盤點）"""
    data = request.get_json(silent=True) or {}
    product_id = data.get('product_id')
    warehouse_id = data.get('warehouse_id')
    quantity = data.get('quantity')

    if not all([product_id, warehouse_id, quantity is not None]):
        return jsonify({'success': False, 'message': '缺少必要參數 product_id / warehouse_id / quantity'}), 400

    p = Product.find_by_id(product_id)
    w = Warehouse.find_by_id(warehouse_id)
    if not p:
        return jsonify({'success': False, 'message': '產品不存在'}), 404
    if not w:
        return jsonify({'success': False, 'message': '倉庫不存在'}), 404

    before_qty, after_qty = Inventory.set_quantity(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=int(quantity),
        location_id=data.get('location_id')
    )
    delta = after_qty - before_qty
    StockMovement.create(
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type='adjust',
        quantity=delta,
        before_qty=before_qty,
        after_qty=after_qty,
        product_name=p['name'],
        product_sku=p['sku'],
        warehouse_name=w['name'],
        remark=data.get('remark', '盤點調整'),
        operator=get_jwt_identity()
    )
    Log.create(get_jwt_identity(), '庫存盤點調整',
               f"product={p['sku']} warehouse={w['name']} {before_qty}→{after_qty}")
    return jsonify({'success': True, 'before_qty': before_qty, 'after_qty': after_qty})


@app_inventory.route('/batch', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def batch_move():
    """
    快速批次出入庫 / 消耗
    ---
    tags:
      - Inventory
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [type, warehouse_id, items]
          properties:
            type:
              type: string
              description: "inbound=入庫 outbound=出庫 consume=消耗"
            warehouse_id: {type: string}
            remark:       {type: string}
            items:
              type: array
              items:
                required: [product_id, qty]
                properties:
                  product_id: {type: string}
                  qty:        {type: integer}
    responses:
      200:
        description: 成功，回傳每筆結果清單
      400:
        description: 參數錯誤
    """
    data = request.get_json(silent=True) or {}
    mov_type     = data.get('type', '')
    warehouse_id = data.get('warehouse_id', '')
    remark       = data.get('remark', '')
    items        = data.get('items', [])

    # ── 驗證 ──
    VALID_TYPES = ('inbound', 'outbound', 'consume')
    if mov_type not in VALID_TYPES:
        return jsonify({'success': False,
                        'message': f'type 必須為 {"/".join(VALID_TYPES)}'}), 400
    if not warehouse_id:
        return jsonify({'success': False, 'message': '請選擇倉庫'}), 400
    if not items:
        return jsonify({'success': False, 'message': '品項清單不能為空'}), 400

    w = Warehouse.find_by_id(warehouse_id)
    if not w:
        return jsonify({'success': False, 'message': '倉庫不存在'}), 404

    operator = get_jwt_identity()
    results  = []
    errors   = []

    # 批次查詢所有 product，避免 N+1；逐筆轉 ObjectId 讓格式錯誤可單獨回報
    from bson import ObjectId, errors as bson_errors
    from src.mongo import get_db
    _oid_map: dict = {}
    _invalid_ids: set = set()
    _valid_oids = []
    for item in items:
        pid = item.get('product_id', '')
        if not pid:
            continue
        try:
            _valid_oids.append(ObjectId(pid))
        except bson_errors.InvalidId:
            _invalid_ids.add(pid)
    if _valid_oids:
        _oid_map = {
            str(p['_id']): p
            for p in get_db()['products'].find(
                {'_id': {'$in': list(set(_valid_oids))}},
                {'name': 1, 'sku': 1},
            )
        }

    for idx, item in enumerate(items):
        product_id = item.get('product_id', '')
        qty_raw    = item.get('qty', 0)
        try:
            qty = int(qty_raw)
        except (ValueError, TypeError):
            errors.append(f'第 {idx+1} 筆數量格式錯誤')
            continue
        if qty <= 0:
            errors.append(f'第 {idx+1} 筆數量必須大於 0')
            continue

        if not product_id:
            errors.append(f'第 {idx+1} 筆產品 ID 不能為空')
            continue
        if product_id in _invalid_ids:
            errors.append(f'第 {idx+1} 筆產品 ID 格式錯誤 (id={product_id})')
            continue
        p = _oid_map.get(product_id)
        if not p:
            errors.append(f'第 {idx+1} 筆產品不存在 (id={product_id})')
            continue

        # inbound = 正數；outbound / consume = 負數
        delta = qty if mov_type == 'inbound' else -qty
        before_qty, after_qty = Inventory.adjust(
            product_id=product_id,
            warehouse_id=warehouse_id,
            delta=delta,
        )
        StockMovement.create(
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=mov_type,
            quantity=delta,
            before_qty=before_qty,
            after_qty=after_qty,
            product_name=p['name'],
            product_sku=p['sku'],
            warehouse_name=w['name'],
            reference_type='quick',
            remark=remark,
            operator=operator,
        )
        results.append({
            'product_id':   product_id,
            'product_name': p['name'],
            'before_qty':   before_qty,
            'after_qty':    after_qty,
        })

    if errors and not results:
        return jsonify({'success': False, 'message': '；'.join(errors)}), 400

    label = MOVEMENT_LABEL.get(mov_type, mov_type)
    Log.create(operator, f'快速{label}',
               f"warehouse={w['name']} items={len(results)}")
    return jsonify({
        'success':  True,
        'results':  results,
        'errors':   errors,
        'message':  f'成功 {len(results)} 筆' + (f'，{len(errors)} 筆失敗' if errors else ''),
    }), 207 if errors else 200


@app_inventory.route('/movement/', methods=['GET'])
@jwt_required()
def list_movements():
    _maybe_auto_cleanup_movements()
    warehouse_id  = request.args.get('warehouse_id', '')
    product_id    = request.args.get('product_id', '')
    movement_type = request.args.get('movement_type', '')
    limit         = min(int(request.args.get('limit', 200)), 1000)
    # product_only=1（預設）：後台只顯示產品資料操作，菜單品項觸發的只紀錄不顯示
    product_only  = request.args.get('product_only', '1') != '0'
    data = StockMovement.find_all(
        warehouse_id=warehouse_id or None,
        product_id=product_id or None,
        movement_type=movement_type or None,
        limit=limit,
        product_only=product_only,
    )
    return jsonify({'success': True, 'data': data})
