import os
import json
from openai import OpenAI

def clean_notification_text(raw_notification: str) -> dict:
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
        return json.loads(response.choices[0].message.content)
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
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"), 
        base_url="https://api.deepseek.com"
    )

    prompt = f"""
    以下是用户收到的多条碎片化通知：
    {notification_list}
    
    请判断这些通知的属性并进行聚合：
    1. 如果这些通知大部分属于营销、优惠券、促销或广告等【无效广告/促销】类，请进行“粗聚合”，不要罗列具体商品，主标题(event_title)必须固定为 "已拦截的消息"，摘要(merged_summary)必须笼统概括为诸如 "来自淘宝、京东、拼多多等平台的促销优惠与营销通知，已为您自动折叠拦截" 的形式，绝不能出现“建议领取”等诱导文案。
    2. 如果是正常的快递、外卖、作业或刷脸等通知，则正常生成详细的事件主标题与融合摘要。

    必须严格输出以下 JSON 格式：
    {
      "event_title": "事件主标题",
      "merged_summary": "融合后的综合摘要",
      "source_apps": ["应用1", "应用2"]
    }
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个多源信息聚合与安全过滤专家。"},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" },
            stream=False
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"event_title": "聚合失败", "merged_summary": str(e), "source_apps": []}