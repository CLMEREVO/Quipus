from __future__ import annotations

import importlib
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from seed import seed_if_empty, force_seed_samples
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
    raise ImportError("找不到清洗函数。")

clean_notification_text, aggregate_notifications = _load_captain_functions()

app = FastAPI(
    title="Quipus Backend",
    description="智能信息去噪与聚合系统后端 API",
    version="0.7.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

seed_if_empty()

class NotificationRequest(BaseModel):
    text: str = Field(..., min_length=1)

class AggregateRequest(BaseModel):
    notifications: list[str] = Field(..., min_length=1)

class RuleRequest(BaseModel):
    app_keyword: str = ""
    text_keyword: str = Field(..., min_length=1)
    target_cat: str = Field(..., min_length=1)

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
        
        # 容错保护：确保返回的字典里一定有前端需要的字段
        if not isinstance(merged, dict):
            merged = {}
            
        event_title = merged.get("event_title") or merged.get("title") or "多源碎片通知智能聚合"
        merged_summary = merged.get("merged_summary") or merged.get("summary") or "已为您成功提取并融合当前通知消息。"
        source_apps = merged.get("source_apps") or []
        
        normalized_result = {
            "event_title": event_title,
            "merged_summary": merged_summary,
            "source_apps": source_apps
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"聚合失败: {exc}") from exc

    return {
        "status": "success",
        "source_count": len(data.notifications),
        "raw_texts": data.notifications,
        "aggregated_result": normalized_result,
    }

@app.get("/api/history")
def get_history(
    tab: str = Query("overview"),
    limit: int = Query(200, ge=1, le=1000),
    q: str | None = Query(None),
):
    if tab not in TAB_TO_CATEGORY:
        raise HTTPException(status_code=400, detail=f"tab 非法")
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

@app.post("/api/seed/refresh")
def refresh_seed():
    added = force_seed_samples()
    return {"status": "success", "added_count": added, "message": f"成功补充了 {added} 条测试示例"}

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