from datetime import datetime
from bson import ObjectId
from src.mongo import get_db


def _fmt(doc) -> dict:
    """將 MongoDB document 轉為可序列化 dict"""
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['_id'] = str(doc['_id'])
    if 'category_id' in d and d['category_id']:
        d['category_id'] = str(d['category_id'])
    return d


# ─────────────────────────────────────────────────────────────
#  產品分類
# ─────────────────────────────────────────────────────────────
class ProductCategory:
    COLLECTION = 'product_categories'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_all(cls) -> list:
        docs = cls._col().find({}).sort('name', 1)
        return [_fmt(d) for d in docs]

    @classmethod
    def find_by_id(cls, cid: str) -> dict:
        return _fmt(cls._col().find_one({'_id': ObjectId(cid)}))

    @classmethod
    def create(cls, name: str, parent_id: str = None, description: str = '') -> str:
        doc = {
            'name': name,
            'parent_id': ObjectId(parent_id) if parent_id else None,
            'description': description,
            'status': 1,
            'created_at': datetime.utcnow(),
        }
        return str(cls._col().insert_one(doc).inserted_id)

    @classmethod
    def update(cls, cid: str, **kwargs) -> bool:
        fields = {}
        if 'name' in kwargs:
            fields['name'] = kwargs['name']
        if 'description' in kwargs:
            fields['description'] = kwargs['description']
        if 'parent_id' in kwargs:
            fields['parent_id'] = ObjectId(kwargs['parent_id']) if kwargs['parent_id'] else None
        if 'status' in kwargs:
            fields['status'] = int(kwargs['status'])
        if not fields:
            return False
        r = cls._col().update_one({'_id': ObjectId(cid)}, {'$set': fields})
        return r.matched_count > 0

    @classmethod
    def delete(cls, cid: str) -> bool:
        r = cls._col().delete_one({'_id': ObjectId(cid)})
        return r.deleted_count > 0


# ─────────────────────────────────────────────────────────────
#  產品
# ─────────────────────────────────────────────────────────────
class Product:
    COLLECTION = 'products'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def _fmt(cls, doc) -> dict:
        if doc is None:
            return None
        d = {k: v for k, v in doc.items() if k != '_id'}
        d['_id'] = str(doc['_id'])
        if d.get('category_id'):
            d['category_id'] = str(d['category_id'])
        return d

    @classmethod
    def find_all(cls, keyword: str = '', category_id: str = '', status: int = None) -> list:
        q = {}
        if keyword:
            q['$or'] = [
                {'name': {'$regex': keyword, '$options': 'i'}},
                {'sku': {'$regex': keyword, '$options': 'i'}},
                {'barcode': {'$regex': keyword, '$options': 'i'}},
            ]
        if category_id:
            q['category_id'] = ObjectId(category_id)
        if status is not None:
            q['status'] = status
        docs = cls._col().find(q).sort('created_at', -1)
        return [cls._fmt(d) for d in docs]

    @classmethod
    def find_by_id(cls, pid: str) -> dict:
        return cls._fmt(cls._col().find_one({'_id': ObjectId(pid)}))

    @classmethod
    def find_by_sku(cls, sku: str) -> dict:
        return cls._fmt(cls._col().find_one({'sku': sku}))

    @classmethod
    def find_by_barcode(cls, barcode: str) -> dict:
        """以條碼精確查詢產品（空字串直接回 None）"""
        if not barcode:
            return None
        return cls._fmt(cls._col().find_one({'barcode': barcode}))

    @classmethod
    def create(cls, data: dict, created_by: str = '') -> str:
        now = datetime.utcnow()
        doc = {
            'sku': data['sku'],
            'barcode': data.get('barcode', ''),
            'name': data['name'],
            'category_id': ObjectId(data['category_id']) if data.get('category_id') else None,
            'unit': data.get('unit', '個'),
            'description': data.get('description', ''),
            'cost_price': float(data.get('cost_price', 0)),
            'sell_price': float(data.get('sell_price', 0)),
            'min_stock': int(data.get('min_stock', 0)),
            'max_stock': int(data.get('max_stock', 0)),
            'status': 1,
            'created_by': created_by,
            'created_at': now,
            'updated_at': now,
        }
        return str(cls._col().insert_one(doc).inserted_id)

    @classmethod
    def update(cls, pid: str, data: dict) -> bool:
        fields = {'updated_at': datetime.utcnow()}
        for key in ('sku', 'barcode', 'name', 'unit', 'description'):
            if key in data:
                fields[key] = data[key]
        for key in ('cost_price', 'sell_price'):
            if key in data:
                fields[key] = float(data[key])
        for key in ('min_stock', 'max_stock', 'status'):
            if key in data:
                fields[key] = int(data[key])
        if 'category_id' in data:
            fields['category_id'] = ObjectId(data['category_id']) if data['category_id'] else None
        r = cls._col().update_one({'_id': ObjectId(pid)}, {'$set': fields})
        return r.matched_count > 0

    @classmethod
    def delete(cls, pid: str) -> bool:
        r = cls._col().delete_one({'_id': ObjectId(pid)})
        return r.deleted_count > 0
