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
                 limit: int = 200, store_filter: dict = None, offset: int = 0) -> list:
        q = cls._build_query(date_from, date_to, cashier, status, source, store_filter)
        # [U3] offset 分頁；_id 作次排序確保同一時間的資料翻頁時順序穩定
        docs = cls._col().find(q).sort([('created_at', -1), ('_id', -1)]).skip(max(0, offset)).limit(limit)
        return [_fmt(d) for d in docs]

    # [OPT-MEM] 匯出只需要的欄位；items 只取 quantity（計算 items_count 用），
    # 不帶完整品項明細與客製化選項，每筆文件體積大幅縮小。
    _EXPORT_PROJECTION = {
        'order_no': 1, 'source': 1, 'warehouse_name': 1, 'cashier': 1,
        'items.quantity': 1, 'subtotal': 1, 'discount': 1, 'total_amount': 1,
        'payment_type': 1, 'cash_amount': 1, 'change_amount': 1,
        'status': 1, 'remark': 1, 'created_at': 1,
    }

    @classmethod
    def iter_export(cls, date_from: datetime = None, date_to: datetime = None,
                    cashier: str = None, status: str = None, source: str = None,
                    store_filter: dict = None, batch_size: int = 500):
        """
        [OPT-MEM] 匯出用：逐筆讀取 cursor（每批 batch_size 筆），無筆數上限。
        原本 find_all(limit=0) 會把整個查詢結果（含完整 items）一次轉成 list，
        記憶體用量隨銷售筆數線性成長，多年資料一次匯出可能讓 worker OOM。
        """
        q = cls._build_query(date_from, date_to, cashier, status, source, store_filter)
        cursor = cls._col().find(q, cls._EXPORT_PROJECTION) \
                           .sort('created_at', -1).batch_size(batch_size)
        return (_fmt(d) for d in cursor)

    @staticmethod
    def _build_query(date_from: datetime = None, date_to: datetime = None,
                     cashier: str = None, status: str = None, source: str = None,
                     store_filter: dict = None) -> dict:
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
        return q

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
        顧客點單完成時，自動建立對應的銷售記錄，並依菜單品項設定扣庫存。
        回傳新建的 pos_order _id (str)，若已存在則回傳既有 _id。

        [D2] 原本完全不扣庫存，與 POS 結帳、外送接單規則不一致。現在比照 POS：
        菜單品項 consume_inventory=True 時依 linked_products（含 consume_qty、指定倉）扣庫；
        未指定倉的連結用本店倉庫（見 _resolve_cust_order_warehouse）。
        餐點已出，庫存不足時不阻擋，改記錄於銷售單 stock_skipped（與外送接單一致）。
        冪等：先寫入銷售單（cust_order_id 唯一索引），撞到重複代表已處理過，不再扣庫。
        """
        from pymongo.errors import DuplicateKeyError

        co_id = str(cust_order.get('_id', ''))
        existing = cls._col().find_one({'cust_order_id': co_id, 'source': 'cust_order'})
        if existing:
            return str(existing['_id'])

        now   = datetime.utcnow()
        total = float(cust_order.get('total', 0))
        default_wid = cls._resolve_cust_order_warehouse(cust_order.get('store_id'))
        default_w = None
        if default_wid:
            from src.models.warehouse import Warehouse
            default_w = Warehouse.find_by_id(default_wid)

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
            'warehouse_id':           ObjectId(default_wid) if default_wid else None,
            'warehouse_name':         (default_w or {}).get('name', ''),
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
        if cust_order.get('store_id'):
            order_doc['store_id'] = ObjectId(str(cust_order['store_id']))
        try:
            sid = str(get_db()[cls.COLLECTION].insert_one(order_doc).inserted_id)
        except DuplicateKeyError:
            # 並發下另一個請求已建立 → 回傳既有的，不重複扣庫
            existing = cls._col().find_one({'cust_order_id': co_id, 'source': 'cust_order'})
            return str(existing['_id']) if existing else ''

        skipped = cls._deduct_cust_order_stock(
            cust_order, sid, order_doc['order_no'], default_wid, operator)
        if skipped:
            cls._col().update_one({'_id': ObjectId(sid)},
                                  {'$set': {'stock_skipped': skipped}})
        return sid

    @staticmethod
    def _resolve_cust_order_warehouse(store_id) -> str:
        """
        掃碼點餐扣庫的預設倉庫（品項連結未指定倉時使用）：
        - 點單屬於某店：系統預設倉（default_warehouse_id）若屬於該店就用它，否則用該店第一個倉庫
        - 點單無店家（單店部署）：系統預設倉
        都找不到回 None（該品項扣庫略過並記錄）。
        """
        from src.models.settings import SystemSettings
        from src.models.warehouse import Warehouse
        default = str(SystemSettings.get('default_warehouse_id') or '')
        if store_id:
            ids = [w['_id'] for w in
                   Warehouse.find_all(store_filter={'store_id': ObjectId(str(store_id))})]
            if default in ids:
                return default
            return ids[0] if ids else None
        return default or None

    @classmethod
    def _deduct_cust_order_stock(cls, cust_order: dict, sid: str, order_no: str,
                                 default_wid: str, operator: str) -> list:
        """依菜單品項 linked_products 扣庫並寫 stock_movements（cust_order_sale）。回傳略過清單。"""
        from src.models.inventory import StockMovement
        from src.models.menu import Menu
        from src.models.warehouse import Warehouse

        inv_col = get_db()['inventory']
        default_wid_obj = ObjectId(default_wid) if default_wid else None
        menu_id = cust_order.get('menu_id') or None
        now = datetime.utcnow()
        skipped, wh_cache = [], {}

        for ci in cust_order.get('items', []):
            name = ci.get('item_name', '')
            mi = Menu.find_item(menu_id, ci.get('item_id')) if ci.get('item_id') else None
            if not mi:
                if ci.get('item_id'):
                    skipped.append(f'{name}（菜單品項已不存在）')
                continue
            if not mi.get('consume_inventory', False):
                continue   # 與 POS 一致：品項未設定「消耗庫存」就不扣
            links = _item_consume_links(
                {'quantity': int(ci.get('qty', 1)),
                 'linked_products': mi.get('linked_products', [])},
                default_wid_obj)
            for lp in links:
                if lp['wid_obj'] is None:
                    skipped.append(f'{name}（找不到扣庫倉庫）')
                    continue
                result = inv_col.find_one_and_update(
                    {'product_id': lp['pid_obj'], 'warehouse_id': lp['wid_obj'],
                     'quantity': {'$gte': lp['need_qty']}},
                    {'$inc': {'quantity': -lp['need_qty']}, '$set': {'updated_at': now}},
                    return_document=True,
                )
                if not result:
                    skipped.append(f'{name}（庫存不足）')
                    continue
                wid = str(lp['wid_obj'])
                if wid not in wh_cache:
                    wh_cache[wid] = Warehouse.find_by_id(wid)
                product = get_db()['products'].find_one({'_id': lp['pid_obj']}) or {}
                StockMovement.create(
                    product_id=str(lp['pid_obj']), warehouse_id=wid,
                    movement_type='outbound', quantity=-lp['need_qty'],
                    before_qty=result['quantity'] + lp['need_qty'],
                    after_qty=result['quantity'],
                    product_name=product.get('name', name),
                    product_sku=product.get('sku', ''),
                    warehouse_name=(wh_cache[wid] or {}).get('name', ''),
                    reference_type='cust_order_sale', reference_id=sid,
                    remark=f'掃碼點餐 {order_no}', operator=operator,
                )
        return skipped

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
        order = cls._col().find_one({'_id': ObjectId(sid), 'status': {'$in': list(PosOrderStatus.REFUNDABLE)}})
        if not order:
            return {'success': False, 'error': '銷售單不存在或已退款'}

        now = datetime.utcnow()
        # [D2] 依庫存異動帳（結帳時實際扣了什麼）原樣回補。
        # 舊做法以 items[].product_id × quantity 回補到訂單倉庫，與結帳的扣庫規則不一致：
        # 多原料連結、consume_qty>1、跨倉、consume_inventory=False 的品項都會補錯。
        cls._restore_stock_by_ledger(order, operator, 'pos_refund',
                                     f"POS 退款 {order['order_no']}")

        cls._col().update_one(
            {'_id': ObjectId(sid)},
            {'$set': {'status': PosOrderStatus.REFUNDED, 'refund_reason': reason,
                      'refunded_by': operator, 'refunded_at': now}},
        )
        return {'success': True}

    # ── [D2] 庫存回沖（依異動帳）─────────────────────────────
    @staticmethod
    def _stock_ref_of(order: dict) -> tuple:
        """
        銷售單扣庫時寫入 stock_movements 的 (reference_type, reference_id)：
        - POS 現場結帳       → ('pos_order', 銷售單 _id)
        - 掃碼點餐完成       → ('cust_order_sale', 銷售單 _id)
        - 外送平台接單       → ('delivery_order', 外送單 _id)
        """
        source = order.get('source') or 'pos'
        if source == 'pos':
            return 'pos_order', str(order['_id'])
        if source == 'cust_order':
            return 'cust_order_sale', str(order['_id'])
        if order.get('delivery_order_id'):
            return 'delivery_order', str(order['delivery_order_id'])
        return None, None

    @classmethod
    def _restore_stock_by_ledger(cls, order: dict, operator: str,
                                 restore_ref_type: str, remark: str) -> list:
        """
        把這張銷售單當初扣的庫存（stock_movements 中對應的 outbound 紀錄）原樣補回，
        回補紀錄寫 reference_type=restore_ref_type、reference_id=銷售單 _id。
        冪等：同一張銷售單若已有 restore_ref_type 的回補紀錄就不再補。
        回傳實際回補的明細（供呼叫端回報）。
        """
        from src.models.inventory import Inventory, StockMovement
        from src.models.warehouse import Warehouse

        sid = str(order['_id'])
        mv_col = StockMovement._col()
        if mv_col.find_one({'reference_type': restore_ref_type, 'reference_id': sid}):
            return []

        ref_type, ref_id = cls._stock_ref_of(order)
        if not ref_type:
            return []

        restored, wh_cache = [], {}
        for mv in mv_col.find({'reference_type': ref_type, 'reference_id': ref_id,
                               'movement_type': 'outbound'}):
            qty = abs(int(mv.get('quantity', 0)))
            if not qty:
                continue
            pid, wid = str(mv['product_id']), str(mv['warehouse_id'])
            before_qty, after_qty = Inventory.adjust(product_id=pid, warehouse_id=wid, delta=qty)
            if wid not in wh_cache:
                wh_cache[wid] = Warehouse.find_by_id(wid)
            StockMovement.create(
                product_id=pid, warehouse_id=wid,
                movement_type='inbound', quantity=qty,
                before_qty=before_qty, after_qty=after_qty,
                product_name=mv.get('product_name', ''),
                product_sku=mv.get('product_sku', ''),
                warehouse_name=(wh_cache[wid] or {}).get('name', mv.get('warehouse_name', '')),
                reference_type=restore_ref_type, reference_id=sid,
                remark=remark, operator=operator,
            )
            restored.append({'product_id': pid, 'warehouse_id': wid, 'quantity': qty})
        return restored

    @classmethod
    def void_delivery_sale(cls, delivery_order_id: str, platform: str,
                           operator: str, reason: str = '外送訂單取消') -> dict:
        """
        [D2] 外送訂單取消時作廢對應銷售紀錄並回補庫存。
        以 compare-and-set（completed → refunded）確保並發／重複推播只執行一次。
        回傳 {'voided': bool, 'sale_id': str | None, 'restored': list}
        """
        now = datetime.utcnow()
        order = cls._col().find_one_and_update(
            {'delivery_order_id': str(delivery_order_id), 'source': platform,
             'status': PosOrderStatus.COMPLETED},
            {'$set': {'status': PosOrderStatus.REFUNDED, 'refund_reason': reason,
                      'refunded_by': operator, 'refunded_at': now}},
        )
        if not order:
            return {'voided': False, 'sale_id': None, 'restored': []}
        restored = cls._restore_stock_by_ledger(
            order, operator, 'delivery_cancel',
            f"{platform} 外送取消 {order.get('external_order_no', '')}")
        return {'voided': True, 'sale_id': str(order['_id']), 'restored': restored}
