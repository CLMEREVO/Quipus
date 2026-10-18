r"""Quipus 后端 —— 通知解析 + 历史存储 + 多 Tab 筛选 + 多源聚合

分工：
    test_ai.py   （队长的文件）提供 clean_notification_text / aggregate_notifications，
                 我这边【只 import 不改动】。
    main.py      （我负责）对外提供 HTTP 接口。
    storage.py   （我负责）SQLite 存储层。
    seed.py      （我负责）预置测试数据，保证云端部署后打开就有内容。

启动：
    .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
    或者直接  python main.py

接口文档：http://127.0.0.1:8000/docs
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


# ---------------------------------------------------------------------------
# 导入队长的函数
#   队长的文件可能叫 test_ai.py 也可能叫 test_ai_3.py，函数名也可能微调，
#   这里按顺序找一遍，找到就用——他改名不用我们跟着改。
# ---------------------------------------------------------------------------
def _load_captain_functions():
    tried = []
    for mod_name in ("test_ai_3", "test_ai", "cleaner"):
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            tried.append(mod_name)
            continue

        clean_fn = None
        for fn_name in ("clean_notification_text", "clean_text", "process_notification"):
            if hasattr(mod, fn_name):
                clean_fn = getattr(mod, fn_name)
                break
        if clean_fn is None:
            tried.append(f"{mod_name}(无清洗函数)")
            continue

        agg_fn = getattr(mod, "aggregate_notifications", None)
        logger.info(
            "队长的函数来自 %s：clean=%s，aggregate=%s",
            mod_name,
            clean_fn.__name__,
            "有" if agg_fn else "无",
        )
        return clean_fn, agg_fn

    raise ImportError(
        "找不到队长的清洗函数。请确认 test_ai.py（或 test_ai_3.py）在本目录下，"
        f"且里面有 clean_notification_text。已尝试：{tried}"
    )


clean_notification_text, aggregate_notifications = _load_captain_functions()


# ---------------------------------------------------------------------------
# 文档元信息（这段会显示在 /docs 页面最上方）
# ---------------------------------------------------------------------------
TAGS_METADATA = [
    {"name": "解析", "description": "把一条原始手机通知交给大模型解析成结构化数据，并自动存入历史库。"},
    {"name": "历史", "description": "查询、按分类筛选、清空已解析的通知。对应前端左侧边栏的三个标签。"},
    {"name": "聚合", "description": "把同一事件的多条碎片化通知（如淘宝发货 + 菜鸟到站）融合成一条摘要卡片。"},
    {"name": "运维", "description": "健康检查等。"},
]

DESCRIPTION = """
## 智能信息去噪与聚合系统 · 后端 API

把手机收到的杂乱通知（促销短信、快递通知、教务通知……）交给大模型，
自动分类、提取要点，并按分类筛选展示。

### 三个分类

| category | 前端表现 |
|---|---|
| `重要/紧急待办` | 标红、置顶 |
| `物流与消费` | 普通卡片罗列 |
| `无效广告/促销` | 折叠 / 归入拦截统计 |

### 建议的调用顺序

1. `POST /api/clean` — 解析一条通知（自动入库）
2. `GET /api/history?tab=blocked` — 按左侧标签拉历史
3. `GET /api/stats` — 顶部计数
4. `POST /api/aggregate` — 多条碎片通知一键融合

### 调试小贴士

每个接口下面点 **Try it out** 可以直接在这里发请求，不用写前端代码。
"""


# ---------------------------------------------------------------------------
# 应用
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Quipus Backend",
    description=DESCRIPTION,
    version="0.4.0",
    openapi_tags=TAGS_METADATA,
    contact={"name": "Quipus 团队", "url": "https://github.com/CLMEREVO/Quipus"},
)

# 🚨 核心：必须加上这段 CORS 中间件配置，允许前端跨域调用！
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 允许所有前端来源
    allow_credentials=True,
    allow_methods=["*"],      # 允许所有 HTTP 方法 (GET, POST, OPTIONS 等)
    allow_headers=["*"],      # 允许所有请求头
)

# 建表 + 预置测试数据（已有数据就跳过，不会重复灌）
seed_if_empty()


# ---------------------------------------------------------------------------
# 数据模型（同时也是 /docs 里展示的响应结构）
# ---------------------------------------------------------------------------
class ProcessedResult(BaseModel):
    """大模型解析出来的结构化结果。"""

    model_config = ConfigDict(extra="allow")

    app_name: str = Field("", description="发送方应用名，例如 淘宝网 / 菜鸟驿站 / 教务处")
    category: str = Field("", description="只能是：重要/紧急待办、物流与消费、无效广告/促销")
    title: str = Field("", description="通知的一句话标题")
    summary: str = Field("", description="50 字以内的要点摘要")
    is_urgent: bool = Field(False, description="是否需要尽快处理（前端据此标红置顶）")


class NotificationRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="前端发来的通知原文",
        examples=["【教务处】重要通知：本周五 14:00-18:00 全校停水检修，请提前储水。"],
    )


class CleanResponse(BaseModel):
    status: str = Field("success", description="固定为 success")
    raw_text: str = Field(..., description="原文回显，方便前端对照")
    processed_result: ProcessedResult = Field(..., description="结构化解析结果")
    id: int = Field(..., description="这条记录在历史库里的编号")


class AggregateRequest(BaseModel):
    notifications: list[str] = Field(
        ...,
        min_length=1,
        description="同一事件的多条碎片通知原文",
        examples=[
            [
                "【淘宝网】您购买的羽绒服已由顺丰速运发货，运单号 SF12345678。",
                "【菜鸟驿站】您的顺丰包裹已到达学校南门驿站，取件码 5-2-3008。",
            ]
        ],
    )


class AggregateResult(BaseModel):
    """聚合函数返回的摘要卡片。"""

    model_config = ConfigDict(extra="allow")

    event_title: str = Field("", description="事件主标题")
    merged_summary: str = Field("", description="融合后的综合摘要，含取件码/运单号等关键信息")
    source_apps: list[str] = Field(default_factory=list, description="涉及的来源应用")


class AggregateResponse(BaseModel):
    status: str = Field("success", description="固定为 success")
    source_count: int = Field(..., description="参与聚合的原始通知条数")
    raw_texts: list[str] = Field(..., description="参与聚合的原文列表")
    aggregated_result: AggregateResult = Field(..., description="融合后的摘要卡片")


class HistoryItem(BaseModel):
    id: int = Field(..., description="记录编号")
    created_at: str = Field(..., description="解析时间，格式 YYYY-MM-DD HH:MM:SS")
    original: str = Field(..., description="通知原文")
    data: ProcessedResult = Field(..., description="解析结果")


class HistoryResponse(BaseModel):
    status: str = Field("success", description="固定为 success")
    tab: str = Field(..., description="本次查询的分类标签")
    category: str | None = Field(None, description="该标签对应的数据库分类，overview 为 null")
    count: int = Field(..., description="本次返回几条")
    items: list[HistoryItem] = Field(..., description="按时间倒序，最新的在前")


class StatsResponse(BaseModel):
    status: str = Field("success", description="固定为 success")
    total: int = Field(..., description="历史通知总数")
    urgent: int = Field(..., description="紧急（is_urgent=true）条数")
    blocked: int = Field(..., description="已拦截广告条数")
    express: int = Field(..., description="物流与消费条数")
    todo: int = Field(..., description="重要/紧急待办条数")
    by_category: dict[str, int] = Field(..., description="按分类的明细计数")


class DeletedResponse(BaseModel):
    status: str = Field("success", description="固定为 success")
    deleted: int = Field(..., description="删掉的条数")


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------
@app.get("/", tags=["运维"], summary="健康检查", description="确认服务在跑，返回一句问候。")
def read_root() -> dict[str, str]:
    return {"message": "Quipus Backend is running successfully!"}


@app.post(
    "/api/clean",
    tags=["解析"],
    summary="解析一条通知并存入历史",
    description="调用队长的 `clean_notification_text` 解析原文，把结果写入 SQLite，并返回给前端。",
    response_model=CleanResponse,
    responses={502: {"description": "大模型调用失败"}},
)
def clean_one(data: NotificationRequest) -> CleanResponse:
    raw_text = data.text
    logger.info("收到通知，长度=%d", len(raw_text))

    # 队长的函数内部已 try/except 过，出错会返回降级字典而不是抛异常；
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

    record = save_notification(raw_text, processed_result)
    return CleanResponse(
        raw_text=raw_text,
        processed_result=ProcessedResult(**processed_result),
        id=record["id"],
    )


@app.post(
    "/api/aggregate",
    tags=["聚合"],
    summary="多条碎片通知聚合成一条摘要",
    description=(
        "调用队长的 `aggregate_notifications`，把同一事件的多条通知"
        "（例如「淘宝发货」+「菜鸟到站」）去重融合成一张摘要卡片。"
    ),
    response_model=AggregateResponse,
    responses={502: {"description": "聚合失败"}, 503: {"description": "队长的聚合函数不可用"}},
)
def aggregate(data: AggregateRequest) -> AggregateResponse:
    if aggregate_notifications is None:
        raise HTTPException(
            status_code=503,
            detail="队长的模块里没有 aggregate_notifications 函数，聚合能力暂不可用",
        )

    logger.info("收到聚合请求，共 %d 条", len(data.notifications))
    try:
        merged = aggregate_notifications(data.notifications)
    except Exception as exc:
        logger.exception("调用 aggregate_notifications 失败")
        raise HTTPException(
            status_code=502, detail=f"聚合失败: {type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(merged, dict):
        raise HTTPException(status_code=502, detail=f"聚合函数返回的不是字典: {merged!r}")

    return AggregateResponse(
        source_count=len(data.notifications),
        raw_texts=data.notifications,
        aggregated_result=AggregateResult(**merged),
    )


@app.get(
    "/api/history",
    tags=["历史"],
    summary="按左侧标签拉历史通知",
    description=(
        "前端左侧边栏三个标签对应的取值范围：\n\n"
        "- `overview` 总览（全部）\n"
        "- `blocked` 已拦截广告 → category = 无效广告/促销\n"
        "- `express` 聚合快递与消费 → category = 物流与消费\n"
        "- `urgent` 重要/紧急待办 → category = 重要/紧急待办\n\n"
        "返回的每一项 `{ id, created_at, original, data }` 就是前端卡片要渲染的数据，"
        "可以直接塞进 `historyList`。"
    ),
    response_model=HistoryResponse,
    responses={400: {"description": "tab 取值非法"}},
)
def get_history(
    tab: str = Query(
        "overview",
        description="overview 全部 / blocked 已拦截广告 / express 物流与消费 / urgent 重要待办",
        examples=["blocked"],
    ),
    limit: int = Query(200, ge=1, le=1000, description="最多返回多少条"),
    q: str | None = Query(None, description="可选：按关键词搜索原文 / 标题 / 应用名"),
) -> HistoryResponse:
    if tab not in TAB_TO_CATEGORY:
        raise HTTPException(
            status_code=400,
            detail=f"tab 只能是 {sorted(TAB_TO_CATEGORY)}，收到的是 {tab!r}",
        )

    items = list_notifications(tab=tab, limit=limit, keyword=q)
    logger.info("拉取历史：tab=%s 命中 %d 条", tab, len(items))
    return HistoryResponse(
        tab=tab,
        category=TAB_TO_CATEGORY[tab],
        count=len(items),
        items=[HistoryItem(**it) for it in items],
    )


@app.get(
    "/api/stats",
    tags=["历史"],
    summary="顶部计数",
    description="返回总数、紧急数、已拦截广告数、物流数、待办数，给前端顶部的数字卡片用。",
    response_model=StatsResponse,
)
def get_stats() -> StatsResponse:
    return StatsResponse(**stats())


@app.delete(
    "/api/history",
    tags=["历史"],
    summary="清空历史",
    description=(
        "把历史库清空（用于演示前重置、或调试）。"
        "**预置数据不会自动回来**，重启服务才会重新灌。"
    ),
    response_model=DeletedResponse,
)
def delete_history() -> DeletedResponse:
    deleted = clear()
    logger.info("清空历史，删除 %d 条", deleted)
    return DeletedResponse(deleted=deleted)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
