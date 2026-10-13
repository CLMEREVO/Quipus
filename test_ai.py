import os
from openai import OpenAI  # DeepSeek 兼容 OpenAI 的调用方式

# 初始化客户端，填入你刚刚复制的 API Key
client = OpenAI(
    api_key="sk-d3effab33794447eabbe6849e9a6af7a", 
    base_url="https://api.deepseek.com"
)

# 模拟一条杂乱的手机通知文本
raw_notification = "【淘宝网】亲爱的会员，您购买的羽绒服已发货，顺丰速运... 另外祝您双十一购物狂欢，全场五折起！"

# 设计给大模型的 Prompt（这是你作为 AI 算法与 Prompt 工程师的核心工作！）
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
        model="deepseek-chat",  # 使用 DeepSeek 对话模型
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_notification}
        ],
        response_format={ "type": "json_object" }, # 强制输出 JSON 格式
        stream=False
    )
    
    print("大模型返回结果：")
    print(response.choices[0].message.content)

except Exception as e:
    print(f"调用出错啦：{e}")