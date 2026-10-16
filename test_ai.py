import os
from openai import OpenAI

def clean_notification_text(raw_notification: str) -> dict:
    """
    接收原始通知文本，调用 DeepSeek 大模型进行去噪与结构化提取
    返回标准的 Python 字典（Dict）
    """
    client = OpenAI(
        api_key="sk-d3effab33794447eabbe6849e9a6af7a", 
        base_url="https://api.deepseek.com"
    )

    system_prompt = """
    你是一个智能信息去噪与聚合系统的核心大脑。请对输入的手机原始通知文本进行语义理解、意图分类与信息提取。
    请严格遵守以下分类与紧急度（is_urgent）判定规则：
    1. 【无效广告/促销】：商城促销、优惠券、理财、课程招生等。
    2. 【物流与消费】：快递派送、订单交易、外卖配送、普通账户充值/消费提醒。
    3. 【重要/紧急待办】：仅限学校教务通知（停水、考试等）、请假审批、账号安全警告、以及【话费余额低于或等于5元、已欠费停机等会导致断网失联的严重临界提醒】。
    
    特别注意判定字段 "is_urgent"（布尔值）：
    - 如果话费余额提示金额 > 5元（如 10元、20元、30元），"is_urgent" 必须为 false（属于普通提醒）。
    - 如果话费余额提示金额 <= 5元 或提示已欠费停机，"is_urgent" 必须为 true，且 category 应归为“重要/紧急待办”，以便触发强提醒和置顶！

    必须严格输出以下标准的 JSON 格式，不要包含任何多余的解释性文字或 Markdown 标记外的内容：
    {
      "app_name": "应用名称",
      "category": "分类（严格从三者中选择：无效广告/促销、物流与消费、重要/紧急待办）",
      "title": "核心标题",
      "summary": "一句话精简摘要",
      "is_urgent": false
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
        
        # 将大模型返回的 JSON 字符串转成 Python 字典
        import json
        result_str = response.choices[0].message.content
        return json.loads(result_str)

    except Exception as e:
        # 如果出错，返回一个降级的默认字典，防止后端崩溃
        return {
            "app_name": "系统提示",
            "category": "无效广告/促销",
            "title": "解析失败",
            "summary": f"大模型调用出错: {str(e)}",
            "is_urgent": False
        }

def aggregate_notifications(notification_list: list) -> dict:
    """
    接收多条同一事件的原始通知文本列表，让大模型进行去重与融合，生成一条精简的综合摘要卡片
    """
    client = OpenAI(
        api_key="sk-d3effab33794447eabbe6849e9a6af7a", 
        base_url="https://api.deepseek.com"
    )

    prompt = f"""
    以下是用户针对同一件商品或事件收到的多条碎片化通知：
    {notification_list}
    
    请帮用户进行“去重并融合”，生成一条精简的综合摘要卡片。必须严格输出以下 JSON 格式：
    {{
      "event_title": "事件主标题（例如：您的羽绒服已到达菜鸟驿站）",
      "merged_summary": "融合后的综合摘要，包含核心提取信息（如取件码、快递单号等）",
      "source_apps": ["淘宝网", "菜鸟驿站"]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个信息去噪与聚合专家。"},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" },
            stream=False
        )
        import json
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"event_title": "聚合失败", "merged_summary": str(e), "source_apps": []}