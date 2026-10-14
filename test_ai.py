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
    必须严格输出以下标准的 JSON 格式，不要包含任何多余的解释性文字或 Markdown 标记外的内容：
    {
      "app_name": "应用名称",
      "category": "分类（可选：无效广告/促销、物流与消费、重要/紧急待办）",
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