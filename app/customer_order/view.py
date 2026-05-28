"""
顧客訂單 Blueprint  /customer-order
- GET  /menu           公開：取得點單用菜單
- POST /               公開：顧客建立訂單
- GET  /               登入：查詢訂單列表
- GET  /active         登入：取得待處理 + 處理中訂單（廚房用）
- GET  /stats          登入：今日統計
- GET  /<oid>          登入：取得單筆訂單
- PUT  /<oid>/status   登入：更新訂單狀態（operator+）
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from src.models.customer_order import CustomerOrder, ORDER_STATUS_LABEL
from src.models.menu import Menu
from src.models.settings import SystemSettings
from src.models.log import Log
from src.permissions import require_role

app_customer_order = Blueprint('app_customer_order', __name__)


# ── 公開：取得點單菜單 ─────────────────────────────
@app_customer_order.route('/menu', methods=['GET'])
def get_order_menu():
    """
    公開 API：取得顧客點單用菜單（不需登入）
    優先使用 settings.order_menu_id；未設定則取第一個啟用的菜單
    """
    menu_id = request.args.get('menu_id') or \
              SystemSettings.get('order_menu_id', '')
    if menu_id:
        m = Menu.find_by_id(menu_id)
        if m and m.get('status', 1) == 1:
            return jsonify({'success': True, 'data': m})

    # fallback：第一個啟用菜單
    menus = Menu.find_all(status=1)
    if not menus:
        return jsonify({'success': False, 'message': '目前無可用菜單'}), 404
    m = Menu.find_by_id(menus[0]['_id'])
    return jsonify({'success': True, 'data': m})


# ── 公開：顧客建立訂單 ────────────────────────────
@app_customer_order.route('/', methods=['POST'])
def create_order():
    """
    公開 API：顧客建立點餐訂單（不需登入）
    body: { table_no, items, total, remark, menu_id }
    items: [{item_id, item_name, qty, price, customizations, note}]
    """
    data = request.get_json(silent=True) or {}
    table_no = (data.get('table_no') or '').strip()
    items    = data.get('items', [])
    total    = data.get('total', 0)
    remark   = data.get('remark', '')
    menu_id  = data.get('menu_id', '')

    if not table_no:
        return jsonify({'success': False, 'message': '請輸入桌號或姓名'}), 400
    if not items:
        return jsonify({'success': False, 'message': '請至少選擇一個品項'}), 400
    if not isinstance(items, list):
        return jsonify({'success': False, 'message': '品項格式錯誤'}), 400

    # 基本欄位驗證
    for i, it in enumerate(items):
        if not it.get('item_name'):
            return jsonify({'success': False,
                            'message': f'第 {i+1} 筆品項缺少名稱'}), 400
        if not isinstance(it.get('qty', 0), (int, float)) or it.get('qty', 0) <= 0:
            return jsonify({'success': False,
                            'message': f'第 {i+1} 筆品項數量無效'}), 400

    oid = CustomerOrder.create(
        table_no=table_no,
        items=items,
        total=float(total),
        remark=remark,
        menu_id=menu_id,
    )
    order = CustomerOrder.find_by_id(oid)
    return jsonify({
        'success':  True,
        'order_id': oid,
        'order_no': order['order_no'],
    }), 201


# ── 需登入：查詢訂單列表 ──────────────────────────
@app_customer_order.route('/', methods=['GET'])
@jwt_required()
def list_orders():
    """查詢訂單（可依 status / date 篩選）"""
    status = request.args.get('status', '')
    date   = request.args.get('date', '')
    limit  = int(request.args.get('limit', 100))
    data = CustomerOrder.find_all(
        status=status or None,
        date=date or None,
        limit=limit,
    )
    return jsonify({'success': True, 'data': data})


# ── 需登入：廚房用（待處理 + 處理中）────────────────
@app_customer_order.route('/active', methods=['GET'])
@jwt_required()
def active_orders():
    """取得待處理 + 處理中的訂單（廚房顯示，先進先出）"""
    data = CustomerOrder.find_active()
    return jsonify({'success': True, 'data': data})


# ── 需登入：今日統計 ──────────────────────────────
@app_customer_order.route('/stats', methods=['GET'])
@jwt_required()
def order_stats():
    """今日各狀態訂單數量與金額"""
    stats = CustomerOrder.today_stats()
    labeled = {
        ORDER_STATUS_LABEL.get(k, k): v
        for k, v in stats.items()
    }
    return jsonify({'success': True, 'data': labeled, 'raw': stats})


# ── 需登入：取得單筆訂單 ──────────────────────────
@app_customer_order.route('/<oid>', methods=['GET'])
@jwt_required()
def get_order(oid):
    order = CustomerOrder.find_by_id(oid)
    if not order:
        return jsonify({'success': False, 'message': '訂單不存在'}), 404
    return jsonify({'success': True, 'data': order})


# ── 需登入：更新訂單狀態 ──────────────────────────
@app_customer_order.route('/<oid>/status', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_order_status(oid):
    """
    更新訂單狀態
    body: { status: 'processing' | 'completed' | 'cancelled' }
    """
    data   = request.get_json(silent=True) or {}
    status = data.get('status', '')
    if not status:
        return jsonify({'success': False, 'message': '請提供 status'}), 400

    operator = get_jwt_identity()
    ok = CustomerOrder.update_status(oid, status, operator)
    if not ok:
        return jsonify({'success': False, 'message': '訂單不存在或狀態無效'}), 404

    order = CustomerOrder.find_by_id(oid)
    Log.create(operator, '更新顧客訂單狀態',
               f"order={order['order_no']} status={status}")
    return jsonify({'success': True})
