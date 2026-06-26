from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
)
from src.models.user import User
from src.models.user_template import UserTemplate
from app.extensions import limiter

app_auth = Blueprint('auth', __name__)


@app_auth.route('/login', methods=['POST'])
@limiter.limit("10 per minute; 50 per hour")
def login():
    """
    帳號密碼登入
    ---
    tags:
      - Auth
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [username, password]
          properties:
            username:    {type: string,  example: admin}
            password:    {type: string,  example: secret}
            remember_me: {type: boolean, description: "true = 同時回傳 30 天 refresh_token"}
    responses:
      200:
        description: 登入成功
        schema:
          properties:
            success:       {type: boolean}
            token:         {type: string, description: "Access token（8 小時）"}
            refresh_token: {type: string, description: "Refresh token（30 天，remember_me=true 時才回傳）"}
            role:          {type: string}
      401:
        description: 帳號或密碼錯誤
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '缺少請求參數'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'success': False, 'message': 'username 或 password 不得為空'}), 400

    user = User.find_by_username(username)
    if not user or not User.check_password(password, user['password']):
        return jsonify({'success': False, 'message': '帳號或密碼錯誤'}), 401

    if user.get('locked'):
        return jsonify({'success': False, 'message': '帳號已停用'}), 403

    store_ids_str = [str(oid) for oid in user.get('store_ids', []) if oid]
    additional_claims = {
        'role':      user.get('role', 'viewer'),
        'store_ids': store_ids_str,
    }

    resp = {
        'success':   True,
        'token':     create_access_token(identity=username,
                                         additional_claims=additional_claims),
        'role':      user.get('role', 'viewer'),
        'store_ids': store_ids_str,
    }
    if data.get('remember_me'):
        resp['refresh_token'] = create_refresh_token(identity=username,
                                                     additional_claims=additional_claims)

    return jsonify(resp)


@app_auth.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    用 Refresh Token 換發新的 Access Token
    ---
    tags:
      - Auth
    security:
      - Bearer: []
    description: >
      Authorization header 帶 Refresh Token（格式同 Bearer），
      成功後回傳新的 access token。
    responses:
      200:
        description: 換發成功
        schema:
          properties:
            success: {type: boolean}
            token:   {type: string}
      401:
        description: Refresh token 無效或過期
    """
    username = get_jwt_identity()
    user = User.find_by_username(username)
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 401
    if user.get('locked'):
        return jsonify({'success': False, 'message': '帳號已停用'}), 403
    store_ids_str = [str(oid) for oid in user.get('store_ids', []) if oid]
    additional_claims = {
        'role':      user.get('role', 'viewer'),
        'store_ids': store_ids_str,
    }
    return jsonify({
        'success':   True,
        'token':     create_access_token(identity=username, additional_claims=additional_claims),
        'role':      user.get('role', 'viewer'),
        'store_ids': store_ids_str,
    })


@app_auth.route('/me', methods=['GET'])
@jwt_required()
def me():
    """
    驗證 token 並回傳目前使用者資訊（含角色模板頁面設定）
    ---
    tags:
      - Auth
    security:
      - Bearer: []
    responses:
      200:
        description: Token 有效
        schema:
          properties:
            success:       {type: boolean}
            username:      {type: string}
            role:          {type: string}
            template_id:   {type: string}
            template_name: {type: string}
            pages_enabled: {type: object, description: "模板頁面顯示設定，無模板時為 null"}
      401:
        description: Token 無效或過期
    """
    username = get_jwt_identity()
    user = User.find_by_username(username)
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 401

    template_id   = user.get('template_id')
    template_name = None
    pages_enabled = None

    if template_id:
        tmpl = UserTemplate.find_by_id(str(template_id))
        if tmpl:
            template_name = tmpl.get('name')
            pages_enabled = tmpl.get('pages_enabled')

    store_ids_str = [str(oid) for oid in user.get('store_ids', []) if oid]
    return jsonify({
        'success':       True,
        'username':      username,
        'role':          user.get('role', 'viewer'),
        'store_ids':     store_ids_str,
        'template_id':   str(template_id) if template_id else None,
        'template_name': template_name,
        'pages_enabled': pages_enabled,
    })
