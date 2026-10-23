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


def _claims_store_oids(claims: dict):
    """None = 總部／super_admin（不限店家）；否則為可存取的 store ObjectId 清單"""
    role = claims.get('role', 'viewer')
    store_ids = claims.get('store_ids', []) or []
    if role == 'super_admin' or not store_ids:
        return None
    oids = [ObjectId(sid) for sid in store_ids if sid]
    return oids or None


def store_filter_from_claims(claims: dict, field: str = 'store_id') -> dict:
    """依 JWT claims（或 SSE ticket 內容）產生店家過濾條件，規則同 get_store_filter"""
    oids = _claims_store_oids(claims)
    if oids is None:
        return {}
    return {field: oids[0]} if len(oids) == 1 else {field: {'$in': oids}}


def get_store_filter(field: str = 'store_id') -> dict:
    """回傳 MongoDB 查詢條件。
    - super_admin 或無 store_ids → {} （查全部）
    - 單一店家帳號 → {'store_id': ObjectId(...)}
    - 多店家帳號   → {'store_id': {'$in': [...]}}
    field：欄位名稱不是 store_id 時指定（例如外送訂單的 store_ref）
    """
    return store_filter_from_claims(get_jwt(), field)


# ── [A2] 多店家隔離共用 helper ─────────────────────────────
def is_hq() -> bool:
    """總部帳號（無綁定店家）或 super_admin：可存取全部店家與全域設定"""
    return _claims_store_oids(get_jwt()) is None


def require_hq(fn):
    """[A2] 影響所有店家的全域設定／全域資料寫入，限總部帳號（需放在 jwt_required 之後）"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_hq():
            return jsonify({'success': False, 'message': '此操作影響所有店家，僅限總部帳號'}), 403
        return fn(*args, **kwargs)
    return wrapper


def allowed_store_ids():
    """None = 不限；否則為可存取的 store ObjectId 清單"""
    return _claims_store_oids(get_jwt())


def store_allowed(store_id) -> bool:
    oids = allowed_store_ids()
    if oids is None:
        return True
    try:
        return ObjectId(str(store_id)) in oids
    except Exception:
        return False


def allowed_warehouse_ids():
    """None = 不限；否則為所屬店家的倉庫 ObjectId 清單（庫存、異動、出入庫依倉庫隔離）"""
    oids = allowed_store_ids()
    if oids is None:
        return None
    from src.mongo import get_db
    return [w['_id'] for w in get_db()['warehouses'].find(
        {'store_id': {'$in': oids}}, {'_id': 1})]


def warehouse_allowed(warehouse_id) -> bool:
    wids = allowed_warehouse_ids()
    if wids is None:
        return True
    try:
        return ObjectId(str(warehouse_id)) in wids
    except Exception:
        return False


def get_current_store_id() -> str | None:
    """回傳目前登入帳號的第一個 store_id 字串，總部帳號回傳 None。
    供需要寫入單一 store_id 的資源建立使用（倉庫、菜單、POS 銷售）。
    """
    store_ids = get_jwt().get('store_ids', [])
    return store_ids[0] if store_ids else None
