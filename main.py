from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 队长的解析模块。如果他的文件不叫 cleaner.py，只需要改这一行的模块名。
from cleaner import process_notification

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("quipus")


# ---------------------------------------------------------------------------
# 应用
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Quipus Backend",
    description="通知解析服务（骨架版）",
    version="0.2.0",
)

# 允许前端页面（浏览器）跨域直接调用。联调阶段先全放开，上线前改成前端实际域名。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------
class CleanRequest(BaseModel):
    text: str = Field(..., min_length=1, description="前端发来的通知原文")


class CleanResponse(BaseModel):
    ok: bool = True
    original: str = Field(..., description="原文，原样回传，方便前端对照")
    data: dict[str, Any] = Field(..., description="大模型解析出的结构化数据")


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------
@app.get("/", summary="健康检查")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "quipus-backend"}


@app.post("/api/clean", response_model=CleanResponse, summary="解析通知文本")
async def clean(payload: CleanRequest) -> CleanResponse:
    text = payload.text
    logger.info("收到通知文本，长度=%d", len(text))

    try:
        # process_notification 是同步函数（内部是阻塞的网络请求），
        # 丢进线程池跑，避免卡住事件循环。
        data = await run_in_threadpool(process_notification, text)
    except Exception as exc:
        logger.exception("调用大模型解析失败")
        raise HTTPException(
            status_code=502,
            detail=f"大模型解析失败: {type(exc).__name__}: {exc}",
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail=f"大模型返回的不是 JSON 对象: {data!r}")

    return CleanResponse(original=text, data=data)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
 