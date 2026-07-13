# [OPT-N2] 可觀測性模組：request-id 追蹤、結構化日誌、慢請求記錄、Sentry（選配）
"""
可觀測性（Observability）— 由 app/__init__.py 的 create_app() 呼叫 init_observability(app)。

功能：
1. Request-ID：
   - before_request 沿用 header `X-Request-ID`（僅接受 1-64 字元的英數/-/_，
     避免 log 注入），否則產生 uuid4().hex[:16]，存入 flask.g.request_id。
   - after_request 回寫至 response header，方便前端 / nginx log 關聯。
   - RequestIdFilter（logging.Filter）把 request_id 注入所有經過 handler 的
     log record；無 request context 時為 '-'。
2. 結構化日誌：
   - env `LOG_JSON=1`：root logger 的 handler 換成 JSON formatter
     （time/level/logger/message/request_id，stdlib json，無額外依賴）。
   - 預設：文字格式，但加上 request_id 欄位。
3. 慢請求記錄：
   - 超過 env `SLOW_REQUEST_MS`（預設 1000）以 warning 記
     method/path/status/耗時/request_id。
   - 排除 SSE（路徑含 /stream，長連線必然超過閾值）。
4. Sentry（選配）：
   - env `SENTRY_DSN` 有值才 import sentry_sdk 並 init（Flask integration）。
   - 未安裝 sentry-sdk 時 log warning，不中斷啟動。

環境變數一覽：
    LOG_JSON=1          啟用 JSON 結構化日誌（預設文字格式）
    SLOW_REQUEST_MS     慢請求閾值毫秒（預設 1000）
    SENTRY_DSN          Sentry DSN（未設定則完全不載入 sentry_sdk）
    SENTRY_TRACES_SAMPLE_RATE   Sentry APM 取樣率（預設 0，不開 tracing）
"""
import json
import logging
import os
import re
import time
import uuid

from flask import g, has_request_context, request

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = 'X-Request-ID'
DEFAULT_SLOW_REQUEST_MS = 1000

# 合法的外部傳入 request id（避免任意 header 內容進入 log）
_RID_PATTERN = re.compile(r'^[A-Za-z0-9_\-]{1,64}$')

# 文字格式：維持一般 stdlib 風格，僅加上 request_id
TEXT_LOG_FORMAT = '[%(asctime)s] %(levelname)s %(name)s [%(request_id)s] %(message)s'

_logging_configured = False


# ─────────────────────────────────────────────────────────────
#  1. Request-ID
# ─────────────────────────────────────────────────────────────
class RequestIdFilter(logging.Filter):
    """把 flask.g.request_id 注入 log record；無 request context 時為 '-'。"""

    def filter(self, record):
        if has_request_context():
            record.request_id = getattr(g, 'request_id', '-') or '-'
        else:
            record.request_id = '-'
        return True


def _resolve_request_id():
    """沿用合法的 X-Request-ID header，否則產生新 id（uuid4 hex 前 16 碼）。"""
    incoming = (request.headers.get(REQUEST_ID_HEADER) or '').strip()
    if incoming and _RID_PATTERN.match(incoming):
        return incoming
    return uuid.uuid4().hex[:16]


# ─────────────────────────────────────────────────────────────
#  2. 結構化日誌
# ─────────────────────────────────────────────────────────────
class JsonRequestFormatter(logging.Formatter):
    """JSON log formatter（stdlib json，無額外依賴）。"""

    def format(self, record):
        payload = {
            'time': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'request_id': getattr(record, 'request_id', '-'),
        }
        if record.exc_info:
            payload['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _setup_logging():
    """裝飾 root logger 的 handler：注入 request_id filter 與 formatter。

    小心不破壞既有設定：
    - root 已有 handler（gunicorn / 其他設定）→ 只加 filter、換 formatter。
    - root 無 handler → 補一個 StreamHandler（否則走 lastResort，格式不可控）。
    - 不改動 root level（維持現行行為）。
    """
    global _logging_configured
    if _logging_configured:
        return
    _logging_configured = True

    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())

    rid_filter = RequestIdFilter()
    use_json = os.getenv('LOG_JSON') == '1'
    formatter = JsonRequestFormatter() if use_json else logging.Formatter(TEXT_LOG_FORMAT)
    for handler in root.handlers:
        handler.addFilter(rid_filter)
        handler.setFormatter(formatter)

    # Flask app.logger 預設掛的 default_handler 不經 root，需另外裝飾
    try:
        from flask.logging import default_handler
        default_handler.addFilter(rid_filter)
        default_handler.setFormatter(formatter)
    except ImportError:  # pragma: no cover
        pass


# ─────────────────────────────────────────────────────────────
#  3. 慢請求
# ─────────────────────────────────────────────────────────────
def _slow_threshold_ms():
    """每次讀 env，方便測試/線上動態調整；非法值回預設 1000。"""
    raw = os.getenv('SLOW_REQUEST_MS')
    if not raw:
        return DEFAULT_SLOW_REQUEST_MS
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_SLOW_REQUEST_MS


def _is_sse_path(path):
    """SSE 長連線（/stream）必然超過閾值，排除慢請求記錄。"""
    return '/stream' in path


# ─────────────────────────────────────────────────────────────
#  4. Sentry（選配）
# ─────────────────────────────────────────────────────────────
def _init_sentry():
    dsn = os.getenv('SENTRY_DSN')
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0') or 0),
            environment=os.getenv('FLASK_ENV', 'production'),
            send_default_pii=False,
        )
        logger.info('Sentry 已啟用（FlaskIntegration）')
    except ImportError:
        logger.warning(
            'SENTRY_DSN 已設定但 sentry-sdk 未安裝，略過 Sentry 初始化。'
            '安裝方式：pip install "sentry-sdk[flask]"')
    except Exception as e:  # init 失敗不可中斷應用啟動
        logger.warning('Sentry 初始化失敗，略過：%s', e)


# ─────────────────────────────────────────────────────────────
#  入口
# ─────────────────────────────────────────────────────────────
def init_observability(app):
    """掛上 request-id / 日誌 / 慢請求 / Sentry。冪等（重複呼叫無副作用）。"""
    if app.extensions.get('observability'):
        return
    app.extensions['observability'] = True

    _setup_logging()
    _init_sentry()

    @app.before_request
    def _obs_before_request():
        g.request_id = _resolve_request_id()
        g._obs_start = time.perf_counter()

    @app.after_request
    def _obs_after_request(response):
        rid = getattr(g, 'request_id', None)
        if rid:
            response.headers[REQUEST_ID_HEADER] = rid
        start = getattr(g, '_obs_start', None)
        if start is not None and not _is_sse_path(request.path):
            elapsed_ms = (time.perf_counter() - start) * 1000
            if elapsed_ms >= _slow_threshold_ms():
                logger.warning(
                    'slow request: %s %s status=%s elapsed=%.0fms request_id=%s',
                    request.method, request.path, response.status_code,
                    elapsed_ms, rid or '-')
        return response
