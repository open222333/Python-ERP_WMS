from flask import Blueprint, request, jsonify, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.pos import PosOrder
from src.models.log import Log
from src.permissions import require_role
from datetime import datetime

app_pos = Blueprint('app_pos', __name__)


@app_pos.route('/')
def index():
    """POS 收銀頁面"""
    from src import ADMIN_TITLE
    return render_template('pos/index.html', admin_title=ADMIN_TITLE)


@app_pos.route('/manifest.json')
def manifest():
    """PWA manifest — 鎖定橫向方向"""
    from flask import jsonify
    return jsonify({
        'name': 'POS 收銀',
        'short_name': 'POS',
        'start_url': '/pos/',
        'display': 'standalone',
        'orientation': 'landscape',
        'background_color': '#1e2235',
        'theme_color': '#1e2235',
        'icons': []
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
            warehouse_id:
              type: string
              description: 出貨倉庫 ID
            items:
              type: array
              items:
                type: object
                required: [product_id, quantity, unit_price]
                properties:
                  product_id:   {type: string}
                  product_name: {type: string}
                  product_sku:  {type: string}
                  unit:         {type: string}
                  quantity:     {type: integer}
                  unit_price:   {type: number}
            payment:
              type: object
              required: [type]
              properties:
                type:        {type: string, enum: [cash, card, mixed]}
                cash_amount: {type: number}
                card_amount: {type: number}
            discount:
              type: number
              description: 整單折扣金額（預設 0）
            remark:
              type: string
    responses:
      201:
        description: 結帳成功
      400:
        description: 庫存不足或資料有誤
    """
    data = request.get_json(silent=True) or {}

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

    result = PosOrder.create_sale(
        warehouse_id=warehouse_id,
        items=items,
        payment=payment,
        discount=discount,
        cashier=get_jwt_identity(),
        remark=remark,
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
      - in: query
        name: date_from
        type: string
        description: "開始日期 YYYY-MM-DD"
      - in: query
        name: date_to
        type: string
        description: "結束日期 YYYY-MM-DD"
      - in: query
        name: cashier
        type: string
      - in: query
        name: status
        type: string
        enum: [completed, refunded]
      - in: query
        name: source
        type: string
        description: "來源：pos（現場）/ ubereats / foodpanda，留空=全部"
      - in: query
        name: limit
        type: integer
    responses:
      200:
        description: 成功
    """
    date_from_str = request.args.get('date_from', '')
    date_to_str   = request.args.get('date_to', '')
    cashier       = request.args.get('cashier', '')
    status        = request.args.get('status', '')
    source        = request.args.get('source', '')
    limit         = int(request.args.get('limit', 200))

    date_from = datetime.strptime(date_from_str, '%Y-%m-%d') if date_from_str else None
    date_to   = datetime.strptime(date_to_str + ' 23:59:59', '%Y-%m-%d %H:%M:%S') if date_to_str else None

    data = PosOrder.find_all(
        date_from=date_from, date_to=date_to,
        cashier=cashier or None,
        status=status or None,
        source=source or None,
        limit=limit,
    )
    return jsonify({'success': True, 'data': data})


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
      - in: path
        name: sid
        type: string
        required: true
    responses:
      200:
        description: 成功
      404:
        description: 不存在
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
      - in: path
        name: sid
        type: string
        required: true
      - in: body
        name: body
        schema:
          properties:
            reason: {type: string, description: 退款原因}
    responses:
      200:
        description: 退款成功
      400:
        description: 失敗
    """
    data   = request.get_json(silent=True) or {}
    reason = data.get('reason', '').strip()
    result = PosOrder.refund(sid, reason, operator=get_jwt_identity())
    if not result['success']:
        return jsonify({'success': False, 'message': result['error']}), 400
    Log.create(get_jwt_identity(), 'POS 退款', f'sale_id={sid} reason={reason}')
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  POS 付款方式設定
# ─────────────────────────────────────────────────────────────

_DEFAULT_PAY_METHODS = [
    {'id': 'cash', 'label': '現金', 'enabled': True, 'has_cash': True, 'sort_order': 0},
]


@app_pos.route('/payment-methods', methods=['GET'])
@jwt_required()
def get_payment_methods():
    """取得 POS 付款方式清單（含停用的，供後台管理）"""
    from src.models.settings import SystemSettings
    methods = SystemSettings.get('pos_payment_methods', _DEFAULT_PAY_METHODS)
    return jsonify({'success': True, 'data': methods})


@app_pos.route('/payment-methods', methods=['PUT'])
@jwt_required()
@require_role('admin')
def update_payment_methods():
    """更新 POS 付款方式（僅限 admin）"""
    from src.models.settings import SystemSettings
    data = request.get_json(silent=True) or {}
    raw = data.get('methods', [])
    validated = []
    for i, m in enumerate(raw):
        mid   = str(m.get('id', '')).strip()
        label = str(m.get('label', '')).strip()
        if not mid or not label:
            continue
        validated.append({
            'id':        mid,
            'label':     label,
            'enabled':   bool(m.get('enabled', True)),
            'has_cash':  bool(m.get('has_cash', False)),
            'sort_order': int(m.get('sort_order', i)),
        })
    if not validated:
        return jsonify({'success': False, 'message': '至少需要一種付款方式'}), 400
    SystemSettings.set('pos_payment_methods', validated)
    Log.create(get_jwt_identity(), '更新 POS 付款方式',
               ', '.join(f"{m['label']}({'啟用' if m['enabled'] else '停用'})" for m in validated))
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  日結報表
# ─────────────────────────────────────────────────────────────

@app_pos.route('/summary', methods=['GET'])
@jwt_required()
@require_role('admin', 'operator', 'cashier')
def daily_summary():
    """
    日結報表
    ---
    tags:
      - POS
    security:
      - Bearer: []
    parameters:
      - in: query
        name: date
        type: string
        description: "日期 YYYY-MM-DD（預設今日）"
    responses:
      200:
        description: 成功
    """
    date_str = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
    try:
        date_from = datetime.strptime(date_str, '%Y-%m-%d')
        date_to   = datetime.strptime(date_str + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return jsonify({'success': False, 'message': '日期格式錯誤'}), 400

    orders = PosOrder.find_all(date_from=date_from, date_to=date_to, status='completed')
    total_orders = len(orders)
    total_amount = sum(o['total_amount'] for o in orders)
    total_discount = sum(o.get('discount', 0) for o in orders)
    cash_total = sum(o.get('cash_amount', 0) for o in orders if o['payment_type'] in ('cash', 'mixed'))
    card_total = sum(o.get('card_amount', 0) for o in orders if o['payment_type'] in ('card', 'mixed'))

    return jsonify({'success': True, 'data': {
        'date':           date_str,
        'total_orders':   total_orders,
        'total_amount':   round(total_amount, 2),
        'total_discount': round(total_discount, 2),
        'cash_total':     round(cash_total, 2),
        'card_total':     round(card_total, 2),
        'orders':         orders,
    }})
