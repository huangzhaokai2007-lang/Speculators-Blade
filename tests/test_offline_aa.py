"""离线替身的群收款名单（2026-11-01 用户实测：「向李四发起 aa 收款」，名单却是王五/赵六）。

根因：`OFFLINE_RULES` 把演示名单**写死**进规则槽位
（`{"payee_ids": ["王五", "赵六"], "amounts": "王五 100、赵六 200"}`），
用户点谁都不影响结果 —— 界面上永远只有王五和赵六。
"""
from __future__ import annotations

import pytest

from agent import orchestrator
from app.cli import offline_llm, offline_verdict


@pytest.mark.parametrize("text, names", [
    ("向李四发起aa收款", ["李四"]),
    ("跟王五和赵六一起AA", ["王五", "赵六"]),
    ("拉上张小美、赵六群收款", ["张小美", "赵六"]),
    ("找赵六AA", ["赵六"]),
])
def test_participants_come_from_the_sentence(text: str, names: list[str]) -> None:
    intent, slots = offline_verdict(text)
    assert intent == "aa_collect"
    assert slots["payee_ids"] == names


def test_no_name_falls_back_to_demo_pair() -> None:
    """完全没点名时才用演示名单，界面不至于空着。"""
    intent, slots = offline_verdict("AA收款")
    assert intent == "aa_collect"
    assert slots["payee_ids"] == ["王五", "赵六"]


def test_stated_total_is_carried_over() -> None:
    intent, slots = offline_verdict("向李四发起AA 300元")
    assert intent == "aa_collect"
    assert slots["amount"] == 300.0


def test_orchestrator_uses_my_participant(seeded) -> None:
    with offline_llm():
        turn = orchestrator.handle("向李四发起aa收款", session_id="offline-aa-1")
    assert turn.intent == "aa_collect"
    # 库里有两位「李四」→ 先追问是哪一位，但**名单来自我这句话**，不是写死的王五/赵六
    assert "李四" in turn.reply and "王五" not in turn.reply
