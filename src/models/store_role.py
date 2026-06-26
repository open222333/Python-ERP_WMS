from datetime import datetime
from bson import ObjectId
from src.mongo import get_db


class StoreRole:
    COLLECTION = 'store_roles'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_all(cls) -> list:
        return [cls._serialize(d) for d in cls._col().find({}).sort('created_at', 1)]

    @classmethod
    def find_by_id(cls, rid: str) -> dict | None:
        try:
            doc = cls._col().find_one({'_id': ObjectId(rid)})
        except Exception:
            return None
        return cls._serialize(doc) if doc else None

    @classmethod
    def create(cls, name: str, description: str = '', is_system: bool = False) -> str:
        doc = {
            'name':        name.strip(),
            'description': description.strip(),
            'is_system':   is_system,
            'created_at':  datetime.utcnow(),
        }
        return str(cls._col().insert_one(doc).inserted_id)

    @classmethod
    def update(cls, rid: str, name: str = None, description: str = None) -> bool:
        fields = {}
        if name        is not None: fields['name']        = name.strip()
        if description is not None: fields['description'] = description.strip()
        if not fields:
            return False
        r = cls._col().update_one({'_id': ObjectId(rid)}, {'$set': fields})
        return r.matched_count > 0

    @classmethod
    def delete(cls, rid: str) -> bool:
        doc = cls.find_by_id(rid)
        if not doc or doc.get('is_system'):
            return False
        return cls._col().delete_one({'_id': ObjectId(rid)}).deleted_count > 0

    @classmethod
    def ensure_defaults(cls) -> dict:
        """建立預設角色模板（總代理、店家），回傳 name→id 的映射。"""
        result = {}
        for name in ('總代理', '店家'):
            existing = cls._col().find_one({'name': name})
            if existing:
                result[name] = str(existing['_id'])
            else:
                rid = cls.create(name=name, is_system=True)
                result[name] = rid
        return result

    @staticmethod
    def _serialize(doc: dict) -> dict | None:
        if not doc:
            return None
        out = {'_id': str(doc['_id'])}
        for k, v in doc.items():
            if k == '_id':
                continue
            if isinstance(v, datetime):
                out[k] = v.isoformat()
            else:
                out[k] = v
        return out
