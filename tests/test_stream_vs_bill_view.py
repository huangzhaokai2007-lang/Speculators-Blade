"""流水与账单是两张皮：说「流水」→ 先挑**流水**时间段，选完再出走势图＋逐笔明细；
说「账单」→ 走账单分析（分类占比），两边都不许出现对方的入口。

2026-11-01 用户实测反馈：问「看看我的流水」时系统追问「请补充起始日期、结束日期」，
页面底下还挂着「选择账单时间段」。本文件锁住修好后的行为：
`interfaces/web/slot_form_ui._txn_range_picker`（流水时间段卡面）＋
`interfaces/web/legacy_bill_ui.render`（最新一轮是流水就不挂账单时间段选择器）。

跑 `app_offline.py`：关键词替身只认意图、不填日期，正好覆盖「没给时间」这条真实路径，
工具层 / 权限 / 渲染全是真链路。
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO / "scripts"))

import demo                                                        # noqa: E402

APP = REPO / "interfaces" / "web" / "app_offline.py"


def _last_month() -> tuple[str, str]:
    """默认时间段：`min(真实今天, 数据集今天)` 的上一个完整月（独立算一遍，防自证）。"""
    from data.seed import AS_OF

    ref = min(date.today(), AS_OF)
    last = ref.replace(day=1) - timedelta(days=1)
    return last.replace(day=1).isoformat(), last.isoformat()


def _app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setenv("DB_PATH", str(demo.build_temp_db()))
    at = AppTest.from_file(str(APP), default_timeout=90).run()
    assert not at.exception
    return at


def _page(at: AppTest) -> str:
    return " ".join(str(item.value) for item in at.markdown)


def _turn(at: AppTest) -> dict:
    return at.session_state["messages"][-1]["turn"] or {}


def test_stream_asks_for_range_first_then_renders_detail_card(monkeypatch):
    """「看看我的流水」→ 先给「选择流水时间段」，选完才出走势图＋逐笔明细。"""
    at = _app(monkeypatch)
    at.chat_input[0].set_value("看看我的流水").run()
    assert not at.exception

    page = _page(at)
    assert "选择流水时间段" in page, "流水没给时间段卡面"
    assert "选择账单时间段" not in page, "流水页面上不该出现账单时间段选择器"
    assert any(b.key == "txn-range-go" for b in at.button)
    assert "逐笔明细" not in page, "还没选时间段就把明细画出来了"

    # 默认区间 = 上一个完整自然月；可选上限 = 今天
    expect_from, expect_to = _last_month()
    assert at.date_input(key="txn-range-start").value == date.fromisoformat(expect_from)
    assert at.date_input(key="txn-range-end").value == date.fromisoformat(expect_to)

    at.button(key="txn-range-go").click().run()
    assert not at.exception

    turn = _turn(at)
    assert turn["intent"] == "txn_query" and not turn["error_code"]
    assert turn["facts"]["date_from"] == expect_from
    assert turn["facts"]["date_to"] == expect_to

    page = _page(at)
    assert "逐笔明细" in page, "选完时间段没出流水明细卡"
    assert len(turn["facts"].get("daily") or []) >= 2, "按日走势画不出来（daily 不足两天）"
    assert "选择流水时间段" not in page, "选完之后卡面应该收起"


def test_selected_range_drives_both_header_and_chart(monkeypatch):
    """挑 8 月上半月 → 回执区间、明细、走势都按这段时间来。"""
    at = _app(monkeypatch)
    at.chat_input[0].set_value("我的流水").run()
    at.date_input(key="txn-range-start").set_value(date(2026, 8, 1))
    at.date_input(key="txn-range-end").set_value(date(2026, 8, 15))
    at.button(key="txn-range-go").click().run()
    assert not at.exception

    turn = _turn(at)
    assert turn["facts"]["date_from"] == "2026-08-01"
    assert turn["facts"]["date_to"] == "2026-08-15"
    assert "2026-08-01 至 2026-08-15" in (turn.get("reply") or "")
    daily = turn["facts"]["daily"]
    assert daily and all("2026-08-01" <= item["date"] <= "2026-08-15" for item in daily)


def test_bill_query_still_uses_bill_view(monkeypatch):
    """「看看我8月的账单」仍是账单分析（分类占比），不会被流水卡顶掉。"""
    at = _app(monkeypatch)
    at.chat_input[0].set_value("看看我8月的账单").run()
    assert not at.exception

    turn = _turn(at)
    assert turn["intent"] == "bill_analysis" and not turn["error_code"]
    assert turn["facts"]["period"] == "2026-08"
    page = _page(at)
    assert "逐笔明细" not in page, "账单分析不该出流水明细卡"
    assert "选择流水时间段" not in page, "账单页面上不该出现流水时间段卡面"
