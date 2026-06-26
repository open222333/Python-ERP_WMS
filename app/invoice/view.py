"""
電子發票 Blueprint  /invoice

  POST /issue               手動開立發票
  POST /<inv_id>/void       作廢發票
  GET  /                    查詢發票列表
  GET  /<inv_id>            查詢單筆發票
  GET  /settings            取得發票設定
  PUT  /settings            更新發票設定（admin）
  GET  /device-models       支援機型清單
  GET  /store/<sid>/terminals/          列出機台
  POST /store/<sid>/terminals/          新增機台
  PUT  /store/<sid>/terminals/<tid>     更新機台
  DELETE /store/<sid>/terminals/<tid>   刪除機台
"""
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.models.invoice import Invoice
from src.models.pos import PosOrder
from src.models.log import Log
from src.models.settings import SystemSettings
from src.permissions import require_role

logger     = logging.getLogger(__name__)
app_invoice = Blueprint('app_invoice', __name__)


# ── 支援機型清單 ────────────────────────────────────────────────
DEVICE_MODELS = [
    'EPSON TM-T88VI', 'EPSON TM-T88V', 'EPSON TM-T70II',
    'Star TSP143III', 'Star TSP654II',
    'Citizen CT-S310II', 'Custom KPM180H', 'Sewoo LK-TL212',
    '其他',
]


# ── 取得 ECPay 實例（支援機台 override）─────────────────────────
def _get_ecpay(store_id: str = None, terminal_id: str = None):
    from src.invoice_providers.ecpay import ECPayInvoice
    s = (SystemSettings.get(_invoice_key(store_id)) if store_id
         else SystemSettings.get('invoice_settings')) or {}

    merchant_id = s.get('merchant_id', '')
    hash_key    = s.get('hash_key', '')
    hash_iv     = s.get('hash_iv', '')

    if terminal_id:
        terminal = next((t for t in s.get('terminals', [])
                         if t['id'] == terminal_id), None)
        if terminal and terminal.get('ecpay_override'):
            ov = terminal['ecpay_override']
            merchant_id = ov.get('merchant_id') or merchant_id
            hash_key    = ov.get('hash_key')    or hash_key
            hash_iv     = ov.get('hash_iv')     or hash_iv

    if not merchant_id or not hash_key or not hash_iv:
        raise ValueError('尚未設定 ECPay 金鑰，請先至「發票設定」填寫')
    return ECPayInvoice(
        merchant_id=merchant_id,
        hash_key=hash_key,
        hash_iv=hash_iv,
        seller_id=s.get('seller_id', ''),
        test_mode=s.get('test_mode', True),
    )


# ─────────────────────────────────────────────────────────────
#  設定
# ─────────────────────────────────────────────────────────────

@app_invoice.route('/settings', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator')
def get_invoice_settings():
    """
    取得電子發票設定
    ---
    tags:
      - Invoice
    security:
      - Bearer: []
    responses:
      200: {description: 成功}
    """
    data = SystemSettings.get('invoice_settings') or {}
    # 不回傳敏感金鑰原文（以 ****** 遮蔽）
    safe = {
        'enabled':         data.get('enabled', False),
        'platform':        data.get('platform', 'ecpay'),
        'merchant_id':     data.get('merchant_id', ''),
        'hash_key':        '******' if data.get('hash_key') else '',
        'hash_iv':         '******' if data.get('hash_iv') else '',
        'seller_id':       data.get('seller_id', ''),
        'test_mode':       data.get('test_mode', True),
        'tax_rate':        data.get('tax_rate', 5),
        'auto_issue':      data.get('auto_issue', False),
    }
    return jsonify({'success': True, 'data': safe})


@app_invoice.route('/settings', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_invoice_settings():
    """
    更新電子發票設定（僅限 admin）
    ---
    tags:
      - Invoice
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          properties:
            enabled:     {type: boolean}
            merchant_id: {type: string}
            hash_key:    {type: string}
            hash_iv:     {type: string}
            seller_id:   {type: string}
            test_mode:   {type: boolean}
            tax_rate:    {type: integer}
            auto_issue:  {type: boolean}
    responses:
      200: {description: 成功}
    """
    body = request.get_json(silent=True) or {}
    existing = SystemSettings.get('invoice_settings') or {}

    # 若前端送來 ****** 代表未修改，保留舊值
    def _keep_if_masked(key):
        val = str(body.get(key, '')).strip()
        return existing.get(key, '') if val == '******' or val == '' else val

    updated = {
        'enabled':    bool(body.get('enabled', existing.get('enabled', False))),
        'platform':   str(body.get('platform', 'ecpay')),
        'merchant_id': str(body.get('merchant_id', existing.get('merchant_id', ''))).strip(),
        'hash_key':   _keep_if_masked('hash_key'),
        'hash_iv':    _keep_if_masked('hash_iv'),
        'seller_id':  str(body.get('seller_id', existing.get('seller_id', ''))).strip(),
        'test_mode':  bool(body.get('test_mode', existing.get('test_mode', True))),
        'tax_rate':   int(body.get('tax_rate', existing.get('tax_rate', 5))),
        'auto_issue': bool(body.get('auto_issue', existing.get('auto_issue', False))),
    }
    SystemSettings.set('invoice_settings', updated)
    Log.create(get_jwt_identity(), '更新電子發票設定',
               f"enabled={updated['enabled']} test_mode={updated['test_mode']}")
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  Per-Store 發票設定
# ─────────────────────────────────────────────────────────────

def _invoice_key(store_id: str) -> str:
    return f'invoice_settings_{store_id}'

def _safe_invoice(data: dict) -> dict:
    return {
        'enabled':        data.get('enabled', False),
        'platform':       data.get('platform', 'ecpay'),
        'merchant_id':    data.get('merchant_id', ''),
        'hash_key':       '******' if data.get('hash_key') else '',
        'hash_iv':        '******' if data.get('hash_iv') else '',
        'seller_id':      data.get('seller_id', ''),
        'test_mode':      data.get('test_mode', True),
        'tax_rate':       data.get('tax_rate', 5),
        'auto_issue':     data.get('auto_issue', False),
        'terminal_count': len(data.get('terminals', [])),
    }


def _safe_terminal(t: dict) -> dict:
    ov = t.get('ecpay_override') or {}
    return {
        'id':           t.get('id', ''),
        'name':         t.get('name', ''),
        'device_model': t.get('device_model', ''),
        'ecpay_override': {
            'merchant_id': ov.get('merchant_id', ''),
            'hash_key':    '******' if ov.get('hash_key') else '',
            'hash_iv':     '******' if ov.get('hash_iv') else '',
        } if ov else None,
    }


@app_invoice.route('/store/', methods=['GET'])
@jwt_required()
@require_role('admin')
def list_store_invoice_settings():
    from src.models.store import Store
    stores = Store.find_all()
    result = []
    for s in stores:
        data = SystemSettings.get(_invoice_key(s['_id'])) or {}
        result.append({
            'store_id':        s['_id'],
            'store_name':      s['name'],
            'store_code':      s.get('code', ''),
            'configured':      bool(data.get('merchant_id')),
            'enabled':         data.get('enabled', False),
            'platform':        data.get('platform', 'ecpay'),
            'terminal_count':  len(data.get('terminals', [])),
        })
    return jsonify({'success': True, 'data': result})


@app_invoice.route('/store/<store_id>/settings', methods=['GET'])
@jwt_required()
@require_role('admin')
def get_store_invoice_settings(store_id):
    data = SystemSettings.get(_invoice_key(store_id)) or {}
    return jsonify({'success': True, 'data': _safe_invoice(data)})


@app_invoice.route('/store/<store_id>/settings', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_store_invoice_settings(store_id):
    body = request.get_json(silent=True) or {}
    existing = SystemSettings.get(_invoice_key(store_id)) or {}

    def _keep_if_masked(key):
        val = str(body.get(key, '')).strip()
        return existing.get(key, '') if val == '******' or val == '' else val

    updated = {
        'enabled':     bool(body.get('enabled', existing.get('enabled', False))),
        'platform':    str(body.get('platform', 'ecpay')),
        'merchant_id': str(body.get('merchant_id', existing.get('merchant_id', ''))).strip(),
        'hash_key':    _keep_if_masked('hash_key'),
        'hash_iv':     _keep_if_masked('hash_iv'),
        'seller_id':   str(body.get('seller_id', existing.get('seller_id', ''))).strip(),
        'test_mode':   bool(body.get('test_mode', existing.get('test_mode', True))),
        'tax_rate':    int(body.get('tax_rate', existing.get('tax_rate', 5))),
        'auto_issue':  bool(body.get('auto_issue', existing.get('auto_issue', False))),
        'terminals':   existing.get('terminals', []),   # 機台設定由各自 API 管理，不在此覆寫
    }
    SystemSettings.set(_invoice_key(store_id), updated)
    Log.create(get_jwt_identity(), '更新店家發票設定',
               f"store={store_id} enabled={updated['enabled']}")
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  機台（Terminal）管理
# ─────────────────────────────────────────────────────────────

@app_invoice.route('/device-models', methods=['GET'])
@jwt_required()
def list_device_models():
    return jsonify({'success': True, 'data': DEVICE_MODELS})


@app_invoice.route('/store/<store_id>/terminals/', methods=['GET'])
@jwt_required()
@require_role('admin')
def list_terminals(store_id):
    data = SystemSettings.get(_invoice_key(store_id)) or {}
    return jsonify({'success': True,
                    'data': [_safe_terminal(t) for t in data.get('terminals', [])]})


@app_invoice.route('/store/<store_id>/terminals/', methods=['POST'])
@jwt_required()
@require_role('admin')
def create_terminal(store_id):
    body = request.get_json(silent=True) or {}
    data = SystemSettings.get(_invoice_key(store_id)) or {}
    terminals = data.get('terminals', [])

    # 自動產生 ID
    existing_ids = {t['id'] for t in terminals}
    n = 1
    while f'T{n:03d}' in existing_ids:
        n += 1
    tid = str(body.get('id', '')).strip() or f'T{n:03d}'

    if any(t['id'] == tid for t in terminals):
        return jsonify({'success': False, 'message': f'機台 ID {tid} 已存在'}), 409

    ov_body = body.get('ecpay_override') or {}
    ecpay_override = None
    if ov_body.get('merchant_id') or ov_body.get('hash_key') or ov_body.get('hash_iv'):
        ecpay_override = {
            'merchant_id': str(ov_body.get('merchant_id', '')).strip(),
            'hash_key':    str(ov_body.get('hash_key', '')).strip(),
            'hash_iv':     str(ov_body.get('hash_iv', '')).strip(),
        }

    terminals.append({
        'id':           tid,
        'name':         str(body.get('name', '')).strip() or tid,
        'device_model': str(body.get('device_model', '')).strip(),
        'ecpay_override': ecpay_override,
    })
    data['terminals'] = terminals
    SystemSettings.set(_invoice_key(store_id), data)
    Log.create(get_jwt_identity(), '新增發票機台', f"store={store_id} terminal={tid}")
    return jsonify({'success': True, 'id': tid}), 201


@app_invoice.route('/store/<store_id>/terminals/<tid>', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_terminal(store_id, tid):
    body = request.get_json(silent=True) or {}
    data = SystemSettings.get(_invoice_key(store_id)) or {}
    terminals = data.get('terminals', [])

    idx = next((i for i, t in enumerate(terminals) if t['id'] == tid), None)
    if idx is None:
        return jsonify({'success': False, 'message': '機台不存在'}), 404

    t = terminals[idx]
    if 'name' in body:
        t['name'] = str(body['name']).strip() or t['name']
    if 'device_model' in body:
        t['device_model'] = str(body['device_model']).strip()

    ov_body = body.get('ecpay_override')
    if ov_body is not None:
        existing_ov = t.get('ecpay_override') or {}
        if not ov_body:
            t['ecpay_override'] = None
        else:
            def _keep(key):
                v = str(ov_body.get(key, '')).strip()
                return existing_ov.get(key, '') if v == '******' or not v else v
            t['ecpay_override'] = {
                'merchant_id': str(ov_body.get('merchant_id', existing_ov.get('merchant_id', ''))).strip(),
                'hash_key':    _keep('hash_key'),
                'hash_iv':     _keep('hash_iv'),
            }

    terminals[idx] = t
    data['terminals'] = terminals
    SystemSettings.set(_invoice_key(store_id), data)
    Log.create(get_jwt_identity(), '更新發票機台', f"store={store_id} terminal={tid}")
    return jsonify({'success': True})


@app_invoice.route('/store/<store_id>/terminals/<tid>', methods=['DELETE'])
@jwt_required()
@require_role('admin')
def delete_terminal(store_id, tid):
    data = SystemSettings.get(_invoice_key(store_id)) or {}
    terminals = data.get('terminals', [])
    before = len(terminals)
    terminals = [t for t in terminals if t['id'] != tid]
    if len(terminals) == before:
        return jsonify({'success': False, 'message': '機台不存在'}), 404
    data['terminals'] = terminals
    SystemSettings.set(_invoice_key(store_id), data)
    Log.create(get_jwt_identity(), '刪除發票機台', f"store={store_id} terminal={tid}")
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  開立發票
# ─────────────────────────────────────────────────────────────

@app_invoice.route('/issue', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator', 'cashier')
def issue_invoice():
    """
    手動開立電子發票
    ---
    tags:
      - Invoice
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [order_id]
          properties:
            order_id:      {type: string}
            carrier_type:  {type: string, enum: ['', '1', '2']}
            carrier_num:   {type: string}
            buyer_id:      {type: string, description: "統一編號（B2B）"}
            love_code:     {type: string, description: "愛心碼"}
            customer_name: {type: string}
            customer_email:{type: string}
    responses:
      201: {description: 發票開立成功}
      400: {description: 失敗}
    """
    body = request.get_json(silent=True) or {}
    order_id      = body.get('order_id', '').strip()
    carrier_type  = str(body.get('carrier_type', '')).strip()
    carrier_num   = str(body.get('carrier_num', '')).strip()
    buyer_id      = str(body.get('buyer_id', '')).strip()
    love_code     = str(body.get('love_code', '')).strip()
    customer_name = str(body.get('customer_name', '')).strip()
    customer_email= str(body.get('customer_email', '')).strip()

    if not order_id:
        return jsonify({'success': False, 'message': '請提供訂單 ID'}), 400

    # 檢查是否已開立
    existing = Invoice.find_by_order(order_id)
    if existing and existing['status'] == 'issued':
        return jsonify({'success': False,
                        'message': f"此訂單已開立發票 {existing['invoice_no']}"}), 400

    # 取得 POS 訂單
    order = PosOrder.find_by_id(order_id)
    if not order:
        return jsonify({'success': False, 'message': '訂單不存在'}), 404
    if order.get('status') != 'completed':
        return jsonify({'success': False, 'message': '僅限已完成訂單'}), 400

    # 建立 Invoice 記錄（pending）
    operator = get_jwt_identity()
    inv_id = Invoice.create(
        order_id=order_id, order_no=order['order_no'],
        total_amount=order['total_amount'],
        items=order.get('items', []),
        carrier_type=carrier_type, carrier_num=carrier_num,
        buyer_id=buyer_id, love_code=love_code,
        customer_name=customer_name, customer_email=customer_email,
        created_by=operator,
    )

    # 呼叫 ECPay
    try:
        from src.invoice_providers.ecpay import build_ecpay_items
        ecpay  = _get_ecpay()
        relate = f"{order['order_no']}-{inv_id[-6:]}"
        ec_items = build_ecpay_items(order.get('items', []))
        result = ecpay.issue(
            relate_no=relate,
            items=ec_items,
            total=int(order['total_amount']),
            carrier_type=carrier_type,
            carrier_num=carrier_num,
            buyer_id=buyer_id,
            love_code=love_code,
            customer_name=customer_name,
            customer_email=customer_email,
            remark=order.get('remark', ''),
        )

        if result.get('RtnCode') != 1:
            msg = result.get('RtnMsg', '開立失敗')
            Invoice.mark_error(inv_id, msg)
            return jsonify({'success': False, 'message': msg}), 400

        Invoice.mark_issued(
            inv_id=inv_id,
            invoice_no=result['InvoiceNo'],
            random_no=result['RandomNumber'],
            invoice_date=result.get('InvoiceDate', ''),
            ecpay_response=result,
        )
        Log.create(operator, '電子發票開立',
                   f"order={order['order_no']} invoice={result['InvoiceNo']}")
        inv = Invoice.find_by_id(inv_id)
        return jsonify({'success': True, 'data': inv}), 201

    except Exception as e:
        Invoice.mark_error(inv_id, str(e))
        logger.exception('電子發票開立失敗')
        return jsonify({'success': False, 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  作廢發票
# ─────────────────────────────────────────────────────────────

@app_invoice.route('/<inv_id>/void', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def void_invoice(inv_id):
    """
    作廢電子發票
    ---
    tags:
      - Invoice
    security:
      - Bearer: []
    parameters:
      - {in: path, name: inv_id, type: string, required: true}
      - in: body
        name: body
        schema:
          properties:
            reason: {type: string}
    responses:
      200: {description: 作廢成功}
      400: {description: 失敗}
    """
    body   = request.get_json(silent=True) or {}
    reason = str(body.get('reason', '')).strip() or '作廢'

    inv = Invoice.find_by_id(inv_id)
    if not inv:
        return jsonify({'success': False, 'message': '發票不存在'}), 404
    if inv['status'] != 'issued':
        return jsonify({'success': False, 'message': '僅限已開立的發票'}), 400

    try:
        ecpay = _get_ecpay()
        result = ecpay.void(
            invoice_no=inv['invoice_no'],
            invoice_date=inv['invoice_date'],
            reason=reason,
        )
        if result.get('RtnCode') != 1:
            msg = result.get('RtnMsg', '作廢失敗')
            return jsonify({'success': False, 'message': msg}), 400

        operator = get_jwt_identity()
        Invoice.mark_voided(inv_id, reason, operator)
        Log.create(operator, '電子發票作廢',
                   f"invoice={inv['invoice_no']} reason={reason}")
        return jsonify({'success': True})

    except Exception as e:
        logger.exception('電子發票作廢失敗')
        return jsonify({'success': False, 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  查詢
# ─────────────────────────────────────────────────────────────

@app_invoice.route('/', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator', 'cashier')
def list_invoices():
    """
    查詢電子發票列表
    ---
    tags:
      - Invoice
    security:
      - Bearer: []
    parameters:
      - {in: query, name: status,    type: string, enum: [pending, issued, voided, error]}
      - {in: query, name: date_from, type: string, description: "YYYY-MM-DD"}
      - {in: query, name: date_to,   type: string, description: "YYYY-MM-DD"}
      - {in: query, name: limit,     type: integer}
    responses:
      200: {description: 成功}
    """
    status        = request.args.get('status', '')
    date_from_str = request.args.get('date_from', '')
    date_to_str   = request.args.get('date_to',   '')
    limit         = int(request.args.get('limit', 100))

    date_from = datetime.strptime(date_from_str, '%Y-%m-%d') if date_from_str else None
    date_to   = datetime.strptime(date_to_str + ' 23:59:59', '%Y-%m-%d %H:%M:%S') \
                if date_to_str else None

    data = Invoice.find_all(
        status=status or None,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return jsonify({'success': True, 'data': data})


@app_invoice.route('/<inv_id>', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator', 'cashier')
def get_invoice(inv_id):
    """
    查詢單筆發票
    ---
    tags:
      - Invoice
    security:
      - Bearer: []
    parameters:
      - {in: path, name: inv_id, type: string, required: true}
    responses:
      200: {description: 成功}
      404: {description: 不存在}
    """
    inv = Invoice.find_by_id(inv_id)
    if not inv:
        return jsonify({'success': False, 'message': '發票不存在'}), 404
    return jsonify({'success': True, 'data': inv})
