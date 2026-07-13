# [REFACTOR] 出入庫「完成」協調邏輯自 app/inbound/view.py、app/outbound/view.py 抽出：
#            單據狀態原子轉移（委派 Model.complete，confirmed → completed，
#            防重複完成語意逐字保留）→ 逐明細調整庫存（inbound +qty / outbound -qty）
#            → 寫入 StockMovement → 操作 Log。順序與欄位值與原 view 完全一致。
#
# [OPT-N1] 交易一致性：上述四步（改狀態→調庫存→寫 movement→寫 log）原本是四筆
# 獨立寫入，任一步之後掛掉都會讓資料不一致（例如狀態已變 completed 但庫存沒調）。
# 在支援 replica set 的環境下，改以 MongoDB multi-document transaction 包住整個
# complete 流程：中途任何例外都會 abort，等同完全沒發生過。
#
# standalone MongoDB（未啟 replica set 的既有部署）與單元測試（mongomock 不支援
# session）皆偵測不到交易能力，此時自動退回原本的循序寫入（見
# src/mongo.py::supports_transactions()，探測結果程序生命週期內快取一次）。
# 兩條路徑呼叫的是同一組 model 方法，唯一差異是是否帶入 session，行為完全一致。
"""
出入庫單 Service 層

介面（回傳完成後的單據 dict；狀態不符則回傳 None，由 view 決定錯誤訊息）：
  complete_inbound_order(oid, operator, received_qtys=None)
  complete_outbound_order(oid, operator, shipped_qtys=None)
"""
import logging

from pymongo.errors import PyMongoError

from src.models.inbound import InboundOrder
from src.models.outbound import OutboundOrder
from src.models.inventory import Inventory, StockMovement
from src.models.warehouse import Warehouse
from src.models.log import Log
from src.mongo import get_client, supports_transactions

logger = logging.getLogger(__name__)


def _apply_stock_and_log(completed: dict, oid: str, operator: str, *,
                         qty_field: str, sign: int, movement_type: str,
                         reference_type: str, remark_prefix: str,
                         log_action: str, session=None) -> None:
    """完成單據後的庫存調整、StockMovement 與操作 Log（inbound sign=+1、outbound sign=-1）。"""
    warehouse_id = completed['warehouse_id']
    w = Warehouse.find_by_id(warehouse_id, session=session)

    for item in completed.get('items', []):
        qty = item.get(qty_field, 0)
        if qty <= 0:
            continue
        before_qty, after_qty = Inventory.adjust(
            product_id=item['product_id'],
            warehouse_id=warehouse_id,
            delta=sign * qty,
            session=session,
        )
        StockMovement.create(
            product_id=item['product_id'],
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            quantity=sign * qty,
            before_qty=before_qty,
            after_qty=after_qty,
            product_name=item.get('product_name', ''),
            product_sku=item.get('product_sku', ''),
            warehouse_name=w['name'] if w else '',
            reference_type=reference_type,
            reference_id=oid,
            remark=f"{remark_prefix} {completed['order_no']}",
            operator=operator,
            session=session,
        )

    Log.create(operator, log_action, f"order_no={completed['order_no']}", session=session)


def _run_complete(complete_fn, apply_kwargs) -> dict:
    """
    [OPT-N1] 執行「狀態轉移 + 庫存/movement/log」，若環境支援交易則整包在
    transaction 內執行（中途例外自動 abort，等同未發生）；不支援則退回循序寫入。
    """
    if supports_transactions():
        try:
            client = get_client()
            with client.start_session() as session:
                with session.start_transaction():
                    completed = complete_fn(session=session)
                    if completed:
                        _apply_stock_and_log(completed, session=session, **apply_kwargs)
                    return completed
        except PyMongoError as e:
            # 交易執行失敗（例如複本集拓樸變動）：pymongo 已保證 abort，
            # 資料庫仍是交易前的一致狀態，安全地退回非交易路徑重試一次。
            logger.warning(
                '[OPT-N1] 交易執行失敗，退回非交易路徑重試：%s', e)

    completed = complete_fn(session=None)
    if completed:
        _apply_stock_and_log(completed, session=None, **apply_kwargs)
    return completed


def complete_inbound_order(oid: str, operator: str, received_qtys: dict = None) -> dict:
    """完成入庫：原子轉移 confirmed → completed，入帳庫存並記錄異動。

    回傳完成後的單據 dict；若單據不存在或非 confirmed 狀態則回傳 None
    （不會產生任何庫存異動）。
    """
    return _run_complete(
        lambda session: InboundOrder.complete(oid, operator, received_qtys, session=session),
        dict(oid=oid, operator=operator,
             qty_field='received_qty', sign=1,
             movement_type='inbound', reference_type='inbound_order',
             remark_prefix='入庫單', log_action='完成入庫'),
    )


def complete_outbound_order(oid: str, operator: str, shipped_qtys: dict = None) -> dict:
    """完成出庫：原子轉移 confirmed → completed，扣減庫存並記錄異動。

    回傳完成後的單據 dict；若單據不存在或非 confirmed 狀態則回傳 None
    （不會產生任何庫存異動）。
    """
    return _run_complete(
        lambda session: OutboundOrder.complete(oid, operator, shipped_qtys, session=session),
        dict(oid=oid, operator=operator,
             qty_field='shipped_qty', sign=-1,
             movement_type='outbound', reference_type='outbound_order',
             remark_prefix='出庫單', log_action='完成出庫'),
    )
