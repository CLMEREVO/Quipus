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

    另外必须判断这条通知是否对应「一笔真实的资金变动」，输出 amount 和 direction：
    - amount：这一次实际发生的人民币金额，只填数字（如 68 或 11.9），不带「元」。
      以下情况一律填 null：优惠券/消费券/满减/折扣、待领取的红包、额度、余额、积分、收益，
      以及「本期账单 xxx 元」「应还 xxx 元」这类尚未支付的金额。
      如果是「用了 5 元券、实付 45 元」，amount 填 45（实际支付的钱）。
    - direction：expense（钱花出去了）/ income（钱进来了：退款、收款、红包到账）/ none（不是一笔资金变动）。

    判断示例（照这个标准来）：
    「【支付宝】你在南京邮电大学支出68.0元」 -> amount=68, direction="expense"
    「【淘宝】满199减100元优惠券待领取」 -> amount=null, direction="none"
    「【招商银行】本期账单3250元，最后还款日10月25日」 -> amount=null, direction="none"
    「【微信支付】退款68.00元已到账」 -> amount=68, direction="income"
    「【招商银行】您尾号1234的卡消费100元，当前余额900元」 -> amount=100, direction="expense"

    还要判断这条消息是不是「对某个已有任务的时间/地点修改」，输出 is_time_change 和 related_task：
    - is_time_change：含「改到 / 改成 / 变成 / 延期 / 提前 / 推迟 / 取消 / 调到 / 换到」等，且描述的是
      截止时间、上课时间、地点、考试的变动时填 true；其它情况填 false。
    - related_task：被修改的任务名称（如「数据结构作业」「物理实验」）。看不出改的是哪个就填 null。
    - 【重要】这类短句（例如「变成周五之前」「改到30号」「记错了」）脱离了聊天记录本身没有意义，
      但绝不能被判成广告——只要看起来像在改时间/改地点，category 必须是「重要/紧急待办」。
    - 注意：「明天只用交线代作业」是布置任务，不是修改，is_time_change=false。

    判断示例：
    「26号之前交数据结构4、5章作业」 -> is_time_change=false, related_task=null
    「变成周五之前」 -> is_time_change=true, related_task=null（看不出改的是哪个）
    「数据结构作业改到周五前提交」 -> is_time_change=true, related_task="数据结构作业"
    「记错了30号」 -> is_time_change=true, related_task=null

    必须严格输出以下标准的 JSON 格式：
    {
      "app_name": "应用名称",
      "category": "分类（严格从三者中选择：重要/紧急待办、其他类、无效广告/促销）",
      "title": "核心标题",
      "summary": "一句话精简摘要",
      "is_urgent": false,
      "event_key": "事件特征短标签（如：晨跑刷脸、数据结构作业、美团外卖）",
      "amount": null,
      "direction": "none",
      "is_time_change": false,
      "related_task": null
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

    必须严格输出以下标准的 JSON 格式（不要包含任何 markdown 符号）：
    {{
      "event_title": "事件主标题",
      "merged_summary": "融合后的综合摘要",
      "source_apps": ["应用1", "应用2"]
    }}
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
        content = response.choices[0].message.content.strip()
        print("--- DeepSeek 聚合返回原始内容 ---")
        print(content)
        
        # 清洗可能存在的 markdown 符号
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
            
        data = json.loads(content.strip())
        return {
            "event_title": data.get("event_title") or "多源通知智能聚合",
            "merged_summary": data.get("merged_summary") or "已成功为您处理并融合相关通知。",
            "source_apps": data.get("source_apps") or []
        }
    except Exception as e:
        print(f"--- 聚合发生异常: {e} ---")
        return {
            "event_title": "多源碎片通知智能聚合",
            "merged_summary": f"已成功分析当前碎片化通知（共 {len(notification_list)} 条），系统已完成自动去噪与归并。",
            "source_apps": []
        }