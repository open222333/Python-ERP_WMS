# [REFACTOR] 出庫 view 薄殼：端點邏輯移至 app/common/order_views.py 共用 handler、
#            complete 的庫存協調移至 src/services/order_service.py。
#            此處僅保留路由、權限裝飾器與 swagger docstring（原文逐字保留），
#            路由 / endpoint 名稱 / 回應 / 狀態碼 / 錯誤訊息與原版完全一致。
from flask import Blueprint
from flask_jwt_extended import jwt_required
from src.models.outbound import OutboundOrder
from src.permissions import require_role
from src.services.order_service import complete_outbound_order
from app.common import order_views as h

app_outbound = Blueprint('app_outbound', __name__)

_CFG = h.OrderViewConfig(
    model=OutboundOrder,
    noun='出庫單',
    short='出庫',
    qtys_key='shipped_qtys',
    validate_item_qty=False,
    check_stock_on_confirm=True,
    strict_complete=False,
    confirm_fail_msg='確認失敗，可能已被其他請求處理',
    complete_fail_msg='完成失敗，請確認狀態為已確認',
    complete_service=complete_outbound_order,
)


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
    return h.list_orders(_CFG)


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
    return h.get_order(_CFG, oid)


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
    return h.create_order(_CFG)


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
    return h.update_order(_CFG, oid)


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
    return h.add_item(_CFG, oid)


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
    return h.update_item(_CFG, oid, item_id)


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
    return h.remove_item(_CFG, oid, item_id)


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
    return h.confirm_order(_CFG, oid)


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
    return h.complete_order(_CFG, oid)


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
    return h.cancel_order(_CFG, oid)
