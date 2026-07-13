# [REFACTOR] 訂單狀態常數模組：集中管理散落於 app/、src/models/ 的狀態 magic string。
# 所有常數值維持原本的小寫字串（'pending' 等），API 回傳值與 DB 內容完全不變。
"""
訂單狀態常數

- OrderStatus          : 出入庫單（inbound_orders / outbound_orders）
- CustomerOrderStatus  : 顧客點單（customer_orders）
- PosOrderStatus       : POS 銷售單（pos_orders）
- DeliveryOrderStatus  : 外送平台訂單（delivery_orders）
- InvoiceStatus        : 電子發票（invoices）
"""


class OrderStatus:
    """出入庫單狀態機：pending → confirmed → completed；pending/confirmed → cancelled"""
    PENDING   = 'pending'
    CONFIRMED = 'confirmed'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

    ALL = (PENDING, CONFIRMED, COMPLETED, CANCELLED)

    # 可取消的狀態（cancel 端點的 $in 查詢條件）
    CANCELLABLE = (PENDING, CONFIRMED)

    VALID_TRANSITIONS = {
        PENDING:   (CONFIRMED, CANCELLED),
        CONFIRMED: (COMPLETED, CANCELLED),
        COMPLETED: (),
        CANCELLED: (),
    }

    @classmethod
    def is_valid_transition(cls, from_status: str, to_status: str) -> bool:
        return to_status in cls.VALID_TRANSITIONS.get(from_status, ())


class CustomerOrderStatus:
    """顧客點單狀態機：pending → processing → completed | cancelled

    [REFACTOR] VALID_TRANSITIONS 由 app/customer_order/view.py 的
    inline 狀態機驗證表遷移至此；LABELS 由 src/models/customer_order.py
    的 ORDER_STATUS_LABEL 遷移至此（原處保留別名，行為不變）。
    """
    PENDING    = 'pending'
    PROCESSING = 'processing'
    COMPLETED  = 'completed'
    CANCELLED  = 'cancelled'

    ALL = (PENDING, PROCESSING, COMPLETED, CANCELLED)

    # 廚房顯示用（find_active 的 $in 查詢條件）
    ACTIVE = (PENDING, PROCESSING)

    LABELS = {
        PENDING:    '待處理',
        PROCESSING: '處理中',
        COMPLETED:  '已完成',
        CANCELLED:  '已取消',
    }

    VALID_TRANSITIONS = {
        PENDING:    (PROCESSING, CANCELLED),
        PROCESSING: (COMPLETED, CANCELLED),
        COMPLETED:  (),
        CANCELLED:  (),
    }

    @classmethod
    def is_valid_transition(cls, from_status: str, to_status: str) -> bool:
        return to_status in cls.VALID_TRANSITIONS.get(from_status, ())


class PosOrderStatus:
    """POS 銷售單狀態：completed →（退款鎖定 refunding）→ refunded

    refunding 為退款期間的暫時鎖定狀態（防並發雙重退款），
    退款失敗會回復為 completed，故不定義嚴格的單向 transitions 表。
    """
    COMPLETED = 'completed'
    REFUNDING = 'refunding'
    REFUNDED  = 'refunded'

    ALL = (COMPLETED, REFUNDING, REFUNDED)

    # 可執行退款的狀態（refund 的 $in 查詢條件）
    REFUNDABLE = (COMPLETED, REFUNDING)

    # 歷史匯入允許的狀態（bulk_import 白名單）
    IMPORTABLE = (COMPLETED, REFUNDED)


class DeliveryOrderStatus:
    """外送平台訂單狀態。

    [REFACTOR] 狀態集合與 terminal state guard 由
    src/models/delivery.py 的 VALID_STATUSES / TERMINAL_STATES 遷移至此
    （原 model 改為引用，行為不變：終態後不可再轉移，其餘轉移不設限）。
    """
    NEW       = 'new'
    CONFIRMED = 'confirmed'
    PREPARING = 'preparing'
    READY     = 'ready'
    PICKED_UP = 'picked_up'
    DELIVERED = 'delivered'
    CANCELLED = 'cancelled'
    REFUNDED  = 'refunded'

    ALL = frozenset({NEW, CONFIRMED, PREPARING, READY,
                     PICKED_UP, DELIVERED, CANCELLED, REFUNDED})

    # 終態：進入後不可再轉移
    TERMINAL_STATES = frozenset({DELIVERED, CANCELLED})


class InvoiceStatus:
    """電子發票狀態：pending → issued → voided；開立失敗 → error"""
    PENDING = 'pending'
    ISSUED  = 'issued'
    VOIDED  = 'voided'
    ERROR   = 'error'

    ALL = (PENDING, ISSUED, VOIDED, ERROR)
