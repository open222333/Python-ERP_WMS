from datetime import datetime, timedelta
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
    def find_all(cls, warehouse_id: str = None, product_id: str = None,
                 limit: int = 2000) -> list:
        q = {}
        if warehouse_id:
            q['warehouse_id'] = ObjectId(warehouse_id)
        if product_id:
            q['product_id'] = ObjectId(product_id)
        docs = cls._col().find(q).limit(limit)
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
        使用 find_one_and_update + $inc 確保原子性，避免並發覆寫。
        """
        q = {
            'product_id': ObjectId(product_id),
            'warehouse_id': ObjectId(warehouse_id),
            'location_id': ObjectId(location_id) if location_id else None,
        }
        now = datetime.utcnow()
        before_doc = cls._col().find_one_and_update(
            q,
            {'$inc': {'quantity': delta}, '$set': {'updated_at': now},
             '$setOnInsert': {'created_at': now}},
            upsert=True,
            return_document=False,  # 回傳更新前的文件
        )
        # before_doc is None when the document did not previously exist (upsert
        # created a new record).  In that case before_qty is 0 and after_qty
        # equals delta.  A negative delta on a brand-new document would leave
        # the inventory at a negative quantity, which is invalid; raise early so
        # the caller can roll back any associated StockMovement record.
        before_qty = before_doc.get('quantity', 0) if before_doc else 0
        after_qty  = before_qty + delta
        if after_qty < 0:
            # Undo the $inc to leave the collection in a consistent state.
            cls._col().update_one(q, {'$inc': {'quantity': -delta}})
            raise ValueError(
                f"Inventory adjustment would result in negative quantity "
                f"(before={before_qty}, delta={delta})."
            )
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
        before_doc = cls._col().find_one_and_update(
            q,
            {'$set': {'quantity': quantity, 'updated_at': now},
             '$setOnInsert': {'created_at': now}},
            upsert=True,
            return_document=False,
        )
        before_qty = before_doc.get('quantity', 0) if before_doc else 0
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

    # reference_type 屬於菜單品項觸發（POS 銷售 / 退款 / 外送）的類型
    _MENU_REF_TYPES = {'pos_order', 'pos_refund', 'delivery_order'}

    @classmethod
    def find_all(cls, warehouse_id: str = None, product_id: str = None,
                 movement_type: str = None, limit: int = 200,
                 product_only: bool = False) -> list:
        q = {}
        if warehouse_id:
            q['warehouse_id'] = ObjectId(warehouse_id)
        if product_id:
            q['product_id'] = ObjectId(product_id)
        if movement_type:
            q['movement_type'] = movement_type
        if product_only:
            # 排除菜單品項觸發的移動（只紀錄，不在後台顯示）
            q['reference_type'] = {'$nin': list(cls._MENU_REF_TYPES)}
        # No field projection is applied so callers receive every stored field,
        # including _id (stringified below).  All fields in stock_movements are
        # intentionally returned: there are no internal-only or oversized
        # embedded fields in this collection.
        docs = cls._col().find(q).sort('created_at', -1).limit(limit)
        result = []
        for d in docs:
            d['_id'] = str(d['_id'])
            d['product_id'] = str(d['product_id'])
            d['warehouse_id'] = str(d['warehouse_id'])
            result.append(d)
        return result

    @classmethod
    def cleanup_old(cls, days: int) -> int:
        """刪除超過 days 天的移動紀錄，傳回刪除筆數。"""
        if days <= 0:
            return 0
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = cls._col().delete_many({'created_at': {'$lt': cutoff}})
        return result.deleted_count
