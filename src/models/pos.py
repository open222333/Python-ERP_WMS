from datetime import datetime
from bson import ObjectId
from src.mongo import get_db
import random, string


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
    for key in ('warehouse_id',):
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
                 limit: int = 200) -> list:
        q = {}
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

    @classmethod
    def find_by_id(cls, sid: str) -> dict:
        try:
            return _fmt(cls._col().find_one({'_id': ObjectId(sid)}))
        except Exception:
            return None

    @classmethod
    def create_sale(cls, warehouse_id: str, items: list, payment: dict,
                    discount: float, cashier: str, remark: str = '') -> dict:
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
        wid_obj = ObjectId(warehouse_id)
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
            'payment_type':  pay_type,
            'cash_amount':   cash_amt,
            'card_amount':   card_amt,
            'change_amount': max(change, 0),
            'cashier':       cashier,
            'remark':        remark,
            'status':        'completed',
            'created_at':    now,
        }
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
        for i in order_doc['items']:
            i['product_id'] = str(i['product_id']) if i['product_id'] else None
        return {'success': True, 'order': order_doc}

    @classmethod
    def create_from_delivery(cls, delivery_order: dict,
                              warehouse_id: str, operator: str) -> dict:
        """
        從外送訂單建立銷售紀錄。
        - delivery_mappings 有對應 → 比照 POS 原子扣庫存
        - 無對應 → 僅記錄銷售，不動庫存（items 保留平台原名稱）
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

        # ── 查詢商品映射 ────────────────────────────────
        maps_col     = db['delivery_mappings']
        raw_items    = delivery_order.get('items', [])
        sale_items   = []
        skipped      = []

        for ri in raw_items:
            ext_id  = str(ri.get('external_id', ''))
            mapping = maps_col.find_one(
                {'platform': platform, 'external_product_id': ext_id}
            ) if ext_id else None
            product = Product.find_by_id(str(mapping['product_id'])) \
                      if mapping else None

            sale_items.append({
                'product_id':   str(mapping['product_id']) if mapping else None,
                'product_name': product['name'] if product
                                else ri.get('product_name', ''),
                'product_sku':  product.get('sku', '') if product else '',
                'unit':         product.get('unit', '份') if product else '份',
                'quantity':     int(ri.get('quantity', 1)),
                'unit_price':   float(ri.get('unit_price', 0)),
                'has_mapping':  mapping is not None,
            })
            if not mapping:
                skipped.append(ri.get('product_name', ext_id))

        # ── 原子扣庫存（只扣有映射的品項）──────────────
        deducted = []
        for item in sale_items:
            if not item['has_mapping']:
                continue
            qty     = item['quantity']
            pid_obj = ObjectId(item['product_id'])
            result  = inv_col.find_one_and_update(
                {'product_id': pid_obj, 'warehouse_id': wid_obj,
                 'quantity': {'$gte': qty}},
                {'$inc': {'quantity': -qty}, '$set': {'updated_at': now}},
                return_document=True,
            )
            if result:
                item['before_qty'] = result['quantity'] + qty
                item['after_qty']  = result['quantity']
                deducted.append(item)
            else:
                skipped.append(f"{item['product_name']}（庫存不足）")

        # ── 計算金額 ────────────────────────────────────
        subtotal     = sum(i['quantity'] * i['unit_price'] for i in sale_items)
        discount     = float(delivery_order.get('discount', 0))
        delivery_fee = float(delivery_order.get('delivery_fee', 0))
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
                'product_id':   ObjectId(i['product_id']) if i['product_id'] else None,
                'product_name': i['product_name'],
                'product_sku':  i['product_sku'],
                'unit':         i['unit'],
                'quantity':     i['quantity'],
                'unit_price':   i['unit_price'],
                'subtotal':     round(i['quantity'] * i['unit_price'], 2),
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
            'status':        'completed',
            'created_at':    placed_at,
        }
        sid = str(db[cls.COLLECTION].insert_one(order_doc).inserted_id)

        # ── 記錄 StockMovement（有扣庫存的品項）─────────
        ext_no = delivery_order.get('external_order_no', '')
        for item in deducted:
            StockMovement.create(
                product_id=item['product_id'],
                warehouse_id=warehouse_id,
                movement_type='outbound',
                quantity=-item['quantity'],
                before_qty=item['before_qty'],
                after_qty=item['after_qty'],
                product_name=item['product_name'],
                product_sku=item['product_sku'],
                warehouse_name=w['name'] if w else '',
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

            status_raw = str(r.get('status') or 'completed').strip()
            status = status_raw if status_raw in ('completed', 'refunded') else 'completed'

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

        order = cls._col().find_one({'_id': ObjectId(sid), 'status': 'completed'})
        if not order:
            return {'success': False, 'error': '銷售單不存在或已退款'}

        now = datetime.utcnow()
        warehouse_id = str(order['warehouse_id'])
        w = Warehouse.find_by_id(warehouse_id)

        for item in order['items']:
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
            {'$set': {'status': 'refunded', 'refund_reason': reason,
                      'refunded_by': operator, 'refunded_at': now}},
        )
        return {'success': True}
