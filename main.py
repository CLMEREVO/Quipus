r"""Quipus 后端 —— 通知解析 + 历史存储 + 多 Tab 筛选 + 多源聚合

分工：
    test_ai_3.py （队长维护）提供 clean_notification_text / aggregate_notifications
    main_4.py    （Xfurry 负责）对外提供 HTTP 接口
    storage.py   （Xfurry 负责）SQLite 存储层
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from seed import seed_if_empty
from storage import (
    TAB_TO_CATEGORY,
    clear,
    list_notifications,
    save_notification,
    stats,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("quipus")

def _load_captain_functions():
    for mod_name in ("test_ai_3", "test_ai", "cleaner"):
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        clean_fn = getattr(mod, "clean_notification_text", None)
        agg_fn = getattr(mod, "aggregate_notifications", None)
        if clean_fn:
            return clean_fn, agg_fn
    raise ImportError("找不到队长的清洗函数。请确认 test_ai_3.py 在本目录下。")

clean_notification_text, aggregate_notifications = _load_captain_functions()

app = FastAPI(
    title="Quipus Backend",
    description="智能信息去噪与聚合系统后端 API",
    version="0.4.0",
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

if __name__ == "__main__":
    import os
    import uvicorn
    
    # 获取 Railway 动态分配的端口（本地没设置时默认 8000）
    port = int(os.environ.get("PORT", 8000))
    
    # 必须绑定 0.0.0.0 才能接收公网流量
    uvicorn.run("main:app", host="0.0.0.0", port=port)