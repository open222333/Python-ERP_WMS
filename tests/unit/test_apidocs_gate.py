"""
[SEC] /apidocs（Swagger）存取控制單元測試。

背景：/apidocs 對外公開會洩漏完整 API 規格（路徑/參數/權限），正式環境
預設關閉（src.ENABLE_SWAGGER，依 FLASK_ENV != 'production' 或
conf/config.ini 的 ENABLE_SWAGGER 明確覆寫）。測試環境未設定 FLASK_ENV，
fallback 為 'production' → 預期 ENABLE_SWAGGER 為 False，等同正式環境行為。
"""
import src as src_pkg


def test_enable_swagger_defaults_false_in_test_env():
    """測試環境未設 FLASK_ENV → fallback production → 預設關閉。"""
    assert src_pkg.FLASK_ENV == 'production'
    assert src_pkg.ENABLE_SWAGGER is False


def test_apidocs_not_registered_returns_404(client):
    """Swagger 未初始化時，/apidocs/ 應為一般 404（路由未註冊），不是 403 或轉址。"""
    resp = client.get('/apidocs/')
    assert resp.status_code == 404


def test_apispec_json_not_registered_returns_404(client):
    resp = client.get('/apispec_1.json')
    assert resp.status_code == 404


def test_root_returns_json_status_instead_of_redirect(client):
    """ENABLE_SWAGGER=False 時 `/` 不應轉址到 /apidocs/，改回傳簡單狀態 JSON。"""
    resp = client.get('/')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body == {'success': True, 'service': 'wms-api'}
