"""Inventory / StockMovement model：adjust 原子性、不可為負、移動紀錄。"""
import pytest
from datetime import datetime, timedelta

from src.models.inventory import Inventory, StockMovement
from helpers import create_product, create_warehouse


@pytest.fixture
def ids():
    return create_product(), create_warehouse()


class TestInventoryAdjust:
    def test_adjust_creates_record(self, ids):
        pid, wid = ids
        before, after = Inventory.adjust(pid, wid, 10)
        assert (before, after) == (0, 10)
        assert Inventory.get_quantity(pid, wid) == 10

    def test_adjust_increments_existing(self, ids):
        pid, wid = ids
        Inventory.adjust(pid, wid, 10)
        before, after = Inventory.adjust(pid, wid, -4)
        assert (before, after) == (10, 6)
        assert Inventory.get_quantity(pid, wid) == 6

    def test_adjust_cannot_go_negative(self, ids):
        pid, wid = ids
        Inventory.adjust(pid, wid, 5)
        with pytest.raises(ValueError):
            Inventory.adjust(pid, wid, -6)
        # 扣減被 rollback，庫存維持原值
        assert Inventory.get_quantity(pid, wid) == 5

    def test_adjust_negative_on_new_record_raises(self, ids):
        pid, wid = ids
        with pytest.raises(ValueError):
            Inventory.adjust(pid, wid, -1)
        assert Inventory.get_quantity(pid, wid) == 0

    def test_set_quantity_returns_before_after(self, ids):
        pid, wid = ids
        assert Inventory.set_quantity(pid, wid, 100) == (0, 100)
        assert Inventory.set_quantity(pid, wid, 30) == (100, 30)

    def test_get_quantity_default_zero(self, ids):
        pid, wid = ids
        assert Inventory.get_quantity(pid, wid) == 0

    def test_find_one_and_find_all(self, ids):
        pid, wid = ids
        Inventory.adjust(pid, wid, 7)
        doc = Inventory.find_one(pid, wid)
        assert doc['quantity'] == 7
        assert doc['product_id'] == pid
        rows = Inventory.find_all(warehouse_id=wid)
        assert len(rows) == 1


class TestStockMovement:
    def test_create_and_find(self, ids):
        pid, wid = ids
        StockMovement.create(pid, wid, 'inbound', 5, 0, 5,
                             product_name='P', warehouse_name='W',
                             reference_type='inbound_order', reference_id='x')
        rows = StockMovement.find_all(warehouse_id=wid)
        assert len(rows) == 1
        assert rows[0]['movement_type'] == 'inbound'
        assert rows[0]['movement_label'] == '入庫'
        assert rows[0]['before_qty'] == 0 and rows[0]['after_qty'] == 5

    def test_product_only_excludes_menu_ref_types(self, ids):
        pid, wid = ids
        StockMovement.create(pid, wid, 'outbound', -1, 5, 4,
                             reference_type='pos_order')
        StockMovement.create(pid, wid, 'inbound', 5, 0, 5,
                             reference_type='inbound_order')
        assert len(StockMovement.find_all(product_only=False)) == 2
        rows = StockMovement.find_all(product_only=True)
        assert len(rows) == 1
        assert rows[0]['reference_type'] == 'inbound_order'

    def test_filter_by_movement_type(self, ids):
        pid, wid = ids
        StockMovement.create(pid, wid, 'adjust', 3, 0, 3)
        StockMovement.create(pid, wid, 'inbound', 2, 3, 5)
        rows = StockMovement.find_all(movement_type='adjust')
        assert len(rows) == 1 and rows[0]['movement_type'] == 'adjust'

    def test_cleanup_old(self, ids, db):
        pid, wid = ids
        StockMovement.create(pid, wid, 'adjust', 1, 0, 1)
        # 造一筆 10 天前的舊紀錄
        old_id = StockMovement.create(pid, wid, 'adjust', 1, 1, 2)
        db['stock_movements'].update_one(
            {'_id': __import__('bson').ObjectId(old_id)},
            {'$set': {'created_at': datetime.utcnow() - timedelta(days=10)}})
        assert StockMovement.cleanup_old(0) == 0    # 0 = 不清
        assert StockMovement.cleanup_old(7) == 1
        assert len(StockMovement.find_all()) == 1
