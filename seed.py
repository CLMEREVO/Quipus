from __future__ import annotations

import logging
from typing import Any
import storage

logger = logging.getLogger("quipus.seed")

SEED_ITEMS: list[tuple[str, dict[str, Any]]] = [
    (
        "【教务处】重要通知：关于本周五下午全校停水检修的紧急通知，请同学们提前做好储水准备。",
        {
            "app_name": "教务处",
            "category": "重要/紧急待办",
            "title": "全校停水检修紧急通知",
            "summary": "本周五下午全校停水检修，请提前储水。",
            "is_urgent": True,
            "event_key": "全校停水"
        },
    ),
    (
        "【班级群】班长：26号之前交数据结构4、5章作业p70扩展题2 6 7 p115扩展题4 5 8 11 12。",
        {
            "app_name": "微信群",
            "category": "重要/紧急待办",
            "title": "数据结构作业提交",
            "summary": "26号前交数据结构第四、五章指定扩展题。",
            "is_urgent": True,
            "event_key": "数据结构作业"
        },
    ),
    (
        "【京东】您的领券中心掉落一张满199减100元全场通用券，限时2小时领取。",
        {
            "app_name": "京东",
            "category": "无效广告/促销",
            "title": "满199减100元优惠券",
            "summary": "全场通用券满199减100，限时领取。",
            "is_urgent": False,
            "event_key": "京东促销"
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