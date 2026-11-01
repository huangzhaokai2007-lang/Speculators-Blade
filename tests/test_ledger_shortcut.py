"""只说话账目词也要接住：8501 上实测「流水」被判 out_of_scope。"""
import pytest

from agent.conversation_language import colloquial


@pytest.mark.parametrize('text', ['流水', '我的流水', '那么我的流水呢', '看看流水',
                                  '看看我的流水', '查一下交易记录', '流水明细呢'])
def test_bare_ledger_word_maps_to_txn_query(text):
    out = colloquial(text)
    assert out is not None, text
    assert out.intent == 'txn_query'
    assert not out.slots          # 不带日期 → 界面先出「选择流水时间段」


@pytest.mark.parametrize('text', ['我想看看我的消费账单', '上个月花了多少', '流水账单怎么取消'])
def test_ledger_shortcut_does_not_swallow_bill_or_scheduling(text):
    out = colloquial(text)
    assert out is None or out.intent != 'txn_query'
