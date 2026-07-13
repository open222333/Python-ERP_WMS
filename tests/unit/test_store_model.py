"""Store model：_next_code 遞增（含 S999→S1000）與 CRUD。"""
from src.models.store import Store


class TestNextCode:
    def test_first_code_is_s001(self):
        assert Store._next_code() == 'S001'

    def test_code_increments(self):
        Store.create(name='A')          # S001
        Store.create(name='B')          # S002
        assert Store._next_code() == 'S003'

    def test_s999_rolls_to_s1000(self):
        Store.create(name='X', code='S999')
        assert Store._next_code() == 'S1000'
        Store.create(name='Y')
        assert Store.find_by_code('S1000')['name'] == 'Y'

    def test_non_matching_codes_ignored(self):
        Store.create(name='X', code='CUSTOM-1')
        Store.create(name='Y', code='S12X')      # 不符 ^S\d+$
        assert Store._next_code() == 'S001'

    def test_explicit_code_kept(self):
        sid = Store.create(name='Z', code=' S777 ')
        assert Store.find_by_id(sid)['code'] == 'S777'   # strip 後保留


class TestStoreCrud:
    def test_create_defaults(self):
        sid = Store.create(name='門市一')
        s = Store.find_by_id(sid)
        assert s['status'] == 'active'
        assert s['store_role_id'] is None
        assert s['code'] == 'S001'

    def test_update_and_delete(self):
        sid = Store.create(name='門市二')
        assert Store.update(sid, name='改名', status='inactive') is True
        s = Store.find_by_id(sid)
        assert s['name'] == '改名' and s['status'] == 'inactive'
        assert Store.update(sid) is False    # 無欄位
        assert Store.delete(sid) is True
        assert Store.find_by_id(sid) is None

    def test_find_all_serializes(self):
        Store.create(name='A')
        rows = Store.find_all()
        assert len(rows) == 1
        assert isinstance(rows[0]['_id'], str)
        assert isinstance(rows[0]['created_at'], str)   # isoformat
