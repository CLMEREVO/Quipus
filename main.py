r"""Quipus 后端 —— 通知解析 + 历史存储 + 多 Tab 筛选 + 多源聚合 + 自定义规则

分工：
    test_ai.py   （队长维护）提供 clean_notification_text / aggregate_notifications
    main.py      （Xfurry 负责）对外提供 HTTP 接口
    storage.py   （Xfurry 负责）SQLite 存储层
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from seed import seed_if_empty
from storage import (
    TAB_TO_CATEGORY,
    clear,
    list_notifications,
    save_notification,
    stats,
    get_custom_rules,
    add_custom_rule,
    delete_custom_rule,
    reset_custom_rules,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("quipus")

def _load_captain_functions():
    for mod_name in ("test_ai", "test_ai_3", "cleaner"):
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        clean_fn = getattr(mod, "clean_notification_text", None)
        agg_fn = getattr(mod, "aggregate_notifications", None)
        if clean_fn:
            return clean_fn, agg_fn
    raise ImportError("找不到队长的清洗函数。请确认 test_ai.py 在本目录下。")

clean_notification_text, aggregate_notifications = _load_captain_functions()

app = FastAPI(
    title="Quipus Backend",
    description="智能信息去噪与聚合系统后端 API",
    version="0.6.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

seed_if_empty()

# --- 请求体数据模型 ---
class NotificationRequest(BaseModel):
    text: str = Field(..., min_length=1)

class AggregateRequest(BaseModel):
    notifications: list[str] = Field(..., min_length=1)

class RuleRequest(BaseModel):
    app_keyword: str = ""
    text_keyword: str = Field(..., min_length=1)
    target_cat: str = Field(..., min_length=1)

# --- API 路由 ---
@app.get("/")
def read_root():
    return {"message": "Quipus Backend is running successfully!"}

@app.post("/api/clean")
def clean_one(data: NotificationRequest):
    try:
        processed_result = clean_notification_text(data.text)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"大模型解析失败: {exc}") from exc

    record = save_notification(data.text, processed_result)
    return {
        "status": "success",
        "raw_text": data.text,
        "processed_result": processed_result,
        "id": record["id"],
    }

@app.post("/api/aggregate")
def aggregate(data: AggregateRequest):
    if aggregate_notifications is None:
        raise HTTPException(status_code=503, detail="聚合函数不可用")
    try:
        merged = aggregate_notifications(data.notifications)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"聚合失败: {exc}") from exc

    return {
        "status": "success",
        "source_count": len(data.notifications),
        "raw_texts": data.notifications,
        "aggregated_result": merged,
    }

@app.get("/api/history")
def get_history(
    tab: str = Query("overview"),
    limit: int = Query(200, ge=1, le=1000),
    q: str | None = Query(None),
):
    if tab not in TAB_TO_CATEGORY:
        raise HTTPException(status_code=400, detail="tab 非法")
    items = list_notifications(tab=tab, limit=limit, keyword=q)
    return {
        "status": "success",
        "tab": tab,
        "category": TAB_TO_CATEGORY[tab],
        "count": len(items),
        "items": items,
    }

@app.get("/api/stats")
def get_stats():
    return {"status": "success", **stats()}

@app.delete("/api/history")
def delete_history():
    deleted = clear()
    return {"status": "success", "deleted": deleted}

# --- 自定义规则管理路由 ---
@app.get("/api/rules")
def list_rules():
    return {"status": "success", "rules": get_custom_rules()}

@app.post("/api/rules")
def create_rule(data: RuleRequest):
    rule_id = add_custom_rule(data.app_keyword, data.text_keyword, data.target_cat)
    return {"status": "success", "id": rule_id}

@app.delete("/api/rules/{rule_id}")
def remove_rule(rule_id: int):
    delete_custom_rule(rule_id)
    return {"status": "success", "deleted_id": rule_id}

@app.post("/api/rules/reset")
def reset_rules():
    reset_custom_rules()
    return {"status": "success", "message": "已恢复默认规则"}

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)