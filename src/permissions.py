from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt
from bson import ObjectId

# super_admin(4) > admin(3) > operator(2) > cashier(1) > viewer(0)
ROLE_LEVELS = {
    'super_admin': 4,
    'admin':       3,
    'operator':    2,
    'cashier':     1,
    'viewer':      0,
}


def require_role(*roles):
    """允許 role level >= 所列最低 level 的使用者存取。
    super_admin 永遠通過所有角色檢查。
    """
    min_level = min(ROLE_LEVELS.get(r, 0) for r in roles)

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            role = claims.get('role', 'viewer')
            if ROLE_LEVELS.get(role, 0) < min_level:
                return jsonify({'success': False, 'message': '權限不足'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_store_filter() -> dict:
    """回傳 MongoDB 查詢條件。
    - super_admin 或無 store_ids → {} （查全部）
    - 單一店家帳號 → {'store_id': ObjectId(...)}
    - 多店家帳號   → {'store_id': {'$in': [...]}}
    """
    claims = get_jwt()
    role = claims.get('role', 'viewer')
    store_ids = claims.get('store_ids', [])
    if role == 'super_admin' or not store_ids:
        return {}
    oids = [ObjectId(sid) for sid in store_ids if sid]
    if not oids:
        return {}
    if len(oids) == 1:
        return {'store_id': oids[0]}
    return {'store_id': {'$in': oids}}


def get_current_store_id() -> str | None:
    """回傳目前登入帳號的第一個 store_id 字串，總部帳號回傳 None。
    供需要寫入單一 store_id 的資源建立使用（倉庫、菜單、POS 銷售）。
    """
    store_ids = get_jwt().get('store_ids', [])
    return store_ids[0] if store_ids else None
