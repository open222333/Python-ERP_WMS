import os
import configparser

_cfg = configparser.ConfigParser()
_cfg.read('conf/config.ini')
_g = _cfg['GUNICORN'] if _cfg.has_section('GUNICORN') else {}

bind         = _g.get('BIND',         f"0.0.0.0:{os.environ.get('FLASK_PORT', '5000')}")
workers      = int(_g.get('WORKERS',      os.environ.get('GUNICORN_WORKERS', '2')))
threads      = int(_g.get('THREADS',      os.environ.get('GUNICORN_THREADS', '2')))
worker_class = _g.get('WORKER_CLASS', 'gthread')
timeout      = int(_g.get('TIMEOUT',  '120'))
preload_app  = True
accesslog    = '-'
errorlog     = '-'
loglevel     = 'info'
