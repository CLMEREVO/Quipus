from __future__ import annotations

import logging
from typing import Any
import storage

logger = logging.getLogger("quipus.seed")

# 让多源并发的通知共享同一个精确时间戳，模拟秒级同时送达
SEED_ITEMS: list[tuple[str, dict[str, Any]]] = [
    # 下面两条支付通知属于【同一时刻】多源并发到达
    (
        "【招商银行】您尾号1234的银行卡已成功支付11.90元。",
        {
            "app_name": "招商银行",
            "category": "其他类",
            "title": "支付成功",
            "summary": "已用银行卡支付11.90.",
            "is_urgent": False,
            "event_key": "支付提醒"
        },
    ),
    (
        "【微信支付】您已成功支付11.90元。",
        {
            "app_name": "微信支付",
            "category": "其他类",
            "title": "支付成功",
            "summary": "已支付11.90.",
            "is_urgent": False,
            "event_key": "支付提醒"
        },
    ),
    # 以下三条快递通知属于【同一时刻】多源并发到达
    (
        "【菜鸟】有一个包裹到菜鸟驿站，取件码 5-2-3008。",
        {
            "app_name": "菜鸟驿站",
            "category": "其他类",
            "title": "取件通知",
            "summary": "顺丰包裹已到南门驿站，取件码 5-2-3008。",
            "is_urgent": False,
            "event_key": "快递物流"
        },
    ),
    (
        "【支付宝】菜鸟驿站发来一条取件提醒，你有一个包裹到达驿站。",
        {
            "app_name": "支付宝",
            "category": "其他类",
            "title": "菜鸟驿站取件提醒",
            "summary": "有一个包裹到达菜鸟驿站。",
            "is_urgent": False,
            "event_key": "快递物流"
        },
    ),
    (
        "【淘宝网】您在淘宝购买的宝贝已送达菜鸟驿站，请及时取件。",
        {
            "app_name": "淘宝网",
            "category": "其他类",
            "title": "包裹已到菜鸟驿站",
            "summary": "宝贝已送达菜鸟驿站，请及时取件。",
            "is_urgent": False,
            "event_key": "快递物流"
        },
    ),
]

_SEED_TIMES = ["7:20", "7:20", "12:15", "12:15", "12:15"]

def _created_ats(n: int) -> list[str]:
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    return [f"{today} {_SEED_TIMES[i % len(_SEED_TIMES)]}:00" for i in range(n)]

def seed_if_empty() -> int:
    storage.init_db()
    return storage.save_many_if_empty(SEED_ITEMS, _created_ats(len(SEED_ITEMS)))

def force_seed_samples() -> int:
    storage.init_db()
    existing_items = storage.list_notifications(tab="overview", limit=1000)
    existing_texts = {item["original"] for item in existing_items}
    
    new_items_to_add = []
    new_times = []
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    
    for idx, (raw_text, result) in enumerate(SEED_ITEMS):
        if raw_text not in existing_texts:
            new_items_to_add.append((raw_text, result))
            new_times.append(f"{today} 10:00:0{idx}")
            
    if new_items_to_add:
        conn = storage._connect()
        added_count = 0
        with conn:
            for i, (raw, res) in enumerate(new_items_to_add):
                conn.execute(
                    """INSERT INTO notifications (created_at, raw_text, category, is_urgent, app_name, title, result_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    storage._to_row(new_times[i], raw, res)
                )
                added_count += 1
        conn.close()
        return added_count
    return 0