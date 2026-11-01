"""「下次扣费」按今天顺延（2026-11-01 用户实测：在订的 4 条全是 9/10 月的过去日期）。

合成库是静态快照 —— `data/seed.py` 里写死的扣费日搁几周就全成过去时，
列表里没有一条「即将扣费」，还会被标成逾期。改为**读取时**按周期顺延，
库不动、快照不烂。
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from tools import subscription


def _now_as(monkeypatch: pytest.MonkeyPatch, moment: datetime) -> None:
    monkeypatch.setattr(subscription, "_now", lambda: moment)


def test_dates_are_unchanged_when_still_in_the_future(seeded, monkeypatch) -> None:
    """时钟停在 2026-09-12 时，种子里的日期本来就都在未来 —— 不许被改动。"""
    _now_as(monkeypatch, datetime(2026, 9, 12, 12, 0, 0))
    items = subscription.list_subscriptions().data["items"]
    assert [i["next_charge_date"] for i in items] == ["2026-09-18", "2026-09-25",
                                                      "2026-10-02", "2026-10-08"]


def test_stale_dates_roll_forward_by_cycle(seeded, monkeypatch) -> None:
    _now_as(monkeypatch, datetime(2026, 11, 1, 9, 0, 0))
    items = {i["merchant"]: i for i in subscription.list_subscriptions().data["items"]}
    assert items["云音乐"]["next_charge_date"] == "2026-11-18"          # 每月 18 号
    assert items["星辰视频"]["next_charge_date"] == "2026-11-25"        # 每月 25 号
    assert items["云端网盘"]["next_charge_date"] == "2026-11-02"        # 每月 2 号（明天）
    assert items["好买会员"]["next_charge_date"] == "2027-10-08"        # 每年 10-08


def test_rolled_dates_are_all_today_or_later(seeded, monkeypatch) -> None:
    today = date(2026, 11, 1)
    _now_as(monkeypatch, datetime(2026, 11, 1, 9, 0, 0))
    result = subscription.list_subscriptions()
    for item in result.data["items"]:
        assert date.fromisoformat(item["next_charge_date"]) >= today


def test_rolling_does_not_create_phantom_overdue(seeded, monkeypatch) -> None:
    """顺延之后不该再出现「逾期」标注（原来的 AS_OF 口径会把它们全判成逾期）。"""
    _now_as(monkeypatch, datetime(2026, 11, 1, 9, 0, 0))
    facts = subscription.list_subscriptions().facts
    assert all("days_overdue" not in item for item in facts["items"])


def test_cancelled_subscriptions_keep_their_history(seeded, monkeypatch) -> None:
    """已取消的是历史事实，顺延会篡改账单 —— 一条都不许动。"""
    _now_as(monkeypatch, datetime(2026, 11, 1, 9, 0, 0))
    items = subscription.list_subscriptions(status="cancelled").data["items"]
    assert items and all(i["next_charge_date"] < "2026-11-01" for i in items)
