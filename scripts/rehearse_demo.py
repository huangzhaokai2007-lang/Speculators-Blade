"""演示前的全链路彩排（答辩/评审前跑一遍）。

和 `pytest` 的分工：
- 单测管「算得对不对」（数字口径、边界、失败路径）；
- 这里管「**演示会不会卡住**」——页面有没有异常、按钮在不在、点下去到不到该到的状态。

覆盖莫负责的 7 个功能：F10 测评 / F11 推荐 / F12 申购 / F13 赎回 / F19 列表 / F04 取消 / F18 提醒。

用法：

```bash
PYTHONPATH=$PWD python scripts/rehearse_demo.py
```

退出码 0 = 可以上台；非 0 = 有环节断了，看上面 ❌ 那几行。
"""
from __future__ import annotations

import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data import dao                      # noqa: E402
from data.seed import generate            # noqa: E402

fails: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'✅' if ok else '❌'} {label}{('  ' + detail) if detail else ''}")
    if not ok:
        fails.append(label)


def main() -> int:
    db = ROOT / "var" / f"rehearse_{int(time.time())}.db"
    generate(db)
    dao.connect_db(db)
    os.environ["DB_PATH"] = str(db)

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "interfaces/web/app.py"), default_timeout=180).run()
    check("首屏无异常", not at.exception, str([e.message for e in at.exception][:1]))
    check("订阅提醒条存在", any("订阅提醒" in m.value for m in at.markdown))

    # ── F10 测评 → 一键进推荐 ────────────────────────────────
    #: 侧边栏入口随时可能被调整（PR #137 就打算摘掉「风险程度」），
    #: 所以这里两条路都试：有按钮点按钮，没有就从对话触发 —— 同一个意图、同一条路径。
    entry = [b for b in at.sidebar.button if b.label == "风险程度"]
    if entry:
        entry[0].click().run()
        check("风险程度页打开（侧边栏入口）", not at.exception)
    else:
        at.chat_input[0].set_value("做风险测评").run()
        check("风险程度页打开（对话入口）", not at.exception)
    next(b for b in at.button if b.label == "开始风险测评").click().run()
    for box in at.selectbox:
        box.set_value(box.options[-1])
    for num in at.number_input:
        num.set_value(50)
    next(b for b in at.button if b.label == "提交测评").click().run()
    check("测评提交无异常", not at.exception, str([e.message for e in at.exception][:1]))
    check("结果卡出现", any("测评结果" in m.value or "可买范围" in m.value for m in at.markdown))
    recommend = [b for b in at.button if "适合我的产品" in b.label]
    check("「看看适合我的产品」按钮在", bool(recommend))

    # ── F11 推荐 + 期限筛选 + F12 申购 ──────────────────────
    if recommend:
        recommend[0].click().run()
        turn = at.session_state["turns"][-1]["turn"]
        items = (turn.get("facts") or {}).get("items") or []
        check("进入推荐页", turn.get("intent") == "wealth_recommend", f"{len(items)} 只")
        check("推荐卡有订购按钮", sum(b.label == "订购" for b in at.button) > 0,
              f"{sum(b.label == '订购' for b in at.button)} 个")

        term = [r for r in at.radio if "全部" in str(r.options)]
        if term:
            term[0].set_value("1 年内").run()
            check("期限筛选可用", not at.exception)

        order = [b for b in at.button if b.label == "订购"]
        if order:
            order[0].click().run()
            states = at.session_state["turns"][-1]["turn"].get("states") or []
            check("订购进入确认卡", "CONFIRM_CARD" in states)

    # ── F19 持仓 + F13 赎回 ─────────────────────────────────
    next(b for b in at.sidebar.button if b.label == "我的理财").click().run()
    check("我的理财无异常", not at.exception, str([e.message for e in at.exception][:1]))
    check("组合曲线渲染", len(at.get("vega_lite_chart")) >= 1)
    check("累计收益在页面上", any("累计收益" in m.value for m in at.markdown))
    redeem = [b for b in at.button if b.label == "赎回"]
    check("赎回按钮在", bool(redeem), f"{len(redeem)} 个")
    if redeem:
        redeem[0].click().run()
        turn = at.session_state["turns"][-1]["turn"]
        # 点按钮只带产品、不带金额 → 应该追问金额（CLARIFY），这是设计如此
        check("赎回先追问金额",
              turn.get("intent") == "wealth_redeem" and "CLARIFY" in (turn.get("states") or []),
              str(turn.get("states")[-3:]))

    # ── F04 取消订阅 ────────────────────────────────────────
    next(b for b in at.sidebar.button if b.label == "管订阅").click().run()
    check("订阅列表无异常", not at.exception)
    cancel = [b for b in at.button if b.label.startswith("取消")]
    check("取消按钮在", bool(cancel), f"{len(cancel)} 个")
    if cancel:
        cancel[0].click().run()
        turn = at.session_state["turns"][-1]["turn"]
        check("取消进入确认卡",
              turn.get("intent") == "subscription_cancel"
              and "CONFIRM_CARD" in (turn.get("states") or []),
              str(turn.get("states")[-3:]))

    print()
    print("=" * 52)
    if fails:
        print(f"彩排结论：{len(fails)} 项未通过 → {fails}")
        return 1
    print("彩排结论：全部通过，可以上台")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
