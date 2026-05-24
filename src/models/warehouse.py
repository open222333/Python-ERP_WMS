from datetime import datetime
from bson import ObjectId
from src.mongo import get_db


def _fmt(doc) -> dict:
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['_id'] = str(doc['_id'])
    if 'warehouse_id' in d and d['warehouse_id']:
        d['warehouse_id'] = str(d['warehouse_id'])
    return d


# ─────────────────────────────────────────────────────────────
#  倉庫
# ─────────────────────────────────────────────────────────────
class Warehouse:
    COLLECTION = 'warehouses'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_all(cls) -> list:
        docs = cls._col().find({}).sort('code', 1)
        return [_fmt(d) for d in docs]

    @classmethod
    def find_by_id(cls, wid: str) -> dict:
        return _fmt(cls._col().find_one({'_id': ObjectId(wid)}))

    @classmethod
    def find_by_code(cls, code: str) -> dict:
        return _fmt(cls._col().find_one({'code': code}))

    @classmethod
    def create(cls, data: dict) -> str:
        doc = {
            'code': data['code'],
            'name': data['name'],
            'address': data.get('address', ''),
            'manager': data.get('manager', ''),
            'phone': data.get('phone', ''),
            'description': data.get('description', ''),
            'status': 1,
            'created_at': datetime.utcnow(),
        }
        return str(cls._col().insert_one(doc).inserted_id)

    @classmethod
    def update(cls, wid: str, data: dict) -> bool:
        fields = {}
        for key in ('code', 'name', 'address', 'manager', 'phone', 'description'):
            if key in data:
                fields[key] = data[key]
        if 'status' in data:
            fields['status'] = int(data['status'])
        if not fields:
            return False
        r = cls._col().update_one({'_id': ObjectId(wid)}, {'$set': fields})
        return r.matched_count > 0

    @classmethod
    def delete(cls, wid: str) -> bool:
        r = cls._col().delete_one({'_id': ObjectId(wid)})
        return r.deleted_count > 0


# ─────────────────────────────────────────────────────────────
#  倉庫位置
# ─────────────────────────────────────────────────────────────
class WarehouseLocation:
    COLLECTION = 'warehouse_locations'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_by_warehouse(cls, warehouse_id: str) -> list:
        docs = cls._col().find({'warehouse_id': ObjectId(warehouse_id)}).sort('code', 1)
        return [_fmt(d) for d in docs]

    @classmethod
    def find_by_id(cls, lid: str) -> dict:
        return _fmt(cls._col().find_one({'_id': ObjectId(lid)}))

    @classmethod
    def create(cls, warehouse_id: str, data: dict) -> str:
        doc = {
            'warehouse_id': ObjectId(warehouse_id),
            'code': data['code'],
            'name': data['name'],
            'description': data.get('description', ''),
            'status': 1,
            'created_at': datetime.utcnow(),
        }
        return str(cls._col().insert_one(doc).inserted_id)

    @classmethod
    def update(cls, lid: str, data: dict) -> bool:
        fields = {}
        for key in ('code', 'name', 'description'):
            if key in data:
                fields[key] = data[key]
        if 'status' in data:
            fields['status'] = int(data['status'])
        if not fields:
            return False
        r = cls._col().update_one({'_id': ObjectId(lid)}, {'$set': fields})
        return r.matched_count > 0

    @classmethod
    def delete(cls, lid: str) -> bool:
        r = cls._col().delete_one({'_id': ObjectId(lid)})
        return r.deleted_count > 0
