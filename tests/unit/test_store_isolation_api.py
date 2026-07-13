"""多店家隔離（IDOR 修復回歸測試）。

FIXES.md 2026-07-04：
- app/warehouse/view.py: update/delete 先以 store_filter 驗證所有權，非本店回 404
- app/menu/view.py: item/category/option-group 等端點以 store_filter 驗證菜單所有權
"""
import pytest
from bson import ObjectId

from helpers import create_store, create_warehouse, create_menu


@pytest.fixture
def two_stores():
    """A/B 兩店各一倉庫一菜單。"""
    sa, sb = create_store('A店'), create_store('B店')
    return {
        'store_a': sa, 'store_b': sb,
        'wh_a': create_warehouse(store_id=sa),
        'wh_b': create_warehouse(store_id=sb),
        'menu_a': create_menu(store_id=sa),
        'menu_b': create_menu(store_id=sb),
    }


class TestWarehouseIsolation:
    def test_list_only_own_store(self, client, make_headers, two_stores):
        h = make_headers('operator', store_ids=[two_stores['store_a']])
        r = client.get('/warehouse/', headers=h)
        ids = [w['_id'] for w in r.get_json()['data']]
        assert two_stores['wh_a'] in ids
        assert two_stores['wh_b'] not in ids

    def test_get_other_store_warehouse_404(self, client, make_headers,
                                           two_stores):
        h = make_headers('operator', store_ids=[two_stores['store_a']])
        r = client.get(f"/warehouse/{two_stores['wh_b']}", headers=h)
        assert r.status_code == 404

    def test_put_other_store_warehouse_404(self, client, make_headers,
                                           two_stores):
        h = make_headers('operator', store_ids=[two_stores['store_a']])
        r = client.put(f"/warehouse/{two_stores['wh_b']}", headers=h,
                       json={'name': 'hacked'})
        assert r.status_code == 404
        # 資料未被竄改
        from src.models.warehouse import Warehouse
        assert Warehouse.find_by_id(two_stores['wh_b'])['name'] != 'hacked'

    def test_delete_other_store_warehouse_404(self, client, make_headers,
                                              two_stores):
        h = make_headers('admin', store_ids=[two_stores['store_a']])
        r = client.delete(f"/warehouse/{two_stores['wh_b']}", headers=h)
        assert r.status_code == 404
        from src.models.warehouse import Warehouse
        assert Warehouse.find_by_id(two_stores['wh_b']) is not None

    def test_put_own_store_warehouse_ok(self, client, make_headers,
                                        two_stores):
        h = make_headers('operator', store_ids=[two_stores['store_a']])
        r = client.put(f"/warehouse/{two_stores['wh_a']}", headers=h,
                       json={'name': '改名'})
        assert r.status_code == 200
        from src.models.warehouse import Warehouse
        assert Warehouse.find_by_id(two_stores['wh_a'])['name'] == '改名'

    def test_super_admin_can_touch_any_store(self, client, make_headers,
                                             two_stores):
        h = make_headers('super_admin')
        r = client.put(f"/warehouse/{two_stores['wh_b']}", headers=h,
                       json={'name': 'HQ改'})
        assert r.status_code == 200


class TestMenuIsolation:
    def test_get_other_store_menu_404(self, client, make_headers, two_stores):
        h = make_headers('operator', store_ids=[two_stores['store_a']])
        assert client.get(f"/menu/{two_stores['menu_b']}",
                          headers=h).status_code == 404

    def test_put_other_store_menu_404(self, client, make_headers, two_stores):
        h = make_headers('operator', store_ids=[two_stores['store_a']])
        r = client.put(f"/menu/{two_stores['menu_b']}", headers=h,
                       json={'name': 'hacked'})
        assert r.status_code == 404

    def test_delete_other_store_menu_404(self, client, make_headers,
                                         two_stores):
        h = make_headers('admin', store_ids=[two_stores['store_a']])
        r = client.delete(f"/menu/{two_stores['menu_b']}", headers=h)
        assert r.status_code == 404
        from src.models.menu import Menu
        assert Menu.find_by_id(two_stores['menu_b']) is not None

    def test_put_menu_item_of_other_store_404(self, client, make_headers,
                                              two_stores):
        # IDOR 修復端點：PUT /menu/<mid>/item/<item_id>
        h = make_headers('operator', store_ids=[two_stores['store_a']])
        r = client.put(f"/menu/{two_stores['menu_b']}/item/{ObjectId()}",
                       headers=h, json={'name': 'x'})
        assert r.status_code == 404

    def test_delete_menu_item_of_other_store_404(self, client, make_headers,
                                                 two_stores):
        h = make_headers('operator', store_ids=[two_stores['store_a']])
        r = client.delete(f"/menu/{two_stores['menu_b']}/item/{ObjectId()}",
                          headers=h)
        assert r.status_code == 404

    def test_put_option_group_of_other_store_404(self, client, make_headers,
                                                 two_stores):
        h = make_headers('operator', store_ids=[two_stores['store_a']])
        r = client.put(f"/menu/{two_stores['menu_b']}/option-group/{ObjectId()}",
                       headers=h, json={'name': 'x'})
        assert r.status_code == 404

    def test_put_own_store_menu_ok(self, client, make_headers, two_stores):
        h = make_headers('operator', store_ids=[two_stores['store_a']])
        r = client.put(f"/menu/{two_stores['menu_a']}", headers=h,
                       json={'name': '新菜單名'})
        assert r.status_code == 200

    def test_list_menus_only_own_store(self, client, make_headers, two_stores):
        h = make_headers('operator', store_ids=[two_stores['store_a']])
        r = client.get('/menu/', headers=h)
        ids = [m['_id'] for m in r.get_json()['data']]
        assert two_stores['menu_a'] in ids
        assert two_stores['menu_b'] not in ids
