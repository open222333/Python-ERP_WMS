"""
POS 收銀 Blueprint  /pos
  POST /sale                      結帳
  GET  /sales                     查詢銷售記錄
  GET  /sales/export              匯出 CSV
  POST /sales/import              匯入 CSV / JSON（admin）
  GET  /sales/<sid>               查詢單筆
  POST /sales/<sid>/refund        退款
  GET  /payment-methods           取得付款方式
  PUT  /payment-methods           更新付款方式（admin）
  GET  /linepay-settings          取得 LINE Pay 設定
  PUT  /linepay-settings          更新 LINE Pay 設定（admin）
  GET  /zpay-settings             取得全支付設定
  PUT  /zpay-settings             更新全支付設定（admin）
  GET  /summary                   銷售報表（支援 day / week / month / year）
"""
import csv
import io
import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, render_template, Response, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity

from bson import ObjectId
from src.mongo import get_db
from src.models.pos import PosOrder
from src.models.log import Log
from src.permissions import require_role

logger  = logging.getLogger(__name__)
app_pos = Blueprint('app_pos', __name__)


# ── 第三方支付實例（依系統設定）────────────────────────────────
def _get_linepay():
    from src.payment_providers.linepay import LinePayCPM
    from src.models.settings import SystemSettings
    s = SystemSettings.get('linepay_settings') or {}
    channel_id     = s.get('channel_id', '').strip()
    channel_secret = s.get('channel_secret', '').strip()
    sandbox        = s.get('sandbox', True)
    if not channel_id or not channel_secret:
        raise ValueError('尚未設定 LINE Pay Channel ID / Secret，請先至付款設定填寫')
    return LinePayCPM(channel_id=channel_id, channel_secret=channel_secret, sandbox=sandbox)


def _get_zpay():
    from src.payment_providers.zpay import ZPayCPM
    from src.models.settings import SystemSettings
    s = SystemSettings.get('zpay_settings') or {}
    merchant_id     = s.get('merchant_id', '').strip()
    merchant_secret = s.get('merchant_secret', '').strip()
    sandbox         = s.get('sandbox', True)
    if not merchant_id or not merchant_secret:
        raise ValueError('尚未設定全支付 Merchant ID / Secret，請先至付款設定填寫')
    return ZPayCPM(merchant_id=merchant_id, merchant_secret=merchant_secret, sandbox=sandbox)



@app_pos.route('/')
def index():
    """POS 收銀頁面"""
    from src import ADMIN_TITLE
    return render_template('pos/index.html', admin_title=ADMIN_TITLE)


@app_pos.route('/manifest.json')
def manifest():
    """PWA manifest — 鎖定橫向方向"""
    return jsonify({
        'name': 'POS 收銀',
        'short_name': 'POS',
        'start_url': '/pos/',
        'display': 'standalone',
        'orientation': 'landscape',
        'background_color': '#1e2235',
        'theme_color': '#1e2235',
        'icons': [],
    })


# ─────────────────────────────────────────────────────────────
#  銷售
# ─────────────────────────────────────────────────────────────

@app_pos.route('/sale', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator', 'cashier')
def create_sale():
    """
    建立 POS 銷售（結帳）
    ---
    tags:
      - POS
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [warehouse_id, items, payment]
          properties:
            warehouse_id:  {type: string}
            items:         {type: array}
            payment:       {type: object}
            discount:      {type: number}
            remark:        {type: string}
    responses:
      201: {description: 結帳成功}
      400: {description: 庫存不足或資料有誤}
    """
    data         = request.get_json(silent=True) or {}
    warehouse_id = data.get('warehouse_id', '').strip()
    items        = data.get('items', [])
    payment      = data.get('payment', {})
    discount     = float(data.get('discount', 0))
    remark       = data.get('remark', '')

    if not warehouse_id:
        return jsonify({'success': False, 'message': '請指定倉庫'}), 400
    if not items:
        return jsonify({'success': False, 'message': '購物車為空'}), 400
    if not payment.get('type'):
        return jsonify({'success': False, 'message': '請選擇付款方式'}), 400

    # ── LINE Pay 全支付：先向 API 扣款，成功才記帳 ────────────────
    if payment.get('type') == 'linepay':
        linepay_key = str(payment.get('linepay_key', '')).strip()
        if not linepay_key:
            return jsonify({'success': False, 'message': '請掃描顧客 LINE Pay 付款條碼'}), 400
        subtotal_for_lp = sum(
            float(i.get('unit_price', 0)) * int(i.get('quantity', 1)) for i in items
        )
        charge_amount = max(0, int(round(subtotal_for_lp - discount, 0)))
        # 用 cashier + timestamp 組成唯一 orderId 傳給 LINE Pay
        lp_order_id = f"POS{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{get_jwt_identity()[:4].upper()}"
        try:
            lp = _get_linepay()
            lp_resp = lp.charge(
                one_time_key=linepay_key,
                order_id=lp_order_id,
                amount=charge_amount,
            )
        except ValueError as ve:
            return jsonify({'success': False, 'message': str(ve)}), 400
        except Exception as e:
            logger.exception('LINE Pay charge failed')
            return jsonify({'success': False, 'message': f'LINE Pay 連線失敗：{e}'}), 500
        if lp_resp.get('returnCode') != '0000':
            msg = lp_resp.get('returnMessage', 'LINE Pay 付款失敗')
            return jsonify({'success': False, 'message': f'LINE Pay：{msg}', 'lp_code': lp_resp.get('returnCode')}), 400
        # 將交易 ID 存入 payment dict，model 層會寫入訂單
        payment['linepay_transaction_id'] = str(lp_resp.get('info', {}).get('transactionId', ''))

    # ── 全支付：先向 API 扣款，成功才記帳 ──────────────────────────
    if payment.get('type') == 'zpay':
        zpay_code = str(payment.get('linepay_key', '')).strip()
        if not zpay_code:
            return jsonify({'success': False, 'message': '請掃描顧客全支付付款條碼'}), 400
        subtotal_zp   = sum(float(i.get('unit_price', 0)) * int(i.get('quantity', 1)) for i in items)
        charge_amount = max(0, int(round(subtotal_zp - discount, 0)))
        zp_order_id   = f"POS{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{get_jwt_identity()[:4].upper()}"
        try:
            zp = _get_zpay()
            zp_resp = zp.charge(qr_code=zpay_code, order_id=zp_order_id, amount=charge_amount)
        except ValueError as ve:
            return jsonify({'success': False, 'message': str(ve)}), 400
        except Exception as e:
            logger.exception('ZPay charge failed')
            return jsonify({'success': False, 'message': f'全支付連線失敗：{e}'}), 500
        if zp_resp.get('returnCode') != '0000':
            msg = zp_resp.get('returnMessage', '全支付付款失敗')
            return jsonify({'success': False, 'message': f'全支付：{msg}'}), 400
        payment['linepay_transaction_id'] = str(zp_resp.get('transactionId', ''))

    result = PosOrder.create_sale(
        warehouse_id=warehouse_id, items=items, payment=payment,
        discount=discount, cashier=get_jwt_identity(), remark=remark,
    )
    if not result['success']:
        return jsonify({'success': False, 'message': result['error']}), 400

    order = result['order']
    Log.create(get_jwt_identity(), 'POS 結帳',
               f"order_no={order['order_no']} total={order['total_amount']}")
    return jsonify({'success': True, 'order': order}), 201


@app_pos.route('/sales', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator', 'cashier')
def list_sales():
    """
    查詢銷售記錄
    ---
    tags:
      - POS
    security:
      - Bearer: []
    parameters:
      - {in: query, name: date_from,  type: string, description: "YYYY-MM-DD"}
      - {in: query, name: date_to,    type: string, description: "YYYY-MM-DD"}
      - {in: query, name: cashier,    type: string}
      - {in: query, name: status,     type: string, enum: [completed, refunded]}
      - {in: query, name: source,     type: string, description: "pos/ubereats/foodpanda"}
      - {in: query, name: limit,      type: integer}
    responses:
      200: {description: 成功}
    """
    date_from_str = request.args.get('date_from', '')
    date_to_str   = request.args.get('date_to',   '')
    cashier       = request.args.get('cashier',    '')
    status        = request.args.get('status',     '')
    source        = request.args.get('source',     '')
    limit         = int(request.args.get('limit', 200))

    date_from = datetime.strptime(date_from_str, '%Y-%m-%d') if date_from_str else None
    date_to   = datetime.strptime(date_to_str + ' 23:59:59', '%Y-%m-%d %H:%M:%S') if date_to_str else None

    data = PosOrder.find_all(
        date_from=date_from, date_to=date_to,
        cashier=cashier or None, status=status or None,
        source=source or None, limit=limit,
    )
    return jsonify({'success': True, 'data': data})


# ─── 匯出 CSV ─────────────────────────────────────────────────

@app_pos.route('/sales/export', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator', 'cashier')
def export_sales():
    """
    匯出銷售記錄為 CSV（不限筆數，依目前篩選條件）
    ---
    tags:
      - POS
    security:
      - Bearer: []
    parameters:
      - {in: query, name: date_from,  type: string}
      - {in: query, name: date_to,    type: string}
      - {in: query, name: cashier,    type: string}
      - {in: query, name: status,     type: string}
      - {in: query, name: source,     type: string}
    responses:
      200: {description: CSV 檔案下載}
    """
    date_from_str = request.args.get('date_from', '')
    date_to_str   = request.args.get('date_to',   '')
    cashier       = request.args.get('cashier',    '')
    status        = request.args.get('status',     '')
    source        = request.args.get('source',     '')

    date_from = datetime.strptime(date_from_str, '%Y-%m-%d') if date_from_str else None
    date_to   = datetime.strptime(date_to_str + ' 23:59:59', '%Y-%m-%d %H:%M:%S') if date_to_str else None

    rows = PosOrder.find_all(
        date_from=date_from, date_to=date_to,
        cashier=cashier or None, status=status or None,
        source=source or None, limit=0,   # 0 = 無上限
    )

    HEADERS = [
        'order_no', 'source', 'warehouse_name', 'cashier',
        'items_count', 'subtotal', 'discount', 'total_amount',
        'payment_type', 'cash_amount', 'change_amount',
        'status', 'remark', 'created_at',
    ]

    def generate():
        buf = io.StringIO()
        w   = csv.writer(buf)
        w.writerow(HEADERS)
        yield buf.getvalue(); buf.seek(0); buf.truncate()
        for r in rows:
            items_count = sum(i.get('quantity', 0) for i in (r.get('items') or []))
            w.writerow([
                r.get('order_no', ''),
                r.get('source', 'pos'),
                r.get('warehouse_name', ''),
                r.get('cashier', ''),
                items_count,
                r.get('subtotal', 0),
                r.get('discount', 0),
                r.get('total_amount', 0),
                r.get('payment_type', ''),
                r.get('cash_amount', 0),
                r.get('change_amount', 0),
                r.get('status', ''),
                r.get('remark', ''),
                r.get('created_at', ''),
            ])
            yield buf.getvalue(); buf.seek(0); buf.truncate()

    ts       = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f'pos_sales_{ts}.csv'
    return Response(
        stream_with_context(generate()),
        mimetype='text/csv; charset=utf-8-sig',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'X-Accel-Buffering': 'no',
        },
    )


# ─── 匯入 CSV / JSON ──────────────────────────────────────────

@app_pos.route('/sales/import', methods=['POST'])
@jwt_required()
@require_role('admin')
def import_sales():
    """
    批次匯入歷史銷售記錄（不執行庫存扣減，僅限 admin）
    ---
    tags:
      - POS
    security:
      - Bearer: []
    consumes:
      - multipart/form-data
    parameters:
      - {in: formData, name: file, type: file, description: "CSV 或 JSON 檔案"}
    responses:
      200: {description: 匯入成功，回傳 inserted 筆數}
      400: {description: 格式錯誤}
    """
    rows: list = []

    if request.files.get('file'):
        f   = request.files['file']
        raw = f.read().decode('utf-8-sig', errors='replace')
        if f.filename.lower().endswith('.json'):
            try:
                rows = json.loads(raw)
                if not isinstance(rows, list):
                    return jsonify({'success': False, 'message': 'JSON 必須為陣列'}), 400
            except Exception:
                return jsonify({'success': False, 'message': 'JSON 格式錯誤'}), 400
        else:
            reader = csv.DictReader(io.StringIO(raw))
            rows   = list(reader)
    else:
        body = request.get_json(silent=True)
        if isinstance(body, list):
            rows = body
        elif isinstance(body, dict) and 'data' in body:
            rows = body['data']

    if not rows:
        return jsonify({'success': False, 'message': '無可匯入的資料'}), 400

    inserted = PosOrder.bulk_import(rows)
    operator = get_jwt_identity()
    Log.create(operator, 'POS 銷售匯入', f'inserted={inserted}')
    return jsonify({'success': True, 'inserted': inserted})


# ─── 查詢單筆 / 退款 ──────────────────────────────────────────

@app_pos.route('/sales/<sid>', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator', 'cashier')
def get_sale(sid):
    """
    查詢單筆銷售
    ---
    tags:
      - POS
    security:
      - Bearer: []
    parameters:
      - {in: path, name: sid, type: string, required: true}
    responses:
      200: {description: 成功}
      404: {description: 不存在}
    """
    order = PosOrder.find_by_id(sid)
    if not order:
        return jsonify({'success': False, 'message': '銷售單不存在'}), 404
    return jsonify({'success': True, 'data': order})


@app_pos.route('/sales/<sid>/refund', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def refund_sale(sid):
    """
    退款（限 admin / operator）
    ---
    tags:
      - POS
    security:
      - Bearer: []
    parameters:
      - {in: path, name: sid, type: string, required: true}
      - in: body
        name: body
        schema:
          properties:
            reason: {type: string}
    responses:
      200: {description: 退款成功}
      400: {description: 失敗}
    """
    data   = request.get_json(silent=True) or {}
    reason = data.get('reason', '').strip()

    # ── 原子搶佔退款名額（completed → refunding），防止並發雙重退款 ──
    _orders_col = get_db()['pos_orders']
    order = _orders_col.find_one_and_update(
        {'_id': ObjectId(sid), 'status': 'completed'},
        {'$set': {'status': 'refunding'}},
        return_document=True,
    )
    if not order:
        return jsonify({'success': False, 'message': '銷售單不存在或已退款'}), 400

    if order.get('payment_type') in ('linepay', 'zpay'):
        txn_id  = order.get('linepay_transaction_id', '')
        pay_type = order.get('payment_type')
        if txn_id:
            try:
                if pay_type == 'linepay':
                    provider   = _get_linepay()
                    name       = 'LINE Pay'
                else:
                    provider   = _get_zpay()
                    name       = '全支付'
                ref_resp = provider.refund(txn_id, round(order['total_amount']))
                if ref_resp.get('returnCode') != '0000':
                    msg = ref_resp.get('returnMessage', '退款失敗')
                    _orders_col.update_one({'_id': ObjectId(sid)}, {'$set': {'status': 'completed'}})
                    return jsonify({'success': False, 'message': f'{name} 退款失敗：{msg}'}), 400
            except ValueError as ve:
                _orders_col.update_one({'_id': ObjectId(sid)}, {'$set': {'status': 'completed'}})
                return jsonify({'success': False, 'message': str(ve)}), 400
            except Exception as e:
                logger.exception('%s refund failed', pay_type)
                _orders_col.update_one({'_id': ObjectId(sid)}, {'$set': {'status': 'completed'}})
                return jsonify({'success': False, 'message': f'{name} 退款連線失敗：{e}'}), 500

    try:
        result = PosOrder.refund(sid, reason, operator=get_jwt_identity())
    except Exception as e:
        logger.exception('PosOrder.refund failed for sid=%s', sid)
        _orders_col.update_one({'_id': ObjectId(sid)}, {'$set': {'status': 'completed'}})
        return jsonify({'success': False, 'message': f'退款處理失敗：{e}'}), 500
    if not result['success']:
        _orders_col.update_one({'_id': ObjectId(sid)}, {'$set': {'status': 'completed'}})
        return jsonify({'success': False, 'message': result['error']}), 400
    Log.create(get_jwt_identity(), 'POS 退款', f'sale_id={sid} reason={reason}')
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  POS 付款方式設定
# ─────────────────────────────────────────────────────────────

_DEFAULT_PAY_METHODS = [
    {'id': 'cash', 'label': '現金', 'enabled': True, 'has_cash': True, 'sort_order': 0},
]


def _sync_payment_method(pay_id: str, default_label: str, enabled: bool) -> None:
    """
    將第三方支付付款方式與 pos_payment_methods 清單同步。

    規則：
      - enabled=True：清單中已存在同 id → 只更新 enabled=True；
                      不存在 → 新增一筆。
      - enabled=False：清單中已存在同 id → 只更新 enabled=False；
                       不存在 → 不新增（停用不需要加入清單）。
    """
    from src.models.settings import SystemSettings
    methods = SystemSettings.get('pos_payment_methods', _DEFAULT_PAY_METHODS)
    match   = next((m for m in methods if m.get('id') == pay_id), None)

    if match:
        if match.get('enabled') != enabled:
            match['enabled'] = enabled
            SystemSettings.set('pos_payment_methods', methods)
    elif enabled:
        methods.append({
            'id':         pay_id,
            'label':      default_label,
            'enabled':    True,
            'has_cash':   False,
            'sort_order': len(methods),
        })
        SystemSettings.set('pos_payment_methods', methods)


@app_pos.route('/payment-methods', methods=['GET'])
@jwt_required()
def get_payment_methods():
    """取得 POS 付款方式清單"""
    from src.models.settings import SystemSettings
    methods = SystemSettings.get('pos_payment_methods', _DEFAULT_PAY_METHODS)
    return jsonify({'success': True, 'data': methods})


@app_pos.route('/payment-methods', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_payment_methods():
    """更新 POS 付款方式（僅限 admin）"""
    from src.models.settings import SystemSettings
    data      = request.get_json(silent=True) or {}
    raw       = data.get('methods', [])
    validated = []
    for i, m in enumerate(raw):
        mid   = str(m.get('id', '')).strip()
        label = str(m.get('label', '')).strip()
        if not mid or not label:
            continue
        validated.append({
            'id':         mid,
            'label':      label,
            'enabled':    bool(m.get('enabled', True)),
            'has_cash':   bool(m.get('has_cash', False)),
            'sort_order': int(m.get('sort_order', i)),
        })
    if not validated:
        return jsonify({'success': False, 'message': '至少需要一種付款方式'}), 400
    SystemSettings.set('pos_payment_methods', validated)
    Log.create(get_jwt_identity(), '更新 POS 付款方式',
               ', '.join(f"{m['label']}({'啟用' if m['enabled'] else '停用'})" for m in validated))
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  LINE Pay 設定
# ─────────────────────────────────────────────────────────────

@app_pos.route('/linepay-settings', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator')
def get_linepay_settings():
    """
    取得 LINE Pay 設定（channel_secret 回傳遮蔽值）
    ---
    tags:
      - POS
    security:
      - Bearer: []
    responses:
      200: {description: 成功}
    """
    from src.models.settings import SystemSettings
    s = SystemSettings.get('linepay_settings') or {}
    return jsonify({'success': True, 'data': {
        'enabled':        s.get('enabled',        False),
        'channel_id':     s.get('channel_id',     ''),
        'channel_secret': '******' if s.get('channel_secret') else '',
        'sandbox':        s.get('sandbox',        True),
    }})


@app_pos.route('/linepay-settings', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_linepay_settings():
    """
    更新 LINE Pay 設定（僅限 admin）
    ---
    tags:
      - POS
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          properties:
            enabled:        {type: boolean}
            channel_id:     {type: string}
            channel_secret: {type: string}
            sandbox:        {type: boolean}
    responses:
      200: {description: 成功}
    """
    from src.models.settings import SystemSettings
    body     = request.get_json(silent=True) or {}
    existing = SystemSettings.get('linepay_settings') or {}

    secret_input = str(body.get('channel_secret', '')).strip()
    channel_secret = existing.get('channel_secret', '') \
        if secret_input in ('', '******') else secret_input

    updated = {
        'enabled':        bool(body.get('enabled',    existing.get('enabled', False))),
        'channel_id':     str(body.get('channel_id',  existing.get('channel_id', ''))).strip(),
        'channel_secret': channel_secret,
        'sandbox':        bool(body.get('sandbox',    existing.get('sandbox', True))),
    }
    SystemSettings.set('linepay_settings', updated)

    _sync_payment_method('linepay', 'LINE Pay', updated['enabled'])

    Log.create(get_jwt_identity(), '更新 LINE Pay 設定',
               f"enabled={updated['enabled']} sandbox={updated['sandbox']}")
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  全支付設定
# ─────────────────────────────────────────────────────────────

@app_pos.route('/zpay-settings', methods=['GET'])
@jwt_required()
def get_zpay_settings():
    """取得全支付設定（merchant_secret 遮蔽）"""
    from src.models.settings import SystemSettings
    s = SystemSettings.get('zpay_settings') or {}
    return jsonify({'success': True, 'data': {
        'enabled':         s.get('enabled',         False),
        'merchant_id':     s.get('merchant_id',     ''),
        'merchant_secret': '******' if s.get('merchant_secret') else '',
        'sandbox':         s.get('sandbox',         True),
    }})


@app_pos.route('/zpay-settings', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_zpay_settings():
    """更新全支付設定（僅限 admin）"""
    from src.models.settings import SystemSettings
    body     = request.get_json(silent=True) or {}
    existing = SystemSettings.get('zpay_settings') or {}

    secret_input    = str(body.get('merchant_secret', '')).strip()
    merchant_secret = existing.get('merchant_secret', '') \
        if secret_input in ('', '******') else secret_input

    updated = {
        'enabled':         bool(body.get('enabled',      existing.get('enabled', False))),
        'merchant_id':     str(body.get('merchant_id',   existing.get('merchant_id', ''))).strip(),
        'merchant_secret': merchant_secret,
        'sandbox':         bool(body.get('sandbox',      existing.get('sandbox', True))),
    }
    SystemSettings.set('zpay_settings', updated)

    _sync_payment_method('zpay', '全支付', updated['enabled'])

    Log.create(get_jwt_identity(), '更新全支付設定',
               f"enabled={updated['enabled']} sandbox={updated['sandbox']}")
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  銷售報表（日 / 週 / 月 / 年）
# ─────────────────────────────────────────────────────────────

def _period_range(period: str, ref: datetime):
    """依 period 與參考日期計算 (start, end) 的 datetime tuple。"""
    if period == 'week':
        # ISO 週：週一為開始
        monday = ref - timedelta(days=ref.weekday())
        start  = datetime(monday.year, monday.month, monday.day)
        end    = start + timedelta(days=7) - timedelta(seconds=1)
    elif period == 'month':
        start = datetime(ref.year, ref.month, 1)
        if ref.month == 12:
            end = datetime(ref.year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end = datetime(ref.year, ref.month + 1, 1) - timedelta(seconds=1)
    elif period == 'year':
        start = datetime(ref.year, 1, 1)
        end   = datetime(ref.year + 1, 1, 1) - timedelta(seconds=1)
    else:  # day（預設）
        start = datetime(ref.year, ref.month, ref.day)
        end   = start + timedelta(days=1) - timedelta(seconds=1)
    return start, end


@app_pos.route('/summary', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator', 'cashier')
def sales_summary():
    """
    銷售報表
    ---
    tags:
      - POS
    security:
      - Bearer: []
    parameters:
      - in: query
        name: period
        type: string
        enum: [day, week, month, year]
        default: day
        description: "報表期間"
      - in: query
        name: date
        type: string
        description: "參考日期 YYYY-MM-DD（day/week 用）"
      - in: query
        name: month
        type: string
        description: "YYYY-MM（month 模式時優先使用）"
      - in: query
        name: year
        type: integer
        description: "YYYY（year 模式時優先使用）"
    responses:
      200:
        description: 成功，包含 summary + breakdown（非 day 模式）+ orders（day 模式）
    """
    period = request.args.get('period', 'day').lower()

    # ── 解析參考日期 ──────────────────────────────
    try:
        if period == 'month' and request.args.get('month'):
            ref = datetime.strptime(request.args.get('month') + '-01', '%Y-%m-%d')
        elif period == 'year' and request.args.get('year'):
            ref = datetime(int(request.args.get('year')), 1, 1)
        else:
            date_str = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
            ref      = datetime.strptime(date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': '日期格式錯誤'}), 400

    date_from, date_to = _period_range(period, ref)

    # ── 查詢已完成訂單 ─────────────────────────────
    orders = PosOrder.find_all(date_from=date_from, date_to=date_to,
                               status='completed', limit=0)

    total_orders   = len(orders)
    total_amount   = sum(o['total_amount']          for o in orders)
    total_discount = sum(o.get('discount', 0)       for o in orders)
    cash_total     = sum(o.get('cash_amount', 0)    for o in orders
                        if o.get('payment_type') in ('cash', 'mixed'))
    card_total     = sum(o.get('card_amount', 0)    for o in orders
                        if o.get('payment_type') in ('card', 'mixed'))

    summary = {
        'period':         period,
        'date_from':      date_from.strftime('%Y-%m-%d'),
        'date_to':        date_to.strftime('%Y-%m-%d'),
        'total_orders':   total_orders,
        'total_amount':   round(total_amount,   2),
        'total_discount': round(total_discount, 2),
        'cash_total':     round(cash_total,     2),
        'card_total':     round(card_total,     2),
    }

    # ── 依期間決定明細格式 ────────────────────────
    if period == 'day':
        # 日模式：回傳個別訂單
        summary['date']   = ref.strftime('%Y-%m-%d')
        summary['orders'] = orders
    else:
        # 週/月模式：依日彙總；年模式：依月彙總
        key_fn = (lambda o: o['created_at'][:7]) if period == 'year' \
                 else (lambda o: o['created_at'][:10])

        grp: dict = defaultdict(lambda: {'orders': 0, 'amount': 0.0, 'discount': 0.0})
        for o in orders:
            k = key_fn(o)
            grp[k]['orders']   += 1
            grp[k]['amount']   += o['total_amount']
            grp[k]['discount'] += o.get('discount', 0)

        summary['breakdown'] = [
            {'period': k, 'orders': v['orders'],
             'amount': round(v['amount'], 2),
             'discount': round(v['discount'], 2)}
            for k, v in sorted(grp.items())
        ]

    return jsonify({'success': True, 'data': summary})
