from datetime import date
from tests.test_web_insight_card import _app, _text
from agent import card_binding_flow


def test_analysis_phrase_asks_for_range_before_any_chart(monkeypatch):
    """说「我想看看我的消费账单」→ 第一步只有时间段选择，不许先弹饼图（用户实测反馈）。

    分类器对这句话给的是 `bill_analysis`（只问花了多少那种），以前它直接渲染成
    「支出合计 + 饼图 + 接着问」，时间段选择被挤到页面最下面。
    """
    at = _app(monkeypatch)
    calls = []
    original = card_binding_flow.handle

    def handle(text, **kwargs):
        calls.append(text)
        return original(text, **kwargs)

    monkeypatch.setattr(card_binding_flow, 'handle', handle)

    at.chat_input[0].set_value('我想看看我的消费账单').run()
    assert not at.exception, at.exception

    page = _text(at)
    assert '选择账单时间段' in page                       # 第一步：时间段
    assert '支出合计' not in page                        # 不许先出图表
    assert '接着问' not in page                          # 也不许先出追问按钮
    assert not any(b.key == 'bill-range-go' and b.disabled for b in at.button)

    at.date_input(key='bill-range-start').set_value(date(2026, 8, 5))
    at.date_input(key='bill-range-end').set_value(date(2026, 8, 20))
    at.button(key='bill-range-go').click().run()
    assert not at.exception, at.exception
    assert calls[-1] == '2026年8月5日至2026年8月20日的账单报告'


def test_picker_queries_once_and_shows_only_latest_report(monkeypatch):
    at = _app(monkeypatch)
    calls = []
    original = card_binding_flow.handle
    def handle(text, **kwargs):
        calls.append(text)
        return original(text, **kwargs)
    monkeypatch.setattr(card_binding_flow, 'handle', handle)
    next(b for b in at.button if b.label == '看账单').click().run()
    assert not calls
    assert not any((m.get('turn') or {}).get('intent') == 'bill_report' for m in at.session_state['messages'])
    for start, end in [(date(2026, 8, 5), date(2026, 8, 20)), (date(2026, 7, 25), date(2026, 8, 10))]:
        at.date_input(key='bill-range-start').set_value(start)
        at.date_input(key='bill-range-end').set_value(end)
        at.button(key='bill-range-go').click().run()
        assert not at.exception
        assert not any('这份账单的图表' in e.label for e in at.expander)
        assert not any('拉取近 3 期账单' in b.label for b in at.button)
        assert calls[-1] == f'{start.year}年{start.month}月{start.day}日至{end.year}年{end.month}月{end.day}日的账单报告'
        turn = at.session_state['messages'][-1]['turn']
        assert not turn['error_code']
        assert turn['facts']['period'] == f'{start.isoformat()} 至 {end.isoformat()}'
        assert sum(m.value.count('账单报告 ·') for m in at.markdown) == 1
    assert len(calls) == 2


def test_range_report_totals_use_only_selected_days(monkeypatch):
    from tools import query
    from tests.test_web_insight_card import demo
    monkeypatch.setenv('DB_PATH', str(demo.build_temp_db()))
    for start, end in [('2026-08-05', '2026-08-20'), ('2026-07-25', '2026-08-10')]:
        result = query.generate_bill_report(f'{start} 至 {end}', 'range')
        rows = query._owned_txns(start, end)
        assert result.ok
        assert result.facts['out_sum'] == sum(-r['amount'] for r in rows if r['amount'] < 0)
        assert result.facts['in_sum'] == sum(r['amount'] for r in rows if r['amount'] > 0)
    for period in ['2026-08-20 至 2026-08-05', '2026-02-30 至 2026-03-01']:
        assert not query.generate_bill_report(period, 'range').ok
