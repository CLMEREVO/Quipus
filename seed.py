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
        "【班级群】吴狄龙：26号之前交数据结构4、5章作业p70扩展题2 6 7 p115扩展题4 5 8 11 12。",
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
        "【班级群】吴狄龙：数据结构作业变成周五之前交！",
        {
            "app_name": "微信群",
            "category": "重要/紧急待办",
            "title": "数据结构作业截止时间更改",
            "summary": "作业截止时间变更为周五之前。",
            "is_urgent": True,
            "event_key": "数据结构作业"
        },
    ),
    (
        "【班级群】杨振宇：本周三下午8、9节你们班来补物理实验课《弗兰克-赫兹实验》，教二427。",
        {
            "app_name": "微信群",
            "category": "重要/紧急待办",
            "title": "物理实验课临时补课通知",
            "summary": "本周三下午8、9节教二427补物理实验。",
            "is_urgent": True,
            "event_key": "物理实验补课"
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
        "【微信支付】您通过微信支付向“校园一卡通”成功充值 50.00 元。",
        {
            "app_name": "微信支付",
            "category": "其他类",
            "title": "一卡通充值成功",
            "summary": "成功充值 50.00 元。",
            "is_urgent": False,
            "event_key": "一卡通充值"
        },
    ),
    (
        "【招商银行】您的尾号1234账户于今日完成快捷支付支出 50.00 元。",
        {
            "app_name": "招商银行",
            "category": "其他类",
            "title": "银行卡支出提醒",
            "summary": "快捷支付支出 50.00 元（双通道联动已确认）。",
            "is_urgent": False,
            "event_key": "一卡通充值"
        },
    ),
    (
        "【菜鸟驿站】您的顺丰包裹已到达学校南门驿站，取件码 5-2-3008。",
        {
            "app_name": "菜鸟驿站",
            "category": "其他类",
            "title": "快递已到南门驿站",
            "summary": "顺丰包裹已到南门驿站，取件码 5-2-3008。",
            "is_urgent": False,
            "event_key": "快递物流"
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

_SEED_TIMES = ["08:12", "09:05", "09:48", "11:20", "12:03", "12:40", "15:15", "16:32", "18:00"]

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