"""
[OPT-N3] Redis JSON 快取 helper

設計原則：快取只是加速器，Redis 故障時一律 fallback 直接執行 producer，
絕不能讓快取層故障影響主流程（例如顧客掃碼點餐）。
"""
import json
import logging

from src.redis_client import get_redis

logger = logging.getLogger(__name__)


def cached_json(key: str, ttl: int, producer):
    """
    讀取 Redis JSON 快取；miss 時呼叫 producer() 取值並回填（TTL 秒）。

    - Redis 讀取失敗 → 直接呼叫 producer，並跳過回填
    - producer 回傳 None → 不快取（避免快取「不存在」造成短暫誤判）
    - 快取值以 json.dumps(default=str) 序列化，須為 JSON 可序列化結構
    """
    r = None
    try:
        r = get_redis()
        raw = r.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception as e:  # noqa: BLE001 — 快取故障不可影響主流程
        logger.warning('[OPT-N3] cache read failed key=%s: %s', key, e)
        r = None

    value = producer()

    if value is not None and r is not None:
        try:
            r.setex(key, ttl, json.dumps(value, default=str))
        except Exception as e:  # noqa: BLE001
            logger.warning('[OPT-N3] cache write failed key=%s: %s', key, e)
    return value


def invalidate(pattern: str) -> int:
    """
    以 scan_iter 刪除符合 pattern 的快取 key（例如 'cache:cust_menu:*'）。
    回傳刪除數量；Redis 故障時記 log 後回傳 0（不拋例外）。
    """
    try:
        r = get_redis()
        deleted = 0
        for k in r.scan_iter(match=pattern, count=200):
            deleted += r.delete(k)
        return deleted
    except Exception as e:  # noqa: BLE001
        logger.warning('[OPT-N3] cache invalidate failed pattern=%s: %s', pattern, e)
        return 0
