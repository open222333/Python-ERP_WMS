"""
[D1] 外送平台狀態轉換＋合法轉移
[D2] 三種銷售管道扣庫／回補規則一致：
     POS 結帳扣、退款依異動帳原樣補；外送接單扣、取消作廢並回補；掃碼點餐完成時扣
"""
import pytest
from bson import ObjectId

from src.constants import DeliveryOrderStatus as S
from src.models.delivery import DeliveryOrder, DeliveryMapping, DeliverySettings
from src.models.pos import PosOrder
from src.services import delivery_service
from helpers import create_store, create_warehouse, create_product, create_menu, seed_stock


def _qty(db, pid, wid):
    d = db['inventory'].find_one({'product_id': ObjectId(pid), 'warehouse_id': ObjectId(wid)})
    return d['quantity'] if d else None


@pytest.fixture
def env(db):
    """一店兩倉；菜單品項「雙料餐」= 珍珠×2（預設倉）＋茶葉×1（指定 W2）"""
    from src.models.menu import Menu
    from src.models.settings import SystemSettings
    sid = create_store()
    w1 = create_warehouse(store_id=sid)
    w2 = create_warehouse(store_id=sid)
    p1 = create_product(name='珍珠')
    p2 = create_product(name='茶葉')
    seed_stock(p1, w1, 100)
    seed_stock(p2, w2, 100)
    mid = create_menu(store_id=sid)
    combo = Menu.add_item(mid, {
        'name': '雙料餐', 'price': 80, 'consume_inventory': True,
        'linked_products': [
            {'product_id': p1, 'warehouse_id': None, 'consume_qty': 2},
            {'product_id': p2, 'warehouse_id': w2,   'consume_qty': 1},
        ],
    })
    no_stock_item = Menu.add_item(mid, {
        'name': '白開水', 'price': 0, 'consume_inventory': False,
        'linked_products': [{'product_id': p1, 'consume_qty': 1}],
    })
    SystemSettings.set('default_warehouse_id', w1)
    return dict(sid=sid, w1=w1, w2=w2, p1=p1, p2=p2, mid=mid,
                combo=combo, water=no_stock_item)


# ═════════════════════════════════════════════════════════════
#  D1：平台狀態轉換
# ═════════════════════════════════════════════════════════════
class TestPlatformStatusMapping:
    @pytest.mark.parametrize('raw,expected', [
        ('CREATED', S.NEW), ('ACCEPTED', S.CONFIRMED), ('DENIED', S.CANCELLED),
        ('CANCELED', S.CANCELLED), ('FINISHED', S.DELIVERED),
    ])
    def test_ubereats(self, raw, expected):
        from app.delivery.adapters.ubereats import UberEatsClient
        n = UberEatsClient.normalize_order({'id': 'x', 'current_state': raw})
        assert n['status'] == expected
        assert n['platform_status'] == raw

    @pytest.mark.parametrize('raw,expected', [
        ('NEW', S.NEW), ('confirmed', S.CONFIRMED), ('ready_for_pickup', S.READY),
        ('picked_up', S.PICKED_UP), ('delivered', S.DELIVERED), ('rejected', S.CANCELLED),
    ])
    def test_foodpanda(self, raw, expected):
        from app.delivery.adapters.foodpanda import FoodpandaClient
        n = FoodpandaClient.normalize_order({'code': 'x', 'status': {'code': raw}})
        assert n['status'] == expected

    def test_unknown_status_is_none_and_kept_raw(self):
        from app.delivery.adapters.ubereats import UberEatsClient
        n = UberEatsClient.normalize_order({'id': 'x', 'current_state': 'SOMETHING_NEW'})
        assert n['status'] is None and n['platform_status'] == 'SOMETHING_NEW'
        oid = DeliveryOrder.create_from_normalized(n)
        o = DeliveryOrder.find_by_id(oid)
        assert o['status'] == S.NEW and o['platform_status'] == 'SOMETHING_NEW'


class TestTransitions:
    @pytest.mark.parametrize('frm,to,ok', [
        (S.NEW, S.CONFIRMED, True), (S.NEW, S.DELIVERED, True),      # 可跳過
        (S.CONFIRMED, S.NEW, False), (S.READY, S.PREPARING, False),  # 不可倒退
        (S.READY, S.CANCELLED, True),
        (S.DELIVERED, S.CANCELLED, False), (S.CANCELLED, S.CONFIRMED, False),  # 終態
        (S.NEW, 'created', False),
    ])
    def test_table(self, frm, to, ok):
        assert S.is_valid_transition(frm, to) is ok

    def _order(self, status):
        oid = DeliveryOrder.create_from_normalized(
            {'platform': 'foodpanda', 'external_order_id': f'T-{ObjectId()}',
             'status': status, 'items': []})
        return oid

    def test_backward_rejected(self):
        oid = self._order(S.READY)
        changed, frm = DeliveryOrder.transition(oid, S.CONFIRMED)
        assert not changed and frm == S.READY
        assert DeliveryOrder.find_by_id(oid)['status'] == S.READY

    def test_same_status_is_noop_but_update_status_true(self):
        oid = self._order(S.CONFIRMED)
        assert DeliveryOrder.transition(oid, S.CONFIRMED) == (False, S.CONFIRMED)
        assert DeliveryOrder.update_status(oid, S.CONFIRMED) is True

    def test_legacy_unknown_status_treated_as_new(self, db):
        """修正前平台值被直接存入（如 'created'），仍可往前推進"""
        oid = self._order(S.NEW)
        db['delivery_orders'].update_one({'_id': ObjectId(oid)}, {'$set': {'status': 'created'}})
        changed, frm = DeliveryOrder.transition(oid, S.CONFIRMED)
        assert changed and frm == 'created'


# ═════════════════════════════════════════════════════════════
#  D2：外送接單／取消
# ═════════════════════════════════════════════════════════════
@pytest.fixture
def delivery_env(env):
    DeliverySettings.upsert('ubereats', store_ref=env['sid'], store_id='UE-STORE',
                            default_warehouse_id=env['w1'])
    DeliveryMapping.upsert('ubereats', None, 'UE-ITEM',
                           menu_id=env['mid'], menu_item_id=env['combo']['_id'])
    return env


def _ue_raw(state, oid='UE-1', qty=3):
    return {'id': oid, 'current_state': state, 'store': {'id': 'UE-STORE'},
            'cart': {'items': [{'id': 'UE-ITEM', 'title': '雙料餐', 'quantity': qty,
                                'price': {'unit_price': {'amount': 8000}}}]}}


def _ingest(state, **kw):
    from app.delivery.adapters.ubereats import UberEatsClient
    return delivery_service.ingest_normalized(UberEatsClient.normalize_order(_ue_raw(state, **kw)))


class TestDeliveryLifecycle:
    def test_platform_cancel_after_accept_voids_sale_and_restores(self, db, delivery_env):
        e = delivery_env
        oid, is_new, _ = _ingest('CREATED')
        assert is_new and _qty(db, e['p1'], e['w1']) == 100

        _ingest('ACCEPTED')                     # 平台端接單（非本系統操作）也要建銷售扣庫
        assert DeliveryOrder.find_by_id(oid)['status'] == S.CONFIRMED
        assert _qty(db, e['p1'], e['w1']) == 94     # 3 × 2
        assert _qty(db, e['p2'], e['w2']) == 97     # 3 × 1，指定倉
        sale = db['pos_orders'].find_one({'delivery_order_id': oid})
        assert sale['status'] == 'completed'

        _ingest('CANCELED')                     # UberEats 單 L 拼法
        assert DeliveryOrder.find_by_id(oid)['status'] == S.CANCELLED
        assert _qty(db, e['p1'], e['w1']) == 100
        assert _qty(db, e['p2'], e['w2']) == 100
        assert db['pos_orders'].find_one({'_id': sale['_id']})['status'] == 'refunded'

        _ingest('CANCELED')                     # 重複推播：不得重複回補
        assert _qty(db, e['p1'], e['w1']) == 100

    def test_new_order_arriving_already_accepted_creates_sale(self, db, delivery_env):
        oid, is_new, info = _ingest('ACCEPTED', oid='UE-2', qty=1)
        assert is_new and info.get('sale_id')
        assert _qty(db, delivery_env['p1'], delivery_env['w1']) == 98

    def test_skip_states_still_creates_sale_once(self, db, delivery_env):
        oid, _, _ = _ingest('CREATED', oid='UE-3', qty=1)
        delivery_service.change_status(oid, S.READY, 'u')       # new → ready（跳過 confirmed）
        delivery_service.change_status(oid, S.DELIVERED, 'u')   # 已接單 → 已接單，不重建
        assert db['pos_orders'].count_documents({'delivery_order_id': oid}) == 1
        assert _qty(db, delivery_env['p1'], delivery_env['w1']) == 98

    def test_cancel_before_accept_has_no_side_effects(self, db, delivery_env):
        oid, _, _ = _ingest('CREATED', oid='UE-4')
        r = delivery_service.change_status(oid, S.CANCELLED, 'u')
        assert r['changed'] and 'voided_sale_id' not in r
        assert db['pos_orders'].count_documents({}) == 0

    def test_api_rejects_backward_and_allows_same(self, db, client, delivery_env,
                                                  make_headers, monkeypatch):
        import app.delivery.views.orders as od

        class Stub:
            def accept_order(self, *a): return True
            def deny_order(self, *a): return True
        monkeypatch.setattr(od, '_get_ubereats_client', lambda: Stub())
        h = make_headers('operator')
        oid, _, _ = _ingest('ACCEPTED', oid='UE-5', qty=1)

        r = client.put(f'/delivery/orders/{oid}/status', json={'status': 'new'}, headers=h)
        assert r.status_code == 400
        r = client.put(f'/delivery/orders/{oid}/status', json={'status': 'confirmed'}, headers=h)
        assert r.status_code == 200 and r.get_json()['changed'] is False
        r = client.put(f'/delivery/orders/{oid}/status', json={'status': 'cancelled'}, headers=h)
        body = r.get_json()
        assert r.status_code == 200 and body['voided_sale_id']
        assert _qty(db, delivery_env['p1'], delivery_env['w1']) == 100


# ═════════════════════════════════════════════════════════════
#  D2：POS 退款依異動帳回補
# ═════════════════════════════════════════════════════════════
class TestPosRefundByLedger:
    def _sale(self, env, item, qty=2):
        r = PosOrder.create_sale(
            warehouse_id=env['w1'],
            items=[{**item, 'item_id': item['_id'], 'product_name': item['name'],
                    'product_sku': '', 'unit': '份', 'quantity': qty,
                    'unit_price': item['price']}],
            payment={'type': 'cash', 'cash_amount': 999}, discount=0, cashier='c')
        assert r['success'], r
        return r['order']['_id']

    def test_refund_restores_exactly_what_was_deducted(self, db, env):
        sid = self._sale(env, env['combo'], qty=2)
        assert _qty(db, env['p1'], env['w1']) == 96 and _qty(db, env['p2'], env['w2']) == 98
        assert PosOrder.refund(sid, '測試', 'c')['success']
        # 舊做法只會補 product_id × 2 = 2 到 w1（應補 4），且不會補 w2 的茶葉
        assert _qty(db, env['p1'], env['w1']) == 100
        assert _qty(db, env['p2'], env['w2']) == 100

    def test_refund_of_non_consuming_item_restores_nothing(self, db, env):
        sid = self._sale(env, env['water'], qty=5)
        assert _qty(db, env['p1'], env['w1']) == 100
        PosOrder.refund(sid, '測試', 'c')
        assert _qty(db, env['p1'], env['w1']) == 100   # 舊做法會憑空多補 5


# ═════════════════════════════════════════════════════════════
#  D2：掃碼點餐完成時扣庫
# ═════════════════════════════════════════════════════════════
class TestCustOrderStock:
    def _co(self, env, items, co_id=None):
        return {'_id': co_id or str(ObjectId()), 'order_no': 'C001', 'table_no': 'T1',
                'menu_id': env['mid'], 'store_id': env['sid'], 'total': 100,
                'items': items}

    def _ci(self, item, qty):
        return {'item_id': item['_id'], 'item_name': item['name'], 'qty': qty,
                'price': item['price']}

    def test_second_cust_order_sale_is_created(self, db, env):
        """回歸：舊 sparse 唯一索引讓第 2 筆點單銷售撞重複鍵、靜默漏建"""
        a = PosOrder.create_from_cust_order(self._co(env, []), 'u')
        b = PosOrder.create_from_cust_order(self._co(env, []), 'u')
        assert a and b and a != b

    def test_deducts_by_linked_products(self, db, env):
        sid = PosOrder.create_from_cust_order(
            self._co(env, [self._ci(env['combo'], 3), self._ci(env['water'], 2)]), 'u')
        assert _qty(db, env['p1'], env['w1']) == 94   # 只扣雙料餐 3×2，白開水不扣
        assert _qty(db, env['p2'], env['w2']) == 97
        sale = db['pos_orders'].find_one({'_id': ObjectId(sid)})
        assert str(sale['warehouse_id']) == env['w1'] and 'stock_skipped' not in sale

    def test_idempotent_no_double_deduction(self, db, env):
        co = self._co(env, [self._ci(env['combo'], 1)])
        a = PosOrder.create_from_cust_order(co, 'u')
        b = PosOrder.create_from_cust_order(co, 'u')
        assert a == b and _qty(db, env['p1'], env['w1']) == 98

    def test_insufficient_stock_recorded_not_blocking(self, db, env):
        sid = PosOrder.create_from_cust_order(self._co(env, [self._ci(env['combo'], 999)]), 'u')
        sale = db['pos_orders'].find_one({'_id': ObjectId(sid)})
        assert sale and any('庫存不足' in s for s in sale['stock_skipped'])
        assert _qty(db, env['p1'], env['w1']) == 100

    def test_refund_of_cust_order_sale_restores(self, db, env):
        sid = PosOrder.create_from_cust_order(self._co(env, [self._ci(env['combo'], 2)]), 'u')
        PosOrder.refund(sid, '客訴', 'u')
        assert _qty(db, env['p1'], env['w1']) == 100 and _qty(db, env['p2'], env['w2']) == 100
