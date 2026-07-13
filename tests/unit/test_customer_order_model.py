"""CustomerOrder model：建立 / find_active limit / 狀態更新 / 統計。"""
from bson import ObjectId

from src.models.customer_order import CustomerOrder


def _order(table='T1', total=100.0, store_id=None):
    return CustomerOrder.create(
        table_no=table,
        items=[{'item_id': 'i1', 'item_name': '牛肉麵', 'qty': 1, 'price': total}],
        total=total,
        store_id=store_id,
    )


class TestCreate:
    def test_create_defaults(self):
        sid = str(ObjectId())
        oid = _order(store_id=sid)
        o = CustomerOrder.find_by_id(oid)
        assert o['status'] == 'pending'
        assert o['table_no'] == 'T1'
        assert o['store_id'] == sid
        assert o['order_no'].endswith('-0001')

    def test_order_no_daily_sequence(self):
        o1 = CustomerOrder.find_by_id(_order())
        o2 = CustomerOrder.find_by_id(_order())
        assert o1['order_no'].endswith('-0001')
        assert o2['order_no'].endswith('-0002')


class TestFindActive:
    def test_only_pending_and_processing_fifo(self):
        o1 = _order('T1')
        o2 = _order('T2')
        o3 = _order('T3')
        CustomerOrder.update_status(o2, 'processing')
        CustomerOrder.update_status(o3, 'completed')
        active = CustomerOrder.find_active()
        assert [a['_id'] for a in active] == [o1, o2]   # 先進先出

    def test_limit_respected(self):
        for _ in range(5):
            _order()
        assert len(CustomerOrder.find_active(limit=3)) == 3

    def test_store_filter(self):
        sid_a, sid_b = ObjectId(), ObjectId()
        _order(store_id=str(sid_a))
        _order(store_id=str(sid_b))
        rows = CustomerOrder.find_active(store_filter={'store_id': sid_a})
        assert len(rows) == 1


class TestUpdateStatus:
    def test_valid_status_appends_log(self):
        oid = _order()
        assert CustomerOrder.update_status(oid, 'processing', 'chef') is True
        o = CustomerOrder.find_by_id(oid)
        assert o['status'] == 'processing'
        assert o['handled_by'] == 'chef'
        assert o['status_log'][-1]['status'] == 'processing'

    def test_invalid_status_rejected(self):
        oid = _order()
        assert CustomerOrder.update_status(oid, 'shipped') is False
        assert CustomerOrder.find_by_id(oid)['status'] == 'pending'

    def test_unknown_id_returns_false(self):
        assert CustomerOrder.update_status(str(ObjectId()), 'completed') is False


class TestQueriesAndStats:
    def test_find_all_status_filter(self):
        o1 = _order()
        _order()
        CustomerOrder.update_status(o1, 'completed')
        assert len(CustomerOrder.find_all(status='completed')) == 1
        assert len(CustomerOrder.find_all()) == 2

    def test_today_stats_aggregation(self):
        o1 = _order(total=100.0)
        _order(total=50.0)
        CustomerOrder.update_status(o1, 'completed')
        stats = CustomerOrder.today_stats()
        assert stats['completed'] == {'count': 1, 'total': 100.0}
        assert stats['pending'] == {'count': 1, 'total': 50.0}
        assert stats['cancelled'] == {'count': 0, 'total': 0.0}
