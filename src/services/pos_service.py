# [REFACTOR] POS 結帳/退款業務邏輯自 app/pos/view.py 抽出至 Service 層。
#            view 僅保留 HTTP 相關（request 解析、jsonify）；本模組負責：
#            輸入驗證、第三方支付（LINE Pay / 全支付）扣款與退款、
#            庫存原子扣減協調（委派 PosOrder.create_sale / PosOrder.refund，
#            原子性與失敗回滾語意逐字保留，參見 docs/FIXES.md）、
#            訂單寫入與操作 Log。所有錯誤訊息、狀態碼與原 view 完全一致。
"""
POS Service 層

介面（回傳 (payload_dict, http_status_code)，view 端 jsonify(payload), status 即可）：
  PosService.checkout(data, operator) : POST /pos/sale 結帳
  PosService.refund(sid, reason, operator) : POST /pos/sales/<sid>/refund 退款

注意：checkout / refund 需在 Flask request context 內呼叫
（store_id 解析依賴 JWT claims：get_jwt / get_current_store_id）。
"""
import logging
from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from flask_jwt_extended import get_jwt

from src.mongo import get_db
from src.models.pos import PosOrder
from src.models.log import Log
from src.permissions import get_current_store_id
from src.constants import PosOrderStatus

logger = logging.getLogger(__name__)


# ── 第三方支付實例（依系統設定）────────────────────────────────
# [REFACTOR] 自 app/pos/view.py 原樣搬移（原 _get_linepay / _get_zpay）
def get_linepay():
    from src.payment_providers.linepay import LinePayCPM
    from src.models.settings import SystemSettings
    s = SystemSettings.get('linepay_settings') or {}
    channel_id     = s.get('channel_id', '').strip()
    channel_secret = s.get('channel_secret', '').strip()
    sandbox        = s.get('sandbox', True)
    if not channel_id or not channel_secret:
        raise ValueError('尚未設定 LINE Pay Channel ID / Secret，請先至付款設定填寫')
    return LinePayCPM(channel_id=channel_id, channel_secret=channel_secret, sandbox=sandbox)


def get_zpay():
    from src.payment_providers.zpay import ZPayCPM
    from src.models.settings import SystemSettings
    s = SystemSettings.get('zpay_settings') or {}
    merchant_id     = s.get('merchant_id', '').strip()
    merchant_secret = s.get('merchant_secret', '').strip()
    sandbox         = s.get('sandbox', True)
    if not merchant_id or not merchant_secret:
        raise ValueError('尚未設定全支付 Merchant ID / Secret，請先至付款設定填寫')
    return ZPayCPM(merchant_id=merchant_id, merchant_secret=merchant_secret, sandbox=sandbox)


class PosService:
    """POS 結帳 / 退款協調邏輯（原 app/pos/view.py 的 create_sale / refund_sale 本體）"""

    # ─────────────────────────────────────────────────────────
    #  結帳
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def checkout(data: dict, operator: str):
        """
        建立 POS 銷售（結帳）。

        data     : request body dict（warehouse_id / items / payment / discount / remark / store_id）
        operator : 收銀員帳號（JWT identity）
        回傳 (payload: dict, status_code: int)
        """
        warehouse_id = data.get('warehouse_id', '').strip()
        items        = data.get('items', [])
        payment      = data.get('payment', {})
        try:
            discount = float(data.get('discount', 0))
        except (ValueError, TypeError):
            return {'success': False, 'message': '折扣格式錯誤'}, 400
        if discount < 0:
            return {'success': False, 'message': '折扣不得為負數'}, 400
        remark       = data.get('remark', '')

        if not warehouse_id:
            return {'success': False, 'message': '請指定倉庫'}, 400
        if not items:
            return {'success': False, 'message': '購物車為空'}, 400
        if not payment.get('type'):
            return {'success': False, 'message': '請選擇付款方式'}, 400

        # ── LINE Pay 全支付：先向 API 扣款，成功才記帳 ────────────────
        if payment.get('type') == 'linepay':
            linepay_key = str(payment.get('linepay_key', '')).strip()
            if not linepay_key:
                return {'success': False, 'message': '請掃描顧客 LINE Pay 付款條碼'}, 400
            subtotal_for_lp = sum(
                float(i.get('unit_price', 0)) * int(i.get('quantity', 1)) for i in items
            )
            charge_amount = max(0, int(round(subtotal_for_lp - discount, 0)))
            # 用 cashier + timestamp 組成唯一 orderId 傳給 LINE Pay
            lp_order_id = f"POS{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{operator[:4].upper()}"
            try:
                lp = get_linepay()
                lp_resp = lp.charge(
                    one_time_key=linepay_key,
                    order_id=lp_order_id,
                    amount=charge_amount,
                )
            except ValueError as ve:
                return {'success': False, 'message': str(ve)}, 400
            except Exception as e:
                logger.exception('LINE Pay charge failed')
                return {'success': False, 'message': f'LINE Pay 連線失敗：{e}'}, 500
            if lp_resp.get('returnCode') != '0000':
                msg = lp_resp.get('returnMessage', 'LINE Pay 付款失敗')
                return {'success': False, 'message': f'LINE Pay：{msg}',
                        'lp_code': lp_resp.get('returnCode')}, 400
            # 將交易 ID 存入 payment dict，model 層會寫入訂單
            payment['linepay_transaction_id'] = str(lp_resp.get('info', {}).get('transactionId', ''))

        # ── 全支付：先向 API 扣款，成功才記帳 ──────────────────────────
        if payment.get('type') == 'zpay':
            zpay_code = str(payment.get('zpay_code', '')).strip()
            if not zpay_code:
                return {'success': False, 'message': '請掃描顧客全支付付款條碼'}, 400
            subtotal_zp   = sum(float(i.get('unit_price', 0)) * int(i.get('quantity', 1)) for i in items)
            charge_amount = max(0, int(round(subtotal_zp - discount, 0)))
            zp_order_id   = f"POS{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{operator[:4].upper()}"
            try:
                zp = get_zpay()
                zp_resp = zp.charge(qr_code=zpay_code, order_id=zp_order_id, amount=charge_amount)
            except ValueError as ve:
                return {'success': False, 'message': str(ve)}, 400
            except Exception as e:
                logger.exception('ZPay charge failed')
                return {'success': False, 'message': f'全支付連線失敗：{e}'}, 500
            if zp_resp.get('returnCode') != '0000':
                msg = zp_resp.get('returnMessage', '全支付付款失敗')
                return {'success': False, 'message': f'全支付：{msg}'}, 400
            payment['linepay_transaction_id'] = str(zp_resp.get('transactionId', ''))

        # 優先使用前端明確指定的 store_id（多店家帳號依 POS 設定切換）
        request_store_id = data.get('store_id', '').strip()
        if request_store_id:
            jwt_claims    = get_jwt()
            jwt_store_ids = jwt_claims.get('store_ids', [])
            if jwt_claims.get('role') == 'super_admin' or not jwt_store_ids or request_store_id in jwt_store_ids:
                store_id = request_store_id
            else:
                store_id = get_current_store_id()
        else:
            store_id = get_current_store_id()
            if not store_id:
                from src.models.settings import SystemSettings
                store_id = SystemSettings.get('pos_default_store_id') or None

        result = PosOrder.create_sale(
            warehouse_id=warehouse_id, items=items, payment=payment,
            discount=discount, cashier=operator, remark=remark,
            store_id=store_id,
        )
        if not result['success']:
            return {'success': False, 'message': result['error']}, 400

        order = result['order']
        Log.create(operator, 'POS 結帳',
                   f"order_no={order['order_no']} total={order['total_amount']}")
        return {'success': True, 'order': order}, 201

    # ─────────────────────────────────────────────────────────
    #  退款
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def refund(sid: str, reason: str, operator: str):
        """
        退款：原子搶佔退款名額 → 第三方退款（失敗回復 completed）→
        PosOrder.refund 回補庫存 → Log。

        回傳 (payload: dict, status_code: int)
        """
        try:
            sid_oid = ObjectId(sid)
        except (InvalidId, TypeError):  # [OPT] 精確捕捉 ObjectId 轉換錯誤並記錄
            logger.warning('refund_sale: 無效的銷售單 ID %r', sid)
            return {'success': False, 'message': '無效的銷售單 ID'}, 400

        # ── 原子搶佔退款名額（completed → refunding），防止並發雙重退款 ──
        _orders_col = get_db()['pos_orders']
        order = _orders_col.find_one_and_update(
            {'_id': sid_oid, 'status': PosOrderStatus.COMPLETED},
            {'$set': {'status': PosOrderStatus.REFUNDING}},
            return_document=True,
        )
        if not order:
            return {'success': False, 'message': '銷售單不存在或已退款'}, 400

        if order.get('payment_type') in ('linepay', 'zpay'):
            txn_id  = order.get('linepay_transaction_id', '')
            pay_type = order.get('payment_type')
            if txn_id:
                try:
                    if pay_type == 'linepay':
                        provider   = get_linepay()
                        name       = 'LINE Pay'
                    else:
                        provider   = get_zpay()
                        name       = '全支付'
                    ref_resp = provider.refund(txn_id, round(order['total_amount']))
                    if ref_resp.get('returnCode') != '0000':
                        msg = ref_resp.get('returnMessage', '退款失敗')
                        _orders_col.update_one({'_id': sid_oid}, {'$set': {'status': PosOrderStatus.COMPLETED}})
                        return {'success': False, 'message': f'{name} 退款失敗：{msg}'}, 400
                except ValueError as ve:
                    _orders_col.update_one({'_id': sid_oid}, {'$set': {'status': PosOrderStatus.COMPLETED}})
                    return {'success': False, 'message': str(ve)}, 400
                except Exception as e:
                    logger.exception('%s refund failed', pay_type)
                    _orders_col.update_one({'_id': sid_oid}, {'$set': {'status': PosOrderStatus.COMPLETED}})
                    return {'success': False, 'message': f'{name} 退款連線失敗：{e}'}, 500

        try:
            result = PosOrder.refund(sid, reason, operator=operator)
        except Exception as e:
            logger.exception('PosOrder.refund failed for sid=%s', sid)
            _orders_col.update_one({'_id': sid_oid}, {'$set': {'status': PosOrderStatus.COMPLETED}})
            return {'success': False, 'message': f'退款處理失敗：{e}'}, 500
        if not result['success']:
            _orders_col.update_one({'_id': sid_oid}, {'$set': {'status': PosOrderStatus.COMPLETED}})
            return {'success': False, 'message': result['error']}, 400
        Log.create(operator, 'POS 退款', f'sale_id={sid} reason={reason}')
        return {'success': True}, 200
