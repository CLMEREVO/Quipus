r"""Quipus 后端 —— 通知解析 + 历史存储 + 按分类筛选

注意分工：
    test_ai.py   队长的文件，提供 clean_notification_text / aggregate_notifications，
                 我这边【不改动它】，只负责调用。
    main.py      我负责，对外提供 HTTP 接口。
    storage.py   我负责，SQLite 存储层。

接口一览：
    GET    /                      健康检查
    POST   /api/clean             解析一条通知，并自动存进历史
    POST   /api/aggregate         把多条碎片通知聚合成一条摘要（调用队长的聚合函数）
    GET    /api/history           按左侧标签拉历史（tab=overview/blocked/express/urgent）
    GET    /api/stats             顶部计数：总数 / 已拦截广告 / 物流 / 待办 / 紧急
    DELETE /api/history           清空历史

启动：
    .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
    或者直接  python main.py

交互式文档：http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from storage import (
    TAB_TO_CATEGORY,
    clear,
    init_db,
    list_notifications,
    save_notification,
    stats,
)

# 队长的解析与聚合函数（test_ai.py 由队长维护，这里只 import，不改它）
from test_ai import aggregate_notifications, clean_notification_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("quipus")


# ---------------------------------------------------------------------------
# 应用
# ---------------------------------------------------------------------------
app = FastAPI(title="Quipus Backend", description="智能信息去噪与聚合系统后端")

# 🚨 核心：必须加上这段 CORS 中间件配置，允许前端跨域调用！
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 允许所有前端来源
    allow_credentials=True,
    allow_methods=["*"],      # 允许所有 HTTP 方法 (GET, POST, OPTIONS 等)
    allow_headers=["*"],      # 允许所有请求头
)

# 建表（已存在就跳过）
init_db()


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------
class NotificationRequest(BaseModel):
    text: str = Field(..., min_length=1, description="前端发来的通知原文")


class AggregateRequest(BaseModel):
    notifications: list[str] = Field(
        ...,
        min_length=1,
        description="同一事件的多条碎片通知原文，例如 [淘宝发货, 菜鸟到站]",
    )


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------
@app.get("/")
def read_root():
    return {"message": "Quipus Backend is running successfully!"}


@app.post("/api/clean", summary="解析一条通知，并存入历史")
def clean_one(data: NotificationRequest) -> dict[str, Any]:
    raw_text = data.text
    logger.info("收到通知，长度=%d", len(raw_text))

    # 队长的函数内部已经 try/except 过，出错会返回降级字典而不是抛异常；
    # 这里再兜一层，防止意料之外的错误把 500 抛给前端。
    try:
        processed_result = clean_notification_text(raw_text)
    except Exception as exc:
        logger.exception("调用 clean_notification_text 失败")
        raise HTTPException(
            status_code=502,
            detail=f"大模型解析失败: {type(exc).__name__}: {exc}",
        ) from exc

    if not isinstance(processed_result, dict):
        raise HTTPException(
            status_code=502, detail=f"清洗函数返回的不是字典: {processed_result!r}"
        )

    # 存进历史库，方便前端按分类拉取
    record = save_notification(raw_text, processed_result)

    return {
        "status": "success",
        "raw_text": raw_text,
        "processed_result": processed_result,
        "id": record["id"],            # 新增：这条记录的编号
    }


@app.post("/api/aggregate", summary="多条碎片通知聚合成一条摘要")
def aggregate(data: AggregateRequest) -> dict[str, Any]:
    logger.info("收到聚合请求，共 %d 条", len(data.notifications))

    try:
        merged = aggregate_notifications(data.notifications)
    except Exception as exc:
        logger.exception("调用 aggregate_notifications 失败")
        raise HTTPException(
            status_code=502,
            detail=f"聚合失败: {type(exc).__name__}: {exc}",
        ) from exc

    if not isinstance(merged, dict):
        raise HTTPException(status_code=502, detail=f"聚合函数返回的不是字典: {merged!r}")

    return {
        "status": "success",
        "source_count": len(data.notifications),
        "raw_texts": data.notifications,
        "aggregated_result": merged,   # { event_title, merged_summary, source_apps }
    }


@app.get("/api/history", summary="按左侧标签拉历史通知")
def get_history(
    tab: str = Query(
        "overview",
        description="overview 全部 / blocked 已拦截广告 / express 物流与消费 / urgent 重要待办",
    ),
    limit: int = Query(200, ge=1, le=1000, description="最多返回多少条"),
    q: str | None = Query(None, description="可选：按关键词搜索原文/标题/应用名"),
) -> dict[str, Any]:
    if tab not in TAB_TO_CATEGORY:
        raise HTTPException(
            status_code=400,
            detail=f"tab 只能是 {sorted(TAB_TO_CATEGORY)}，收到的是 {tab!r}",
        )

    items = list_notifications(tab=tab, limit=limit, keyword=q)
    logger.info("拉取历史：tab=%s 命中 %d 条", tab, len(items))
    return {
        "status": "success",
        "tab": tab,
        "category": TAB_TO_CATEGORY[tab],
        "count": len(items),
        "items": items,          # 每项形如 { id, created_at, original, data }
    }


@app.get("/api/stats", summary="顶部计数")
def get_stats() -> dict[str, Any]:
    return {"status": "success", **stats()}


@app.delete("/api/history", summary="清空历史")
def delete_history() -> dict[str, Any]:
    deleted = clear()
    logger.info("清空历史，删除 %d 条", deleted)
    return {"status": "success", "deleted": deleted}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
