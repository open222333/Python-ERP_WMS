"""PosOrder.summary aggregation 統計。

mongomock 4.3.0 不支援 $dateToString 的 onNull 參數
（NotImplementedError: "Although onNull is a valid field for the
$dateToString operator, it is currently not implemented in Mongomock."），
而 PosOrder.summary 的 pipeline 使用了 onNull，故整組測試 skip。
重構後若改用真實 MongoDB 整合測試，應恢復驗證以下行為：
- total_orders / total_amount / total_discount 加總正確
- cash_total 只計 payment_type in (cash, mixed) 的 cash_amount
- card_total 只計 payment_type in (card, mixed) 的 card_amount
- granularity='day'/'month' 的 breakdown period 格式與排序
- status 過濾（預設只統計 completed）
- store_filter 多店家隔離
"""
from datetime import datetime

import pytest

SKIP_REASON = ('mongomock 不支援 $dateToString 的 onNull 參數'
               '（PosOrder.summary pipeline 使用 onNull，執行即拋 NotImplementedError）')


@pytest.mark.skip(reason=SKIP_REASON)
def test_summary_totals_and_breakdown(db):
    from src.models.pos import PosOrder
    db['pos_orders'].insert_many([
        {'created_at': datetime(2026, 1, 2), 'status': 'completed',
         'total_amount': 100, 'discount': 10,
         'payment_type': 'cash', 'cash_amount': 100, 'card_amount': 0},
        {'created_at': datetime(2026, 1, 3), 'status': 'completed',
         'total_amount': 200, 'discount': 0,
         'payment_type': 'card', 'cash_amount': 0, 'card_amount': 200},
    ])
    r = PosOrder.summary(datetime(2026, 1, 1), datetime(2026, 2, 1))
    assert r['total_orders'] == 2
    assert r['total_amount'] == 300
    assert r['cash_total'] == 100
    assert r['card_total'] == 200
    assert [b['period'] for b in r['breakdown']] == ['2026-01-02', '2026-01-03']


@pytest.mark.skip(reason=SKIP_REASON)
def test_summary_status_filter_excludes_refunded(db):
    from src.models.pos import PosOrder
    db['pos_orders'].insert_many([
        {'created_at': datetime(2026, 1, 2), 'status': 'completed',
         'total_amount': 100, 'payment_type': 'cash', 'cash_amount': 100},
        {'created_at': datetime(2026, 1, 2), 'status': 'refunded',
         'total_amount': 999, 'payment_type': 'cash', 'cash_amount': 999},
    ])
    r = PosOrder.summary(datetime(2026, 1, 1), datetime(2026, 2, 1))
    assert r['total_orders'] == 1
    assert r['total_amount'] == 100
