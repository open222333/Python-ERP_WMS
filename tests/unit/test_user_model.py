"""User model：create / check_password 容錯 / update / delete 鎖定保護。"""
import bcrypt
from bson import ObjectId

from src.models.user import User


class TestUserCreate:
    def test_create_and_find_by_username(self):
        uid = User.create('alice', 'secret123', role='operator')
        assert ObjectId.is_valid(uid)
        doc = User.find_by_username('alice')
        assert doc['role'] == 'operator'
        assert doc['store_ids'] == []
        # 密碼必須是 bcrypt hash，不可為明文
        assert doc['password'] != 'secret123'
        assert doc['password'].startswith('$2')

    def test_create_with_store_ids_stored_as_objectid(self):
        sid = str(ObjectId())
        User.create('bob', 'pw', role='cashier', store_ids=[sid, '', None])
        doc = User.find_by_username('bob')
        assert doc['store_ids'] == [ObjectId(sid)]   # 空值被過濾

    def test_serialize_store_ids_to_str(self):
        sid = str(ObjectId())
        User.create('carol', 'pw', store_ids=[sid])
        users = {u['username']: u for u in User.find_all()}
        assert users['carol']['store_ids'] == [sid]
        assert 'password' not in users['carol']


class TestCheckPassword:
    def test_correct_password(self):
        hashed = bcrypt.hashpw(b'goodpw', bcrypt.gensalt()).decode()
        assert User.check_password('goodpw', hashed) is True

    def test_wrong_password(self):
        hashed = bcrypt.hashpw(b'goodpw', bcrypt.gensalt()).decode()
        assert User.check_password('badpw', hashed) is False

    def test_malformed_hash_returns_false(self):
        # FIXES.md: check_password 對格式錯誤 hash 應回 False 而非拋例外
        assert User.check_password('any', 'not-a-bcrypt-hash') is False

    def test_none_hash_returns_false(self):
        assert User.check_password('any', None) is False

    def test_empty_hash_returns_false(self):
        assert User.check_password('any', '') is False


class TestUserUpdateDelete:
    def test_update_password_and_role(self):
        uid = User.create('dave', 'oldpw', role='viewer')
        assert User.update(uid, password='newpw', role='admin') is True
        doc = User.find_by_username('dave')
        assert doc['role'] == 'admin'
        assert User.check_password('newpw', doc['password'])
        assert not User.check_password('oldpw', doc['password'])

    def test_update_nothing_returns_false(self):
        uid = User.create('erin', 'pw')
        assert User.update(uid) is False

    def test_update_unset_template_id(self):
        uid = User.create('frank', 'pw', template_id='tmpl1')
        assert User.update(uid, template_id=None) is True
        doc = User.find_by_username('frank')
        assert 'template_id' not in doc

    def test_delete_normal_user(self):
        uid = User.create('gina', 'pw')
        assert User.delete(uid) is True
        assert User.find_by_username('gina') is None

    def test_delete_locked_user_refused(self):
        User.ensure_guest_user()
        guest = User.find_by_username('__guest__')
        assert User.delete(str(guest['_id'])) is False
        assert User.find_by_username('__guest__') is not None

    def test_update_role_by_template(self):
        User.create('h1', 'pw', role='viewer', template_id='t1')
        User.create('h2', 'pw', role='viewer', template_id='t1')
        User.create('h3', 'pw', role='viewer', template_id='t2')
        assert User.update_role_by_template('t1', 'operator') == 2
        assert User.find_by_username('h1')['role'] == 'operator'
        assert User.find_by_username('h3')['role'] == 'viewer'
