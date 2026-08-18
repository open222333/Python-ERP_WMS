from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from src.mongo import get_db
# [REFACTOR] 狀態字串改由 src/constants.py 統一管理
from src.constants import PosOrderStatus
import random, string


def _to_object_id(value, field_name: str):
    """
    Convert *value* to ObjectId, raising ValueError with a clear message on
    failure.  Treats None, empty string, and the literal string 'None' all as
    absent (returns None).
    """
    if value is None or value == '' or value == 'None':
        return None
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise ValueError(f'{field_name} 格式無效: {value!r}')


def _gen_order_no() -> str:
    d = datetime.utcnow().strftime('%Y%m%d')
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f'POS-{d}-{rand}'


def _item_consume_links(item: dict, wid_obj) -> list:
    """
    回傳該品項需要扣減的庫存清單。
    支援新格式 linked_products 及舊格式 product_id/warehouse_id/consume_qty。
    每筆：{'pid_obj', 'wid_obj', 'need_qty', 'consume_qty'}
    """
    qty = item['quantity']
    lps = item.get('linked_products') or []
    if lps:
        result = []
        for lp in lps:
            pid = lp.get('product_id')
            if not pid:
                continue
            cqty = max(1, int(lp.get('consume_qty', 1) or 1))
            w_obj = ObjectId(lp['warehouse_id']) if lp.get('warehouse_id') else wid_obj
            result.append({'pid_obj': ObjectId(pid), 'wid_obj': w_obj,
                           'consume_qty': cqty, 'need_qty': qty * cqty})
        return result
    # 舊格式向下相容
    if item.get('product_id'):
        cqty = max(1, int(item.get('consume_qty', 1) or 1))
        w_obj = ObjectId(item['warehouse_id']) if item.get('warehouse_id') else wid_obj
        return [{'pid_obj': ObjectId(item['product_id']), 'wid_obj': w_obj,
                 'consume_qty': cqty, 'need_qty': qty * cqty}]
    return []


def _fmt(doc) -> dict:
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['_id'] = str(doc['_id'])
    for key in ('warehouse_id', 'store_id'):
        if key in d and d[key]:
            d[key] = str(d[key])
    for key in ('created_at', 'refunded_at'):
        if key in d and d[key]:
            d[key] = d[key].isoformat() + 'Z'
    # 確保 source 欄位存在（舊資料向下相容）
    d.setdefault('source', 'pos')
    # 序列化 items 內的 ObjectId（product_id 在 DB 中以 ObjectId 儲存）
    for item in d.get('items', []):
        if item.get('product_id') is not None:
            item['product_id'] = str(item['product_id'])
    return d


class PosOrder:
    COLLECTION = 'pos_orders'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_all(cls, date_from: datetime = None, date_to: datetime = None,
                 cashier: str = None, status: str = None, source: str = None,
                 limit: int = 200, store_filter: dict = None) -> list:
        q = dict(store_filter or {})
        if date_from or date_to:
            q['created_at'] = {}
            if date_from:
                q['created_at']['$gte'] = date_from
            if date_to:
                q['created_at']['$lte'] = date_to
        if cashier:
            q['cashier'] = cashier
        if status:
            q['status'] = status
        if source == 'pos':
            # 僅 POS 現場：source 為 'pos' 或欄位不存在（舊資料）
            q['$or'] = [{'source': 'pos'}, {'source': {'$exists': False}}]
        elif source:
            q['source'] = source
        docs = cls._col().find(q).sort('created_at', -1).limit(limit)
        return [_fmt(d) for d in docs]

    # [OPT] 銷售報表改用 MongoDB aggregation 統計，取代撈全部訂單再 Python groupby
    @classmethod
    def summary(cls, date_from: datetime, date_to: datetime,
                granularity: str = 'day', status: str = PosOrderStatus.COMPLETED,
                store_filter: dict = None) -> dict:
        """
        以 aggregation 統計期間內訂單。
        granularity: 'day' → 依日分組（YYYY-MM-DD）；'month' → 依月分組（YYYY-MM）
        回傳 {'total_orders', 'total_amount', 'total_discount', 'cash_total',
              'card_total', 'breakdown': [{'period','orders','amount','discount'}]}
        """
        match = dict(store_filter or {})
        match['created_at'] = {'$gte': date_from, '$lte': date_to}
        if status:
            match['status'] = status
        fmt = '%Y-%m' if granularity == 'month' else '%Y-%m-%d'
        pipeline = [
            {'$match': match},
            {'$group': {
                '_id': {'$dateToString': {'format': fmt, 'date': '$created_at',
                                          'onNull': ''}},
                'orders':   {'$sum': 1},
                'amount':   {'$sum': {'$ifNull': ['$total_amount', 0]}},
                'discount': {'$sum': {'$ifNull': ['$discount', 0]}},
                'cash':     {'$sum': {'$cond': [
                    {'$in': ['$payment_type', ['cash', 'mixed']]},
                    {'$ifNull': ['$cash_amount', 0]}, 0]}},
                'card':     {'$sum': {'$cond': [
                    {'$in': ['$payment_type', ['card', 'mixed']]},
                    {'$ifNull': ['$card_amount', 0]}, 0]}},
            }},
            {'$sort': {'_id': 1}},
        ]
        groups = list(cls._col().aggregate(pipeline))
        return {
            'total_orders':   sum(g['orders']   for g in groups),
            'total_amount':   round(sum(g['amount']   for g in groups), 2),
            'total_discount': round(sum(g['discount'] for g in groups), 2),
            'cash_total':     round(sum(g['cash']     for g in groups), 2),
            'card_total':     round(sum(g['card']     for g in groups), 2),
            'breakdown': [
                {'period':   g['_id'],
                 'orders':   g['orders'],
                 'amount':   round(g['amount'],   2),
                 'discount': round(g['discount'], 2)}
                for g in groups
            ],
        }

    @classmethod
    def find_by_id(cls, sid: str, store_filter: dict = None) -> dict:
        try:
            q = {'_id': ObjectId(sid)}
            if store_filter:
                q.update(store_filter)
            return _fmt(cls._col().find_one(q))
        except Exception:
            return None

    @classmethod
    def create_sale(cls, warehouse_id: str, items: list, payment: dict,
                    discount: float, cashier: str, remark: str = '',
                    store_id: str = None) -> dict:
        """
        建立銷售單並原子性扣減庫存。
        items: [{product_id, product_name, product_sku, unit, quantity, unit_price}]
        payment: {type: cash|card|mixed, cash_amount, card_amount}
        回傳 {'success': bool, 'order': dict|None, 'error': str}
        """
        from src.models.inventory import Inventory, StockMovement
        from src.models.warehouse import Warehouse

        db = get_db()
        inv_col = db['inventory']
        wid_obj = _to_object_id(warehouse_id, 'warehouse_id')
        if wid_obj is None:
            raise ValueError(f'warehouse_id 格式無效: {warehouse_id!r}')
        w = Warehouse.find_by_id(warehouse_id)

        now = datetime.utcnow()

        # ── 只針對「消耗庫存」品項做前置庫存檢查（支援多商品連結）────────
        for item in items:
            if not item.get('consume_inventory', True):
                continue
            for lp in _item_consume_links(item, wid_obj):
                inv = inv_col.find_one(
                    {'product_id': lp['pid_obj'], 'warehouse_id': lp['wid_obj']})
                current = inv['quantity'] if inv else 0
                if current < lp['need_qty']:
                    cqty = lp['consume_qty']
                    need_str = (f"{item['quantity']}×{cqty}={lp['need_qty']}"
                                if cqty > 1 else str(lp['need_qty']))
                    return {
                        'success': False,
                        'error': (f"產品「{item['product_name']}」庫存不足"
                                  f"（現有 {current}，需求 {need_str}）"),
                    }

        # ── 逐筆原子扣庫存（每個 linked_product 各自扣）──
        # deducted：已成功扣減的明細，用於 rollback 及 StockMovement
        deducted = []
        for item in items:
            if not item.get('consume_inventory', True):
                continue
            for lp in _item_consume_links(item, wid_obj):
                result = inv_col.find_one_and_update(
                    {'product_id': lp['pid_obj'], 'warehouse_id': lp['wid_obj'],
                     'quantity': {'$gte': lp['need_qty']}},
                    {'$inc': {'quantity': -lp['need_qty']},
                     '$set': {'updated_at': now}},
                    return_document=True,
                )
                if result is None:
                    # race condition — rollback 已扣的
                    for done in deducted:
                        inv_col.update_one(
                            {'product_id': done['pid_obj'],
                             'warehouse_id': done['wid_obj']},
                            {'$inc': {'quantity': done['deduct_qty']},
                             '$set': {'updated_at': now}},
                        )
                    return {
                        'success': False,
                        'error': f"產品「{item['product_name']}」庫存不足（並發衝突），請重試",
                    }
                deducted.append({
                    'pid_obj':     lp['pid_obj'],
                    'wid_obj':     lp['wid_obj'],
                    'deduct_qty':  lp['need_qty'],
                    'before_qty':  result['quantity'] + lp['need_qty'],
                    'after_qty':   result['quantity'],
                    'product_id':  str(lp['pid_obj']),
                    'warehouse_id': str(lp['wid_obj']) if lp['wid_obj'] != wid_obj else '',
                    'product_name': item['product_name'],
                    'product_sku':  item.get('product_sku', ''),
                })

        # ── 計算金額 ────────────────────────────────────
        subtotal = sum(i['quantity'] * i['unit_price'] for i in items)
        total    = round(subtotal - discount, 2)
        pay_type = payment.get('type', 'cash')
        cash_amt = float(payment.get('cash_amount', 0))
        card_amt = float(payment.get('card_amount', 0))
        change   = round(cash_amt - total, 2) if cash_amt > 0 else 0

        # ── 建立銷售單 ──────────────────────────────────
        def _primary_pid(i):
            """取品項的主要 product_id（用於訂單記錄，顯示用途）"""
            lps = i.get('linked_products') or []
            if lps and lps[0].get('product_id'):
                return ObjectId(lps[0]['product_id'])
            if i.get('product_id'):
                return ObjectId(i['product_id'])
            return None

        order_doc = {
            'order_no':      _gen_order_no(),
            'warehouse_id':  wid_obj,
            'warehouse_name': w['name'] if w else '',
            'items': [{
                'product_id':              _primary_pid(i),
                'product_name':            i['product_name'],
                'product_sku':             i['product_sku'],
                'unit':                    i.get('unit', '個'),
                'quantity':                i['quantity'],
                'unit_price':              i['unit_price'],
                'subtotal':                round(i['quantity'] * i['unit_price'], 2),
                'customizations_selected': i.get('customizations_selected', []),
            } for i in items],
            'subtotal':      round(subtotal, 2),
            'discount':      round(discount, 2),
            'total_amount':  total,
            'payment_type':           pay_type,
            'cash_amount':            cash_amt,
            'card_amount':            card_amt,
            'change_amount':          max(change, 0),
            'linepay_transaction_id': str(payment.get('linepay_transaction_id', '')),
            'cashier':                cashier,
            'remark':                 remark,
            'status':                 PosOrderStatus.COMPLETED,
            'created_at':             now,
        }
        if store_id:
            sid_obj = _to_object_id(store_id, 'store_id')
            if sid_obj is None:
                raise ValueError(f'store_id 格式無效: {store_id!r}')
            order_doc['store_id'] = sid_obj
        sid = str(db[cls.COLLECTION].insert_one(order_doc).inserted_id)

        # ── 記錄 StockMovement（每個 linked_product 各一筆）──────────────────────────
        for done in deducted:
            done_wid_str = done['warehouse_id'] or warehouse_id
            done_w = Warehouse.find_by_id(done_wid_str) if done['warehouse_id'] else w
            StockMovement.create(
                product_id=done['product_id'],
                warehouse_id=done_wid_str,
                movement_type='outbound',
                quantity=-done['deduct_qty'],
                before_qty=done['before_qty'],
                after_qty=done['after_qty'],
                product_name=done['product_name'],
                product_sku=done['product_sku'],
                warehouse_name=done_w['name'] if done_w else '',
                reference_type='pos_order',
                reference_id=sid,
                remark=f"POS 銷售 {order_doc['order_no']}",
                operator=cashier,
            )

        order_doc['_id'] = sid
        order_doc['warehouse_id'] = warehouse_id
        order_doc['created_at'] = now.isoformat() + 'Z'
        if 'store_id' in order_doc:
            order_doc['store_id'] = str(order_doc['store_id'])
        for i in order_doc['items']:
            i['product_id'] = str(i['product_id']) if i['product_id'] else None
        return {'success': True, 'order': order_doc}

    @classmethod
    def create_from_delivery(cls, delivery_order: dict,
                              warehouse_id: str, operator: str,
                              settings: dict = None) -> dict:
        """
        從外送訂單建立銷售紀錄。對應解析順序（每品項）：
        1. delivery_mappings（platform + external_id）
           - 菜單品項對應（menu_item_id）→ 依品項 linked_products 扣庫存（可多原料/跨倉）
           - 產品對應（product_id）→ 於預設倉扣庫存（既有行為）
        2. 名稱式對應：settings.item_mappings（店家/全域），空則回退 mapping_template
           system_items 支援 {type:'menu_item', menu_id, menu_item_id} 與
           {product_id, qty}（無 type 視為 product，向下相容）
        3. 無對應 → 僅記錄銷售，不動庫存（items 保留平台原名稱）
        回傳 {'success': bool, 'sale_id': str, 'skipped_items': list, 'error': str}
        """
        from src.models.inventory import Inventory, StockMovement
        from src.models.warehouse import Warehouse
        from src.models.product import Product

        # 防止重複建立
        platform = delivery_order.get('platform', '')
        del_oid  = delivery_order.get('_id', '')
        existing = cls._col().find_one(
            {'delivery_order_id': del_oid, 'source': platform}
        )
        if existing:
            return {'success': True, 'sale_id': str(existing['_id']),
                    'duplicate': True}

        db       = get_db()
        inv_col  = db['inventory']
        wid_obj  = ObjectId(warehouse_id)
        w        = Warehouse.find_by_id(warehouse_id)
        now      = datetime.utcnow()

        # ── 批次查詢商品映射（避免 N+1）──────────────────
        maps_col  = db['delivery_mappings']
        raw_items = delivery_order.get('items', [])
        sale_items = []
        skipped    = []

        ext_ids = [str(ri.get('external_id', '')) for ri in raw_items if ri.get('external_id')]
        mapping_map = {
            m['external_product_id']: m
            for m in maps_col.find({'platform': platform, 'external_product_id': {'$in': ext_ids}})
        } if ext_ids else {}

        # ── 名稱式對應表（店家/全域 item_mappings，空則回退模板）────
        name_map = {}
        s = settings or {}
        raw_name_mappings = s.get('item_mappings') or []
        if not raw_name_mappings and s.get('mapping_template_id'):
            from src.models.delivery import DeliveryMappingTemplate
            tpl = DeliveryMappingTemplate.find_by_id(s['mapping_template_id'])
            raw_name_mappings = (tpl or {}).get('items', [])
        for nm in raw_name_mappings:
            nm_key = (nm.get('platform_item_name') or '').strip().lower()
            if nm_key:
                name_map[nm_key] = nm.get('system_items', [])

        mapped_pids = [ObjectId(m['product_id']) for m in mapping_map.values() if m.get('product_id')]
        for sis in name_map.values():
            for si in sis:
                if si.get('product_id') and si.get('type', 'product') == 'product':
                    try:
                        mapped_pids.append(ObjectId(si['product_id']))
                    except Exception:
                        pass
        product_map = {
            str(p['_id']): p
            for p in db['products'].find({'_id': {'$in': mapped_pids}})
        } if mapped_pids else {}

        from src.models.menu import Menu

        def _menu_consumptions(menu_id, item_id, times):
            """菜單品項 → linked_products 消耗清單；回傳 (menu_item, [consumption])"""
            mi = Menu.find_item(menu_id, item_id)
            if not mi:
                return None, []
            cons = []
            for lp in mi.get('linked_products', []):
                if not lp.get('product_id'):
                    continue
                cons.append({
                    'product_id':   str(lp['product_id']),
                    'warehouse_id': str(lp['warehouse_id']) if lp.get('warehouse_id') else warehouse_id,
                    'qty':          max(1, int(lp.get('consume_qty', 1) or 1)) * times,
                })
            return mi, cons

        consumptions = []  # 待扣庫存清單 [{product_id, warehouse_id, qty, sale_idx}]

        for ri in raw_items:
            ext_id  = str(ri.get('external_id', ''))
            qty     = int(ri.get('quantity', 1))
            mapping = mapping_map.get(ext_id) if ext_id else None
            idx     = len(sale_items)

            sale_item = {
                'product_id':     None,
                'menu_item_id':   None,
                'menu_item_name': '',
                'product_name':   ri.get('product_name', ''),
                'product_sku':    '',
                'unit':           '份',
                'quantity':       qty,
                'unit_price':     float(ri.get('unit_price', 0)),
                'has_mapping':    False,
            }

            if mapping and mapping.get('menu_item_id'):
                # 1a. external_id → 菜單品項
                mi, cons = _menu_consumptions(mapping.get('menu_id'),
                                              mapping['menu_item_id'], qty)
                if mi:
                    sale_item.update({
                        'menu_item_id':   str(mapping['menu_item_id']),
                        'menu_item_name': mi.get('name', ''),
                        'has_mapping':    True,
                    })
                    for c in cons:
                        c['sale_idx'] = idx
                    consumptions.extend(cons)
                else:
                    skipped.append(f"{sale_item['product_name']}（菜單品項已不存在）")
            elif mapping and mapping.get('product_id'):
                # 1b. external_id → 產品（既有行為）
                product = product_map.get(str(mapping['product_id']))
                sale_item.update({
                    'product_id':   str(mapping['product_id']),
                    'product_name': product.get('name', '') if product
                                    else sale_item['product_name'],
                    'product_sku':  product.get('sku', '') if product else '',
                    'unit':         product.get('unit', '份') if product else '份',
                    'has_mapping':  True,
                })
                consumptions.append({'product_id': str(mapping['product_id']),
                                     'warehouse_id': warehouse_id,
                                     'qty': qty, 'sale_idx': idx})
            else:
                # 2. 名稱式對應（item_mappings / 模板）
                sis = name_map.get((ri.get('product_name') or '').strip().lower(), [])
                matched = False
                for si in sis:
                    si_qty = max(1, int(si.get('qty', 1) or 1))
                    if si.get('type') == 'menu_item' and si.get('menu_item_id'):
                        mi, cons = _menu_consumptions(si.get('menu_id'),
                                                      si['menu_item_id'], qty * si_qty)
                        if mi:
                            matched = True
                            if not sale_item['menu_item_id']:
                                sale_item.update({
                                    'menu_item_id':   str(si['menu_item_id']),
                                    'menu_item_name': mi.get('name', ''),
                                })
                            for c in cons:
                                c['sale_idx'] = idx
                            consumptions.extend(cons)
                    elif si.get('product_id'):
                        matched = True
                        if not sale_item['product_id']:
                            product = product_map.get(str(si['product_id']))
                            sale_item.update({
                                'product_id':  str(si['product_id']),
                                'product_sku': product.get('sku', '') if product else '',
                                'unit':        product.get('unit', '份') if product else '份',
                            })
                        consumptions.append({'product_id': str(si['product_id']),
                                             'warehouse_id': warehouse_id,
                                             'qty': qty * si_qty, 'sale_idx': idx})
                if matched:
                    sale_item['has_mapping'] = True
                else:
                    skipped.append(ri.get('product_name', ext_id))

            sale_items.append(sale_item)

        # ── 原子扣庫存（依消耗清單逐筆，支援跨倉）──────────
        deducted = []
        prod_cache = {}
        for c in consumptions:
            c_qty = c['qty']
            try:
                pid_obj = ObjectId(c['product_id'])
                c_wid   = ObjectId(c['warehouse_id'])
            except Exception:
                skipped.append(f"{sale_items[c['sale_idx']]['product_name']}（對應資料無效）")
                continue
            result = inv_col.find_one_and_update(
                {'product_id': pid_obj, 'warehouse_id': c_wid,
                 'quantity': {'$gte': c_qty}},
                {'$inc': {'quantity': -c_qty}, '$set': {'updated_at': now}},
                return_document=True,
            )
            if result:
                p = prod_cache.get(c['product_id']) or product_map.get(c['product_id']) \
                    or db['products'].find_one({'_id': pid_obj}) or {}
                prod_cache[c['product_id']] = p
                deducted.append({
                    'product_id':   c['product_id'],
                    'warehouse_id': c['warehouse_id'],
                    'quantity':     c_qty,
                    'before_qty':   result['quantity'] + c_qty,
                    'after_qty':    result['quantity'],
                    'product_name': p.get('name', sale_items[c['sale_idx']]['product_name']),
                    'product_sku':  p.get('sku', ''),
                })
            else:
                skipped.append(f"{sale_items[c['sale_idx']]['product_name']}（庫存不足）")

        # ── 計算金額 ────────────────────────────────────
        subtotal     = sum(i['quantity'] * i['unit_price'] for i in sale_items)
        discount     = float(delivery_order.get('discount', 0))
        delivery_fee = float(delivery_order.get('delivery_fee', 0))
        # total_amount 只計食品金額（不含外送費，平台通常自留），避免虛高營收
        total        = round(subtotal - discount, 2)

        # ── 建立銷售單 ──────────────────────────────────
        placed_str = delivery_order.get('placed_at', delivery_order.get('created_at', ''))
        try:
            placed_at = datetime.fromisoformat(
                placed_str.replace('Z','').replace('+00:00','')) \
                if placed_str else now
        except Exception:
            placed_at = now

        order_doc = {
            'order_no':          _gen_order_no(),
            'source':            platform,
            'delivery_order_id': del_oid,
            'external_order_no': delivery_order.get('external_order_no', ''),
            'warehouse_id':      wid_obj,
            'warehouse_name':    w['name'] if w else '',
            'customer_name':     delivery_order.get('customer_name', ''),
            'items': [{
                'product_id':     ObjectId(i['product_id']) if i['product_id'] else None,
                'menu_item_id':   i.get('menu_item_id'),
                'menu_item_name': i.get('menu_item_name', ''),
                'product_name':   i['product_name'],
                'product_sku':    i['product_sku'],
                'unit':           i['unit'],
                'quantity':       i['quantity'],
                'unit_price':     i['unit_price'],
                'subtotal':       round(i['quantity'] * i['unit_price'], 2),
            } for i in sale_items],
            'subtotal':      round(subtotal, 2),
            'delivery_fee':  delivery_fee,
            'discount':      discount,
            'total_amount':  total,
            'payment_type':  delivery_order.get('payment_method', 'online'),
            'cash_amount':   0.0,
            'card_amount':   0.0,
            'change_amount': 0.0,
            'cashier':       operator,
            'remark':        delivery_order.get('note', ''),
            'status':        PosOrderStatus.COMPLETED,
            'created_at':    placed_at,
        }
        sid = str(db[cls.COLLECTION].insert_one(order_doc).inserted_id)

        # ── 記錄 StockMovement（有扣庫存的品項，倉別依消耗清單）──
        ext_no = delivery_order.get('external_order_no', '')
        wh_cache = {warehouse_id: w}
        for item in deducted:
            wid_i = item['warehouse_id']
            if wid_i not in wh_cache:
                wh_cache[wid_i] = Warehouse.find_by_id(wid_i)
            StockMovement.create(
                product_id=item['product_id'],
                warehouse_id=wid_i,
                movement_type='outbound',
                quantity=-item['quantity'],
                before_qty=item['before_qty'],
                after_qty=item['after_qty'],
                product_name=item['product_name'],
                product_sku=item['product_sku'],
                warehouse_name=(wh_cache[wid_i] or {}).get('name', ''),
                reference_type='delivery_order',
                reference_id=del_oid,
                remark=f"{platform} 外送 {ext_no}",
                operator=operator,
            )

        return {
            'success':       True,
            'sale_id':       sid,
            'skipped_items': skipped,
        }

    @classmethod
    def create_from_cust_order(cls, cust_order: dict, operator: str) -> str:
        """
        顧客點單完成時，自動建立對應的銷售記錄（不扣庫存）。
        回傳新建的 pos_order _id (str)，若已存在則回傳既有 _id。
        """
        co_id = cust_order.get('_id', '')
        existing = cls._col().find_one({'cust_order_id': co_id, 'source': 'cust_order'})
        if existing:
            return str(existing['_id'])

        now   = datetime.utcnow()
        total = float(cust_order.get('total', 0))

        sale_items = [{
            'product_id':   None,
            'product_name': i.get('item_name', ''),
            'product_sku':  '',
            'unit':         '份',
            'quantity':     int(i.get('qty', 1)),
            'unit_price':   float(i.get('price', 0)),
            'subtotal':     round(int(i.get('qty', 1)) * float(i.get('price', 0)), 2),
            'customizations_selected': i.get('customizations', []),
        } for i in cust_order.get('items', [])]

        order_doc = {
            'order_no':               f"CO-{cust_order.get('order_no', '')}",
            'warehouse_id':           None,
            'warehouse_name':         '',
            'items':                  sale_items,
            'subtotal':               total,
            'discount':               0.0,
            'total_amount':           total,
            'payment_type':           'cash',
            'cash_amount':            total,
            'card_amount':            0.0,
            'change_amount':          0.0,
            'linepay_transaction_id': '',
            'cashier':                operator,
            'remark':                 f"顧客點單 桌號：{cust_order.get('table_no', '')}",
            'status':                 PosOrderStatus.COMPLETED,
            'source':                 'cust_order',
            'cust_order_id':          co_id,
            'created_at':             now,
        }
        return str(get_db()[cls.COLLECTION].insert_one(order_doc).inserted_id)

    @classmethod
    def bulk_import(cls, rows: list) -> int:
        """
        批次匯入歷史銷售紀錄（僅寫入記錄，不執行庫存扣減）。
        支援從 export 匯出的 CSV 欄位，或自訂 JSON 陣列。
        回傳成功插入筆數。
        """
        docs = []
        for r in rows:
            order_no = str(r.get('order_no') or '').strip() or _gen_order_no()
            source   = str(r.get('source')   or 'pos').strip()

            def _f(key, default=0.0):
                try:    return float(r.get(key) or default)
                except: return default  # noqa: E722

            total_amount  = _f('total_amount')
            subtotal      = _f('subtotal', total_amount)
            discount      = _f('discount')
            cash_amount   = _f('cash_amount')
            card_amount   = _f('card_amount')
            change_amount = _f('change_amount')

            try:
                raw_ts = str(r.get('created_at') or '').rstrip('Z')
                created_at = datetime.fromisoformat(raw_ts) if raw_ts else datetime.utcnow()
            except (ValueError, TypeError):
                created_at = datetime.utcnow()

            status_raw = str(r.get('status') or PosOrderStatus.COMPLETED).strip()
            status = status_raw if status_raw in PosOrderStatus.IMPORTABLE else PosOrderStatus.COMPLETED

            docs.append({
                'order_no':      order_no,
                'source':        source,
                'warehouse_name': str(r.get('warehouse_name') or ''),
                'cashier':       str(r.get('cashier')        or ''),
                'items':         [],          # 歷史匯入無品項明細
                'subtotal':      subtotal,
                'discount':      discount,
                'total_amount':  total_amount,
                'payment_type':  str(r.get('payment_type')   or 'cash'),
                'cash_amount':   cash_amount,
                'card_amount':   card_amount,
                'change_amount': change_amount,
                'remark':        str(r.get('remark')         or ''),
                'status':        status,
                'created_at':    created_at,
                'imported':      True,        # 標記為匯入資料
            })

        if docs:
            cls._col().insert_many(docs)
        return len(docs)

    @classmethod
    def refund(cls, sid: str, reason: str, operator: str) -> dict:
        """
        退款：把 status 改為 refunded，並回補庫存。
        回傳 {'success': bool, 'error': str}
        """
        from src.models.inventory import Inventory, StockMovement
        from src.models.warehouse import Warehouse

        order = cls._col().find_one({'_id': ObjectId(sid), 'status': {'$in': list(PosOrderStatus.REFUNDABLE)}})
        if not order:
            return {'success': False, 'error': '銷售單不存在或已退款'}

        now = datetime.utcnow()
        raw_wid = order.get('warehouse_id')
        # Guard against None, empty string, or the literal string 'None' stored
        # in older documents; any of those means "no warehouse tracked".
        _raw_wid_str = str(raw_wid) if raw_wid is not None else ''
        warehouse_id = _raw_wid_str if _raw_wid_str not in ('', 'None') else None
        w = Warehouse.find_by_id(warehouse_id) if warehouse_id else None

        for item in order['items']:
            if not item.get('product_id'):
                continue
            if not warehouse_id:
                # Skip inventory restore for orders without warehouse tracking
                pass
            else:
                before_qty, after_qty = Inventory.adjust(
                    product_id=str(item['product_id']),
                    warehouse_id=warehouse_id,
                    delta=item['quantity'],
                )
                StockMovement.create(
                    product_id=str(item['product_id']),
                    warehouse_id=warehouse_id,
                    movement_type='inbound',
                    quantity=item['quantity'],
                    before_qty=before_qty,
                    after_qty=after_qty,
                    product_name=item['product_name'],
                    product_sku=item['product_sku'],
                    warehouse_name=w['name'] if w else '',
                    reference_type='pos_refund',
                    reference_id=sid,
                    remark=f"POS 退款 {order['order_no']}",
                    operator=operator,
                )

        cls._col().update_one(
            {'_id': ObjectId(sid)},
            {'$set': {'status': PosOrderStatus.REFUNDED, 'refund_reason': reason,
                      'refunded_by': operator, 'refunded_at': now}},
        )
        return {'success': True}
