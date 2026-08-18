"""
delivery 模組單元測試：
- DeliveryMapping（產品/菜單品項兩型）
- DeliverySettings（店家反查、有效設定合併）
- DeliveryOrder（external_store_id → store_ref 歸屬）
- PosOrder.create_from_delivery（對應解析順序、linked_products 扣庫存、跨倉、名稱式/模板回退）
- webhook 與訂單狀態 API（store 專屬設定生效）
"""
import pytest
from bson import ObjectId

from src.constants import DeliveryOrderStatus
from src.models.delivery import (
    DeliveryOrder, DeliveryMapping, DeliverySettings, DeliveryMappingTemplate,
)
from helpers import create_store, create_warehouse, create_product, create_menu, seed_stock


# ─────────────────────────────────────────────────────────────
#  共用建料
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def base_env(db):
    """一店一倉一產品 + 一份菜單（品項連結該產品，consume_qty=2）"""
    from src.models.menu import Menu
    sid = create_store()
    wid = create_warehouse(store_id=sid)
    pid = create_product(name='珍珠', unit='包')
    seed_stock(pid, wid, 100)
    mid = create_menu(name='POS 菜單', store_id=sid)
    item = Menu.add_item(mid, {
        'name': '珍珠奶茶', 'price': 60, 'consume_inventory': True,
        'linked_products': [{'product_id': pid, 'warehouse_id': wid, 'consume_qty': 2}],
    })
    return {'sid': sid, 'wid': wid, 'pid': pid, 'mid': mid, 'item': item}


def _order_doc(platform='foodpanda', ext_id='I-1', name='珍珠奶茶', qty=3,
               store_ref=None, external_order_no='FP-001'):
    return {
        '_id': str(ObjectId()),
        'platform': platform,
        'external_order_no': external_order_no,
        'store_ref': store_ref,
        'items': [{'external_id': ext_id, 'product_name': name,
                   'quantity': qty, 'unit_price': 60.0}],
        'delivery_fee': 30, 'payment_method': 'online', 'note': '',
    }


def _inv_qty(db, pid, wid):
    doc = db['inventory'].find_one(
        {'product_id': ObjectId(pid), 'warehouse_id': ObjectId(wid)})
    return doc['quantity'] if doc else None


# ─────────────────────────────────────────────────────────────
#  DeliveryMapping model
# ─────────────────────────────────────────────────────────────
class TestDeliveryMapping:
    def test_upsert_product_type(self, base_env):
        mid = DeliveryMapping.upsert('foodpanda', base_env['pid'], 'EXT-1', '珍珠')
        rows = DeliveryMapping.find_all(platform='foodpanda')
        assert len(rows) == 1 and rows[0]['_id'] == mid
        assert rows[0]['product_id'] == base_env['pid']

    def test_upsert_menu_item_type(self, base_env):
        item_id = base_env['item']['_id']
        DeliveryMapping.upsert('foodpanda', None, 'EXT-2',
                               menu_id=base_env['mid'], menu_item_id=item_id,
                               menu_item_name='珍珠奶茶')
        row = DeliveryMapping.find_all(platform='foodpanda')[0]
        assert row['menu_item_id'] == item_id
        assert row['menu_id'] == base_env['mid']
        assert row['product_id'] is None

    def test_upsert_requires_target(self):
        with pytest.raises(ValueError):
            DeliveryMapping.upsert('foodpanda', None, 'EXT-X')


# ─────────────────────────────────────────────────────────────
#  DeliverySettings：店家反查與有效設定
# ─────────────────────────────────────────────────────────────
class TestDeliverySettings:
    def test_find_store_by_external(self, base_env):
        sid = base_env['sid']
        DeliverySettings.upsert('foodpanda', store_ref=sid, vendor_code='V-123')
        assert DeliverySettings.find_store_by_external('foodpanda', 'V-123') == sid
        assert DeliverySettings.find_store_by_external('foodpanda', 'nope') is None
        assert DeliverySettings.find_store_by_external('foodpanda', '') is None

    def test_effective_merges_store_over_global(self, base_env):
        sid, wid = base_env['sid'], base_env['wid']
        gw = create_warehouse()
        DeliverySettings.upsert('foodpanda', auto_confirm=True,
                                default_warehouse_id=gw,
                                mapping_template_id='tpl-global')
        # 店家設定：有自己的倉，但沒設模板 → 模板回退全域
        DeliverySettings.upsert('foodpanda', store_ref=sid,
                                auto_confirm=False, default_warehouse_id=wid)
        eff = DeliverySettings.effective('foodpanda', store_ref=sid)
        assert eff['default_warehouse_id'] == wid          # 店家值優先
        assert eff['auto_confirm'] is False                # 布林以店家為準
        assert eff['mapping_template_id'] == 'tpl-global'  # 空值回退全域

    def test_effective_without_store_doc_falls_back_global(self, base_env):
        gw = create_warehouse()
        DeliverySettings.upsert('foodpanda', default_warehouse_id=gw)
        eff = DeliverySettings.effective('foodpanda', store_ref=base_env['sid'])
        assert eff['default_warehouse_id'] == gw


# ─────────────────────────────────────────────────────────────
#  DeliveryOrder：external_store_id → store_ref
# ─────────────────────────────────────────────────────────────
class TestOrderStoreResolution:
    def test_create_resolves_store_ref(self, base_env):
        sid = base_env['sid']
        DeliverySettings.upsert('foodpanda', store_ref=sid, vendor_code='V-9')
        oid = DeliveryOrder.create_from_normalized({
            'platform': 'foodpanda', 'external_order_id': 'X1',
            'external_store_id': 'V-9', 'items': [],
        })
        order = DeliveryOrder.find_by_id(oid)
        assert order['store_ref'] == sid
        assert order['external_store_id'] == 'V-9'

    def test_create_without_match_leaves_none(self):
        oid = DeliveryOrder.create_from_normalized({
            'platform': 'foodpanda', 'external_order_id': 'X2',
            'external_store_id': 'unknown', 'items': [],
        })
        assert DeliveryOrder.find_by_id(oid)['store_ref'] is None


# ─────────────────────────────────────────────────────────────
#  create_from_delivery：對應解析與扣庫存
# ─────────────────────────────────────────────────────────────
class TestCreateFromDelivery:
    def test_product_mapping_deducts_default_warehouse(self, db, base_env):
        from src.models.pos import PosOrder
        DeliveryMapping.upsert('foodpanda', base_env['pid'], 'I-1')
        r = PosOrder.create_from_delivery(_order_doc(qty=3), base_env['wid'], 'tester')
        assert r['success'] and not r['skipped_items']
        assert _inv_qty(db, base_env['pid'], base_env['wid']) == 97
        sale = db['pos_orders'].find_one({'_id': ObjectId(r['sale_id'])})
        assert str(sale['items'][0]['product_id']) == base_env['pid']

    def test_menu_item_mapping_uses_linked_products(self, db, base_env):
        """menu_item 對應：qty=3 × consume_qty=2 → 扣 6"""
        from src.models.pos import PosOrder
        DeliveryMapping.upsert('foodpanda', None, 'I-1',
                               menu_id=base_env['mid'],
                               menu_item_id=base_env['item']['_id'])
        r = PosOrder.create_from_delivery(_order_doc(qty=3), base_env['wid'], 'tester')
        assert r['success'] and not r['skipped_items']
        assert _inv_qty(db, base_env['pid'], base_env['wid']) == 94
        sale = db['pos_orders'].find_one({'_id': ObjectId(r['sale_id'])})
        assert sale['items'][0]['menu_item_id'] == base_env['item']['_id']
        # StockMovement 有記錄
        mv = db['stock_movements'].find_one({'reference_type': 'delivery_order'})
        assert mv and mv['quantity'] == -6

    def test_menu_item_cross_warehouse_multi_material(self, db, base_env):
        """品項連結兩原料、其中一個指定別倉 → 各自扣各自的倉"""
        from src.models.menu import Menu
        from src.models.pos import PosOrder
        wid2 = create_warehouse(store_id=base_env['sid'])
        pid2 = create_product(name='茶葉')
        seed_stock(pid2, wid2, 50)
        item2 = Menu.add_item(base_env['mid'], {
            'name': '雙料餐', 'price': 99,
            'linked_products': [
                {'product_id': base_env['pid'], 'warehouse_id': None, 'consume_qty': 1},
                {'product_id': pid2, 'warehouse_id': wid2, 'consume_qty': 3},
            ],
        })
        DeliveryMapping.upsert('foodpanda', None, 'I-1',
                               menu_id=base_env['mid'], menu_item_id=item2['_id'])
        r = PosOrder.create_from_delivery(
            _order_doc(qty=2, name='雙料餐'), base_env['wid'], 'tester')
        assert r['success'] and not r['skipped_items']
        assert _inv_qty(db, base_env['pid'], base_env['wid']) == 98   # 1×2，未指定倉→預設倉
        assert _inv_qty(db, pid2, wid2) == 44                          # 3×2，指定倉

    def test_name_mapping_from_settings(self, db, base_env):
        """名稱式對應：settings.item_mappings 指到菜單品項"""
        from src.models.pos import PosOrder
        settings = {'item_mappings': [{
            'platform_item_name': '珍珠奶茶',
            'system_items': [{'type': 'menu_item', 'menu_id': base_env['mid'],
                              'menu_item_id': base_env['item']['_id'], 'qty': 1}],
        }]}
        r = PosOrder.create_from_delivery(
            _order_doc(ext_id='NO-MAP', qty=1), base_env['wid'], 'tester',
            settings=settings)
        assert r['success'] and not r['skipped_items']
        assert _inv_qty(db, base_env['pid'], base_env['wid']) == 98  # consume_qty=2

    def test_name_mapping_falls_back_to_template(self, db, base_env):
        """settings 無 item_mappings 但綁模板 → 用模板內容（product 型，向下相容無 type）"""
        from src.models.pos import PosOrder
        tid = DeliveryMappingTemplate.create('T1', 'foodpanda', [{
            'platform_item_name': '珍珠奶茶',
            'system_items': [{'product_id': base_env['pid'], 'qty': 4}],
        }])
        r = PosOrder.create_from_delivery(
            _order_doc(ext_id='NO-MAP', qty=1), base_env['wid'], 'tester',
            settings={'item_mappings': [], 'mapping_template_id': tid})
        assert r['success'] and not r['skipped_items']
        assert _inv_qty(db, base_env['pid'], base_env['wid']) == 96  # qty 1 × 模板 qty 4

    def test_no_mapping_records_sale_without_deduction(self, db, base_env):
        from src.models.pos import PosOrder
        r = PosOrder.create_from_delivery(
            _order_doc(ext_id='NO-MAP', name='神秘品項'), base_env['wid'], 'tester')
        assert r['success'] and '神秘品項' in r['skipped_items']
        assert _inv_qty(db, base_env['pid'], base_env['wid']) == 100
        sale = db['pos_orders'].find_one({'_id': ObjectId(r['sale_id'])})
        assert sale['items'][0]['product_id'] is None

    def test_insufficient_stock_skips_deduction(self, db, base_env):
        from src.models.pos import PosOrder
        DeliveryMapping.upsert('foodpanda', base_env['pid'], 'I-1')
        r = PosOrder.create_from_delivery(_order_doc(qty=999), base_env['wid'], 'tester')
        assert r['success']
        assert any('庫存不足' in s for s in r['skipped_items'])
        assert _inv_qty(db, base_env['pid'], base_env['wid']) == 100

    def test_duplicate_returns_existing(self, base_env):
        from src.models.pos import PosOrder
        doc = _order_doc()
        r1 = PosOrder.create_from_delivery(doc, base_env['wid'], 'tester')
        r2 = PosOrder.create_from_delivery(doc, base_env['wid'], 'tester')
        assert r2.get('duplicate') and r2['sale_id'] == r1['sale_id']


# ─────────────────────────────────────────────────────────────
#  Webhook / 訂單狀態 API（store 專屬設定生效）
# ─────────────────────────────────────────────────────────────
class _StubClient:
    client_id = 'stub'
    api_key   = 'stub'

    def verify_webhook(self, payload, sig): return True
    def accept_order(self, *a, **k):        return True
    def confirm_order(self, *a, **k):       return True
    def deny_order(self, *a, **k):          return True
    def cancel_order(self, *a, **k):        return True


@pytest.fixture
def stub_clients(monkeypatch):
    stub = _StubClient()
    import app.delivery.views.webhooks as wh
    import app.delivery.views.orders as od
    monkeypatch.setattr(wh, '_get_ubereats_client',  lambda: stub)
    monkeypatch.setattr(wh, '_get_foodpanda_client', lambda: stub)
    monkeypatch.setattr(od, '_get_ubereats_client',  lambda: stub)
    monkeypatch.setattr(od, '_get_foodpanda_client', lambda: stub)
    return stub


class TestDeliveryApi:
    def _fp_payload(self, vendor_code='V-77', code='FP-XYZ'):
        return {
            'event': 'order.placed',
            'order': {
                'code': code,
                'vendor': {'code': vendor_code},
                'status': {'code': 'new'},
                'customer': {'first_name': '王', 'last_name': '小明'},
                'products': [{'id': 'I-1', 'name': '珍珠奶茶',
                              'quantity': 2, 'unit_price': 60}],
                'order_total': {'subtotal': 120, 'delivery_fee': 30,
                                'grand_total': 150},
            },
        }

    def test_webhook_auto_confirm_uses_store_settings(self, db, client, base_env,
                                                      stub_clients):
        """webhook 進單 → 依 vendor code 歸屬店家 → 用店家倉自動接單扣庫存"""
        sid, wid = base_env['sid'], base_env['wid']
        DeliverySettings.upsert('foodpanda', store_ref=sid, vendor_code='V-77',
                                auto_confirm=True, default_warehouse_id=wid)
        DeliveryMapping.upsert('foodpanda', None, 'I-1',
                               menu_id=base_env['mid'],
                               menu_item_id=base_env['item']['_id'])

        resp = client.post('/delivery/webhook/foodpanda', json=self._fp_payload())
        assert resp.status_code == 200

        order = DeliveryOrder.find_by_external('foodpanda', 'FP-XYZ')
        assert order['store_ref'] == sid
        assert order['status'] == DeliveryOrderStatus.CONFIRMED
        assert _inv_qty(db, base_env['pid'], wid) == 96  # 2 × consume_qty 2
        assert db['pos_orders'].count_documents({'source': 'foodpanda'}) == 1

    def test_webhook_no_auto_confirm_only_saves(self, db, client, base_env,
                                                stub_clients):
        DeliverySettings.upsert('foodpanda', store_ref=base_env['sid'],
                                vendor_code='V-77', auto_confirm=False,
                                default_warehouse_id=base_env['wid'])
        resp = client.post('/delivery/webhook/foodpanda', json=self._fp_payload())
        assert resp.status_code == 200
        order = DeliveryOrder.find_by_external('foodpanda', 'FP-XYZ')
        assert order['status'] == 'new'
        assert db['pos_orders'].count_documents({}) == 0

    def test_update_status_confirm_uses_store_warehouse(self, db, client, base_env,
                                                        stub_clients, make_headers):
        """手動 confirm：訂單歸屬店家 → 用店家設定倉扣庫存（非全域倉）"""
        sid, wid = base_env['sid'], base_env['wid']
        global_wid = create_warehouse()
        DeliverySettings.upsert('foodpanda', default_warehouse_id=global_wid)
        DeliverySettings.upsert('foodpanda', store_ref=sid, vendor_code='V-77',
                                default_warehouse_id=wid)
        DeliveryMapping.upsert('foodpanda', base_env['pid'], 'I-1')

        oid = DeliveryOrder.create_from_normalized({
            'platform': 'foodpanda', 'external_order_id': 'M1',
            'external_store_id': 'V-77',
            'items': [{'external_id': 'I-1', 'product_name': '珍珠',
                       'quantity': 5, 'unit_price': 60}],
        })
        resp = client.put(f'/delivery/orders/{oid}/status',
                          json={'status': 'confirmed'},
                          headers=make_headers('operator'))
        assert resp.status_code == 200
        assert _inv_qty(db, base_env['pid'], wid) == 95      # 店家倉被扣
        assert _inv_qty(db, base_env['pid'], global_wid) is None  # 全域倉沒動

    def test_create_mapping_api_menu_item(self, client, base_env, make_headers):
        resp = client.post('/delivery/mappings', json={
            'platform': 'foodpanda', 'external_product_id': 'E-9',
            'menu_id': base_env['mid'], 'menu_item_id': base_env['item']['_id'],
            'menu_item_name': '珍珠奶茶',
        }, headers=make_headers('operator'))
        assert resp.status_code == 201

    def test_create_mapping_api_rejects_both_targets(self, client, base_env,
                                                     make_headers):
        resp = client.post('/delivery/mappings', json={
            'platform': 'foodpanda', 'external_product_id': 'E-9',
            'product_id': base_env['pid'],
            'menu_id': base_env['mid'], 'menu_item_id': base_env['item']['_id'],
        }, headers=make_headers('operator'))
        assert resp.status_code == 400

    def test_store_settings_api_accepts_vendor_code(self, client, base_env,
                                                    make_headers):
        sid = base_env['sid']
        resp = client.put(f'/delivery/store/{sid}/settings/foodpanda',
                          json={'enabled': True, 'vendor_code': 'V-55'},
                          headers=make_headers('admin'))
        assert resp.status_code == 200
        assert DeliverySettings.find_store_by_external('foodpanda', 'V-55') == sid
