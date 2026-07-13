"""測試資料建立 helper（直接呼叫 model 層）。"""
import itertools

_seq = itertools.count(1)


def create_store(name=None, code=''):
    from src.models.store import Store
    n = next(_seq)
    return Store.create(name=name or f'Store{n}', code=code)


def create_warehouse(name=None, code=None, store_id=None):
    from src.models.warehouse import Warehouse
    n = next(_seq)
    return Warehouse.create(
        {'code': code or f'W{n:03d}', 'name': name or f'Warehouse{n}'},
        store_id=store_id,
    )


def create_product(sku=None, name=None, **extra):
    from src.models.product import Product
    n = next(_seq)
    data = {'sku': sku or f'SKU{n:04d}', 'name': name or f'Product{n}'}
    data.update(extra)
    return Product.create(data)


def create_menu(name=None, store_id=None):
    from src.models.menu import Menu
    n = next(_seq)
    return Menu.create(name=name or f'Menu{n}', store_id=store_id)


def seed_stock(product_id, warehouse_id, qty):
    from src.models.inventory import Inventory
    Inventory.set_quantity(product_id, warehouse_id, qty)
