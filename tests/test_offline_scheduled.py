"""离线替身的定时转账判定（2026-11-01 用户实测：「定时转账被转账覆盖」）。

回归点有两个，缺一个就会重现：
1. `OFFLINE_RULES` 里原本没有 `transfer_scheduled`，任何带「转」的话都被 (`"转",`) 截成即时转账；
2. 编排层会往分类文本尾部追加「（当前日期：2026-09-12）」—— 时间词判定若不去掉这个尾巴，
   **每一笔**普通转账都会命中日期，全被误判成定时转账（第一版就是这么错的）。
"""
from __future__ import annotations

import pytest

from agent import orchestrator
from app.cli import offline_llm, offline_verdict


@pytest.mark.parametrize("text", [
    "给王五转100",
    "转账",
    "给王五转 100 元",                     # 无时间词 → 即时转账
])
def test_plain_transfer_stays_single(text: str) -> None:
    intent, _ = offline_verdict(text)
    assert intent == "transfer_single", f"「{text}」被判成了 {intent}"


@pytest.mark.parametrize("text, expect_schedule", [
    ("明天9点给王五转100", "2026-11-02T09:00"),
    ("后天 10 点给王五转 100 元", "2026-11-03T10:00"),
])
def test_relative_time_goes_scheduled(text: str, expect_schedule: str) -> None:
    intent, slots = offline_verdict(text)
    assert intent == "transfer_scheduled"
    assert slots["payee"] == "王五" and slots["amount"] == 100.0
    assert slots["schedule"].startswith(expect_schedule[:10])   # 日期对；时刻按相对时间解析


def test_cycle_words_fill_repeat() -> None:
    intent, slots = offline_verdict("每周一给王五转50")
    assert intent == "transfer_scheduled"
    assert slots.get("repeat") == "每周一"      # 循环说法原样交给 repeat_cycle 归一


def test_time_words_without_transfer_is_not_scheduled() -> None:
    intent, _ = offline_verdict("明天有空吗")
    assert intent != "transfer_scheduled"


def test_orchestrator_injected_date_does_not_flip_plain_transfer(seeded) -> None:
    """编排层追加的「（当前日期：…）」不许把普通转账翻成定时转账。"""
    with offline_llm():
        turn = orchestrator.handle("给王五转100", session_id="offline-sched-1")
    assert turn.intent == "transfer_single"


def test_orchestrator_routes_scheduled_to_its_own_flow(seeded) -> None:
    with offline_llm():
        turn = orchestrator.handle("明天9点给王五转100", session_id="offline-sched-2")
    assert turn.intent == "transfer_scheduled"
    assert "定时转账" in turn.reply
