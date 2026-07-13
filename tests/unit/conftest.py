"""
pytest 單元測試共用 fixture。

重點：
- 在 import `app` 套件「之前」就以 mongomock / fakeredis 取代
  src.mongo 與 src.redis_client 的模組層單例，
  確保所有 model 的 get_db() / get_redis() 拿到假的連線。
- `app` fixture 為 session 級（app/__init__.py 的 Flask 實例是模組層全域，
  create_app() 只能呼叫一次，否則 blueprint 會重複註冊）。
- 每個測試 function 級清空所有 mongomock collection 與 fakeredis。
- flask-limiter 在測試中停用（storage 指向 Redis，避免計數/連線干擾）。
"""
import itertools
import os
import sys
from pathlib import Path

import pytest
from bson import ObjectId

# ── 專案根目錄加入 sys.path，並 chdir（conf/config.ini 為相對路徑讀取）──
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# ── 先 patch MongoDB / Redis 單例，再 import app ────────────────────
import mongomock
import src.mongo as _mongo_mod

_mongo_client = mongomock.MongoClient()
_mongo_mod._client = _mongo_client
_mongo_mod._db = _mongo_client['wms_unit_test']

import fakeredis
import src.redis_client as _redis_mod

_fake_redis = fakeredis.FakeRedis(decode_responses=True)
_redis_mod._client = _fake_redis

# ── 加速 bcrypt：測試中一律使用最低 cost（不影響產品程式碼）─────────
import bcrypt as _bcrypt

_orig_gensalt = _bcrypt.gensalt
_bcrypt.gensalt = lambda rounds=12, prefix=b"2b": _orig_gensalt(rounds=4)


# ─────────────────────────────────────────────────────────────
#  Flask app / client
# ─────────────────────────────────────────────────────────────
@pytest.fixture(scope='session')
def app():
    from app import create_app
    from app.extensions import limiter
    from conf.config import TestingConfig

    application = create_app(TestingConfig)
    application.config.update(TESTING=True)
    # 登入速率限制停用：storage URI 指向 Redis，測試中不需要
    limiter.enabled = False
    return application


@pytest.fixture
def client(app):
    return app.test_client()


# ─────────────────────────────────────────────────────────────
#  每個測試清空 DB / Redis（function 級隔離）
# ─────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def db():
    database = _mongo_mod._db
    for name in database.list_collection_names():
        database[name].delete_many({})
    _fake_redis.flushall()
    yield database


# ─────────────────────────────────────────────────────────────
#  認證 helper
# ─────────────────────────────────────────────────────────────
_seq = itertools.count(1)


@pytest.fixture
def make_user(db):
    """建立真實使用者（bcrypt hash 密碼），回傳帳密資訊。供登入測試使用。"""

    def _make(role='admin', store_ids=None, username=None,
              password='pw123456', locked=False):
        from src.models.user import User
        username = username or f'u{next(_seq)}_{role}'
        uid = User.create(username, password, role=role,
                          store_ids=[str(s) for s in (store_ids or [])])
        if locked:
            db['users'].update_one({'username': username},
                                   {'$set': {'locked': True}})
        return {'_id': uid, 'username': username, 'password': password}

    return _make


@pytest.fixture
def make_headers(app, db):
    """建立使用者並直接簽發 JWT，回傳 Authorization header dict。

    role: super_admin / admin / operator / cashier / viewer
    store_ids: 綁定店家（多店家隔離用），None 或 [] = 總部帳號
    """

    def _make(role='admin', store_ids=None, username=None):
        from flask_jwt_extended import create_access_token
        username = username or f'h{next(_seq)}_{role}'
        sids = [str(s) for s in (store_ids or [])]
        db['users'].insert_one({
            'username': username,
            'password': 'x',        # 不經登入端點，hash 不重要
            'role': role,
            'store_ids': [ObjectId(s) for s in sids],
        })
        with app.test_request_context():
            token = create_access_token(
                identity=username,
                additional_claims={'role': role, 'store_ids': sids})
        return {'Authorization': f'Bearer {token}'}

    return _make


@pytest.fixture
def admin_headers(make_headers):
    return make_headers('admin')


@pytest.fixture
def operator_headers(make_headers):
    return make_headers('operator')


@pytest.fixture
def cashier_headers(make_headers):
    return make_headers('cashier')
