import json
import secrets
from os.path import join

# 本機開發：自動載入 .env（Docker 不影響，docker-compose 已透過 env_file 注入）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_FLASK_JSON_PATH = join('conf', 'flask.json')
with open(_FLASK_JSON_PATH, 'r') as _f:
    _flask_conf = json.load(_f)

if not _flask_conf.get('SECRET_KEY'):
    _flask_conf['SECRET_KEY'] = secrets.token_hex(32)
    with open(_FLASK_JSON_PATH, 'w') as _f:
        json.dump(_flask_conf, _f, indent=2)
    print('[init] 已自動產生 SECRET_KEY 並寫入 conf/flask.json')

from app import create_app
from conf.config import TestingConfig
from src.models.user import User
from src.models.user_template import UserTemplate
from src import FLASK_PORT


app = create_app(TestingConfig)

# ── 確保預設 admin 帳號存在 ──
admin = User.find_by_username('admin')
if not admin:
    User.create('admin', 'admin', role='admin')
    print('[init] 已建立預設帳號 admin / admin，請登入後立即修改密碼')
elif not admin.get('role'):
    User.update(str(admin['_id']), role='admin')
    print('[init] 已修正 admin 帳號 role 為 admin')

# ── 確保系統預設「管理者」使用者模板存在，並指派給 admin ──
# ensure_defaults() 會在 user_templates collection 建立 is_system=True 的模板（若尚未存在）
admin_tmpl_id = UserTemplate.ensure_defaults()
admin = User.find_by_username('admin')   # re-fetch（帳號可能剛建立）
if admin:
    current_tid = admin.get('template_id')
    # 需要指派的條件：
    #   1. 尚無模板
    #   2. 有模板 ID 但在新 collection (user_templates) 查無此 ID
    #      （換 collection 後的升級遷移情境）
    needs_assign = not current_tid or not UserTemplate.find_by_id(str(current_tid))
    if needs_assign:
        User.update(str(admin['_id']), template_id=admin_tmpl_id)
        print('[init] 已將「管理者」使用者模板指派給 admin 帳號')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=FLASK_PORT, debug=True)
