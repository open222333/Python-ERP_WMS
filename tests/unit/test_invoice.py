"""
電子發票：
[A3] 防重複開立（唯一索引＋有效發票優先）
[A4] 店家 ECPay 設定生效、回退全域、機台覆寫、作廢必須同一商店代號
[D3] 折扣分攤：送出的品項合計必須等於發票金額
ECPay 以替身取代，不對外連線。
"""
from datetime import datetime

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

import src.invoice_providers.ecpay as ecpay_mod
from src.models.invoice import Invoice
from src.models.settings import SystemSettings
from helpers import create_store


class FakeECPay:
    calls = []
    next_rtn = 1

    def __init__(self, merchant_id, hash_key, hash_iv, seller_id='', test_mode=True):
        self.merchant_id = merchant_id

    def issue(self, **kw):
        FakeECPay.calls.append(('issue', self.merchant_id, kw))
        if FakeECPay.next_rtn != 1:
            return {'RtnCode': FakeECPay.next_rtn, 'RtnMsg': '測試失敗'}
        n = len(FakeECPay.calls)
        return {'RtnCode': 1, 'InvoiceNo': f'AB{n:08d}', 'RandomNumber': '1234',
                'InvoiceDate': '2026-10-24 12:00:00'}

    def void(self, **kw):
        FakeECPay.calls.append(('void', self.merchant_id, kw))
        return {'RtnCode': 1}


@pytest.fixture(autouse=True)
def fake_ecpay(monkeypatch):
    FakeECPay.calls, FakeECPay.next_rtn = [], 1
    monkeypatch.setattr(ecpay_mod, 'ECPayInvoice', FakeECPay)
    SystemSettings.set('invoice_settings', {'merchant_id': 'HQ001', 'hash_key': 'k', 'hash_iv': 'v'})
    return FakeECPay


@pytest.fixture
def store(db):
    return create_store('A店')


def _order(db, store_id, items=None, total=None, discount=0):
    items = items or [{'product_name': '大腸麵線（小）', 'quantity': 3, 'unit_price': 65},
                      {'product_name': '臭豆腐', 'quantity': 1, 'unit_price': 80}]
    sub = sum(i['quantity'] * i['unit_price'] for i in items)
    return str(db['pos_orders'].insert_one({
        'order_no': f'POS-{ObjectId()}', 'store_id': ObjectId(store_id), 'status': 'completed',
        'items': items, 'subtotal': sub, 'discount': discount,
        'total_amount': sub - discount if total is None else total,
        'created_at': datetime.utcnow()}).inserted_id)


def _issue(client, headers, oid, **extra):
    return client.post('/invoice/issue', headers=headers, json={'order_id': oid, **extra})


# ─────────────────────────────────────────────────────────────
#  [A3] 防重複開立
# ─────────────────────────────────────────────────────────────
class TestDuplicate:
    def test_second_issue_rejected(self, client, db, store, admin_headers):
        oid = _order(db, store)
        assert _issue(client, admin_headers, oid).status_code == 201
        r = _issue(client, admin_headers, oid)
        assert r.status_code == 400 and '已開立' in r.get_json()['message']
        assert len([c for c in FakeECPay.calls if c[0] == 'issue']) == 1

    def test_pending_blocks_with_409(self, client, db, store, admin_headers):
        oid = _order(db, store)
        Invoice.create(order_id=oid, order_no='X', total_amount=275, items=[])
        assert _issue(client, admin_headers, oid).status_code == 409
        assert FakeECPay.calls == []

    def test_unique_index_blocks_concurrent_create(self, db, store):
        oid = _order(db, store)
        Invoice.create(order_id=oid, order_no='X', total_amount=1, items=[])
        with pytest.raises(DuplicateKeyError):
            Invoice.create(order_id=oid, order_no='X', total_amount=1, items=[])

    def test_can_reissue_after_error(self, client, db, store, admin_headers):
        oid = _order(db, store)
        FakeECPay.next_rtn = 0
        assert _issue(client, admin_headers, oid).status_code == 400
        FakeECPay.next_rtn = 1
        assert _issue(client, admin_headers, oid).status_code == 201

    def test_find_by_order_prefers_issued_over_newer_voided(self, db, store):
        oid = _order(db, store)
        db['invoices'].insert_one({'order_id': oid, 'status': 'issued', 'invoice_no': 'OLD',
                                   'created_at': datetime(2026, 1, 1)})
        db['invoices'].insert_one({'order_id': oid, 'status': 'voided', 'invoice_no': 'NEW',
                                   'created_at': datetime(2026, 2, 1)})
        assert Invoice.find_by_order(oid)['invoice_no'] == 'OLD'


# ─────────────────────────────────────────────────────────────
#  [A4] 金鑰來源
# ─────────────────────────────────────────────────────────────
class TestMerchantResolution:
    def test_store_without_own_settings_falls_back_to_global(self, client, db, store, admin_headers):
        r = _issue(client, admin_headers, _order(db, store))
        assert r.status_code == 201
        assert FakeECPay.calls[-1][1] == 'HQ001'
        assert r.get_json()['data']['merchant_id'] == 'HQ001'
        assert r.get_json()['data']['store_id'] == store

    def test_store_settings_used_when_enabled(self, client, db, store, admin_headers):
        SystemSettings.set(f'invoice_settings_{store}',
                           {'enabled': True, 'merchant_id': 'ST001', 'hash_key': 'k', 'hash_iv': 'v'})
        assert _issue(client, admin_headers, _order(db, store)).status_code == 201
        assert FakeECPay.calls[-1][1] == 'ST001'

    def test_terminal_override(self, client, db, store, admin_headers):
        SystemSettings.set(f'invoice_settings_{store}', {
            'enabled': False, 'terminals': [{'id': 'T001', 'ecpay_override': {
                'merchant_id': 'TM001', 'hash_key': 'k', 'hash_iv': 'v'}}]})
        assert _issue(client, admin_headers, _order(db, store), terminal_id='T001').status_code == 201
        assert FakeECPay.calls[-1][1] == 'TM001'

    def test_void_uses_issuing_merchant_and_rejects_change(self, client, db, store, admin_headers):
        SystemSettings.set(f'invoice_settings_{store}',
                           {'enabled': True, 'merchant_id': 'ST001', 'hash_key': 'k', 'hash_iv': 'v'})
        inv = _issue(client, admin_headers, _order(db, store)).get_json()['data']
        # 店家改用別組商店代號後，舊發票不能用新金鑰作廢
        SystemSettings.set(f'invoice_settings_{store}',
                           {'enabled': True, 'merchant_id': 'ST999', 'hash_key': 'k', 'hash_iv': 'v'})
        r = client.post(f"/invoice/{inv['_id']}/void", headers=admin_headers, json={})
        assert r.status_code == 400 and 'ST001' in r.get_json()['message']
        SystemSettings.set(f'invoice_settings_{store}',
                           {'enabled': True, 'merchant_id': 'ST001', 'hash_key': 'k', 'hash_iv': 'v'})
        assert client.post(f"/invoice/{inv['_id']}/void", headers=admin_headers,
                           json={}).status_code == 200
        assert FakeECPay.calls[-1][:2] == ('void', 'ST001')

    def test_missing_config_returns_400_without_record(self, client, db, store, admin_headers):
        SystemSettings.set('invoice_settings', {})
        assert _issue(client, admin_headers, _order(db, store)).status_code == 400
        assert db['invoices'].count_documents({}) == 0


# ─────────────────────────────────────────────────────────────
#  [D3] 折扣分攤
# ─────────────────────────────────────────────────────────────
class TestDiscount:
    def test_items_sum_equals_sales_amount(self, client, db, store, admin_headers):
        oid = _order(db, store, discount=27.5)          # 小計 275，折後 247.5 → 248
        assert _issue(client, admin_headers, oid).status_code == 201
        kw = FakeECPay.calls[-1][2]
        assert kw['total'] == 248
        assert sum(i['ItemAmount'] for i in kw['items']) == 248
        assert all(i['ItemCount'] * i['ItemPrice'] == i['ItemAmount'] for i in kw['items'])

    def test_zero_amount_rejected(self, client, db, store, admin_headers):
        oid = _order(db, store, total=0)
        assert _issue(client, admin_headers, oid).status_code == 400
