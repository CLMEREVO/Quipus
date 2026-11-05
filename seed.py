from __future__ import annotations

import logging
from typing import Any
import storage

logger = logging.getLogger("quipus.seed")

# 让多源并发的通知共享同一个精确时间戳，模拟秒级同时送达
SEED_ITEMS: list[tuple[str, dict[str, Any]]] = [
    (
        "【教务处】重要通知：关于本周五下午全校停水检修的紧急通知，请同学们提前做好储水准备。",
        {
            "app_name": "教务处",
            "category": "重要/紧急待办",
            "title": "全校停水检修紧急通知",
            "summary": "本周五下午全校停水检修，请提前储水.",
            "is_urgent": True,
            "event_key": "全校停水"
        },
    ),
    # 以下三条快递通知属于【同一时刻】多源并发到达
    (
        "【菜鸟驿站】您的顺丰包裹已到达学校南门驿站，取件码 5-2-3008。",
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

_SEED_TIMES = ["08:12", "09:05", "15:15"]

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