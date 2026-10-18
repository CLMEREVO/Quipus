r"""预置测试数据 —— 云端部署后，评委一打开页面就能看到内容。

作用：
1. 服务启动、数据库为空时，自动灌入 8 条真实感强的通知
2. 数据库里已经有数据时**什么都不做**（不会重复灌、不会覆盖评委自己输入的内容）

数据覆盖三类（对应前端左侧三个标签）：
    重要/紧急待办  3 条：教务停水、图书到期、信用卡账单
    物流与消费     3 条：淘宝发货、菜鸟取件、美团外卖
    无效广告/促销  2 条：京东优惠券、机构招生广告

字段和队长的 clean_notification_text 输出完全一致：
    app_name / category / title / summary / is_urgent
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import storage

logger = logging.getLogger("quipus.seed")

# (原始通知文本, 解析结果)
SEED_ITEMS: list[tuple[str, dict[str, Any]]] = [
    # ---------------- 重要/紧急待办 ----------------
    (
        "【教务处】重要通知：关于本周五下午 14:00-18:00 全校停水检修的紧急通知，请同学们提前做好储水准备。",
        {
            "app_name": "教务处",
            "category": "重要/紧急待办",
            "title": "周五下午全校停水检修",
            "summary": "本周五 14:00-18:00 全校停水检修，请提前储水。",
            "is_urgent": True,
        },
    ),
    (
        "【图书馆】读者您好，您借阅的《深入浅出计算机组成原理》将于明天到期，请及时归还或登录系统办理续借。",
        {
            "app_name": "图书馆",
            "category": "重要/紧急待办",
            "title": "借阅图书明天到期",
            "summary": "《深入浅出计算机组成原理》明天到期，请归还或续借。",
            "is_urgent": True,
        },
    ),
    (
        "【招商银行】尊贵的信用卡客户，您的本期账单金额 3,250.00 元，最后还款日为 10月25日，请按时还款以免影响征信。",
        {
            "app_name": "招商银行",
            "category": "重要/紧急待办",
            "title": "信用卡账单 3250 元待还",
            "summary": "本期账单 3250 元，最后还款日 10月25日。",
            "is_urgent": True,
        },
    ),
    # ---------------- 物流与消费 ----------------
    (
        "【淘宝网】亲爱的会员，您购买的羽绒服已由顺丰速运发货，运单号 SF12345678，请注意查收。",
        {
            "app_name": "淘宝网",
            "category": "物流与消费",
            "title": "羽绒服已发货",
            "summary": "您购买的羽绒服已由顺丰发出，运单号 SF12345678。",
            "is_urgent": False,
        },
    ),
    (
        "【菜鸟驿站】您的顺丰包裹已到达学校南门驿站，取件码 5-2-3008，请于 20:00 前取件。",
        {
            "app_name": "菜鸟驿站",
            "category": "物流与消费",
            "title": "包裹已到南门驿站",
            "summary": "顺丰包裹已到学校南门驿站，取件码 5-2-3008，20:00 前取。",
            "is_urgent": False,
        },
    ),
    (
        "【美团外卖】您的骑士正在为您配送“黄焖鸡米饭”，预计 13:15 送达，请保持电话畅通。",
        {
            "app_name": "美团外卖",
            "category": "物流与消费",
            "title": "外卖预计 13:15 送达",
            "summary": "骑士正在配送黄焖鸡米饭，预计 13:15 送达。",
            "is_urgent": False,
        },
    ),
    # ---------------- 无效广告/促销 ----------------
    (
        "【京东】您的领券中心掉落一张满199减100元全场通用券，限时2小时领取，点击抢购 https://jd.com/xxx",
        {
            "app_name": "京东",
            "category": "无效广告/促销",
            "title": "满199减100元优惠券",
            "summary": "京东全场通用券满199减100，限时2小时领取。",
            "is_urgent": False,
        },
    ),
    (
        "【XX教育】零基础大二学生如何逆袭搞定 Python 大模型开发？名额仅剩5位，点击链接报名送公开课。",
        {
            "app_name": "XX教育",
            "category": "无效广告/促销",
            "title": "Python 大模型课程招生",
            "summary": "大模型开发课程招生广告，名额仅剩5位。",
            "is_urgent": False,
        },
    ),
]

# 让时间看起来自然一点（同一天的不同时刻），而不是 8 条一模一样的时间戳
_SEED_TIMES = ["08:12", "09:05", "09:48", "11:20", "12:03", "12:40", "15:15", "16:32"]


def _created_ats(n: int) -> list[str]:
    today = datetime.now().strftime("%Y-%m-%d")
    return [f"{today} {_SEED_TIMES[i % len(_SEED_TIMES)]}:00" for i in range(n)]


def seed_if_empty() -> int:
    """数据库为空时灌入预置数据，返回本次插入的条数（已有数据则返回 0）。"""
    storage.init_db()
    inserted = storage.save_many_if_empty(SEED_ITEMS, _created_ats(len(SEED_ITEMS)))
    if inserted:
        logger.info("数据库为空，已预置 %d 条测试数据", inserted)
    else:
        logger.info("数据库里已有数据，跳过预置")
    return inserted


if __name__ == "__main__":
    # 想手动重灌：先清空再灌
    logging.basicConfig(level=logging.INFO)
    removed = storage.clear()
    print(f"已清空 {removed} 条")
    print(f"已预置 {seed_if_empty()} 条")
    print("现在的统计：", storage.stats())
