from datetime import datetime
from bson import ObjectId
from src.mongo import get_db


def _fmt(doc) -> dict:
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['_id'] = str(doc['_id'])
    for key in ('product_id', 'warehouse_id', 'location_id'):
        if key in d and d[key]:
            d[key] = str(d[key])
    return d


# ─────────────────────────────────────────────────────────────
#  庫存
# ─────────────────────────────────────────────────────────────
class Inventory:
    COLLECTION = 'inventory'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_all(cls, warehouse_id: str = None, product_id: str = None) -> list:
        q = {}
        if warehouse_id:
            q['warehouse_id'] = ObjectId(warehouse_id)
        if product_id:
            q['product_id'] = ObjectId(product_id)
        docs = cls._col().find(q)
        return [_fmt(d) for d in docs]

    @classmethod
    def find_one(cls, product_id: str, warehouse_id: str, location_id: str = None) -> dict:
        q = {
            'product_id': ObjectId(product_id),
            'warehouse_id': ObjectId(warehouse_id),
            'location_id': ObjectId(location_id) if location_id else None,
        }
        return _fmt(cls._col().find_one(q))

    @classmethod
    def get_quantity(cls, product_id: str, warehouse_id: str, location_id: str = None) -> int:
        doc = cls.find_one(product_id, warehouse_id, location_id)
        return doc['quantity'] if doc else 0

    @classmethod
    def adjust(cls, product_id: str, warehouse_id: str, delta: int,
               location_id: str = None) -> tuple[int, int]:
        """
        調整庫存，回傳 (before_qty, after_qty)
        delta 正數=增加，負數=減少
        """
        q = {
            'product_id': ObjectId(product_id),
            'warehouse_id': ObjectId(warehouse_id),
            'location_id': ObjectId(location_id) if location_id else None,
        }
        now = datetime.utcnow()
        existing = cls._col().find_one(q)
        before_qty = existing['quantity'] if existing else 0
        after_qty = before_qty + delta

        if existing:
            cls._col().update_one(q, {'$set': {'quantity': after_qty, 'updated_at': now}})
        else:
            cls._col().insert_one({**q, 'quantity': after_qty,
                                   'created_at': now, 'updated_at': now})
        return before_qty, after_qty

    @classmethod
    def set_quantity(cls, product_id: str, warehouse_id: str, quantity: int,
                     location_id: str = None) -> tuple[int, int]:
        """直接設定庫存數量，回傳 (before_qty, after_qty)"""
        q = {
            'product_id': ObjectId(product_id),
            'warehouse_id': ObjectId(warehouse_id),
            'location_id': ObjectId(location_id) if location_id else None,
        }
        now = datetime.utcnow()
        existing = cls._col().find_one(q)
        before_qty = existing['quantity'] if existing else 0
        if existing:
            cls._col().update_one(q, {'$set': {'quantity': quantity, 'updated_at': now}})
        else:
            cls._col().insert_one({**q, 'quantity': quantity,
                                   'created_at': now, 'updated_at': now})
        return before_qty, quantity


# ─────────────────────────────────────────────────────────────
#  庫存移動紀錄
# ─────────────────────────────────────────────────────────────
MOVEMENT_TYPES = ('inbound', 'outbound', 'transfer_in', 'transfer_out', 'adjust', 'consume')
MOVEMENT_LABEL = {
    'inbound': '入庫',
    'outbound': '出庫',
    'transfer_in': '調撥入',
    'transfer_out': '調撥出',
    'adjust': '盤點調整',
    'consume': '消耗',
}


class StockMovement:
    COLLECTION = 'stock_movements'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def create(cls, product_id: str, warehouse_id: str,
               movement_type: str, quantity: int,
               before_qty: int, after_qty: int,
               product_name: str = '', product_sku: str = '',
               warehouse_name: str = '',
               reference_type: str = '', reference_id: str = '',
               remark: str = '', operator: str = '') -> str:
        doc = {
            'product_id': ObjectId(product_id),
            'product_name': product_name,
            'product_sku': product_sku,
            'warehouse_id': ObjectId(warehouse_id),
            'warehouse_name': warehouse_name,
            'movement_type': movement_type,
            'movement_label': MOVEMENT_LABEL.get(movement_type, movement_type),
            'quantity': quantity,
            'before_qty': before_qty,
            'after_qty': after_qty,
            'reference_type': reference_type,
            'reference_id': reference_id,
            'remark': remark,
            'operator': operator,
            'created_at': datetime.utcnow(),
        }
        return str(cls._col().insert_one(doc).inserted_id)

    @classmethod
    def find_all(cls, warehouse_id: str = None, product_id: str = None,
                 movement_type: str = None, limit: int = 200) -> list:
        q = {}
        if warehouse_id:
            q['warehouse_id'] = ObjectId(warehouse_id)
        if product_id:
            q['product_id'] = ObjectId(product_id)
        if movement_type:
            q['movement_type'] = movement_type
        docs = cls._col().find(q, {'_id': 0}).sort('created_at', -1).limit(limit)
        result = []
        for d in docs:
            d['product_id'] = str(d['product_id'])
            d['warehouse_id'] = str(d['warehouse_id'])
            result.append(d)
        return result
