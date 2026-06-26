from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from src.mongo import get_db


def _fmt(doc) -> dict:
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['_id'] = str(doc['_id'])
    if 'warehouse_id' in d and d['warehouse_id']:
        d['warehouse_id'] = str(d['warehouse_id'])
    if 'store_id' in d and d['store_id']:
        d['store_id'] = str(d['store_id'])
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
    def find_all(cls, store_filter: dict = None) -> list:
        docs = cls._col().find(dict(store_filter or {})).sort('code', 1)
        return [_fmt(d) for d in docs]

    @classmethod
    def find_by_id(cls, wid: str, store_filter: dict = None) -> dict:
        try:
            oid = ObjectId(wid)
        except InvalidId:
            raise ValueError(f'無效的倉庫 ID：{wid}')
        q = {'_id': oid}
        if store_filter:
            q.update(store_filter)
        return _fmt(cls._col().find_one(q))

    @classmethod
    def find_by_code(cls, code: str, store_filter: dict = None) -> dict:
        q = {'code': code}
        if store_filter:
            q.update(store_filter)
        return _fmt(cls._col().find_one(q))

    @classmethod
    def create(cls, data: dict, store_id: str = None) -> str:
        doc = {
            'code':        data['code'],
            'name':        data['name'],
            'address':     data.get('address', ''),
            'manager':     data.get('manager', ''),
            'phone':       data.get('phone', ''),
            'description': data.get('description', ''),
            'status':      1,
            'created_at':  datetime.utcnow(),
        }
        if store_id:
            try:
                doc['store_id'] = ObjectId(store_id)
            except InvalidId:
                raise ValueError(f'無效的 store_id：{store_id}')
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
        try:
            oid = ObjectId(wid)
        except InvalidId:
            raise ValueError(f'無效的倉庫 ID：{wid}')
        r = cls._col().update_one({'_id': oid}, {'$set': fields})
        return r.matched_count > 0

    @classmethod
    def delete(cls, wid: str) -> bool:
        try:
            oid = ObjectId(wid)
        except InvalidId:
            raise ValueError(f'無效的倉庫 ID：{wid}')
        r = cls._col().delete_one({'_id': oid})
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
        try:
            oid = ObjectId(warehouse_id)
        except InvalidId:
            raise ValueError(f'無效的倉庫 ID：{warehouse_id}')
        docs = cls._col().find({'warehouse_id': oid}).sort('code', 1)
        return [_fmt(d) for d in docs]

    @classmethod
    def find_by_id(cls, lid: str) -> dict:
        try:
            oid = ObjectId(lid)
        except InvalidId:
            raise ValueError(f'無效的位置 ID：{lid}')
        return _fmt(cls._col().find_one({'_id': oid}))

    @classmethod
    def create(cls, warehouse_id: str, data: dict) -> str:
        try:
            wid_oid = ObjectId(warehouse_id)
        except InvalidId:
            raise ValueError(f'無效的倉庫 ID：{warehouse_id}')
        doc = {
            'warehouse_id': wid_oid,
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
        try:
            oid = ObjectId(lid)
        except InvalidId:
            raise ValueError(f'無效的位置 ID：{lid}')
        r = cls._col().update_one({'_id': oid}, {'$set': fields})
        return r.matched_count > 0

    @classmethod
    def delete(cls, lid: str) -> bool:
        try:
            oid = ObjectId(lid)
        except InvalidId:
            raise ValueError(f'無效的位置 ID：{lid}')
        r = cls._col().delete_one({'_id': oid})
        return r.deleted_count > 0
