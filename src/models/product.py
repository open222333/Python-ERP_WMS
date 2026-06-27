import logging
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from src.mongo import get_db

logger = logging.getLogger(__name__)


def _fmt(doc) -> dict:
    """將 MongoDB document 轉為可序列化 dict"""
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['_id'] = str(doc['_id'])
    if 'category_id' in d and d['category_id']:
        d['category_id'] = str(d['category_id'])
    if 'parent_id' in d and d['parent_id']:
        d['parent_id'] = str(d['parent_id'])
    return d


# ─────────────────────────────────────────────────────────────
#  產品分類
# ─────────────────────────────────────────────────────────────
class ProductCategory:
    COLLECTION = 'product_categories'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_all(cls) -> list:
        try:
            docs = cls._col().find({}).sort([('sort_order', 1), ('_id', 1)])
            return [_fmt(d) for d in docs]
        except Exception:
            logger.error('ProductCategory.find_all 查詢失敗', exc_info=True)
            raise

    @classmethod
    def find_by_id(cls, cid: str) -> dict:
        try:
            oid = ObjectId(cid)
        except InvalidId:
            raise ValueError(f'分類 ID 格式無效: {cid!r}')
        try:
            return _fmt(cls._col().find_one({'_id': oid}))
        except Exception:
            logger.error(f'ProductCategory.find_by_id 查詢失敗 cid={cid}', exc_info=True)
            raise

    @classmethod
    def create(cls, name: str, parent_id: str = None, description: str = '',
               sort_order: int = None) -> str:
        try:
            parent_oid = ObjectId(parent_id) if parent_id else None
        except InvalidId:
            raise ValueError(f'父分類 ID 格式無效: {parent_id!r}')
        if sort_order is None:
            last = cls._col().find_one({}, sort=[('sort_order', -1)])
            sort_order = (last['sort_order'] + 1) if last and 'sort_order' in last else 0
        try:
            doc = {
                'name': name,
                'parent_id': parent_oid,
                'description': description,
                'sort_order': sort_order,
                'status': 1,
                'created_at': datetime.utcnow(),
            }
            return str(cls._col().insert_one(doc).inserted_id)
        except Exception:
            logger.error(f'ProductCategory.create 新增失敗 name={name!r}', exc_info=True)
            raise

    @classmethod
    def update(cls, cid: str, **kwargs) -> bool:
        try:
            oid = ObjectId(cid)
        except InvalidId:
            raise ValueError(f'分類 ID 格式無效: {cid!r}')
        fields = {}
        if 'name' in kwargs:
            fields['name'] = kwargs['name']
        if 'description' in kwargs:
            fields['description'] = kwargs['description']
        if 'sort_order' in kwargs:
            fields['sort_order'] = int(kwargs['sort_order'])
        if 'parent_id' in kwargs:
            try:
                fields['parent_id'] = ObjectId(kwargs['parent_id']) if kwargs['parent_id'] else None
            except InvalidId:
                raise ValueError(f'父分類 ID 格式無效: {kwargs["parent_id"]!r}')
        if 'status' in kwargs:
            fields['status'] = int(kwargs['status'])
        if not fields:
            return False
        try:
            r = cls._col().update_one({'_id': oid}, {'$set': fields})
            return r.matched_count > 0
        except Exception:
            logger.error(f'ProductCategory.update 更新失敗 cid={cid}', exc_info=True)
            raise

    @classmethod
    def delete(cls, cid: str) -> bool:
        try:
            oid = ObjectId(cid)
        except InvalidId:
            raise ValueError(f'分類 ID 格式無效: {cid!r}')
        try:
            r = cls._col().delete_one({'_id': oid})
            return r.deleted_count > 0
        except Exception:
            logger.error(f'ProductCategory.delete 刪除失敗 cid={cid}', exc_info=True)
            raise


# ─────────────────────────────────────────────────────────────
#  產品
# ─────────────────────────────────────────────────────────────
class Product:
    COLLECTION = 'products'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def _fmt(cls, doc) -> dict:
        if doc is None:
            return None
        d = {k: v for k, v in doc.items() if k != '_id'}
        d['_id'] = str(doc['_id'])
        if d.get('category_id'):
            d['category_id'] = str(d['category_id'])
        return d

    @classmethod
    def find_all(cls, keyword: str = '', category_id: str = '', status: int = None,
                 limit: int = 1000) -> list:
        q = {}
        if keyword:
            q['$or'] = [
                {'name': {'$regex': keyword, '$options': 'i'}},
                {'sku': {'$regex': keyword, '$options': 'i'}},
                {'barcode': {'$regex': keyword, '$options': 'i'}},
            ]
        if category_id:
            try:
                q['category_id'] = ObjectId(category_id)
            except InvalidId:
                raise ValueError(f'分類 ID 格式無效: {category_id!r}')
        if status is not None:
            q['status'] = status
        try:
            docs = cls._col().find(q).sort('created_at', -1).limit(limit)
            return [cls._fmt(d) for d in docs]
        except Exception:
            logger.error(
                f'Product.find_all 查詢失敗 keyword={keyword!r} category_id={category_id!r}',
                exc_info=True,
            )
            raise

    @classmethod
    def find_by_id(cls, pid: str) -> dict:
        try:
            oid = ObjectId(pid)
        except InvalidId:
            raise ValueError(f'產品 ID 格式無效: {pid!r}')
        try:
            return cls._fmt(cls._col().find_one({'_id': oid}))
        except Exception:
            logger.error(f'Product.find_by_id 查詢失敗 pid={pid}', exc_info=True)
            raise

    @classmethod
    def find_by_sku(cls, sku: str) -> dict:
        try:
            return cls._fmt(cls._col().find_one({'sku': sku}))
        except Exception:
            logger.error(f'Product.find_by_sku 查詢失敗 sku={sku!r}', exc_info=True)
            raise

    @classmethod
    def find_by_barcode(cls, barcode: str) -> dict:
        """以條碼精確查詢產品（空字串直接回 None）"""
        if not barcode:
            return None
        try:
            return cls._fmt(cls._col().find_one({'barcode': barcode}))
        except Exception:
            logger.error(f'Product.find_by_barcode 查詢失敗 barcode={barcode!r}', exc_info=True)
            raise

    @classmethod
    def create(cls, data: dict, created_by: str = '') -> str:
        for required in ('sku', 'name'):
            if not data.get(required):
                raise ValueError(f'缺少必要欄位: {required!r}')
        try:
            category_oid = ObjectId(data['category_id']) if data.get('category_id') else None
        except InvalidId:
            raise ValueError(f'分類 ID 格式無效: {data["category_id"]!r}')
        try:
            now = datetime.utcnow()
            doc = {
                'sku': data['sku'],
                'barcode': data.get('barcode', ''),
                'name': data['name'],
                'category_id': category_oid,
                'unit': data.get('unit', '個'),
                'description': data.get('description', ''),
                'cost_price': float(data.get('cost_price', 0)),
                'sell_price': float(data.get('sell_price', 0)),
                'min_stock': int(data.get('min_stock', 0)),
                'max_stock': int(data.get('max_stock', 0)),
                'status': 1,
                'created_by': created_by,
                'created_at': now,
                'updated_at': now,
            }
            return str(cls._col().insert_one(doc).inserted_id)
        except (ValueError, TypeError) as e:
            logger.error(f'Product.create 資料格式錯誤 sku={data.get("sku")!r}', exc_info=True)
            raise ValueError(f'欄位資料格式錯誤: {e}')
        except Exception:
            logger.error(f'Product.create 新增失敗 sku={data.get("sku")!r}', exc_info=True)
            raise

    @classmethod
    def update(cls, pid: str, data: dict) -> bool:
        try:
            oid = ObjectId(pid)
        except InvalidId:
            raise ValueError(f'產品 ID 格式無效: {pid!r}')
        fields = {'updated_at': datetime.utcnow()}
        for key in ('sku', 'barcode', 'name', 'unit', 'description'):
            if key in data:
                fields[key] = data[key]
        try:
            for key in ('cost_price', 'sell_price'):
                if key in data:
                    fields[key] = float(data[key])
            for key in ('min_stock', 'max_stock', 'status'):
                if key in data:
                    fields[key] = int(data[key])
        except (ValueError, TypeError) as e:
            raise ValueError(f'欄位資料格式錯誤: {e}')
        if 'category_id' in data:
            try:
                fields['category_id'] = ObjectId(data['category_id']) if data['category_id'] else None
            except InvalidId:
                raise ValueError(f'分類 ID 格式無效: {data["category_id"]!r}')
        try:
            r = cls._col().update_one({'_id': oid}, {'$set': fields})
            return r.matched_count > 0
        except Exception:
            logger.error(f'Product.update 更新失敗 pid={pid}', exc_info=True)
            raise

    @classmethod
    def delete(cls, pid: str) -> bool:
        try:
            oid = ObjectId(pid)
        except InvalidId:
            raise ValueError(f'產品 ID 格式無效: {pid!r}')
        try:
            r = cls._col().delete_one({'_id': oid})
            return r.deleted_count > 0
        except Exception:
            logger.error(f'Product.delete 刪除失敗 pid={pid}', exc_info=True)
            raise

    @classmethod
    def batch_update(cls, ids: list, updates: dict) -> int:
        if not ids or not updates:
            return 0
        oids = []
        for id_ in ids:
            try:
                oids.append(ObjectId(id_))
            except InvalidId:
                pass
        if not oids:
            return 0
        fields = {'updated_at': datetime.utcnow()}
        for key in ('sku', 'barcode', 'name', 'unit', 'description'):
            if key in updates:
                fields[key] = updates[key]
        try:
            for key in ('cost_price', 'sell_price'):
                if key in updates:
                    fields[key] = float(updates[key])
            for key in ('min_stock', 'max_stock', 'status'):
                if key in updates:
                    fields[key] = int(updates[key])
        except (ValueError, TypeError) as e:
            raise ValueError(f'欄位資料格式錯誤: {e}')
        if 'category_id' in updates:
            try:
                fields['category_id'] = ObjectId(updates['category_id']) if updates['category_id'] else None
            except InvalidId:
                raise ValueError(f'分類 ID 格式無效: {updates["category_id"]!r}')
        try:
            r = cls._col().update_many({'_id': {'$in': oids}}, {'$set': fields})
            return r.modified_count
        except Exception:
            logger.error('Product.batch_update 批量更新失敗', exc_info=True)
            raise

    @classmethod
    def batch_delete(cls, ids: list) -> int:
        if not ids:
            return 0
        oids = []
        for id_ in ids:
            try:
                oids.append(ObjectId(id_))
            except InvalidId:
                pass
        if not oids:
            return 0
        try:
            r = cls._col().delete_many({'_id': {'$in': oids}})
            return r.deleted_count
        except Exception:
            logger.error('Product.batch_delete 批量刪除失敗', exc_info=True)
            raise
