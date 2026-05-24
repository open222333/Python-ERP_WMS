from datetime import datetime
from bson import ObjectId
from src.mongo import get_db


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


def _gen_order_no() -> str:
    from datetime import datetime
    from src.mongo import get_db
    today = datetime.utcnow().strftime('%Y%m%d')
    db = get_db()
    count = db['inbound_orders'].count_documents({
        'order_no': {'$regex': f'^IN{today}'}
    })
    return f'IN{today}{count + 1:04d}'


class InboundOrder:
    COLLECTION = 'inbound_orders'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_all(cls, status: str = None, warehouse_id: str = None,
                 limit: int = 100) -> list:
        q = {}
        if status:
            q['status'] = status
        if warehouse_id:
            q['warehouse_id'] = ObjectId(warehouse_id)
        docs = cls._col().find(q).sort('created_at', -1).limit(limit)
        return [_fmt_order(d) for d in docs]

    @classmethod
    def find_by_id(cls, oid: str) -> dict:
        return _fmt_order(cls._col().find_one({'_id': ObjectId(oid)}))

    @classmethod
    def find_by_order_no(cls, order_no: str) -> dict:
        return _fmt_order(cls._col().find_one({'order_no': order_no}))

    @classmethod
    def create(cls, data: dict, created_by: str = '') -> str:
        now = datetime.utcnow()
        doc = {
            'order_no': _gen_order_no(),
            'supplier': data.get('supplier', ''),
            'warehouse_id': ObjectId(data['warehouse_id']),
            'warehouse_name': data.get('warehouse_name', ''),
            'status': 'pending',
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
        for key in ('supplier', 'remark'):
            if key in data:
                fields[key] = data[key]
        if 'warehouse_id' in data:
            fields['warehouse_id'] = ObjectId(data['warehouse_id'])
            fields['warehouse_name'] = data.get('warehouse_name', '')
        r = cls._col().update_one(
            {'_id': ObjectId(oid), 'status': 'pending'},
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
            'received_qty': 0,
            'unit_price': float(item_data.get('unit_price', 0)),
        }
        r = cls._col().update_one(
            {'_id': ObjectId(oid), 'status': 'pending'},
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
            {'_id': ObjectId(oid), 'status': 'pending'},
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
            {'_id': ObjectId(oid), 'status': 'pending', 'items._id': ObjectId(item_id)},
            {'$set': fields}
        )
        cls._recalc_total(oid)
        return r.matched_count > 0

    @classmethod
    def _recalc_total(cls, oid: str):
        doc = cls._col().find_one({'_id': ObjectId(oid)})
        if not doc:
            return
        total = sum(
            item.get('expected_qty', 0) * item.get('unit_price', 0)
            for item in doc.get('items', [])
        )
        cls._col().update_one({'_id': ObjectId(oid)}, {'$set': {'total_amount': round(total, 2)}})

    @classmethod
    def confirm(cls, oid: str, confirmed_by: str) -> bool:
        now = datetime.utcnow()
        r = cls._col().update_one(
            {'_id': ObjectId(oid), 'status': 'pending'},
            {'$set': {'status': 'confirmed', 'confirmed_by': confirmed_by,
                      'confirmed_at': now, 'updated_at': now}}
        )
        return r.matched_count > 0

    @classmethod
    def complete(cls, oid: str, completed_by: str, received_qtys: dict = None) -> dict:
        """
        完成入庫：更新 received_qty，回傳 items 清單供呼叫者更新庫存
        received_qtys: {item_id: qty} 若為 None 則使用 expected_qty
        """
        doc = cls._col().find_one({'_id': ObjectId(oid), 'status': 'confirmed'})
        if not doc:
            return None
        now = datetime.utcnow()
        # 更新各明細的 received_qty
        for item in doc.get('items', []):
            item_id_str = str(item['_id'])
            qty = int(received_qtys.get(item_id_str, item['expected_qty'])) if received_qtys else item['expected_qty']
            cls._col().update_one(
                {'_id': ObjectId(oid), 'items._id': item['_id']},
                {'$set': {'items.$.received_qty': qty}}
            )
        cls._col().update_one(
            {'_id': ObjectId(oid)},
            {'$set': {'status': 'completed', 'completed_by': completed_by,
                      'completed_at': now, 'updated_at': now}}
        )
        # 重新讀取最新 doc
        return _fmt_order(cls._col().find_one({'_id': ObjectId(oid)}))

    @classmethod
    def cancel(cls, oid: str, operator: str) -> bool:
        now = datetime.utcnow()
        r = cls._col().update_one(
            {'_id': ObjectId(oid), 'status': {'$in': ['pending', 'confirmed']}},
            {'$set': {'status': 'cancelled', 'updated_at': now}}
        )
        return r.matched_count > 0
