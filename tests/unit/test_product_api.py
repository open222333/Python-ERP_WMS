"""Product API：CRUD、重複 SKU、/batch route 順序（batch 不可被當作 pid）。"""
from bson import ObjectId

from helpers import create_product


class TestProductCrudApi:
    def test_create_201(self, client, operator_headers):
        r = client.post('/product/', headers=operator_headers,
                        json={'sku': 'API-1', 'name': '測試品'})
        assert r.status_code == 201
        assert ObjectId.is_valid(r.get_json()['id'])

    def test_create_duplicate_sku_409(self, client, operator_headers):
        create_product(sku='DUP-1')
        r = client.post('/product/', headers=operator_headers,
                        json={'sku': 'DUP-1', 'name': 'x'})
        assert r.status_code == 409

    def test_create_missing_fields_400(self, client, operator_headers):
        r = client.post('/product/', headers=operator_headers,
                        json={'name': 'no sku'})
        assert r.status_code == 400

    def test_get_list_and_keyword(self, client, admin_headers):
        create_product(sku='KW-COFFEE', name='咖啡')
        create_product(sku='KW-TEA', name='茶')
        r = client.get('/product/?keyword=咖啡', headers=admin_headers)
        data = r.get_json()['data']
        assert len(data) == 1 and data[0]['name'] == '咖啡'

    def test_get_missing_product_404(self, client, admin_headers):
        r = client.get(f'/product/{ObjectId()}', headers=admin_headers)
        assert r.status_code == 404

    def test_update_and_delete(self, client, admin_headers):
        pid = create_product()
        r = client.put(f'/product/{pid}', headers=admin_headers,
                       json={'name': '改名'})
        assert r.status_code == 200
        r = client.delete(f'/product/{pid}', headers=admin_headers)
        assert r.status_code == 200
        assert client.get(f'/product/{pid}',
                          headers=admin_headers).status_code == 404

    def test_get_by_barcode(self, client, admin_headers):
        create_product(barcode='4710001')
        r = client.get('/product/barcode/4710001', headers=admin_headers)
        assert r.status_code == 200
        assert r.get_json()['data']['barcode'] == '4710001'
        assert client.get('/product/barcode/0000',
                          headers=admin_headers).status_code == 404


class TestBatchRouteOrder:
    """CLAUDE.md：/batch 必須在 /<pid> 之前註冊，否則 'batch' 會被當作 pid。"""

    def test_batch_update_not_treated_as_pid(self, client, operator_headers):
        p1, p2 = create_product(), create_product()
        r = client.put('/product/batch', headers=operator_headers,
                       json={'ids': [p1, p2], 'status': 0})
        assert r.status_code == 200
        assert r.get_json()['updated'] == 2
        from src.models.product import Product
        assert Product.find_by_id(p1)['status'] == 0

    def test_batch_update_disallowed_fields_filtered(self, client,
                                                     operator_headers):
        p1 = create_product(sku='KEEP-SKU')
        r = client.put('/product/batch', headers=operator_headers,
                       json={'ids': [p1], 'sku': 'HACKED'})
        assert r.status_code == 400   # sku 不在白名單 → 無更新欄位
        from src.models.product import Product
        assert Product.find_by_id(p1)['sku'] == 'KEEP-SKU'

    def test_batch_delete(self, client, admin_headers):
        p1, p2 = create_product(), create_product()
        r = client.delete('/product/batch', headers=admin_headers,
                          json={'ids': [p1, p2]})
        assert r.status_code == 200
        assert r.get_json()['deleted'] == 2

    def test_batch_empty_ids_400(self, client, operator_headers):
        r = client.put('/product/batch', headers=operator_headers,
                       json={'ids': [], 'status': 0})
        assert r.status_code == 400


class TestCategoryApi:
    def test_category_crud(self, client, operator_headers, admin_headers):
        r = client.post('/product/category/', headers=operator_headers,
                        json={'name': '飲料'})
        assert r.status_code == 201
        cid = r.get_json()['id']
        r = client.put(f'/product/category/{cid}', headers=operator_headers,
                       json={'name': '飲品'})
        assert r.status_code == 200
        r = client.get('/product/category/', headers=operator_headers)
        assert r.get_json()['data'][0]['name'] == '飲品'
        assert client.delete(f'/product/category/{cid}',
                             headers=admin_headers).status_code == 200

    def test_category_empty_name_400(self, client, operator_headers):
        r = client.post('/product/category/', headers=operator_headers,
                        json={'name': '  '})
        assert r.status_code == 400
