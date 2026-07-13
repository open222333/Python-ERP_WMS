# [REFACTOR] OutboundOrder 改繼承 src/models/order_base.py 的 OrderBase，
#            共用 CRUD / 明細操作 / 狀態轉移；此處僅保留 outbound 差異
#            （OUT 單號前綴、customer 欄位、shipped_qty）。公開介面不變。
#            complete() 隨基底改為原子轉移（原本 find_one → 逐項更新 → 改狀態
#            存在並發雙重完成的競態窗口；對外回傳值語意完全相同）。
from bson import ObjectId

from src.models.order_base import OrderBase, _fmt_order  # noqa: F401  (相容舊 import)


class OutboundOrder(OrderBase):
    COLLECTION = 'outbound_orders'
    ORDER_NO_PREFIX = 'OUT'
    COUNTER_PREFIX = 'outbound'
    PARTY_FIELD = 'customer'
    DONE_QTY_FIELD = 'shipped_qty'

    @classmethod
    def find_by_id(cls, oid: str) -> dict:
        # 保留原行為：不吞 InvalidId（與 InboundOrder 的防禦版不同），
        # 非法 ObjectId 直接拋例外，避免改變 API 回應行為。
        return _fmt_order(cls._col().find_one({'_id': ObjectId(oid)}))

    @classmethod
    def complete(cls, oid: str, completed_by: str, shipped_qtys: dict = None,
                session=None) -> dict:
        """
        完成出庫：更新 shipped_qty，回傳 items 清單供呼叫者扣減庫存
        shipped_qtys: {item_id: qty}
        session: [OPT-N1] 可選 pymongo ClientSession，交易內呼叫時傳入
        """
        return super().complete(oid, completed_by, shipped_qtys, session=session)
