# [REFACTOR] 出入庫單共用 view handler：app/inbound/view.py 與 app/outbound/view.py
#            原本近乎複製貼上的 10 個端點邏輯抽至此，兩邊 view 變薄殼
#            （僅保留路由 / 權限裝飾器 / swagger docstring 原文，body 一行委派）。
#            差異點以 OrderViewConfig 表達：
#              - model：InboundOrder / OutboundOrder
#              - noun / short：文案（入庫單/出庫單、入庫/出庫）
#              - qtys_key：complete 請求數量欄位（received_qtys / shipped_qtys）
#              - validate_item_qty：inbound 對 expected_qty > 0 的驗證
#              - check_stock_on_confirm：outbound confirm 的冪等回應 + 狀態機 + 庫存檢查
#              - strict_complete：inbound complete 的 404 / 負數驗證 / 帶狀態錯誤訊息
#              - complete_service：src/services/order_service.py 的完成協調函式
#            所有回應 JSON、狀態碼、錯誤訊息與檢查順序均與原 view 逐字一致。
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity

from src.models.inventory import Inventory
from src.models.product import Product
from src.models.warehouse import Warehouse
from src.models.log import Log
from src.constants import OrderStatus
# [REFACTOR] pydantic 驗證層：型別/結構防線（必填檢查仍由下方手寫檢查負責，保留原訊息）
from src.schemas.base import validate_payload, apply_coerced
from src.schemas.domain import InOutOrderCreate, InOutOrderItemPayload


class OrderViewConfig:
    def __init__(self, *, model, noun, short, qtys_key,
                 validate_item_qty, check_stock_on_confirm, strict_complete,
                 confirm_fail_msg, complete_fail_msg, complete_service):
        self.model = model
        self.noun = noun                    # '入庫單' / '出庫單'
        self.short = short                  # '入庫' / '出庫'
        self.qtys_key = qtys_key            # 'received_qtys' / 'shipped_qtys'
        self.validate_item_qty = validate_item_qty
        self.check_stock_on_confirm = check_stock_on_confirm
        self.strict_complete = strict_complete
        self.confirm_fail_msg = confirm_fail_msg
        self.complete_fail_msg = complete_fail_msg
        self.complete_service = complete_service


def list_orders(cfg):
    status = request.args.get('status', '')
    warehouse_id = request.args.get('warehouse_id', '')
    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))
    data = cfg.model.find_all(
        status=status or None,
        warehouse_id=warehouse_id or None,
        limit=limit,
        offset=offset
    )
    return jsonify({'success': True, 'data': data})


def get_order(cfg, oid):
    order = cfg.model.find_by_id(oid)
    if not order:
        return jsonify({'success': False, 'message': f'{cfg.noun}不存在'}), 404
    return jsonify({'success': True, 'data': order})


def create_order(cfg):
    data = request.get_json(silent=True) or {}
    # [REFACTOR] 型別/結構驗證（非法 ObjectId、非數字 qty/price 等原會 500，現回 400）
    _, err = validate_payload(InOutOrderCreate, data)
    if err:
        return err
    if not data.get('warehouse_id'):
        return jsonify({'success': False, 'message': '請指定倉庫'}), 400
    w = Warehouse.find_by_id(data['warehouse_id'])
    if not w:
        return jsonify({'success': False, 'message': '倉庫不存在'}), 404
    data['warehouse_name'] = w['name']
    oid = cfg.model.create(data, created_by=get_jwt_identity())
    Log.create(get_jwt_identity(), f'建立{cfg.noun}', f'warehouse={w["name"]}')
    return jsonify({'success': True, 'id': oid}), 201


def update_order(cfg, oid):
    data = request.get_json(silent=True) or {}
    if 'warehouse_id' in data:
        w = Warehouse.find_by_id(data['warehouse_id'])
        if not w:
            return jsonify({'success': False, 'message': '倉庫不存在'}), 404
        data['warehouse_name'] = w['name']
    if not cfg.model.update_basic(oid, data):
        return jsonify({'success': False, 'message': f'{cfg.noun}不存在或非待處理狀態'}), 400
    return jsonify({'success': True})


def add_item(cfg, oid):
    data = request.get_json(silent=True) or {}
    # [REFACTOR] 型別/結構驗證＋數值轉型寫回（字串數字與 0 比較原會 TypeError → 500）
    payload, err = validate_payload(InOutOrderItemPayload, data)
    if err:
        return err
    apply_coerced(data, payload, ('expected_qty', 'qty', 'price', 'unit_price'))
    if not data.get('product_id'):
        return jsonify({'success': False, 'message': '請指定產品'}), 400
    if cfg.validate_item_qty:
        expected_qty = data.get('expected_qty', 0)
        if expected_qty <= 0:
            return jsonify({'success': False, 'message': '數量必須大於 0'}), 400
    p = Product.find_by_id(data['product_id'])
    if not p:
        return jsonify({'success': False, 'message': '產品不存在'}), 404
    data['product_name'] = p['name']
    data['product_sku'] = p['sku']
    data['unit'] = p['unit']
    if not cfg.model.add_item(oid, data):
        return jsonify({'success': False, 'message': f'{cfg.noun}不存在或非待處理狀態'}), 400
    return jsonify({'success': True})


def update_item(cfg, oid, item_id):
    data = request.get_json(silent=True) or {}
    # [REFACTOR] 型別/結構驗證＋數值轉型寫回
    payload, err = validate_payload(InOutOrderItemPayload, data)
    if err:
        return err
    apply_coerced(data, payload, ('expected_qty', 'qty', 'price', 'unit_price'))
    if cfg.validate_item_qty and 'expected_qty' in data:
        expected_qty = data['expected_qty']
        if expected_qty <= 0:
            return jsonify({'success': False, 'message': '數量必須大於 0'}), 400
    if not cfg.model.update_item(oid, item_id, data):
        return jsonify({'success': False, 'message': '更新失敗'}), 400
    return jsonify({'success': True})


def remove_item(cfg, oid, item_id):
    if not cfg.model.remove_item(oid, item_id):
        return jsonify({'success': False, 'message': '刪除失敗'}), 400
    return jsonify({'success': True})


def confirm_order(cfg, oid):
    order = cfg.model.find_by_id(oid)
    if not order:
        return jsonify({'success': False, 'message': f'{cfg.noun}不存在'}), 404
    if cfg.check_stock_on_confirm:
        if order['status'] == OrderStatus.CONFIRMED:
            return jsonify({'success': True, 'message': '已確認'}), 200
        # 僅 pending → confirmed 允許，行為與原 status != 'pending' 等價
        if not OrderStatus.is_valid_transition(order['status'], OrderStatus.CONFIRMED):
            return jsonify({'success': False, 'message': f"無法從 {order['status']} 狀態確認"}), 400
    if not order.get('items'):
        return jsonify({'success': False, 'message': f'請先新增{cfg.short}明細'}), 400
    if cfg.check_stock_on_confirm:
        # 檢查庫存是否足夠
        warehouse_id = order['warehouse_id']
        for item in order['items']:
            current_qty = Inventory.get_quantity(item['product_id'], warehouse_id)
            if current_qty < item['expected_qty']:
                return jsonify({
                    'success': False,
                    'message': f"產品 {item['product_name']} 庫存不足 (現有:{current_qty}, 需求:{item['expected_qty']})"
                }), 400
    # 狀態轉移在 model 以 find_one_and_update({status: 'pending'}) 原子完成，
    # 並發請求越過上方檢查後會因文件已翻轉為 'confirmed' 而失敗（matched_count == 0）。
    if not cfg.model.confirm(oid, get_jwt_identity()):
        return jsonify({'success': False, 'message': cfg.confirm_fail_msg}), 400
    Log.create(get_jwt_identity(), f'確認{cfg.noun}', f"order_no={order['order_no']}")
    return jsonify({'success': True})


def complete_order(cfg, oid):
    data = request.get_json(silent=True) or {}
    qtys = data.get(cfg.qtys_key)  # {item_id: qty}
    operator = get_jwt_identity()

    order = None
    if cfg.strict_complete:
        order = cfg.model.find_by_id(oid)
        if order is None:
            return jsonify({'success': False, 'message': f'{cfg.noun}不存在'}), 404
        if qtys is not None:
            for item_id, qty in qtys.items():
                if qty < 0:
                    return jsonify({'success': False, 'message': f'實收數量不可為負值（item_id={item_id}）'}), 400

    # Service 層：原子轉移 confirmed → completed + 調整庫存 + StockMovement + Log
    completed = cfg.complete_service(oid, operator, qtys)
    if not completed:
        if cfg.strict_complete:
            current = order['status']
            return jsonify({'success': False,
                            'message': f'完成失敗，目前狀態為「{current}」，需為「confirmed」'}), 400
        return jsonify({'success': False, 'message': cfg.complete_fail_msg}), 400

    return jsonify({'success': True, 'order_no': completed['order_no']})


def cancel_order(cfg, oid):
    order = cfg.model.find_by_id(oid)
    if not order:
        return jsonify({'success': False, 'message': f'{cfg.noun}不存在'}), 404
    if not cfg.model.cancel(oid, get_jwt_identity()):
        return jsonify({'success': False, 'message': '取消失敗，已完成的單據無法取消'}), 400
    Log.create(get_jwt_identity(), f'取消{cfg.noun}', f"order_no={order['order_no']}")
    return jsonify({'success': True})
