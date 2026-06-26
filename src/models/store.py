from datetime import datetime
from bson import ObjectId
from src.mongo import get_db


class Store:
    COLLECTION = 'stores'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_all(cls) -> list:
        return [cls._serialize(s) for s in cls._col().find({})]

    @classmethod
    def find_by_code(cls, code: str) -> dict | None:
        doc = cls._col().find_one({'code': code})
        return cls._serialize(doc) if doc else None

    @classmethod
    def find_by_id(cls, store_id: str) -> dict | None:
        doc = cls._col().find_one({'_id': ObjectId(store_id)})
        return cls._serialize(doc) if doc else None

    @classmethod
    def _next_code(cls) -> str:
        n = cls._col().count_documents({})
        for i in range(n + 1, n + 999):
            code = f'S{i:03d}'
            if not cls._col().find_one({'code': code}):
                return code
        return f'S{n + 1:03d}'

    @classmethod
    def create(cls, name: str, code: str = '', store_role_id: str = None) -> str:
        doc = {
            'name':       name,
            'code':       code.strip() or cls._next_code(),
            'status':     'active',
            'created_at': datetime.utcnow(),
        }
        if store_role_id:
            doc['store_role_id'] = ObjectId(store_role_id)
        return str(cls._col().insert_one(doc).inserted_id)

    @classmethod
    def update(cls, store_id: str, name: str = None, code: str = None,
               status: str = None, store_role_id: str = None) -> bool:
        fields = {}
        if name          is not None: fields['name']   = name
        if code          is not None: fields['code']   = code
        if status        is not None: fields['status'] = status
        if store_role_id is not None:
            fields['store_role_id'] = ObjectId(store_role_id) if store_role_id else None
        if not fields:
            return False
        result = cls._col().update_one({'_id': ObjectId(store_id)}, {'$set': fields})
        return result.matched_count > 0

    @classmethod
    def delete(cls, store_id: str) -> bool:
        return cls._col().delete_one({'_id': ObjectId(store_id)}).deleted_count > 0

    @staticmethod
    def _serialize(doc: dict) -> dict | None:
        if not doc:
            return None
        out = {'_id': str(doc['_id'])}
        for k, v in doc.items():
            if k == '_id':
                continue
            if k == 'store_role_id' and isinstance(v, ObjectId):
                out[k] = str(v)
            elif isinstance(v, datetime):
                out[k] = v.isoformat()
            else:
                out[k] = v
        if 'store_role_id' not in out:
            out['store_role_id'] = None
        return out
