"""
外送訂單狀態變更與庫存／銷售副作用（[D1] [D2]）

所有會改變外送訂單狀態的入口（後台手動、webhook 推播、主動拉單、自動接單）
一律經過這裡，確保規則一致：

- 狀態只依合法轉移表變更（DeliveryOrderStatus.is_valid_transition），
  compare-and-set 確保並發推播時副作用只執行一次
- 由「未接單」進入「已接單」狀態（confirmed／preparing／ready／picked_up／delivered，
  平台常跳過中間狀態）→ 建立 POS 銷售紀錄並依品項對應扣庫存
- 由「已接單」轉為 cancelled → 作廢該銷售紀錄並依庫存異動帳原樣回補
"""
import logging

from pymongo.errors import DuplicateKeyError

from src.constants import DeliveryOrderStatus as S
from src.models.delivery import DeliveryOrder, DeliverySettings

logger = logging.getLogger(__name__)


def create_sale_for_order(order: dict, operator: str) -> dict:
    """
    依訂單 store_ref 取「有效設定」（店家設定優先、空值回退全域），
    有 default_warehouse_id 才建立銷售紀錄並依對應扣庫存。
    回傳 {'sale_id', 'skipped_items'} 或空 dict。
    """
    settings = DeliverySettings.effective(order['platform'], order.get('store_ref'))
    wid = settings.get('default_warehouse_id', '')
    if not wid:
        logger.warning('外送訂單 %s 已接單但未設定預設倉庫，未建立銷售紀錄、未扣庫存',
                       order.get('_id'))
        return {}
    from src.models.pos import PosOrder
    result = PosOrder.create_from_delivery(order, wid, operator, settings=settings)
    return {
        'sale_id':       result.get('sale_id'),
        'skipped_items': result.get('skipped_items', []),
    }


def _apply_side_effects(oid: str, from_status: str, to_status: str, operator: str) -> dict:
    """狀態已成功轉移後執行副作用，回傳要給呼叫端的資訊。"""
    was_accepted = from_status in S.ACCEPTED_STATES
    info = {}
    if not was_accepted and to_status in S.ACCEPTED_STATES:
        order = DeliveryOrder.find_by_id(oid)
        if order:
            try:
                info.update(create_sale_for_order(order, operator))
            except Exception as e:   # 不影響狀態變更本身，但必須留下紀錄
                logger.exception('外送訂單 %s 建立銷售紀錄失敗：%s', oid, e)
    elif was_accepted and to_status == S.CANCELLED:
        order = DeliveryOrder.find_by_id(oid)
        if order:
            from src.models.pos import PosOrder
            try:
                v = PosOrder.void_delivery_sale(order['_id'], order['platform'], operator)
                info.update({'voided_sale_id': v['sale_id'],
                             'restored_items': v['restored']})
            except Exception as e:
                logger.exception('外送訂單 %s 取消回沖失敗：%s', oid, e)
    return info


def change_status(oid: str, to_status: str, operator: str,
                  platform_status: str = None) -> dict:
    """
    變更外送訂單狀態並執行副作用。
    回傳 {'changed': bool, 'from_status': str|None, 'status': str, ...副作用資訊}
    相同狀態視為冪等（changed=False 但不是錯誤）；非法轉移 changed=False。
    """
    changed, from_status = DeliveryOrder.transition(
        oid, to_status, operator, platform_status=platform_status)
    result = {'changed': changed, 'from_status': from_status, 'status': to_status}
    if changed:
        effective_from = from_status if from_status in S.ALL else S.NEW
        result.update(_apply_side_effects(oid, effective_from, to_status, operator))
    return result


def ingest_normalized(normalized: dict, operator: str = 'system') -> tuple:
    """
    webhook／主動拉單共用：新單建立、舊單依平台狀態推進。
    回傳 (order_id, is_new, info)
    - 新單直接以「已接單」狀態進來（平台端已接單、或拉單時已確認）→ 立即建銷售扣庫
    - 平台狀態無法辨識（status=None）→ 新單以 new 建立；舊單不變更狀態，只記錄 platform_status
    """
    existing = DeliveryOrder.find_by_external(
        normalized['platform'], normalized.get('external_order_id', ''))
    if existing:
        to_status = normalized.get('status')
        if not to_status:
            if normalized.get('platform_status'):
                DeliveryOrder.transition(existing['_id'], existing['status'], operator,
                                         platform_status=normalized['platform_status'])
            return existing['_id'], False, {}
        return existing['_id'], False, change_status(
            existing['_id'], to_status, operator,
            platform_status=normalized.get('platform_status'))

    try:
        oid = DeliveryOrder.create_from_normalized(normalized)
    except DuplicateKeyError:
        # [A5] 並發下另一個請求（webhook 重送／主動拉單）剛建立同一張單：改走既有單的狀態推進
        existing = DeliveryOrder.find_by_external(
            normalized['platform'], normalized.get('external_order_id', ''))
        if not existing:
            raise
        info = {}
        if normalized.get('status'):
            info = change_status(existing['_id'], normalized['status'], operator,
                                 platform_status=normalized.get('platform_status'))
        return existing['_id'], False, info
    order = DeliveryOrder.find_by_id(oid)
    info = {}
    if order and order['status'] in S.ACCEPTED_STATES:
        info = _apply_side_effects(oid, S.NEW, order['status'], operator)
    return oid, True, info
