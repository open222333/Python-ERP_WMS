"""
電子發票 Model
Collection: invoices
"""
from datetime import datetime
from bson import ObjectId
from src.mongo import get_db


def _fmt(doc) -> dict:
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['_id'] = str(doc['_id'])
    for key in ('created_at', 'issued_at', 'voided_at'):
        if key in d and d[key]:
            d[key] = d[key].isoformat() + 'Z'
    return d


class Invoice:
    COLLECTION = 'invoices'

    # 載具類型映射
    CARRIER_LABELS = {
        '':  '無（紙本）',
        '1': '手機條碼',
        '2': '自然人憑證',
    }

    @classmethod
    def _col(cls):
        return get_db()[cls.COLLECTION]

    # ── 建立（pending 狀態）───────────────────────────────
    @classmethod
    def create(cls, order_id: str, order_no: str, total_amount: float,
               items: list, carrier_type: str = '', carrier_num: str = '',
               buyer_id: str = '', love_code: str = '',
               customer_name: str = '', customer_email: str = '',
               remark: str = '', created_by: str = '') -> str:
        doc = {
            'order_id':       order_id,
            'order_no':       order_no,
            'total_amount':   int(total_amount),
            'items':          items,
            'carrier_type':   carrier_type,
            'carrier_num':    carrier_num,
            'buyer_id':       buyer_id,          # 統一編號（B2B）
            'love_code':      love_code,         # 愛心碼
            'customer_name':  customer_name,
            'customer_email': customer_email,
            'remark':         remark,
            'status':         'pending',         # pending / issued / voided / error
            'invoice_no':     '',
            'random_no':      '',
            'invoice_date':   '',
            'ecpay_response': None,
            'error_msg':      '',
            'voided_by':      '',
            'void_reason':    '',
            'created_by':     created_by,
            'created_at':     datetime.utcnow(),
            'issued_at':      None,
            'voided_at':      None,
        }
        return str(cls._col().insert_one(doc).inserted_id)

    # ── 狀態更新 ──────────────────────────────────────────
    @classmethod
    def mark_issued(cls, inv_id: str, invoice_no: str, random_no: str,
                    invoice_date: str, ecpay_response: dict):
        cls._col().update_one(
            {'_id': ObjectId(inv_id)},
            {'$set': {
                'status':         'issued',
                'invoice_no':     invoice_no,
                'random_no':      random_no,
                'invoice_date':   invoice_date,
                'ecpay_response': ecpay_response,
                'issued_at':      datetime.utcnow(),
                'error_msg':      '',
            }},
        )

    @classmethod
    def mark_error(cls, inv_id: str, error_msg: str):
        cls._col().update_one(
            {'_id': ObjectId(inv_id)},
            {'$set': {'status': 'error', 'error_msg': error_msg}},
        )

    @classmethod
    def mark_voided(cls, inv_id: str, reason: str, operator: str):
        cls._col().update_one(
            {'_id': ObjectId(inv_id)},
            {'$set': {
                'status':     'voided',
                'void_reason': reason,
                'voided_by':  operator,
                'voided_at':  datetime.utcnow(),
            }},
        )

    # ── 查詢 ──────────────────────────────────────────────
    @classmethod
    def find_by_id(cls, inv_id: str) -> dict:
        try:
            return _fmt(cls._col().find_one({'_id': ObjectId(inv_id)}))
        except Exception:
            return None

    @classmethod
    def find_by_order(cls, order_id: str) -> dict:
        return _fmt(cls._col().find_one({'order_id': order_id}))

    @classmethod
    def find_all(cls, status: str = None, date_from: datetime = None,
                 date_to: datetime = None, limit: int = 100) -> list:
        q = {}
        if status:
            q['status'] = status
        if date_from or date_to:
            q['created_at'] = {}
            if date_from:
                q['created_at']['$gte'] = date_from
            if date_to:
                q['created_at']['$lte'] = date_to
        docs = cls._col().find(q).sort('created_at', -1).limit(limit)
        return [_fmt(d) for d in docs]
