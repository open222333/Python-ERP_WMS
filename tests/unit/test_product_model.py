"""Product model：CRUD / find_by_skus / find_by_ids / 批次操作。"""
import pytest
from bson import ObjectId

from src.models.product import Product
from helpers import create_product


class TestProductCreate:
    def test_create_requires_sku_and_name(self):
        with pytest.raises(ValueError):
            Product.create({'name': 'no-sku'})
        with pytest.raises(ValueError):
            Product.create({'sku': 'no-name'})

    def test_create_defaults_and_roundtrip(self):
        pid = Product.create({'sku': 'A-1', 'name': '蘋果', 'sell_price': '12.5'})
        p = Product.find_by_id(pid)
        assert p['sku'] == 'A-1'
        assert p['unit'] == '個'
        assert p['status'] == 1
        assert p['sell_price'] == 12.5
        assert p['cost_price'] == 0.0

    def test_create_invalid_category_id(self):
        with pytest.raises(ValueError):
            Product.create({'sku': 'X', 'name': 'X', 'category_id': 'bad-id'})


class TestProductFind:
    def test_find_by_id_invalid_format_raises(self):
        with pytest.raises(ValueError):
            Product.find_by_id('not-an-objectid')

    def test_find_by_id_missing_returns_none(self):
        assert Product.find_by_id(str(ObjectId())) is None

    def test_find_by_sku(self):
        create_product(sku='SKU-A')
        assert Product.find_by_sku('SKU-A')['sku'] == 'SKU-A'
        assert Product.find_by_sku('NOPE') is None

    def test_find_by_skus_batch(self):
        create_product(sku='S1')
        create_product(sku='S2')
        result = Product.find_by_skus(['S1', 'S2', 'MISSING'])
        assert set(result.keys()) == {'S1', 'S2'}
        assert result['S1']['sku'] == 'S1'
        assert Product.find_by_skus([]) == {}

    def test_find_by_ids_skips_invalid(self):
        pid = create_product()
        result = Product.find_by_ids([pid, 'garbage', None])
        assert set(result.keys()) == {pid}
        assert Product.find_by_ids(['garbage']) == {}

    def test_find_all_keyword_matches_name_sku_barcode(self):
        create_product(sku='COF-001', name='咖啡豆', barcode='471000')
        create_product(sku='TEA-001', name='紅茶')
        assert len(Product.find_all(keyword='咖啡')) == 1
        assert len(Product.find_all(keyword='cof')) == 1     # 不分大小寫
        assert len(Product.find_all(keyword='471000')) == 1
        assert len(Product.find_all(keyword='nothing')) == 0


class TestProductUpdateDelete:
    def test_update_fields(self):
        pid = create_product()
        assert Product.update(pid, {'name': '新名', 'sell_price': '99'}) is True
        p = Product.find_by_id(pid)
        assert p['name'] == '新名'
        assert p['sell_price'] == 99.0

    def test_update_bad_price_raises(self):
        pid = create_product()
        with pytest.raises(ValueError):
            Product.update(pid, {'sell_price': 'abc'})

    def test_delete(self):
        pid = create_product()
        assert Product.delete(pid) is True
        assert Product.find_by_id(pid) is None
        assert Product.delete(pid) is False

    def test_batch_update_and_delete(self):
        p1, p2 = create_product(), create_product()
        assert Product.batch_update([p1, p2, 'bad-id'], {'status': 0}) == 2
        assert Product.find_by_id(p1)['status'] == 0
        assert Product.batch_delete([p1, p2]) == 2
        assert Product.batch_delete([]) == 0
