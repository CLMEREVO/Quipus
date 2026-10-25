import os
import json
from openai import OpenAI

def clean_notification_text(raw_notification: str) -> dict:
    """
    接收原始通知文本，调用 DeepSeek 大模型进行去噪与结构化提取
    返回标准的 Python 字典（Dict）
    """
    client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"), 
    base_url="https://api.deepseek.com"
)

    system_prompt = """
    你是一个智能信息去噪与聚合系统的核心大脑。请对输入的手机原始通知文本进行语义理解、意图分类与信息提取。
    请严格遵守以下分类与判定规则：
    1. 【重要/紧急待办】：仅限学校教务通知（停水、考试等）、班级群作业提交/变更通知、临时补课/调课、账号安全警告、话费<=5元或欠费。
    2. 【其他类】：晨跑刷脸/打卡成功通知、快递派送/到达、外卖配送、订单交易/充值、微信/银行卡支付提醒。
    3. 【无效广告/促销】：商城促销、优惠券、理财、课程招生、营销推广等。
    
    必须严格输出以下标准的 JSON 格式：
    {
      "app_name": "应用名称",
      "category": "分类（严格从三者中选择：重要/紧急待办、其他类、无效广告/促销）",
      "title": "核心标题",
      "summary": "一句话精简摘要",
      "is_urgent": false,
      "event_key": "事件特征短标签（如：晨跑刷脸、数据结构作业、美团外卖）"
    }
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_notification}
            ],
            response_format={ "type": "json_object" },
            stream=False
        )
        result_str = response.choices[0].message.content
        return json.loads(result_str)

    except Exception as e:
        return {
            "app_name": "系统提示",
            "category": "其他类",
            "title": "解析失败",
            "summary": f"大模型调用出错: {str(e)}",
            "is_urgent": False,
            "event_key": "error"
        }

def aggregate_notifications(notification_list: list) -> dict:
    """
    接收多条同一事件的原始通知文本列表，进行去重、融合与流式聚合
    """
    client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"), 
    base_url="https://api.deepseek.com"
)

    prompt = f"""
    以下是用户针对同一类事件（如快递、外卖、刷脸或支付）收到的多条碎片化通知：
    {notification_list}
    
    请帮用户进行多源聚合，生成一条精简的综合摘要卡片。必须严格输出以下 JSON 格式：
    {{
      "event_title": "事件主标题（例如：今日晨跑刷脸已完成 / 您的多个快递已到达驿站）",
      "merged_summary": "融合后的综合摘要，包含最新状态、接收次数或累计信息",
      "source_apps": ["应用1", "应用2"]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个多源信息聚和专家。"},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" },
            stream=False
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"event_title": "聚合失败", "merged_summary": str(e), "source_apps": []}