r"""Quipus 后端 —— 通知解析 + 历史存储 + 按分类筛选

接口一览：
    GET    /                      健康检查
    POST   /api/clean             解析一条通知，并自动存进历史
    GET    /api/history           按左侧标签拉历史（tab=overview/blocked/express/urgent）
    GET    /api/stats             顶部计数：总数 / 已拦截广告 / 物流 / 待办 / 紧急
    DELETE /api/history           清空历史

启动：
    .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
    或者直接  python main.py

交互式文档：http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import importlib
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("quipus")


# ---------------------------------------------------------------------------
# 导入队长写的清洗函数
#   队长可能会把文件改名（test_ai / test_ai_2 ...），这里自动找一个能用的，
#   省得他每次改名你都要跟着改代码。
# ---------------------------------------------------------------------------
def _load_cleaner():
    for mod_name in ("test_ai", "test_ai_2", "cleaner"):
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for fn_name in ("clean_notification_text", "process_notification", "clean_text"):
            if hasattr(mod, fn_name):
                logger.info("使用 %s.%s() 作为清洗函数", mod_name, fn_name)
                return getattr(mod, fn_name)
    raise ImportError(
        "找不到清洗函数。请确认 test_ai.py（或 test_ai_2.py / cleaner.py）在本目录下，"
        "且里面有 clean_notification_text 函数。"
    )


clean_notification_text = _load_cleaner()


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


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------
@app.get("/")
def read_root():
    return {"message": "Quipus Backend is running successfully!"}


@app.post("/api/clean", summary="解析通知并存入历史")
def clean_notification(data: NotificationRequest) -> dict[str, Any]:
    raw_text = data.text
    logger.info("收到通知，长度=%d", len(raw_text))

    # 调用大模型函数进行清洗
    try:
        processed_data = clean_notification_text(raw_text)
    except Exception as exc:
        logger.exception("调用大模型失败")
        raise HTTPException(
            status_code=502,
            detail=f"大模型解析失败: {type(exc).__name__}: {exc}",
        ) from exc

    if not isinstance(processed_data, dict):
        raise HTTPException(
            status_code=502, detail=f"大模型返回的不是 JSON 对象: {processed_data!r}"
        )

    # 存进历史库，方便前端后面按分类拉
    record = save_notification(raw_text, processed_data)

    return {
        "status": "success",
        "raw_text": raw_text,
        "processed_result": processed_data,
        "id": record["id"],            # 新增：这条记录的编号
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
