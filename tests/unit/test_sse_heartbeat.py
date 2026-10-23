"""
[D5] SSE 心跳：資料沒變時也定期寫出 ': ping'，讓斷線可被偵測、釋放執行緒。
[A2] 廚房串流依 ticket 內的 store_ids 過濾：店家帳號只看本店訂單。
"""
import json

import pytest

import app.customer_order.view as cov
from src.models.customer_order import CustomerOrder
from src.models.sse_ticket import SseTicket
from helpers import create_store


class _FakeTime:
    """sleep 不真的等待，只推進虛擬時鐘"""
    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def sleep(self, s):
        self.now += s


@pytest.fixture
def fake_time(monkeypatch):
    ft = _FakeTime()
    monkeypatch.setattr(cov, 'time', ft)
    return ft


def _chunks(resp, n):
    it = iter(resp.response)
    out = []
    for _ in range(n):
        c = next(it)
        out.append(c.decode() if isinstance(c, bytes) else c)
    resp.close()
    return out


def _ticket(store_ids=None, role='operator'):
    return SseTicket.issue('kitchen', claims={'role': role, 'store_ids': store_ids or []})


def test_kitchen_stream_sends_heartbeat_when_idle(client, fake_time):
    resp = client.get(f'/customer-order/stream?ticket={_ticket()}', buffered=False)
    assert resp.status_code == 200
    chunks = _chunks(resp, 2)
    assert chunks[0].startswith('data: ')          # 第一次一定推送現況
    assert chunks[1] == ': ping\n\n'               # 之後資料沒變 → 心跳
    # 2 秒輪詢、15 秒心跳：第一個心跳應在 16 秒（第 8 次輪詢）時送出
    assert 15 <= fake_time.now - 1000.0 <= 18


def test_customer_stream_sends_heartbeat_when_idle(client, fake_time, monkeypatch):
    monkeypatch.setattr(cov.TableSession, 'get_by_token',
                        classmethod(lambda cls, t: {'table_no': 'T1'}))
    monkeypatch.setattr(cov.TableSession, 'is_closed', classmethod(lambda cls, t: False))
    resp = client.get('/customer-order/customer-stream?token=x', buffered=False)
    chunks = _chunks(resp, 2)
    assert chunks[0].startswith('event: order_update')
    assert chunks[1] == ': ping\n\n'


def test_kitchen_stream_filters_by_ticket_store(client, fake_time):
    sa, sb = create_store(), create_store()
    CustomerOrder.create('A1', [], 10, store_id=sa)
    CustomerOrder.create('B1', [], 10, store_id=sb)

    def tables(ticket):
        resp = client.get(f'/customer-order/stream?ticket={ticket}', buffered=False)
        data = json.loads(_chunks(resp, 1)[0][len('data: '):])
        return sorted(o['table_no'] for o in data['orders'])

    assert tables(_ticket([sa])) == ['A1']
    assert tables(_ticket([])) == ['A1', 'B1']           # 總部帳號看全部
