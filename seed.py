from __future__ import annotations

import logging
from typing import Any
import storage

logger = logging.getLogger("quipus.seed")

# 默认示例数据：全部标记 seed=True，前端会显示「测试用」标签。
# 顺序即写入顺序（id 递增），快递状态机按接收顺序推演，所以顺序本身有意义。
SEED_ITEMS: list[tuple[str, dict[str, Any]]] = [
    # ---------------- 重要 / 紧急待办 ----------------
    (
        "【教务处】重要通知：本周五（11月13日）14:00-18:00全校停水检修，请各宿舍提前储水。",
        {
            "app_name": "教务处", "category": "重要/紧急待办",
            "title": "全校停水检修通知",
            "summary": "本周五 14:00-18:00 全校停水检修，请提前储水。",
            "is_urgent": True, "event_key": "停水通知", "seed": True,
        },
    ),
    (
        "【班长】重要提醒：数据结构第 4、5 章作业明天上课前交，逾期扣平时分。",
        {
            "app_name": "班长", "category": "重要/紧急待办",
            "title": "数据结构作业",
            "summary": "明天上课前交第 4、5 章作业，逾期扣平时分。",
            "is_urgent": True, "event_key": "数据结构作业", "seed": True,
        },
    ),
    (
        "变成周五之前",
        {
            "app_name": "班长", "category": "重要/紧急待办",
            "title": "时间变更通知",
            "summary": "变成周五之前",
            "is_urgent": True, "event_key": "作业变更",
            "is_time_change": True, "related_task": None, "seed": True,
        },
    ),

    # ---------------- 支付：两条同秒多源 ----------------
    (
        "【微信支付】微信支付凭证：已支付 11.90 元，收款方：南京邮电大学。",
        {
            "app_name": "微信支付", "category": "其他类",
            "title": "支付成功",
            "summary": "已支付 11.90 元（收款方：南京邮电大学）",
            "is_urgent": False, "event_key": "消费支付",
            "amount": 11.90, "direction": "expense", "seed": True,
        },
    ),
    (
        "【招商银行】您尾号 1234 的银行卡于 11 月 8 日 12:15 快捷支付 11.90 元。",
        {
            "app_name": "招商银行", "category": "其他类",
            "title": "银行卡支付",
            "summary": "尾号 1234 快捷支付 11.90 元",
            "is_urgent": False, "event_key": "消费支付",
            "amount": 11.90, "direction": "expense", "seed": True,
        },
    ),

    # ---------------- 快递：三条同秒多源到达 ----------------
    (
        "【菜鸟驿站】您的包裹已到南京邮电大学菜鸟驿站，取件码 5-2-3008，请及时取件。",
        {
            "app_name": "菜鸟驿站", "category": "其他类",
            "title": "取件通知",
            "summary": "包裹已到驿站，取件码 5-2-3008。",
            "is_urgent": False, "event_key": "快递物流", "seed": True,
        },
    ),
    (
        "【支付宝】菜鸟驿站：您有 1 个包裹已到达，取件码 5-2-3008，请凭码取件。",
        {
            "app_name": "支付宝", "category": "其他类",
            "title": "菜鸟驿站取件提醒",
            "summary": "有 1 个包裹到达驿站，取件码 5-2-3008。",
            "is_urgent": False, "event_key": "快递物流", "seed": True,
        },
    ),
    (
        "【淘宝网】您购买的宝贝已送达菜鸟驿站，取件码 5-2-3008，感谢使用菜鸟驿站。",
        {
            "app_name": "淘宝网", "category": "其他类",
            "title": "包裹已到菜鸟驿站",
            "summary": "宝贝已送达驿站，取件码 5-2-3008。",
            "is_urgent": False, "event_key": "快递物流", "seed": True,
        },
    ),

    # ---------------- 支付：单笔支出 ----------------
    (
        "【支付宝】您已成功付款 68.00 元，商户：南邮仙林食堂二楼。",
        {
            "app_name": "支付宝", "category": "其他类",
            "title": "食堂消费",
            "summary": "付款 68.00 元（南邮仙林食堂二楼）",
            "is_urgent": False, "event_key": "消费支付",
            "amount": 68.00, "direction": "expense", "seed": True,
        },
    ),

    # ---------------- 快递：第二件到达 ----------------
    (
        "【菜鸟】您的包裹已到南京邮电大学菜鸟驿站，取件码 13-4-1426。",
        {
            "app_name": "菜鸟", "category": "其他类",
            "title": "取件通知",
            "summary": "包裹已到驿站，取件码 13-4-1426。",
            "is_urgent": False, "event_key": "快递物流", "seed": True,
        },
    ),

    # ---------------- 支付：退款（收入） ----------------
    (
        "【淘宝】您的订单已退款 68.00 元，退款将原路退回支付宝账户。",
        {
            "app_name": "淘宝", "category": "其他类",
            "title": "订单退款",
            "summary": "退款 68.00 元，原路退回",
            "is_urgent": False, "event_key": "消费支付",
            "amount": 68.00, "direction": "income", "seed": True,
        },
    ),

    # ---------------- 快递：签收（无取件码，待用户确认） ----------------
    (
        "【菜鸟】您已签收一个包裹，剩余 1 个包裹待取。",
        {
            "app_name": "菜鸟", "category": "其他类",
            "title": "包裹签收通知",
            "summary": "已签收一个包裹，剩余 1 个待取。",
            "is_urgent": False, "event_key": "快递物流", "seed": True,
        },
    ),

    # ---------------- 快递：滞留提醒（待用户确认是否更新件数） ----------------
    (
        "【菜鸟】您有 3 个快递滞留在菜鸟驿站，时间已超过 24 小时，请尽快取件。",
        {
            "app_name": "菜鸟", "category": "其他类",
            "title": "快递滞留提醒",
            "summary": "3 个包裹滞留超 24 小时。",
            "is_urgent": False, "event_key": "快递物流", "seed": True,
        },
    ),

    # ---------------- 其他：刷脸打卡（同事件两条） ----------------
    (
        "你已在材料院-图书馆方向起点处刷脸成功。",
        {
            "app_name": "晨跑人脸识别", "category": "其他类",
            "title": "晨跑刷脸成功",
            "summary": "材料院-图书馆方向起点处刷脸成功。",
            "is_urgent": False, "event_key": "晨跑刷脸", "seed": True,
        },
    ),
    (
        "你已在材料院-图书馆方向起点处刷脸成功。",
        {
            "app_name": "晨跑人脸识别", "category": "其他类",
            "title": "晨跑刷脸成功",
            "summary": "材料院-图书馆方向起点处刷脸成功。",
            "is_urgent": False, "event_key": "晨跑刷脸", "seed": True,
        },
    ),

    # ---------------- 无效广告 / 促销 ----------------
    (
        "【淘宝】双 11 预售开启，全场满 300 减 50，点击抢先加购。",
        {
            "app_name": "淘宝", "category": "无效广告/促销",
            "title": "双 11 预售",
            "summary": "全场满 300 减 50。",
            "is_urgent": False, "event_key": "营销推广", "seed": True,
        },
    ),
    (
        "【京东】您的白条额度已提升至 8000 元，先享后付更轻松。",
        {
            "app_name": "京东", "category": "无效广告/促销",
            "title": "白条额度提升",
            "summary": "白条额度提升至 8000 元。",
            "is_urgent": False, "event_key": "营销推广", "seed": True,
        },
    ),
    (
        "【美团】您有 1 张 5 元无门槛外卖红包待领取，今日 24 点过期。",
        {
            "app_name": "美团", "category": "无效广告/促销",
            "title": "外卖红包",
            "summary": "5 元无门槛红包，今日 24 点过期。",
            "is_urgent": False, "event_key": "营销推广", "seed": True,
        },
    ),
]

# 与 SEED_ITEMS 一一对应的接收时间（HH:MM）。
# 同一条事件的多源推送共享同一分钟；顺序即 id 顺序，快递状态机按 id 推演。
_SEED_TIMES = [
    "07:30", "08:10", "08:20",        # 重要
    "12:15", "12:15",                 # 支付（同秒多源，合并为一笔）
    "12:15", "12:15", "12:15",        # 快递（同秒三源，合并为一件）
    "12:45",                          # 支付
    "12:51",                          # 快递第二件
    "13:05",                          # 退款
    "13:20",                          # 签收（待确认）
    "13:30",                          # 滞留（待确认）
    "07:26", "07:27",                 # 刷脸
    "09:10", "09:20", "09:50",        # 广告
]


def _created_ats(n: int) -> list[str]:
    today = storage.today_cn()
    return [f"{today} {_SEED_TIMES[i % len(_SEED_TIMES)]}:00" for i in range(n)]


def seed_if_empty() -> int:
    storage.init_db()
    return storage.save_many_if_empty(SEED_ITEMS, _created_ats(len(SEED_ITEMS)))


def force_seed_samples() -> int:
    storage.init_db()
    existing_items = storage.list_notifications(tab="overview", limit=1000)
    existing_texts = {item["original"] for item in existing_items}

    times = _created_ats(len(SEED_ITEMS))
    new_items = [
        (raw, res, times[i])
        for i, (raw, res) in enumerate(SEED_ITEMS)
        if raw not in existing_texts
    ]
    if not new_items:
        return 0

    conn = storage._connect()
    added = 0
    try:
        with conn:
            for raw, res, stamp in new_items:
                conn.execute(
                    """INSERT INTO notifications
                       (created_at, raw_text, category, is_urgent, app_name, title, result_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    storage._to_row(stamp, raw, res),
                )
                added += 1
    finally:
        conn.close()
    return added
