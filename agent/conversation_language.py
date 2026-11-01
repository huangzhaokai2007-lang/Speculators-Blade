"""Narrow, deterministic short answers; business validation remains in existing flows."""
import re

from agent import classifier, pending_slots, scene_language
from agent.period import resolve_day


#: 整句就是一个**功能名**时的归口表：顺序敏感，具体的排前面。
#: 2026-11-01（用户在 8501 实测）：真实模型对「流水」「定时转账」这类**只有功能名**的短句
#: 直接给 out_of_scope，回一句「没太理解您的意思」—— 离线替身（`app/cli.OFFLINE_RULES`）
#: 有关键词表所以从没暴露；评委现场第一句就是这种说法。规则层补一张同口径的表，不再问模型。
FEATURE_WORDS: tuple[tuple[str, str], ...] = (
    (r'定时转账|预约转账|定期转账|自动转账|循环转账', 'transfer_scheduled'),
    (r'账单总结|账单报告|月账单', 'bill_report'),
    (r'风险测评|测评问卷|测评|风险评估', 'risk_assess'),
    (r'收款人|白名单', 'payee_list'),
    (r'异常交易|异常支出|异常消费|可疑交易|异常|可疑', 'anomaly_check'),
    (r'消费账单|账单分析|对账单|账单', 'bill_analysis'),
    (r'订阅|自动续费', 'subscription_list'),
    (r'理财产品|理财推荐|理财|风险等级', 'wealth_recommend'),
    (r'账户余额|余额', 'balance_query'),
    (r'流水明细|流水记录|交易记录|交易明细|收支明细|流水|明细', 'txn_query'),
    (r'转账|汇款|打钱', 'transfer_single'),
    (r'我的银行卡|银行卡|我的卡|卡片列表|卡片', 'card_query'),
)
#: 功能名前后常见的口头语缀（「那我的流水呢」「帮我看看定时转账」）
_FEATURE_PREFIX = re.compile(r'^(?:麻烦|帮我|给我|我要|我想|想看看|想看|看看|看一下|看|'
                             r'查一下|查查|查|那么|那|然后|所以|再|'
                             r'来一份|来|做个|做一个|一个|一份|我的)+\s*')
_FEATURE_SUFFIX = re.compile(r'\s*(?:呢|吧|啊|呗|嘛|的|了|一下|怎么弄|在哪|在哪儿|有哪些|在哪看)+$')


def feature_intent(text: object) -> str | None:
    """整句只有一个功能名 → 直接给意图（不带槽位：缺什么由编排层接着问/给卡面）。

    只认「整句就是这个功能名」，不做子串匹配 —— 否则「给王五转 100 元」会被「转账」截走，
    收款人和金额就丢了。
    """
    raw = str(text or '').strip().rstrip('。？！?!').strip()
    if not raw:
        return None
    core = _FEATURE_SUFFIX.sub('', _FEATURE_PREFIX.sub('', raw)).strip()
    if not core:
        return None
    for pattern, intent in FEATURE_WORDS:
        if re.fullmatch(pattern, core):
            return intent
    return None


def understand(text: str, session: str) -> classifier.IntentOut | None:
    raw = str(text or '').strip().rstrip('。？！?!').strip()
    item = pending_slots.peek(session)
    intent, slots = '', {}
    if item and item['intent'] in ('anomaly_check', 'bill_report', 'bill_analysis'):
        decision = scene_language.plan(raw, {'intent': item['intent']}) or {}
        period = decision.get('slots', {}).get('period')
        if period:
            intent, slots = item['intent'], {**item['slots'], 'period': period}
    if item and item['intent'] == 'transfer_single':
        amount = re.fullmatch(r'(?:金额(?:是|为)?|转)?\s*(\d+(?:\.\d{1,2})?)\s*(?:元|块钱|块)?', raw)
        payee = re.fullmatch(r'(?:收款人(?:是|为)|给)\s*([^，,。！？!?\s]{1,20})', raw)
        if amount and 'amount' in item['missing']:
            intent, slots = item['intent'], {**item['slots'], 'amount': amount[1]}
        elif payee and 'payee' in item['missing']:
            intent, slots = item['intent'], {**item['slots'], 'payee': payee[1]}
    if item and item['intent'] == 'txn_query':
        start, end = resolve_day(raw, edge='start'), resolve_day(raw, edge='end')
        if start and end:
            dates = {key: value for key, value in (('date_from', start), ('date_to', end))
                     if key in item['missing']}
            intent, slots = item['intent'], {**item['slots'], **dates}
    return classifier.IntentOut(intent=intent, confidence=1, slots=slots) if intent else None


def colloquial(text: str) -> classifier.IntentOut | None:
    """Only handle a whole, unambiguous utterance after contextual reference resolution."""
    raw = str(text or '').strip().rstrip('。？！?!').strip()
    intent, slots = '', {}
    # Leave negation, questions and scheduling to the contextual/model classifier.
    if re.search(r'不要|不想|别|取消|怎么|如何|能否|可不可以|明天|后天|下周|下月|月底|定时|预约|每[天周月年]|\d+[年月日号点:]|[一二三四五六七八九十]+[点月日号]', raw):
        return None
    transfer = re.fullmatch(r'(?:麻烦|帮我)?(?:给|向)([^，,。！？!?\s]{1,20}?)\s*(?:转账|转钱|打钱|汇款|转|打)\s*(\d+(?:\.\d{1,2})?)\s*(?:元|块钱|块)(?:吧|呗)?', raw)
    informal = re.search(r'^(?:麻烦|帮我)|转钱|打钱|汇款|打\s*\d|块|呗$', raw)
    if transfer and informal and transfer[1] not in ('他', '她', '它', '这位', '这个人', '那个人', '对方') and not transfer[1].startswith('第'):
        intent, slots = 'transfer_single', {'payee': transfer[1], 'amount': transfer[2]}
    if not intent and re.fullmatch(r'(?:麻烦|帮我|我要|我想|我想要)?\s*(?:转账|转钱|打钱|汇款)(?:吧|呗)?', raw):
        intent = 'transfer_single'
    if not intent and raw in ('帮我瞅瞅还剩多少钱', '我卡里还有多少啊', '查下余额呗',
                               '瞅瞅余额', '还有多少余额', '查下余额', '余额还有多少'):
        intent = 'balance_query'
    #: 2026-11-01（用户在 8501 上实测）：只说「流水」「那么我的流水呢」时，
    #: 真实模型判成 out_of_scope，回一句「没太理解您的意思」—— 评委现场第一句就会撞上。
    #: 这类**整句就是一个账目词**的说法在规则层直接归口，不再问模型（离线替身早就这么干）。
    if not intent and re.fullmatch(r'(?:那|那么|然后|所以|再)?\s*(?:我|我的)?\s*'
                                   r'(?:想|要|想看|想看看|看看|看一下|看|查|查一下|查查)?\s*'
                                   r'(?:我的)?\s*(?:流水|流水明细|流水记录|交易记录|交易明细|收支明细|明细)'
                                   r'(?:呢|吧|啊|呗|嘛)?', raw):
        intent = 'txn_query'
    if not intent:
        return None
    return classifier.IntentOut(intent=intent, confidence=1, slots=slots)
