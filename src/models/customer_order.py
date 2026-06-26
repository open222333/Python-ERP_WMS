"""
顧客訂單 Model
Collection: customer_orders
狀態: pending → processing → completed | cancelled
"""
from datetime import datetime, timedelta
from bson import ObjectId
from src.mongo import get_db


ORDER_STATUS = ('pending', 'processing', 'completed', 'cancelled')
ORDER_STATUS_LABEL = {
    'pending':    '待處理',
    'processing': '處理中',
    'completed':  '已完成',
    'cancelled':  '已取消',
}


def _fmt(doc) -> dict:
    if doc is None:
        return None
    d = {}
    for k, v in doc.items():
        if k == '_id':
            continue
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif k == 'status_log' and isinstance(v, list):
            d[k] = [
                {**e, 'at': e['at'].isoformat() if isinstance(e.get('at'), datetime) else e.get('at')}
                for e in v
            ]
        elif k == 'store_id' and v is not None:
            d[k] = str(v)
        else:
            d[k] = v
    d['_id'] = str(doc['_id'])
    return d


class CustomerOrder:
    COLLECTION = 'customer_orders'

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    # ── 建立訂單（顧客） ──────────────────────────
    @classmethod
    def create(cls, table_no: str, items: list, total: float,
               remark: str = '', menu_id: str = '',
               store_id=None) -> str:
        """
        建立訂單，回傳訂單 _id
        items: [{item_id, item_name, qty, price, customizations, note}]
        """
        now = datetime.utcnow()
        today_str = now.strftime('%Y%m%d')
        counter = get_db()['counters'].find_one_and_update(
            {'_id': f'cust_order_{today_str}'},
            {'$inc': {'seq': 1}},
            upsert=True,
            return_document=True,
        )
        order_no = f"{today_str}-{counter['seq']:04d}"

        doc = {
            'order_no':   order_no,
            'order_date': today_str,
            'table_no':   table_no,
            'items':      items,
            'total':      total,
            'status':     'pending',
            'menu_id':    menu_id,
            'remark':     remark,
            'handled_by': '',
            'status_log': [],
            'created_at': now,
            'updated_at': now,
        }
        if store_id:
            doc['store_id'] = ObjectId(store_id)
        result = cls._col().insert_one(doc)
        return str(result.inserted_id)

    # ── 查詢 ──────────────────────────────────────
    @classmethod
    def find_all(cls, status: str = None, date: str = None,
                 limit: int = 100, store_filter: dict = None) -> list:
        """查詢訂單，預設最新100筆"""
        q = dict(store_filter or {})
        if status and status in ORDER_STATUS:
            q['status'] = status
        if date:
            q['order_date'] = date
        docs = cls._col().find(q).sort('created_at', -1).limit(limit)
        return [_fmt(d) for d in docs]

    @classmethod
    def find_active(cls, store_filter: dict = None) -> list:
        """待處理 + 處理中 訂單（廚房顯示用）"""
        q = dict(store_filter or {})
        q['status'] = {'$in': ['pending', 'processing']}
        docs = cls._col().find(q).sort('created_at', 1)   # 先進先出
        return [_fmt(d) for d in docs]

    @classmethod
    def find_by_id(cls, oid: str, store_filter: dict = None) -> dict:
        try:
            q = {'_id': ObjectId(oid)}
            if store_filter:
                q.update(store_filter)
            doc = cls._col().find_one(q)
        except Exception:
            return None
        return _fmt(doc)

    # ── 更新狀態 ──────────────────────────────────
    @classmethod
    def update_status(cls, oid: str, status: str,
                      operator: str = '') -> bool:
        if status not in ORDER_STATUS:
            return False
        try:
            now = datetime.utcnow()
            result = cls._col().update_one(
                {'_id': ObjectId(oid)},
                {
                    '$set': {
                        'status':     status,
                        'handled_by': operator,
                        'updated_at': now,
                    },
                    '$push': {
                        'status_log': {'status': status, 'by': operator, 'at': now}
                    },
                }
            )
            return result.matched_count > 0
        except Exception:
            return False

    @classmethod
    def find_by_table(cls, table_no: str) -> list:
        """取得此桌今日所有訂單（顧客 SSE 用，先進先出）"""
        today = datetime.utcnow().strftime('%Y%m%d')
        docs = cls._col().find(
            {'table_no': table_no, 'order_date': today}
        ).sort('created_at', 1)
        return [_fmt(d) for d in docs]

    # ── 統計 ──────────────────────────────────────
    @classmethod
    def today_stats(cls, store_filter: dict = None) -> dict:
        today = datetime.utcnow().strftime('%Y%m%d')
        match = dict(store_filter or {})
        match['order_date'] = today
        pipeline = [
            {'$match': match},
            {'$group': {
                '_id':   '$status',
                'count': {'$sum': 1},
                'total': {'$sum': '$total'},
            }}
        ]
        result = {s: {'count': 0, 'total': 0.0} for s in ORDER_STATUS}
        for r in cls._col().aggregate(pipeline):
            s = r['_id']
            if s in result:
                result[s] = {'count': r['count'], 'total': round(r['total'], 2)}
        return result
