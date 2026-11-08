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
                result["custom_rule"] = True
                # 自定义规则要求"直接已读"的，前端不再展示
                if r["target_cat"] == "无效广告/促销":
                    result["auto_read"] = True
                result["summary"] = f"[自定义] {result.get('summary', '')}"
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

def delete_notification(item_id: int) -> int:
    conn = _connect()
    try:
        with conn:
            before = conn.execute("SELECT COUNT(*) AS n FROM notifications").fetchone()["n"]
            conn.execute("DELETE FROM notifications WHERE id = ?", (item_id,))
            after = conn.execute("SELECT COUNT(*) AS n FROM notifications").fetchone()["n"]
        return before - after
    finally:
        conn.close()

def update_notification(item_id: int, patch: dict[str, Any]) -> dict[str, Any] | None:
    """把 patch 合并进某条通知的 result_json（用于用户确认时间变更后改写）。"""
    with closing(_connect()) as conn:
        with conn:
            row = conn.execute("SELECT * FROM notifications WHERE id = ?", (item_id,)).fetchone()
            if row is None:
                return None
            data = json.loads(row["result_json"])
            for key, value in patch.items():
                if value is not None:
                    data[key] = value
            conn.execute(
                "UPDATE notifications SET result_json = ?, title = ?, category = ?, is_urgent = ? WHERE id = ?",
                (
                    json.dumps(data, ensure_ascii=False),
                    str(data.get("title") or row["title"]),
                    str(data.get("category") or row["category"]),
                    1 if data.get("is_urgent") else 0,
                    item_id,
                ),
            )
    return {"id": item_id, "created_at": row["created_at"], "original": row["raw_text"], "data": data}


def save_manual_entry(amount: float, direction: str, note: str = "") -> dict[str, Any]:
    """手动记账：用户在聚合卡里补一笔手机账单里没有的收支。"""
    kind = "支出" if direction == "expense" else "收入"
    result: dict[str, Any] = {
        "app_name": "手动记账",
        "category": "其他类",
        "title": (note or "").strip() or f"手动{kind}",
        "summary": f"手动记录{kind} ¥{amount:.2f}" + (f"（{note.strip()}）" if note and note.strip() else ""),
        "is_urgent": False,
        "event_key": "手动记账",
        "amount": float(amount),
        "direction": direction,
        "manual": True,
    }
    return save_notification(f"[手动记账] {kind} {amount:.2f} 元 {note or ''}".strip(), result)


def reclassify_existing(app_keyword: str, text_keyword: str, target_cat: str) -> int:
    """新建规则后，把历史里已经存在的匹配消息重新归类，并打上「分类已变更」标记。"""
    is_urgent = 1 if target_cat == "重要/紧急待办" else 0
    changed = 0
    with closing(_connect()) as conn:
        with conn:
            rows = conn.execute(
                "SELECT id, raw_text, app_name, result_json FROM notifications"
            ).fetchall()
            for row in rows:
                app_name = row["app_name"] or ""
                raw_text = row["raw_text"] or ""
                if app_keyword and app_keyword not in app_name:
                    continue
                if text_keyword not in raw_text:
                    continue
                data = json.loads(row["result_json"])
                if data.get("category") == target_cat and data.get("custom_rule"):
                    continue
                data["category"] = target_cat
                data["is_urgent"] = bool(is_urgent)
                data["custom_rule"] = True
                data["reclassified"] = True
                if target_cat == "无效广告/促销":
                    data["auto_read"] = True
                conn.execute(
                    "UPDATE notifications SET result_json = ?, category = ?, is_urgent = ? WHERE id = ?",
                    (json.dumps(data, ensure_ascii=False), target_cat, is_urgent, row["id"]),
                )
                changed += 1
    return changed


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