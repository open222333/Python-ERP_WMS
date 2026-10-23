"""
[A2] 多店家隔離：庫存、出入庫、分析、外送、操作紀錄、發票
（倉庫與菜單見 test_store_isolation_api.py）

原則：店家帳號只看得到／改得到本店資料，他店資料一律視同不存在（404 或空清單）；
影響所有店家的全域設定與全域資料寫入限總部帳號（403）。
"""
from datetime import datetime

import pytest
from bson import ObjectId

from src.models.delivery import DeliveryOrder, DeliverySettings
from src.models.inbound import InboundOrder
from src.models.inventory import StockMovement
from src.models.log import Log
from helpers import create_store, create_warehouse, create_product, seed_stock


@pytest.fixture
def env(db):
    sa, sb = create_store('A店'), create_store('B店')
    wa, wb = create_warehouse(store_id=sa), create_warehouse(store_id=sb)
    p = create_product(name='珍珠', min_stock=50)
    seed_stock(p, wa, 10)
    seed_stock(p, wb, 20)
    return dict(sa=sa, sb=sb, wa=wa, wb=wb, p=p)


@pytest.fixture
def h_a(make_headers, env):
    return make_headers('admin', store_ids=[env['sa']], username='a_admin')


@pytest.fixture
def h_hq(make_headers):
    return make_headers('admin', username='hq_admin')


# ─────────────────────────────────────────────────────────────
#  庫存與異動
# ─────────────────────────────────────────────────────────────
class TestInventory:
    def test_list_only_own_warehouses(self, client, env, h_a, h_hq):
        rows = client.get('/inventory/', headers=h_a).get_json()['data']
        assert {r['warehouse_id'] for r in rows} == {env['wa']}
        rows = client.get(f"/inventory/?warehouse_id={env['wb']}", headers=h_a).get_json()['data']
        assert rows == []
        assert len(client.get('/inventory/', headers=h_hq).get_json()['data']) == 2

    def test_adjust_other_store_404(self, client, db, env, h_a):
        r = client.post('/inventory/adjust', headers=h_a,
                        json={'product_id': env['p'], 'warehouse_id': env['wb'], 'quantity': 0})
        assert r.status_code == 404
        doc = db['inventory'].find_one({'warehouse_id': ObjectId(env['wb'])})
        assert doc['quantity'] == 20

    def test_batch_other_store_404(self, client, env, h_a):
        r = client.post('/inventory/batch', headers=h_a, json={
            'type': 'outbound', 'warehouse_id': env['wb'],
            'items': [{'product_id': env['p'], 'qty': 1}]})
        assert r.status_code == 404

    def test_movements_only_own(self, client, env, h_a):
        for wid in (env['wa'], env['wb']):
            StockMovement.create(product_id=env['p'], warehouse_id=wid, movement_type='inbound',
                                 quantity=1, before_qty=0, after_qty=1)
        rows = client.get('/inventory/movement/', headers=h_a).get_json()['data']
        assert {r['warehouse_id'] for r in rows} == {env['wa']}


# ─────────────────────────────────────────────────────────────
#  出入庫單
# ─────────────────────────────────────────────────────────────
class TestInOutbound:
    def _order(self, wid):
        return InboundOrder.create({'warehouse_id': wid, 'warehouse_name': 'W'})

    def test_list_get_and_actions(self, client, env, h_a):
        oa, ob = self._order(env['wa']), self._order(env['wb'])
        ids = [o['_id'] for o in client.get('/inbound/', headers=h_a).get_json()['data']]
        assert oa in ids and ob not in ids
        assert client.get(f'/inbound/{ob}', headers=h_a).status_code == 404
        assert client.post(f'/inbound/{ob}/confirm', headers=h_a).status_code == 404
        assert client.post(f'/inbound/{ob}/cancel', headers=h_a).status_code == 404
        assert client.post(f'/inbound/{ob}/complete', headers=h_a, json={}).status_code == 404
        assert client.put(f'/inbound/{ob}', headers=h_a, json={'remark': 'x'}).status_code == 404
        assert client.post(f'/inbound/{ob}/item', headers=h_a,
                           json={'product_id': env['p'], 'expected_qty': 1}).status_code == 404
        assert client.get(f'/inbound/{oa}', headers=h_a).status_code == 200

    def test_create_with_other_store_warehouse_404(self, client, env, h_a):
        r = client.post('/inbound/', headers=h_a, json={'warehouse_id': env['wb']})
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────
#  儀表板分析
# ─────────────────────────────────────────────────────────────
def test_analytics_alerts_only_own(client, env, h_a, h_hq):
    alerts = client.get('/analytics/stock_alerts', headers=h_a).get_json()['data']
    assert {a['warehouse_id'] for a in alerts} == {env['wa']}       # 兩倉都低於 min_stock 50
    assert len(client.get('/analytics/stock_alerts', headers=h_hq).get_json()['data']) == 2
    s = client.get('/analytics/summary', headers=h_a).get_json()['data']
    assert s['stock_alert_count']['low'] == 1


# ─────────────────────────────────────────────────────────────
#  外送
# ─────────────────────────────────────────────────────────────
class TestDelivery:
    def _order(self, ext, store_code=None):
        return DeliveryOrder.create_from_normalized({
            'platform': 'foodpanda', 'external_order_id': ext,
            'external_store_id': store_code or '', 'items': []})

    def test_orders_scoped(self, client, env, h_a, h_hq):
        DeliverySettings.upsert('foodpanda', store_ref=env['sa'], vendor_code='VA')
        DeliverySettings.upsert('foodpanda', store_ref=env['sb'], vendor_code='VB')
        oa, ob, ou = self._order('A1', 'VA'), self._order('B1', 'VB'), self._order('U1')
        ids = [o['_id'] for o in client.get('/delivery/orders', headers=h_a).get_json()['data']]
        assert ids == [oa]
        assert client.get(f'/delivery/orders/{ob}', headers=h_a).status_code == 404
        assert client.get(f'/delivery/orders/{ou}', headers=h_a).status_code == 404   # 未歸屬→限總部
        assert client.put(f'/delivery/orders/{ob}/status', headers=h_a,
                          json={'status': 'cancelled'}).status_code == 404
        assert len(client.get('/delivery/orders', headers=h_hq).get_json()['data']) == 3

    def test_global_writes_require_hq(self, client, env, h_a):
        assert client.put('/delivery/settings/foodpanda', headers=h_a,
                          json={'enabled': True}).status_code == 403
        assert client.post('/delivery/mappings', headers=h_a, json={
            'platform': 'foodpanda', 'external_product_id': 'E', 'product_id': env['p']
        }).status_code == 403
        assert client.post('/delivery/mapping-templates/', headers=h_a,
                           json={'name': 'T'}).status_code == 403
        assert client.post('/delivery/sync/foodpanda', headers=h_a).status_code == 403

    def test_store_settings_scoped(self, client, env, h_a):
        assert client.get(f"/delivery/store/{env['sb']}/settings/foodpanda",
                          headers=h_a).status_code == 404
        assert client.put(f"/delivery/store/{env['sb']}/settings/foodpanda",
                          headers=h_a, json={'enabled': True}).status_code == 404
        stores = client.get('/delivery/store/', headers=h_a).get_json()['data']
        assert [s['store_id'] for s in stores] == [env['sa']]
        assert client.get(f"/delivery/store/{env['sa']}/settings/foodpanda",
                          headers=h_a).status_code == 200


# ─────────────────────────────────────────────────────────────
#  操作紀錄（[A2] 店家過濾、[A6] 關鍵字跳脫）
# ─────────────────────────────────────────────────────────────
class TestLogs:
    def test_only_own_store_users(self, client, db, env, h_a):
        db['users'].insert_one({'username': 'b_staff', 'store_ids': [ObjectId(env['sb'])]})
        Log.create('a_admin', '登入', '')
        Log.create('b_staff', '登入', '')
        Log.create('hq_admin', '登入', '')
        names = {l['username'] for l in client.get('/log/', headers=h_a).get_json()['data']}
        assert names == {'a_admin'}
        assert client.get('/log/stats', headers=h_a).get_json()['total'] == 1

    def test_cleanup_and_import_require_hq(self, client, h_a):
        assert client.post('/log/cleanup', headers=h_a, json={'days': 1}).status_code == 403
        assert client.post('/log/import', headers=h_a, json={'rows': []}).status_code == 403

    def test_keyword_is_literal_not_regex(self, client, h_hq):
        Log.create('alice', '登入', '')
        assert client.get('/log/?username=.*', headers=h_hq).get_json()['data'] == []
        assert len(client.get('/log/?username=ALI', headers=h_hq).get_json()['data']) == 1


# ─────────────────────────────────────────────────────────────
#  發票
# ─────────────────────────────────────────────────────────────
def _pos_order(db, store_id, total=100):
    return str(db['pos_orders'].insert_one({
        'order_no': f'POS-{ObjectId()}', 'store_id': ObjectId(store_id), 'status': 'completed',
        'items': [{'product_name': '大腸麵線', 'quantity': 1, 'unit_price': total}],
        'total_amount': total, 'created_at': datetime.utcnow()}).inserted_id)


class TestInvoiceIsolation:
    def test_list_get_issue_scoped(self, client, db, env, h_a):
        oa, ob = _pos_order(db, env['sa']), _pos_order(db, env['sb'])
        ia = db['invoices'].insert_one({'order_id': oa, 'store_id': ObjectId(env['sa']),
                                        'status': 'issued', 'created_at': datetime.utcnow()}).inserted_id
        ib = db['invoices'].insert_one({'order_id': ob, 'store_id': ObjectId(env['sb']),
                                        'status': 'issued', 'created_at': datetime.utcnow()}).inserted_id
        # 舊資料沒有 store_id：依銷售單判斷
        il = db['invoices'].insert_one({'order_id': ob, 'status': 'voided',
                                        'created_at': datetime.utcnow()}).inserted_id
        ids = [i['_id'] for i in client.get('/invoice/', headers=h_a).get_json()['data']]
        assert ids == [str(ia)]
        assert client.get(f'/invoice/{ib}', headers=h_a).status_code == 404
        assert client.get(f'/invoice/{il}', headers=h_a).status_code == 404
        assert client.post(f'/invoice/{ib}/void', headers=h_a, json={}).status_code == 404
        assert client.post('/invoice/issue', headers=h_a, json={'order_id': ob}).status_code == 404

    def test_store_settings_scoped(self, client, env, h_a):
        assert client.get(f"/invoice/store/{env['sb']}/settings", headers=h_a).status_code == 404
        assert client.post(f"/invoice/store/{env['sb']}/terminals/", headers=h_a,
                           json={'name': 'x'}).status_code == 404
        assert client.put('/invoice/settings', headers=h_a, json={}).status_code == 403
