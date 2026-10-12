"""
外送平台 adapters 共用工具。

[D1] 平台原始訂單狀態 → 系統內部狀態（src.constants.DeliveryOrderStatus）的轉換。
各 adapter 定義自己的 STATUS_MAP（key 一律小寫），normalize_order() 透過
map_platform_status() 轉換：
- 'status'          → 內部狀態；平台值無法辨識時為 None（呼叫端決定如何處理）
- 'platform_status' → 平台原始值（保留供追查與日後補對照）
"""
import logging

logger = logging.getLogger(__name__)


def map_platform_status(platform: str, raw_status, status_map: dict):
    """回傳 (internal_status | None, platform_status_raw)"""
    raw = str(raw_status or '').strip()
    internal = status_map.get(raw.lower())
    if raw and internal is None:
        logger.warning('外送平台 %s 未知訂單狀態 %r，未對應到內部狀態（請補 STATUS_MAP）',
                       platform, raw)
    return internal, raw
