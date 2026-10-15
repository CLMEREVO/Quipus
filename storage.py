r"""历史通知的存储层（SQLite）。

为什么要存后端：现在前端用 historyList 在浏览器内存里管状态，一刷新就没了，
而且筛选全靠前端算。放到后端存，前端只要一次 GET 就能按分类拉数据。

为什么用 SQLite：sqlite3 是 Python 标准库，不用 pip 装任何东西；
而且 uvicorn --reload 每次改代码都会重启进程，用内存列表数据会一直被清空，
存 SQLite 就不会丢。

数据库文件：同目录的 quipus.db（已加进 .gitignore）
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).with_name("quipus.db")

# 前端左侧边栏的标签 -> 数据库里的分类
# 前端 currentTab 的取值是 overview / blocked / express（见 index.html）
TAB_TO_CATEGORY: dict[str, str | None] = {
    "overview": None,             # 总览：全部
    "blocked": "无效广告/促销",    # 已拦截广告
    "express": "物流与消费",       # 聚合快递与消费
    "urgent": "重要/紧急待办",     # 重要/紧急待办
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,
    raw_text    TEXT    NOT NULL,
    category    TEXT    NOT NULL DEFAULT '',
    is_urgent   INTEGER NOT NULL DEFAULT 0,
    app_name    TEXT    NOT NULL DEFAULT '',
    title       TEXT    NOT NULL DEFAULT '',
    result_json TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_category ON notifications(category);
CREATE INDEX IF NOT EXISTS idx_created  ON notifications(id DESC);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表。每次服务启动时调一次，已存在就什么都不做。"""
    with closing(_connect()) as conn:
        with conn:
            conn.executescript(_SCHEMA)


def _row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    """转成前端直接能用的形状，和 index.html 里的 formattedItem 一致。"""
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "original": row["raw_text"],
        "data": json.loads(row["result_json"]),
    }


def save_notification(raw_text: str, result: dict[str, Any]) -> dict[str, Any]:
    """存一条，返回带 id 的记录。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with closing(_connect()) as conn:
        with conn:
            cur = conn.execute(
                """INSERT INTO notifications
                   (created_at, raw_text, category, is_urgent, app_name, title, result_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    now,
                    raw_text,
                    str(result.get("category") or ""),
                    1 if result.get("is_urgent") else 0,
                    str(result.get("app_name") or ""),
                    str(result.get("title") or ""),
                    json.dumps(result, ensure_ascii=False),
                ),
            )
            row_id = cur.lastrowid
    return {"id": row_id, "created_at": now, "original": raw_text, "data": result}


def list_notifications(
    tab: str = "overview",
    limit: int = 200,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    """按左侧标签拉历史。tab 见 TAB_TO_CATEGORY。"""
    if tab not in TAB_TO_CATEGORY:
        raise ValueError(f"tab 只能是 {sorted(TAB_TO_CATEGORY)}")

    sql = "SELECT * FROM notifications"
    where: list[str] = []
    params: list[Any] = []

    category = TAB_TO_CATEGORY[tab]
    if category:
        where.append("category = ?")
        params.append(category)
    if keyword:
        where.append("(raw_text LIKE ? OR title LIKE ? OR app_name LIKE ?)")
        params += [f"%{keyword}%"] * 3
    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, min(int(limit), 1000)))

    with closing(_connect()) as conn:
        return [_row_to_item(r) for r in conn.execute(sql, params)]


def stats() -> dict[str, Any]:
    """给前端顶部的计数用：总数、已拦截广告、物流、待办、紧急。"""
    with closing(_connect()) as conn:
        by_cat = {
            r["category"]: r["n"]
            for r in conn.execute(
                "SELECT category, COUNT(*) AS n FROM notifications GROUP BY category"
            )
        }
        total = conn.execute("SELECT COUNT(*) AS n FROM notifications").fetchone()["n"]
        urgent = conn.execute(
            "SELECT COUNT(*) AS n FROM notifications WHERE is_urgent = 1"
        ).fetchone()["n"]

    return {
        "total": total,
        "urgent": urgent,
        "blocked": by_cat.get("无效广告/促销", 0),
        "express": by_cat.get("物流与消费", 0),
        "todo": by_cat.get("重要/紧急待办", 0),
        "by_category": by_cat,
    }


def clear() -> int:
    """清空历史，返回删掉的条数。"""
    with closing(_connect()) as conn:
        with conn:
            n = conn.execute("SELECT COUNT(*) AS n FROM notifications").fetchone()["n"]
            conn.execute("DELETE FROM notifications")
    return n
