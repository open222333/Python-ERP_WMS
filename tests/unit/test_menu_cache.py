# [OPT-N3] 顧客點餐 menu 快取測試
import json

from src.models.menu import Menu
from src.redis_client import get_redis


def _create_menu(admin_headers, client, name='M1'):
    r = client.post('/menu/', json={'name': name}, headers=admin_headers)
    return r.get_json()['_id']


class TestCustMenuCache:
    def test_menu_endpoint_populates_cache(self, client, admin_headers):
        mid = _create_menu(admin_headers, client)
        client.post(f'/menu/{mid}/item', json={'name': 'A', 'price': 10},
                   headers=admin_headers)

        r = client.get(f'/customer-order/menu?menu_id={mid}')
        assert r.status_code == 200
        assert r.get_json()['data']['name'] == 'M1'

        raw = get_redis().get(f'cache:cust_menu:{mid}')
        assert raw is not None
        cached = json.loads(raw)
        assert cached['name'] == 'M1'

    def test_cache_hit_returns_stale_data_until_invalidated(self, client, admin_headers):
        mid = _create_menu(admin_headers, client)
        client.get(f'/customer-order/menu?menu_id={mid}')

        # 直接竄改快取值，證明第二次請求走快取（不重新讀 DB）
        get_redis().setex(f'cache:cust_menu:{mid}', 60,
                          json.dumps({'_id': mid, 'name': 'STALE_FROM_CACHE'}))
        r = client.get(f'/customer-order/menu?menu_id={mid}')
        assert r.get_json()['data']['name'] == 'STALE_FROM_CACHE'

    def test_update_menu_invalidates_cache(self, client, admin_headers):
        mid = _create_menu(admin_headers, client)
        client.get(f'/customer-order/menu?menu_id={mid}')
        assert get_redis().get(f'cache:cust_menu:{mid}') is not None

        client.put(f'/menu/{mid}', json={'name': 'M1-renamed'}, headers=admin_headers)
        assert get_redis().get(f'cache:cust_menu:{mid}') is None

        r = client.get(f'/customer-order/menu?menu_id={mid}')
        assert r.get_json()['data']['name'] == 'M1-renamed'

    def test_add_item_invalidates_cache(self, client, admin_headers):
        mid = _create_menu(admin_headers, client)
        client.get(f'/customer-order/menu?menu_id={mid}')
        client.post(f'/menu/{mid}/item', json={'name': 'B', 'price': 20},
                   headers=admin_headers)
        assert get_redis().get(f'cache:cust_menu:{mid}') is None

    def test_redis_failure_falls_back_to_direct_read(self, client, admin_headers, monkeypatch):
        mid = _create_menu(admin_headers, client)

        import src.cache as cache_mod

        def _boom():
            raise ConnectionError('redis down')

        monkeypatch.setattr(cache_mod, 'get_redis', _boom)
        r = client.get(f'/customer-order/menu?menu_id={mid}')
        assert r.status_code == 200
        assert r.get_json()['data']['name'] == 'M1'
