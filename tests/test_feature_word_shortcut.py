"""整句只有一个功能名时，规则层直接归口 —— 8501 上实测「流水」「定时转账」被判 out_of_scope。"""
import pytest

from agent.conversation_language import feature_intent


@pytest.mark.parametrize('text,intent', [
    ('流水', 'txn_query'),
    ('我的流水', 'txn_query'),
    ('那么我的流水呢', 'txn_query'),
    ('看看流水', 'txn_query'),
    ('查一下交易记录', 'txn_query'),
    ('定时转账', 'transfer_scheduled'),
    ('帮我看看定时转账', 'transfer_scheduled'),
    ('转账', 'transfer_single'),
    ('余额', 'balance_query'),
    ('我的银行卡', 'card_query'),
    ('收款人', 'payee_list'),
    ('理财', 'wealth_recommend'),
    ('风险测评', 'risk_assess'),
    ('账单总结', 'bill_report'),
    ('消费账单', 'bill_analysis'),
    ('订阅', 'subscription_list'),
    ('异常交易', 'anomaly_check'),
])
def test_feature_word_maps_to_intent(text, intent):
    assert feature_intent(text) == intent


@pytest.mark.parametrize('text', [
    '给王五转100元',          # 带收款人/金额：交给模型抽槽位，不能被「转账」截走
    '上个月花了多少',
    '明天给张三转两百',
    '今天天气怎么样',
    '',
])
def test_longer_or_unrelated_utterances_are_left_alone(text):
    assert feature_intent(text) is None
