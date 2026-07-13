import logging
import threading
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from src import MONGO_URI, MONGO_DB


_lock = threading.Lock()
_client = None
_db = None
_logger = logging.getLogger(__name__)

# [OPT-N1] 交易支援探測結果快取（None=未探測 / True / False）。
# standalone MongoDB 與 mongomock（測試環境）皆不支援 session/transaction，
# 探測一次即可，避免每次呼叫都重新嘗試。
_txn_support = None
_txn_lock = threading.Lock()


def get_db():
    global _client, _db
    if _db is None:
        with _lock:
            if _db is None:
                _client = MongoClient(MONGO_URI)
                _db = _client[MONGO_DB]
    return _db


def get_client():
    """[OPT-N1] 取得底層 MongoClient（供開啟 session/transaction 用）。"""
    get_db()  # 確保已初始化
    return _client


def supports_transactions() -> bool:
    """
    [OPT-N1] 探測目前 MongoDB 連線是否支援多文件交易（需 replica set / mongos）。
    - mongomock（測試環境）：start_session() 直接拋 NotImplementedError → False
    - standalone MongoDB：start_transaction() 內的第一個操作會拋
      OperationFailure（"Transaction numbers are only allowed on a replica
      set member or mongos"）→ False
    - replica set：探測成功 → True
    結果快取於程序生命週期內，避免每次交易呼叫都重新探測一次。
    """
    global _txn_support
    if _txn_support is not None:
        return _txn_support
    with _txn_lock:
        if _txn_support is not None:
            return _txn_support
        try:
            client = get_client()
            db = get_db()
            with client.start_session() as session:
                with session.start_transaction():
                    db.command('ping', session=session)
                session.abort_transaction()
            _txn_support = True
        except Exception as e:  # noqa: BLE001 — 任何探測失敗一律視為不支援
            _logger.info(
                '[OPT-N1] MongoDB 不支援多文件交易（standalone 或測試環境），'
                '出入庫完成流程將退回原本的循序寫入：%s', e)
            _txn_support = False
    return _txn_support


def reset_transaction_probe():
    """[OPT-N1] 測試用：重置交易支援探測快取。"""
    global _txn_support
    _txn_support = None
