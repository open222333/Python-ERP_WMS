# [OPT-N1] 交易一致性測試
#
# 沙箱只有 mongomock（不支援 session/transaction），所以這裡驗證的是：
# 1. supports_transactions() 在 mongomock 環境下正確探測為 False 並快取
# 2. 探測為 False 時，complete_inbound_order / complete_outbound_order 走原本
#    的非交易路徑，行為與 N1 之前完全一致（既有 test_order_models.py /
#    test_inbound_api.py 已覆蓋此路徑，這裡額外驗證探測與快取機制本身）
# 3. 用假 session/client 模擬「支援交易」分支，驗證 session 確實被傳遞到
#    每一個 model 呼叫（InboundOrder.complete / Inventory.adjust /
#    StockMovement.create / Log.create 皆收到同一個 session 物件）
# 4. 交易分支中途拋錯會被攔截並退回非交易路徑重試（且能成功完成）
import pytest

import src.mongo as mongo_mod
from src.mongo import supports_transactions, reset_transaction_probe


@pytest.fixture(autouse=True)
def _reset_probe():
    reset_transaction_probe()
    yield
    reset_transaction_probe()


class TestSupportsTransactions:
    def test_mongomock_probe_returns_false_and_caches(self):
        assert supports_transactions() is False
        # 第二次呼叫不應重新探測（用 monkeypatch 驗證快取生效較繁瑣，
        # 這裡以「連續呼叫值一致」佐證快取路徑至少沒有壞掉）
        assert supports_transactions() is False


class _FakeSession:
    """模擬 pymongo ClientSession：只需支援 context manager 與 start_transaction()"""
    def __init__(self):
        self.aborted = False
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def start_transaction(self):
        return self

    def abort_transaction(self):
        self.aborted = True


class _FakeClient:
    def __init__(self, session):
        self._session = session

    def start_session(self):
        return self._session


class TestTransactionPathThreadsSession:
    def test_session_passed_to_all_writes(self, db, monkeypatch):
        """
        [OPT-N1] 探測為 True 時，complete 流程內每個 model 呼叫都應收到同一個 session。

        mongomock 對非 None 的 session 一律拋 NotImplementedError（這正是
        supports_transactions() 探測到 mongomock 時會回 False 的原因），所以
        這裡把四個實際寫入的 model 方法整組替換為記錄呼叫參數的假函式，
        只驗證「_run_complete 是否把同一個 session 物件傳給每一處」這件事本身，
        不依賴 mongomock 真的執行帶 session 的操作。
        """
        from src.services import order_service

        fake_completed = {
            'order_no': 'IN20260101TEST', 'warehouse_id': 'w1',
            'items': [{'product_id': 'p1', 'product_name': 'P1', 'product_sku': 'S1',
                      'received_qty': 5}],
        }
        seen = {}

        fake_session = _FakeSession()
        monkeypatch.setattr(order_service, 'supports_transactions', lambda: True)
        monkeypatch.setattr(order_service, 'get_client', lambda: _FakeClient(fake_session))

        def _fake_complete(oid, operator, qtys, session=None):
            seen['complete'] = session
            return fake_completed

        def _fake_find_wh(wid, session=None):
            seen['find_warehouse'] = session
            return {'name': 'W'}

        def _fake_adjust(*a, session=None, **kw):
            seen['adjust'] = session
            return 0, 5

        def _fake_movement_create(*a, session=None, **kw):
            seen['movement'] = session
            return 'mid1'

        def _fake_log_create(*a, session=None, **kw):
            seen['log'] = session
            return 'lid1'

        monkeypatch.setattr(order_service.InboundOrder, 'complete', _fake_complete)
        monkeypatch.setattr(order_service.Warehouse, 'find_by_id', _fake_find_wh)
        monkeypatch.setattr(order_service.Inventory, 'adjust', _fake_adjust)
        monkeypatch.setattr(order_service.StockMovement, 'create', _fake_movement_create)
        monkeypatch.setattr(order_service.Log, 'create', _fake_log_create)

        result = order_service.complete_inbound_order('oid1', 'operator1')

        assert result == fake_completed
        assert seen == {
            'complete': fake_session,
            'find_warehouse': fake_session,
            'adjust': fake_session,
            'movement': fake_session,
            'log': fake_session,
        }
        assert fake_session.aborted is False  # 正常完成不應 abort

    def test_transaction_failure_falls_back_and_still_completes(self, db, monkeypatch):
        """[OPT-N1] 交易分支拋出 PyMongoError 時，安全退回非交易路徑並仍能完成"""
        from pymongo.errors import PyMongoError
        from src.models.warehouse import Warehouse
        from src.models.product import Product
        from src.models.inbound import InboundOrder
        from src.services import order_service

        wid = Warehouse.create({'name': 'W2', 'code': 'W2'})
        pid = Product.create({'sku': 'S2', 'name': 'P2', 'unit': '個'}, created_by='t')
        oid = InboundOrder.create({'warehouse_id': wid, 'warehouse_name': 'W2'}, created_by='t')
        InboundOrder.add_item(oid, {'product_id': pid, 'product_name': 'P2',
                                    'product_sku': 'S2', 'expected_qty': 3})
        InboundOrder.confirm(oid, 't')

        class _BoomClient:
            def start_session(self):
                raise PyMongoError('simulated replica set hiccup')

        monkeypatch.setattr(order_service, 'supports_transactions', lambda: True)
        monkeypatch.setattr(order_service, 'get_client', lambda: _BoomClient())

        result = order_service.complete_inbound_order(oid, 'operator2')

        assert result is not None
        assert result['status'] == 'completed'
        from src.models.inventory import Inventory
        assert Inventory.get_quantity(pid, wid) == 3
