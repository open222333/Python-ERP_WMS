# [REFACTOR] pydantic 驗證層測試：確認畸形輸入回 400（原本部分情境會 500）
import pytest


class TestSchemaBase:
    def test_object_id_lenient(self):
        from src.schemas.base import _check_object_id_lenient
        assert _check_object_id_lenient('') == ''
        assert _check_object_id_lenient(None) is None
        assert _check_object_id_lenient('0' * 24) == '0' * 24
        with pytest.raises(ValueError):
            _check_object_id_lenient('not-an-oid')

    def test_validate_payload_error_shape(self, app):
        from src.schemas.base import validate_payload
        from src.schemas.domain import ProductPayload
        with app.app_context():
            model, err = validate_payload(ProductPayload, {'price': 'abc'})
            assert model is None
            resp, code = err
            assert code == 400
            body = resp.get_json()
            assert body['success'] is False
            assert body['errors'] and body['errors'][0]['field'] == 'price'


class TestCustomerOrderValidation:
    def test_non_numeric_price_returns_400_not_500(self, client):
        # 原本 float('abc') 會拋 ValueError → 500
        r = client.post('/customer-order/', json={
            'table_no': 'T1',
            'items': [{'item_name': 'A', 'qty': 1, 'price': 'abc'}],
        })
        assert r.status_code == 400
        assert r.get_json()['success'] is False

    def test_valid_order_still_works(self, client):
        r = client.post('/customer-order/', json={
            'table_no': 'T1',
            'items': [{'item_name': 'A', 'qty': 1, 'price': 50}],
        })
        assert r.status_code in (200, 201)


class TestOrderValidation:
    def test_create_inbound_invalid_warehouse_oid_400(self, client, admin_headers):
        # 原本非法 ObjectId 進 Warehouse.find_by_id 會拋例外 → 500
        r = client.post('/inbound/', json={'warehouse_id': 'bad-oid'},
                        headers=admin_headers)
        assert r.status_code == 400

    def test_add_item_string_qty_400(self, client, admin_headers):
        w = client.post('/warehouse/', json={'name': 'W1', 'code': 'W1'},
                        headers=admin_headers).get_json()
        p = client.post('/product/', json={'sku': 'SKU-T', 'name': 'P1', 'unit': '個'},
                        headers=admin_headers).get_json()
        seed_warehouse, seed_product = w['id'], p['id']
        r = client.post('/inbound/', json={'warehouse_id': seed_warehouse},
                        headers=admin_headers)
        oid = r.get_json()['id']
        # 原本字串 qty 與 0 比較會 TypeError → 500
        r2 = client.post(f'/inbound/{oid}/item',
                         json={'product_id': seed_product, 'expected_qty': 'many'},
                         headers=admin_headers)
        assert r2.status_code == 400


class TestProductValidation:
    def test_create_product_bad_price_400(self, client, admin_headers):
        r = client.post('/product/', json={'sku': 'S1', 'name': 'N', 'price': 'cheap'},
                        headers=admin_headers)
        assert r.status_code == 400

    def test_create_product_bad_category_oid_400(self, client, admin_headers):
        r = client.post('/product/', json={'sku': 'S2', 'name': 'N', 'category_id': 'xx'},
                        headers=admin_headers)
        assert r.status_code == 400


class TestInventoryValidation:
    def test_adjust_bad_quantity_400(self, client, admin_headers):
        r = client.post('/inventory/adjust',
                        json={'product_id': '0' * 24, 'warehouse_id': '0' * 24,
                              'quantity': 'lots'},
                        headers=admin_headers)
        assert r.status_code == 400
