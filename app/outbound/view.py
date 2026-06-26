from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.outbound import OutboundOrder
from src.models.inventory import Inventory, StockMovement
from src.models.product import Product
from src.models.warehouse import Warehouse
from src.models.log import Log
from src.permissions import require_role

app_outbound = Blueprint('app_outbound', __name__)


@app_outbound.route('/', methods=['GET'])
@jwt_required()
def list_orders():
    """
    列出出庫單
    ---
    tags:
      - 出庫管理
    security:
      - Bearer: []
    parameters:
      - in: query
        name: status
        type: string
        enum: [pending, confirmed, completed, cancelled]
        description: 篩選狀態（留空 = 全部）
      - in: query
        name: warehouse_id
        type: string
        description: 篩選倉庫 ID
    responses:
      200:
        description: 成功
        schema:
          properties:
            success: {type: boolean}
            data:
              type: array
              items:
                $ref: '#/definitions/OutboundOrder'
    """
    status = request.args.get('status', '')
    warehouse_id = request.args.get('warehouse_id', '')
    data = OutboundOrder.find_all(
        status=status or None,
        warehouse_id=warehouse_id or None
    )
    return jsonify({'success': True, 'data': data})


@app_outbound.route('/<oid>', methods=['GET'])
@jwt_required()
def get_order(oid):
    """
    查看出庫單詳情
    ---
    tags:
      - 出庫管理
    security:
      - Bearer: []
    parameters:
      - in: path
        name: oid
        type: string
        required: true
        description: 出庫單 ID
    responses:
      200:
        description: 成功
        schema:
          properties:
            success: {type: boolean}
            data:
              $ref: '#/definitions/OutboundOrder'
      404:
        description: 出庫單不存在
    """
    order = OutboundOrder.find_by_id(oid)
    if not order:
        return jsonify({'success': False, 'message': '出庫單不存在'}), 404
    return jsonify({'success': True, 'data': order})


@app_outbound.route('/', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def create_order():
    """
    建立出庫單
    ---
    tags:
      - 出庫管理
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [warehouse_id]
          properties:
            warehouse_id:
              type: string
              description: 出貨倉庫 ID
            customer:
              type: string
              description: 客戶名稱
            remark:
              type: string
              description: 備註
    responses:
      201:
        description: 建立成功
        schema:
          properties:
            success: {type: boolean}
            id: {type: string, description: 新出庫單 ID}
      400:
        description: 缺少必填欄位
      404:
        description: 倉庫不存在
    """
    data = request.get_json(silent=True) or {}
    if not data.get('warehouse_id'):
        return jsonify({'success': False, 'message': '請指定倉庫'}), 400
    w = Warehouse.find_by_id(data['warehouse_id'])
    if not w:
        return jsonify({'success': False, 'message': '倉庫不存在'}), 404
    data['warehouse_name'] = w['name']
    oid = OutboundOrder.create(data, created_by=get_jwt_identity())
    Log.create(get_jwt_identity(), '建立出庫單', f'warehouse={w["name"]}')
    return jsonify({'success': True, 'id': oid}), 201


@app_outbound.route('/<oid>', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_order(oid):
    """
    更新出庫單基本資料（限 pending 狀態）
    ---
    tags:
      - 出庫管理
    security:
      - Bearer: []
    parameters:
      - in: path
        name: oid
        type: string
        required: true
        description: 出庫單 ID
      - in: body
        name: body
        schema:
          properties:
            customer: {type: string, description: 客戶名稱}
            remark: {type: string, description: 備註}
            warehouse_id: {type: string, description: 倉庫 ID}
    responses:
      200:
        description: 更新成功
      400:
        description: 出庫單不存在或非 pending 狀態
    """
    data = request.get_json(silent=True) or {}
    if 'warehouse_id' in data:
        w = Warehouse.find_by_id(data['warehouse_id'])
        if not w:
            return jsonify({'success': False, 'message': '倉庫不存在'}), 404
        data['warehouse_name'] = w['name']
    if not OutboundOrder.update_basic(oid, data):
        return jsonify({'success': False, 'message': '出庫單不存在或非待處理狀態'}), 400
    return jsonify({'success': True})


@app_outbound.route('/<oid>/item', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def add_item(oid):
    """
    新增出庫明細（限 pending 狀態）
    ---
    tags:
      - 出庫管理
    security:
      - Bearer: []
    parameters:
      - in: path
        name: oid
        type: string
        required: true
        description: 出庫單 ID
      - in: body
        name: body
        required: true
        schema:
          required: [product_id]
          properties:
            product_id:
              type: string
              description: 產品 ID
            expected_qty:
              type: integer
              description: 預計出庫數量（預設 0）
            unit_price:
              type: number
              description: 單價（預設 0）
    responses:
      200:
        description: 新增成功
      400:
        description: 缺少產品 ID 或出庫單非 pending 狀態
      404:
        description: 產品不存在
    """
    data = request.get_json(silent=True) or {}
    if not data.get('product_id'):
        return jsonify({'success': False, 'message': '請指定產品'}), 400
    p = Product.find_by_id(data['product_id'])
    if not p:
        return jsonify({'success': False, 'message': '產品不存在'}), 404
    data['product_name'] = p['name']
    data['product_sku'] = p['sku']
    data['unit'] = p['unit']
    if not OutboundOrder.add_item(oid, data):
        return jsonify({'success': False, 'message': '出庫單不存在或非待處理狀態'}), 400
    return jsonify({'success': True})


@app_outbound.route('/<oid>/item/<item_id>', methods=['PUT'])
@jwt_required()
@require_role('admin', 'operator')
def update_item(oid, item_id):
    """
    更新出庫明細（限 pending 狀態）
    ---
    tags:
      - 出庫管理
    security:
      - Bearer: []
    parameters:
      - in: path
        name: oid
        type: string
        required: true
        description: 出庫單 ID
      - in: path
        name: item_id
        type: string
        required: true
        description: 明細項目 ID
      - in: body
        name: body
        schema:
          properties:
            expected_qty: {type: integer, description: 預計出庫數量}
            unit_price: {type: number, description: 單價}
    responses:
      200:
        description: 更新成功
      400:
        description: 更新失敗
    """
    data = request.get_json(silent=True) or {}
    if not OutboundOrder.update_item(oid, item_id, data):
        return jsonify({'success': False, 'message': '更新失敗'}), 400
    return jsonify({'success': True})


@app_outbound.route('/<oid>/item/<item_id>', methods=['DELETE'])
@jwt_required()
@require_role('admin', 'operator')
def remove_item(oid, item_id):
    """
    移除出庫明細（限 pending 狀態）
    ---
    tags:
      - 出庫管理
    security:
      - Bearer: []
    parameters:
      - in: path
        name: oid
        type: string
        required: true
        description: 出庫單 ID
      - in: path
        name: item_id
        type: string
        required: true
        description: 明細項目 ID
    responses:
      200:
        description: 刪除成功
      400:
        description: 刪除失敗
    """
    if not OutboundOrder.remove_item(oid, item_id):
        return jsonify({'success': False, 'message': '刪除失敗'}), 400
    return jsonify({'success': True})


@app_outbound.route('/<oid>/confirm', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def confirm_order(oid):
    """
    確認出庫單（pending → confirmed），自動驗證各產品庫存是否充足
    ---
    tags:
      - 出庫管理
    security:
      - Bearer: []
    parameters:
      - in: path
        name: oid
        type: string
        required: true
        description: 出庫單 ID
    responses:
      200:
        description: 確認成功
      400:
        description: 無明細、庫存不足或確認失敗
        schema:
          properties:
            success: {type: boolean}
            message:
              type: string
              example: "產品 商品A 庫存不足 (現有:3, 需求:10)"
      404:
        description: 出庫單不存在
    """
    order = OutboundOrder.find_by_id(oid)
    if not order:
        return jsonify({'success': False, 'message': '出庫單不存在'}), 404
    if order['status'] == 'confirmed':
        return jsonify({'success': True, 'message': '已確認'}), 200
    if order['status'] != 'pending':
        return jsonify({'success': False, 'message': f"無法從 {order['status']} 狀態確認"}), 400
    if not order.get('items'):
        return jsonify({'success': False, 'message': '請先新增出庫明細'}), 400
    # 檢查庫存是否足夠
    warehouse_id = order['warehouse_id']
    for item in order['items']:
        current_qty = Inventory.get_quantity(item['product_id'], warehouse_id)
        if current_qty < item['expected_qty']:
            return jsonify({
                'success': False,
                'message': f"產品 {item['product_name']} 庫存不足 (現有:{current_qty}, 需求:{item['expected_qty']})"
            }), 400
    # Fix 2: the status transition is done atomically in the model via
    # find_one_and_update with {status: 'pending'} as the filter, so a
    # concurrent confirm that races past the stock check above will find the
    # document already flipped to 'confirmed' and get matched_count == 0.
    if not OutboundOrder.confirm(oid, get_jwt_identity()):
        return jsonify({'success': False, 'message': '確認失敗，可能已被其他請求處理'}), 400
    Log.create(get_jwt_identity(), '確認出庫單', f"order_no={order['order_no']}")
    return jsonify({'success': True})


@app_outbound.route('/<oid>/complete', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def complete_order(oid):
    """
    完成出庫（confirmed → completed），自動扣減庫存
    ---
    tags:
      - 出庫管理
    security:
      - Bearer: []
    parameters:
      - in: path
        name: oid
        type: string
        required: true
        description: 出庫單 ID
      - in: body
        name: body
        description: 選填。不帶則以各明細 expected_qty 作為實出數量
        schema:
          properties:
            shipped_qtys:
              type: object
              description: "覆寫各明細實出數量，格式：{item_id: qty}"
              example: {"<item_id>": 8}
    responses:
      200:
        description: 完成成功
        schema:
          properties:
            success: {type: boolean}
            order_no: {type: string}
      400:
        description: 出庫單不為 confirmed 狀態
    """
    data = request.get_json(silent=True) or {}
    shipped_qtys = data.get('shipped_qtys')
    operator = get_jwt_identity()

    completed = OutboundOrder.complete(oid, operator, shipped_qtys)
    if not completed:
        return jsonify({'success': False, 'message': '完成失敗，請確認狀態為已確認'}), 400

    warehouse_id = completed['warehouse_id']
    w = Warehouse.find_by_id(warehouse_id)

    for item in completed.get('items', []):
        qty = item.get('shipped_qty', 0)
        if qty <= 0:
            continue
        before_qty, after_qty = Inventory.adjust(
            product_id=item['product_id'],
            warehouse_id=warehouse_id,
            delta=-qty
        )
        StockMovement.create(
            product_id=item['product_id'],
            warehouse_id=warehouse_id,
            movement_type='outbound',
            quantity=-qty,
            before_qty=before_qty,
            after_qty=after_qty,
            product_name=item.get('product_name', ''),
            product_sku=item.get('product_sku', ''),
            warehouse_name=w['name'] if w else '',
            reference_type='outbound_order',
            reference_id=oid,
            remark=f"出庫單 {completed['order_no']}",
            operator=operator
        )

    Log.create(operator, '完成出庫', f"order_no={completed['order_no']}")
    return jsonify({'success': True, 'order_no': completed['order_no']})


@app_outbound.route('/<oid>/cancel', methods=['POST'])
@jwt_required()
@require_role('admin', 'operator')
def cancel_order(oid):
    """
    取消出庫單（pending / confirmed 均可取消，completed 不可）
    ---
    tags:
      - 出庫管理
    security:
      - Bearer: []
    parameters:
      - in: path
        name: oid
        type: string
        required: true
        description: 出庫單 ID
    responses:
      200:
        description: 取消成功
      400:
        description: 已完成的單據無法取消
      404:
        description: 出庫單不存在
    """
    order = OutboundOrder.find_by_id(oid)
    if not order:
        return jsonify({'success': False, 'message': '出庫單不存在'}), 404
    if not OutboundOrder.cancel(oid, get_jwt_identity()):
        return jsonify({'success': False, 'message': '取消失敗，已完成的單據無法取消'}), 400
    Log.create(get_jwt_identity(), '取消出庫單', f"order_no={order['order_no']}")
    return jsonify({'success': True})
