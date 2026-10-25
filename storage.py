from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).with_name("quipus.db")

TAB_TO_CATEGORY: dict[str, str | list[str] | None] = {
    "overview": None,
    "urgent": "重要/紧急待办",
    "other": ["其他类", "物流与消费"],
    "blocked": "无效广告/促销",
    "express": "聚合体",
    "custom": None,
}

_INSERT_SQL = """INSERT INTO notifications
                 (created_at, raw_text, category, is_urgent, app_name, title, result_json)
                 VALUES (?, ?, ?, ?, ?, ?, ?)"""

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

CREATE TABLE IF NOT EXISTS custom_rules (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    app_keyword  TEXT    NOT NULL DEFAULT '',
    text_keyword TEXT    NOT NULL,
    target_cat   TEXT    NOT NULL,
    is_urgent    INTEGER NOT NULL DEFAULT 0
);
"""

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    with closing(_connect()) as conn:
        with conn:
            conn.executescript(_SCHEMA)

def apply_custom_rules(app_name: str, raw_text: str, result: dict[str, Any]) -> dict[str, Any]:
    with closing(_connect()) as conn:
        rules = conn.execute("SELECT * FROM custom_rules").fetchall()
        for r in rules:
            app_kw = r["app_keyword"].strip()
            text_kw = r["text_keyword"].strip()
            
            app_matched = (not app_kw) or (app_kw in app_name)
            text_matched = text_kw in raw_text
            
            if app_matched and text_matched:
                result["category"] = r["target_cat"]
                result["is_urgent"] = bool(r["is_urgent"])
                result["summary"] = f"[用户自定义规则命中] {result.get('summary', '')}"
                break
    return result

def _row_to_item(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "original": row["raw_text"],
        "data": json.loads(row["result_json"]),
    }

def _to_row(created_at: str, raw_text: str, result: dict[str, Any]) -> tuple:
    return (
        created_at,
        raw_text,
        str(result.get("category") or "其他类"),
        1 if result.get("is_urgent") else 0,
        str(result.get("app_name") or ""),
        str(result.get("title") or ""),
        json.dumps(result, ensure_ascii=False),
    )

def save_notification(raw_text: str, result: dict[str, Any]) -> dict[str, Any]:
    app_name = str(result.get("app_name") or "")
    result = apply_custom_rules(app_name, raw_text, result)
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with closing(_connect()) as conn:
        with conn:
            cur = conn.execute(_INSERT_SQL, _to_row(now, raw_text, result))
            row_id = cur.lastrowid
    return {"id": row_id, "created_at": now, "original": raw_text, "data": result}

def save_many_if_empty(
    items: list[tuple[str, dict[str, Any]]],
    created_ats: list[str] | None = None,
) -> int:
    if not items:
        return 0
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute("SELECT COUNT(*) AS n FROM notifications").fetchone()["n"]
        if existing:
            conn.execute("ROLLBACK")
            return 0
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            _to_row(created_ats[i] if created_ats else now, raw, result)
            for i, (raw, result) in enumerate(items)
        ]
        conn.executemany(_INSERT_SQL, rows)
        conn.execute("COMMIT")
        return len(rows)
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()

def list_notifications(
    tab: str = "overview",
    limit: int = 200,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    if tab not in TAB_TO_CATEGORY:
        raise ValueError(f"tab 只能是 {sorted(TAB_TO_CATEGORY)}")
    
    if tab == "express":
        return []

    sql = "SELECT * FROM notifications"
    where: list[str] = []
    params: list[Any] = []

    category = TAB_TO_CATEGORY[tab]
    if category:
        if isinstance(category, list):
            placeholders = ",".join(["?"] * len(category))
            where.append(f"category IN ({placeholders})")
            params.extend(category)
        else:
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

    other_count = by_cat.get("其他类", 0) + by_cat.get("物流与消费", 0)

    return {
        "total": total,
        "urgent": urgent,
        "blocked": by_cat.get("无效广告/促销", 0),
        "other": other_count,
        "by_category": by_cat,
    }

def clear() -> int:
    with closing(_connect()) as conn:
        with conn:
            n = conn.execute("SELECT COUNT(*) AS n FROM notifications").fetchone()["n"]
            conn.execute("DELETE FROM notifications")
    return n

def get_custom_rules() -> list[dict[str, Any]]:
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT * FROM custom_rules ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

def add_custom_rule(app_keyword: str, text_keyword: str, target_cat: str) -> int:
    is_urgent = 1 if target_cat == "重要/紧急待办" else 0
    with closing(_connect()) as conn:
        with conn:
            cur = conn.execute(
                "INSERT INTO custom_rules (app_keyword, text_keyword, target_cat, is_urgent) VALUES (?, ?, ?, ?)",
                (app_keyword, text_keyword, target_cat, is_urgent)
            )
            return cur.lastrowid

def delete_custom_rule(rule_id: int) -> int:
    with closing(_connect()) as conn:
        with conn:
            conn.execute("DELETE FROM custom_rules WHERE id = ?", (rule_id,))
    return rule_id

def reset_custom_rules() -> None:
    with closing(_connect()) as conn:
        with conn:
            conn.execute("DELETE FROM custom_rules")