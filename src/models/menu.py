"""
菜單 Model
Collection: menus
每份菜單包含：
  categories — embedded 分類陣列（{_id, name, sort_order, status}）
  items      — embedded 品項陣列（{_id, name, price, category, consume_inventory, …}）
品項的 category 欄位儲存分類名稱字串，與 categories[].name 對應。
"""
from datetime import datetime
from bson import ObjectId
from src.mongo import get_db
import uuid


def _new_item_id() -> str:
    """品項使用 UUID 字串作為 _id（embedded doc 不需 ObjectId）"""
    return str(uuid.uuid4())


def _parse_linked_products(raw: list) -> list:
    """將前端傳入的 linked_products 陣列轉換為 DB 儲存格式（ObjectId）。"""
    result = []
    for lp in (raw or []):
        pid = lp.get('product_id')
        wid = lp.get('warehouse_id')
        if not pid:
            continue
        result.append({
            'product_id':  ObjectId(pid),
            'warehouse_id': ObjectId(wid) if wid else None,
            'consume_qty': max(1, int(lp.get('consume_qty', 1) or 1)),
        })
    return result


def _parse_customizations(raw: list) -> list:
    """
    將前端傳入的客製化選項陣列轉換為 DB 儲存格式。
    每組：{_id, name, type('single'|'multiple'), required, choices[{_id,name,extra_price,is_default}]}
    """
    result = []
    for grp in (raw or []):
        name = (grp.get('name') or '').strip()
        if not name:
            continue
        is_multiple = grp.get('type') == 'multiple'
        choices = []
        for ch in (grp.get('choices') or []):
            ch_name = (ch.get('name') or '').strip()
            if not ch_name:
                continue
            choices.append({
                '_id':         ch.get('_id') or _new_item_id(),
                'name':        ch_name,
                'extra_price': max(0.0, float(ch.get('extra_price') or 0)),
                'is_default':  bool(ch.get('is_default', False)),
            })
        # 單選組：若多個選項都標記為預設，只保留第一個
        if not is_multiple:
            found = False
            for ch in choices:
                if ch['is_default']:
                    if found:
                        ch['is_default'] = False
                    else:
                        found = True
        result.append({
            '_id':      grp.get('_id') or _new_item_id(),
            'name':     name,
            'type':     'multiple' if is_multiple else 'single',
            'required': bool(grp.get('required', True)),
            'choices':  choices,
        })
    return result


def _fmt_linked_products(lps: list) -> list:
    """將 DB 格式的 linked_products 序列化為前端可用的字串格式。"""
    return [
        {
            'product_id':  str(lp['product_id'])  if lp.get('product_id')  else None,
            'warehouse_id': str(lp['warehouse_id']) if lp.get('warehouse_id') else None,
            'consume_qty': lp.get('consume_qty', 1),
        }
        for lp in (lps or [])
    ]


def _fmt_menu(doc) -> dict:
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['_id'] = str(doc['_id'])
    for key in ('created_at', 'updated_at'):
        if key in d and d[key]:
            d[key] = d[key].isoformat() + 'Z'

    # 確保 option_groups 欄位存在（舊資料向下相容）
    if 'option_groups' not in d:
        d['option_groups'] = []
    # 建立 gid → group 查詢表，供品項解析 applied_group_ids 用
    og_lookup = {og['_id']: og for og in d['option_groups']}

    # 格式化 items
    for item in d.get('items', []):
        # 舊欄位（向下相容）
        if item.get('product_id'):
            item['product_id'] = str(item['product_id'])
        if item.get('warehouse_id'):
            item['warehouse_id'] = str(item['warehouse_id'])
        # 格式化 linked_products（多商品連結）
        for lp in item.get('linked_products', []):
            if lp.get('product_id'):
                lp['product_id'] = str(lp['product_id'])
            if lp.get('warehouse_id'):
                lp['warehouse_id'] = str(lp['warehouse_id'])
        # 舊資料自動合成 linked_products（確保前端永遠有此欄位）
        if 'linked_products' not in item:
            if item.get('product_id'):
                item['linked_products'] = [{
                    'product_id':  item['product_id'],
                    'warehouse_id': item.get('warehouse_id'),
                    'consume_qty': item.get('consume_qty', 1) or 1,
                }]
            else:
                item['linked_products'] = []
        # 確保 customizations 欄位永遠存在（舊資料向下相容）
        if 'customizations' not in item:
            item['customizations'] = []
        # 確保 applied_group_ids 欄位永遠存在
        if 'applied_group_ids' not in item:
            item['applied_group_ids'] = []
        # 解析 applied_group_ids → applied_groups（供前端 & POS 直接使用）
        item['applied_groups'] = [
            og_lookup[gid] for gid in item['applied_group_ids']
            if gid in og_lookup
        ]
    return d


class Menu:
    COLLECTION = 'menus'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    # ── 查詢 ──────────────────────────────────────
    @classmethod
    def find_all(cls, status: int = None) -> list:
        q = {}
        if status is not None:
            q['status'] = status
        docs = cls._col().find(q).sort('sort_order', 1)
        return [_fmt_menu(d) for d in docs]

    @classmethod
    def find_by_id(cls, mid: str) -> dict:
        try:
            return _fmt_menu(cls._col().find_one({'_id': ObjectId(mid)}))
        except Exception:
            return None

    # ── 菜單 CRUD ─────────────────────────────────
    @classmethod
    def create(cls, name: str, description: str = '',
               sort_order: int = 0) -> str:
        now = datetime.utcnow()
        doc = {
            'name':          name,
            'description':   description,
            'status':        1,
            'sort_order':    sort_order,
            'categories':    [],
            'items':         [],
            'option_groups': [],
            'created_at':    now,
            'updated_at':    now,
        }
        return str(cls._col().insert_one(doc).inserted_id)

    @classmethod
    def update(cls, mid: str, **kwargs) -> bool:
        fields = {'updated_at': datetime.utcnow()}
        for k in ('name', 'description', 'sort_order'):
            if k in kwargs:
                fields[k] = kwargs[k]
        if 'status' in kwargs:
            fields['status'] = int(kwargs['status'])
        r = cls._col().update_one({'_id': ObjectId(mid)}, {'$set': fields})
        return r.matched_count > 0

    @classmethod
    def delete(cls, mid: str) -> bool:
        r = cls._col().delete_one({'_id': ObjectId(mid)})
        return r.deleted_count > 0

    # ── 品項 CRUD（embedded） ─────────────────────
    @classmethod
    def add_item(cls, mid: str, data: dict) -> dict:
        """
        新增品項，回傳完整品項 dict。
        data 欄位：
          name, price, category, consume_inventory,
          linked_products(選填): [{product_id, warehouse_id, consume_qty}],
          sort_order, description, status
        """
        linked_products = _parse_linked_products(data.get('linked_products', []))
        raw_gids = data.get('applied_group_ids') or []
        item = {
            '_id':               _new_item_id(),
            'name':              data.get('name', '').strip(),
            'description':       data.get('description', ''),
            'price':             float(data.get('price', 0)),
            'category':          data.get('category', '').strip(),
            'consume_inventory': bool(data.get('consume_inventory', False)),
            'linked_products':   linked_products,
            'customizations':    _parse_customizations(data.get('customizations', [])),
            'applied_group_ids': [str(g) for g in raw_gids],
            'sort_order':        int(data.get('sort_order', 0)),
            'status':            int(data.get('status', 1)),
        }
        cls._col().update_one(
            {'_id': ObjectId(mid)},
            {'$push': {'items': item},
             '$set':  {'updated_at': datetime.utcnow()}},
        )
        # 回傳序列化版本
        item['linked_products'] = _fmt_linked_products(item['linked_products'])
        return item

    @classmethod
    def update_item(cls, mid: str, item_id: str, data: dict) -> bool:
        set_fields = {'updated_at': datetime.utcnow()}
        for k in ('name', 'description', 'category'):
            if k in data:
                set_fields[f'items.$[el].{k}'] = data[k]
        if 'price' in data:
            set_fields['items.$[el].price'] = float(data['price'])
        if 'sort_order' in data:
            set_fields['items.$[el].sort_order'] = int(data['sort_order'])
        if 'status' in data:
            set_fields['items.$[el].status'] = int(data['status'])
        if 'consume_inventory' in data:
            set_fields['items.$[el].consume_inventory'] = bool(data['consume_inventory'])
        if 'linked_products' in data:
            set_fields['items.$[el].linked_products'] = \
                _parse_linked_products(data['linked_products'])
        if 'customizations' in data:
            set_fields['items.$[el].customizations'] = \
                _parse_customizations(data['customizations'])
        if 'applied_group_ids' in data:
            set_fields['items.$[el].applied_group_ids'] = \
                [str(g) for g in (data['applied_group_ids'] or [])]

        r = cls._col().update_one(
            {'_id': ObjectId(mid)},
            {'$set': set_fields},
            array_filters=[{'el._id': item_id}],
        )
        return r.matched_count > 0

    @classmethod
    def delete_item(cls, mid: str, item_id: str) -> bool:
        r = cls._col().update_one(
            {'_id': ObjectId(mid)},
            {'$pull': {'items': {'_id': item_id}},
             '$set':  {'updated_at': datetime.utcnow()}},
        )
        return r.matched_count > 0

    # ── 取得單一品項 ──────────────────────────────
    @classmethod
    def find_item(cls, mid: str, item_id: str) -> dict:
        doc = cls._col().find_one(
            {'_id': ObjectId(mid), 'items._id': item_id},
            {'items.$': 1},
        )
        if not doc or not doc.get('items'):
            return None
        item = dict(doc['items'][0])
        if item.get('product_id'):
            item['product_id'] = str(item['product_id'])
        if item.get('warehouse_id'):
            item['warehouse_id'] = str(item['warehouse_id'])
        return item

    # ── 分類 CRUD（embedded） ──────────────────────
    @classmethod
    def add_category(cls, mid: str, data: dict) -> dict:
        """
        新增分類，回傳完整分類 dict。
        data 欄位：name（必填）、sort_order、status
        """
        cat = {
            '_id':        _new_item_id(),
            'name':       data.get('name', '').strip(),
            'sort_order': int(data.get('sort_order', 0)),
            'status':     int(data.get('status', 1)),
        }
        cls._col().update_one(
            {'_id': ObjectId(mid)},
            {'$push': {'categories': cat},
             '$set':  {'updated_at': datetime.utcnow()}},
        )
        return cat

    @classmethod
    def update_category(cls, mid: str, cat_id: str, data: dict) -> bool:
        set_fields = {'updated_at': datetime.utcnow()}
        if 'name' in data:
            old_name = None
            # 取出舊名稱，同步更新所有品項的 category 字串
            doc = cls._col().find_one(
                {'_id': ObjectId(mid), 'categories._id': cat_id},
                {'categories.$': 1},
            )
            if doc and doc.get('categories'):
                old_name = doc['categories'][0].get('name', '')
            set_fields['categories.$[c].name'] = data['name']
            # 同步品項 category 欄位
            if old_name and old_name != data['name']:
                cls._col().update_one(
                    {'_id': ObjectId(mid)},
                    {'$set': {'items.$[i].category': data['name']}},
                    array_filters=[{'i.category': old_name}],
                )
        if 'sort_order' in data:
            set_fields['categories.$[c].sort_order'] = int(data['sort_order'])
        if 'status' in data:
            set_fields['categories.$[c].status'] = int(data['status'])
        r = cls._col().update_one(
            {'_id': ObjectId(mid)},
            {'$set': set_fields},
            array_filters=[{'c._id': cat_id}],
        )
        return r.matched_count > 0

    @classmethod
    def delete_category(cls, mid: str, cat_id: str) -> bool:
        r = cls._col().update_one(
            {'_id': ObjectId(mid)},
            {'$pull': {'categories': {'_id': cat_id}},
             '$set':  {'updated_at': datetime.utcnow()}},
        )
        return r.matched_count > 0

    # ── 選項組 CRUD（embedded option_groups） ──────
    @classmethod
    def add_option_group(cls, mid: str, data: dict) -> dict:
        """
        新增選項組，回傳完整 dict。
        data 欄位：
          name（必填）、type('single'|'multiple')、required、
          choices[{name, extra_price, is_default}]
        """
        og = {
            '_id':      _new_item_id(),
            'name':     (data.get('name') or '').strip(),
            'type':     'multiple' if data.get('type') == 'multiple' else 'single',
            'required': bool(data.get('required', True)),
            'choices':  [],
        }
        for ch in (data.get('choices') or []):
            ch_name = (ch.get('name') or '').strip()
            if not ch_name:
                continue
            og['choices'].append({
                '_id':         ch.get('_id') or _new_item_id(),
                'name':        ch_name,
                'extra_price': max(0.0, float(ch.get('extra_price') or 0)),
                'is_default':  bool(ch.get('is_default', False)),
            })
        # 單選組：只保留第一個 is_default
        if og['type'] == 'single':
            found = False
            for ch in og['choices']:
                if ch['is_default']:
                    if found:
                        ch['is_default'] = False
                    else:
                        found = True
        cls._col().update_one(
            {'_id': ObjectId(mid)},
            {'$push': {'option_groups': og},
             '$set':  {'updated_at': datetime.utcnow()}},
        )
        return og

    @classmethod
    def update_option_group(cls, mid: str, gid: str, data: dict) -> bool:
        set_fields = {'updated_at': datetime.utcnow()}
        if 'name' in data:
            set_fields['option_groups.$[g].name'] = (data['name'] or '').strip()
        if 'type' in data:
            set_fields['option_groups.$[g].type'] = \
                'multiple' if data['type'] == 'multiple' else 'single'
        if 'required' in data:
            set_fields['option_groups.$[g].required'] = bool(data['required'])
        if 'choices' in data:
            choices = []
            for ch in (data['choices'] or []):
                ch_name = (ch.get('name') or '').strip()
                if not ch_name:
                    continue
                choices.append({
                    '_id':         ch.get('_id') or _new_item_id(),
                    'name':        ch_name,
                    'extra_price': max(0.0, float(ch.get('extra_price') or 0)),
                    'is_default':  bool(ch.get('is_default', False)),
                })
            set_fields['option_groups.$[g].choices'] = choices
        r = cls._col().update_one(
            {'_id': ObjectId(mid)},
            {'$set': set_fields},
            array_filters=[{'g._id': gid}],
        )
        return r.matched_count > 0

    @classmethod
    def delete_option_group(cls, mid: str, gid: str) -> bool:
        """刪除選項組，同時從所有品項的 applied_group_ids 中移除該 gid。"""
        r = cls._col().update_one(
            {'_id': ObjectId(mid)},
            {
                '$pull': {'option_groups': {'_id': gid}},
                '$set':  {'updated_at': datetime.utcnow()},
            },
        )
        # 清除品項中的參照
        cls._col().update_one(
            {'_id': ObjectId(mid)},
            {'$pull': {'items.$[].applied_group_ids': gid}},
        )
        return r.matched_count > 0
