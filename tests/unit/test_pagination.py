"""[U3] 列表 offset 分頁：頁與頁不重疊、不漏；limit=0／負數不可變成「不限筆數」。"""
from helpers import create_product

from src.models.customer_order import CustomerOrder
from src.models.product import Product


def _ids(rows):
    return [r['_id'] for r in rows]


class TestProductOffsetApi:
    def test_pages_do_not_overlap_and_cover_all(self, client, admin_headers):
        for i in range(7):
            create_product(sku=f'PG-{i}')
        seen = []
        for off in (0, 3, 6):
            r = client.get(f'/product/?limit=3&offset={off}', headers=admin_headers)
            assert r.status_code == 200
            seen += _ids(r.get_json()['data'])
        assert len(seen) == 7 and len(set(seen)) == 7

    def test_offset_past_end_is_empty(self, client, admin_headers):
        create_product(sku='PG-END')
        r = client.get('/product/?limit=10&offset=50', headers=admin_headers)
        assert r.get_json()['data'] == []

    def test_negative_offset_treated_as_zero(self, client, admin_headers):
        create_product(sku='PG-NEG')
        r = client.get('/product/?offset=-5', headers=admin_headers)
        assert r.status_code == 200 and len(r.get_json()['data']) == 1

    def test_limit_zero_is_not_unlimited(self, client, admin_headers):
        for i in range(3):
            create_product(sku=f'PG-Z{i}')
        r = client.get('/product/?limit=0', headers=admin_headers)
        assert len(r.get_json()['data']) == 1

    def test_export_not_capped_by_list_limit(self):
        for i in range(3):
            create_product(sku=f'PG-X{i}')
        assert len(Product.find_all(limit=0)) == 3   # 匯出用 limit=0 取全部


class TestCustomerOrderOffsetModel:
    def test_offset_pages_stable(self):
        for i in range(5):
            CustomerOrder.create(table_no=f'T{i}', items=[], total=0)
        p1 = _ids(CustomerOrder.find_all(limit=2, offset=0))
        p2 = _ids(CustomerOrder.find_all(limit=2, offset=2))
        p3 = _ids(CustomerOrder.find_all(limit=2, offset=4))
        allp = p1 + p2 + p3
        assert len(allp) == 5 and len(set(allp)) == 5
