r"""通知解析模块 —— 队长负责。

main.py 依赖这里的：

    clean_notification_text(raw_text: str) -> dict

返回的字段必须和前端 index.html 对齐（前端会读这几个）：
    app_name   发送方名称，显示在卡片上
    title      标题
    category   只有三种：重要/紧急待办、物流与消费、无效广告/促销
    is_urgent  布尔值，前端用它决定"标红置顶"
    summary    摘要

依赖：pip install openai（DeepSeek 用 OpenAI 兼容接口）

API Key 从环境变量读：
    $env:DEEPSEEK_API_KEY = "sk-xxxxxxxx"
"""

from __future__ import annotations

import logging
import os

from openai import OpenAI

logger = logging.getLogger("quipus.cleaner")

# ---------------------------------------------------------------------------
# 客户端
# ---------------------------------------------------------------------------
# openai 3.x 在 api_key 为空时会直接抛 OpenAIError，导致模块导入失败、服务起不来。
# 所以密钥缺失时塞一个占位值，让服务照常启动，真正调用接口时才返回 502。
_api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
if not _api_key:
    logger.warning("未设置 DEEPSEEK_API_KEY：服务能启动，但调用接口会返回 502")
    _api_key = "placeholder-please-set-DEEPSEEK_API_KEY"

client = OpenAI(
    api_key=_api_key,
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)

# ---------------------------------------------------------------------------
# 提示词
# ---------------------------------------------------------------------------
# 注意 1：用了 response_format={"type": "json_object"}，提示词里必须出现 "json" 字样
# 注意 2：category 的取值必须和前端约定的三种完全一致，否则前端渲染错位
# 注意 3：字段名也必须和前端一致（app_name / is_urgent 不能少）
system_prompt = """你是一个手机通知整理助手。把用户发来的原始通知整理成 json，字段固定为：
{
  "app_name": "发送方名称，去掉【】，例如 淘宝、菜鸟驿站、招商银行、中国移动、教务处",
  "title": "一句话概括这条通知说了什么，去掉情绪化修饰",
  "category": "只能填这三个之一：重要/紧急待办、物流与消费、无效广告/促销",
  "is_urgent": "布尔值 true 或 false，表示是否需要用户尽快处理",
  "summary": "50 字以内的要点摘要",
  "deadline": "截止时间或最后期限，没有就填 null",
  "location": "地点，没有就填 null",
  "contact": "联系人或联系电话，没有就填 null"
}

category 的判断标准：
- 重要/紧急待办：学校教务通知、账单还款、图书到期、停水停电、考试作业等需要用户行动或关注的
- 物流与消费：快递发货、驿站取件、外卖配送、支付扣款等交易和物流类
- 无效广告/促销：营销推广、优惠券、招生广告等用户不需要的垃圾信息

is_urgent 为 true 的情形：有明确截止时间、会停机/欠费/逾期、临近过期、要求尽快处理。
其余情况填 false。

注意：contact 只填具体的联系人或电话；发送方机构名称要填在 app_name 里，不要填进 contact。

只返回 json，不要任何解释文字。"""


# ---------------------------------------------------------------------------
# 解析函数
# ---------------------------------------------------------------------------
def clean_notification_text(raw_text: str):
    """接收一条原始通知文本，返回解析后的字典数据。"""
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_text},
        ],
        response_format={"type": "json_object"},
        stream=False,
    )
    # 直接将 JSON 字符串解析成 Python 字典返回
    import json

    return json.loads(response.choices[0].message.content)


# 旧名字也保留，谁 import 都不会报错
process_notification = clean_notification_text
clean_text = clean_notification_text
