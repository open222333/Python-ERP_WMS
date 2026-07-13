# [REFACTOR] 各領域寫入端點的 pydantic schema
#
# 設計原則：只驗「型別與結構」，欄位一律 Optional——
# 必填與業務規則仍由端點既有手寫檢查負責（保留原錯誤訊息），
# schema 攔截的是手寫檢查涵蓋不到的畸形輸入（錯誤型別、非數字、非法 ObjectId、巢狀結構錯誤）。
from typing import List, Optional, Union

from .base import BaseSchema, LooseObjectIdStr


# ── inbound / outbound ────────────────────────────────
class InOutOrderItem(BaseSchema):
    product_id: LooseObjectIdStr = None
    expected_qty: Optional[float] = None
    qty: Optional[float] = None
    price: Optional[float] = None
    unit_price: Optional[float] = None


class InOutOrderCreate(BaseSchema):
    warehouse_id: LooseObjectIdStr = None
    supplier: Optional[str] = None
    customer: Optional[str] = None
    remark: Optional[str] = None
    items: Optional[List[InOutOrderItem]] = None


class InOutOrderItemPayload(InOutOrderItem):
    """add_item / update_item 用（欄位同品項）"""
    pass


# ── customer order（公開端點，最重要）──────────────────
class CustomerOrderItem(BaseSchema):
    item_name: Optional[str] = None
    qty: Optional[float] = None
    price: Optional[float] = None
    note: Optional[str] = None
    customizations: Optional[list] = None


class CustomerOrderCreate(BaseSchema):
    session_token: Optional[str] = None
    qr_token: Optional[str] = None
    table_no: Optional[Union[str, int]] = None
    items: Optional[List[CustomerOrderItem]] = None
    total: Optional[float] = None
    remark: Optional[str] = None
    menu_id: Optional[str] = None


# ── product ───────────────────────────────────────────
class ProductPayload(BaseSchema):
    sku: Optional[str] = None
    name: Optional[str] = None
    unit: Optional[str] = None
    price: Optional[float] = None
    cost: Optional[float] = None
    min_stock: Optional[float] = None
    max_stock: Optional[float] = None
    sort_order: Optional[int] = None
    status: Optional[str] = None
    category_id: LooseObjectIdStr = None


# ── inventory ─────────────────────────────────────────
class InventoryAdjust(BaseSchema):
    product_id: LooseObjectIdStr = None
    warehouse_id: LooseObjectIdStr = None
    location_id: LooseObjectIdStr = None
    quantity: Optional[float] = None
    remark: Optional[str] = None


class InventoryBatchItem(BaseSchema):
    product_id: LooseObjectIdStr = None
    warehouse_id: LooseObjectIdStr = None
    quantity: Optional[float] = None
    qty: Optional[float] = None


class InventoryBatch(BaseSchema):
    warehouse_id: LooseObjectIdStr = None
    items: Optional[List[InventoryBatchItem]] = None


# ── pos checkout（頂層結構）────────────────────────────
class PosPayment(BaseSchema):
    type: Optional[str] = None
    cash_amount: Optional[float] = None
    card_amount: Optional[float] = None


class PosCheckoutItem(BaseSchema):
    qty: Optional[float] = None
    price: Optional[float] = None


class PosCheckout(BaseSchema):
    warehouse_id: LooseObjectIdStr = None
    discount: Optional[float] = None
    items: Optional[List[PosCheckoutItem]] = None
    payment: Optional[PosPayment] = None
