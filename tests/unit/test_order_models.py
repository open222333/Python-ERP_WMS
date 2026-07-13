"""InboundOrder / OutboundOrder model：狀態機 pending → confirmed → completed / cancel。"""
import pytest

from src.models.inbound import InboundOrder
from src.models.outbound import OutboundOrder
from helpers import create_product, create_warehouse


@pytest.fixture
def wid():
    return create_warehouse()


@pytest.fixture
def pid():
    return create_product()


def _inbound(wid, pid, qty=5, price=2.0):
    oid = InboundOrder.create({'warehouse_id': wid, 'warehouse_name': 'W'})
    InboundOrder.add_item(oid, {'product_id': pid, 'expected_qty': qty,
                                'unit_price': price})
    return oid


def _outbound(wid, pid, qty=5, price=2.0):
    oid = OutboundOrder.create({'warehouse_id': wid, 'warehouse_name': 'W'})
    OutboundOrder.add_item(oid, {'product_id': pid, 'expected_qty': qty,
                                 'unit_price': price})
    return oid


class TestInboundOrder:
    def test_create_pending_with_order_no(self, wid):
        oid = InboundOrder.create({'warehouse_id': wid})
        o = InboundOrder.find_by_id(oid)
        assert o['status'] == 'pending'
        assert o['order_no'].startswith('IN')
        assert o['items'] == [] and o['total_amount'] == 0.0

    def test_order_no_sequence_increments(self, wid):
        o1 = InboundOrder.find_by_id(InboundOrder.create({'warehouse_id': wid}))
        o2 = InboundOrder.find_by_id(InboundOrder.create({'warehouse_id': wid}))
        assert int(o2['order_no'][-4:]) == int(o1['order_no'][-4:]) + 1

    def test_add_update_remove_item_recalcs_total(self, wid, pid):
        oid = _inbound(wid, pid, qty=5, price=2.0)
        assert InboundOrder.find_by_id(oid)['total_amount'] == 10.0
        item_id = InboundOrder.find_by_id(oid)['items'][0]['_id']
        InboundOrder.update_item(oid, item_id, {'expected_qty': 7})
        assert InboundOrder.find_by_id(oid)['total_amount'] == 14.0
        InboundOrder.remove_item(oid, item_id)
        o = InboundOrder.find_by_id(oid)
        assert o['items'] == [] and o['total_amount'] == 0.0

    def test_confirm_only_from_pending(self, wid, pid):
        oid = _inbound(wid, pid)
        assert InboundOrder.confirm(oid, 'op') is True
        assert InboundOrder.find_by_id(oid)['status'] == 'confirmed'
        assert InboundOrder.confirm(oid, 'op') is False   # 已 confirmed

    def test_add_item_refused_after_confirm(self, wid, pid):
        oid = _inbound(wid, pid)
        InboundOrder.confirm(oid, 'op')
        assert InboundOrder.add_item(oid, {'product_id': pid,
                                           'expected_qty': 1}) is False

    def test_complete_only_once(self, wid, pid):
        oid = _inbound(wid, pid, qty=5)
        InboundOrder.confirm(oid, 'op')
        done = InboundOrder.complete(oid, 'op')
        assert done['status'] == 'completed'
        assert done['items'][0]['received_qty'] == 5   # 預設帶 expected_qty
        assert InboundOrder.complete(oid, 'op') is None   # 第二次失敗

    def test_complete_from_pending_refused(self, wid, pid):
        oid = _inbound(wid, pid)
        assert InboundOrder.complete(oid, 'op') is None
        assert InboundOrder.find_by_id(oid)['status'] == 'pending'

    def test_complete_with_received_qtys_override(self, wid, pid):
        oid = _inbound(wid, pid, qty=5)
        item_id = InboundOrder.find_by_id(oid)['items'][0]['_id']
        InboundOrder.confirm(oid, 'op')
        done = InboundOrder.complete(oid, 'op', {item_id: 3})
        assert done['items'][0]['received_qty'] == 3

    def test_cancel_rules(self, wid, pid):
        # pending 可取消
        oid = _inbound(wid, pid)
        assert InboundOrder.cancel(oid, 'op') is True
        assert InboundOrder.find_by_id(oid)['status'] == 'cancelled'
        # confirmed 可取消
        oid2 = _inbound(wid, pid)
        InboundOrder.confirm(oid2, 'op')
        assert InboundOrder.cancel(oid2, 'op') is True
        # completed 不可取消
        oid3 = _inbound(wid, pid)
        InboundOrder.confirm(oid3, 'op')
        InboundOrder.complete(oid3, 'op')
        assert InboundOrder.cancel(oid3, 'op') is False
        assert InboundOrder.find_by_id(oid3)['status'] == 'completed'

    def test_update_basic_only_pending(self, wid, pid):
        oid = _inbound(wid, pid)
        assert InboundOrder.update_basic(oid, {'supplier': 'ACME'}) is True
        InboundOrder.confirm(oid, 'op')
        assert InboundOrder.update_basic(oid, {'supplier': 'x'}) is False

    def test_find_by_id_invalid_returns_none(self):
        assert InboundOrder.find_by_id('bad-id') is None


class TestOutboundOrder:
    def test_create_pending_with_order_no(self, wid):
        oid = OutboundOrder.create({'warehouse_id': wid})
        o = OutboundOrder.find_by_id(oid)
        assert o['status'] == 'pending'
        assert o['order_no'].startswith('OUT')

    def test_confirm_atomic_only_once(self, wid, pid):
        oid = _outbound(wid, pid)
        assert OutboundOrder.confirm(oid, 'op') is True
        assert OutboundOrder.confirm(oid, 'op') is False

    def test_complete_sets_shipped_qty_and_only_once(self, wid, pid):
        oid = _outbound(wid, pid, qty=4)
        OutboundOrder.confirm(oid, 'op')
        done = OutboundOrder.complete(oid, 'op')
        assert done['status'] == 'completed'
        assert done['items'][0]['shipped_qty'] == 4
        assert OutboundOrder.complete(oid, 'op') is None

    def test_complete_from_pending_refused(self, wid, pid):
        oid = _outbound(wid, pid)
        assert OutboundOrder.complete(oid, 'op') is None

    def test_cancel_completed_refused(self, wid, pid):
        oid = _outbound(wid, pid)
        OutboundOrder.confirm(oid, 'op')
        OutboundOrder.complete(oid, 'op')
        assert OutboundOrder.cancel(oid, 'op') is False

    def test_find_all_limit_offset(self, wid):
        ids = [OutboundOrder.create({'warehouse_id': wid}) for _ in range(3)]
        all_rows = OutboundOrder.find_all()
        assert len(all_rows) == 3
        page = OutboundOrder.find_all(limit=2, offset=1)
        assert len(page) == 2
        # offset=1 應跳過排序後（created_at 倒序）第一筆
        assert [r['_id'] for r in page] == [r['_id'] for r in all_rows[1:3]]

    def test_find_all_status_filter(self, wid, pid):
        o1 = _outbound(wid, pid)
        _outbound(wid, pid)
        OutboundOrder.confirm(o1, 'op')
        assert len(OutboundOrder.find_all(status='confirmed')) == 1
        assert len(OutboundOrder.find_all(status='pending')) == 1
