"""
電子發票 Model
Collection: invoices
"""
from datetime import datetime
from bson import ObjectId
from src.mongo import get_db
# [REFACTOR] 狀態字串改由 src/constants.py 統一管理
from src.constants import InvoiceStatus


def _fmt(doc) -> dict:
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != '_id'}
    d['_id'] = str(doc['_id'])
    if d.get('store_id'):
        d['store_id'] = str(d['store_id'])
    d.pop('active_order_id', None)
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
               remark: str = '', created_by: str = '',
               store_id: str = None, terminal_id: str = '',
               merchant_id: str = '') -> str:
        """
        [A3] 寫入 active_order_id（唯一索引）：同一訂單同時只能有一張開立中／已開立的發票，
        並發重複開立時第二筆會撞 DuplicateKeyError，由 view 回 409。
        開立失敗（error）或作廢（voided）時移除 active_order_id，才能重新開立。
        [A4] 記錄開立時的店家、機台與商店代號，作廢必須用同一組金鑰。
        """
        doc = {
            'order_id':       order_id,
            'active_order_id': order_id,
            'order_no':       order_no,
            'store_id':       ObjectId(store_id) if store_id else None,
            'terminal_id':    terminal_id or '',
            'merchant_id':    merchant_id or '',
            'total_amount':   int(round(float(total_amount))),
            'items':          items,
            'carrier_type':   carrier_type,
            'carrier_num':    carrier_num,
            'buyer_id':       buyer_id,          # 統一編號（B2B）
            'love_code':      love_code,         # 愛心碼
            'customer_name':  customer_name,
            'customer_email': customer_email,
            'remark':         remark,
            'status':         InvoiceStatus.PENDING,   # pending / issued / voided / error
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
                'status':         InvoiceStatus.ISSUED,
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
            {'$set': {'status': InvoiceStatus.ERROR, 'error_msg': error_msg},
             '$unset': {'active_order_id': ''}},
        )

    @classmethod
    def mark_voided(cls, inv_id: str, reason: str, operator: str):
        cls._col().update_one(
            {'_id': ObjectId(inv_id)},
            {'$set': {
                'status':     InvoiceStatus.VOIDED,
                'void_reason': reason,
                'voided_by':  operator,
                'voided_at':  datetime.utcnow(),
            }, '$unset': {'active_order_id': ''}},
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
        """
        [A3] 優先回傳開立中／已開立的那張；沒有時回傳最新一筆（error／voided）。
        原本 find_one 不排序，訂單有多筆發票時可能取到作廢那筆而讓重複開立通過檢查。
        """
        active = cls._col().find_one(
            {'order_id': order_id,
             'status': {'$in': [InvoiceStatus.PENDING, InvoiceStatus.ISSUED]}},
            sort=[('created_at', -1)])
        if active:
            return _fmt(active)
        return _fmt(cls._col().find_one({'order_id': order_id}, sort=[('created_at', -1)]))

    @classmethod
    def find_all(cls, status: str = None, date_from: datetime = None,
                 date_to: datetime = None, limit: int = 100,
                 store_filter: dict = None, offset: int = 0) -> list:
        """store_filter：[A2] 例 {'store_id': ...} 或含舊資料的 $or 條件"""
        q = dict(store_filter or {})
        if status:
            q['status'] = status
        if date_from or date_to:
            q['created_at'] = {}
            if date_from:
                q['created_at']['$gte'] = date_from
            if date_to:
                q['created_at']['$lte'] = date_to
        docs = cls._col().find(q).sort([('created_at', -1), ('_id', -1)]).skip(max(0, offset)).limit(limit)   # [U3]
        return [_fmt(d) for d in docs]
