"""
外送平台訂單 / 映射 Model
Collections:
  delivery_orders   — 訂單（每筆對應一個外送平台訂單）
  delivery_mappings — 平台商品 ID ↔ 系統 product._id 或菜單品項（menu_id + menu_item_id）映射
  delivery_settings — 各平台啟用狀態及 webhook 設定（全域一筆 + 每店家每平台一筆）
"""
from datetime import datetime
from bson import ObjectId
from src.mongo import get_db
# [REFACTOR] 狀態集合與 terminal state guard 遷移至 src/constants.py 統一管理
from src.constants import DeliveryOrderStatus
import random, string


def _gen_order_no(platform: str) -> str:
    d    = datetime.utcnow().strftime('%Y%m%d')
    rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    prefix = {'ubereats': 'UBE', 'foodpanda': 'FP'}.get(platform, 'DEL')
    return f'{prefix}-{d}-{rand}'


def _fmt(doc) -> dict:
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['_id'] = str(doc['_id'])
    for key in ('created_at', 'updated_at', 'synced_at'):
        if key in d and d[key]:
            d[key] = d[key].isoformat() + 'Z'
    for oid_key in ('product_id', 'menu_id', 'menu_item_id', 'store_ref'):
        if oid_key in d and d[oid_key]:
            d[oid_key] = str(d[oid_key])
    return d


# ─────────────────────────────────────────────────────────────
#  DeliveryOrder
# ─────────────────────────────────────────────────────────────
class DeliveryOrder:
    COLLECTION = 'delivery_orders'

    # [REFACTOR] 引用常數模組，保留類別屬性名維持既有引用相容
    VALID_STATUSES = DeliveryOrderStatus.ALL

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    # ── 查詢 ──────────────────────────────────────
    @classmethod
    def find_all(cls, platform: str = None, status: str = None,
                 date_from: datetime = None, date_to: datetime = None,
                 limit: int = 200) -> list:
        q = {}
        if platform:
            q['platform'] = platform
        if status:
            q['status'] = status
        if date_from or date_to:
            q['placed_at'] = {}
            if date_from:
                q['placed_at']['$gte'] = date_from
            if date_to:
                q['placed_at']['$lte'] = date_to
        docs = cls._col().find(q).sort('placed_at', -1).limit(limit)
        return [_fmt(d) for d in docs]

    @classmethod
    def find_by_id(cls, oid: str) -> dict:
        try:
            return _fmt(cls._col().find_one({'_id': ObjectId(oid)}))
        except Exception:
            return None

    @classmethod
    def find_by_external(cls, platform: str, external_order_id: str) -> dict:
        return _fmt(cls._col().find_one(
            {'platform': platform, 'external_order_id': external_order_id}
        ))

    # ── 建立 ──────────────────────────────────────
    @classmethod
    def create_from_normalized(cls, normalized: dict) -> str:
        """接收 adapter.normalize_order() 的輸出，儲存到 DB"""
        now = datetime.utcnow()
        placed_str = normalized.get('placed_at', '')
        try:
            placed_at = datetime.fromisoformat(placed_str.replace('Z', '+00:00').replace('+00:00', ''))
        except Exception:
            placed_at = now

        # 依平台端店家代號（store id / vendor code）解析所屬分店
        external_store_id = str(normalized.get('external_store_id', '') or '')
        store_ref = None
        if external_store_id:
            store_ref = DeliverySettings.find_store_by_external(
                normalized['platform'], external_store_id)

        doc = {
            'platform':          normalized['platform'],
            'external_order_id': normalized.get('external_order_id', ''),
            'external_store_id': external_store_id,
            'store_ref':         ObjectId(store_ref) if store_ref else None,
            'order_no':          _gen_order_no(normalized['platform']),
            'external_order_no': normalized.get('order_no', ''),
            'status':            normalized.get('status', DeliveryOrderStatus.NEW),
            'customer_name':     normalized.get('customer_name', ''),
            'customer_phone':    normalized.get('customer_phone', ''),
            'items':             normalized.get('items', []),
            'subtotal':          float(normalized.get('subtotal', 0)),
            'delivery_fee':      float(normalized.get('delivery_fee', 0)),
            'total_amount':      float(normalized.get('total_amount', 0)),
            'payment_method':    normalized.get('payment_method', 'online'),
            'note':              normalized.get('note', ''),
            'placed_at':         placed_at,
            'estimated_pickup_at': normalized.get('estimated_pickup_at', ''),
            'raw_payload':       normalized.get('raw', {}),
            'created_at':        now,
            'updated_at':        now,
        }
        return str(cls._col().insert_one(doc).inserted_id)

    # ── 更新狀態 ──────────────────────────────────
    @classmethod
    def update_status(cls, oid: str, status: str,
                      operator: str = 'system') -> bool:
        if status not in cls.VALID_STATUSES:
            return False
        col = cls._col()
        current = col.find_one({'_id': ObjectId(oid)}, {'status': 1})
        if current and current.get('status') in DeliveryOrderStatus.TERMINAL_STATES:
            return False  # cannot transition from terminal state
        r = col.update_one(
            {'_id': ObjectId(oid)},
            {'$set': {'status': status, 'updated_at': datetime.utcnow(),
                      'last_operator': operator}},
        )
        return r.matched_count > 0

    # ── Upsert（webhook 重複推送保護）────────────
    @classmethod
    def upsert_from_normalized(cls, normalized: dict) -> tuple:
        """
        回傳 (internal_id, is_new)
        若相同 platform + external_order_id 已存在則更新狀態，否則建立
        """
        existing = cls.find_by_external(
            normalized['platform'], normalized.get('external_order_id', '')
        )
        if existing:
            cls.update_status(existing['_id'], normalized.get('status', existing['status']))
            return existing['_id'], False
        return cls.create_from_normalized(normalized), True


# ─────────────────────────────────────────────────────────────
#  DeliveryMapping  (平台商品 ID ↔ 系統 product_id)
# ─────────────────────────────────────────────────────────────
class DeliveryMapping:
    COLLECTION = 'delivery_mappings'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_all(cls, platform: str = None) -> list:
        q = {'platform': platform} if platform else {}
        return [_fmt(d) for d in cls._col().find(q).sort('product_name', 1)]

    @classmethod
    def find_by_product(cls, platform: str, product_id: str) -> dict:
        return _fmt(cls._col().find_one(
            {'platform': platform, 'product_id': ObjectId(product_id)}
        ))

    @classmethod
    def upsert(cls, platform: str, product_id: str,
               external_product_id: str, product_name: str = '',
               menu_id: str = None, menu_item_id: str = None,
               menu_item_name: str = '') -> str:
        """
        對應目標二擇一：
        - product_id                 → 產品層級對應（既有行為）
        - menu_id + menu_item_id     → 菜單品項對應（扣庫存走品項 linked_products）
        """
        now = datetime.utcnow()
        if product_id:
            key = {'platform': platform, 'product_id': ObjectId(product_id)}
        elif menu_item_id:
            # 菜單品項 _id 為 UUID 字串（embedded doc），不可轉 ObjectId
            key = {'platform': platform, 'menu_item_id': str(menu_item_id)}
        else:
            raise ValueError('product_id 與 menu_item_id 至少須填一項')

        set_fields = {
            'external_product_id': external_product_id,
            'product_name':        product_name,
            'updated_at':          now,
        }
        if menu_item_id:
            set_fields['menu_id']        = ObjectId(menu_id) if menu_id else None
            set_fields['menu_item_id']   = str(menu_item_id)
            set_fields['menu_item_name'] = menu_item_name
            set_fields['product_id']     = None
        r = cls._col().find_one_and_update(
            key,
            {'$set': set_fields, '$setOnInsert': {'created_at': now}},
            upsert=True,
            return_document=True,
        )
        return str(r['_id'])

    @classmethod
    def delete(cls, mid: str) -> bool:
        r = cls._col().delete_one({'_id': ObjectId(mid)})
        return r.deleted_count > 0


# ─────────────────────────────────────────────────────────────
#  DeliverySettings  (每平台設定，每平台僅一筆)
# ─────────────────────────────────────────────────────────────
class DeliverySettings:
    COLLECTION = 'delivery_settings'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def _default(cls, platform: str) -> dict:
        return {'platform': platform, 'enabled': False, 'auto_confirm': False,
                'default_warehouse_id': '', 'webhook_url': '', 'last_sync': None,
                'store_id': '', 'vendor_code': '',
                'item_mappings': [], 'mapping_template_id': None}

    @classmethod
    def _fmt_doc(cls, doc: dict) -> dict:
        d = _fmt(doc)
        if d.get('default_warehouse_id'):
            d['default_warehouse_id'] = str(d['default_warehouse_id'])
        if 'store_ref' in d and d['store_ref']:
            d['store_ref'] = str(d['store_ref'])
        return d

    @classmethod
    def get(cls, platform: str, store_ref: str = None) -> dict:
        from bson import ObjectId as ObjId
        q = {'platform': platform,
             'store_ref': ObjId(store_ref) if store_ref else None}
        doc = cls._col().find_one(q)
        if doc is None:
            return cls._default(platform)
        return cls._fmt_doc(doc)

    @classmethod
    def find_store_by_external(cls, platform: str, external_store_id: str) -> str:
        """依平台端店家代號（UberEats store id / foodpanda vendor code）反查 store_ref"""
        if not external_store_id:
            return None
        doc = cls._col().find_one({
            'platform':  platform,
            'store_ref': {'$ne': None},
            '$or': [{'store_id': external_store_id},
                    {'vendor_code': external_store_id}],
        })
        return str(doc['store_ref']) if doc else None

    @classmethod
    def effective(cls, platform: str, store_ref: str = None) -> dict:
        """
        取得「有效設定」：有 store_ref 且該店有設定時以店家設定優先，
        空值欄位（default_warehouse_id / item_mappings / mapping_template_id）回退全域。
        """
        from bson import ObjectId as ObjId
        base = cls.get(platform)
        if not store_ref:
            return base
        doc = cls._col().find_one(
            {'platform': platform, 'store_ref': ObjId(store_ref)})
        if doc is None:
            return base
        store = cls._fmt_doc(doc)
        merged = dict(base)
        for k, v in store.items():
            if k in ('enabled', 'auto_confirm') or v not in (None, '', []):
                merged[k] = v
        merged['store_ref'] = store_ref
        return merged

    @classmethod
    def get_store_platforms(cls, store_ref: str) -> dict:
        """回傳指定 store 的所有平台設定摘要 {platform: {enabled, auto_confirm}}"""
        from bson import ObjectId as ObjId
        docs = cls._col().find({'store_ref': ObjId(store_ref)})
        result = {}
        for doc in docs:
            d = cls._fmt_doc(doc)
            result[d['platform']] = {'enabled': d.get('enabled', False),
                                     'auto_confirm': d.get('auto_confirm', False)}
        return result

    @classmethod
    def upsert(cls, platform: str, store_ref: str = None, **kwargs) -> dict:
        from bson import ObjectId as ObjId
        now = datetime.utcnow()
        store_ref_oid = ObjId(store_ref) if store_ref else None
        update_fields = {'updated_at': now}
        for k in ('enabled', 'auto_confirm', 'webhook_url', 'store_id',
                  'vendor_code', 'last_sync'):
            if k in kwargs:
                update_fields[k] = kwargs[k]
        if 'default_warehouse_id' in kwargs:
            wid = kwargs['default_warehouse_id']
            update_fields['default_warehouse_id'] = ObjId(wid) if wid else None
        if 'item_mappings' in kwargs:
            update_fields['item_mappings'] = kwargs['item_mappings']
        if 'mapping_template_id' in kwargs:
            tid = kwargs['mapping_template_id']
            update_fields['mapping_template_id'] = tid if tid else None
        cls._col().update_one(
            {'platform': platform, 'store_ref': store_ref_oid},
            {'$set': update_fields,
             '$setOnInsert': {'platform': platform, 'store_ref': store_ref_oid,
                              'created_at': now}},
            upsert=True,
        )
        return cls.get(platform, store_ref)


# ─────────────────────────────────────────────────────────────
#  DeliveryMappingTemplate  (品項對應模板)
# ─────────────────────────────────────────────────────────────
class DeliveryMappingTemplate:
    COLLECTION = 'delivery_mapping_templates'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    @classmethod
    def find_all(cls) -> list:
        return [_fmt(d) for d in cls._col().find().sort('name', 1)]

    @classmethod
    def find_by_id(cls, oid: str) -> dict:
        try:
            return _fmt(cls._col().find_one({'_id': ObjectId(oid)}))
        except Exception:
            return None

    @classmethod
    def create(cls, name: str, platform: str, items: list) -> str:
        now = datetime.utcnow()
        doc = {
            'name':       name,
            'platform':   platform,
            'items':      items,
            'created_at': now,
            'updated_at': now,
        }
        return str(cls._col().insert_one(doc).inserted_id)

    @classmethod
    def update(cls, oid: str, **kwargs) -> bool:
        fields = {'updated_at': datetime.utcnow()}
        for k in ('name', 'platform', 'items'):
            if k in kwargs:
                fields[k] = kwargs[k]
        r = cls._col().update_one({'_id': ObjectId(oid)}, {'$set': fields})
        return r.matched_count > 0

    @classmethod
    def delete(cls, oid: str) -> bool:
        r = cls._col().delete_one({'_id': ObjectId(oid)})
        return r.deleted_count > 0
