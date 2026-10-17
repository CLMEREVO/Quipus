r"""验证新增的「历史存储 + 按 Tab 筛选」接口。

先把服务跑起来（另开一个终端）：
    .\.venv\Scripts\python.exe -m uvicorn main:app --port 8000

再跑本脚本：
    .\.venv\Scripts\python.exe test_history.py
"""

from __future__ import annotations

import json
import os
import sys

import requests

# 默认测 8000；想测别的端口就设环境变量 QUIPUS_BASE
BASE = os.getenv("QUIPUS_BASE", "http://127.0.0.1:8000")

SAMPLES = [
    "【淘宝网】亲爱的会员，您购买的羽绒服已由顺丰速运发货，运单号SF12345678，请注意查收。",
    "【菜鸟驿站】您的顺丰包裹已到达学校南门驿站，取件码 5-2-3008，请于20:00前取件。",
    "【京东】您的领券中心掉落一张满199减100元全场通用券，限时2小时领取，点击抢购 https://jd.com/xxx",
    "【招商银行】尊贵的信用卡客户，您的本期账单金额 3,250.00 元，最后还款日为 10月25日，请按时还款。",
    "【图书馆】读者您好，您借阅的《深入浅出计算机组成原理》将于明天到期，请及时归还或登录系统续借。",
]


def jp(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def main() -> int:
    # 0) 健康检查
    try:
        r = requests.get(f"{BASE}/", timeout=5)
        print("[0] 健康检查 ->", r.json())
    except requests.RequestException as exc:
        print("服务没起来：", exc)
        print("先在另一个终端跑：. \\.venv\\Scripts\\python.exe -m uvicorn main:app --port 8000")
        return 1

    # 1) 清空历史，从干净状态开始
    r = requests.delete(f"{BASE}/api/history", timeout=10)
    print("[1] 清空历史 ->", r.json())

    # 2) 灌 5 条通知进去
    print("\n[2] 逐条调用 /api/clean（会真的调大模型，稍等）")
    for i, text in enumerate(SAMPLES, 1):
        r = requests.post(f"{BASE}/api/clean", json={"text": text}, timeout=120)
        if r.status_code != 200:
            print(f"    #{i} HTTP {r.status_code} -> {r.text[:200]}")
            continue
        body = r.json()
        d = body.get("processed_result", {})
        print(
            f"    #{i} id={body.get('id')}  "
            f"category={d.get('category')!r}  is_urgent={d.get('is_urgent')}  "
            f"app_name={d.get('app_name')!r}"
        )

    # 3) 逐个 tab 拉历史
    print("\n[3] 按 tab 拉历史")
    for tab in ("overview", "blocked", "express", "urgent"):
        r = requests.get(f"{BASE}/api/history", params={"tab": tab}, timeout=10)
        body = r.json()
        print(f"    tab={tab:9s} -> HTTP {r.status_code}  命中 {body.get('count')} 条")
        for it in body.get("items", []):
            print(f"         #{it['id']} [{it['data'].get('category')}] {it['data'].get('title')}")

    # 4) 统计
    r = requests.get(f"{BASE}/api/stats", timeout=10)
    print("\n[4] 统计 ->", jp(r.json()))

    # 5) 关键词搜索
    r = requests.get(f"{BASE}/api/history", params={"q": "顺丰"}, timeout=10)
    print(f"\n[5] 搜索 '顺丰' -> 命中 {r.json().get('count')} 条")

    # 6) 非法 tab 应该报 400
    r = requests.get(f"{BASE}/api/history", params={"tab": "xxx"}, timeout=10)
    print(f"[6] 非法 tab=xxx -> HTTP {r.status_code}（期望 400）: {r.json().get('detail')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
