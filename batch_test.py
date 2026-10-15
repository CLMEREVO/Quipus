r"""批量测试队长的清洗函数 —— 看每条通知是不是都能"完美识别"。

用法：
    cd C:\Quipus-Backend
    .\.venv\Scripts\python.exe batch_test.py          # 全部跑
    .\.venv\Scripts\python.exe batch_test.py 3        # 只跑前 3 条（省额度，先试水）

数据文件 test_data.txt 的格式（一行一条）：
    期望分类 | 通知原文        ← 推荐，能顺便检查分类对不对
    通知原文                   ← 也行，只是没有分类核对

输出：
    - 表 A：分类核对（期望 vs 实际）
    - 表 B：字段提取情况
    - 完整结果存到 batch_result.json
"""

from __future__ import annotations

import json
import sys
import time
import unicodedata
from pathlib import Path

import importlib

# ---------------------------------------------------------------------------
# 1. 找队长的清洗函数
#    模块名可能是 test_ai（团队约定的名字）也可能是 cleaner，函数名也可能不一样，
#    这里全部自动试一遍，找到就用，不用你手动改。
# ---------------------------------------------------------------------------
clean_fn = None
_used = ""

for _mod_name in ("test_ai", "cleaner"):
    try:
        _mod = importlib.import_module(_mod_name)
    except ImportError:
        continue
    for _fn_name in ("clean_notification_text", "process_notification", "clean_text"):
        if hasattr(_mod, _fn_name):
            clean_fn = getattr(_mod, _fn_name)
            _used = f"{_mod_name}.{_fn_name}"
            break
    if clean_fn:
        break

if clean_fn is None:
    sys.exit(
        "× 找不到清洗函数。请确认 test_ai.py（或 cleaner.py）就在本文件夹里，"
        "且里面有 clean_notification_text 这个函数。"
    )

# 这 5 个字段每条都必须有值（= 前端 index.html 真正会读的字段）
REQUIRED_KEYS = ["app_name", "title", "category", "is_urgent", "summary"]
# 这 3 个可以为 null（通知里本来就可能没写）
OPTIONAL_KEYS = ["deadline", "location", "contact"]

# 前端约定的三种分类，出现别的就说明提示词没约束住
VALID_CATEGORIES = ["重要/紧急待办", "物流与消费", "无效广告/促销"]

FALLBACK = [
    "【教务处】重要通知：关于本周五下午全校停水检修的紧急通知，请同学们提前做好准备。",
    "【淘宝网】亲爱的会员，您购买的羽绒服已由顺丰速运发货，运单号SF12345678，请注意查收。",
    "【京东】您的领券中心掉落一张满199减100元全场通用券，限时2小时领取，点击抢购 https://jd.com/xxx",
]

# ---------------------------------------------------------------------------
# 2. 读测试数据
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

print(f"[函数] 使用 {_used}()")
print("=" * 96)


# ---------------------------------------------------------------------------
# 3. 对齐工具（中文算 2 格，否则表格会歪）
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
# 4. 逐条跑
# ---------------------------------------------------------------------------
results: list[dict] = []

for i, (expected, text) in enumerate(items, start=1):
    print(f"[{i}/{len(items)}] {text[:44]}{'…' if len(text) > 44 else ''}")
    t0 = time.time()
    try:
        data = clean_fn(text)
        err = None
    except Exception as exc:
        data, err = None, f"{type(exc).__name__}: {exc}"
    cost = time.time() - t0

    if err:
        status, miss_req, miss_opt = "❌ 报错", list(REQUIRED_KEYS), []
    elif not isinstance(data, dict):
        status, miss_req, miss_opt = "❌ 非字典", list(REQUIRED_KEYS), []
    else:
        miss_req = [k for k in REQUIRED_KEYS if data.get(k) in (None, "", [], {})]
        miss_opt = [k for k in OPTIONAL_KEYS if data.get(k) in (None, "", [], {})]
        # ○ 不是错误：通知里本来就可能没有截止时间/地点/联系人
        status = "❌ 缺必填" if miss_req else ("✅ 全字段都有" if not miss_opt else "○ 可选为空")

    match = cat_match(expected, (data or {}).get("category") if isinstance(data, dict) else None)
    actual_cat = val(data, "category")
    cat_illegal = isinstance(data, dict) and data.get("category") not in VALID_CATEGORIES

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
            "必填字段缺失": miss_req,
            "可选字段为空": miss_opt,
        }
    )

    flag = "" if not cat_illegal else "   ← 分类不在约定的三种里！"
    print(f"         -> {status} ｜ 分类 {match}（期望 {expected or '—'} / 实际 {actual_cat}）｜ {cost:.1f} 秒{flag}")
    time.sleep(0.4)

# ---------------------------------------------------------------------------
# 5. 表 A：分类核对
# ---------------------------------------------------------------------------
print("=" * 96)
print("【表 A】分类核对")
print(pad("#", 4) + pad("期望分类", 16) + pad("实际分类", 18) + pad("匹配", 8) + pad("is_urgent", 12) + "app_name / title")
print("-" * 96)
for r in results:
    d = r["解析结果"]
    print(
        pad(r["序号"], 4) + pad(r["期望分类"] or "—", 16) + pad(r["实际分类"], 18)
        + pad(r["分类匹配"], 8) + pad(val(d, "is_urgent"), 12)
        + pad(val(d, "app_name"), 12) + pad(val(d, "title"), 26)
    )

# ---------------------------------------------------------------------------
# 6. 表 B：字段提取
# ---------------------------------------------------------------------------
print()
print("【表 B】字段提取情况（- 表示该字段为 null）")
print(pad("#", 4) + pad("状态", 16) + pad("deadline", 14) + pad("location", 14) + pad("contact", 18) + "summary")
print("-" * 96)
for r in results:
    d = r["解析结果"]
    print(
        pad(r["序号"], 4) + pad(r["状态"], 16) + pad(val(d, "deadline"), 14)
        + pad(val(d, "location"), 14) + pad(val(d, "contact"), 18) + pad(val(d, "summary"), 34)
    )
print("-" * 96)

# ---------------------------------------------------------------------------
# 7. 统计
# ---------------------------------------------------------------------------
ok = sum(1 for r in results if r["状态"].startswith("✅"))
opt = sum(1 for r in results if r["状态"].startswith("○"))
bad = sum(1 for r in results if r["状态"].startswith("❌"))

has_exp = [r for r in results if r["期望分类"]]
cat_ok = sum(1 for r in has_exp if r["分类匹配"] == "✅")
cat_fuzzy = sum(1 for r in has_exp if r["分类匹配"] == "△")
cat_bad = sum(1 for r in has_exp if r["分类匹配"] == "❌")
illegal = [r for r in results if isinstance(r["解析结果"], dict)
           and r["解析结果"].get("category") not in VALID_CATEGORIES]

print(f"字段完整度：共 {len(results)} 条 ｜ ✅ 七个字段全都有 {ok} 条 ｜ ○ 可选字段为空 {opt} 条 ｜ ❌ 有问题 {bad} 条")
print("  说明：○ 不是错误 —— 通知里本来就可能没有截止时间/地点/联系人，模型填 null 是对的。")

if has_exp:
    print(f"分类准确度：共 {len(has_exp)} 条有期望值 ｜ ✅ 完全一致 {cat_ok} 条 ｜ △ 沾边 {cat_fuzzy} 条 ｜ ❌ 不一致 {cat_bad} 条")

if illegal:
    print(f"\n⚠️ 有 {len(illegal)} 条的 category 不在约定的三种里（前端会渲染错位）：")
    for r in illegal:
        print(f"   #{r['序号']} 实际返回：{r['实际分类']!r}")

if bad:
    print("\n【有问题的条目】")
    for r in results:
        if r["状态"].startswith("❌"):
            print(f"  #{r['序号']} {r['状态']}  原因：{r['错误'] or ('缺 ' + '/'.join(r['必填字段缺失']))}")
            print(f"      原文：{r['原文']}")

out = Path(__file__).with_name("batch_result.json")
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n完整结果已存到：{out}")
