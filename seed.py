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
        "【慕课】单元测验即将截止，注意按时完成。",
        {
            "app_name": "慕课",
            "category": "重要/紧急待办",
            "title": "单元测验即将截止",
            "summary": "单元测验即将截止，请注意按时完成。",
            "is_urgent": True,
            "event_key": "慕课测验"
        },
    ),
    (
        "【晨跑人脸识别】你已在材料院-图书馆方向起点处 刷脸成功。起点刷脸6点35到7点10之间有效。",
        {
            "app_name": "晨跑打卡",
            "category": "其他类",
            "title": "晨跑起点刷脸成功",
            "summary": "已在材料院起点刷脸成功（多路摄像头已同步）。",
            "is_urgent": False,
            "event_key": "晨跑刷脸"
        },
    ),
    (
        "【淘宝网】淘宝提醒您有四张共655元消费券待领取，属于营销促销。",
        {
            "app_name": "淘宝网",
            "category": "无效广告/促销",
            "title": "淘宝655元消费券待领取",
            "summary": "淘宝提醒您有四张共655元消费券待领取，属于营销促销。",
            "is_urgent": False,
            "event_key": "淘宝促销"
        },
    ),
]

_SEED_TIMES = ["08:12", "09:05", "12:03", "15:15"]

def _created_ats(n: int) -> list[str]:
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    return [f"{today} {_SEED_TIMES[i % len(_SEED_TIMES)]}:00" for i in range(n)]

def seed_if_empty() -> int:
    storage.init_db()
    inserted = storage.save_many_if_empty(SEED_ITEMS, _created_ats(len(SEED_ITEMS)))
    if inserted:
        logger.info("数据库为空，已预置 %d 条真实场景测试数据", inserted)
    return inserted

def force_seed_samples() -> int:
    """主动刷新/重置示例数据，自动检测并跳过已存在的重复内容"""
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