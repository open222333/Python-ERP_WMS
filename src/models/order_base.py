# [REFACTOR] 出入庫單共用基底類別：InboundOrder / OutboundOrder 原本近乎複製貼上的
#            CRUD、明細操作與狀態轉移（pending → confirmed → completed / cancelled）
#            抽至此。差異點以類別屬性表達：
#              - ORDER_NO_PREFIX / COUNTER_PREFIX：單號前綴（IN / OUT）與 counters key
#              - PARTY_FIELD：對象欄位名（supplier / customer）
#              - DONE_QTY_FIELD：完成數量欄位（received_qty / shipped_qty）
#            子類公開介面（方法名、參數、回傳值）與原實作完全一致。
#            complete() 統一採用原 InboundOrder 的原子版本（find_one_and_update 以
#            status=confirmed 為條件），防止並發雙重完成；對外回傳值語意不變。
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from src.mongo import get_db
from src.constants import OrderStatus


def _fmt_order(doc) -> dict:
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['_id'] = str(doc['_id'])
    if d.get('warehouse_id'):
        d['warehouse_id'] = str(d['warehouse_id'])
    # 格式化 items 內的 ObjectId
    items = []
    for item in d.get('items', []):
        item = dict(item)
        item['_id'] = str(item['_id'])
        if item.get('product_id'):
            item['product_id'] = str(item['product_id'])
        items.append(item)
    d['items'] = items
    # datetime -> isoformat
    for key in ('confirmed_at', 'completed_at', 'created_at', 'updated_at'):
        if d.get(key) and isinstance(d[key], datetime):
            d[key] = d[key].isoformat()
    return d


class OrderBase:
    COLLECTION = ''        # MongoDB collection 名稱
    ORDER_NO_PREFIX = ''   # 單號前綴：'IN' / 'OUT'
    COUNTER_PREFIX = ''    # counters collection key 前綴：'inbound' / 'outbound'
    PARTY_FIELD = ''       # 對象欄位：'supplier' / 'customer'
    DONE_QTY_FIELD = ''    # 完成數量欄位：'received_qty' / 'shipped_qty'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def _gen_order_no(cls) -> str:
        today = datetime.utcnow().strftime('%Y%m%d')
        db = get_db()
        counter = db['counters'].find_one_and_update(
            {'_id': f'{cls.COUNTER_PREFIX}_{today}'},
            {'$inc': {'seq': 1}},
            upsert=True,
            return_document=True,
        )
        return f'{cls.ORDER_NO_PREFIX}{today}{counter["seq"]:04d}'

    @classmethod
    def find_all(cls, status: str = None, warehouse_id: str = None,
                 limit: int = 100, offset: int = 0) -> list:
        q = {}
        if status:
            q['status'] = status
        if warehouse_id:
            q['warehouse_id'] = ObjectId(warehouse_id)
        docs = cls._col().find(q).sort('created_at', -1).skip(offset).limit(limit)
        return [_fmt_order(d) for d in docs]

    @classmethod
    def find_by_id(cls, oid: str) -> dict:
        try:
            obj_id = ObjectId(oid)
        except (InvalidId, Exception):
            return None
        return _fmt_order(cls._col().find_one({'_id': obj_id}))

    @classmethod
    def find_by_order_no(cls, order_no: str) -> dict:
        return _fmt_order(cls._col().find_one({'order_no': order_no}))

    @classmethod
    def create(cls, data: dict, created_by: str = '') -> str:
        now = datetime.utcnow()
        doc = {
            'order_no': cls._gen_order_no(),
            cls.PARTY_FIELD: data.get(cls.PARTY_FIELD, ''),
            'warehouse_id': ObjectId(data['warehouse_id']),
            'warehouse_name': data.get('warehouse_name', ''),
            'status': OrderStatus.PENDING,
            'items': [],
            'total_amount': 0.0,
            'remark': data.get('remark', ''),
            'created_by': created_by,
            'confirmed_by': None,
            'confirmed_at': None,
            'completed_by': None,
            'completed_at': None,
            'created_at': now,
            'updated_at': now,
        }
        return str(cls._col().insert_one(doc).inserted_id)

    @classmethod
    def update_basic(cls, oid: str, data: dict) -> bool:
        """更新基本資料 (只能在 pending 狀態)"""
        fields = {'updated_at': datetime.utcnow()}
        for key in (cls.PARTY_FIELD, 'remark'):
            if key in data:
                fields[key] = data[key]
        if 'warehouse_id' in data:
            fields['warehouse_id'] = ObjectId(data['warehouse_id'])
            fields['warehouse_name'] = data.get('warehouse_name', '')
        r = cls._col().update_one(
            {'_id': ObjectId(oid), 'status': OrderStatus.PENDING},
            {'$set': fields}
        )
        return r.matched_count > 0

    @classmethod
    def add_item(cls, oid: str, item_data: dict) -> bool:
        item = {
            '_id': ObjectId(),
            'product_id': ObjectId(item_data['product_id']),
            'product_name': item_data.get('product_name', ''),
            'product_sku': item_data.get('product_sku', ''),
            'unit': item_data.get('unit', '個'),
            'expected_qty': int(item_data.get('expected_qty', 0)),
            cls.DONE_QTY_FIELD: 0,
            'unit_price': float(item_data.get('unit_price', 0)),
        }
        r = cls._col().update_one(
            {'_id': ObjectId(oid), 'status': OrderStatus.PENDING},
            {
                '$push': {'items': item},
                '$set': {'updated_at': datetime.utcnow()},
            }
        )
        cls._recalc_total(oid)
        return r.matched_count > 0

    @classmethod
    def remove_item(cls, oid: str, item_id: str) -> bool:
        r = cls._col().update_one(
            {'_id': ObjectId(oid), 'status': OrderStatus.PENDING},
            {
                '$pull': {'items': {'_id': ObjectId(item_id)}},
                '$set': {'updated_at': datetime.utcnow()},
            }
        )
        cls._recalc_total(oid)
        return r.matched_count > 0

    @classmethod
    def update_item(cls, oid: str, item_id: str, data: dict) -> bool:
        fields = {}
        if 'expected_qty' in data:
            fields['items.$.expected_qty'] = int(data['expected_qty'])
        if 'unit_price' in data:
            fields['items.$.unit_price'] = float(data['unit_price'])
        if not fields:
            return False
        fields['updated_at'] = datetime.utcnow()
        r = cls._col().update_one(
            {'_id': ObjectId(oid), 'status': OrderStatus.PENDING, 'items._id': ObjectId(item_id)},
            {'$set': fields}
        )
        cls._recalc_total(oid)
        return r.matched_count > 0

    @classmethod
    def _recalc_total(cls, oid: str):
        # Use find_one_and_update with $set so the read that drives the total
        # happens on the document state *after* the preceding push/pull/set has
        # been committed.  A plain find_one → update_one pair is vulnerable to a
        # concurrent add_item landing between the two round-trips and producing a
        # stale total_amount.
        doc = cls._col().find_one({'_id': ObjectId(oid)})
        if not doc:
            return
        total = sum(
            item.get('expected_qty', 0) * item.get('unit_price', 0)
            for item in doc.get('items', [])
        )
        # Write back and immediately confirm what MongoDB stored.
        cls._col().find_one_and_update(
            {'_id': ObjectId(oid)},
            {'$set': {'total_amount': round(total, 2)}},
        )

    @classmethod
    def confirm(cls, oid: str, confirmed_by: str) -> bool:
        """Atomically transition status pending → confirmed.

        The filter {status: 'pending'} and the write happen in a single
        server-side operation, so a concurrent request that races past the
        caller's checks (e.g. the outbound stock check) will find the document
        already flipped to 'confirmed' and fail here, preventing oversell.
        """
        now = datetime.utcnow()
        r = cls._col().update_one(
            {'_id': ObjectId(oid), 'status': OrderStatus.PENDING},
            {'$set': {'status': OrderStatus.CONFIRMED, 'confirmed_by': confirmed_by,
                      'confirmed_at': now, 'updated_at': now}}
        )
        return r.matched_count > 0

    @classmethod
    def complete(cls, oid: str, completed_by: str, done_qtys: dict = None,
                session=None) -> dict:
        """
        完成單據：更新各明細的完成數量欄位（DONE_QTY_FIELD），
        回傳最新單據 dict 供呼叫者更新庫存。
        done_qtys: {item_id: qty} 若為 None 則使用 expected_qty
        session: [OPT-N1] 可選 pymongo ClientSession，供 order_service 在交易內
                 呼叫時保持同一交易上下文（standalone/mongomock 環境傳 None 即可）
        """
        col = cls._col()
        now = datetime.utcnow()
        # Atomically transition status confirmed → completed so that two
        # concurrent requests cannot both pass the guard and double-adjust inventory.
        result = col.find_one_and_update(
            {'_id': ObjectId(oid), 'status': OrderStatus.CONFIRMED},
            {'$set': {'status': OrderStatus.COMPLETED, 'completed_by': completed_by,
                      'completed_at': now, 'updated_at': now}},
            return_document=False,
            session=session,
        )
        if result is None:
            return None  # already completed or not in confirmed state
        doc = result
        # 更新各明細的完成數量
        for item in doc.get('items', []):
            item_id_str = str(item['_id'])
            qty = int(done_qtys.get(item_id_str, item['expected_qty'])) if done_qtys else item['expected_qty']
            col.update_one(
                {'_id': ObjectId(oid), 'items._id': item['_id']},
                {'$set': {f'items.$.{cls.DONE_QTY_FIELD}': qty}},
                session=session,
            )
        # 重新讀取最新 doc（同一 session，確保交易內讀到自己剛寫入的值）
        return _fmt_order(col.find_one({'_id': ObjectId(oid)}, session=session))

    @classmethod
    def cancel(cls, oid: str, operator: str) -> bool:
        now = datetime.utcnow()
        r = cls._col().update_one(
            {'_id': ObjectId(oid), 'status': {'$in': list(OrderStatus.CANCELLABLE)}},
            {'$set': {'status': OrderStatus.CANCELLED, 'updated_at': now}}
        )
        return r.matched_count > 0
