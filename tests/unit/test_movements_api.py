"""GET /inventory/movement/：日期區間篩選（原本前端有送、後端忽略）與回傳欄位名稱。"""
from datetime import datetime

from bson import ObjectId

from src.models.inventory import StockMovement
from helpers import create_product, create_warehouse


def _mv(db, pid, wid, when, qty=5):
    mid = StockMovement.create(product_id=pid, warehouse_id=wid, movement_type='inbound',
                               quantity=qty, before_qty=0, after_qty=qty,
                               product_name='珍珠', product_sku='SKU-PEARL')
    db['stock_movements'].update_one({'_id': ObjectId(mid)}, {'$set': {'created_at': when}})
    return mid


def test_date_range_filter(client, db, operator_headers):
    pid, wid = create_product(), create_warehouse()
    _mv(db, pid, wid, datetime(2026, 10, 1, 12))
    keep = _mv(db, pid, wid, datetime(2026, 10, 15, 23, 59))   # 迄日當天最後一分鐘也要含入
    _mv(db, pid, wid, datetime(2026, 10, 16, 0, 1))

    r = client.get('/inventory/movement/?date_from=2026-10-10&date_to=2026-10-15',
                   headers=operator_headers)
    assert r.status_code == 200
    assert [m['_id'] for m in r.get_json()['data']] == [keep]


def test_bad_date_returns_400(client, operator_headers):
    r = client.get('/inventory/movement/?date_from=2026/10/10', headers=operator_headers)
    assert r.status_code == 400


def test_response_field_names_used_by_frontend(client, db, operator_headers):
    """MovementsView 讀 product_sku / before_qty / after_qty（原本讀錯名稱導致欄位空白）"""
    pid, wid = create_product(), create_warehouse()
    _mv(db, pid, wid, datetime(2026, 10, 1))
    m = client.get('/inventory/movement/', headers=operator_headers).get_json()['data'][0]
    assert m['product_sku'] == 'SKU-PEARL'
    assert m['before_qty'] == 0 and m['after_qty'] == 5
