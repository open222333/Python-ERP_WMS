# [REFACTOR] InboundOrder 改繼承 src/models/order_base.py 的 OrderBase，
#            共用 CRUD / 明細操作 / 狀態轉移；此處僅保留 inbound 差異
#            （IN 單號前綴、supplier 欄位、received_qty）。公開介面不變。
from src.models.order_base import OrderBase, _fmt_order  # noqa: F401  (相容舊 import)


class InboundOrder(OrderBase):
    COLLECTION = 'inbound_orders'
    ORDER_NO_PREFIX = 'IN'
    COUNTER_PREFIX = 'inbound'
    PARTY_FIELD = 'supplier'
    DONE_QTY_FIELD = 'received_qty'

    @classmethod
    def complete(cls, oid: str, completed_by: str, received_qtys: dict = None,
                session=None) -> dict:
        """
        完成入庫：更新 received_qty，回傳 items 清單供呼叫者更新庫存
        received_qtys: {item_id: qty} 若為 None 則使用 expected_qty
        session: [OPT-N1] 可選 pymongo ClientSession，交易內呼叫時傳入
        """
        return super().complete(oid, completed_by, received_qtys, session=session)
