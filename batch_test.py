r"""批量测试队长的 clean_notification_text —— 看每条通知是不是都能"完美识别"。

用法：
    cd C:\Quipus-Backend
    .\.venv\Scripts\python.exe batch_test.py          # 全部跑
    .\.venv\Scripts\python.exe batch_test.py 3        # 只跑前 3 条（省额度，先试水）

数据文件 test_data.txt 的格式（一行一条）：
    期望分类 | 通知原文        ← 推荐，能顺便检查分类对不对
    通知原文                   ← 也行，只是没有分类核对

队长函数的固定输出（这 5 个字段）：
    app_name / category / title / summary / is_urgent
"""

from __future__ import annotations

import json
import sys
import time
import unicodedata
from pathlib import Path

# 队长的文件，只调用不改
from test_ai import clean_notification_text

# 这 5 个字段前端 index.html 会真正用到，缺一个都算不合格
REQUIRED_KEYS = ["app_name", "category", "title", "summary", "is_urgent"]

# 前端约定的三种分类
VALID_CATEGORIES = ["重要/紧急待办", "物流与消费", "无效广告/促销"]

FALLBACK = [
    "【教务处】重要通知：关于本周五下午全校停水检修的紧急通知，请同学们提前做好准备。",
    "【淘宝网】亲爱的会员，您购买的羽绒服已由顺丰速运发货，运单号SF12345678，请注意查收。",
    "【京东】您的领券中心掉落一张满199减100元全场通用券，限时2小时领取，点击抢购 https://jd.com/xxx",
]

# ---------------------------------------------------------------------------
# 读测试数据
# ---------------------------------------------------------------------------
DATA_FILE = Path(__file__).with_name("test_data.txt")
items: list[tuple[str | None, str]] = []

if DATA_FILE.exists():
    for line in DATA_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            exp, _, txt = line.partition("|")
            items.append((exp.strip() or None, txt.strip()))
        else:
            items.append((None, line))
    print(f"[数据] 来自 test_data.txt，共 {len(items)} 条")
else:
    items = [(None, t) for t in FALLBACK]
    print(f"[数据] 没找到 test_data.txt，用脚本内置的 {len(items)} 条样例")

if len(sys.argv) > 1:
    try:
        items = items[: int(sys.argv[1])]
        print(f"[数据] 命令行限制：只跑前 {len(items)} 条")
    except ValueError:
        pass

print("[函数] 使用 test_ai.clean_notification_text()")
print("=" * 100)


# ---------------------------------------------------------------------------
# 对齐工具（中文算 2 格，否则表格会歪）
# ---------------------------------------------------------------------------
def _w(s: str) -> int:
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))


def pad(s: object, n: int) -> str:
    s = str(s)
    if _w(s) > n:
        out = ""
        for c in s:
            if _w(out) + _w(c) > n - 1:
                break
            out += c
        s = out + "…"
    return s + " " * max(0, n - _w(s))


def val(d: object, k: str) -> str:
    if not isinstance(d, dict):
        return "-"
    v = d.get(k)
    return "-" if v in (None, "", [], {}) else v


def cat_match(expected: str | None, actual: object) -> str:
    """宽松比对：'重要/紧急待办' 和 '待办' 也算对得上。"""
    if expected is None:
        return "—"
    if not actual:
        return "❌"
    e, a = expected.strip(), str(actual).strip()
    if e == a or e in a or a in e:
        return "✅"
    for kw in ("待办", "物流", "消费", "广告", "促销"):
        if kw in e and kw in a:
            return "△"
    return "❌"


# ---------------------------------------------------------------------------
# 逐条跑
# ---------------------------------------------------------------------------
results: list[dict] = []

for i, (expected, text) in enumerate(items, start=1):
    print(f"[{i}/{len(items)}] {text[:44]}{'…' if len(text) > 44 else ''}")
    t0 = time.time()
    try:
        data = clean_notification_text(text)
        err = None
    except Exception as exc:
        data, err = None, f"{type(exc).__name__}: {exc}"
    cost = time.time() - t0

    if err:
        status, missing = "❌ 报错", list(REQUIRED_KEYS)
    elif not isinstance(data, dict):
        status, missing = "❌ 非字典", list(REQUIRED_KEYS)
    else:
        missing = [k for k in REQUIRED_KEYS if data.get(k) in (None, "", [], {})]
        status = "❌ 缺字段" if missing else "✅ 五字段齐全"

    match = cat_match(expected, (data or {}).get("category") if isinstance(data, dict) else None)
    actual_cat = val(data, "category")
    illegal = isinstance(data, dict) and data.get("category") not in VALID_CATEGORIES

    results.append(
        {
            "序号": i,
            "原文": text,
            "期望分类": expected,
            "实际分类": actual_cat,
            "分类匹配": match,
            "耗时秒": round(cost, 1),
            "状态": status,
            "解析结果": data,
            "错误": err,
            "缺失字段": missing,
        }
    )

    flag = "" if not illegal else "   ← 分类不在约定的三种里！"
    print(
        f"         -> {status} ｜ 分类 {match}（期望 {expected or '—'} / 实际 {actual_cat}）"
        f" ｜ is_urgent={val(data, 'is_urgent')} ｜ {cost:.1f} 秒{flag}"
    )
    time.sleep(0.4)

# ---------------------------------------------------------------------------
# 汇总表
# ---------------------------------------------------------------------------
print("=" * 100)
print("【分类核对 + 关键字段】")
print(
    pad("#", 4) + pad("状态", 16) + pad("期望分类", 16) + pad("实际分类", 18)
    + pad("匹配", 8) + pad("is_urgent", 11) + pad("app_name", 12) + "title"
)
print("-" * 100)
for r in results:
    d = r["解析结果"]
    print(
        pad(r["序号"], 4) + pad(r["状态"], 16) + pad(r["期望分类"] or "—", 16)
        + pad(r["实际分类"], 18) + pad(r["分类匹配"], 8) + pad(val(d, "is_urgent"), 11)
        + pad(val(d, "app_name"), 12) + pad(val(d, "title"), 30)
    )
print("-" * 100)

ok = sum(1 for r in results if r["状态"].startswith("✅"))
bad = sum(1 for r in results if r["状态"].startswith("❌"))
print(f"字段完整度：共 {len(results)} 条 ｜ ✅ 五个字段齐全 {ok} 条 ｜ ❌ 有问题 {bad} 条")

has_exp = [r for r in results if r["期望分类"]]
if has_exp:
    c_ok = sum(1 for r in has_exp if r["分类匹配"] == "✅")
    c_fz = sum(1 for r in has_exp if r["分类匹配"] == "△")
    c_bad = sum(1 for r in has_exp if r["分类匹配"] == "❌")
    print(
        f"分类准确度：共 {len(has_exp)} 条有期望值 ｜ ✅ 完全一致 {c_ok} 条"
        f" ｜ △ 沾边 {c_fz} 条 ｜ ❌ 不一致 {c_bad} 条"
    )

urgent = sum(
    1 for r in results if isinstance(r["解析结果"], dict) and r["解析结果"].get("is_urgent") is True
)
print(f"判定为紧急（is_urgent=true）的：{urgent} 条")

illegal = [
    r for r in results
    if isinstance(r["解析结果"], dict) and r["解析结果"].get("category") not in VALID_CATEGORIES
]
if illegal:
    print(f"\n⚠️ 有 {len(illegal)} 条的 category 不在约定的三种里（前端会渲染错位）：")
    for r in illegal:
        print(f"   #{r['序号']} 实际返回：{r['实际分类']!r}")

if bad:
    print("\n【有问题的条目】")
    for r in results:
        if r["状态"].startswith("❌"):
            print(f"  #{r['序号']} {r['状态']}  原因：{r['错误'] or ('缺 ' + '/'.join(r['缺失字段']))}")
            print(f"      原文：{r['原文']}")

out = Path(__file__).with_name("batch_result.json")
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n完整结果已存到：{out}")
