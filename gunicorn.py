import gc
import os
import configparser
import multiprocessing

_cfg = configparser.ConfigParser()
_cfg.read('conf/config.ini')
_g = _cfg['GUNICORN'] if _cfg.has_section('GUNICORN') else {}


def _opt(key: str, env: str, default: str) -> str:
    """覆寫優先序：conf/config.ini [GUNICORN] > 環境變數 > 預設值"""
    return _g.get(key, os.environ.get(env, default))


bind = _opt('BIND', 'GUNICORN_BIND', f"0.0.0.0:{os.environ.get('FLASK_PORT', '5000')}")

# [OPT-MEM] 少程序、多執行緒：每個 worker 程序約 80MB，執行緒共用程序記憶體。
# 原預設 max(2, CPU*2+1) × 2 threads 在 1 vCPU 主機為 3 程序 / 6 併發；
# 改為 max(2, CPU+1) × 4 threads → 1 vCPU 為 2 程序 / 8 併發，
# 少一個程序（約省 80MB）且 SSE 長連線可佔用的併發數反而增加。
# 本專案請求以 MongoDB / Redis / 外部 API 等 I/O 等待為主，GIL 影響小。
workers = int(_opt('WORKERS', 'GUNICORN_WORKERS', str(max(2, multiprocessing.cpu_count() + 1))))
threads = int(_opt('THREADS', 'GUNICORN_THREADS', '4'))
worker_class = _opt('WORKER_CLASS', 'GUNICORN_WORKER_CLASS', 'gthread')
timeout = int(_opt('TIMEOUT', 'GUNICORN_TIMEOUT', '120'))

# [OPT-MEM] 定期回收 worker：Python 程序記憶體碎片化後通常不會還給系統，
# 長時間執行會緩慢膨脹。處理 N 個請求後優雅重啟該 worker，jitter 避免同時重啟。
# 被回收的 worker 上的 SSE 連線會斷線，前端（KitchenView / OrderView）會自動重連。
# 設為 0 可停用。
max_requests = int(_opt('MAX_REQUESTS', 'GUNICORN_MAX_REQUESTS', '1000'))
max_requests_jitter = int(_opt('MAX_REQUESTS_JITTER', 'GUNICORN_MAX_REQUESTS_JITTER', '100'))

preload_app = True
accesslog = '-'
errorlog = '-'
loglevel = 'info'


def pre_fork(server, worker):
    """[OPT-MEM] fork 前凍結 GC 追蹤的物件：preload 載入的模組物件移到永久世代，
    子程序的 GC 不再掃描（寫入）這些物件，copy-on-write 共享頁面較不會被複製，
    降低每個 worker 的實際記憶體佔用。"""
    gc.freeze()
