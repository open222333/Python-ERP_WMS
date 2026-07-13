"""Inbound API：完整流程 pending → confirm → complete 增庫存、狀態機防護。"""
import pytest
from bson import ObjectId

from src.models.inventory import Inventory, StockMovement
from helpers import create_product, create_warehouse


@pytest.fixture
def ctx(operator_headers):
    return {'h': operator_headers,
            'wid': create_warehouse(),
            'pid': create_product()}


def _make_order(client, ctx, qty=10, price=3.0):
    r = client.post('/inbound/', headers=ctx['h'],
                    json={'warehouse_id': ctx['wid'], 'supplier': '供應商'})
    assert r.status_code == 201
    oid = r.get_json()['id']
    r = client.post(f'/inbound/{oid}/item', headers=ctx['h'],
                    json={'product_id': ctx['pid'], 'expected_qty': qty,
                          'unit_price': price})
    assert r.status_code == 200
    return oid


class TestInboundCreate:
    def test_create_missing_warehouse_400(self, client, ctx):
        assert client.post('/inbound/', headers=ctx['h'],
                           json={}).status_code == 400

    def test_create_unknown_warehouse_404(self, client, ctx):
        r = client.post('/inbound/', headers=ctx['h'],
                        json={'warehouse_id': str(ObjectId())})
        assert r.status_code == 404

    def test_add_item_qty_zero_400(self, client, ctx):
        oid = _make_order(client, ctx)
        r = client.post(f'/inbound/{oid}/item', headers=ctx['h'],
                        json={'product_id': ctx['pid'], 'expected_qty': 0})
        assert r.status_code == 400


class TestInboundFlow:
    def test_full_flow_increases_inventory(self, client, ctx):
        oid = _make_order(client, ctx, qty=10)
        assert client.post(f'/inbound/{oid}/confirm',
                           headers=ctx['h']).status_code == 200
        assert Inventory.get_quantity(ctx['pid'], ctx['wid']) == 0  # 尚未完成
        r = client.post(f'/inbound/{oid}/complete', headers=ctx['h'])
        assert r.status_code == 200
        assert Inventory.get_quantity(ctx['pid'], ctx['wid']) == 10
        # 移動紀錄
        moves = StockMovement.find_all(warehouse_id=ctx['wid'])
        assert len(moves) == 1
        assert moves[0]['movement_type'] == 'inbound'
        assert moves[0]['reference_type'] == 'inbound_order'
        assert moves[0]['after_qty'] == 10

    def test_complete_with_received_qtys_override(self, client, ctx):
        oid = _make_order(client, ctx, qty=10)
        r = client.get(f'/inbound/{oid}', headers=ctx['h'])
        item_id = r.get_json()['data']['items'][0]['_id']
        client.post(f'/inbound/{oid}/confirm', headers=ctx['h'])
        r = client.post(f'/inbound/{oid}/complete', headers=ctx['h'],
                        json={'received_qtys': {item_id: 7}})
        assert r.status_code == 200
        assert Inventory.get_quantity(ctx['pid'], ctx['wid']) == 7

    def test_complete_negative_received_qty_400(self, client, ctx):
        oid = _make_order(client, ctx)
        client.post(f'/inbound/{oid}/confirm', headers=ctx['h'])
        r = client.post(f'/inbound/{oid}/complete', headers=ctx['h'],
                        json={'received_qtys': {'whatever': -1}})
        assert r.status_code == 400

    def test_confirm_without_items_400(self, client, ctx):
        r = client.post('/inbound/', headers=ctx['h'],
                        json={'warehouse_id': ctx['wid']})
        oid = r.get_json()['id']
        assert client.post(f'/inbound/{oid}/confirm',
                           headers=ctx['h']).status_code == 400

    def test_complete_when_pending_400(self, client, ctx):
        oid = _make_order(client, ctx)
        assert client.post(f'/inbound/{oid}/complete',
                           headers=ctx['h']).status_code == 400
        assert Inventory.get_quantity(ctx['pid'], ctx['wid']) == 0

    def test_complete_twice_no_double_inventory(self, client, ctx):
        oid = _make_order(client, ctx, qty=10)
        client.post(f'/inbound/{oid}/confirm', headers=ctx['h'])
        assert client.post(f'/inbound/{oid}/complete',
                           headers=ctx['h']).status_code == 200
        assert client.post(f'/inbound/{oid}/complete',
                           headers=ctx['h']).status_code == 400
        assert Inventory.get_quantity(ctx['pid'], ctx['wid']) == 10   # 不重複入帳

    def test_cancel_completed_400(self, client, ctx):
        oid = _make_order(client, ctx)
        client.post(f'/inbound/{oid}/confirm', headers=ctx['h'])
        client.post(f'/inbound/{oid}/complete', headers=ctx['h'])
        assert client.post(f'/inbound/{oid}/cancel',
                           headers=ctx['h']).status_code == 400

    def test_cancel_pending_ok(self, client, ctx):
        oid = _make_order(client, ctx)
        assert client.post(f'/inbound/{oid}/cancel',
                           headers=ctx['h']).status_code == 200
        r = client.get(f'/inbound/{oid}', headers=ctx['h'])
        assert r.get_json()['data']['status'] == 'cancelled'


class TestInboundList:
    def test_list_pagination_and_status_filter(self, client, ctx):
        oids = [_make_order(client, ctx) for _ in range(3)]
        client.post(f'/inbound/{oids[0]}/confirm', headers=ctx['h'])

        r = client.get('/inbound/?limit=2', headers=ctx['h'])
        assert len(r.get_json()['data']) == 2
        r = client.get('/inbound/?limit=2&offset=2', headers=ctx['h'])
        assert len(r.get_json()['data']) == 1
        r = client.get('/inbound/?status=confirmed', headers=ctx['h'])
        data = r.get_json()['data']
        assert len(data) == 1 and data[0]['_id'] == oids[0]
