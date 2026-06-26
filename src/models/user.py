from datetime import datetime
from bson import ObjectId
import bcrypt
from src.mongo import get_db

# super_admin: 主帳號，無 store_ids，可見所有店家資料
# admin/operator/cashier/viewer: 店家帳號，帶 store_ids，僅見指定店家
ROLES = ['super_admin', 'admin', 'operator', 'cashier', 'viewer']

_UNSET = object()   # sentinel — 區分「未傳入」與「傳入 None / ''」


class User:
    COLLECTION = 'users'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def _serialize(cls, u: dict) -> dict:
        doc = {'_id': str(u['_id'])}
        for k, v in u.items():
            if k == '_id':
                continue
            if k == 'template_id' and v:
                doc[k] = str(v)
            elif k == 'store_ids' and v:
                doc[k] = [str(oid) for oid in v]
            else:
                doc[k] = v
        if 'store_ids' not in doc:
            doc['store_ids'] = []
        return doc

    @classmethod
    def find_all(cls) -> list:
        return [cls._serialize(u)
                for u in cls._col().find({}, {'password': 0})]

    @classmethod
    def find_by_store(cls, store_id: str) -> list:
        return [cls._serialize(u)
                for u in cls._col().find(
                    {'store_ids': ObjectId(store_id)}, {'password': 0})]

    @classmethod
    def find_by_username(cls, username: str) -> dict:
        return cls._col().find_one({'username': username})

    @classmethod
    def create(cls, username: str, password: str, role: str = 'viewer',
               template_id: str = None, store_ids: list = None) -> str:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        doc = {
            'username':   username,
            'password':   hashed.decode(),
            'role':       role,
            'store_ids':  [ObjectId(sid) for sid in store_ids if sid] if store_ids else [],
            'created_at': datetime.utcnow(),
        }
        if template_id:
            doc['template_id'] = template_id
        result = cls._col().insert_one(doc)
        return str(result.inserted_id)

    @classmethod
    def update(cls, user_id: str, password: str = None, role: str = None,
               template_id=_UNSET, store_ids=_UNSET) -> bool:
        set_fields   = {}
        unset_fields = {}

        if password:
            set_fields['password'] = bcrypt.hashpw(
                password.encode(), bcrypt.gensalt()).decode()
        if role:
            set_fields['role'] = role

        if template_id is not _UNSET:
            if template_id:
                set_fields['template_id'] = template_id
            else:
                unset_fields['template_id'] = ''

        if store_ids is not _UNSET:
            set_fields['store_ids'] = [ObjectId(sid) for sid in store_ids if sid] if store_ids else []

        if not set_fields and not unset_fields:
            return False

        op = {}
        if set_fields:   op['$set']   = set_fields
        if unset_fields: op['$unset'] = unset_fields

        result = cls._col().update_one({'_id': ObjectId(user_id)}, op)
        return result.matched_count > 0

    @classmethod
    def get_primary_store_id(cls, user_doc: dict) -> str | None:
        """回傳使用者第一個 store_id（相容舊邏輯需要單一 store 的情況）。"""
        ids = user_doc.get('store_ids', [])
        return str(ids[0]) if ids else None

    @classmethod
    def ensure_guest_user(cls) -> None:
        """啟動時確保 __guest__ 系統帳號存在（鎖定，不可刪除）。"""
        if cls._col().find_one({'username': '__guest__'}):
            return
        hashed = bcrypt.hashpw(b'__guest__', bcrypt.gensalt())
        cls._col().insert_one({
            'username':   '__guest__',
            'password':   hashed.decode(),
            'role':       'viewer',
            'locked':     True,
            'created_at': datetime.utcnow(),
        })

    @classmethod
    def delete(cls, user_id: str) -> bool:
        doc = cls._col().find_one({'_id': ObjectId(user_id)}, {'locked': 1})
        if doc and doc.get('locked'):
            return False
        result = cls._col().delete_one({'_id': ObjectId(user_id)})
        return result.deleted_count > 0

    @classmethod
    def update_role_by_template(cls, template_id: str, role: str) -> int:
        """將所有指派此模板的使用者角色同步為 role，回傳更新筆數
        template_id 在 users collection 以字串儲存，直接用字串比對。
        """
        result = cls._col().update_many(
            {'template_id': str(template_id)},
            {'$set': {'role': role}}
        )
        return result.modified_count

    @staticmethod
    def check_password(plain: str, hashed: str) -> bool:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
