"""离线替身的理财申购/赎回判定（2026-11-01 用户实测：「点订购没反应」）。

理财卡上的「订购」按钮发的是 `买 {产品名} {金额} 元`（`wealth_ui._card`），
而 `OFFLINE_RULES` 里只有 `("理财", "推荐")` —— 这句话没有任何关键词命中，
落到 `out_of_scope`，界面上就是按钮点了没反应，只多一条「没太理解您的意思」。
"""
from __future__ import annotations

import pytest

from agent import orchestrator
from app.cli import offline_llm, offline_verdict


def test_buy_button_sentence_is_wealth_buy() -> None:
    intent, slots = offline_verdict("买 黄金 ETF 联接 10000 元")
    assert intent == "wealth_buy"
    assert slots["product"] == "黄金 ETF 联接"
    assert slots["amount"] == 10_000


def test_amount_prefers_currency_not_days_in_product_name() -> None:
    """产品名里带「365 天」，不能把 365 当成申购金额。"""
    intent, slots = offline_verdict("买红利优选 365 天 10000 元")
    assert intent == "wealth_buy"
    assert slots["amount"] == 10_000
    assert slots["product"] == "红利优选"


@pytest.mark.parametrize("text", ["申购稳健增利 5000 元", "我要买 5000 元 稳健增利"])
def test_buy_words_are_recognised(text: str) -> None:
    assert offline_verdict(text)[0] == "wealth_buy"


def test_redeem_is_its_own_intent() -> None:
    intent, slots = offline_verdict("赎回黄金 ETF 联接 2000 元")
    assert intent == "wealth_redeem"
    assert slots["amount"] == 2_000


@pytest.mark.parametrize("text", ["我买了哪些理财", "推荐理财产品", "理财风险测评"])
def test_queries_are_not_hijacked_by_buy(text: str) -> None:
    assert offline_verdict(text)[0] != "wealth_buy"


def test_orchestrator_routes_order_button_to_wealth_buy(seeded) -> None:
    """按钮发出去的那句话，编排层必须认成 wealth_buy（不是 out_of_scope）。"""
    with offline_llm():
        turn = orchestrator.handle("买 黄金 ETF 联接 10000 元", session_id="offline-wealth-1")
    assert turn.intent == "wealth_buy"
    assert turn.intent != "out_of_scope"


#: 2026-11-01 用户实测：点侧边栏「我的理财」却出的是**推荐**页。
#: 场景按钮发的原话就是「我买了哪些理财」——含「理财」二字，被泛理财规则抢走。
@pytest.mark.parametrize("text", ["我买了哪些理财", "我的理财持仓", "我持有多少理财"])
def test_holdings_sentences_are_not_recommendations(text: str) -> None:
    intent, _ = offline_verdict(text)
    assert intent == "wealth_holdings", f"「{text}」被判成了 {intent}"


def test_recommendation_still_wins_for_recommend_words() -> None:
    assert offline_verdict("推荐理财产品")[0] == "wealth_recommend"


def test_orchestrator_renders_holdings_for_my_wealth_scene(seeded) -> None:
    with offline_llm():
        turn = orchestrator.handle("我买了哪些理财", session_id="offline-wealth-2")
    assert turn.intent == "wealth_holdings"
    assert "持有" in turn.reply                       # 持仓回执，不是推荐列表

