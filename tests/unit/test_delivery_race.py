"""[A5] 外送訂單唯一索引：同平台同外部單號只能有一筆，並發建立時改走既有單。"""
import pytest
from pymongo.errors import DuplicateKeyError

from src.models.delivery import DeliveryOrder
from src.services import delivery_service


def _n(ext='FP-1', status='new'):
    return {'platform': 'foodpanda', 'external_order_id': ext, 'status': status, 'items': []}


def test_unique_index_blocks_duplicate(db):
    DeliveryOrder.create_from_normalized(_n())
    with pytest.raises(DuplicateKeyError):
        DeliveryOrder.create_from_normalized(_n())


def test_empty_external_id_not_constrained(db):
    DeliveryOrder.create_from_normalized(_n(ext=''))
    DeliveryOrder.create_from_normalized(_n(ext=''))
    assert db['delivery_orders'].count_documents({}) == 2


def test_ingest_race_falls_back_to_existing(db, monkeypatch):
    """模擬：查詢時對方還沒建好（查無），建立時對方已建好（撞唯一鍵）"""
    first, _, _ = delivery_service.ingest_normalized(_n())
    real = DeliveryOrder.find_by_external
    calls = {'n': 0}

    def flaky(platform, ext):
        calls['n'] += 1
        return None if calls['n'] == 1 else real(platform, ext)

    monkeypatch.setattr(DeliveryOrder, 'find_by_external', staticmethod(flaky))
    oid, is_new, info = delivery_service.ingest_normalized(_n(status='confirmed'))
    assert oid == first and is_new is False
    assert db['delivery_orders'].count_documents({}) == 1
    assert DeliveryOrder.find_by_id(first)['status'] == 'confirmed'
