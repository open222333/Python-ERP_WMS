"""
[OPT-MEM] 記憶體優化相關回歸測試：
- 操作紀錄匯出改真串流，且修正原本只匯出 1 筆的 bug
- POS 銷售匯出改逐筆讀 cursor，只取需要的欄位，輸出內容不變
- 外送訂單列表排除 raw_payload，單筆詳情仍保留
"""
import csv
import io
import types
from datetime import datetime

from bson import ObjectId

from src.models.log import Log
from src.models.pos import PosOrder
from src.models.delivery import DeliveryOrder


def _csv_rows(resp):
    text = resp.get_data(as_text=True).lstrip('﻿')
    return list(csv.reader(io.StringIO(text)))


# ─────────────────────────────────────────────────────────────
#  操作紀錄匯出
# ─────────────────────────────────────────────────────────────
class TestLogExport:
    def test_iter_all_is_lazy_generator(self):
        assert isinstance(Log.iter_all(), types.GeneratorType)

    def test_export_returns_all_rows_not_just_one(self, client, operator_headers):
        """回歸：原本 find_all(limit=0) 被夾成 limit=1，匯出只有 1 筆。"""
        for i in range(5):
            Log.create(f'user{i}', '測試動作', f'detail {i}')
        resp = client.get('/log/export', headers=operator_headers)
        assert resp.status_code == 200
        rows = _csv_rows(resp)
        assert rows[0] == ['username', 'action', 'detail', 'success', 'created_at']
        assert len(rows) - 1 == 5

    def test_export_filters_still_apply(self, client, operator_headers):
        Log.create('alice', '登入', 'x')
        Log.create('bob', '登出', 'y')
        resp = client.get('/log/export?username=alice', headers=operator_headers)
        rows = _csv_rows(resp)
        assert [r[0] for r in rows[1:]] == ['alice']

    def test_export_bad_date_returns_400_before_streaming(self, client, operator_headers):
        resp = client.get('/log/export?start_date=not-a-date', headers=operator_headers)
        assert resp.status_code == 400

    def test_list_endpoint_limit_unchanged(self):
        for i in range(3):
            Log.create('u', 'a', str(i))
        assert len(Log.find_all(limit=2)) == 2


# ─────────────────────────────────────────────────────────────
#  POS 銷售匯出
# ─────────────────────────────────────────────────────────────
class TestPosExport:
    def _seed(self, db, n=3):
        now = datetime.utcnow()
        for i in range(n):
            db['pos_orders'].insert_one({
                'order_no': f'POS-{i:03d}', 'cashier': 'c1', 'warehouse_name': 'W',
                'items': [{'product_id': ObjectId(), 'product_name': '很長的品項名稱' * 5,
                           'quantity': 2, 'unit_price': 10,
                           'customizations_selected': [{'name': '加大'}]},
                          {'product_id': ObjectId(), 'product_name': 'B',
                           'quantity': 3, 'unit_price': 5}],
                'subtotal': 35, 'discount': 0, 'total_amount': 35,
                'payment_type': 'cash', 'cash_amount': 35, 'change_amount': 0,
                'status': 'completed', 'remark': '', 'created_at': now,
            })

    def test_iter_export_is_lazy_and_projects_fields(self, db):
        self._seed(db, 1)
        it = PosOrder.iter_export()
        assert isinstance(it, types.GeneratorType)
        row = next(it)
        # 只帶 quantity，不帶完整品項明細
        assert row['items'] == [{'quantity': 2}, {'quantity': 3}]
        assert row['source'] == 'pos'            # _fmt 預設值仍套用
        assert row['created_at'].endswith('Z')

    def test_export_csv_content(self, client, db, make_headers):
        self._seed(db, 3)
        resp = client.get('/pos/sales/export', headers=make_headers('cashier'))
        assert resp.status_code == 200
        rows = _csv_rows(resp)
        assert len(rows) - 1 == 3
        header = rows[0]
        first = dict(zip(header, rows[1]))
        assert first['items_count'] == '5'       # 2 + 3
        assert first['total_amount'] == '35'
        assert first['source'] == 'pos'

    def test_find_all_still_returns_full_items(self, db):
        self._seed(db, 1)
        item = PosOrder.find_all()[0]['items'][0]
        assert 'product_name' in item and 'unit_price' in item


# ─────────────────────────────────────────────────────────────
#  外送訂單列表
# ─────────────────────────────────────────────────────────────
class TestDeliveryListProjection:
    def test_list_excludes_raw_payload_detail_keeps_it(self):
        oid = DeliveryOrder.create_from_normalized({
            'platform': 'foodpanda', 'external_order_id': 'RAW-1', 'items': [],
            'raw': {'huge': 'x' * 5000},
        })
        listed = DeliveryOrder.find_all()
        assert len(listed) == 1
        assert 'raw_payload' not in listed[0]
        assert DeliveryOrder.find_by_id(oid)['raw_payload'] == {'huge': 'x' * 5000}
